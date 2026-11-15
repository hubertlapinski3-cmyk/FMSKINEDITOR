import { useEffect, useMemo, useState } from 'react'
import { rpc } from './engine'
import { sayOf, type Said } from './plainError'

type Verdict = 'works' | 'exceptions' | 'clash' | 'not-done'
interface Finding { id: string; kind: 'missing' | 'open' | 'decision' | 'works' | 'info'; title: string; screens: string[]; themes: string[]; text: string; fix?: string }
export interface FindingsData {
  title: string; date: string; source: string; game: string
  themes: { id: string; name: string; inputs: string; skin: string }[]
  screens: { id: string; name: string }[]
  verdicts: Record<string, { v: Verdict; note: string }>
  findings: Finding[]
  shots: Record<string, string>
}

export const VERDICT_WORDS: Record<Verdict, string> = { works: 'works', exceptions: 'works, with exceptions', clash: 'clashes', 'not-done': 'not looked at' }
const KIND_WORDS: Record<Finding['kind'], string> = { missing: 'Not changed by the theme', open: 'Still open', decision: 'Decided', works: 'Works', info: 'Kept on purpose' }
const KIND_ORDER: Finding['kind'][] = ['missing', 'open', 'decision', 'works', 'info']

const cache = new Map<string, string>()
function useShot(name: string): string {
  const [src, setSrc] = useState(cache.get(name) ?? '')
  useEffect(() => {
    if (!name) { setSrc(''); return }
    if (cache.has(name)) { setSrc(cache.get(name)!); return }
    setSrc(''); let live = true
    rpc<{ content_type: string; base64: string }>('screens.image', { name }).then((r) => { const u = `data:${r.content_type};base64,${r.base64}`; cache.set(name, u); if (live) setSrc(u) }).catch(() => {})
    return () => { live = false }
  }, [name])
  return src
}
const Shot = ({ name, alt, onClick }: { name: string; alt: string; onClick?: () => void }) => {
  const src = useShot(name)
  return src ? <img className="fnd-shot" src={src} alt={alt} onClick={onClick} /> : <div className="fnd-shot empty">{name ? 'Loading ...' : 'No screenshot for this one'}</div>
}

/** What the Session 2 pass found in the game (Advanced mode). A grid of theme by screen, the screenshots, and the list of what the themes do not change, so what is missing can be seen with your own eyes.
 *  The screenshots live in the workspace's game-screens folder on this PC (they show real club and player names); this view is not in Simple mode. */
