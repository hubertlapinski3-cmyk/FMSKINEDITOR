// SKIN-RR1/RR2: Read-only third-party skin inspector.
// Diffs a chosen skin folder against stock bundles via `skin.inspect`, attaches changes
// to parent screens (grouping breakpoint & mode variants), defaults to the screen with the
// most changes, surfaces full-name tooltips without truncation, and shows a Source note.
// Strictly read-only: no Apply, Install, Save, or Write path exists here.

import { useEffect, useMemo, useState } from 'react'
import { rpc, RpcError } from './engine'

interface DiffItem {
  bundle: string
  kind: 'added' | 'removed' | 'changed'
  type: string
  name: string
  field_count?: number
  source_label?: string
  variant?: string | null
  via?: string | null
  unmapped_reason?: string | null
  derived?: boolean
}

interface SkinInspectReport {
  skin_dir: string
  stock_dir: string
  source?: { name: string; version: string; label: string }
  default_screen?: string | null
  screen_meta?: Record<string, { count: number; variants: string[] }>
  totals: { bundles: number; added: number; removed: number; changed: number; unchanged: number }
  by_category: Record<string, { added: number; removed: number; changed: number }>
  by_screen: Record<string, Record<string, DiffItem[]>>
  compositions: { name: string; bundle: string; kind: string; screen: string; variant?: string | null; summary?: any }[]
  bundles: { bundle: string; status: string; counts: { added: number; removed: number; changed: number; unchanged: number } }[]
}

const NOT_TIED = 'Not tied to a screen'

interface PreviewHost {
  space: string
  order: number
  element_id: string
  x: number
  y: number
  w: number
  h: number
  rect?: number[] | null
}

interface SkinPreview {
  composition: string
  source: string
  engine: string
  confidence?: { label?: string }
  viewport?: { width: number; height: number; mode?: string; information_display?: string; text_scaling?: string }
  design: { cols: number; rows: number }
  grid: { cols: number; rows: number }
  cells: PreviewHost[]
  slots: PreviewHost[]
  problems: string[]
}

const CAT_GROUPS: { id: string; label: string; cats: string[] }[] = [
  { id: 'all', label: 'All', cats: [] },
  { id: 'composition', label: 'Composition', cats: ['composition', 'composition_set'] },
  { id: 'tiles', label: 'Tiles', cats: ['element_set'] },
  { id: 'sizes', label: 'Sizes', cats: ['description'] },
  { id: 'styles', label: 'Styles', cats: ['style'] },
  { id: 'uxml', label: 'UXML', cats: ['uxml'] },
  { id: 'tables', label: 'Tables', cats: ['table_factory', 'table_view'] },
  { id: 'navigation', label: 'Navigation', cats: ['navigation'] },
  { id: 'textures', label: 'Textures', cats: ['texture'] },
]

