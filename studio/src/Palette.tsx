import { useCallback, useEffect, useMemo, useState } from 'react'
import { rpc } from './engine'
import { sayOf } from './plainError'
import { grouped, hexOf, shortName, type BrowseRow } from './colourGroups'

interface Col { rgb: string; a: number }
interface Override { token: string; value: Col | string; vanilla?: string }
const isCol = (v: unknown): v is Col => !!v && typeof v === 'object' && 'rgb' in (v as object)
const css = (c: Col) => `rgba(${parseInt(c.rgb.slice(1, 3), 16)},${parseInt(c.rgb.slice(3, 5), 16)},${parseInt(c.rgb.slice(5, 7), 16)},${c.a})`
const BAR_DEFAULT: Col = { rgb: '#171717', a: 1 }

/** The project's colours (Simple mode's Colours view). Three parts: the top bar and headers (one flat colour instead of each club's, an option of the project), what the game uses
 *  (every colour its rules use, grouped; click a swatch to change it, "put back" to undo), and the list of the changes made. Every edit goes through the engine's project model,
 *  which rewrites styles/tokens.uss. */
export default function Palette({ project, onChanged, say }: { project: string; onChanged: () => void; say: (s: string) => void }) {
  const [model, setModel] = useState<any>(null)
  const [q, setQ] = useState('')
  const [found, setFound] = useState<any[]>([])
  const [err, setErr] = useState('')
  const [all, setAll] = useState<BrowseRow[] | null>(null)
  const [filter, setFilter] = useState('')
  const [open, setOpen] = useState<Set<string>>(new Set())
  const load = useCallback(async () => { setModel(await rpc('project.get', { name: project })) }, [project])
  useEffect(() => { setErr(''); load().catch((e) => { setModel(null); setErr(String(e.message || e)) }) }, [load])
  useEffect(() => { rpc<{ rows: BrowseRow[] }>('tokens.browse').then((r) => setAll(r.rows)).catch((e) => say('ERROR ' + sayOf(e).details)) }, [say])
  useEffect(() => {
    if (q.trim().length < 2) { setFound([]); return }
    const t = setTimeout(() => rpc('tokens.list', { q: q.trim(), colours: true }).then((r) => setFound(r.rows.slice(0, 40))).catch(() => {}), 200)
    return () => clearTimeout(t)
  }, [q])

  const save = async (m: any) => {
    try { const r = await rpc<{ project: any }>('project.save', { project: m }); setModel(r.project); onChanged() }
    catch (e) { say('ERROR ' + sayOf(e).details) }
  }
  const set = (token: string, value: Col | string) => save({ ...model, token_overrides: model.token_overrides.map((o: Override) => (o.token === token ? { ...o, value } : o)) })
  const remove = (token: string) => save({ ...model, token_overrides: model.token_overrides.filter((o: Override) => o.token !== token) })
  const add = (row: any) => {
    if (model.token_overrides.some((o: Override) => o.token === row.name)) return
    save({ ...model, token_overrides: [...model.token_overrides, { token: row.name, value: row.resolved || row.value, vanilla: String(row.value) }] })
    setQ('')
  }
  const rows: Override[] = model?.token_overrides ?? []
  const byToken = useMemo(() => new Map(rows.map((o) => [o.token, o])), [rows])
  const groups = useMemo(() => {
    const f = filter.trim().toLowerCase().replace(/^#/, '')
    const list = !all ? [] : !f ? all : all.filter((r) => r.name.toLowerCase().includes(f) || r.rgb.toLowerCase().includes('#' + f) || r.rgb.toLowerCase().slice(1).startsWith(f))
    return grouped(list)
  }, [all, filter])

  // a click on a swatch: change an existing override's colour, or start one from the game's own value
  const pick = (row: BrowseRow, rgb: string) => {
    const o = byToken.get(row.name)
    if (o && isCol(o.value)) return set(row.name, { ...o.value, rgb: rgb.toUpperCase() })
    return save({ ...model, token_overrides: [...rows, { token: row.name, value: { rgb: rgb.toUpperCase(), a: row.a }, vanilla: hexOf(row.rgb, row.a) }] })
  }

  // the top bar and the club headers: the game paints them in code from the club's colours, so there is no token to change; the project option is one flat colour for all of them
  const flat = model?.options?.club_colours === false
  const bar: Col = model?.options?.club_colours_replacement ?? BAR_DEFAULT
  const setBar = (patch: { club_colours?: boolean; club_colours_replacement?: Col }) => save({ ...model, options: { ...(model.options || {}), ...patch } })

  if (err) return <div className="note bad">The palette needs a project that compiles. Fix the Problems first: {err}</div>
  if (!model) return <div className="note">Loading ...</div>
  return (
    <div className="palette">
      <section className="pal-bar" data-testid="topbar-section">
        <div className="head">TOP BAR AND HEADERS</div>
        <label><input type="checkbox" checked={flat} onChange={(e) => setBar({ club_colours: !e.target.checked })} /> One flat colour instead of each club&apos;s colours</label>
        {flat && <label className="pal-barcol"><input type="color" aria-label="Top bar colour" value={bar.rgb.toLowerCase()} onChange={(e) => setBar({ club_colours_replacement: { rgb: e.target.value.toUpperCase(), a: 1 } })} /> {bar.rgb.toUpperCase()}</label>}
        <div className="dim small">The game paints the top bar and the club headers from the club&apos;s colours, in code, so there is no single colour to change: this is the way to set them, for every club at once. Not yet checked in the game in this form.</div>
      </section>

      <div className="head">WHAT THE GAME USES {all ? `(${all.length})` : ''}</div>
      <input className="search" placeholder="Find a colour: a word from its name, or a code like #1A1A1A" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Find a colour" />
      {!all && <div className="note">Loading the game&apos;s colours ...</div>}
      <div className="pal-groups">
        {groups.map((g) => {
          const isOpen = open.has(g.label) || filter.trim().length > 0
          const changed = g.rows.filter((r) => byToken.has(r.name)).length
          return <div key={g.label} className="pal-group">
            <button className="pal-ghead" aria-expanded={isOpen} onClick={() => setOpen((s) => { const n = new Set(s); if (n.has(g.label)) n.delete(g.label); else n.add(g.label); return n })}>
              {isOpen ? '▾' : '▸'} {g.label} <small>{g.rows.length}{changed ? ` · ${changed} changed` : ''}</small>
            </button>
            {isOpen && <ul className="tokens">{g.rows.map((r) => {
              const o = byToken.get(r.name)
              const cur = o && isCol(o.value) ? o.value : { rgb: r.rgb, a: r.a }
              return <li key={r.name} className={o ? 'changed' : ''}>
                <input type="color" aria-label={`Colour of ${shortName(r.name)}`} value={cur.rgb.toLowerCase()} onChange={(e) => pick(r, e.target.value)} />
                <span className="name" title={`${r.name} · game's colour ${hexOf(r.rgb, r.a)} · used in ${r.reach} place(s)`}>{shortName(r.name)}</span>
                <small className="dim">used in {r.reach}</small>
                {o && <button onClick={() => remove(r.name)} title="Back to the game's colour">put back</button>}
              </li>
            })}</ul>}
          </div>
        })}
        {all && !groups.length && <div className="note">No colour matches that.</div>}
      </div>

      <div className="head">YOUR CHANGES ({rows.length})</div>
      <input className="search" placeholder="Add a token by name or #hex (advanced) ..." value={q} onChange={(e) => setQ(e.target.value)} />
      {found.length > 0 && <ul className="found">{found.map((r) => <li key={r.name} onClick={() => add(r)}><i style={{ background: r.resolved ? css(r.resolved) : 'none' }} />{r.name}</li>)}</ul>}
      {!rows.length && <div className="dim small" style={{ padding: '4px 10px' }}>Nothing changed yet: the skin looks like the game. Open a group above and click a colour.</div>}
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
