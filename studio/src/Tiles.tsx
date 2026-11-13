import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { rpc, RpcError } from './engine'
import { collisions, commitEdits, dirty, extent, movable, pos, snap, stage, type Cell, type Staged } from './tileStage'

interface Variant { breakpoint: number; variant_idx: number; composition: string; composition_info: { preset_w: number; preset_h: number; layout_mode: string; preset_name: string } | null; cells: (Cell & { configs: { layout: string; cfg_index: number; size_w: number; size_h: number }[]; h_align: string; v_align: string })[] }
interface SetInfo { set_name: string; host: { layout: string }; variants: Variant[] }
interface Screen { panel_id: string; layout: string; area: string; sets: SetInfo[] }
interface StoredEdit { id: string; composition: string; cell_index: number; cell_element_id: string; geometry: { x: number; y: number; w: number; h: number } | null; old: { geometry: { x: number; y: number } }; state: string; reasons?: string[] }
interface Check { blocks: string[]; warnings: string[]; collisions: unknown[] }
const UNIT = 36
const BP = ['XS', 'S', 'Standard', 'Large', 'XL', 'Phone']

/** Tile layout editor: the grid compositions of a screen as a canvas, one breakpoint at a time. Drag a cell (or type x and y) to stage a move; positions
 *  only, a cell's size comes from its configs. Commit stores the moves as placement edits; a bundle build writes them (bundle target). */
