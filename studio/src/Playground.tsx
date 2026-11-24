import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { rpc, RpcError } from './engine'
import { RenderBrowser, labelOf, nodeAt, styleOf, type LayoutRow, type RNode, type RResult } from './Render'
import ReadLayoutDump from './ReadLayoutDump'
import BreakpointSelector from './Breakpoint'

/* Stage 5C: the Visual Playground canvas. The ENGINE owns every decision (the tree, the cascade, the computed
   declarations, the evidence flags); this view adds the interaction the brief asks for: a hierarchy panel with
   two-way selection sync, hover and parent/child outlines, a selected-element bounding box, pan/zoom/fit, and
   diagnostics that separate errors from reconstruction limitations. Like the Render view it extends, the drawing
   is an approximation and says so.

   HIDE/SHOW IS A VIEW TOGGLE, NOT AN OPERATION (review point, 2026-11-18): hiding an element only stops this
   canvas from DRAWING it - React view state, no session write, no engine call, no operation record. A real
   visibility edit is a SetVisibility operation with its own evidence and the runtime-dependent caveat (5B/5E);
   the two must never be confused. The buttons say so on screen and a test asserts no operation is written.

   IDENTITY LIMITATION (owner finding 5, 2026-11-18): this canvas addresses elements by their RENDER path, not by
   the UiDocument identity. The two node sets disagree by design (the UiDocument keeps roots and non-visual
   components and expands without a limit; the render tree drops them and stops 3 includes deep), render nodes
   are identified by layout name + m_Id + a position that counts non-visual siblings, and layout names repeat -
   so a render path is NOT a stable operation address. The reliable join is (bundle, path_id, m_Id) against a
   generalised UiDocument, which today exists only for Team Instructions at Large. Until that join ships, this
   view is an inspection and visualisation surface; operations authored from it carry this limitation.

   THE JOIN (review order 2026-11-18, step 3): where the join IS built - a TOP layout (panel or tile) of a
   composition with a built UiDocument, SquadComposition-Standard included - the engine's `uidoc.join` maps this
   canvas's render positions to UiDocument identity (logical_id, bundle, path_id, m_Id), and this canvas
   addresses elements by THAT identity and says so. Everywhere else the render-path caveat above still stands. */

export interface Diag { level: 'error' | 'limitation'; message: string; path: string | null }

/** One row of the uidoc.join table: the UiDocument identity behind one render position (or its not-drawn state). */
export interface JoinRow { logical_id: string; m_id: string; bundle?: string; path_id?: string; layout?: string; layout_guid?: string; state: string }

/** The engine's uidoc.join answer, reduced to what this canvas consumes. */
export interface JoinResponse {
  joinable: boolean
  composition?: string
  counts?: { joined: number; not_drawn: Record<string, number>; unmatched_doc: string[]; unmatched_render: string[] }
  instances?: { rows: Record<string, JoinRow>; not_drawn: Record<string, JoinRow> }[]
  reason?: string
  cell_configurations?: { cell_index: number; element_id: string; min_size?: { x: number; y: number }; max_size?: { x: number; y: number }; descriptions: { path_id?: string; read?: boolean; name?: string; id?: string; configurations?: { size?: { x: number; y: number }; type?: number; asset_guid?: string; asset_path_id?: string }[] }[] }[] | null
}

/** One computed property of a joined node, as uidoc.inspect reports it (the backend owns every classification). */
export interface InspectProp {
  name: string
  value: unknown
  evidence: string
  note?: string | null
  tokens?: string[] | null
  source?: Record<string, unknown> | null
  editable: 'colour' | 'spacing' | 'visibility' | null
  runtime_caveat?: boolean
}

/** The editable surface of one joined node: properties, the selector proposal with its MEASURED reach, and the
   two colour routes. The backend classifies; this panel only displays and collects. */
export interface InspectResponse {
  composition: string
  node: { logical_id: string; structural_key: string; type: string; name: string; classes: string[]; layout?: string; layout_guid?: string; locator: Record<string, string>; bundle_sha256?: string; render_pos: string | null }
  properties: InspectProp[]
  selector: { selector: string; reason: string; reach: { elements: number; layouts: number; screens: number; measured_by: string; note: string; no_match?: boolean } }
  colour_routes: { through_token: { token: string; chain: string[]; effect: string }; through_scoped_rule: { selector: string; reach: Record<string, unknown>; effect: string } } | null
  visibility_caveat: string | null
}

/** The project's Playground session (playground.session): the 5B history plus the projection. */
export interface SessionResponse {
  session: { schema: string; project: string; screen: string | null; game_build: string | null; operations: Record<string, unknown>[] }
  projection: Record<string, unknown[]>
  counts: Record<string, number>
}

/** One composition that holds tiles (playground.screens). */
export interface ScreenRow { name: string; preset: [number, number]; cells: { cell_index: number; element_id: string; x: number; y: number; w: number; h: number; flags: string[] }[] }

/** One host of the assembled screen (render.screen). */
export interface ScreenHost { element_id: string; col: number; row: number; w: number; h: number; px: { left: number; top: number; width: number; height: number }; tile_layout: string | null; tile_how: string | null; mode: string[] }

/** The backend preview (render.preview): everything the browser shows is computed here. */
export interface MeasuredPoint { width: number; height: number; window_mode: string | null; ui_setting: string | null; composition: string; attempt: string }
export interface PreviewGap { code: string; set: string; breakpoint?: number; kind: string; detail: string }
export interface PreviewSlot {
  id: string; kind: string; element_id: string; direction: string; location: Record<string, number> | null
  conditions: string[]; config_conditions: string[]; default: boolean; visible: boolean; label: string
}
export interface PreviewGameState { state: string; value: boolean; default: boolean; evidence: string }
export interface PreviewResult {
  screen: string
  composition: string
  breakpoint: number
  /** UI1: the preview confidence label, consumed additively (falls back to selection.evidence). */
  confidence?: string
  width: number
  height: number
  setting: string
  information_display: { setting: string; locked: boolean; reason: string; evidence: string }
  state_options: { state: string; label: string; evidence: string }[]
  selection: {
    label: string; evidence: 'MEASURED' | 'ESTIMATE'
    measured_points: MeasuredPoint[]
    corroborating_points: { width: number; height: number; window_mode: string | null; ui_setting: string | null; composition: string }[]
    source: { kind: string; asset: string; set?: string; bundle?: string; path_id?: string }
    cross_check: { status: string; dump_rows: number; keys_compared: number[]; gaps: PreviewGap[] }
    gaps: PreviewGap[]
  }
  grid: { cols: number; rows: number; pitch: { cell: number; gap: number; measured: boolean; label: string }; layout_label?: string }
  hosts: PreviewHost[]
  cells: PreviewCell[]
  slots: PreviewSlot[]
  competition: { bundesliga: boolean; default: boolean; label: string; sheet: string; bundle: string; rules: number; evidence: string; note: string }
  game_states: { scenario: string; defaults: Record<string, boolean>; values: Record<string, boolean>; options: PreviewGameState[] }
  operations: { applied: Record<string, unknown>[]; pending: Record<string, unknown>[] }
  measured: string[]
  estimated: string[]
  notice: string
}

export interface BuildOperation {
  id: string; kind: string; route: string; reason: string; refused: boolean
  translation: Record<string, unknown>; target_bundle?: string
  /** ST1: the custom-layout route: the file the operation changes, whether it replaces a file the user already has, and the warning for a bundle edit on a customised screen */
  custom_layout_file?: string; replaces_user_file?: boolean; warning?: string
}
/** ST1: customlayout.list - the screens customised in the game (files in the game's CustomGridCompositions folder). */
export interface CustomLayoutList {
  folder: string; folder_exists: boolean; badge: string; warning: string
  files: { composition: string; size: number; mtime: string; sha256: string }[]
}
/** ST1: playground.tile_set - the tiles available in one composition's own tile set. */
export interface TileSetResponse { composition: string; tiles: { id: string; object: string; sizes: number[][] }[] }
export interface ProjectRouting {
  project: string
  route_preference: 'skin_folder' | 'bundle'
  route_preference_explicit: boolean
  edit_competition_sheets: boolean
  edit_competition_sheets_explicit: boolean
  layout_route?: 'custom_layout' | 'bundle'
  layout_route_explicit?: boolean
  layout_route_default?: string
  layout_route_note?: string
  default: string
  tradeoffs: Record<string, string>
  note: string
}
export interface BuildReport {
  schema: string
  project: string
  operations: BuildOperation[]
  refusals: { id: string; kind: string; reason: string }[]
  conflicts: { kind: string; reason: string; cells?: string[] }[]
  competition_warnings?: {
    bundesliga_rules: { op_id: string; kind: string; sheet: string; selector: string; properties: string[]; reason: string }[]
    token_competition_sheets: { token: string; redefined_by: { sheet: string; definitions: number }[]; note: string }[]
    edit_competition_sheets: boolean
    note: string
  }
  layout_route?: string
  custom_layout_files?: string[]
  customised_in_game?: string[]
  warnings?: { id: string; kind: string; warning: string }[]
  custom_layouts?: { files: { name: string; size: number; sha256: string }[]; layout_route: string }
  targets: string[]
  referrers: { source: string; affected: string[]; by_bundle: Record<string, string[]> }
  cell_check: null | { ok: boolean; differences: string[]; by_bundle: Record<string, { intended: Record<string, unknown>; built_cell_changes: Record<string, unknown> }> }
  outputs: { built_dir: string; skin_folder: string | null; package: string | null; manifest: string | null; bundles: Record<string, string> }
  buildability?: { buildable: boolean; reason: string }
  installation_ready?: { ready: boolean; reason: string }
  integrity?: { bundle: string; status: string }[]
  optional_slot_effects?: { op_id: string; kind: string; element_id: string; composition: string; summary: string; hidden: string[]; moved: { element_id: string; from_row: number; to_row: number }[] }[]
  addcell_placement_options?: { op_id: string; element_id: string; composition: string; options: { label: string; geometry: Record<string, number>; design_bottom: number; hidden: string[]; summary: string }[]; recommended: { label: string } }[]
  blocked?: string[]
}

