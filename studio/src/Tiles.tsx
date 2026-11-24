import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { pickScreenshot } from './pickImage'
import { rpc, RpcError } from './engine'
import { collisions, commitEdits, dirty, extent, movable, pos, snap, stage, type Cell, type Staged } from './tileStage'
import ReadLayoutDump from './ReadLayoutDump'

interface Variant { breakpoint: number; variant_idx: number; composition: string; composition_info: { preset_w: number; preset_h: number; layout_mode: string; preset_name: string } | null; cells: (Cell & { configs: { layout: string; cfg_index: number; size_w: number; size_h: number }[]; h_align: string; v_align: string })[] }
interface SetInfo { set_name: string; host: { layout: string }; variants: Variant[] }
interface Screen { panel_id: string; layout: string; area: string; sets: SetInfo[] }
interface StoredEdit { id: string; composition: string; cell_index: number; cell_element_id: string; geometry: { x: number; y: number; w: number; h: number } | null; old: { geometry: { x: number; y: number } }; state: string; reasons?: string[] }
interface Check { blocks: string[]; warnings: string[]; collisions: unknown[] }
const UNIT = 36
const BP = ['XS', 'S', 'Standard', 'Large', 'XL', 'Phone']

/** Tile layout editor: the grid compositions of a screen as a canvas, one breakpoint at a time. Drag a cell (or type x and y) to stage a move; positions
 *  only, a cell's size comes from its configs. Commit stores the moves as placement edits; a bundle build writes them (bundle target). */
