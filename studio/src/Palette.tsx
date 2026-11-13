import { useCallback, useEffect, useState } from 'react'
import { rpc, RpcError } from './engine'

interface Col { rgb: string; a: number }
interface Override { token: string; value: Col | string; vanilla?: string }
const isCol = (v: unknown): v is Col => !!v && typeof v === 'object' && 'rgb' in (v as object)
const css = (c: Col) => `rgba(${parseInt(c.rgb.slice(1, 3), 16)},${parseInt(c.rgb.slice(3, 5), 16)},${parseInt(c.rgb.slice(5, 7), 16)},${c.a})`

/** Simple mode: the project's token overrides as colour swatches. Every edit goes through the engine's project model, which rewrites styles/tokens.uss. */
export default function Palette({ project, onChanged, say }: { project: string; onChanged: () => void; say: (s: string) => void }) {
  const [model, setModel] = useState<any>(null)
  const [q, setQ] = useState('')
  const [found, setFound] = useState<any[]>([])
  const [err, setErr] = useState('')
  const load = useCallback(async () => { setModel(await rpc('project.get', { name: project })) }, [project])
  useEffect(() => { setErr(''); load().catch((e) => { setModel(null); setErr(String(e.message || e)) }) }, [load])
  useEffect(() => {
    if (q.trim().length < 2) { setFound([]); return }
    const t = setTimeout(() => rpc('tokens.list', { q: q.trim(), colours: true }).then((r) => setFound(r.rows.slice(0, 40))).catch(() => {}), 200)
    return () => clearTimeout(t)
  }, [q])

  const save = async (m: any) => {
    try { const r = await rpc<{ project: any }>('project.save', { project: m }); setModel(r.project); onChanged() }
    catch (e) { say('ERROR ' + (e instanceof RpcError ? e.message : String(e))) }
  }
  const set = (token: string, value: Col | string) => save({ ...model, token_overrides: model.token_overrides.map((o: Override) => (o.token === token ? { ...o, value } : o)) })
  const remove = (token: string) => save({ ...model, token_overrides: model.token_overrides.filter((o: Override) => o.token !== token) })
  const add = (row: any) => {
    if (model.token_overrides.some((o: Override) => o.token === row.name)) return
    save({ ...model, token_overrides: [...model.token_overrides, { token: row.name, value: row.resolved || row.value, vanilla: String(row.value) }] })
    setQ('')
  }
  if (err) return <div className="note bad">The palette needs a project that compiles. Fix the Problems first: {err}</div>
  if (!model) return <div className="note">Loading ...</div>
  const rows: Override[] = model.token_overrides
  return (
    <div className="palette">
      <div className="head">PALETTE ({rows.length})</div>
      <input className="search" placeholder="Add a token (name or #hex) ..." value={q} onChange={(e) => setQ(e.target.value)} />
      {found.length > 0 && <ul className="found">{found.map((r) => <li key={r.name} onClick={() => add(r)}><i style={{ background: r.resolved ? css(r.resolved) : 'none' }} />{r.name}</li>)}</ul>}
      <ul className="tokens">
        {rows.map((o) => (
          <li key={o.token}>
            {isCol(o.value) ? (<>
              <input type="color" value={o.value.rgb.toLowerCase()} onChange={(e) => set(o.token, { ...(o.value as Col), rgb: e.target.value.toUpperCase() })} />
              <input className="alpha" type="number" min={0} max={1} step={0.01} value={Number((o.value as Col).a.toFixed(3))} onChange={(e) => { const a = parseFloat(e.target.value); if (a >= 0 && a <= 1) set(o.token, { ...(o.value as Col), a }) }} />
            </>) : <span className="var">{String(o.value)}</span>}
            <span className="name" title={o.vanilla ? `vanilla: ${o.vanilla}` : ''}>{o.token}</span>
            <button onClick={() => remove(o.token)} title="Remove override">×</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