export interface PreviewCompare {
  a: { width: number; height: number; composition: string; selection: string; evidence: string }
  b: { width: number; height: number; composition: string; selection: string; evidence: string }
  cells: { appear: { element_id: string }[]; disappear: { element_id: string }[]; changed: { element_id: string; from: Record<string, number>; to: Record<string, number> }[] }
}

export interface PreviewHost { host: PreviewCell; px?: { left: number; top: number; width: number; height: number }; tile_layout?: string; evidence: string | null; children: PreviewNode[]; note?: string }
export interface PreviewNode { path: string; type: string; name: string; classes: string[]; evidence: string; text?: { value: string | null; flag: string }; placeholder_box?: { label: string; flag: string }; state_computed?: Record<string, { value: string; source: Record<string, unknown>; unresolved?: string | null }>; states?: string[]; children: PreviewNode[]; worst_flag?: string }
export interface PreviewCell { cell_index: number; element_id: string; geometry: { x: number; y: number; w: number; h: number }; px?: { left: number; top: number; width: number; height: number }; flags: string[] }

/** The render.screen answer, reduced to what the screen canvas draws. */
export interface ScreenResult { composition: string; pitch: Record<string, number>; grid: { cols: number; rows: number }; hosts: ScreenHost[] }

/** The playground.validate_move gate answer, extended with the snapped position the drag was at. */
export interface GateResult { valid: boolean; blocks: string[]; warnings: string[]; collisions: { cell_index: number; element_id: string; geometry: { x: number; y: number; w: number; h: number } }[]; cell_element_id: string | null; x?: number; y?: number; w?: number; h?: number; configuration?: { description_id?: string; path_id?: string; config_index?: number; size?: { x: number; y: number } } | null }

/** Every error vs limitation the reconstruction knows about, with the node it belongs to (clickable). */
export function diagnostics(res: RResult): Diag[] {
  const out: Diag[] = []
  const walk = (n: RNode, p: string) => {
    for (const [k, d] of Object.entries(n.computed || {})) {
      if (d.unresolved?.length) out.push({ level: 'error', message: `${labelOf(n)}: ${k} has an unresolved variable (${d.unresolved.join(', ')})`, path: p })
      if (d.status === 'unmapped' || d.status === 'unknown') out.push({ level: 'limitation', message: `${labelOf(n)}: ${k} is ${d.status} - the value is shown as a best effort, not as the game renders it`, path: p })
      if (d.status === 'partial') out.push({ level: 'limitation', message: `${labelOf(n)}: ${k} is only partially drawable (${d.note})`, path: p })
    }
    if (n.include && !n.include.resolved) out.push({ level: 'error', message: `${labelOf(n)}: the template ${n.include.layout ?? n.include.alias} did not resolve${n.include.problem ? ' - ' + n.include.problem : ''}`, path: p })
    if (n.placeholder === 'empty') out.push({ level: 'limitation', message: `${labelOf(n)}: no text known (bound or set from code) - a placeholder is drawn`, path: p })
    if (n.font) out.push({ level: 'limitation', message: `${labelOf(n)}: font ${n.font} is drawn with a stand-in, not its own glyphs`, path: p })
    n.children.forEach((c, i) => walk(c, p + '/' + i))
  }
  res.tree.forEach((n, i) => walk(n, String(i)))
  for (const g of res.gaps || []) out.push({ level: 'limitation', message: g, path: null })
  return out.slice(0, 400)
}

const ancestorsOf = (p: string) => { const out: string[] = []; let i = p.lastIndexOf('/'); while (i > 0) { out.push(p.slice(0, i)); i = p.lastIndexOf('/', i - 1) } return out }

function PNode({ n, path, sel, hidden, hl, onSel }: { n: RNode; path: string; sel: string | null; hidden: Set<string>; hl: Set<string>; onSel: (p: string, r: DOMRect) => void }) {
  const isHidden = hidden.has(path)
  return (
    <div className={'rnode pg-node' + (sel === path ? ' sel' : '') + (hl.has(path) ? ' pghl' : '') + (isHidden ? ' pghidden' : '')}
      data-testid="pg-node" data-path={path} data-hidden={isHidden || undefined} title={labelOf(n)}
      style={{ ...styleOf(n), ...(isHidden ? { opacity: 0.25, outline: '1px dashed #e08888' } : {}) }}
      onClick={(e) => { e.stopPropagation(); onSel(path, (e.currentTarget as HTMLElement).getBoundingClientRect()) }}>
      {n.text}
      {n.children.map((c, i) => <PNode key={i} n={c} path={path + '/' + i} sel={sel} hidden={hidden} hl={hl} onSel={onSel} />)}
    </div>
  )
}

/** One row of the hierarchy panel: clickable, expandable, carries the node's evidence flag and hidden marker. */
export function TreeRow({ n, path, depth, sel, collapsed, onSel, onToggle }: { n: RNode; path: string; depth: number; sel: string | null; collapsed: Set<string>; onSel: (p: string) => void; onToggle: (p: string) => void }) {
  const has = n.children.length > 0 || !!n.collapsed
  const open = has && !collapsed.has(path)
  return (
    <div>
      <div className={'pgrow' + (sel === path ? ' sel' : '')} data-testid="pg-row" data-path={path} style={{ paddingLeft: 4 + depth * 12 }} onClick={() => onSel(path)}>
        {has ? <button type="button" className="pgtw" onClick={(e) => { e.stopPropagation(); onToggle(path) }}>{open ? '▾' : '▸'}</button> : <span className="pgtw" />}
        <span className="mono small">{labelOf(n)}</span>
        {n.flag && <span className={'badge st ' + (n.flag === 'partial' ? 'warn' : 'dim')} title={`evidence: ${n.flag}`}>{n.flag}</span>}
        {n.collapsed && <span className="badge st dim" title="elements below are not drawn yet">{n.collapsed.descendants} more</span>}
      </div>
      {open && n.children.map((c, i) => <TreeRow key={i} n={c} path={path + '/' + i} depth={depth + 1} sel={sel} collapsed={collapsed} onSel={onSel} onToggle={onToggle} />)}
    </div>
  )
}