export default function Tiles({ project, target, onChanged, say }: { project: string | null; target: string; onChanged: () => void; say: (s: string) => void }) {
  const [state, setState] = useState<any>(null)
  const [q, setQ] = useState('')
  const [screens, setScreens] = useState<{ panel_id: string; area: string; tiles: number }[]>([])
  const [screen, setScreen] = useState<Screen | null>(null)
  const [vi, setVi] = useState<string>('')                      // "<set index>:<variant index>"
  const [staged, setStaged] = useState<Staged>({})
  const [sel, setSel] = useState<number | null>(null)
  const [stored, setStored] = useState<StoredEdit[]>([])
  const [checks, setChecks] = useState<Record<number, Check>>({})
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const drag = useRef<{ i: number; sx: number; sy: number; from: { x: number; y: number } } | null>(null)
  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) }, [say])

  const loadState = useCallback(() => rpc<any>('layout.state').then(setState).catch(fail), [fail])
  useEffect(() => { loadState() }, [loadState])
  useEffect(() => {
    if (!state?.present) return
    const t = setTimeout(() => rpc<{ screens: { panel_id: string; area: string; tiles: number }[] }>('layout.screens', { q }).then((r) => setScreens(r.screens.filter((s) => s.tiles > 0))).catch(fail), 200)
    return () => clearTimeout(t)
  }, [state?.present, q, fail])
  const loadStored = useCallback(async () => { if (project) try { setStored((await rpc<{ edits: StoredEdit[] }>('placement.list', { project })).edits) } catch (e) { fail(e) } }, [project, fail])
  useEffect(() => { loadStored() }, [loadStored])

  const choose = async (panel: string) => {
    try {
      const s = await rpc<Screen>('layout.screen', { panel }); setScreen(s); setStaged({}); setSel(null); setChecks({}); setErr('')
      const first = s.sets.findIndex((x) => x.variants.length); setVi(first >= 0 ? `${first}:0` : '')
    } catch (e) { fail(e) }
  }
  const variant: Variant | null = useMemo(() => { if (!screen || !vi) return null; const [a, b] = vi.split(':').map(Number); return screen.sets[a]?.variants[b] ?? null }, [screen, vi])
  const cells = variant?.cells ?? []
  const info = variant?.composition_info
  const preset = info && info.preset_w > 0 && info.preset_h > 0 ? { w: info.preset_w, h: info.preset_h } : null
  const ext = extent(cells, preset, staged)
  const coll = collisions(cells, staged)
  const moved = dirty(cells, staged)
  const storedFor = (i: number) => stored.find((e) => variant && e.composition === variant.composition && e.cell_index === i)
  const cellsKey = variant?.composition

  const check = useCallback(async (c: Cell, p: { x: number; y: number }) => {
    if (!project || !variant) return
    try { const r = await rpc<Check>('placement.check', { project, edit: { composition: variant.composition, cell_index: c.cell_index, geometry: { x: p.x, y: p.y, w: c.w, h: c.h } } }); setChecks((k) => ({ ...k, [c.cell_index]: r })) } catch (e) { fail(e) }
  }, [project, variant, fail])

  const move = (c: Cell, p: { x: number; y: number }) => {
    setStaged((s) => stage(s, c, p)); check(c, p)
    if (p.x === c.x && p.y === c.y) setChecks((k) => { const n = { ...k }; delete n[c.cell_index]; return n })
  }
  const onDown = (ev: React.PointerEvent, c: Cell) => {
    setSel(c.cell_index)
    if (!movable(c) || !project) return
    ;(ev.target as Element).setPointerCapture?.(ev.pointerId)
    drag.current = { i: c.cell_index, sx: ev.clientX, sy: ev.clientY, from: pos(c, staged) }
  }
  const onMove = (ev: React.PointerEvent, c: Cell) => {
    const d = drag.current
    if (!d || d.i !== c.cell_index) return
    const p = snap(c, d.from, ev.clientX - d.sx, ev.clientY - d.sy, UNIT, ext.cols, ext.rows)
    const cur = pos(c, staged)
    if (p.x !== cur.x || p.y !== cur.y) setStaged((s) => stage(s, c, p))
  }
  const onUp = (_: React.PointerEvent, c: Cell) => { const d = drag.current; drag.current = null; if (d && d.i === c.cell_index) check(c, pos(c, staged)) }

  const blocks = moved.flatMap((i) => checks[i]?.blocks ?? [])
  const commit = async () => {
    if (!project || !variant || !moved.length) return
    if (coll.length && !confirm(`Cells ${coll.join(', ')} overlap. Overlap can be intentional layering; store the moves anyway?`)) return
    setBusy(true); setErr('')
    try {
      for (const e of commitEdits(variant.composition, cells, staged)) await rpc('placement.add', { project, edit: e, confirm: true })
      say(`stored ${moved.length} position edit(s) for ${variant.composition}`); setStaged({}); setChecks({}); await loadStored(); onChanged()
    } catch (e) { fail(e) } finally { setBusy(false) }
  }
  const revertStored = async (id: string) => { try { await rpc('placement.remove', { project, id }); await loadStored(); onChanged() } catch (e) { fail(e) } }
  const selCell = cells.find((c) => c.cell_index === sel)

  return (
    <div className="tiles">
      <div className="head">TILE LAYOUT</div>
      {err && <div className="warn pad">{err}</div>}
      {target !== 'bundles' && project && <div className="warn pad">This project's target is <b>{target}</b>: position edits are written only by a bundle build.</div>}
      {!state && <div className="dim pad">Loading ...</div>}
      {state && !state.present && <div className="pad">No layout index is imported yet. <button onClick={async () => { setBusy(true); try { const r = await rpc<any>('layout.export_index'); say(`layout index loaded: ${r.crosscheck.compositions} compositions, ${r.crosscheck.cells} cells checked against the bundles`); await loadState() } catch (e) { fail(e) } finally { setBusy(false) } }} disabled={busy}>Load the layout index</button></div>}
      {state?.present && state.staleness.status !== 'fresh' && <div className="warn pad">The imported layout index is <b>{state.staleness.status}</b>: {state.staleness.message || 'edits are not accepted'}</div>}
      {state?.present && <>
        <input className="search" placeholder="Filter screens (panel id) ..." value={q} onChange={(e) => setQ(e.target.value)} />
        {!screen && <ul className="llist">{screens.map((s) => <li key={s.panel_id} onClick={() => choose(s.panel_id)}>{s.panel_id}<small> {s.area}</small></li>)}</ul>}
        {screen && <>
          <div className="pad"><button onClick={() => { setScreen(null); setStaged({}) }}>← screens</button> <b>{screen.panel_id}</b> <small className="dim">{screen.area}</small></div>
          <div className="pad"><select value={vi} onChange={(e) => { setVi(e.target.value); setStaged({}); setSel(null); setChecks({}) }}>
            {screen.sets.flatMap((s, a) => s.variants.map((v, b) => <option key={`${a}:${b}`} value={`${a}:${b}`}>{s.host.layout} · {s.set_name.replace(/CompositionSet$/, '')} · {BP[v.breakpoint] ?? 'bp' + v.breakpoint}{v.variant_idx ? ' #' + v.variant_idx : ''}</option>))}
          </select></div>
          {variant && <>
            <div className="pad dim small">{variant.composition} · grid {ext.cols} × {ext.rows}{preset ? '' : ' (no preset size: taken from the cells)'} · 1 unit = {UNIT}px</div>
            <div className="canvas">
              <svg width={ext.cols * UNIT + 2} height={ext.rows * UNIT + 2} role="img" aria-label="grid composition">
                {Array.from({ length: ext.cols + 1 }, (_, i) => <line key={'v' + i} x1={i * UNIT + 1} y1={1} x2={i * UNIT + 1} y2={ext.rows * UNIT + 1} className="gl" />)}
                {Array.from({ length: ext.rows + 1 }, (_, i) => <line key={'h' + i} x1={1} y1={i * UNIT + 1} x2={ext.cols * UNIT + 1} y2={i * UNIT + 1} className="gl" />)}
                {cells.map((c) => {
                  const p = pos(c, staged), isMoved = moved.includes(c.cell_index), bad = (checks[c.cell_index]?.blocks.length ?? 0) > 0, hit = coll.includes(c.cell_index)
                  return (
                    <g key={c.cell_index} transform={`translate(${p.x * UNIT + 1},${p.y * UNIT + 1})`} onPointerDown={(e) => onDown(e, c)} onPointerMove={(e) => onMove(e, c)} onPointerUp={(e) => onUp(e, c)}
                      className={'tcell' + (sel === c.cell_index ? ' sel' : '') + (isMoved ? ' moved' : '') + (bad ? ' bad' : '') + (hit ? ' hit' : '') + (movable(c) ? '' : ' fixed')} data-testid={'cell-' + c.cell_index}>
                      <rect width={c.w * UNIT} height={c.h * UNIT} rx={3} />
                      <text x={6} y={16}>{c.cell_index}: {c.element_id.slice(0, Math.max(4, c.w * 5))}</text>
                      <text x={6} y={c.h * UNIT - 6} className="dim">{p.x},{p.y} · {c.w}×{c.h}{movable(c) ? '' : c.flags.includes('locked') ? ' · locked' : ' · auto'}</text>
                    </g>)
                })}
              </svg>
            </div>
            {selCell && <div className="pad cellbox">
              <b>{selCell.element_id}</b> <small className="dim">cell {selCell.cell_index}</small>
              <div className="row">x <input type="number" min={0} value={pos(selCell, staged).x} disabled={!movable(selCell) || !project} onChange={(e) => move(selCell, { ...pos(selCell, staged), x: Math.max(0, Number(e.target.value) | 0) })} />
                y <input type="number" min={0} value={pos(selCell, staged).y} disabled={!movable(selCell) || !project} onChange={(e) => move(selCell, { ...pos(selCell, staged), y: Math.max(0, Number(e.target.value) | 0) })} />
                <span className="dim small" title="A cell's size is derived from its configs (4,724 of 5,162 cells); only the position is editable.">w {selCell.w} h {selCell.h} (fixed)</span></div>
              <div className="dim small">min {selCell.min_w}×{selCell.min_h} · max {selCell.max_w || '∞'}×{selCell.max_h || '∞'} · flags {selCell.flags.join(', ') || 'none'} · align {selCell.h_align}/{selCell.v_align}</div>
              {selCell.configs.length > 0 && <div className="dim small">configs: {selCell.configs.map((k) => `${k.cfg_index}: ${k.layout} ${k.size_w}×${k.size_h}`).join(' · ')}</div>}
              {storedFor(selCell.cell_index) && <div className="small">stored edit: {storedFor(selCell.cell_index)!.state}</div>}
            </div>}
            <div className="pad">
              <b>Validation</b>
              {!moved.length && <div className="dim small">Drag a cell to stage a move.</div>}
              {moved.map((i) => <div key={i} className="small">cell {i}: {(checks[i]?.blocks ?? []).map((b, k) => <div key={k} className="bad">blocked: {b}</div>)}{(checks[i]?.warnings ?? []).map((w, k) => <div key={'w' + k} className="warnline">{w}</div>)}{checks[i] && !checks[i].blocks.length && !checks[i].warnings.length && <span className="ok">ok</span>}</div>)}
              {coll.length > 0 && <div className="warnline small">Overlap: cells {coll.join(', ')}</div>}
              <div className="ctl"><button className="primary" disabled={!project || !moved.length || blocks.length > 0 || busy || state.staleness.status !== 'fresh'} onClick={commit}>Store {moved.length || ''} edit(s)</button>
                <button disabled={!moved.length} onClick={() => { setStaged({}); setChecks({}) }}>Revert</button></div>
              {!project && <div className="dim small">Open a project to store edits.</div>}
            </div>
          </>}
          {stored.length > 0 && <div className="pad"><b>Stored edits ({stored.length})</b>{stored.map((e) => <div key={e.id} className="small mono">{e.composition.slice(-34)} / {e.cell_element_id}: {e.old.geometry.x},{e.old.geometry.y} → {e.geometry ? `${e.geometry.x},${e.geometry.y}` : 'config'} <span className={e.state === 'valid' ? 'ok' : 'bad'}>{e.state}</span> <a onClick={() => revertStored(e.id)}>revert</a></div>)}</div>}
        </>}
      </>}
      <span hidden>{cellsKey}</span>
    </div>
  )
}