export default function SkinInspect({ say, onOpenGameLayout }: { say: (s: string) => void; onOpenGameLayout?: (comp: string) => void }) {
  const [folder, setFolder] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [report, setReport] = useState<SkinInspectReport | null>(null)
  const [catFilter, setCatFilter] = useState('all')
  const [screenQ, setScreenQ] = useState('')
  const [selectedScreen, setSelectedScreen] = useState<string | null>(null)
  const [selectedVariant, setSelectedVariant] = useState<string>('all')
  const [preview, setPreview] = useState<SkinPreview | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewErr, setPreviewErr] = useState('')

  const rankScreens = (r: SkinInspectReport, cats: Set<string> | null, q: string) => {
    const ql = q.trim().toLowerCase()
    const out: { name: string; count: number; variants: string[]; untied: boolean }[] = []
    for (const [scr, byCat] of Object.entries(r.by_screen || {})) {
      if (ql && !scr.toLowerCase().includes(ql)) continue
      let count = 0
      const vset = new Set<string>(r.screen_meta?.[scr]?.variants || [])
      for (const [cat, items] of Object.entries(byCat)) {
        if (!cats || cats.has(cat)) {
          count += items.length
          for (const it of items) {
            if (it.variant) vset.add(it.variant)
          }
        }
      }
      if (count > 0) {
        out.push({ name: scr, count, variants: Array.from(vset).sort(), untied: scr === NOT_TIED })
      }
    }
    return out.sort((a, b) => {
      if (a.untied !== b.untied) return a.untied ? 1 : -1
      return b.count - a.count || a.name.localeCompare(b.name)
    })
  }

  const runInspect = async () => {
    const target = folder.trim()
    if (!target || busy) return
    setBusy(true); setErr(''); setPreview(null); setPreviewErr(''); setSelectedVariant('all')
    try {
      const r = await rpc<SkinInspectReport>('skin.inspect', { folder: target })
      setReport(r)
      const ranked = rankScreens(r, null, '')
      const pick = r.default_screen && ranked.some((s) => s.name === r.default_screen)
        ? r.default_screen
        : (ranked[0]?.name ?? null)
      setSelectedScreen(pick)
      say(`inspected skin (${r.totals.bundles} bundles: ${r.totals.changed} changed, ${r.totals.added} added, ${r.totals.removed} removed)`)
    } catch (e) {
      const m = e instanceof RpcError ? e.message : String(e)
      setErr(m)
    } finally {
      setBusy(false)
    }
  }

  const pickFolder = async () => {
    if ('__TAURI_INTERNALS__' in window) {
      try {
        const { open } = await import('@tauri-apps/plugin-dialog')
        const r = await open({ directory: true, multiple: false, title: 'Pick a third-party skin folder to inspect (read-only)' })
        if (typeof r === 'string') setFolder(r)
        return
      } catch { /* fallback to input */ }
    }
    const p = prompt('Path to third-party skin folder (read-only):', folder)?.trim()
    if (p) setFolder(p)
  }

  const previewComposition = async (compName: string) => {
    if (!report || previewBusy) return
    setPreviewBusy(true); setPreviewErr('')
    try {
      const p = await rpc<SkinPreview>('skin.preview_composition', { folder: report.skin_dir, composition: compName })
      setPreview(p)
    } catch (e) {
      setPreviewErr(e instanceof RpcError ? e.message : String(e))
    } finally {
      setPreviewBusy(false)
    }
  }

  const activeCats = useMemo(() => {
    const g = CAT_GROUPS.find((x) => x.id === catFilter)
    return g && g.cats.length ? new Set(g.cats) : null
  }, [catFilter])

  const screens = useMemo(() => {
    if (!report) return []
    return rankScreens(report, activeCats, screenQ)
  }, [report, activeCats, screenQ])

  useEffect(() => {
    if (!screens.length) {
      if (selectedScreen !== null) setSelectedScreen(null)
      return
    }
    if (!selectedScreen || !screens.some((s) => s.name === selectedScreen)) {
      setSelectedScreen(screens[0].name)
      setSelectedVariant('all')
    }
  }, [screens, selectedScreen])

  const selectedVariants = useMemo(() => {
    if (!report || !selectedScreen) return []
    const byCat = report.by_screen[selectedScreen] || {}
    const vset = new Set<string>()
    for (const [cat, items] of Object.entries(byCat)) {
      if (activeCats && !activeCats.has(cat)) continue
      for (const it of items) {
        if (it.variant) vset.add(it.variant)
      }
    }
    return Array.from(vset).sort()
  }, [report, selectedScreen, activeCats])

  const currentItems = useMemo(() => {
    if (!report || !selectedScreen) return []
    const byCat = report.by_screen[selectedScreen] || {}
    const out: { cat: string; items: DiffItem[] }[] = []
    for (const [cat, items] of Object.entries(byCat)) {
      if (activeCats && !activeCats.has(cat)) continue
      const filtered = selectedVariant === 'all'
        ? items
        : items.filter((it) => (it.variant || 'Base') === selectedVariant)
      if (filtered.length) out.push({ cat, items: filtered })
    }
    return out
  }, [report, selectedScreen, activeCats, selectedVariant])

  const sourceLabel = useMemo(() => {
    if (!report) return 'Inspected skin'
    return report.source?.label || report.source?.name || report.skin_dir.split(/[\\/]/).filter(Boolean).pop() || 'Inspected skin'
  }, [report])

  const previewTiles = useMemo(() => {
    if (!preview) return []
    return [...(preview.cells || []), ...(preview.slots || [])]
  }, [preview])

  const UNIT = 34

  return (
    <div className="skininspect" data-testid="skin-inspect">
      <div className="skininspect-top">
        <b>Inspect skin</b>
        <span className="badge st dim">read-only</span>
        <input className="search" data-testid="skin-inspect-path" style={{ maxWidth: 460, margin: 0 }}
          placeholder="Folder of a third-party skin (read-only) ..." value={folder}
          onChange={(e) => setFolder(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') runInspect() }} />
        <button type="button" onClick={pickFolder}>Browse ...</button>
        <button type="button" className="primary" data-testid="skin-inspect-run" disabled={!folder.trim() || busy} onClick={runInspect}>
          {busy ? 'Inspecting ...' : 'Inspect'}
        </button>
        <span className="small dim">Compares skin bundles against stock. Never installs or writes game files.</span>
      </div>

      {err && <div className="warn pad small" role="alert" data-testid="skin-inspect-error">{err}</div>}

      {report && <>
        <div className="skininspect-bar" data-testid="skin-inspect-summary">
          <span className="small">
            <span className="skininspect-source" data-testid="skin-inspect-source" title={`Inspected skin folder: ${report.skin_dir}`}>
              Source: {sourceLabel}
            </span>{' '}
            <b>{report.totals.bundles}</b> bundles · <b>{report.totals.changed}</b> changed · <b>{report.totals.added}</b> added · <b>{report.totals.removed}</b> removed · <span className="dim">{report.totals.unchanged} unchanged</span>
          </span>
          <div className="skininspect-cats">
            {CAT_GROUPS.map((g) => (
              <button key={g.id} type="button" data-testid={`skin-cat-${g.id}`}
                className={catFilter === g.id ? 'on' : ''} onClick={() => setCatFilter(g.id)}>
                {g.label}
              </button>
            ))}
          </div>
        </div>

        <div className="skininspect-body">
          <aside className="skininspect-screens">
            <div className="head">SCREENS ({screens.length})</div>
            <input className="search" placeholder="Filter screens ..." value={screenQ} onChange={(e) => setScreenQ(e.target.value)} />
            <ul>
              {screens.map((s) => {
                const tip = `${s.name} · ${s.count} change(s)${s.variants.length ? ' · variants: ' + s.variants.join(', ') : ''}`
                return (
                  <li key={s.name} data-testid="skin-screen-row" data-screen={s.name}
                    title={tip}
                    className={(selectedScreen === s.name ? 'sel ' : '') + (s.untied ? 'untied' : '')}
                    onClick={() => { setSelectedScreen(s.name); setSelectedVariant('all') }}>
                    <div className="skininspect-screen-row-main">
                      <span className="skininspect-screen-name" title={s.name}>{s.name}</span>
                      <small className="dim">{s.count}</small>
                    </div>
                    {s.variants.length > 0 && (
                      <div className="skininspect-variants">
                        {s.variants.slice(0, 6).map((v) => (
                          <span key={v} className="skininspect-var-pill" title={`Variant ${v} under ${s.name}`}>{v}</span>
                        ))}
                        {s.variants.length > 6 && (
                          <span className="skininspect-var-pill" title={s.variants.join(', ')}>+{s.variants.length - 6} more</span>
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
              {!screens.length && <li className="dim">No matching screens.</li>}
            </ul>
          </aside>

          <section className="skininspect-detail">
            {selectedScreen ? <>
              <div className="head" title={selectedScreen}>CHANGES FOR {selectedScreen}</div>
              {selectedVariants.length > 0 && (
                <div className="skininspect-var-bar" data-testid="skin-variant-filter">
                  <button type="button" className={selectedVariant === 'all' ? 'on' : ''} onClick={() => setSelectedVariant('all')}>
                    All variants
                  </button>
                  {selectedVariants.map((v) => (
                    <button key={v} type="button" title={`Filter to variant ${v}`}
                      className={selectedVariant === v ? 'on' : ''} onClick={() => setSelectedVariant(v)}>
                      {v}
                    </button>
                  ))}
                </div>
              )}
              {currentItems.map(({ cat, items }) => (
                <div key={cat} className="skininspect-group" data-testid={`skin-group-${cat}`}>
                  <div className="small"><b>{cat}</b> ({items.length})</div>
                  {items.map((it, idx) => {
                    const itemSource = it.source_label || sourceLabel
                    const fullTip = `${it.name} (${it.type} · ${it.bundle})${it.via ? ' · ' + it.via : ''}${it.unmapped_reason ? ' · ' + it.unmapped_reason : ''} · Source: ${itemSource}`
                    return (
                      <div key={`${it.bundle}:${it.name}:${idx}`} className="skininspect-item small" title={fullTip}>
                        <span className={'badge st ' + (it.kind === 'added' ? 'ok' : it.kind === 'removed' ? 'bad' : 'warn')}>{it.kind}</span>{' '}
                        {it.variant && (
                          <span className="skininspect-var-pill" title={`Variant: ${it.variant}`}>{it.variant}</span>
                        )}
                        <span className="mono" title={it.name}>{it.name}</span>{' '}
                        <span className="dim" title={`${it.type} in ${it.bundle}`}>({it.type} · {it.bundle})</span>{' '}
                        {it.via && <span className="dim" title={`Linked via ${it.via}`}>via {it.via}</span>}
                        {it.unmapped_reason && <span className="warn" title={it.unmapped_reason}>— {it.unmapped_reason}</span>}
                        <span className="skininspect-source" data-testid="skin-item-source" title={`Third-party skin source: ${itemSource}`}>
                          Source: {itemSource}
                        </span>
                        {cat === 'composition' && it.kind !== 'removed' && (
                          <>
                            <button type="button" className="small" data-testid="skin-inspect-preview-btn"
                              data-composition={it.name} disabled={previewBusy}
                              onClick={() => previewComposition(it.name)}>Preview with rea</button>{' '}
                            {onOpenGameLayout && (
                              <button type="button" className="small" onClick={() => onOpenGameLayout(it.name)}>Open stock in Game Layouts</button>
                            )}
                          </>
                        )}
                      </div>
                    )
                  })}
                </div>
              ))}
              {!currentItems.length && <div className="dim small pad">No changes in this category for {selectedScreen}.</div>}
            </> : <div className="dim small pad">Pick a screen on the left to see its changes.</div>}

            {previewErr && <div className="warn pad small">{previewErr}</div>}

            {preview && (
              <div className="skininspect-preview" data-testid="skin-inspect-preview">
                <div className="head">
                  REA RUNTIME PREVIEW · <b>{preview.composition}</b>{' '}
                  <span className="dim">design {preview.design.cols}×{preview.design.rows} → runtime {preview.grid.cols}×{preview.grid.rows} · engine: {preview.engine} · read-only</span>
                </div>
                {preview.problems.length > 0 && (
                  <div className="warn small pad">Runtime checks: {preview.problems.join('; ')}</div>
                )}
                <div className="skininspect-canvas-wrap">
                  <div className="layout-canvas" style={{ width: preview.grid.cols * UNIT + 24, height: preview.grid.rows * UNIT + 24 }}>
                    {previewTiles.map((t) => (
                      <div key={`${t.space}:${t.order}:${t.element_id}`}
                        className={'layout-tile runtime' + (t.h * UNIT < 38 ? ' compact' : '')}
                        data-testid="skin-preview-tile" data-element={t.element_id}
                        title={`${t.element_id} (${t.space}) · runtime x${t.x} y${t.y} ${t.w}×${t.h}${t.rect ? ` · rect [${t.rect.join(', ')}]` : ''}`}
                        style={{ left: 12 + t.x * UNIT, top: 12 + t.y * UNIT, width: Math.max(24, t.w * UNIT - 6), height: Math.max(20, t.h * UNIT - 6) }}>
                        <span className="tile-name mono small">{t.element_id}</span>
                        {t.h * UNIT >= 38 && <small className="dim">x{t.x} y{t.y} · {t.w}×{t.h}</small>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </>}
    </div>
  )
}
