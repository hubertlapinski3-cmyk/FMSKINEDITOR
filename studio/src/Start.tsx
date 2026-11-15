import { useEffect, useRef, useState } from 'react'
import { rpc } from './engine'
import { sayOf, type Said } from './plainError'
import Strip from './MyColoursStrip'
import { loadMine } from './myColours'
import { shortToken } from './Recolour'

const NAME_OK = /^[A-Za-z0-9._-]+$/
const HEX6 = /^#[0-9A-F]{6}$/

export function suggestName(existing: string[], base = 'my-first-skin'): string {
  if (!existing.includes(base)) return base
  for (let i = 2; i < 1000; i++) if (!existing.includes(`${base}-${i}`)) return `${base}-${i}`
  return base + '-new'
}

/** What removing the club colours does in the native route (from the code, skin_editor/club_colours.py and native.py). Not "proven in the Crimson skin": that was the bundle build. */
export const CLUB_REMOVAL_TEXT = "The top bar's text and icons use the dark-bar colours, so light club colours stay readable; the club wallpaper (the picture and the 3D background) stops drawing; the club's card frames and the news headers are hidden and filled with one flat colour; the kit strip disappears. This has not been looked at in the game in this form yet."

/** Every generated theme says this until Session 2 has looked at it in the game (docs/SIMPLE-MODE-PLAN.md S4). */
export const UNCHECKED = 'not yet checked in the game'

export type Three = { background: string; accent: string; text: string; mode: 'dark' | 'light' }
export type GalleryTheme = Three & { name: string; status: string; ok: boolean; failures: number; checked: number }
export type Pair = { fg: string; bg: string; ratio: number }
export type Check = {
  inputs: Three; writes: number; keeps: number; status: string; ok: boolean; missing?: string[]
  contrast: { minimum: number; pairs: number; checked: number; failures: Pair[]; game_failures: Pair[]; unchecked: { fg: string; bg: string }[] }
  preview: Record<string, { rgb: string; a: number }>
}

/** One contrast pair in words: which text on which background, the ratio it reaches and the one it needs. */
export function pairText(p: Pair, minimum: number): string {
  return `${shortToken(p.fg)} on ${shortToken(p.bg)}: ${p.ratio.toFixed(2)} to 1, needs ${minimum} to 1`
}

type Pick = null | 'theme' | 'three' | 'empty'

function Swatches({ t }: { t: { background: string; accent: string; text: string } }) {
  return <span className="theme-sw" aria-hidden="true">{[t.background, t.accent, t.text].map((c, i) => <span key={i} className="sw" style={{ background: c }} />)}</span>
}

/** The three colour pickers, each with My colours beside it. Values are #RRGGBB; nothing is adjusted. */
function ThreeColours({ value, onChange }: { value: Three; onChange: (v: Three) => void }) {
  const mine = loadMine()
  const row = (key: 'background' | 'accent' | 'text', label: string) => (
    <div className="three-row" key={key}>
      <label>{label} <input type="color" aria-label={label} value={value[key].toLowerCase()} onChange={(e) => onChange({ ...value, [key]: e.target.value.toUpperCase() })} /></label>
      <span className="mono small">{value[key]}</span>
      <Strip mine={mine} label={`My colours for the ${label.toLowerCase()}`} onPick={(c) => onChange({ ...value, [key]: c.toUpperCase() })} />
    </div>
  )
  return (
    <div className="three" data-testid="three">
      {row('background', 'Background')}
      {row('accent', 'Accent')}
      {row('text', 'Text')}
      <fieldset className="start-mode">
        <legend>Dark or light</legend>
        <label><input type="radio" name="mode" checked={value.mode === 'dark'} onChange={() => onChange({ ...value, mode: 'dark' })} /> Dark</label>
        <label><input type="radio" name="mode" checked={value.mode === 'light'} onChange={() => onChange({ ...value, mode: 'light' })} /> Light</label>
      </fieldset>
    </div>
  )
}

