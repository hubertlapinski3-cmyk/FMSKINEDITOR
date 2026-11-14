import { useCallback, useEffect, useMemo, useState } from 'react'
import { rpc, RpcError } from './engine'

/* The two engine-only render calls as Studio views (v1.1.0): a whole screen's tiles placed on the game's grid (`render.screen`) and a table view as a labelled placeholder table
   (`render.table`). Like the layout render they are an approximation and say so: nothing here decides a position or a column, the engine does; this draws what it returns. */

interface Host { element_id: string; col: number; row: number; w: number; h: number; mode?: string[]; px: { left: number; top: number; width: number; height: number }; tile_layout: string | null; tile_how: string | null; placeholder?: string }
export interface ScreenRes { composition: string; pitch: { cell: number; gap: number; measured: boolean; flag: string | null }; grid: { columns: number; rows: number }; hosts: Host[]; runtime_slots: Host[]; flags: string[] }
interface Variant { breakpoint: number; composition: string }
interface Panel { panel_id: string; area: string; tiles: number }
interface TableRow { name: string; path_id: string; columns: number }
export interface TableRes { view: string; path_id: string; edited: boolean; ops: number; notes: string[]; breakpoint: number | null; columns: { id: string; width: number | null; header_text_id?: number | null }[]; label: string }

const errText = (e: unknown) => (e instanceof RpcError ? e.message : String(e))

/** A screen's composition on a grid container of a given size: the cells as boxes, each named and tagged with the tile layout the engine chose. */
export function RenderScreenView({ project, say }: { project: string | null; say: (s: string) => void }) {
  const [q, setQ] = useState('')
  const [panels, setPanels] = useState<Panel[]>([])
  const [panel, setPanel] = useState('')
  const [variants, setVariants] = useState<Variant[]>([])
  const [comp, setComp] = useState('')
  const [w, setW] = useState(2468.8)
  const [h, setH] = useState(1319.3)
  const [reserved, setReserved] = useState(0)
  const [padding, setPadding] = useState(12)
  const [skin, setSkin] = useState(true)
  const [res, setRes] = useState<ScreenRes | null>(null)
  const [err, setErr] = useState('')
  const fail = useCallback((e: unknown) => { const m = errText(e); setErr(m); say('ERROR ' + m) }, [say])

  useEffect(() => {
    const t = setTimeout(() => rpc<{ screens: Panel[] }>('layout.screens', { q }).then((r) => { setPanels(r.screens.filter((s) => s.tiles > 0)); setErr('') }).catch(fail), q ? 200 : 0)
    return () => clearTimeout(t)
  }, [q, fail])
  useEffect(() => {
    if (!panel) return
    rpc<{ sets: { variants: Variant[] }[] }>('layout.screen', { panel }).then((s) => { const vs = s.sets.flatMap((x) => x.variants); setVariants(vs); setComp(vs[0]?.composition ?? '') }).catch(fail)
  }, [panel, fail])
  useEffect(() => {
    if (!comp) return
    let live = true
    rpc<ScreenRes>('render.screen', { composition: comp, width: w, height: h, reserved_right: reserved, padding, ...(project ? { project, skin } : {}) })
      .then((r) => { if (live) { setRes(r); setErr('') } }).catch((e) => { if (live) fail(e) })
    return () => { live = false }
  }, [comp, w, h, reserved, padding, project, skin, fail])

  const scale = useMemo(() => Math.min(1, 900 / Math.max(w, 1)), [w])
  const flags = res ? [...(res.pitch.flag ? [res.pitch.flag] : []), ...res.flags.filter((f) => f !== res.pitch.flag)] : []
  return (
    <div className="rsplit" data-testid="screenview">
      <aside className="rbrowser">
        <div className="head">SCREENS</div>
        <input className="search" placeholder="Filter screens ..." value={q} onChange={(e) => setQ(e.target.value)} />
        <ul>{panels.map((p) => <li key={p.panel_id} className={panel === p.panel_id ? 'sel' : ''} onClick={() => setPanel(p.panel_id)}>{p.panel_id}<small> {p.tiles}</small></li>)}</ul>
      </aside>
      <div className="rmain">
        <div className="rbar">
          <label>composition <select value={comp} onChange={(e) => setComp(e.target.value)}>{variants.map((v) => <option key={v.composition + v.breakpoint} value={v.composition}>{v.composition}</option>)}</select></label>
          <label>width <input type="number" value={w} min={100} max={5000} onChange={(e) => setW(Number(e.target.value) || 100)} /></label>
          <label>height <input type="number" value={h} min={100} max={5000} onChange={(e) => setH(Number(e.target.value) || 100)} /></label>
          <label title="columns held back on the right for slots the composition does not hold">reserved <input type="number" value={reserved} min={0} max={20} onChange={(e) => setReserved(Number(e.target.value) || 0)} /></label>
          <label>padding <input type="number" value={padding} min={0} max={40} onChange={(e) => setPadding(Number(e.target.value) || 0)} /></label>
          {project && <label title="Apply the open project's tile moves"><input type="checkbox" checked={skin} onChange={(e) => setSkin(e.target.checked)} /> skin: {project}</label>}
          {res && <span className="dim small">{res.grid.columns} x {res.grid.rows} grid · {res.hosts.length} cells</span>}
        </div>
        <div className="rnotice" role="note">Approximation: the grid model was fitted to captures of a few screens and checked on three others; cells show the tile layout the engine chose. It never shows live data.</div>
        {flags.map((f, i) => <div key={i} className="rnotice" role="alert">{f}</div>)}
        {err && <div className="warn pad">{err}</div>}
        {!res && !err && <div className="empty">Pick a screen on the left, then a composition.</div>}
        <div className="rscroll"><div className="rstage" data-testid="screenstage" style={{ position: 'relative', width: w, height: h, transform: `scale(${scale})`, transformOrigin: '0 0', background: '#11151f' }}>
          {res && [...res.hosts, ...res.runtime_slots].map((c) => (
            <div key={c.element_id + c.col + ',' + c.row} className="rcell" data-element={c.element_id} title={`${c.element_id} · ${c.w}x${c.h} · ${c.tile_how ?? ''}`}
              style={{ position: 'absolute', left: c.px.left, top: c.px.top, width: c.px.width, height: c.px.height, border: '1px solid #61afef', background: 'rgba(97,175,239,.12)', overflow: 'hidden', fontSize: 14, padding: 4, boxSizing: 'border-box' }}>
              <b>{c.element_id}</b><div className="small dim">{c.tile_layout ?? 'no tile layout'}{c.placeholder ? ' · run-time slot' : ''}</div>
            </div>))}
        </div></div>
      </div>
    </div>
  )
}

