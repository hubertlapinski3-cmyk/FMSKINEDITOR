import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { rpc, RpcError, subscribe } from './engine'
import Gutter, { useStoredSize } from './Gutter'

/* Offline render of a game layout (Phase 9, docs/PHASE9-PLAN.md): the engine resolves the tree, the cascade and the computed declarations; this draws them with CSS.
   It is an approximation and says so on every render. Nothing here decides which rule wins: the explain panel shows what the engine matched, flagged where a
   property could not be drawn faithfully. */

export type Flag = 'unknown' | 'unmapped' | 'partial' | null
export interface Computed { value: string; raw: string | null; tokens: string[] | null; source: Record<string, any>; unresolved: string[] | null; status: string; note: string; css: string[][]; inferred_name_from?: string }
export interface RNode {
  type: string; name: string; classes: string[]; runtime_classes: string[]; style: Record<string, string>; text: string | null; flag: Flag
  matched: { sheet: string; rule: number; selector: string; specificity: number; origin?: { file: string; selector: string } }[]; computed: Record<string, Computed>; children: RNode[]
  placeholder?: 'set' | 'sample' | 'empty' | null; font?: string | null
  layout?: string; include?: { alias: string; layout?: string; resolved: boolean; slot?: string; problem?: string }; components?: string[]
  /** M8: a node of a large layout whose children are not drawn yet (render/cap.py); its path is sent in `open` to expand it. */
  collapsed?: { children: number; descendants: number }
}
export interface Truncated { total: number; shown: number; cap: number; collapsed: number; opened: number }
export interface RResult {
  layout: string; notice: string; tree: RNode[]; includes: unknown[]; truncated?: Truncated | null; summary: { elements: number; properties: number; by_status: Record<string, number>; unresolved_variables: Record<string, number> }
  sheet_order: { position: number; sheet: string; why: string }[]; gaps: string[]; timing_ms: { total: number }
  origins?: Origins | null
  overlay?: { project: string; output: string; layout_patch_ops_applied: number; notes: string[]; not_applied: string[] } | null
}
/** Where a project's own rules and token overrides live in its files (engine `render.layout` with a project). */
export interface Origin { file: string; line: number | null; end: number | null; selector: string; sheet: string; ids: { sheet: string; rule: number }[] }
export interface Origins { rules: Origin[]; tokens: Record<string, { file: string; line: number }> }
export interface RuleData { sheet: string; rule: number; text: string; vanilla: boolean; origin: { file: string; line: number | null; end: number | null } | null; properties: { name: string; value: string }[]; token_rule: boolean }
export interface TokenData { name: string; value: string | null; chain: string[]; defs: Record<string, string> }
export interface LayoutRow { name: string; bundle: string; path_id: string; elements: number }

const DEFAULTS: CSSProperties = { boxSizing: 'border-box', display: 'flex', flexDirection: 'column', flexGrow: 0, flexShrink: 1, flexBasis: 'auto', alignItems: 'stretch', alignSelf: 'auto',
  alignContent: 'flex-start', justifyContent: 'flex-start', flexWrap: 'nowrap', position: 'relative', minWidth: 0, minHeight: 0, margin: 0, padding: 0, border: '0 solid transparent',
  overflow: 'visible', whiteSpace: 'normal', fontFamily: 'Arial, Helvetica, sans-serif', fontSize: 14, color: '#ebebeb' }   // UI Toolkit's (Yoga) initial values, which differ from CSS's

const camel = (k: string) => k.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase())
export const styleOf = (n: RNode): CSSProperties => ({ ...DEFAULTS, ...Object.fromEntries(Object.entries(n.style).map(([k, v]) => [camel(k), v])) })
export const labelOf = (n: RNode) => n.type + (n.name ? '#' + n.name : '') + n.classes.map((c) => '.' + c).join('')

