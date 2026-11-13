import { useCallback, useEffect, useMemo, useState } from 'react'
import { rpc, RpcError } from './engine'

interface Row { bundle: string; name: string; path_id: string; elements: number }
interface El {
  id: number; kind: 'element' | 'template'; type: string; name: string; classes: string[]; rule_index: number; attrs: Record<string, unknown>; attrs_set: string[]
  bindings: unknown[]; properties: { name: string; value: string }[]; inline?: [string, string][] | null; template?: string; children: El[]
  included?: { bundle: string; name: string; path_id: string; root: El }
}
interface Tree { bundle: string; path_id: string; name: string; root: El; patches?: { ops: any[] } | null }
interface Usage { class: string; layouts: { name: string; bundle: string; path_id: string; uses: number }[]; rules: { sheet: string; selector: string; props: Record<string, string> }[] }

const FORBIDDEN = /binding|datasource|template|valuevars|funcs|viewdatakey|uxmlassetid|^name$/i

/** Read the game's UXML layouts and edit them with small per-layout patches: add/remove classes, inline styles, attributes the game already uses.
 *  Elements are addressed by id with a type/name guard; nothing structural can be changed. Bundle target only. */
export default function Layouts({ project, target, onChanged, say }: { project: string | null; target: string; onChanged: () => void; say: (s: string) => void }) {
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [tree, setTree] = useState<Tree | null>(null)
  const [sel, setSel] = useState<number | null>(null)
  const [open, setOpen] = useState<Set<number>>(new Set())
  const [usage, setUsage] = useState<Usage | null>(null)
  const [err, setErr] = useState('')
  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) }, [say])

  useEffect(() => {
    const t = setTimeout(() => rpc<{ total: number; layouts: Row[] }>('layouts.list', { q, limit: 200 }).then((r) => { setRows(r.layouts); setTotal(r.total); setErr('') }).catch(fail), 200)
    return () => clearTimeout(t)
  }, [q, fail])

  const load = useCallback(async (b: string, id: string) => {
    try { const t = await rpc<Tree>('layouts.tree', { bundle: b, path_id: id, ...(project ? { project } : {}) }); setTree(t); setErr(''); return t } catch (e) { fail(e) }
  }, [project, fail])
  const choose = async (r: Row) => { setSel(null); setUsage(null); const t = await load(r.bundle, r.path_id); if (t) setOpen(new Set([t.root.id])) }

  const byId = useMemo(() => {
    const m = new Map<number, El>()
    const walk = (e: El) => { m.set(e.id, e); e.children.forEach(walk) }
    if (tree) walk(tree.root)
    return m
  }, [tree])
  const el = sel != null ? byId.get(sel) : undefined
  const patchOps = (id: number) => (tree?.patches?.ops ?? []).filter((o) => o.id === id)
  const guard = (e: El) => ({ type: e.type, name: e.name })

  const edit = async (e: El, op: Record<string, unknown>) => {
    if (!project || !tree) return
    try {
      await rpc('layouts.edit', { project, bundle: tree.bundle, name: tree.name, path_id: tree.path_id, op: { id: e.id, guard: guard(e), ...op } })
      await load(tree.bundle, tree.path_id); onChanged(); say(`layout edit stored: ${tree.name} / ${e.type}${e.name ? '#' + e.name : ''}`)
    } catch (x) { fail(x) }
  }
  const unedit = async (e: El) => {
    if (!project || !tree) return
    try { await rpc('layouts.unedit', { project, bundle: tree.bundle, name: tree.name, id: e.id }); await load(tree.bundle, tree.path_id); onChanged() } catch (x) { fail(x) }
  }
  const addClass = (e: El) => { const c = prompt('Class to add (a game class, or one your own rules define):')?.trim(); if (c) edit(e, { op: 'set-classes', add: [c] }) }
  const where = async (c: string) => { try { setUsage(await rpc<Usage>('layouts.class_usage', { class: c })) } catch (x) { fail(x) } }
  const setAttr = (e: El, name: string) => {
    const cur = e.attrs[name]
    const v = prompt(`New value for ${name} (now ${JSON.stringify(cur)}):`, typeof cur === 'string' ? cur : String(cur))
    if (v === null) return
    edit(e, { op: 'set-attr', name, value: typeof cur === 'number' ? Number(v) : typeof cur === 'boolean' ? v === 'true' : v })
  }
  const setInline = (e: El) => {
    const cur = (e.inline ?? []).map(([k, v]) => `${k}: ${v}`).join('; ')
    const txt = prompt('Inline style to set (property: value; property: value). Only the listed properties change:', cur)
    if (txt === null) return
    const props: Record<string, string> = {}
    for (const part of txt.split(';')) { const i = part.indexOf(':'); if (i > 0) props[part.slice(0, i).trim()] = part.slice(i + 1).trim() }
    if (Object.keys(props).length) edit(e, { op: 'set-inline', props })
  }

  const Node = ({ e, d, ro }: { e: El; d: number; ro?: boolean }) => {
    const isOpen = open.has(e.id)
    const patched = !ro && patchOps(e.id).length > 0
    return (
      <>
        <div className={'lnode' + (sel === e.id && !ro ? ' sel' : '') + (patched ? ' patched' : '')} style={{ paddingLeft: 8 + d * 12 }} onClick={() => { if (!ro) setSel(e.id) }}>
          <span className="caret" onClick={(ev) => { ev.stopPropagation(); setOpen((s) => { const n = new Set(s); if (n.has(e.id)) n.delete(e.id); else n.add(e.id); return n }) }}>{e.children.length || e.included ? (isOpen ? '▾' : '▸') : ' '}</span>
          <b>{e.type}</b>{e.name && <span className="nm">#{e.name}</span>}
          {e.classes.length > 0 && <small className="dim"> .{e.classes.slice(0, 3).join(' .')}{e.classes.length > 3 ? ' …' : ''}</small>}
          {patched && <span className="dot" title="Edited by this project">●</span>}
        </div>
        {isOpen && e.children.map((c) => <Node key={c.id} e={c} d={d + 1} ro={ro} />)}
        {isOpen && e.included && (
          <div className="inc" style={{ paddingLeft: 8 + (d + 1) * 12 }}>
            <small className="dim">includes <a onClick={() => load(e.included!.bundle, e.included!.path_id)}>{e.included.name}</a> (read-only here; open it to edit)</small>
            <Node e={e.included.root} d={d + 1} ro />
          </div>
        )}
      </>
    )
  }

  const attrs = el ? Object.entries(el.attrs).filter(([, v]) => v !== '' && v !== 0 && v !== false && !(typeof v === 'object')).slice(0, 30) : []
  return (
    <div className="layouts">
      <div className="head">UXML LAYOUTS ({total})</div>
      {target !== 'bundles' && project && <div className="warn pad">This project's target is <b>{target}</b>: layout edits only apply to the bundle target (the native build drops them and says so).</div>}
      {err && <div className="warn pad">{err}</div>}
      <input className="search" placeholder="Filter layouts by name ..." value={q} onChange={(e) => setQ(e.target.value)} />
      {!tree && <ul className="llist">{rows.map((r) => <li key={r.bundle + r.path_id} onClick={() => choose(r)} title={r.bundle}>{r.name}<small> {r.elements}</small></li>)}</ul>}
      {tree && <>
        <div className="pad"><button onClick={() => { setTree(null); setSel(null); setUsage(null) }}>← layouts</button> <b>{tree.name}</b> <small className="dim">{tree.bundle.replace('ui-visualtreeassets_assets_', '').replace('visualtreeassetpreload.bundle', '')}</small></div>
        <div className="ltree">{<Node e={tree.root} d={0} />}</div>
        {el && <div className="inspector">
          <div className="pad"><b>{el.type}</b>{el.name && <> #{el.name}</>} <small className="dim">id {el.id}{el.kind === 'template' ? ' · template ' + el.template : ''}</small></div>
          <div className="pad">
            <div className="dim small">classes</div>
            {el.classes.map((c) => <span key={c} className="chip">{c} <a title="Where is this class used?" onClick={() => where(c)}>?</a>{project && <a title="Remove this class" onClick={() => edit(el, { op: 'set-classes', remove: [c] })}> ×</a>}</span>)}
            {patchOps(el.id).filter((o) => o.op === 'set-classes').map((o) => (o.remove ?? []).map((c: string) => <span key={'r' + c} className="chip gone" title="removed by this project">{c}</span>))}
            {project && <button onClick={() => addClass(el)}>+ class</button>}
          </div>
          {el.inline && el.inline.length > 0 && <div className="pad"><div className="dim small">inline style</div>{el.inline.map(([k, v]) => <div key={k} className="mono small">{k}: {v}</div>)}</div>}
          {project && <div className="pad"><button onClick={() => setInline(el)}>edit inline style</button></div>}
          {attrs.length > 0 && <div className="pad"><div className="dim small">attributes (set in this layout)</div>{attrs.map(([k, v]) => <div key={k} className="mono small">{k} = {JSON.stringify(v)} {project && !FORBIDDEN.test(k) && <a onClick={() => setAttr(el, k)}>edit</a>}</div>)}</div>}
          {(el.bindings.length > 0 || el.properties.length > 0) && <div className="pad"><div className="dim small">bindings (read-only)</div>{el.properties.slice(0, 6).map((p, i) => <div key={i} className="mono small">{p.name}: {String(p.value).slice(0, 90)}</div>)}{el.bindings.length > 0 && <div className="mono small">{el.bindings.length} binding(s)</div>}</div>}
          {project && patchOps(el.id).length > 0 && <div className="pad"><button onClick={() => unedit(el)}>Revert this element's edits</button></div>}
        </div>}
        {usage && <div className="usage">
          <div className="pad"><b>.{usage.class}</b> <a onClick={() => setUsage(null)}>close</a></div>
          <div className="pad dim small">{usage.layouts.length}{usage.layouts.length >= 200 ? '+' : ''} layout(s), {usage.rules.length} style rule(s)</div>
          {usage.layouts.slice(0, 40).map((l) => <div key={l.path_id} className="mono small hit" onClick={() => load(l.bundle, l.path_id)}>{l.name} <span className="dim">×{l.uses}</span></div>)}
          {usage.rules.slice(0, 40).map((r, i) => <div key={i} className="mono small">[{r.sheet}] {r.selector.slice(0, 90)}</div>)}
        </div>}
      </>}
    </div>
  )
}
