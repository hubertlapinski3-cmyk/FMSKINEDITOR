import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { rpc, RpcError } from './engine'
import Gutter, { useStoredSize } from './Gutter'

/* Offline render of a game layout (Phase 9, docs/PHASE9-PLAN.md): the engine resolves the tree, the cascade and the computed declarations; this draws them with CSS.
   It is an approximation and says so on every render. Nothing here decides which rule wins: the explain panel shows what the engine matched, flagged where a
   property could not be drawn faithfully. */

export type Flag = 'unknown' | 'unmapped' | 'partial' | null
export interface Computed { value: string; raw: string | null; tokens: string[] | null; source: Record<string, any>; unresolved: string[] | null; status: string; note: string; css: string[][]; inferred_name_from?: string }
export interface RNode {
  type: string; name: string; classes: string[]; runtime_classes: string[]; style: Record<string, string>; text: string | null; flag: Flag
  matched: { sheet: string; rule: number; selector: string; specificity: number }[]; computed: Record<string, Computed>; children: RNode[]
  placeholder?: 'set' | 'sample' | 'empty' | null; font?: string | null
  layout?: string; include?: { alias: string; layout?: string; resolved: boolean; slot?: string; problem?: string }; components?: string[]
}
export interface RResult {
  layout: string; notice: string; tree: RNode[]; includes: unknown[]; summary: { elements: number; properties: number; by_status: Record<string, number>; unresolved_variables: Record<string, number> }
  sheet_order: { position: number; sheet: string; why: string }[]; gaps: string[]; timing_ms: { total: number }
}
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