/** The layouts of the game, filtered by name. */
export function RenderBrowser({ picked, onPick, say }: { picked: string | null; onPick: (r: LayoutRow) => void; say: (s: string) => void }) {
  const [q, setQ] = useState('')
  const [rows, setRows] = useState<LayoutRow[]>([])
  const [total, setTotal] = useState(0)
  const [err, setErr] = useState('')
  useEffect(() => {
    let live = true
    const t = setTimeout(() => {
      rpc<{ total: number; layouts: LayoutRow[] }>('render.layouts', { q, limit: 200 }).then((r) => { if (live) { setRows(r.layouts); setTotal(r.total); setErr('') } })
        .catch((e) => { if (live) { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) } })
    }, q ? 200 : 0)
    return () => { live = false; clearTimeout(t) }
  }, [q, say])
  return (
    <div className="rbrowser">
      <div className="head">GAME LAYOUTS ({total})</div>
      <input className="search" placeholder="Filter by name ..." value={q} onChange={(e) => setQ(e.target.value)} />
      {err && <div className="warn pad">{err}</div>}
      <ul>{rows.map((r) => <li key={r.bundle + r.path_id} className={picked === r.bundle + r.path_id ? 'sel' : ''} onClick={() => onPick(r)} title={r.bundle}>{r.name}<small> {r.elements}</small></li>)}</ul>
      {total > rows.length && <div className="dim pad small">Showing the first {rows.length} of {total}; narrow the filter.</div>}
    </div>
  )
}

function Node({ n, path, sel, onSel, markers, hl, onOpen }: { n: RNode; path: string; sel: string | null; onSel: (p: string) => void; markers: boolean; hl: Set<string>; onOpen?: (p: string) => void }) {
  return (
    <div className={'rnode' + (sel === path ? ' sel' : '') + (hl.has(path) ? ' hl' : '')} data-path={path} data-flag={markers && n.flag ? n.flag : undefined} data-placeholder={n.placeholder === 'sample' || n.placeholder === 'empty' ? n.placeholder : undefined}
      title={labelOf(n) + (n.placeholder === 'sample' ? ' | sample text from the layout, not the delivered value' : n.placeholder === 'empty' ? ' | no text known (bound or set from code)' : '') + (n.font ? ' | font ' + n.font + ' (stand-in drawn)' : '')} style={styleOf(n)}
      onClick={(e) => { e.stopPropagation(); onSel(path) }}>
      {n.text}
      {n.children.map((c, i) => <Node key={i} n={c} path={path + '/' + i} sel={sel} onSel={onSel} markers={markers} hl={hl} onOpen={onOpen} />)}
      {n.collapsed && <button type="button" className="rmore" data-testid="rmore" title={`${n.collapsed.descendants} elements below, not drawn yet`}
        onClick={(e) => { e.stopPropagation(); onOpen?.(path) }}>▸ show {n.collapsed.children} child element{n.collapsed.children === 1 ? '' : 's'} ({n.collapsed.descendants} in all)</button>}
    </div>
  )
}

function at(tree: RNode[], path: string | null): RNode | null {
  if (!path) return null
  const idx = path.split('/').map(Number)
  let n: RNode | undefined = tree[idx[0]]
  for (const i of idx.slice(1)) n = n?.children[i]
  return n ?? null
}

