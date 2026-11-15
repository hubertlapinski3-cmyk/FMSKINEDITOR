import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { rpc } from './engine'
import { sayOf } from './plainError'
import { tokenPaths, labelOf, type Computed, type RNode } from './Render'
import Strip from './MyColoursStrip'
import { loadMine } from './myColours'

/* "Click it, recolour it" (S3): the colours of one clicked element (background, text, border), each with what it comes from and what a change would touch.
   A colour from a game token changes that token; one written directly into a game rule is offered as a literal swap only while it copies at most 50 rules (the count is shown
   first); a colour from the layout file, from the parent element, or painted while the game runs is said so, and not offered. "Put it back" returns the game's own colour. */

type Kind = 'token' | 'literal' | 'inline' | 'inherited' | 'unknown' | 'notcolour'
interface Entry { key: string; label: string; d: Computed; kind: Kind }
interface Col { rgb: string; a: number }
interface ScreenCount { screens: number; of: number }
interface LiteralInfo { uses: number; selectors: number; copied_rules: number; limit: number; offered: boolean; a_exact?: number }

const HEXC = /^#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?$/
export function parseColour(v: string): Col | null {
  const m = HEXC.exec(v.trim())
  return m ? { rgb: '#' + m[1].toUpperCase(), a: m[2] ? Math.round((parseInt(m[2], 16) / 255) * 1000) / 1000 : 1 } : null
}
export const shortToken = (t: string) => t.replace(/^--/, '')
export function screensText(c: ScreenCount): string {
  return c.screens > 0 ? `used on ${c.screens} of the ${c.of} measured screens we have models for`
    : `not used on the ${c.of} screens we have models for; it may still change screens we have not measured`
}

export function kindOf(d: Computed): Kind {
  if (!parseColour(d.value)) return 'notcolour'
  if (d.tokens && d.tokens.length) return 'token'
  if (d.source?.inline) return 'inline'
  if (d.source?.inherited) return 'inherited'
  if (d.source?.selector) return 'literal'
  return 'unknown'
}

/** The colour properties of an element worth offering, grouped: background, text, border (the four sides as one when they are the same colour from the same source). */
export function entriesOf(n: RNode): Entry[] {
  const out: Entry[] = []
  const c = n.computed
  if (c['background-color']) out.push({ key: 'background-color', label: 'Background', d: c['background-color'], kind: kindOf(c['background-color']) })
  if (c['color']) out.push({ key: 'color', label: 'Text', d: c['color'], kind: kindOf(c['color']) })
  const sides = ['top', 'right', 'bottom', 'left'].filter((s) => c[`border-${s}-color`])
  const groups = new Map<string, string[]>()
  for (const s of sides) { const d = c[`border-${s}-color`]; const k = d.value + '|' + (d.tokens?.[0] ?? d.source?.selector ?? ''); groups.set(k, [...(groups.get(k) ?? []), s]) }
  for (const [, ss] of groups) {
    const d = c[`border-${ss[0]}-color`]
    if (parseColour(d.value)?.a === 0) continue                                  // an invisible border is not worth a picker
    out.push({ key: 'border-' + ss.join('-'), label: ss.length === 4 ? 'Border' : `Border (${ss.join(', ')})`, d, kind: kindOf(d) })
  }
  return out
}

const screensCache = new Map<string, ScreenCount>()