/** The contrast result in words. Failures block; the game's own pairs and the pairs that cannot be checked are said, not hidden. */
function CheckView({ c }: { c: Check }) {
  const k = c.contrast
  return (
    <div className="theme-check" data-testid="theme-check">
      <div>This theme sets {c.writes} of the game&apos;s colours and leaves {c.keeps} at the game&apos;s own colour. It is {UNCHECKED}.</div>
      {c.missing && c.missing.length > 0 && <div className="notice" role="alert" data-testid="theme-missing">This version of the game no longer has {c.missing.length} of the colours a theme sets, so the theme can&apos;t be made. Read the game again; if it repeats, update FM Skin Studio.</div>}
      {k.failures.length === 0
        ? <div className="ok">Readable: all {k.checked - k.game_failures.length} text and background pairs it changes reach {k.minimum} to 1.</div>
        : <div className="notice" role="alert"><div>Some text would be hard to read, so this theme can&apos;t be made. Change one of the three colours. Nothing is adjusted for you.</div>
          <ul data-testid="theme-failures">{k.failures.map((p) => <li key={p.fg + p.bg}>{pairText(p, k.minimum)}</li>)}</ul></div>}
      {k.game_failures.length > 0 && <div className="dim small" data-testid="theme-game-failures">Already under {k.minimum} to 1 in the game itself, and not changed by this theme: {k.game_failures.map((p) => pairText(p, k.minimum)).join('; ')}.</div>}
      {k.unchecked.length > 0 && <div className="dim small" data-testid="theme-unchecked">{k.unchecked.length} of the {k.pairs} pairs can&apos;t be checked here, because one of their colours is a colour family the theme does not set.</div>}
    </div>
  )
}