/** Paths of the nodes for which `test` holds (the Node paths used for selection: "0/2/1"). */
export function pathsWhere(tree: RNode[], test: (n: RNode) => boolean): string[] {
  const out: string[] = []
  const walk = (n: RNode, p: string) => { if (test(n)) out.push(p); n.children.forEach((c, i) => walk(c, p + '/' + i)) }
  tree.forEach((n, i) => walk(n, String(i)))
  return out
}
/** Rule -> elements: the nodes the cascade matched with any of these rule ids. */
export const rulePaths = (tree: RNode[], ids: { sheet: string; rule: number }[]) => pathsWhere(tree, (n) => n.matched.some((m) => ids.some((i) => i.sheet === m.sheet && i.rule === m.rule)))
/** Token -> elements: the nodes with a property whose value came through this token. */
export const tokenPaths = (tree: RNode[], token: string) => pathsWhere(tree, (n) => Object.values(n.computed).some((d) => d.tokens?.includes(token)))
/** Editor caret -> the project rule whose lines hold it. */
export const ruleAtLine = (o: Origins | null | undefined, file: string, line: number): Origin | null => o?.rules.find((r) => r.file === file && r.line != null && line >= r.line && line <= (r.end ?? r.line)) ?? null
/** The --token under a column of one line of USS text. */
export function tokenAt(text: string, col: number): string | null {
  for (const m of text.matchAll(/--[\w-]+/g)) if (m.index! < col && col <= m.index! + m[0].length) return m[0]
  return null
}

const ORDER: Record<string, number> = { unknown: 0, unmapped: 1, partial: 2, mapped: 3, variable: 4, shorthand: 5 }
const sourceText = (s: Record<string, any>) => s.inline ? 'inline (layout)' : s.inherited ? `inherited from ${s.from?.selector ?? s.from?.sheet ?? 'parent'}` : `${s.sheet}  ${s.selector}  (spec ${s.specificity})`

/** The explain panel: why this element looks the way it does, in the engine's cascade order, with every property that could not be drawn faithfully flagged. Rules and tokens
    are clickable: a rule opens as USS text (a project's own rule in the editor at its line, a game rule as read-only text with an override), a token shows its alias chain and
    definitions, and the open project's override of it. */