/** A table view as the game would build its header row: the columns in order, cells as labelled placeholders (no data). */
export function RenderTableView({ project, say }: { project: string | null; say: (s: string) => void }) {
  const [q, setQ] = useState('')
  const [rows, setRows] = useState<TableRow[]>([])
  const [total, setTotal] = useState(0)
  const [pid, setPid] = useState('')
  const [bp, setBp] = useState('')
  const [skin, setSkin] = useState(true)
  const [res, setRes] = useState<TableRes | null>(null)
  const [err, setErr] = useState('')
  const fail = useCallback((e: unknown) => { const m = errText(e); setErr(m); say('ERROR ' + m) }, [say])
  useEffect(() => {
    const t = setTimeout(() => rpc<{ total: number; views: TableRow[] }>('tables.list', { q, limit: 200 }).then((r) => { setRows(r.views); setTotal(r.total); setErr('') }).catch(fail), q ? 200 : 0)
    return () => clearTimeout(t)
  }, [q, fail])
  useEffect(() => {
    if (!pid) return
    let live = true
    rpc<TableRes>('render.table', { path_id: pid, ...(bp !== '' ? { breakpoint: Number(bp) } : {}), ...(project ? { project, skin } : {}) })
      .then((r) => { if (live) { setRes(r); setErr('') } }).catch((e) => { if (live) fail(e) })
    return () => { live = false }
  }, [pid, bp, project, skin, fail])
  return (
    <div className="rsplit" data-testid="tableview">
      <aside className="rbrowser">
        <div className="head">TABLE VIEWS ({total})</div>
        <input className="search" placeholder="Filter table views ..." value={q} onChange={(e) => setQ(e.target.value)} />
        <ul>{rows.map((r) => <li key={r.path_id} className={pid === r.path_id ? 'sel' : ''} onClick={() => setPid(r.path_id)}>{r.name}<small> {r.columns}</small></li>)}</ul>
      </aside>
      <div className="rmain">
        <div className="rbar">
          <b>{res?.view ?? 'Table view'}</b>
          <label title="the breakpoint of the screen the table sits on; blank shows every column">breakpoint <input type="number" value={bp} min={0} max={9} onChange={(e) => setBp(e.target.value)} /></label>
          {project && <label title="Apply the open project's column edits"><input type="checkbox" checked={skin} onChange={(e) => setSkin(e.target.checked)} /> skin: {project}</label>}
          {res && <span className="dim small">{res.columns.length} columns{res.edited ? ` · ${res.ops} edit(s) applied` : ''}</span>}
        </div>
        <div className="rnotice" role="note">{res?.label ?? 'Placeholder table: the header row is the column order the game builds; the cells hold no data.'}</div>
        {(res?.notes ?? []).map((n, i) => <div key={i} className="rnotice" role="alert">{n}</div>)}
        {err && <div className="warn pad">{err}</div>}
        {!res && !err && <div className="empty">Pick a table view on the left.</div>}
        {res && <div className="rscroll"><table className="rtable" data-testid="placeholdertable"><thead><tr>{res.columns.map((c) => <th key={c.id} title={c.id}>{c.id}<div className="small dim">{c.width ?? 'auto'}</div></th>)}</tr></thead>
          <tbody>{[0, 1, 2].map((r) => <tr key={r}>{res.columns.map((c) => <td key={c.id} className="dim small">placeholder</td>)}</tr>)}</tbody></table></div>}
      </div>
    </div>
  )
}