export default function Findings({ say }: { say: (s: string) => void }) {
  const [data, setData] = useState<FindingsData | null>(null)
  const [problem, setProblem] = useState<Said | null>(null)
  const [sel, setSel] = useState<{ theme: string; screen: string } | null>(null)
  const [kinds, setKinds] = useState<Finding['kind'][]>(['missing', 'open', 'decision'])

  useEffect(() => { rpc<FindingsData>('findings.get').then((d) => { setData(d); setSel({ theme: d.themes[0].id, screen: d.screens[0].id }) }).catch((e) => { setProblem(sayOf(e)); say('ERROR ' + sayOf(e).details) }) }, [say])

  const shown = useMemo(() => (data ? data.findings.filter((f) => kinds.includes(f.kind)) : []), [data, kinds])
  if (problem) return <div className="findings"><div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div></div>
  if (!data || !sel) return <div className="findings dim pad">Loading ...</div>

  const theme = data.themes.find((t) => t.id === sel.theme)!, screen = data.screens.find((s) => s.id === sel.screen)!
  const verdict = data.verdicts[`${sel.theme}/${sel.screen}`]
  const forScreen = data.findings.filter((f) => f.screens.includes(sel.screen) && (f.themes.length === 0 || f.themes.includes(sel.theme)))
  const have = Object.keys(data.shots).length
  const toggle = (k: Finding['kind']) => setKinds((l) => (l.includes(k) ? l.filter((x) => x !== k) : [...l, k]))
  const open = (f: Finding) => setSel({ theme: f.themes[0] && data.themes.some((t) => t.id === f.themes[0]) ? (f.themes.includes(sel.theme) ? sel.theme : f.themes[0]) : sel.theme, screen: f.screens[0] ?? sel.screen })

  return (
    <div className="findings" data-testid="findings">
      <h2>{data.title}</h2>
      <p className="dim small">{data.date} · {data.game}. {data.source}</p>
      <div className="warn small">These pictures show real club and player names. They stay on this PC (your workspace's game-screens folder) and are never put in a project or a skin. {have} of {data.themes.length * data.screens.length} are here.</div>

      <h3>Theme by screen</h3>
      <table className="fnd-grid" aria-label="Verdict per theme and screen">
        <thead><tr><th /> {data.themes.map((t) => <th key={t.id} title={t.inputs}>{t.name}</th>)}</tr></thead>
        <tbody>{data.screens.map((s) => <tr key={s.id}><th scope="row">{s.name}</th>
          {data.themes.map((t) => { const v = data.verdicts[`${t.id}/${s.id}`]; return <td key={t.id}>{v
            ? <button className={`fnd-cell v-${v.v}` + (sel.theme === t.id && sel.screen === s.id ? ' on' : '')} title={v.note} aria-label={`${t.name}, ${s.name}: ${VERDICT_WORDS[v.v]}`} data-testid={`cell-${t.id}-${s.id}`} onClick={() => setSel({ theme: t.id, screen: s.id })}>{VERDICT_WORDS[v.v]}</button>
            : <span className="dim">-</span>}</td> })}</tr>)}</tbody>
      </table>
      <div className="dim small">Green: nothing missing seen. Amber: works, with game-coloured parts the theme does not change. Red: clashes with the theme. Grey: not looked at.</div>

      <h3>{theme.name} on {screen.name}</h3>
      <div className="row"><span className="dim small">Compare:</span>{data.themes.map((t) => <button key={t.id} className={sel.theme === t.id ? 'on' : ''} onClick={() => setSel({ theme: t.id, screen: sel.screen })}>{t.name}</button>)}</div>
      {verdict && <p data-testid="verdict-note"><b className={`v-${verdict.v}-text`}>{VERDICT_WORDS[verdict.v]}</b>: {verdict.note}</p>}
      <Shot name={data.shots[`${sel.theme}/${sel.screen}`] ?? ''} alt={`${theme.name} on ${screen.name}`} />
      <div className="fnd-compare" data-testid="compare">{data.themes.map((t) => <figure key={t.id} className={sel.theme === t.id ? 'on' : ''}><Shot name={data.shots[`${t.id}/${sel.screen}`] ?? ''} alt={`${t.name} on ${screen.name} (small)`} onClick={() => setSel({ theme: t.id, screen: sel.screen })} /><figcaption>{t.name}</figcaption></figure>)}</div>
      {forScreen.length > 0 && <><h4>Findings about this screen</h4><ul>{forScreen.map((f) => <li key={f.id}><b>{f.title}</b> <small className="dim">({KIND_WORDS[f.kind]})</small><div className="small">{f.text}</div>{f.fix && <div className="small dim">What can be done: {f.fix}</div>}</li>)}</ul></>}

      <h3>Everything found</h3>
      <div className="row" role="group" aria-label="Kinds of finding">{KIND_ORDER.map((k) => <label key={k}><input type="checkbox" checked={kinds.includes(k)} onChange={() => toggle(k)} /> {KIND_WORDS[k]} ({data.findings.filter((f) => f.kind === k).length})</label>)}</div>
      <ul className="fnd-list" data-testid="fnd-list">{shown.map((f) => <li key={f.id} className={'k-' + f.kind}>
        <button className="linkish" onClick={() => open(f)} title="Show it on its screen"><b>{f.title}</b></button> <small className="dim">{KIND_WORDS[f.kind]}{f.themes.length ? ' · ' + f.themes.map((id) => data.themes.find((t) => t.id === id)?.name ?? id).join(', ') : ''}</small>
        <div className="small">{f.text}</div>{f.fix && <div className="small dim">What can be done: {f.fix}</div>}</li>)}</ul>
    </div>
  )
}