export default function Playground({ project, say, onOpenInstall }: { project: string | null; say: (s: string) => void; onOpenInstall?: () => void }) {
  const [row, setRow] = useState<LayoutRow | null>(null)
  const [res, setRes] = useState<RResult | null>(null)
  const [err, setErr] = useState('')
  const [sel, setSel] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [hoverBox, setHoverBox] = useState<DOMRect | null>(null)
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [box, setBox] = useState<DOMRect | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [busy, setBusy] = useState(false)
  const [join, setJoin] = useState<JoinResponse | null>(null)
  const dragging = useRef<{ x: number; y: number } | null>(null)
  const canvas = useRef<HTMLDivElement | null>(null)

  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) }, [say])

  useEffect(() => {
    if (!row) return
    let live = true
    setBusy(true); setErr(''); setSel(null); setBox(null); setHidden(new Set()); setCollapsed(new Set()); setZoom(1); setPan({ x: 0, y: 0 })
    rpc<RResult>('render.layout', { bundle: row.bundle, path_id: row.path_id, depth: 64, max_nodes: 800, ...(project ? { project, skin: false } : {}) })
      .then((r) => { if (live) setRes(r) }).catch((e) => { if (live) fail(e) }).finally(() => { if (live) setBusy(false) })
    return () => { live = false }
  }, [row, project, fail])

  /* The finding-5 join, where it is built: a top layout of a composition with a built UiDocument maps this
     canvas's render positions to UiDocument identity. Everywhere else (no join, an included layout, an engine
     without a dump) the render-path caveat stays - a failed join call is silent, never an error. */
  useEffect(() => {
    if (!row) return
    let live = true
    setJoin(null)
    rpc<JoinResponse>('uidoc.join', { bundle: row.bundle, path_id: row.path_id })
      .then((j) => { if (live) setJoin(j) }).catch(() => { if (live) setJoin(null) })
    return () => { live = false }
  }, [row])

  const select = useCallback((p: string | null, r?: DOMRect) => { setSel(p); setBox(r ?? null) }, [])
  const toggleTree = (p: string) => setCollapsed((c) => { const n = new Set(c); if (n.has(p)) { n.delete(p) } else { n.add(p) } return n })
  const toggleHidden = (p: string | null) => {
    if (!p) return
    setHidden((h) => { const n = new Set(h); if (n.has(p)) { n.delete(p) } else { n.add(p) } return n })
  }
  const hl = useMemo(() => new Set(sel ? ancestorsOf(sel) : []), [sel])
  const diags = useMemo(() => (res ? diagnostics(res) : []), [res])
  const node = useMemo(() => (res && sel ? nodeAt(res.tree, sel) : null), [res, sel])
  const ident = useMemo(() => {
    if (!join?.joinable) return null
    const map = new Map<string, JoinRow>()
    let conflicts = 0
    for (const inst of join.instances ?? []) {
      for (const [pos, r] of Object.entries({ ...(inst.not_drawn || {}), ...(inst.rows || {}) })) {
        const prev = map.get(pos)
        if (prev && prev.logical_id !== r.logical_id) { conflicts++; map.set(pos, { ...r, state: 'ambiguous' }) }
        else if (!prev) map.set(pos, r)
      }
    }
    const notDrawn = Object.values(join.counts?.not_drawn ?? {}).reduce((a, b) => a + b, 0)
    return { composition: join.composition, counts: join.counts, map, conflicts, notDrawn,
             unmatched: (join.counts?.unmatched_doc?.length ?? 0) + (join.counts?.unmatched_render?.length ?? 0) }
  }, [join])
  const identRow = useMemo(() => (ident && sel ? ident.map.get(sel) ?? null : null), [ident, sel])

  /* 5E: the Playground session (the 5B history) and the editing gestures. The screen mode draws a composition's
     cells on the grid; a tile drag snaps to the 82-px stride and the backend overlap gate runs AS THE TILE MOVES
     (playground.validate_move); the drop records a MoveNode operation. Resize, reorder and a non-tile move are
     preview-only: the refusal text shows at the point of the gesture, and nothing is ever recorded. */
  const [session, setSession] = useState<SessionResponse | null>(null)
  const [dump, setDump] = useState<{ present: boolean; staleness?: { status: string; message?: string } } | null | undefined>(undefined)
  const dumpMissing = dump?.present === false
  const [screens, setScreens] = useState<{ total: number; screens: ScreenRow[] } | null>(null)
  const [screenQ, setScreenQ] = useState('')
  const [screen, setScreen] = useState<ScreenRow | null>(null)
  const [screenRes, setScreenRes] = useState<ScreenResult | null>(null)
  const [mode, setMode] = useState<'layout' | 'screen'>('layout')
  const [gate, setGate] = useState<GateResult | null>(null)
  const [previewOnly, setPreviewOnly] = useState<string | null>(null)
  const [screenJoin, setScreenJoin] = useState<JoinResponse | null>(null)
  const [preview, setPreview] = useState<PreviewResult | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [seed, setSeed] = useState('preview')
  const [setting, setSetting] = useState('Large UI')
  const [simVisible, setSimVisible] = useState(true)
  const [competitionOn, setCompetitionOn] = useState(false)
  const [preset, setPreset] = useState('1600x900')
  const [width, setWidth] = useState(1600)
  const [height, setHeight] = useState(900)
  // UI1 step 2: default to auto at the project's preview resolution (loaded from preview settings above).
  const [breakpointMode, setBreakpointMode] = useState('auto')
  const [uiState, setUiState] = useState('normal')
  const [gameStates, setGameStates] = useState<Record<string, boolean>>({})
  const [compareOn, setCompareOn] = useState(false)
  const [comparePreset, setComparePreset] = useState('1920x1080')
  const [compare, setCompare] = useState<PreviewCompare | null>(null)
  const [buildReport, setBuildReport] = useState<BuildReport | null>(null)
  const [buildBusy, setBuildBusy] = useState(false)
  const [routing, setRouting] = useState<ProjectRouting | null>(null)
  const [customised, setCustomised] = useState<CustomLayoutList | null>(null)
  const [swapEid, setSwapEid] = useState<string | null>(null)
  const [tileSet, setTileSet] = useState<TileSetResponse | null>(null)
  const [swapTile, setSwapTile] = useState('')
  const [swapSize, setSwapSize] = useState('')
  const previewLoaded = useRef<string | null>(null)
  const [addMode, setAddMode] = useState(false)
  const [addDesc, setAddDesc] = useState<string>('')
  const [addCfg, setAddCfg] = useState(0)
  const [addEid, setAddEid] = useState('')
  const dragRef = useRef<{ cellIndex: number; elementId: string; startX: number; startY: number; baseX: number; baseY: number; w: number; h: number } | null>(null)
  const resizeRef = useRef<{ cellIndex: number; elementId: string; startX: number; startY: number; baseW: number; baseH: number; baseX: number; baseY: number } | null>(null)
  const gateSeq = useRef(0)

  const refreshSession = useCallback(() => {
    if (!project) { setSession(null); return }
    rpc<SessionResponse>('playground.session', { project }).then(setSession).catch(() => setSession(null))
  }, [project])

  useEffect(() => {
    if (!project) { setSession(null); return }
    refreshSession()
  }, [project, refreshSession])

  useEffect(() => {
    if (!project) { setRouting(null); return }
    let live = true
    rpc<ProjectRouting>('project.routing', { project }).then((r) => { if (live) setRouting(r) }).catch(() => { if (live) setRouting(null) })
    return () => { live = false }
  }, [project])

  useEffect(() => {
    let live = true
    rpc<CustomLayoutList>('customlayout.list', {}).then((r) => { if (live) setCustomised(r) }).catch(() => { if (live) setCustomised(null) })
    return () => { live = false }
  }, [project])

  const setLayoutRoute = async (value: 'custom_layout' | 'bundle') => {
    try {
      setRouting(await rpc<ProjectRouting>('project.set_routing', { project, layout_route: value }))
    } catch (e) { say(String(e instanceof RpcError ? e.message : e)) }
  }

  const openSwap = async (eid: string) => {
    if (!screen) return
    setSwapEid(eid); setTileSet(null); setSwapTile(''); setSwapSize('')
    try { setTileSet(await rpc<TileSetResponse>('playground.tile_set', { composition: screen.name })) } catch (e) { say(String(e instanceof RpcError ? e.message : e)) }
  }

  const recordSwap = async () => {
    if (!screen || !swapEid || !swapTile || !swapSize || !project) return
    const [x, y] = swapSize.split('x').map(Number)
    try {
      // the BACKEND checks the tile is in the composition's own tile set and builds the record; the browser never assembles an operation
      const built = await rpc<{ refused?: string; operation?: Record<string, unknown> }>('playground.build_operation',
        { kind: 'SwapTile', composition: screen.name, element_id: swapEid, tile: { name: swapTile, size: { x, y } }, project })
      if (built.refused || !built.operation) { say(`the swap was refused by the backend: ${built.refused}`); return }
      await rpc<Record<string, unknown>>('playground.add_operation', { project, operation: built.operation })
      refreshSession()
      say(`tile of ${swapEid} swapped to ${swapTile} (${swapSize}) - recorded${built.operation?.label ? ': ' + String(built.operation.label) : ''}; it goes to the custom-layout file`)
      setSwapEid(null)
    } catch (err) { fail(err) }
  }

  const setRoutePreference = async (value: 'skin_folder' | 'bundle') => {
    try {
      setRouting(await rpc<ProjectRouting>('project.set_routing', { project, route_preference: value }))
    } catch (e) { say(String(e instanceof RpcError ? e.message : e)) }
  }

  const setCompetitionChoice = async (value: boolean) => {
    try {
      setRouting(await rpc<ProjectRouting>('project.set_routing', { project, edit_competition_sheets: value }))
    } catch (e) { say(String(e instanceof RpcError ? e.message : e)) }
  }

  useEffect(() => {
    if (!project || previewLoaded.current === project) return
    const pv = (session?.session as any)?.preview
    if (pv) {
      if (typeof pv.width === 'number') setWidth(pv.width)
      if (typeof pv.height === 'number') setHeight(pv.height)
      if (typeof pv.setting === 'string') setSetting(pv.setting)
      if (typeof pv.seed === 'string') setSeed(pv.seed)
      if (typeof pv.state === 'string') setUiState(pv.state)
      if (typeof pv.sim_visible === 'boolean') setSimVisible(pv.sim_visible)
      if (typeof pv.competition === 'boolean') setCompetitionOn(pv.competition)
      if (pv.game_states && typeof pv.game_states === 'object') setGameStates(pv.game_states)
    }
    previewLoaded.current = project
  }, [project, session])

  useEffect(() => {
    if (!project || previewLoaded.current !== project) return
    rpc('playground.preview_settings', { project, settings: {
      width, height, setting, seed, state: uiState, sim_visible: simVisible, competition: competitionOn, game_states: gameStates,
    } }).catch(() => {})
  }, [project, width, height, setting, seed, uiState, simVisible, competitionOn, gameStates])

  const loadDump = useCallback(() => {
    rpc<{ present: boolean; staleness?: { status: string; message?: string } }>('layout.state')
      .then((d) => { setDump(d); setScreens(null) }).catch(() => setDump(null))
  }, [])
  useEffect(() => { if (mode === 'screen') loadDump() }, [mode, loadDump])

  useEffect(() => {
    if (mode !== 'screen' || screens || dumpMissing) return
    rpc<{ total: number; screens: ScreenRow[] }>('playground.screens', {}).then(setScreens).catch(() => setScreens(null))
  }, [mode, screens, dumpMissing])

  useEffect(() => {
    if (!screen) { setScreenRes(null); setScreenJoin(null); setPreview(null); return }
    let live = true
    setScreenRes(null); setScreenJoin(null); setPreview(null); setGate(null); setSel(null); setBox(null)
    rpc<ScreenResult>('render.screen', { composition: screen.name, width: 1600, height: 900, project: project || undefined })
      .then((r) => { if (live) setScreenRes(r) }).catch((e) => { if (live) fail(e) })
    rpc<JoinResponse>('uidoc.join', { composition: screen.name })
      .then((j) => { if (live) setScreenJoin(j) }).catch(() => { if (live) setScreenJoin(null) })
    return () => { live = false }
  }, [screen, project, fail])

  // 5F: the deterministic preview, computed by the backend; the browser renders what it returns
  useEffect(() => {
    if (mode !== 'screen' || !screen) { setPreview(null); return }
    let live = true
    setPreviewBusy(true)
    rpc<PreviewResult>('render.preview', { screen: screen.name, width, height, setting,
                                           states: uiState === 'normal' ? [] : [uiState], seed,
                                           project, simulated_visible: simVisible, competition: competitionOn,
                                           game_states: gameStates })
      .then((p) => { if (live) setPreview(p) }).catch(() => { if (live) setPreview(null) }).finally(() => { if (live) setPreviewBusy(false) })
    return () => { live = false }
  }, [mode, screen, width, height, setting, uiState, seed, simVisible, project, competitionOn, gameStates])

  // 5F: the side-by-side comparison (two resolutions), also computed by the backend
  useEffect(() => {
    if (!compareOn || mode !== 'screen' || !screen) { setCompare(null); return }
    const [bw, bh] = comparePreset.split('x').map(Number)
    let live = true
    rpc<PreviewCompare>('render.preview_compare', { screen: screen.name, a_width: width, a_height: height,
                                                    b_width: bw, b_height: bh, setting, seed, project,
                                                    simulated_visible: simVisible, competition: competitionOn,
                                                    game_states: gameStates })
      .then((c) => { if (live) setCompare(c) }).catch(() => { if (live) setCompare(null) })
    return () => { live = false }
  }, [compareOn, comparePreset, mode, screen, width, height, setting, seed, simVisible, project, competitionOn, gameStates])

  useEffect(() => {
    if (!preview) return
    if (!(preview.state_options || []).some((o) => o.state === uiState)) setUiState('normal')
  }, [preview, uiState])

  const buildSession = async () => {
    if (!project) { say('save the project as a folder project first: the build reads the session from its folder'); return }
    setBuildBusy(true)
    try {
      const r = await rpc<BuildReport>('build.session', { project })
      setBuildReport(r)
    } catch (e) {
      say(String(e instanceof RpcError ? e.message : e))
    } finally {
      setBuildBusy(false)
    }
  }

  const choosePreset = (v: string) => {
    setPreset(v)
    const [w, h] = v.split('x').map(Number)
    if (w && h) { setWidth(w); setHeight(h) }
  }

  const cellAt = (elementId: string) => screen?.cells.find((c) => c.element_id === elementId) ?? null

  const snap = (n: number) => Math.round(n / 82)

  const onTileDown = (e: React.MouseEvent, host: ScreenHost) => {
    if (!screen) return
    const cell = cellAt(host.element_id)
    if (!cell) return
    e.stopPropagation()
    dragRef.current = { cellIndex: cell.cell_index, elementId: cell.element_id, startX: e.clientX, startY: e.clientY, baseX: cell.x, baseY: cell.y, w: cell.w, h: cell.h }
    setPreviewOnly(null)
  }

  const onTileMove = (e: React.MouseEvent) => {
    const drag = dragRef.current
    if (!drag) return
    const gx = drag.baseX + snap(e.clientX - drag.startX)
    const gy = drag.baseY + snap(e.clientY - drag.startY)
    if (!screen) return
    const seq = ++gateSeq.current
    rpc<GateResult>('playground.validate_move', { composition: screen.name, cell_index: drag.cellIndex, geometry: { x: gx, y: gy, w: drag.w, h: drag.h }, project })
      .then((g) => { if (gateSeq.current === seq) setGate({ ...g, x: gx, y: gy }) })
      .catch((err) => { if (gateSeq.current === seq) setGate({ x: gx, y: gy, valid: false, blocks: [String(err instanceof RpcError ? err.message : err)], warnings: [], collisions: [], cell_element_id: drag.elementId } as GateResult) })
  }

  const onTileUp = async () => {
    const drag = dragRef.current
    dragRef.current = null
    if (!drag || !screen || !gate) return
    const gx = gate.x ?? drag.baseX, gy = gate.y ?? drag.baseY
    setGate(null)
    if (gx === drag.baseX && gy === drag.baseY) return
    if (!project) { say('pick a project to record edits'); return }
    try {
      // the BACKEND builds the record (the gate runs again inside it); the browser never assembles an operation
      const built = await rpc<{ refused?: string; operation?: Record<string, unknown> }>('playground.build_operation',
        { kind: 'MoveNode', composition: screen.name, cell_index: drag.cellIndex, geometry: { x: gx, y: gy, w: drag.w, h: drag.h }, project })
      if (built.refused || !built.operation) { say(`the move was refused by the backend: ${built.refused}`); return }
      await rpc<Record<string, unknown>>('playground.add_operation', { project, operation: built.operation })
      refreshSession()
      say(`tile ${drag.elementId} move recorded (${gx}, ${gy}); the D2 overlap gate runs again at build review`)
    } catch (err) {
      fail(err)
    }
  }

  /* Resize is BUILDABLE for ENLARGEMENT (Test C, 2026-11-20): the drag resizes in grid units, the backend overlap
     gate runs as it moves, and the drop records a ResizeNode. A shrink below the tile's configured size is refused
     by the backend. The operation carries the composition it applies to, and the history says it only takes effect
     at window sizes where that composition is active. */
  const resizeGate = (cellIndex: number, elementId: string, geometry: { x: number; y: number; w: number; h: number }) => {
    if (!screen) return
    const seq = ++gateSeq.current
    rpc<GateResult>('playground.validate_move', { composition: screen.name, cell_index: cellIndex, geometry, project, resize: true })
      .then((g) => { if (gateSeq.current === seq) setGate({ ...g, x: geometry.x, y: geometry.y, w: geometry.w, h: geometry.h }) })
      .catch((err) => { if (gateSeq.current === seq) setGate({ x: geometry.x, y: geometry.y, w: geometry.w, h: geometry.h, valid: false, blocks: [String(err instanceof RpcError ? err.message : err)], warnings: [], collisions: [], cell_element_id: elementId }) })
  }

  const onResizeDown = (e: React.MouseEvent, host: ScreenHost) => {
    if (!screen) return
    const cell = cellAt(host.element_id)
    if (!cell) return
    e.stopPropagation()
    resizeRef.current = { cellIndex: cell.cell_index, elementId: cell.element_id, startX: e.clientX, startY: e.clientY, baseW: cell.w, baseH: cell.h, baseX: cell.x, baseY: cell.y }
    setPreviewOnly(null)
  }

  const onResizeMove = (e: React.MouseEvent) => {
    const rz = resizeRef.current
    if (!rz) return
    const w = Math.max(1, rz.baseW + snap(e.clientX - rz.startX))
    const h = Math.max(1, rz.baseH + snap(e.clientY - rz.startY))
    resizeGate(rz.cellIndex, rz.elementId, { x: rz.baseX, y: rz.baseY, w, h })
  }

  const onResizeUp = async () => {
    const rz = resizeRef.current
    resizeRef.current = null
    if (!rz || !screen || !gate) return
    const w = gate.w ?? rz.baseW, h = gate.h ?? rz.baseH
    setGate(null)
    if (w === rz.baseW && h === rz.baseH) return
    if (!project) { say('pick a project to record edits'); return }
    try {
      const built = await rpc<{ refused?: string; operation?: Record<string, unknown> }>('playground.build_operation',
        { kind: 'ResizeNode', composition: screen.name, cell_index: rz.cellIndex,
          geometry: { x: rz.baseX, y: rz.baseY, w, h }, max_size: { x: w, y: h }, project })
      if (built.refused || !built.operation) { say(`the resize was refused by the backend: ${built.refused}`); return }
      await rpc<Record<string, unknown>>('playground.add_operation', { project, operation: built.operation })
      refreshSession()
      say(`tile ${rz.elementId} resize recorded (${w}x${h}) - buildable enlargement (configuration unchanged)`)
    } catch (err) {
      fail(err)
    }
  }

  /* Add-tile: reuses an EXISTING description and configuration. Buildable when the runtime's packing lands it
     at the requested row; the backend refuses a placement it would move and names the packed row. */
  const descriptions = useMemo(() => {
    const out: { key: string; id: string; path_id: string; configs: number }[] = []
    for (const rec of screenJoin?.cell_configurations ?? []) {
      for (const d of rec.descriptions ?? []) {
        if (d.read && d.path_id) out.push({ key: String(d.path_id), id: d.id ?? d.name ?? String(d.path_id), path_id: String(d.path_id), configs: (d.configurations ?? []).length })
      }
    }
    return out
  }, [screenJoin])

  const onStageClickForAdd = async (e: React.MouseEvent) => {
    if (!addMode || !screen) return
    e.stopPropagation()
    const stage = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const gx = snap((e.clientX - stage.left) / (zoom || 1) - 12)
    const gy = snap((e.clientY - stage.top) / (zoom || 1) - 12)
    const desc = descriptions.find((d) => d.key === addDesc)
    const used = screen.cells.map((c) => c.cell_index)
    const newIndex = (used.length ? Math.max(...used) : -1) + 1
    const eid = addEid.trim() || `AddedTile${newIndex}`
    const geometry = { x: Math.max(0, gx), y: Math.max(0, gy), w: 2, h: 2 }
    try {
      if (!project) { say('pick a project to record edits'); return }
      // the BACKEND runs the add gate and builds the record; the browser never assembles an operation
      const built = await rpc<{ refused?: string; operation?: Record<string, unknown> }>('playground.build_operation',
        { kind: 'AddCell', composition: screen.name, cell_index: newIndex, element_id: eid, geometry,
          description: desc ? { path_id: desc.path_id, config_index: addCfg } : {}, project })
      if (built.refused || !built.operation) { say(`the add was refused by the backend: ${built.refused}`); return }
      await rpc<Record<string, unknown>>('playground.add_operation', { project, operation: built.operation })
      refreshSession()
      say(`cell ${eid} recorded${built.operation?.label ? ' - ' + String(built.operation.label) : ''}; the build checks the packed row`)
    } catch (err) {
      fail(err)
    }
  }

  const onLayoutDrag = (e: React.MouseEvent) => {
    if (mode !== 'layout' || !dragging.current || !sel) return
    const moved = Math.abs(e.clientX - dragOrigin.current.x) + Math.abs(e.clientY - dragOrigin.current.y)
    if (moved > 12) setPreviewOnly('move: a generic element move has no writer - only a composition CELL has one (the '
      + 'placement edit). This move is a preview only, it can never be built')
  }
  const dragOrigin = useRef({ x: 0, y: 0 })

  const recordVerdict = async () => {
    if (!verdict?.validation?.ok || !verdictOp || !project) return
    try {
      await rpc<Record<string, unknown>>('playground.add_operation', { project, operation: verdictOp })
      setVerdictRecorded(true)
      refreshSession()
    } catch (err) {
      fail(err)
    }
  }

  /* 5D: the editable inspector, joined nodes only. The backend classifies (uidoc.inspect / uidoc.classify); this
     panel displays the evidence, collects the value and the route, and shows the backend's verdict verbatim. */
  const [inspect, setInspect] = useState<InspectResponse | null>(null)
  const [editProp, setEditProp] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [editRoute, setEditRoute] = useState<'scoped_rule' | 'token'>('scoped_rule')
  const [verdict, setVerdict] = useState<{ refused?: string; validation?: { ok: boolean; safety: string; scope?: { elements: number | null; scope_change: boolean; note?: string }; findings?: string[]; translation?: { fragment: string; writer: string; effect_evidence?: string } } } | null>(null)
  const [verdictOp, setVerdictOp] = useState<Record<string, unknown> | null>(null)
  const [verdictRecorded, setVerdictRecorded] = useState(false)
  const [checkBusy, setCheckBusy] = useState(false)

  useEffect(() => {
    if (!identRow || identRow.state !== 'joined' || !ident || !row) { setInspect(null); setEditProp(null); setVerdict(null); return }
    let live = true
    setInspect(null); setEditProp(null); setVerdict(null)
    rpc<InspectResponse>('uidoc.inspect', { composition: ident.composition, render_pos: sel, bundle: row.bundle, path_id: row.path_id })
      .then((r) => { if (live) setInspect(r) }).catch(() => { if (live) setInspect(null) })
    return () => { live = false }
  }, [identRow, ident, row, sel])

  const classify = async () => {
    if (!inspect || !editProp || !ident) return
    const prop = inspect.properties.find((p) => p.name === editProp)
    if (!prop) return
    setCheckBusy(true); setVerdict(null)
    type V = { ok: boolean; safety: string; scope?: { elements: number | null; scope_change: boolean; note?: string }; findings?: string[]; translation?: { fragment: string; writer: string; effect_evidence?: string } }
    try {
      const base = { composition: inspect.composition, render_pos: sel, bundle: row?.bundle, path_id: row?.path_id }
      let res: { refused?: string; validation?: V; operation?: Record<string, unknown> }
      if (prop.editable === 'colour' && editRoute === 'token' && inspect.colour_routes) {
        res = await rpc<{ refused?: string; validation?: V; operation?: Record<string, unknown> }>('uidoc.classify', {
          ...base, kind: 'ReplaceToken', props: editValue.trim(),
          token: inspect.colour_routes.through_token.token,
          route: { chosen: 'token', reason: 'the colour comes from this token; the token route is the one the user chose' },
        })
      } else {
        res = await rpc<{ refused?: string; validation?: V; operation?: Record<string, unknown> }>('uidoc.classify', {
          ...base, kind: prop.editable === 'colour' ? 'SetColor' : prop.editable === 'spacing' ? 'SetSpacing' : 'SetVisibility',
          props: { [prop.name]: editValue.trim() },
          ...(prop.editable === 'colour' ? { route: { chosen: 'scoped_rule', reason: 'the scoped rule is the route the user chose; its reach is measured' } } : {}),
        })
      }
      setVerdict(res)
      setVerdictOp(res.operation ?? null)
      setVerdictRecorded(false)
    } catch (e) {
      setVerdict({ refused: e instanceof RpcError ? e.message : String(e) })
      setVerdictOp(null)
      setVerdictRecorded(false)
    } finally {
      setCheckBusy(false)
    }
  }

  const fit = () => { const el = canvas.current; if (el && res) setZoom(Math.min(1, Math.max(0.15, Math.min(el.clientWidth / 1600, el.clientHeight / 900)))); setPan({ x: 0, y: 0 }) }

  return (
    <div className="pg" data-testid="playground">
      <aside className="pg-tree" data-testid="pg-tree">
        <div className="head">HIERARCHY {!res && <span className="dim">(no screen open)</span>}</div>
        {res && res.tree.map((n, i) => <TreeRow key={i} n={n} path={String(i)} depth={0} sel={sel} collapsed={collapsed} onSel={(p) => select(p)} onToggle={toggleTree} />)}
        {session && <div className="pkg" data-testid="pg-session">
          <b className="small">History <span className="dim small">{session.counts?.applied ?? 0} applied / {session.counts?.total ?? 0} total</span></b>
          <div style={{ display: 'flex', gap: 4 }}>
            <button type="button" data-testid="pg-undo" onClick={() => { rpc<Record<string, unknown>>('playground.undo', { project }).then(() => refreshSession()).catch(fail) }}>undo</button>
            <button type="button" data-testid="pg-redo" onClick={() => { const last = [...(session.session.operations as { id?: string; state?: string }[])].reverse().find((o) => o.state === 'reverted'); if (last?.id) rpc<Record<string, unknown>>('playground.redo', { project, op_id: last.id }).then(() => refreshSession()).catch(fail) }}>redo</button>
            <button type="button" data-testid="pg-revert" onClick={() => { rpc<Record<string, unknown>>('playground.revert', { project }).then(() => refreshSession()).catch(fail) }}>revert all</button>
          </div>
          {(session.session.operations as Record<string, any>[]).length > 0 && <div data-testid="pg-op-list" style={{ marginTop: 6 }}>
            {(session.session.operations as Record<string, any>[]).map((op) => {
              const comp = (op?.target?.cell?.composition as string | undefined) ?? null
              const label = (op.label as string | undefined) ?? `${op.kind}${comp ? ' in ' + comp : ''}`
              const active = preview?.composition
              const inactive = !!(comp && active && active !== comp)
              return <div key={String(op.id)} data-testid="pg-op" data-kind={String(op.kind)} data-state={String(op.state)} className="small" style={{ marginTop: 4 }}>
                <span className="dim">{String(op.state)}</span> {label}
                {comp && <div className="dim" data-testid="pg-op-scope">Only takes effect at window sizes where {comp} is the active composition.</div>}
                {inactive && <div className="warn" data-testid="pg-op-inactive">Not active at this preview size: the active composition is {active}.</div>}
              </div>
            })}
          </div>}
          {!project && <div className="small warn">pick a project to record edits</div>}
        </div>}
      </aside>
      <div className="pg-main">
        <div className="rbar">
          <button type="button" data-testid="pg-mode-layout" onClick={() => setMode('layout')}>layout</button>
          <button type="button" data-testid="pg-mode-screen" onClick={() => setMode('screen')}>screen</button>
          <span className="dim">|</span>
          <button type="button" data-testid="pg-zoom-out" onClick={() => setZoom((z) => Math.max(0.15, z / 1.25))}>−</button>
          <span className="mono small">{Math.round(zoom * 100)}%</span>
          <button type="button" data-testid="pg-zoom-in" onClick={() => setZoom((z) => Math.min(4, z * 1.25))}>+</button>
          <button type="button" data-testid="pg-fit" onClick={fit}>fit</button>
          <button type="button" disabled={!sel} data-testid="pg-hide" onClick={() => toggleHidden(sel)} title="View toggle only: stops drawing the element on this canvas. It never writes an operation - a real visibility edit is a SetVisibility operation with its own evidence.">{hidden.has(sel ?? '') ? 'show element' : 'hide element'}</button>
          {mode === 'screen' && <button type="button" data-testid="pg-add-toggle" onClick={() => { setAddMode((v) => !v); setGate(null) }}>{addMode ? 'stop adding' : 'add tile'}</button>}
          {mode === 'screen' && addMode && <>
            <select data-testid="pg-add-desc" value={addDesc} onChange={(e) => setAddDesc(e.target.value)}>
              <option value="">pick a tile description ...</option>
              {descriptions.map((d) => <option key={d.key} value={d.key}>{d.id} ({d.configs} configs)</option>)}
            </select>
            <input data-testid="pg-add-cfg" type="number" min={0} value={addCfg} onChange={(e) => setAddCfg(Math.max(0, Number(e.target.value) || 0))} style={{ width: 52 }} title="configuration index" />
            <input data-testid="pg-add-eid" value={addEid} placeholder="new element id" onChange={(e) => setAddEid(e.target.value)} style={{ width: 110 }} />
          </>}
          {mode === 'layout' && row && <span className="dim small">{row.name} · {row.bundle}</span>}
          {mode === 'screen' && screen && <span className="dim small" data-testid="pg-screen-name">{screen.name}</span>}
          {mode === 'screen' && screen && customised?.files.some((f) => f.composition === screen.name) && <span className="warn small" data-testid="pg-customised-badge"
            title={customised.warning}>{customised.badge}</span>}
          {busy && <span className="dim" data-testid="pg-progress">reconstructing ...</span>}
        </div>
        {res && mode === 'layout' && <div className="rnotice" role="note">{res.notice}</div>}
        {res && mode === 'layout' && <div className="rnotice" role="note" data-testid="pg-identity-note">{ident
          ? `Element addressing on this canvas is by UiDocument identity: the (bundle, path_id, m_Id) join of ${ident.composition} (${ident.counts?.joined ?? 0} joined, ${ident.notDrawn} not drawn, ${ident.unmatched} unmatched)${ident.conflicts ? `; ${ident.conflicts} position(s) shared by several cells stay on render-path addressing` : ''}. Screens without a built join keep render-path addressing.`
          : 'Element addressing in this canvas is by render position, not the UiDocument identity: the two trees differ by design, and layout names repeat. Reliable operation addressing needs the (bundle, path_id, m_Id) join, built so far only for Team Instructions at Large.'}</div>}
        {err && <div className="warn pad">{err}</div>}
        <div className="pg-canvas" ref={canvas} data-testid="pg-canvas"
          onClick={() => select(null)}
          /* one delegated hover handler: the DEEPEST node under the pointer is the hovered one. Per-node onMouseEnter
             cannot do this: React fires enter on the ancestors too, and the last state write would win, so the
             outermost element would be "hovered" instead of the one under the pointer. */
          onMouseOver={(e) => { const el = (e.target as HTMLElement).closest('[data-path]'); if (el) { setHover(el.getAttribute('data-path')); setHoverBox(el.getBoundingClientRect()) } }}
          onMouseOut={(e) => { const el = (e.target as HTMLElement).closest('[data-path]'); if (el) { setHover(null); setHoverBox(null) } }}
          onMouseDown={(e) => { if (e.button === 0) { dragging.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }; dragOrigin.current = { x: e.clientX, y: e.clientY } } }}
          onMouseMove={(e) => { if (dragging.current) { setPan({ x: e.clientX - dragging.current.x, y: e.clientY - dragging.current.y }); onLayoutDrag(e) } }}
          onMouseUp={() => { dragging.current = null; if (mode === 'layout') setTimeout(() => setPreviewOnly(null), 1500) }} onMouseLeave={() => { dragging.current = null; setHover(null); setHoverBox(null) }}>
          <div className="rstage" data-testid="pg-stage" style={{ width: 1600, height: 900, transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: '0 0', background: '#11151f' }}
            onClick={(e) => { onStageClickForAdd(e) }}>
            {mode === 'layout' && res?.tree.map((n, i) => <PNode key={i} n={n} path={String(i)} sel={sel} hidden={hidden} hl={hl} onSel={select} />)}
            {mode === 'screen' && screenRes?.hosts.map((h) => {
              const drag = dragRef.current
              const rz = resizeRef.current
              const moving = drag && drag.elementId === h.element_id && gate && gate.x !== undefined
              const resizing = rz && rz.elementId === h.element_id && gate && gate.w !== undefined
              const left = moving ? 12 + 82 * (gate!.x ?? h.col) : h.px.left
              const top = moving ? 12 + 82 * (gate!.y ?? h.row) : h.px.top
              const width = resizing ? 82 * (gate!.w ?? h.w) - 16 : h.px.width
              const height = resizing ? 82 * (gate!.h ?? h.h) - 16 : h.px.height
              const ok = (moving || resizing) ? gate!.valid : true
              return (
                <div key={h.element_id} data-testid="pg-tile" data-element={h.element_id}
                  className="rnode" title={h.tile_layout ?? h.element_id}
                  style={{ position: 'absolute', left, top, width, height,
                           border: (moving || resizing) ? `2px solid ${ok ? '#5fd35f' : '#e05555'}` : '1px solid #3a4a6a',
                           background: 'rgba(30,40,70,0.35)', overflow: 'hidden', cursor: project ? 'grab' : 'default' }}
                  onMouseDown={(e) => onTileDown(e, h)} onMouseMove={(e) => { onTileMove(e); onResizeMove(e) }} onMouseUp={() => { onTileUp(); onResizeUp() }}>
                  <span className="mono small dim" style={{ padding: 4, display: 'block' }}>{h.element_id}</span>
                  {(moving || resizing) && !ok && <span className="small" style={{ color: '#ff9a9a', padding: 4, display: 'block' }} data-testid="pg-gate">
                    {(gate!.blocks?.[0] || (gate!.collisions?.length ? `overlaps ${gate!.collisions[0].element_id} at x=${gate!.collisions[0].geometry.x}, y=${gate!.collisions[0].geometry.y}, w=${gate!.collisions[0].geometry.w}, h=${gate!.collisions[0].geometry.h}` : ''))}
                  </span>}
                  {(moving || resizing) && ok && gate && (gate.warnings?.length ?? 0) > 0 && <span className="small" style={{ color: '#ffd88a', padding: 4, display: 'block' }}>{gate!.warnings[0]}</span>}
                  {project && <button type="button" data-testid="pg-swap" title="Swap this cell's tile by name, from the composition's own tile set (goes to the custom-layout file)"
                    style={{ position: 'absolute', right: 0, top: 0, fontSize: 10 }}
                    onMouseDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); openSwap(h.element_id) }}>swap</button>}
                  <button type="button" data-testid="pg-resize" title="Buildable enlargement: the drag resizes by m_location + m_maxSize (the configured size stays unchanged), the overlap gate runs as it moves, and the drop records a ResizeNode. A shrink below the configured size is refused."
                    style={{ position: 'absolute', right: 0, bottom: 0, width: 14, height: 14, cursor: 'nwse-resize' }}
                    onMouseDown={(e) => onResizeDown(e, h)} />
                </div>
              )
            })}
            {mode === 'screen' && !screenRes && <div className="dim small pad">pick a composition from the screens list</div>}
            {mode === 'screen' && addMode && <div className="dim small pad" data-testid="pg-add-hint" style={{ position: 'absolute', top: 4, left: 8 }}>add mode: click a free grid position to place a 2x2 cell reusing the picked description</div>}
          </div>
          {hoverBox && hover && hover !== sel && <div className="pg-hoverbox" data-testid="pg-hoverbox" style={{ position: 'absolute', left: hoverBox.left, top: hoverBox.top, width: Math.max(hoverBox.width, 6), height: Math.max(hoverBox.height, 6) }} title={hover} />}
          {box && sel && <div className="pg-selbox" data-testid="pg-selbox" style={{ position: 'absolute', left: box.left, top: box.top, width: Math.max(box.width, 8), height: Math.max(box.height, 8) }} />}
        </div>
        {mode === 'screen' && screen && routing?.layout_route === 'bundle' && customised?.files.some((f) => f.composition === screen.name) &&
          <div className="warn small pad" data-testid="pg-customised-warning" role="alert">{customised.warning}: {screen.name} is customised in the game, so its custom-layout file is used instead of the bundle. Use the custom-layout route for layout edits.</div>}
        {previewOnly && <div className="warn pad" data-testid="pg-preview-only" role="alert">{previewOnly}</div>}
        {mode === 'layout' && hover && <div className="small dim pad mono" data-testid="pg-hoverinfo">{identRow && hover === sel ? `hovering ${hover} · ${identRow.logical_id}` : `hovering ${hover} (render path; the identity caveat above applies)`}</div>}
        {mode === 'layout' && box && sel && <div className="small dim pad mono" data-testid="pg-box">selected box: {Math.round(box.width)} x {Math.round(box.height)} at ({Math.round(box.left)}, {Math.round(box.top)}) - offline layout, not the game's own geometry</div>}
      </div>
      <aside className="pg-inspector" data-testid="pg-inspector">
        <div className="head">ELEMENT {!node && <span className="dim">(nothing selected)</span>}</div>
        {!node && <div className="dim small pad">Select an element on the canvas or in the hierarchy. Every shown value carries its evidence; the offline reconstruction is an approximation.</div>}
        {node && <>
          <div className="pkg" data-testid="pg-identity">
            <b className="small">UiDocument identity</b>
            {!ident && <div className="small dim">not joined on this screen - addressed by render path only</div>}
            {ident && !identRow && <div className="small dim">this render position has no UiDocument row on {ident.composition}</div>}
            {ident && identRow && (identRow.state === 'ambiguous'
              ? <div className="small warn">this render position is shared by several cell instances of the layout; it stays on render-path addressing</div>
              : <>
                <div className="small mono" data-testid="pg-identity-id">{identRow.logical_id}</div>
                <div className="small dim" data-testid="pg-identity-locator">locator: {identRow.bundle ?? '?'} · path_id {identRow.path_id ?? '?'} · m_Id {identRow.m_id}{identRow.layout ? ` · ${identRow.layout}` : ''}</div>
                {identRow.state !== 'joined' && <div className="small warn" data-testid="pg-identity-state">{identRow.state} - the render does not draw this node</div>}
              </>)}
          </div>
          <div className="pkg"><b className="mono small">{labelOf(node)}</b>
            <div className="small dim">path {sel} · {node.children.length} children{node.type ? '' : ''}</div>
            <div><button type="button" title="View toggle only: never writes an operation." onClick={() => toggleHidden(sel)}>{hidden.has(sel ?? '') ? 'show this element' : 'hide this element'}</button></div>
          </div>
          <div className="pkg"><b className="small">Matched rules (cascade order)</b>
            {node.matched.length === 0 && <div className="dim small">none - this element is styled by initial values only</div>}
            {node.matched.map((m, i) => <div key={i} className="small mono">{m.sheet} rule {m.rule} · {m.selector} (spec {m.specificity})</div>)}
          </div>
          <div className="pkg"><b className="small">Properties and evidence</b>
            <table className="tbl"><thead><tr><th>property</th><th>value</th><th>evidence</th></tr></thead><tbody>
              {Object.entries(node.computed || {}).map(([k, d]) => (
                <tr key={k}><td className="mono small">{k}</td><td className="mono small">{d.value}</td>
                  <td className={'small ' + (d.status === 'mapped' ? 'ok' : d.status === 'partial' ? 'warn' : 'bad')} data-testid="pg-evidence">{d.status}{d.tokens?.length ? ` · ${d.tokens.join(' → ')}` : ''}</td></tr>))}
            </tbody></table>
          </div>
          {inspect && <>
            <div className="pkg" data-testid="pg-edit">
              <b className="small">Edit (joined node - the backend classifies)</b>
              <div className="small dim mono" data-testid="pg-edit-selector">proposed selector {inspect.selector.selector} ({inspect.selector.reason}) · measured reach {inspect.selector.reach.elements} element(s) in {inspect.selector.reach.layouts} layout(s) · {inspect.selector.reach.measured_by}</div>
              {inspect.selector.reach.elements > 1 && <div className="small warn" data-testid="pg-edit-scope">scope change: the selector reaches more than this element - every element it matches, on every screen, changes</div>}
              {inspect.visibility_caveat && <div className="small warn" data-testid="pg-edit-caveat">{inspect.visibility_caveat}</div>}
              {inspect.properties.filter((p) => p.editable).length === 0 && <div className="dim small">this node carries no editable colour, spacing or visibility property</div>}
              {inspect.properties.filter((p) => p.editable).map((p) => (
                <div key={p.name} className="small" style={{ marginTop: 4 }}>
                  <button type="button" data-testid="pg-edit-prop" onClick={() => { setEditProp(p.name); setEditValue(''); setVerdict(null); setEditRoute('scoped_rule') }}>{editProp === p.name ? '▸' : '▸'} {p.editable}: {p.name}</button>
                </div>))}
              {editProp && (() => {
                const prop = inspect.properties.find((p) => p.name === editProp)!
                return <>
                  <div className="small" style={{ marginTop: 4 }}>
                    <input data-testid="pg-edit-value" value={editValue} placeholder={prop.editable === 'colour' ? '#1a2b3c' : prop.editable === 'spacing' ? '4px' : 'hidden'} onChange={(e) => setEditValue(e.target.value)} />
                  </div>
                  {prop.editable === 'colour' && inspect.colour_routes && <>
                    <label className="small" style={{ display: 'block' }}><input type="radio" checked={editRoute === 'scoped_rule'} onChange={() => setEditRoute('scoped_rule')} /> scoped rule on {inspect.colour_routes.through_scoped_rule.selector} - {inspect.colour_routes.through_scoped_rule.effect}</label>
                    <label className="small" style={{ display: 'block' }}><input type="radio" checked={editRoute === 'token'} onChange={() => setEditRoute('token')} /> token {inspect.colour_routes.through_token.token} - {inspect.colour_routes.through_token.effect}</label>
                  </>}
                  <button type="button" data-testid="pg-classify" disabled={!editValue.trim() || checkBusy} onClick={classify}>{checkBusy ? 'checking ...' : 'check with the backend'}</button>
                  {verdict && <div data-testid="pg-verdict">
                    {verdict.refused
                      ? <div className="bad small">refused by the backend: {verdict.refused}</div>
                      : <div className={verdict.validation?.safety === 'scope' ? 'warn small' : 'ok small'}>
                          {verdict.validation?.safety === 'scope' ? 'scope change' : 'value edit'} · {verdict.validation?.translation?.writer}
                          {(verdict.validation?.findings ?? []).map((f, i) => <div key={i} className="small dim">{f}</div>)}
                          {verdictOp && !verdictRecorded && <div style={{ marginTop: 4 }}>
                            <button type="button" data-testid="pg-record" onClick={recordVerdict}>record this edit (undoable)</button>
                          </div>}
                          {verdictRecorded && <div className="ok small">recorded in the session (undo/redo/revert in the history bar)</div>}
                        </div>}
                  </div>}
                </>
              })()}
            </div>
          </>}
          {!inspect && identRow?.state === 'joined' && <div className="dim small pad">the editable surface of this node is loading ...</div>}
        </>}
        <div className="pkg"><b className="small">Diagnostics <span className={diags.some((d) => d.level === 'error') ? 'bad' : 'dim'}>{diags.filter((d) => d.level === 'error').length} error(s)</span></b>
          {diags.length === 0 && <div className="ok small">No errors; the reconstruction is complete to the extent the source data permits.</div>}
          {diags.map((d, i) => (
            <div key={i} className={'diag ' + d.level} data-testid="pg-diag" data-level={d.level} data-path={d.path ?? undefined}
              onClick={() => d.path && select(d.path)}>{d.message}</div>))}
        </div>
      </aside>
      <div className="pg-browser">
        {mode === 'screen' && swapEid && <div className="pkg" data-testid="pg-swap-panel">
          <b className="small">SWAP TILE of {swapEid}</b>
          <div className="small dim">The tiles available in {screen?.name}'s own tile set. The slot (location, minimum and maximum size) stays; the tile changes by name.</div>
          {!tileSet && <div className="dim small">loading the tile set ...</div>}
          {tileSet && <>
            <select data-testid="pg-swap-tile" value={swapTile} onChange={(e) => { setSwapTile(e.target.value); setSwapSize('') }}>
              <option value="">pick a tile ...</option>
              {tileSet.tiles.map((t) => <option key={t.object} value={t.id}>{t.id} ({t.sizes.length} sizes)</option>)}
            </select>{' '}
            <select data-testid="pg-swap-size" value={swapSize} onChange={(e) => setSwapSize(e.target.value)} disabled={!swapTile}>
              <option value="">size ...</option>
              {(tileSet.tiles.find((t) => t.id === swapTile)?.sizes ?? []).map((z) => <option key={z.join('x')} value={z.join('x')}>{z.join('x')}</option>)}
            </select>{' '}
            <button type="button" data-testid="pg-swap-record" disabled={!swapTile || !swapSize} onClick={recordSwap}>record swap (undoable)</button>{' '}
            <button type="button" data-testid="pg-swap-cancel" onClick={() => setSwapEid(null)}>cancel</button>
          </>}
        </div>}
        {mode === 'screen' && preview && <div className="pkg" data-testid="pg-preview">
          <b className="small">PREVIEW (deterministic; computed by the backend)</b>{previewBusy && <span className="dim small"> updating...</span>}
          <div className="small mono">{preview.composition} · breakpoint {preview.breakpoint} · {preview.width}x{preview.height}</div>
          <BreakpointSelector width={width} height={height} mode={breakpointMode} onModeChange={setBreakpointMode}
            composition={preview.composition || screen?.name} confidence={preview} />
          <div className="small dim" data-testid="pg-preview-selection" data-evidence={preview.selection.evidence}>{preview.selection.label}</div>
          <div className="small dim" data-testid="pg-preview-source">
            keys: {preview.selection.source.kind} · {preview.selection.source.asset}
            {preview.selection.source.set ? ` (${preview.selection.source.set})` : ''} · cross-check {preview.selection.cross_check.status}
            {preview.selection.gaps.map((g, i) => <div key={i} className="warn small">{g.code} {g.kind}: {g.detail}</div>)}
          </div>
          <div className="small" data-testid="pg-preview-info">
            Information Display {preview.setting}: {preview.information_display.locked
              ? <span className="bad">locked by the game ({preview.information_display.evidence})</span>
              : <span className="ok">available ({preview.information_display.evidence})</span>}
          </div>
          <div className="small dim">grid {preview.grid.cols} x {preview.grid.rows} · pitch {preview.grid.pitch.label}</div>
          <div className="small dim" data-testid="pg-preview-engine">{preview.grid.layout_label}</div>
          <div style={{ marginTop: 4 }} data-testid="pg-preview-controls">
            <label className="small">resolution{' '}
              <select data-testid="pg-preview-preset" value={preset} onChange={(e) => choosePreset(e.target.value)}>
                <option value="1024x768">1024 x 768 (Small)</option>
                <option value="1440x900">1440 x 900 (Standard)</option>
                <option value="1600x900">1600 x 900</option>
                <option value="1920x1080">1920 x 1080 (Large)</option>
                <option value="2560x1440">2560 x 1440 (Large)</option>
                <option value="custom">custom</option>
              </select>
            </label>
            <label className="small"> W <input data-testid="pg-preview-width" type="number" value={width} style={{ width: 64 }}
              onChange={(e) => { setPreset('custom'); setWidth(Number(e.target.value) || 1) }} /></label>
            <label className="small"> H <input data-testid="pg-preview-height" type="number" value={height} style={{ width: 64 }}
              onChange={(e) => { setPreset('custom'); setHeight(Number(e.target.value) || 1) }} /></label>
            <label className="small"> state{' '}
              <select data-testid="pg-preview-state" value={uiState} onChange={(e) => setUiState(e.target.value)}>
                {(preview.state_options || []).map((o) => <option key={o.state} value={o.state} title={o.evidence}>{o.label}</option>)}
              </select>
            </label>
            <select data-testid="pg-preview-setting" value={setting} onChange={(e) => setSetting(e.target.value)}>
              <option>Small UI</option><option>Normal UI</option><option>Large UI</option>
            </select>
            <input data-testid="pg-preview-seed" value={seed} onChange={(e) => setSeed(e.target.value)} style={{ width: 90 }} title="the placeholder seed (deterministic)" />
            <label className="small" style={{ display: 'block' }}>
              <input type="checkbox" data-testid="pg-preview-sim" checked={simVisible} onChange={(e) => setSimVisible(e.target.checked)} /> show simulated content
            </label>
            <label className="small" style={{ display: 'block' }}>
              <input type="checkbox" data-testid="pg-preview-competition" checked={competitionOn} onChange={(e) => setCompetitionOn(e.target.checked)} /> Bundesliga competition context (preview data, off by default)
            </label>
          </div>
          {preview.competition && <div className="small" data-testid="pg-preview-competition-context">
            competition context: <b>{preview.competition.bundesliga ? 'Bundesliga on' : 'off'}</b>{' '}
            <span className="dim">({preview.competition.label}; default off; {preview.competition.rules} rules in {preview.competition.bundle}; changing the sheet's definitions is a separate per-project choice, off by default)</span>
          </div>}
          <div className="small" data-testid="pg-preview-game-states">
            <b>game states (preview data; default scenario: {preview.game_states.scenario})</b>
            {preview.game_states.options.length === 0 && <div className="dim">this composition has no conditional slots</div>}
            {preview.game_states.options.map((o) => <label key={o.state} className="small" style={{ display: 'block' }}>
              <input type="checkbox" data-testid="pg-preview-game-state" data-state={o.state} checked={o.value}
                onChange={(e) => setGameStates({ ...gameStates, [o.state]: e.target.checked })} />{' '}
              {o.state} <span className="dim">(default {String(o.default)})</span>
            </label>)}
          </div>
          <div className="small" data-testid="pg-preview-slots">
            <b>optional slots (visibility follows the game states, inverse flags applied)</b>
            {preview.slots.length === 0 && <div className="dim">this composition has no optional slots</div>}
            {preview.slots.map((s) => <div key={s.id} className="small" data-testid="pg-preview-slot" data-slot={s.id}
              data-visible={String(s.visible)}>
              <span className={s.visible ? 'ok' : 'dim'}>{s.visible ? 'visible' : 'hidden'}</span>{' '}
              {s.kind} {s.element_id}{s.conditions.length > 0 ? ` (${s.conditions.join(', ')})` : ''}
            </div>)}
          </div>
          <div className="small" data-testid="pg-preview-compare-control">
            <label><input type="checkbox" data-testid="pg-preview-compare" checked={compareOn} onChange={(e) => setCompareOn(e.target.checked)} /> side-by-side comparison</label>
            {compareOn && <select data-testid="pg-preview-compare-preset" value={comparePreset} onChange={(e) => setComparePreset(e.target.value)}>
              <option value="1024x768">1024 x 768 (Small)</option>
              <option value="1440x900">1440 x 900 (Standard)</option>
              <option value="1920x1080">1920 x 1080 (Large)</option>
              <option value="2560x1440">2560 x 1440 (Large)</option>
            </select>}
          </div>
          {compareOn && compare && <div className="small" data-testid="pg-compare">
            <div data-testid="pg-compare-a">A {compare.a.width}x{compare.a.height}: {compare.a.composition} ({compare.a.evidence})</div>
            <div data-testid="pg-compare-b">B {compare.b.width}x{compare.b.height}: {compare.b.composition} ({compare.b.evidence})</div>
            <div data-testid="pg-compare-appear">appear: {compare.cells.appear.map((c) => c.element_id).join(', ') || 'none'}</div>
            <div data-testid="pg-compare-disappear">disappear: {compare.cells.disappear.map((c) => c.element_id).join(', ') || 'none'}</div>
            <div data-testid="pg-compare-changed">changed geometry: {compare.cells.changed.map((c) => c.element_id).join(', ') || 'none'}</div>
          </div>}
          <div className="small" data-testid="pg-preview-measured"><b>measured:</b> {preview.measured.map((m, i) => <div key={i} className="small dim">{m}</div>)}</div>
          <div className="small" data-testid="pg-preview-estimated"><b>estimated:</b> {preview.estimated.length === 0 && <span className="dim">nothing</span>}{preview.estimated.map((m, i) => <div key={i} className="small warn">{m}</div>)}</div>
        </div>}
        {mode === 'screen' && dumpMissing && <div className="pkg" data-testid="pg-preview-dump-missing">
          <b className="small">PREVIEW (5F)</b>
          <ReadLayoutDump say={say} onDone={loadDump} detail="The 5F preview is computed from the imported layout dump; reading the game builds it from your own files." />
        </div>}
        {mode === 'screen' && <div className="pkg" data-testid="pg-build-panel">
          <b className="small">BUILD SESSION (5G: routes by what is proven; installs nothing)</b>
          {routing && <div className="small" data-testid="pg-build-routing">
            <b>Build routing</b> {!routing.route_preference_explicit && <span className="dim">(default: {routing.default})</span>}
            <div data-testid="pg-build-route">
              <label><input type="radio" data-testid="pg-build-route-bundle" checked={routing.route_preference === 'bundle'}
                onChange={() => setRoutePreference('bundle')} /> Bundle</label>{' '}
              <label><input type="radio" data-testid="pg-build-route-skin" checked={routing.route_preference === 'skin_folder'}
                onChange={() => setRoutePreference('skin_folder')} /> Skin folder</label>
            </div>
            <div className="dim">{routing.tradeoffs[routing.route_preference]}</div>
            {routing.layout_route && <div data-testid="pg-layout-route" style={{ marginTop: 4 }}>
              <b>Layout edits</b> {!routing.layout_route_explicit && <span className="dim">(default: {routing.layout_route_default})</span>}{' '}
              <label><input type="radio" data-testid="pg-layout-route-custom" checked={routing.layout_route === 'custom_layout'}
                onChange={() => setLayoutRoute('custom_layout')} /> Custom-layout files</label>{' '}
              <label><input type="radio" data-testid="pg-layout-route-bundle" checked={routing.layout_route === 'bundle'}
                onChange={() => setLayoutRoute('bundle')} /> Bundle</label>
              <div className="dim">{routing.layout_route_note}</div>
            </div>}
            <label className="small" style={{ display: 'block' }}>
              <input type="checkbox" data-testid="pg-build-edit-competition" checked={routing.edit_competition_sheets}
                onChange={(e) => setCompetitionChoice(e.target.checked)} /> edit competition sheets' own definitions
            </label>
            <div className="dim">{routing.tradeoffs.edit_competition_sheets}</div>
          </div>}
          <div><button data-testid="pg-build" onClick={buildSession} disabled={buildBusy}>{buildBusy ? 'building...' : 'Build session'}</button></div>
          {buildReport && <>
            <div className="small" data-testid="pg-buildability">
              buildable: {buildReport.buildability ? (buildReport.buildability.buildable ? 'yes' : 'no') : (buildReport.blocked?.length ? 'no' : 'yes')}
              {buildReport.buildability && <span className="dim"> - {buildReport.buildability.reason}</span>}
            </div>
            <div className="small" data-testid="pg-build-ready">
              installation ready: {buildReport.installation_ready?.ready ? 'yes' : 'no'}
              {buildReport.installation_ready && <span className="dim"> - {buildReport.installation_ready.reason}</span>}
            </div>
            <div className="small" data-testid="pg-build-ops">
              {buildReport.operations.map((o) => <div key={o.id} data-testid="pg-build-op" data-route={o.route} data-kind={o.kind}>
                <span className={o.refused ? 'bad' : 'ok'}>{o.route}</span> {o.kind}
                <span className="dim"> - {o.reason}</span>
                {o.custom_layout_file && <div className="small" data-testid="pg-build-op-file">writes the custom-layout file {o.custom_layout_file}{o.replaces_user_file && <span className="warn"> - replaces the file you already have (needs your confirmation)</span>}</div>}
                {o.warning && <div className="small warn" data-testid="pg-build-op-warning">{o.warning}</div>}
                <div className="small dim">translation: {JSON.stringify(o.translation)}</div>
              </div>)}
            </div>
            {(buildReport.custom_layouts?.files.length ?? 0) > 0 && <div className="small" data-testid="pg-build-custom-files">
              <b>custom-layout files that will be written</b>
              {buildReport.custom_layouts!.files.map((f) => <div key={f.name} data-testid="pg-build-custom-file" data-name={f.name}>{f.name} <span className="dim">({f.size} bytes)</span>
                {buildReport.customised_in_game?.includes(f.name) && <span className="warn"> - customised in the game: replaces your file</span>}</div>)}
            </div>}
            {(buildReport.warnings?.length ?? 0) > 0 && <div className="small warn" data-testid="pg-build-warnings">
              {buildReport.warnings!.map((w) => <div key={w.id}>{w.kind}: {w.warning}</div>)}
            </div>}
            {buildReport.refusals.length > 0 && <div className="small warn" data-testid="pg-build-refusals">
              <b>refused</b>{buildReport.refusals.map((r) => <div key={r.id}>{r.kind}: {r.reason}</div>)}
            </div>}
            {buildReport.conflicts.length > 0 && <div className="small warn" data-testid="pg-build-conflicts">
              <b>conflicts</b>{buildReport.conflicts.map((c, i) => <div key={i}>{c.kind}: {c.reason}{c.cells ? ' (' + c.cells.join(', ') + ')' : ''}</div>)}
            </div>}
            {(buildReport.optional_slot_effects?.length ?? 0) > 0 && <div className="small warn" data-testid="pg-build-optional-slots">
              <b>optional tiles affected</b>
              {buildReport.optional_slot_effects!.map((e, i) => <div key={i}>{e.summary}</div>)}
            </div>}
            {(buildReport.addcell_placement_options?.length ?? 0) > 0 && <div className="small" data-testid="pg-build-addcell-options">
              <b>add-tile placement options</b>
              {buildReport.addcell_placement_options!.map((e) => <div key={e.op_id}>
                {e.element_id}: {e.options.map((o) => <span key={o.label} style={{ marginRight: 8 }}>
                  <b>{o.label}</b> at y={o.geometry.y} ({o.summary}{o.label === e.recommended.label ? ' - default: fewest optional tiles hidden' : ''})
                </span>)}
              </div>)}
            </div>}
            {buildReport.competition_warnings && (buildReport.competition_warnings.bundesliga_rules.length > 0
              || buildReport.competition_warnings.token_competition_sheets.length > 0) &&
              <div className="small warn" data-testid="pg-build-competition">
                <b>competition sheets</b> <span className="dim">(warnings only; changing their definitions is OFF by default)</span>
                {buildReport.competition_warnings.bundesliga_rules.map((w, i) => <div key={i} data-testid="pg-build-competition-rule">
                  {w.sheet} {w.selector} sets {w.properties.join(', ')} on an element this edit touches
                </div>)}
                {buildReport.competition_warnings.token_competition_sheets.map((t, i) => <div key={'t' + i} data-testid="pg-build-competition-token">
                  {t.token} is redefined by {t.redefined_by.map((d) => d.sheet).join(', ') || 'no competition sheet'}
                </div>)}
              </div>}
            {buildReport.cell_check && <div className="small" data-testid="pg-build-cells" data-ok={String(buildReport.cell_check.ok)}>
              <b>cell layer</b>: {buildReport.cell_check.ok ? 'intended = built' : 'DIFFERS'}
              {Object.entries(buildReport.cell_check.by_bundle).map(([b, v]) => <div key={b} className="small">
                <div>{b}</div>
                <div className="dim">intended: {JSON.stringify(v.intended)}</div>
                <div className="dim">built: {JSON.stringify(v.built_cell_changes)}</div>
              </div>)}
              {buildReport.cell_check.differences.map((d, i) => <div key={i} className="warn">{d}</div>)}
            </div>}
            <div className="small" data-testid="pg-build-outputs">
              target bundles: {buildReport.targets.join(', ') || 'none'} · affected (referrers): {buildReport.referrers.affected.join(', ') || 'none'}
              {buildReport.outputs.package && <div className="dim">package: {buildReport.outputs.package}</div>}
              {buildReport.outputs.skin_folder && <div className="dim">skin folder: {buildReport.outputs.skin_folder}</div>}
            </div>
            {buildReport.integrity && buildReport.integrity.length > 0 && <div className="small dim" data-testid="pg-build-integrity">
              integrity: {buildReport.integrity.map((i) => i.bundle + ': ' + i.status).join(' | ')}
            </div>}
            {onOpenInstall && <button data-testid="pg-build-open-install" onClick={onOpenInstall}>Open the Install view</button>}
          </>}
        </div>}
        {mode === 'layout' && <RenderBrowser picked={row ? row.bundle + row.path_id : null} onPick={setRow} say={say} />}
        {mode === 'screen' && <div className="pad" data-testid="pg-screens">
          <b className="small">COMPOSITIONS with tiles</b>
          {dump === undefined && <div className="dim small">checking for a layout dump ...</div>}
          {dumpMissing && <ReadLayoutDump say={say} onDone={loadDump} detail="The Playground and the 5F preview read the game’s own layouts; this only reads, and it never changes the game." />}
          {!dumpMissing && !screens && dump !== undefined && <div className="dim small">the screens list is loading (from the imported layout dump) ...</div>}
          {!dumpMissing && screens && <>
            <input data-testid="pg-screen-q" value={screenQ} placeholder="filter compositions" onChange={(e) => setScreenQ(e.target.value)} style={{ width: '100%' }} />
            <div style={{ maxHeight: 400, overflow: 'auto' }}>
              {screens.screens.filter((s) => !screenQ || s.name.toLowerCase().includes(screenQ.toLowerCase())).slice(0, 300).map((s) => (
                <div key={s.name} className="pgrow" data-testid="pg-screen-row" onClick={() => setScreen(s)}>{s.name} <span className="dim small">{s.cells.length} cells</span></div>
              ))}
            </div>
          </>}
        </div>}
      </div>
    </div>
  )
}
