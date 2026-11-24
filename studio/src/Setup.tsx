import { useState } from 'react'
import { rpc, RpcError, type EngineState } from './engine'
import { sayOf, sayOfJobError, type Said } from './plainError'

type Step = 'find' | 'read' | 'styles'
interface Line { step: Step; label: string; state: 'todo' | 'doing' | 'done' | 'failed'; took?: number; note?: string }

const secs = (ms: number) => (ms < 950 ? `${(ms / 1000).toFixed(2)} s` : `${(ms / 1000).toFixed(1)} s`)

/** First-run setup (S1a): find the game, read it once, build the style index. Each step says what it is doing in words and shows the time it really took. */
export default function Setup({ state, refresh, say, pickFolder }: { state: EngineState; refresh: () => Promise<void>; say: (s: string) => void; pickFolder?: () => Promise<string | undefined> }) {
  const [lines, setLines] = useState<Line[]>([])
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<Said | null>(null)
  const [choices, setChoices] = useState<{ game_dir: string; version?: string | null }[] | null>(null)

  const todo: Step[] = []
  if (!state.install) todo.push('find')
  if (!state.vanilla) todo.push('read')
  if (!state.indexed) todo.push('styles')

  const set = (step: Step, patch: Partial<Line>) => setLines((ls) => { const i = ls.findIndex((l) => l.step === step); const base: Line = i >= 0 ? ls[i] : { step, label: LABELS[step], state: 'todo' }; const next = { ...base, ...patch }; return i >= 0 ? ls.map((l, j) => (j === i ? next : l)) : [...ls, next] })

  async function timed<T>(step: Step, fn: () => Promise<T>): Promise<T> {
    set(step, { state: 'doing', note: undefined })
    const t0 = performance.now()
    try { const r = await fn(); set(step, { state: 'done', took: performance.now() - t0 }); return r } catch (e) { set(step, { state: 'failed' }); throw e }
  }

  async function findGame(): Promise<EngineState> {
    let s = await rpc<EngineState & { candidates?: { game_dir: string; version?: string | null }[] | null }>('game.detect')
    if (s.install) return s
    const found = s.candidates ?? []
    if (found.length > 1) { setChoices(found); throw new Choose() }
    const dir = pickFolder ? await pickFolder() : undefined
    if (!dir) throw new Error('no game folder chosen')
    s = await rpc<EngineState>('game.select', { game_dir: dir })
    return s
  }

  async function run(chosen?: string) {
    setBusy(true); setProblem(null); setChoices(null)
    try {
      let s = state
      if (!s.install) s = chosen ? await timed('find', () => rpc<EngineState>('game.select', { game_dir: chosen })) : await timed('find', findGame)
      if (!s.vanilla) {
        set('read', { note: 'Reading the game\'s style files and layouts (the game must be closed)' })
        s = await timed('read', async () => {
          const st = await rpc<EngineState>('snapshot.take', {})
          const { job } = await rpc<{ job: string }>('layout.scan')
          const done = await rpc<{ state: string; error: string | null }>('jobs.wait', { id: job, timeout: 600 })
          if (done.state !== 'done') throw new Error(done.error || 'the game\'s layout files could not be read')
          return st
        })
      }
      if (!s.indexed) {
        set('styles', { note: 'Reading the game\'s colours and rules' })
        await timed('styles', async () => {
          const { job } = await rpc<{ job: string }>('index.build')
          const done = await rpc<{ state: string; error: string | null }>('jobs.wait', { id: job, timeout: 120 })
          if (done.state !== 'done') throw new Error(done.error || 'the style index could not be built')
        })
      }
      say('first-run setup done')
      await refresh()
    } catch (e) {
      if (e instanceof Choose) return
      const text = e instanceof Error ? e.message : String(e)
      let said: Said
      if (e instanceof RpcError) said = sayOf(e)                                                    // the engine's own sentence
      else if (text === 'no game folder chosen') said = { plain: "No game folder was chosen. Pick the folder that contains the game's fm.exe.", details: text }
      else said = await sayOfJobError(text)                                                         // a failed job: its text through the engine's table
      setProblem(said)
      say('ERROR ' + text)
    } finally { setBusy(false) }
  }

  if (!todo.length) return <div className="setup"><h2>Ready</h2><p>The game has been read. You can start.</p></div>
  return (
    <div className="setup" data-testid="setup">
      <h2>Let&apos;s get set up</h2>
      <p>The Studio needs to read your copy of Football Manager once, so it knows what the game looks like. It only reads: your game is not changed.</p>
      <ol className="setup-steps">
        {(['find', 'read', 'styles'] as Step[]).map((s) => {
          const l = lines.find((x) => x.step === s)
          const needed = todo.includes(s)
          const st = l?.state ?? (needed ? 'todo' : 'done')
          return <li key={s} className={'setup-' + st}>
            <b>{LABELS[s]}</b>{' '}
            {st === 'done' && <span className="ok">done{l?.took !== undefined ? ` in ${secs(l.took)}` : ''}</span>}
            {st === 'doing' && <span className="dim">{l?.note || 'working ...'}</span>}
            {st === 'failed' && <span className="bad">did not finish</span>}
          </li>
        })}
      </ol>
      {choices && <div className="setup-choose"><p>More than one copy of the game was found. Which one?</p>{choices.map((c) => <button key={c.game_dir} onClick={() => run(c.game_dir)}>{c.game_dir}{c.version ? ` (${c.version})` : ''}</button>)}</div>}
      {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}
      <button className="primary" disabled={busy} onClick={() => run()}>{busy ? 'Working ...' : todo[0] === 'find' ? 'Find my game and read it' : 'Read the game'}</button>
    </div>
  )
}

class Choose extends Error {}
const LABELS: Record<Step, string> = { find: 'Find the game', read: 'Read the game files', styles: 'Read the game\'s colours and rules' }