function Node({ n, path, sel, onSel, markers }: { n: RNode; path: string; sel: string | null; onSel: (p: string) => void; markers: boolean }) {
  return (
    <div className={'rnode' + (sel === path ? ' sel' : '')} data-path={path} data-flag={markers && n.flag ? n.flag : undefined} data-placeholder={n.placeholder === 'sample' || n.placeholder === 'empty' ? n.placeholder : undefined}
      title={labelOf(n) + (n.placeholder === 'sample' ? ' | sample text from the layout, not the delivered value' : n.placeholder === 'empty' ? ' | no text known (bound or set from code)' : '') + (n.font ? ' | font ' + n.font + ' (stand-in drawn)' : '')} style={styleOf(n)}
      onClick={(e) => { e.stopPropagation(); onSel(path) }}>
      {n.text}
      {n.children.map((c, i) => <Node key={i} n={c} path={path + '/' + i} sel={sel} onSel={onSel} markers={markers} />)}
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

const ORDER: Record<string, number> = { unknown: 0, unmapped: 1, partial: 2, mapped: 3, variable: 4, shorthand: 5 }
const sourceText = (s: Record<string, any>) => s.inline ? 'inline (layout)' : s.inherited ? `inherited from ${s.from?.selector ?? s.from?.sheet ?? 'parent'}` : `${s.sheet}  ${s.selector}  (spec ${s.specificity})`

/** The explain panel: why this element looks the way it does, in the engine's cascade order, with every property that could not be drawn faithfully flagged. */
export function Explain({ n }: { n: RNode | null }) {
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  if (!n) return <div className="dim pad">Click an element to see which rules matched it and where each value comes from.</div>
  const props = Object.entries(n.computed).sort((a, b) => (ORDER[a[1].status] ?? 9) - (ORDER[b[1].status] ?? 9) || a[0].localeCompare(b[0]))
    .filter(([, d]) => !flaggedOnly || ['unknown', 'unmapped', 'partial'].includes(d.status))
  return (
    <div className="explain">
      <div className="pad"><b className="mono">{labelOf(n)}</b>{n.runtime_classes.length > 0 && <div className="small dim" title="Classes the control adds in code, learned from inspector captures">runtime classes (learned): {n.runtime_classes.join(' ')}</div>}
        {n.include && <div className="small dim">template {n.include.alias} {n.include.resolved ? `-> ${n.include.layout} (${n.include.slot})` : `NOT resolved: ${n.include.problem}`}</div>}
        {n.layout && <div className="small dim">from layout {n.layout}</div>}</div>
      <div className="head">MATCHED RULES ({n.matched.length}), lowest first, the last one wins</div>
      {n.matched.length === 0 && <div className="dim pad small">No rule matched; only the layout's inline style and inheritance apply.</div>}
      <table className="rtable"><tbody>{n.matched.map((m, i) => <tr key={i}><td>{m.sheet}</td><td className="mono">{m.selector}</td><td>{m.specificity}</td></tr>)}</tbody></table>
      <div className="head">COMPUTED ({props.length}) <label className="small"><input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} /> flagged only</label></div>
      <table className="rtable"><tbody>{props.map(([k, d]) => (
        <tr key={k} className={'st-' + d.status}>
          <td className="mono">{k}{d.inferred_name_from && <span className="badge" title={`name inferred from ${d.inferred_name_from} by numbering and value pattern`}>inferred</span>}</td>
          <td className="mono" title={d.raw ?? ''}>{d.value}{d.tokens && <div className="small dim">{d.tokens.join(' → ')}</div>}{d.unresolved && <div className="small bad">unresolved: {d.unresolved.join(', ')}</div>}</td>
          <td><span className={'badge st ' + d.status} title={d.note}>{d.status}</span></td>
          <td className="small dim">{sourceText(d.source)}</td>
        </tr>))}</tbody></table>
    </div>
  )
}

/** One layout drawn from its render tree, with the explain panel beside it. */
export function RenderCanvas({ layout, say }: { layout: LayoutRow | null; say: (s: string) => void }) {
  const [res, setRes] = useState<RResult | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [sel, setSel] = useState<string | null>(null)
  const [w, setW] = useState(800)
  const [h, setH] = useState(600)
  const [zoom, setZoom] = useState(1)
  const [markers, setMarkers] = useState(true)
  const [explainW, setExplainW] = useStoredSize('studio.explainW', 400, 240, 800)
  useEffect(() => {
    if (!layout) return
    let live = true
    setBusy(true); setErr(''); setSel(null)
    rpc<RResult>('render.layout', { bundle: layout.bundle, path_id: layout.path_id }).then((r) => { if (live) { setRes(r); setBusy(false) } })
      .catch((e) => { if (live) { const m = e instanceof RpcError ? e.message : String(e); setErr(m); setBusy(false); say('ERROR ' + m) } })
    return () => { live = false }
  }, [layout, say])
  const node = useMemo(() => (res ? at(res.tree, sel) : null), [res, sel])
  if (!layout) return <div className="empty">Pick a game layout on the left to see it drawn.</div>
  const by = res?.summary.by_status ?? {}
  return (
    <div className="rsplit">
      <div className="rmain">
        <div className="rbar">
          <b>{layout.name}</b>
          <label>width <input type="number" value={w} min={10} max={4000} onChange={(e) => setW(Number(e.target.value) || 10)} /></label>
          <label>height <input type="number" value={h} min={10} max={4000} onChange={(e) => setH(Number(e.target.value) || 10)} /></label>
          <label>zoom <select value={zoom} onChange={(e) => setZoom(Number(e.target.value))}>{[0.25, 0.5, 0.75, 1, 1.5, 2].map((z) => <option key={z} value={z}>{z * 100}%</option>)}</select></label>
          <label><input type="checkbox" checked={markers} onChange={(e) => setMarkers(e.target.checked)} /> markers</label>
          {busy && <span className="dim">rendering ...</span>}
          {res && <span className="dim small">{res.summary.elements} elements · {res.timing_ms.total} ms</span>}
        </div>
        {res && <div className="rnotice" role="note">{res.notice}</div>}
        {res && <div className="small pad rfid">Properties on this render: {Object.entries(by).map(([k, v]) => <span key={k} className={'badge st ' + k}>{k} {v}</span>)}
          {markers && <span className="dim"> · corner marker: red = unknown or unmapped property, amber = partial</span>}</div>}
        {err && <div className="warn pad">{err}</div>}
        <div className="rscroll" onClick={() => setSel(null)}>
          <div className="rstage" data-testid="stage" style={{ width: w, height: h, transform: `scale(${zoom})` }}>
            {res?.tree.map((n, i) => <Node key={i} n={n} path={String(i)} sel={sel} onSel={setSel} markers={markers} />)}
          </div>
        </div>
        {res && res.gaps.length > 0 && <details className="small pad"><summary>What this render does not know ({res.gaps.length})</summary><ul>{res.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
          <div>Sheet order: {res.sheet_order.map((s) => s.sheet).join(' → ')}</div></details>}
      </div>
      <Gutter axis="x" invert inflow value={explainW} min={240} max={800} def={400} onChange={setExplainW} label="Explain panel width" />
      <aside className="rexplain" style={{ width: explainW }}><Explain n={node} /></aside>
    </div>
  )
}