/** The start screen (S1, S4): four ways to begin. */
export default function Start({ projects, onCreated, onImport, say }: { projects: string[]; onCreated: (name: string) => Promise<void>; onImport: () => void; say: (s: string) => void }) {
  const [pick, setPick] = useState<Pick>(null)
  const [name, setName] = useState(() => suggestName(projects))
  const [keep, setKeep] = useState(true)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<Said | null>(null)
  const [gallery, setGallery] = useState<{ themes: GalleryTheme[]; crimson: Three | null } | null>(null)
  const [galleryProblem, setGalleryProblem] = useState<Said | null>(null)
  const [chosen, setChosen] = useState<string>('crimson')
  const [picked, setThree] = useState<Three | null>(null)
  const [result, setResult] = useState<{ key: string; check: Check | null } | null>(null)
  const seq = useRef(0)
  const three = picked ?? gallery?.crimson ?? null              // the engine's Crimson colours until the person picks one: never a colour typed here
  const key = three ? JSON.stringify(three) : ''
  const checking = pick === 'three' && !!three && result?.key !== key
  const check = result?.key === key ? result.check : null
  const nameOk = NAME_OK.test(name) && !projects.includes(name)

  useEffect(() => {
    if ((pick !== 'theme' && pick !== 'three') || gallery) return
    let live = true
    rpc('theme.gallery').then((r: any) => {
      if (!live) return
      const crimson = r?.crimson && HEX6.test(r.crimson.background) ? { background: r.crimson.background, accent: r.crimson.accent, text: r.crimson.text, mode: 'dark' as const } : null
      setGallery({ themes: Array.isArray(r?.themes) ? r.themes : [], crimson })
    }).catch((e) => { if (live) setGalleryProblem(sayOf(e)) })
    return () => { live = false }
  }, [pick, gallery])

  useEffect(() => {
    if (pick !== 'three' || !key) return
    const my = ++seq.current
    const t = setTimeout(() => {
      rpc('theme.generate', JSON.parse(key)).then((r: any) => { if (my === seq.current) { setResult({ key, check: r as Check }); setProblem(null) } })
        .catch((e) => { if (my === seq.current) { setResult({ key, check: null }); setProblem(sayOf(e)) } })
    }, 250)
    return () => clearTimeout(t)
  }, [pick, key])

  const galleryTheme = pick === 'theme' && chosen !== 'crimson' ? gallery?.themes.find((t) => t.name === chosen) ?? null : null
  const threeReady = pick === 'three' && !!three && !checking && !!check && check.ok
  const canMake = !!pick && nameOk && !busy && (pick !== 'three' || threeReady) && (!galleryTheme || galleryTheme.ok)

  async function make() {
    if (!canMake) return
    setBusy(true); setProblem(null)
    try {
      if (pick === 'three' && three) await rpc('theme.create', { name, ...three, keep_club_colours: keep })
      else if (galleryTheme) await rpc('theme.create', { name, background: galleryTheme.background, accent: galleryTheme.accent, text: galleryTheme.text, mode: galleryTheme.mode, keep_club_colours: keep })
      else await rpc('project.create_folder', { name, target: 'native', ...(pick === 'theme' ? { preset: 'crimson' } : {}), keep_club_colours: keep })
      say(`created ${name}`)
      await onCreated(name)
    } catch (e) { setProblem(sayOf(e)); say('ERROR ' + sayOf(e).details) } finally { setBusy(false) }
  }

  const choose = (p: Pick) => { setPick(p); setProblem(null) }

  return (
    <div className="start" data-testid="start">
      <h2>Make a skin for Football Manager</h2>
      <p>Choose how to begin. You can change everything afterwards.</p>
      <div className="start-choices">
        <button onClick={() => choose('theme')} className={pick === 'theme' ? 'on' : ''}><b>Start from a ready-made theme</b><span>A dark crimson look, complete, or one of a few more. Not yet checked in the game in this form.</span></button>
        <button onClick={() => choose('three')} className={pick === 'three' ? 'on' : ''}><b>Make a theme from three colours</b><span>Pick a background, an accent and a text colour; the Studio checks that the text stays readable.</span></button>
        <button onClick={onImport}><b>Open a skin I downloaded</b><span>Pick the folder of a skin from the forums. It is only read; you get your own copy.</span></button>
        <button onClick={() => choose('empty')} className={pick === 'empty' ? 'on' : ''}><b>Start from the game&apos;s look</b><span>Nothing changed yet; you choose the colours.</span></button>
      </div>
      {pick && <div className="start-form">
        {pick === 'theme' && <fieldset className="start-gallery" data-testid="gallery">
          <legend>Which theme</legend>
          <label><input type="radio" name="theme" checked={chosen === 'crimson'} onChange={() => setChosen('crimson')} /> {gallery?.crimson && <Swatches t={gallery.crimson} />} Crimson <span className="dim small">the dark crimson look</span></label>
          {gallery?.themes.map((t) => (
            <label key={t.name}><input type="radio" name="theme" checked={chosen === t.name} onChange={() => setChosen(t.name)} disabled={!t.ok} /> <Swatches t={t} /> {t.name}{' '}
              <span className="dim small">{t.mode}, {UNCHECKED}{t.ok ? '' : `; fails the readability check on ${t.failures} pair(s) on this game build`}</span></label>
          ))}
          {galleryProblem && <div className="dim small" data-testid="gallery-problem">Only Crimson is listed: the other themes could not be checked just now.</div>}
        </fieldset>}
        {pick === 'three' && (three
          ? <><ThreeColours value={three} onChange={setThree} />
            {gallery?.crimson && <div className="dim small">Starts from the Crimson theme&apos;s own background, accent and text.</div>}
            {checking && <div className="dim small" data-testid="theme-checking">Checking the colours ...</div>}
            {!checking && check && <CheckView c={check} />}</>
          : galleryProblem
            ? <div className="notice" role="alert"><div>{galleryProblem.plain}</div><details><summary>details</summary><div className="mono small">{galleryProblem.details}</div></details></div>
            : <div className="dim small">Loading the starting colours ...</div>)}
        <label>Name of your skin <input value={name} onChange={(e) => setName(e.target.value.trim())} aria-label="Name of your skin" /></label>
        {!NAME_OK.test(name) && <div className="warn">Use only letters, digits, dots, dashes and underscores.</div>}
        {NAME_OK.test(name) && projects.includes(name) && <div className="warn">A skin with that name already exists. Choose another name.</div>}
        <fieldset className="start-club">
          <legend>The club&apos;s own colours</legend>
          <label><input type="radio" name="club" checked={keep} onChange={() => setKeep(true)} /> Keep each club&apos;s own colours, as the game paints them</label>
          <label><input type="radio" name="club" checked={!keep} onChange={() => setKeep(false)} /> Use one flat look for every club</label>
          {!keep && <div className="dim small" data-testid="club-removal-text">{CLUB_REMOVAL_TEXT}</div>}
        </fieldset>
        {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}
        <button className="primary" disabled={!canMake} onClick={make}>{busy ? 'Making it ...' : 'Make it'}</button>
      </div>}
    </div>
  )
}
