import { useState } from 'react'
import { rpc } from './engine'
import { sayOf, type Said } from './plainError'

const NAME_OK = /^[A-Za-z0-9._-]+$/

export function suggestName(existing: string[], base = 'my-first-skin'): string {
  if (!existing.includes(base)) return base
  for (let i = 2; i < 1000; i++) if (!existing.includes(`${base}-${i}`)) return `${base}-${i}`
  return base + '-new'
}

/** What removing the club colours does in the native route (from the code, skin_editor/club_colours.py and native.py). Not "proven in the Crimson skin": that was the bundle build. */
export const CLUB_REMOVAL_TEXT = "The top bar's text and icons use the dark-bar colours, so light club colours stay readable; the club wallpaper (the picture and the 3D background) stops drawing; the club's card frames and the news headers are hidden and filled with one flat colour; the kit strip disappears. This has not been looked at in the game in this form yet."

type Pick = null | 'theme' | 'empty'

/** The start screen (S1): three ways to begin. */
export default function Start({ projects, onCreated, onImport, say }: { projects: string[]; onCreated: (name: string) => Promise<void>; onImport: () => void; say: (s: string) => void }) {
  const [pick, setPick] = useState<Pick>(null)
  const [name, setName] = useState(() => suggestName(projects))
  const [keep, setKeep] = useState(true)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<Said | null>(null)
  const nameOk = NAME_OK.test(name) && !projects.includes(name)

  async function make() {
    if (!pick || !nameOk) return
    setBusy(true); setProblem(null)
    try {
      await rpc('project.create_folder', { name, target: 'native', ...(pick === 'theme' ? { preset: 'crimson' } : {}), keep_club_colours: keep })
      say(`created ${name}`)
      await onCreated(name)
    } catch (e) { setProblem(sayOf(e)); say('ERROR ' + sayOf(e).details) } finally { setBusy(false) }
  }

  return (
    <div className="start" data-testid="start">
      <h2>Make a skin for Football Manager</h2>
      <p>Choose how to begin. You can change everything afterwards.</p>
      <div className="start-choices">
        <button onClick={() => { setPick('theme'); setProblem(null) }} className={pick === 'theme' ? 'on' : ''}><b>Start from a ready-made theme</b><span>A dark crimson look, complete. Not yet checked in the game in this form.</span></button>
        <button onClick={onImport}><b>Open a skin I downloaded</b><span>Pick the folder of a skin from the forums. It is only read; you get your own copy.</span></button>
        <button onClick={() => { setPick('empty'); setProblem(null) }} className={pick === 'empty' ? 'on' : ''}><b>Start from the game&apos;s look</b><span>Nothing changed yet; you choose the colours.</span></button>
      </div>
      {pick && <div className="start-form">
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
        <button className="primary" disabled={busy || !nameOk} onClick={make}>{busy ? 'Making it ...' : 'Make it'}</button>
      </div>}
    </div>
  )
}