export default function Recolour({ node, tree, project, say, onClose }: { node: RNode; tree: RNode[]; project: string; say: (s: string) => void; onClose: () => void }) {
  const [model, setModel] = useState<any>(null)
  const [mine] = useState<string[]>(() => loadMine())
  const [problem, setProblem] = useState('')
  const load = useCallback(async () => { try { setModel(await rpc('project.get', { name: project })) } catch (e) { setProblem(sayOf(e).plain) } }, [project])
  useEffect(() => { load() }, [load])
  const entries = useMemo(() => entriesOf(node), [node])

  const save = async (m: any) => {
    try { const r = await rpc<{ project: any }>('project.save', { project: m }); setModel(r.project); setProblem('') }
    catch (e) { setProblem(sayOf(e).plain); say('ERROR ' + sayOf(e).details) }
  }

  return (
    <aside className="recolour" data-testid="recolour" aria-label="Recolour">
      <div className="recolour-head"><b>You clicked</b> <code title={labelOf(node)}>{node.type}{node.name ? ' ' + node.name : ''}</code><button className="mini" aria-label="Close" onClick={onClose}>×</button></div>
      {problem && <div className="notice" role="alert">{problem}</div>}
      {!entries.length && <p className="dim small">This part has no colour of its own to change (it shows what is behind it). Click another part.</p>}
      {model && entries.map((e) => <EntryView key={e.key + e.d.value} e={e} tree={tree} model={model} mine={mine} save={save} say={say} />)}
      <p className="dim small">Changes go into your skin. "Put it back" returns the game's own colour.</p>
    </aside>
  )
}

function Swatch({ c }: { c: Col }) {
  return <span className="sw" style={{ background: `rgba(${parseInt(c.rgb.slice(1, 3), 16)},${parseInt(c.rgb.slice(3, 5), 16)},${parseInt(c.rgb.slice(5, 7), 16)},${c.a})` }} />
}

function EntryView({ e, tree, model, mine, save, say }: { e: Entry; tree: RNode[]; model: any; mine: string[]; save: (m: any) => Promise<void>; say: (s: string) => void }) {
  const cur = parseColour(e.d.value)
  const head = <div className="rc-title"><b>{e.label}</b> {cur && <Swatch c={cur} />} <code>{e.d.value.toUpperCase()}</code></div>
  if (e.kind === 'notcolour' || !cur) return <section className="rc">{head}<p className="small">This is not a plain colour (a gradient or a picture), so it can't be changed here.</p></section>
  if (e.kind === 'inline') return <section className="rc">{head}<p className="small">This colour is written into the game's layout file itself, so it can't be changed here.</p></section>
  if (e.kind === 'inherited') return <section className="rc">{head}<p className="small">This part takes its colour from the part around it: click that one.</p></section>
  if (e.kind === 'unknown') return <section className="rc">{head}<p className="small">The game paints this while running; it can't be changed here.</p></section>
  if (e.kind === 'token') return <TokenEntry e={e} cur={cur} head={head} tree={tree} model={model} mine={mine} save={save} say={say} />
  return <LiteralEntry e={e} cur={cur} head={head} model={model} mine={mine} save={save} say={say} />
}

function TokenEntry({ e, cur, head, tree, model, mine, save }: { e: Entry; cur: Col; head: ReactNode; tree: RNode[]; model: any; mine: string[]; save: (m: any) => Promise<void>; say: (s: string) => void }) {
  const token = e.d.tokens![0]
  const [count, setCount] = useState<ScreenCount | null>(screensCache.get(token) ?? null)
  useEffect(() => {
    if (screensCache.has(token)) return
    rpc<ScreenCount>('simple.token_screens', { token }).then((r) => { screensCache.set(token, r); setCount(r) }).catch(() => setCount(null))
  }, [token])
  const others = Math.max(0, tokenPaths(tree, token).length - 1)
  const overrides: any[] = model.token_overrides ?? []
  const mineO = overrides.find((o) => o.token === token)
  const set = (rgb: string) => {
    const value = { rgb: rgb.toUpperCase(), a: cur.a }
    save({ ...model, token_overrides: mineO ? overrides.map((o) => (o.token === token ? { ...o, value } : o)) : [...overrides, { token, value, vanilla: e.d.value.toUpperCase() }] })
  }
  return (
    <section className="rc" data-kind="token">
      {head}
      <p className="small">From the game's colour <code>{shortToken(token)}</code>. Changing it also changes {others} other part{others === 1 ? '' : 's'} of this picture, and it is {count ? screensText(count) : '...'}.</p>
      <div className="rc-pick"><input type="color" aria-label={`New ${e.label.toLowerCase()} colour`} value={cur.rgb.toLowerCase()} onChange={(ev) => set(ev.target.value)} />
        <Strip mine={mine} label={`My colours for the ${e.label.toLowerCase()}`} onPick={set} />
        {mineO && <button onClick={() => save({ ...model, token_overrides: overrides.filter((o) => o.token !== token) })}>Put it back</button>}</div>
    </section>
  )
}

