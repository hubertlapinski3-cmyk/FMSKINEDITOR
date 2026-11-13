import { useCallback, useEffect, useState } from 'react'
import { rpc, RpcError } from './engine'

interface Row { name: string; path_id: string; columns: number }
interface Cell { default_width: number; minimum_width: number; cell_layout: string; cell_layout_guid: string; header_text_id: number | null; sortable: boolean }
interface Col { index: number; id: string; width: number; min_width: number; required: boolean; sorting_disabled: boolean; priority: number; breakpoints: number; conditions: number; cell: Cell | null }
interface View { name: string; path_id: string; columns: Col[]; available: (Cell & { id: string })[]; factory: { name: string; coverage: number; cells: number } | null; patches?: { ops: any[] } | null }

/** Table view browser and editor: the game's column sets with what each column's row cell draws, and edits to width, visibility and order
 *  (small per-view patch files, bundle target only). */
export default function Tables({ project, target, onChanged, say }: { project: string | null; target: string; onChanged: () => void; say: (s: string) => void }) {
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [view, setView] = useState<View | null>(null)
  const [add, setAdd] = useState('')
  const [err, setErr] = useState('')
  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) }, [say])

  useEffect(() => {
    const t = setTimeout(() => rpc<{ total: number; views: Row[] }>('tables.list', { q, limit: 200 }).then((r) => { setRows(r.views); setTotal(r.total); setErr('') }).catch(fail), 200)
    return () => clearTimeout(t)
  }, [q, fail])

  const load = useCallback(async (pid: string) => { try { setView(await rpc<View>('tables.view', { path_id: pid, ...(project ? { project } : {}) })); setErr('') } catch (e) { fail(e) } }, [project, fail])
  const edit = async (op: Record<string, unknown>) => {
    if (!project || !view) return
    try { await rpc('tables.edit', { project, name: view.name, path_id: view.path_id, op }); await load(view.path_id); onChanged(); say(`table edit stored: ${view.name} ${op.op} ${op.column}`) } catch (e) { fail(e) }
  }
  const revert = async () => { if (!project || !view) return; try { await rpc('tables.unedit', { project, name: view.name }); await load(view.path_id); onChanged() } catch (e) { fail(e) } }
  const patched = (id: string) => (view?.patches?.ops ?? []).filter((o) => o.column === id).map((o) => o.op)
  const hasOps = (view?.patches?.ops?.length ?? 0) > 0
  const addable = (view?.available ?? []).filter((a) => !add || a.id.toLowerCase().includes(add.toLowerCase())).slice(0, 40)

  return (
    <div className="tables">
      <div className="head">TABLE VIEWS ({total})</div>
      {target !== 'bundles' && project && <div className="warn pad">This project's target is <b>{target}</b>: table edits only apply to the bundle target (the native build drops them and says so).</div>}
      {err && <div className="warn pad">{err}</div>}
      {!view && <>
        <input className="search" placeholder="Filter table views by name ..." value={q} onChange={(e) => setQ(e.target.value)} />
        <ul className="llist">{rows.map((r) => <li key={r.path_id} onClick={() => load(r.path_id)}>{r.name}<small> {r.columns} columns</small></li>)}</ul>
      </>}
      {view && <>
        <div className="pad"><button onClick={() => setView(null)}>← views</button> <b>{view.name}</b></div>
        <div className="pad dim small">{view.factory ? `row cells from ${view.factory.name} (${view.factory.cells} cells, ${Math.round(view.factory.coverage * 100)}% of this view's columns defined there)` : 'no row cell factory found for these columns'}</div>
        <table className="tcols"><thead><tr><th>#</th><th>column</th><th>width</th><th>draws</th><th></th></tr></thead><tbody>
          {view.columns.map((c, i) => (
            <tr key={c.id} className={patched(c.id).length ? 'patched' : ''}>
              <td>{i + 1}</td>
              <td title={`priority ${c.priority}${c.required ? ' · required' : ''}${c.sorting_disabled ? ' · sorting disabled' : ''}${c.conditions ? ' · ' + c.conditions + ' condition(s)' : ''}`}><b>{c.id}</b>{c.required && <small className="dim"> required</small>}{patched(c.id).length > 0 && <span className="dot"> ●</span>}</td>
              <td>{project ? <input type="number" min={0} max={2000} defaultValue={c.width} key={c.id + c.width} onBlur={(e) => { const v = Number(e.target.value); if (v !== c.width && v >= 0) edit({ op: 'set-width', column: c.id, width: v }) }} /> : c.width}<small className="dim"> {c.cell ? `(default ${c.cell.default_width})` : ''}</small></td>
              <td className="small">{c.cell ? (c.cell.cell_layout || c.cell.cell_layout_guid.slice(0, 8)) : <span className="warnline">not in this factory</span>}</td>
              <td>{project && <>
                <button title="Move up" disabled={i === 0} onClick={() => edit({ op: 'move-column', column: c.id, ...(i > 1 ? { after: view.columns[i - 2].id } : {}) })}>↑</button>
                <button title="Move down" disabled={i === view.columns.length - 1} onClick={() => edit({ op: 'move-column', column: c.id, after: view.columns[i + 1].id })}>↓</button>
                <button title={c.required ? 'This column is required' : 'Hide this column'} disabled={c.required} onClick={() => edit({ op: 'hide-column', column: c.id })}>hide</button></>}</td>
            </tr>))}
        </tbody></table>
        {project && <div className="pad">
          <div className="dim small">Add a column the factory can draw ({view.available.length}):</div>
          <input className="search" placeholder="Filter available columns ..." value={add} onChange={(e) => setAdd(e.target.value)} />
          <div className="addlist">{addable.map((a) => <div key={a.id} className="small"><button onClick={() => edit({ op: 'show-column', column: a.id, after: view.columns[view.columns.length - 1]?.id })}>+ {a.id}</button> <span className="dim">{a.cell_layout || ''} {a.default_width}px</span></div>)}</div>
          {hasOps && <button onClick={revert}>Revert all edits of this view</button>}
        </div>}
      </>}
    </div>
  )
}