export function Explain({ n, project = null, skin = true, origins = null, onOpenFile, say = () => {} }: { n: RNode | null; project?: string | null; skin?: boolean; origins?: Origins | null; onOpenFile?: (file: string, line?: number) => void; say?: (s: string) => void }) {
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [box, setBox] = useState<{ kind: 'rule'; data: RuleData; selector: string } | { kind: 'token'; data: TokenData } | null>(null)
  const [value, setValue] = useState('')
  const fail = (e: unknown) => say('ERROR ' + (e instanceof RpcError ? e.message : String(e)))
  const openRule = (sheet: string, rule: number | undefined, selector: string) => {
    if (rule == null) return
    rpc<RuleData>('render.rule', { sheet, rule, ...(project ? { project, skin } : {}) }).then((data) => data && setBox({ kind: 'rule', data, selector })).catch(fail)
  }
  const openToken = (name: string) => { rpc<TokenData>('tokens.get', { name }).then((data) => { if (data) { setBox({ kind: 'token', data }); setValue('') } }).catch(fail) }
  const override = async (d: RuleData, selector: string) => {
    if (!project) return
    try {
      const p = await rpc<any>('project.get', { name: project })
      p.scoped_rules = [...(p.scoped_rules ?? []), { sheet: d.sheet, selector, props: Object.fromEntries(d.properties.map((x) => [x.name, x.value])), why: 'override started from the render' }]
      await rpc('project.save', { project: p })
      say(`override of ${selector} added to styles/${d.sheet}.uss`)
      onOpenFile?.(`styles/${d.sheet}.uss`)
    } catch (e) { fail(e) }
  }
  const setOverride = async (token: string) => {
    if (!project || !value.trim()) return
    try {
      const p = await rpc<any>('project.get', { name: project })
      p.token_overrides = [...(p.token_overrides ?? []).filter((x: any) => x.token !== token), { token, value: value.trim() }]
      await rpc('project.save', { project: p })
      say(`${token} overridden in ${project}`)
    } catch (e) { fail(e) }
  }
  if (!n) return <div className="dim pad">Click an element to see which rules matched it and where each value comes from.</div>
  const props = Object.entries(n.computed).sort((a, b) => (ORDER[a[1].status] ?? 9) - (ORDER[b[1].status] ?? 9) || a[0].localeCompare(b[0]))
    .filter(([, d]) => !flaggedOnly || ['unknown', 'unmapped', 'partial'].includes(d.status))
  return (
    <div className="explain">
      <div className="pad"><b className="mono">{labelOf(n)}</b>{n.runtime_classes.length > 0 && <div className="small dim" title="Classes the control adds in code, learned from inspector captures">runtime classes (learned): {n.runtime_classes.join(' ')}</div>}
        {n.include && <div className="small dim">template {n.include.alias} {n.include.resolved ? `-> ${n.include.layout} (${n.include.slot})` : `NOT resolved: ${n.include.problem}`}</div>}
        {n.layout && <div className="small dim">from layout {n.layout}</div>}</div>
      {box && <div className="rbox pad" data-testid="rulebox">
        {box.kind === 'rule' ? <>
          <div className="head">RULE · {box.data.sheet} #{box.data.rule} · {box.data.vanilla ? 'game (read-only)' : 'project'}<button className="x" aria-label="close" onClick={() => setBox(null)}>×</button></div>
          <pre className="mono small">{box.data.text}</pre>
          {box.data.origin
            ? <button onClick={() => onOpenFile?.(box.data.origin!.file, box.data.origin!.line ?? undefined)}>Open {box.data.origin.file}{box.data.origin.line ? ':' + box.data.origin.line : ''} in the editor</button>
            : project ? <button onClick={() => override(box.data, box.selector)}>Override in {project}</button> : <span className="dim small">Open a project to override this rule.</span>}
        </> : <>
          <div className="head">TOKEN · {box.data.name}<button className="x" aria-label="close" onClick={() => setBox(null)}>×</button></div>
          <div className="small mono">{box.data.chain.join(' → ')}{box.data.value ? ' = ' + box.data.value : ''}</div>
          <ul className="small">{Object.entries(box.data.defs ?? {}).map(([s, v]) => <li key={s}><span className="dim">{s}</span> <span className="mono">{v}</span></li>)}</ul>
          {origins?.tokens[box.data.name]
            ? <button onClick={() => onOpenFile?.(origins.tokens[box.data.name].file, origins.tokens[box.data.name].line)}>Open the project's override ({origins.tokens[box.data.name].file}:{origins.tokens[box.data.name].line})</button>
            : project ? <span><input placeholder="new value, e.g. #FF0000" value={value} onChange={(e) => setValue(e.target.value)} /> <button disabled={!value.trim()} onClick={() => setOverride(box.data.name)}>Override in {project}</button></span> : <span className="dim small">Open a project to override this token.</span>}
        </>}
      </div>}
      <div className="head">MATCHED RULES ({n.matched.length}), lowest first, the last one wins</div>
      {n.matched.length === 0 && <div className="dim pad small">No rule matched; only the layout's inline style and inheritance apply.</div>}
      <table className="rtable"><tbody>{n.matched.map((m, i) => <tr key={i} className="clickable" title={m.origin ? 'a rule of the open project' : 'a rule of the game'} onClick={() => openRule(m.sheet, m.rule, m.selector)}><td>{m.sheet}{m.origin && <span className="badge" title="project rule">project</span>}</td><td className="mono">{m.selector}</td><td>{m.specificity}</td></tr>)}</tbody></table>
      <div className="head">COMPUTED ({props.length}) <label className="small"><input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} /> flagged only</label></div>
      <table className="rtable"><tbody>{props.map(([k, d]) => (
        <tr key={k} className={'st-' + d.status}>
          <td className="mono">{k}{d.inferred_name_from && <span className="badge" title={`name inferred from ${d.inferred_name_from} by numbering and value pattern`}>inferred</span>}</td>
          <td className="mono" title={d.raw ?? ''}>{d.value}{d.tokens && <div className="small dim">{d.tokens.map((tk, i) => <span key={tk}>{i > 0 && ' → '}<button className="chip" onClick={() => openToken(tk)}>{tk}</button></span>)}</div>}{d.unresolved && <div className="small bad">unresolved: {d.unresolved.join(', ')}</div>}</td>
          <td><span className={'badge st ' + d.status} title={d.note}>{d.status}</span></td>
          <td className="small dim">{d.source.rule != null && !d.source.inherited ? <button className="chip" onClick={() => openRule(d.source.sheet, d.source.rule, d.source.selector)}>{sourceText(d.source)}</button> : sourceText(d.source)}</td>
        </tr>))}</tbody></table>
    </div>
  )
}