function LiteralEntry({ e, cur, head, model, mine, save, say }: { e: Entry; cur: Col; head: ReactNode; model: any; mine: string[]; save: (m: any) => Promise<void>; say: (s: string) => void }) {
  const swaps: any[] = model.literal_swaps ?? []
  const same = (x: Col, y: Col) => x.rgb.toUpperCase() === y.rgb.toUpperCase() && Math.abs(x.a - y.a) < 0.004
  const applied = swaps.find((s) => s.to && same(s.to, cur))                // this colour is one I already swapped in: offer to change or put back
  const [info, setInfo] = useState<LiteralInfo | null>(null)
  useEffect(() => { if (!applied) rpc<LiteralInfo>('simple.literal_info', { rgb: cur.rgb, a: cur.a }).then(setInfo).catch((err) => say('ERROR ' + sayOf(err).details)) }, [applied, cur.rgb, cur.a, say])
  if (applied) {
    const change = (rgb: string) => save({ ...model, literal_swaps: swaps.map((s) => (s === applied ? { ...s, to: { rgb: rgb.toUpperCase(), a: cur.a } } : s)) })
    return (
      <section className="rc" data-kind="literal">
        {head}
        <p className="small">You changed this colour from <code>{applied.from.rgb}</code> everywhere the game uses it.</p>
        <div className="rc-pick"><input type="color" aria-label={`New ${e.label.toLowerCase()} colour`} value={cur.rgb.toLowerCase()} onChange={(ev) => change(ev.target.value)} />
          <Strip mine={mine} label={`My colours for the ${e.label.toLowerCase()}`} onPick={change} />
          <button onClick={() => save({ ...model, literal_swaps: swaps.filter((s) => s !== applied) })}>Put it back</button></div>
      </section>
    )
  }
  if (!info) return <section className="rc">{head}<p className="small dim">Counting where the game uses this colour ...</p></section>
  if (!info.offered) {
    return (
      <section className="rc" data-kind="literal">
        {head}
        {info.copied_rules > info.limit
          ? <p className="small" data-testid="literal-advanced">This colour is used in many places ({info.copied_rules} game rules); changing it here is an Advanced job.</p>
          : <p className="small">This colour can't be changed from here.</p>}
      </section>
    )
  }
  const from = { rgb: cur.rgb, a: info.a_exact ?? cur.a }          // the exact alpha the game's rules carry: the native export copies only those rules
  const swap = (rgb: string) => save({ ...model, literal_swaps: [...swaps.filter((s) => !(s.from && same(s.from, cur))), { from, to: { rgb: rgb.toUpperCase(), a: cur.a }, mode: 'rgba' }] })
  return (
    <section className="rc" data-kind="literal">
      {head}
      <p className="small" data-testid="literal-cost">This colour is written directly into the game's rules. Changing it copies <b>{info.copied_rules} game rule{info.copied_rules === 1 ? '' : 's'}</b> into your skin ({info.selectors} selector{info.selectors === 1 ? '' : 's'}), everywhere the game uses exactly this colour.</p>
      <div className="rc-pick"><input type="color" aria-label={`New ${e.label.toLowerCase()} colour`} value={cur.rgb.toLowerCase()} onChange={(ev) => swap(ev.target.value)} />
        <Strip mine={mine} label={`My colours for the ${e.label.toLowerCase()}`} onPick={swap} /></div>
    </section>
  )
}
