import { useCallback, useEffect, useRef, useState } from 'react'
import { rpc } from './engine'
import { sayOf, sayOfJobError, type Said } from './plainError'
import { labsRemoval } from './labs'

interface Pre { project: string; skin: string; changes: Record<string, number>; has_changes: boolean; skins_folder: string | null; skins_folder_found: boolean; folder: string | null; first_time: boolean }
interface Done { project: string; skin: string; folder: string; first_time: boolean; steps_left: string[]; tokens: number; rules: number; images: number; fonts: number; skipped: string[]; problems: string[] }
interface JobView { state: string; label: string; progress: number; error: string | null; result: Done | null }

export const NOTHING_CHANGED = "You haven't changed anything yet, so there is nothing to put in the game. Open Colours and change something first."
export const REMOVAL_FIRST = "First switch to the default skin in the game's Preferences, then take this one out."

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))
const kinds = (c: Record<string, number>) => Object.entries(c).map(([k, v]) => (k === 'flat look' ? 'the flat top bar and headers' : `${v} ${k}`)).join(', ')

/** "Put it in the game" (S2): one button, the native route only (a skin folder in your skins folder; no game file is written). While it runs, the middle of the screen says which step it is on in words;
 *  afterwards it says what is left to do in the game with the skin's name filled in (only "Reload Skin" once the skin has been put there before). */
export default function PutInGame({ project, say, minShowMs = 900, pollMs = 120 }: { project: string; say: (s: string) => void; minShowMs?: number; pollMs?: number }) {
  const [pre, setPre] = useState<Pre | null>(null)
  const [busy, setBusy] = useState<{ label: string; progress: number } | null>(null)
  const [done, setDone] = useState<Done | null>(null)
  const [problem, setProblem] = useState<Said | null>(null)
  const [removed, setRemoved] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  const look = useCallback(async () => { try { const p = await rpc<Pre>('native.preflight', { project }); if (alive.current) setPre(p) } catch (e) { if (alive.current) setProblem(sayOf(e)) } }, [project])
  useEffect(() => { setDone(null); setProblem(null); setRemoved(''); look() }, [look])

  async function put() {
    setProblem(null); setDone(null); setRemoved('')
    const t0 = Date.now()
    setBusy({ label: 'Starting', progress: 0 })
    try {
      const { job } = await rpc<{ job: string }>('native.put', { project })
      let v: JobView
      for (;;) {
        v = await rpc<JobView>('jobs.get', { id: job })
        if (!alive.current) return
        setBusy({ label: v.label || 'Working', progress: v.progress })
        if (v.state === 'done' || v.state === 'failed' || v.state === 'cancelled') break
        await wait(pollMs)
      }
      const left = minShowMs - (Date.now() - t0)                                  // a quick job still shows its steps long enough to be read
      if (left > 0) await wait(left)
      if (!alive.current) return
      if (v.state === 'done' && v.result) { setDone(v.result); say(`put ${v.result.skin} in the game: ${v.result.folder}`) }
      else { const s = await sayOfJobError(v.error || 'the job did not finish'); if (alive.current) { setProblem(s); say('ERROR ' + s.details) } }
    } catch (e) { if (alive.current) { setProblem(sayOf(e)); say('ERROR ' + sayOf(e).details) } }
    finally { if (alive.current) { setBusy(null); look() } }
  }

  async function takeOut() {
    if (!pre?.folder || !confirm(`Take the skin "${pre.skin}" out of your skins folder?\n\n${REMOVAL_FIRST}\n\nFolder: ${pre.folder}`)) return
    try { const r = await rpc<{ removed: string }>('native.remove', { project, confirm: true }); setRemoved(r.removed); setDone(null); say('removed ' + r.removed); look() } catch (e) { setProblem(sayOf(e)) }
  }

  const empty = pre && !pre.has_changes
  return (
    <div className="put" data-testid="put">
      <h2>Put it in the game</h2>
      {!pre && !problem && <p className="dim">Looking at your skin ...</p>}
      {pre && <p>Your skin <b>{pre.skin}</b> {pre.has_changes ? <>carries {kinds(pre.changes)}.</> : <>has no changes yet.</>}</p>}
      {empty && <div className="warn" data-testid="put-guard">{NOTHING_CHANGED}</div>}
      {pre && !pre.skins_folder_found && <div className="warn">The Studio can&apos;t find your Football Manager 27 documents folder. Start the game once so it creates it.</div>}
      <p className="dim small">This writes your skin as a folder in your skins folder{pre?.skins_folder ? ` (${pre.skins_folder})` : ''}. It does not change any game file, and the game can stay open.</p>
      <button className="primary" disabled={!pre || !pre.has_changes || !pre.skins_folder_found || !!busy} onClick={put}>Put it in the game</button>

      {busy && <div className="busy-overlay" role="status" aria-live="polite" data-testid="put-progress">
        <div className="busy-card"><div className="busy-step">{busy.label} ...</div><progress max={1} value={busy.progress} aria-label="Progress" /></div>
      </div>}

      {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}

      {done && <div className="put-done" data-testid="put-done">
        <h3>Your skin is in your skins folder</h3>
        <p>What is left to do in the game{done.first_time ? '' : ' (this skin has been put there before, so it is already chosen)'}:</p>
        <ol>{done.steps_left.map((s) => <li key={s}>{s}</li>)}</ol>
        {done.problems.length > 0 && <div className="warn">The skin was written, but {done.problems.length} check(s) did not pass: {done.problems.join('; ')}</div>}
        <details><summary>details</summary>
          <div className="mono small">{done.folder}: {done.tokens} colours, {done.rules} rules, {done.images} pictures{done.fonts ? `, ${done.fonts} fonts` : ''}</div>
          {done.skipped.length > 0 && <div className="small dim">Not included in this way: {done.skipped.join('; ')}</div>}
        </details>
      </div>}

      {labsRemoval() && pre && !pre.first_time && <div className="put-remove" data-testid="put-remove">
        <h3>Take it out of the game</h3>
        <p className="dim small">{REMOVAL_FIRST}</p>
        <button onClick={takeOut}>Take it out of the game</button>
      </div>}
      {removed && <p data-testid="put-removed">Removed: {removed}</p>}
    </div>
  )
}