/** The first render after the Studio starts reads and cascades the game's stylesheets (about 9 to 13 seconds on the S0 machine, then instant): say so in words. */
export const FIRST_RENDER_TEXT = "Reading the game's styles for the first time. This takes about ten seconds and happens once."
let renderedOnce = false

/** One layout drawn from its render tree, with the explain panel beside it. */
export function RenderCanvas({ layout, say, project = null, onOpenFile, onResult, highlight = [] }: { layout: LayoutRow | null; say: (s: string) => void; project?: string | null; onOpenFile?: (file: string, line?: number) => void; onResult?: (r: RResult | null, layout: LayoutRow | null) => void; highlight?: string[] }) {
  const [res, setRes] = useState<RResult | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [sel, setSel] = useState<string | null>(null)
  const [w, setW] = useState(800)
  const [h, setH] = useState(600)
  const [zoom, setZoom] = useState(1)
  const [markers, setMarkers] = useState(true)
  const [skin, setSkin] = useState(true)          // the vanilla/skin toggle: on = the open project's edits are drawn, off = the game as it ships
  const [tick, setTick] = useState(0)             // bumped by every `render.invalidate` event of the open project, so the view repaints after any edit
  const [explainW, setExplainW] = useStoredSize('studio.explainW', 400, 240, 800)
  // M8, large layouts: the engine cuts the tree to about 1,000 nodes; `open` is the list of collapsed nodes the user expanded, `all` asks for every node. Both belong to one layout and reset with it.
  const key = layout ? layout.bundle + '|' + layout.path_id : ''
  const [ex, setEx] = useState<{ key: string; open: string[]; all: boolean }>({ key: '', open: [], all: false })
  const open = ex.key === key ? ex.open : []
  const all = ex.key === key && ex.all
  const openKey = open.join(',')
  const lastKey = useRef('')
  useEffect(() => {
    if (!layout) return
    let live = true
    setBusy(true); setErr('')
    if (lastKey.current !== key) { setSel(null); lastKey.current = key }            // expanding a branch keeps the selection; another layout clears it
    rpc<RResult>('render.layout', { bundle: layout.bundle, path_id: layout.path_id, ...(project ? { project, skin } : {}), ...(open.length ? { open } : {}), ...(all ? { max_nodes: 0 } : {}) }).then((r) => { renderedOnce = true; if (live) { setRes(r); setBusy(false); onResult?.(r, layout) } })
      .catch((e) => { if (live) { const m = e instanceof RpcError ? e.message : String(e); setErr(m); setBusy(false); say('ERROR ' + m) } })
    return () => { live = false }
  }, [layout, say, project, skin, tick, openKey, all])      // eslint-disable-line react-hooks/exhaustive-deps
  const openNode = (p: string) => setEx((s) => ({ key, open: [...(s.key === key ? s.open : []), p], all: false }))
  useEffect(() => subscribe((t, d) => { if (t === 'render.invalidate' && project && d?.project === project) setTick((n) => n + 1) }), [project])
  const node = useMemo(() => (res ? at(res.tree, sel) : null), [res, sel])
  const hl = useMemo(() => new Set(highlight), [highlight])
  if (!layout) return <div className="empty">Pick a game layout on the left to see it drawn.</div>
  const by = res?.summary.by_status ?? {}
  return (
    <div className="rsplit">
      <div className="rmain">
        <div className="rbar">
          <b>{layout.name}</b>
          {project && <label title="Draw the open project's edits over the game's own styles"><input type="checkbox" checked={skin} onChange={(e) => setSkin(e.target.checked)} /> skin: {project}</label>}
          <label>width <input type="number" value={w} min={10} max={4000} onChange={(e) => setW(Number(e.target.value) || 10)} /></label>
          <label>height <input type="number" value={h} min={10} max={4000} onChange={(e) => setH(Number(e.target.value) || 10)} /></label>
          <label>zoom <select value={zoom} onChange={(e) => setZoom(Number(e.target.value))}>{[0.25, 0.5, 0.75, 1, 1.5, 2].map((z) => <option key={z} value={z}>{z * 100}%</option>)}</select></label>
          <label><input type="checkbox" checked={markers} onChange={(e) => setMarkers(e.target.checked)} /> markers</label>
          {busy && <span className="dim" data-testid="render-progress">{renderedOnce ? 'rendering ...' : FIRST_RENDER_TEXT}</span>}
          {res && <span className="dim small">{res.summary.elements} elements · {res.timing_ms.total} ms</span>}
        </div>
        {res && <div className="rnotice" role="note">{res.notice}</div>}
        {res?.truncated && <div className="rnotice" role="status" data-testid="truncated">Large layout: {res.truncated.shown.toLocaleString()} of {res.truncated.total.toLocaleString()} elements are drawn
          ({res.truncated.collapsed} collapsed branch{res.truncated.collapsed === 1 ? '' : 'es'}). Use a "show" button inside the stage to open one branch, or{' '}
          <button type="button" className="link" onClick={() => setEx({ key, open: [], all: true })}>draw all {res.truncated.total.toLocaleString()}</button> (slower, a large payload).</div>}
        {all && res && !res.truncated && <div className="rnotice" role="status">Every element is drawn. <button type="button" className="link" onClick={() => setEx({ key, open: [], all: false })}>back to the capped view</button></div>}
        {res && <div className="small pad rfid">Properties on this render: {Object.entries(by).map(([k, v]) => <span key={k} className={'badge st ' + k}>{k} {v}</span>)}
          {markers && <span className="dim"> · corner marker: red = unknown or unmapped property, amber = partial</span>}</div>}
        {err && <div className="warn pad">{err}</div>}
        <div className="rscroll" onClick={() => setSel(null)}>
          <div className="rstage" data-testid="stage" style={{ width: w, height: h, transform: `scale(${zoom})` }}>
            {res?.tree.map((n, i) => <Node key={i} n={n} path={String(i)} sel={sel} onSel={setSel} markers={markers} hl={hl} onOpen={openNode} />)}
          </div>
        </div>
        {res?.overlay && <details className="small pad" open={res.overlay.notes.length > 0}><summary>Project overlay: {res.overlay.project} ({res.overlay.output}), {res.overlay.layout_patch_ops_applied} layout patch op(s) applied{res.overlay.notes.length ? `, ${res.overlay.notes.length} note(s)` : ''}</summary>
          <ul>{res.overlay.notes.map((n, i) => <li key={i}>{n}</li>)}</ul><div className="dim">Not applied in this view: {res.overlay.not_applied.join('; ')}</div></details>}
        {res && res.gaps.length > 0 && <details className="small pad"><summary>What this render does not know ({res.gaps.length})</summary><ul>{res.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
          <div>Sheet order: {res.sheet_order.map((s) => s.sheet).join(' → ')}</div></details>}
      </div>
      <Gutter axis="x" invert inflow value={explainW} min={240} max={800} def={400} onChange={setExplainW} label="Explain panel width" />
      <aside className="rexplain" style={{ width: explainW }}><Explain n={node} project={project} skin={skin} origins={res?.origins ?? null} onOpenFile={onOpenFile} say={say} /></aside>
    </div>
  )
}