export default function Tiles({ project, target, expTileSizes = false, onChanged, say }: { project: string | null; target: string; expTileSizes?: boolean; onChanged: () => void; say: (s: string) => void }) {
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
  const [tileTab, setTileTab] = useState<'layout' | 'sizes' | 'sets'>('layout')
  const [descs, setDescs] = useState<{ path_id: string; name: string; id: string; configurations: { width: number; height: number; guid: string }[] }[]>([])
  const [esets, setEsets] = useState<{ path_id: string; name: string; descriptions: { path_id: string; name: string; id: string }[] }[]>([])
  const [dq, setDq] = useState('')
  const [eq, setEq] = useState('')
  const [selDesc, setSelDesc] = useState('')
  const [sizeW, setSizeW] = useState(4)
  const [sizeH, setSizeH] = useState(4)
  const [selSet, setSelSet] = useState('')
  const [addDesc, setAddDesc] = useState('')
  const [tileOps, setTileOps] = useState<any[]>([])
  // a screenshot of the real game behind the grid, to line the tiles up by eye (Advanced only; the pictures live in the workspace, never in a project or a skin)
  const [shots, setShots] = useState<{ name: string; width: number; height: number }[]>([])
  const [shot, setShot] = useState('')
  const [shotUrl, setShotUrl] = useState('')
  const [shotOpacity, setShotOpacity] = useState(0.45)
  const [shotFit, setShotFit] = useState<'stretch' | 'contain'>('stretch')
  useEffect(() => { rpc<{ screens: { name: string; width: number; height: number }[] }>('screens.list').then((r) => setShots(r.screens)).catch(() => {}) }, [])
  useEffect(() => {
    if (!shot) { setShotUrl(''); return }
    let live = true
    rpc<{ content_type: string; base64: string }>('screens.image', { name: shot }).then((r) => { if (live) setShotUrl(`data:${r.content_type};base64,${r.base64}`) }).catch(() => { if (live) { setShotUrl(''); setShot('') } })
    return () => { live = false }
  }, [shot])
  const addShot = async () => {
    try {
      const path = await pickScreenshot(); if (!path) return
      const r = await rpc<{ name: string; width: number; height: number }>('screens.add', { path })
      setShots((l) => [...l.filter((x) => x.name !== r.name), r].sort((a, b) => a.name.localeCompare(b.name))); setShot(r.name); setErr('')
    } catch (e) { fail(e) }
  }
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

  useEffect(() => {
    if (tileTab === 'layout') return
    let live = true
    if (!descs.length) {
      rpc<{ descriptions: typeof descs }>('tiles.descriptions', {}).then((r) => {
        if (!live) return
        setDescs(r.descriptions || [])
        if (!selDesc && r.descriptions?.length) setSelDesc(r.descriptions[0].id || r.descriptions[0].name)
        if (!addDesc && r.descriptions?.length) setAddDesc(r.descriptions[0].id || r.descriptions[0].name)
      }).catch((e) => { if (live) fail(e) })
    }
    if (tileTab === 'sets' && !esets.length) {
      rpc<{ element_sets: typeof esets }>('tiles.element_sets', {}).then((r) => {
        if (!live) return
        setEsets(r.element_sets || [])
        if (!selSet && r.element_sets?.length) setSelSet(r.element_sets[0].name)
      }).catch((e) => { if (live) fail(e) })
    }
    return () => { live = false }
  }, [tileTab])

  const filteredDescs = useMemo(() => {
    const f = dq.trim().toLowerCase()
    return f ? descs.filter((d) => d.id.toLowerCase().includes(f) || d.name.toLowerCase().includes(f)) : descs
  }, [descs, dq])
  const filteredSets = useMemo(() => {
    const f = eq.trim().toLowerCase()
    return f ? esets.filter((s) => s.name.toLowerCase().includes(f)) : esets
  }, [esets, eq])
  const curDesc = descs.find((d) => d.id === selDesc || d.name === selDesc)
  const curSet = esets.find((s) => s.name === selSet)

  const addTileSize = async () => {
    if (!project || !curDesc) return
    setBusy(true); setErr('')
    try {
      const r = await rpc<{ op: any; tile_bundle_ops: any[] }>('tiles.add_size', { project, description: curDesc.id || curDesc.name, width: sizeW, height: sizeH })
      setTileOps(r.tile_bundle_ops || [])
      say(`Staged add-tile-size ${curDesc.id} ${sizeW}x${sizeH}. Click Build bundles, then Install build.`)
      onChanged()
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  const allowTileInSet = async (action: 'add' | 'remove', descId: string) => {
    if (!project || !curSet || !descId) return
    setBusy(true); setErr('')
    try {
      const r = await rpc<{ op: any; tile_bundle_ops: any[] }>('tiles.set_allow', { project, action, element_set: curSet.name, description: descId })
      setTileOps(r.tile_bundle_ops || [])
      say(`Staged set-${action}-tile ${descId} on ${curSet.name}. Click Build bundles, then Install build.`)
      onChanged()
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  return (
    <div className="tiles">
      <div className="head" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>TILE LAYOUT</span>
        <button type="button" className={tileTab === 'layout' ? 'primary' : ''} onClick={() => setTileTab('layout')}>Layout index</button>
        <button type="button" className={tileTab === 'sizes' ? 'primary' : ''} data-testid="tiles-tab-sizes" onClick={() => setTileTab('sizes')}>Tile sizes</button>
        <button type="button" className={tileTab === 'sets' ? 'primary' : ''} data-testid="tiles-tab-sets" onClick={() => setTileTab('sets')}>Allowed tiles</button>
      </div>
      {err && <div className="warn pad">{err}</div>}
      {tileTab === 'sizes' && (
        <div className="pad" data-testid="tiles-sizes-panel">
          <div className="small dim" style={{ marginBottom: 8 }}>Add a new size to an existing TileDescription (reuses an existing UXML GUID). After adding, click <b>Build bundles</b> then <b>Install build</b>.</div>
          {!expTileSizes && <div className="warn" data-testid="tile-sizes-experimental-note" style={{ marginBottom: 8 }}>Experimental (not owner-confirmed in v1.5): enable <b>experimental: tile sizes</b> in the BUILD panel to unlock adding new tile sizes.</div>}
          {!project && <div className="warn" style={{ marginBottom: 8 }}>Open a project first.</div>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
            <input className="search" placeholder="Filter tiles (e.g. Atmosphere) ..." value={dq} onChange={(e) => setDq(e.target.value)} />
            <select data-testid="tile-size-desc" value={selDesc} onChange={(e) => setSelDesc(e.target.value)}>
              {filteredDescs.slice(0, 120).map((d) => <option key={d.path_id} value={d.id || d.name}>{d.id || d.name} ({d.name})</option>)}
            </select>
            <label className="small">W <input data-testid="tile-size-w" type="number" min={1} max={30} value={sizeW} onChange={(e) => setSizeW(Number(e.target.value) || 1)} style={{ width: 52 }} /></label>
            <label className="small">H <input data-testid="tile-size-h" type="number" min={1} max={20} value={sizeH} onChange={(e) => setSizeH(Number(e.target.value) || 1)} style={{ width: 52 }} /></label>
            <button type="button" className="primary" data-testid="tile-size-add" disabled={!project || !curDesc || !expTileSizes || busy} onClick={addTileSize}>Add tile size</button>
          </div>
          {curDesc && <div className="small dim">Existing sizes: {curDesc.configurations.map((c) => `${c.width}×${c.height}`).join(', ') || 'none'}</div>}
          {tileOps.length > 0 && <div className="small mono" style={{ marginTop: 8 }}>Staged bundle ops: {tileOps.map((o) => `${o.op}:${o.description || o.description_id}`).join(', ')}</div>}
        </div>
      )}
      {tileTab === 'sets' && (
        <div className="pad" data-testid="tiles-sets-panel">
          <div className="small dim" style={{ marginBottom: 8 }}>Add or remove an existing TileDescription in a screen’s GridElementSet (e.g. SquadTileSet). After editing, click <b>Build bundles</b> then <b>Install build</b>.</div>
          {!project && <div className="warn" style={{ marginBottom: 8 }}>Open a project first.</div>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
            <input className="search" placeholder="Filter tile sets (e.g. SquadTileSet) ..." value={eq} onChange={(e) => setEq(e.target.value)} />
            <select data-testid="tile-set-select" value={selSet} onChange={(e) => setSelSet(e.target.value)}>
              {filteredSets.map((s) => <option key={s.path_id} value={s.name}>{s.name} ({s.descriptions.length})</option>)}
            </select>
            <select data-testid="tile-set-add-desc" value={addDesc} onChange={(e) => setAddDesc(e.target.value)}>
              {descs.map((d) => <option key={d.path_id} value={d.id || d.name}>{d.id || d.name} ({d.name})</option>)}
            </select>
            <button type="button" className="primary" data-testid="tile-set-add-btn" disabled={!project || !curSet || !addDesc || busy} onClick={() => allowTileInSet('add', addDesc)}>Add tile to set</button>
          </div>
          {curSet && (
            <ul className="llist" style={{ maxHeight: 240, overflow: 'auto' }}>
              {curSet.descriptions.map((d) => (
                <li key={d.path_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{d.id || d.name} <small className="dim">{d.name}</small></span>
                  <button type="button" className="small" disabled={!project || busy} onClick={() => allowTileInSet('remove', d.id || d.name)}>Remove</button>
                </li>
              ))}
            </ul>
          )}
          {tileOps.length > 0 && <div className="small mono" style={{ marginTop: 8 }}>Staged bundle ops: {tileOps.map((o) => `${o.op}:${o.description || o.description_id}`).join(', ')}</div>}
        </div>
      )}
      {tileTab === 'layout' && <>
      {target !== 'bundles' && project && <div className="warn pad">This project's target is <b>{target}</b>: position edits are written only by a bundle build.</div>}
      {!state && <div className="dim pad">Loading ...</div>}
      {state && !state.present && <>
        <ReadLayoutDump say={say} onDone={loadState} detail="This reads the layouts, compositions and tile configs from your own game files; it only reads." />
        {state.index?.configured
          ? <div className="pad">No layout index is imported yet. <button data-testid="load-layout-index" onClick={async () => { setBusy(true); try { const r = await rpc<any>('layout.export_index'); say(`layout index loaded: ${r.crosscheck.compositions} compositions, ${r.crosscheck.cells} cells checked against the bundles`); await loadState() } catch (e) { fail(e) } finally { setBusy(false) } }} disabled={busy}>Load the layout index</button> <span className="dim">Developer cross-check only: FM27_LayoutMCP’s sqlite index.</span></div>
          : <div className="pad" data-testid="layout-index-not-configured">No layout index is imported yet, and none is configured. <span className="dim">{state.index?.help || 'The layout index is built by FM27_LayoutMCP, a developer-only tool that is not shipped with FM27 Skin Studio; set FM27_LAYOUT_INDEX (or layout_index in the workspace config.json) to use the Tiles view.'}</span></div>}
      </>}
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
            <div className="pad shotbar" data-testid="shotbar">
              <label>Game screenshot behind the grid <select aria-label="Game screenshot behind the grid" value={shot} onChange={(e) => setShot(e.target.value)}><option value="">none</option>{shots.map((x) => <option key={x.name} value={x.name}>{x.name} ({x.width}x{x.height})</option>)}</select></label>
              {shot && <>
                <label>Opacity <input type="range" min={0.1} max={1} step={0.05} value={shotOpacity} aria-label="Screenshot opacity" onChange={(e) => setShotOpacity(Number(e.target.value))} /></label>
                <label>Fit <select aria-label="Screenshot fit" value={shotFit} onChange={(e) => setShotFit(e.target.value as 'stretch' | 'contain')}><option value="stretch">stretch to the grid</option><option value="contain">keep its shape</option></select></label>
              </>}
              <button onClick={addShot}>Add a screenshot ...</button>
              <div className="dim small">Screenshots stay on this PC (your workspace's game-screens folder); they are never put in a project or a skin. Lining up is by eye: the grid is the screen's tile area, not the whole window.</div>
            </div>
            <div className="canvas">
              <svg width={ext.cols * UNIT + 2} height={ext.rows * UNIT + 2} role="img" aria-label="grid composition">
                {shotUrl && <image data-testid="shot-image" href={shotUrl} x={1} y={1} width={ext.cols * UNIT} height={ext.rows * UNIT} opacity={shotOpacity} preserveAspectRatio={shotFit === 'stretch' ? 'none' : 'xMidYMid meet'} style={{ pointerEvents: 'none' }} />}
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
      </>}
      <span hidden>{cellsKey}</span>
    </div>
  )
}
