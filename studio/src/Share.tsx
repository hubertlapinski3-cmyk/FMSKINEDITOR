import { useState } from 'react'
import { rpc } from './engine'
import { sayOf, type Said } from './plainError'
import { suggestName } from './Start'

const inTauri = () => '__TAURI_INTERNALS__' in window
const NAME_OK = /^[A-Za-z0-9._-]+$/

export interface Inspected {
  skin: string; folder: string; sheets: number; pictures: number; fonts: number; files: number; build_note: string | null
  manifest: { format?: string; studio_version?: string; game_build?: string | null; made_utc?: string } | null
  refused: { file: string; why: string }[]
}

/** What Start over takes away, in words a person can check (the engine counts by kind: native.changes). */
export function lostText(lost: Record<string, number>): string[] {
  const words: Record<string, (n: number) => string> = {
    colours: (n) => `${n} colour change${n === 1 ? '' : 's'}`,
    'colour swaps': (n) => `${n} colour${n === 1 ? '' : 's'} swapped in the game's rules`,
    rules: (n) => `${n} rule${n === 1 ? '' : 's'} written in Advanced mode`,
    pictures: (n) => `${n} picture${n === 1 ? '' : 's'}`,
    fonts: (n) => `${n} font${n === 1 ? '' : 's'}`,
    'imported sheets': (n) => `${n} style sheet${n === 1 ? '' : 's'} of a skin you opened`,
    'imported files': (n) => `${n} file${n === 1 ? '' : 's'} of a skin you opened`,
    'flat look': () => 'the flat look for every club (club colours removed)',
  }
  return Object.entries(lost).map(([k, n]) => (words[k] ? words[k](n) : `${n} ${k}`))
}

async function studioVersion(): Promise<string> {
  if (!inTauri()) return 'development'
  try { const m = await import('@tauri-apps/api/app'); return await m.getVersion() } catch { return 'unknown' }
}
async function pickSave(name: string): Promise<string | undefined> {
  if (!inTauri()) return prompt('Where to save the skin file (a path ending in .zip):', name + '.zip')?.trim() || undefined
  const { save } = await import('@tauri-apps/plugin-dialog')
  const r = await save({ title: 'Save my skin as a file', defaultPath: name + '.zip', filters: [{ name: 'Skin file', extensions: ['zip'] }] })
  return r || undefined
}
async function pickOpen(): Promise<string | undefined> {
  if (!inTauri()) return prompt('Path of the skin file (.zip):')?.trim() || undefined
  const { open } = await import('@tauri-apps/plugin-dialog')
  const r = await open({ multiple: false, directory: false, title: 'Open a skin file (it is only read)', filters: [{ name: 'Skin file', extensions: ['zip'] }] })
  return typeof r === 'string' ? r : undefined
}

/** Share and undo (S7, Simple mode): save the skin as one file, open a downloaded skin file as a copy (checked and shown first), and Start over (what is lost is said first). */
export default function Share({ project, projects, say, onOpened, onChanged }: { project: string | null; projects: string[]; say: (s: string) => void; onOpened: (name: string) => Promise<void>; onChanged: () => void }) {
  const [problem, setProblem] = useState<Said | null>(null)
  const [saved, setSaved] = useState<{ file: string; files: number; bytes: number } | null>(null)
  const [busy, setBusy] = useState('')
  const [opened, setOpened] = useState<{ path: string; info: Inspected } | null>(null)
  const [name, setName] = useState('')
  const [lost, setLost] = useState<{ lost: Record<string, number>; trash: string } | null>(null)
  const [done, setDone] = useState('')
  const fail = (e: unknown) => { setProblem(sayOf(e)); say('ERROR ' + sayOf(e).details) }

  async function saveFile() {
    if (!project) return
    setProblem(null); setSaved(null)
    try {
      const path = await pickSave(project); if (!path) return
      setBusy('save')
      const r = await rpc<{ file: string; files: number; bytes: number }>('share.save', { project, path, studio_version: await studioVersion(), overwrite: inTauri() })   // the desktop save dialog has already asked about replacing
      setSaved(r); say(`skin saved as ${r.file}`)
    } catch (e) { fail(e) } finally { setBusy('') }
  }
  async function openFile() {
    setProblem(null); setOpened(null)
    try {
      const path = await pickOpen(); if (!path) return
      setBusy('inspect')
      const info = await rpc<Inspected>('share.inspect', { path })
      setOpened({ path, info }); setName(suggestName(projects, (info.skin || 'downloaded-skin').replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'downloaded-skin'))
    } catch (e) { fail(e) } finally { setBusy('') }
  }
  const nameOk = NAME_OK.test(name) && !projects.includes(name)
  async function makeCopy() {
    if (!opened || !nameOk) return
    setProblem(null); setBusy('open')
    try { await rpc('share.open', { path: opened.path, name }); say(`opened ${opened.info.skin} as ${name}`); setOpened(null); await onOpened(name) } catch (e) { fail(e) } finally { setBusy('') }
  }
  async function askStartOver() {
    if (!project) return
    setProblem(null); setDone('')
    try { setLost(await rpc<{ lost: Record<string, number>; trash: string }>('project.start_over_preview', { project })) } catch (e) { fail(e) }
  }
  async function startOver() {
    if (!project) return
    setBusy('over')
    try { const r = await rpc<{ trash: string }>('project.start_over', { project, confirm: true }); setLost(null); setDone(r.trash); onChanged(); say(`started over: ${project} (the previous state is in ${r.trash})`) } catch (e) { fail(e) } finally { setBusy('') }
  }

  const v = opened?.info.manifest
  return (
    <div className="share" data-testid="share">
      <h2>Share and undo</h2>
      {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}

      <section>
        <h3>Save my skin as a file</h3>
        {!project ? <div className="dim small">Open a skin first (Projects).</div> : <>
          <p className="dim small">One .zip file you can send to a friend or keep as a copy. It holds the skin as "Put it in the game" writes it, and the versions it was made with.</p>
          <button className="primary" disabled={!!busy} onClick={saveFile}>{busy === 'save' ? 'Saving ...' : 'Save my skin as a file'}</button>
          {saved && <div className="ok small" data-testid="saved">Saved: {saved.file} ({saved.files} files, {Math.max(1, Math.round(saved.bytes / 1024))} KB).</div>}
        </>}
      </section>

      <section>
        <h3>Open a skin file</h3>
        <p className="dim small">A skin file (.zip) you downloaded. It is only read: you see what is inside first, then get your own copy as a new skin. Nothing goes into the game until you put it there.</p>
        <button disabled={!!busy} onClick={openFile}>{busy === 'inspect' ? 'Reading it ...' : 'Open a skin file'}</button>
        {opened && <div className="share-inspect" data-testid="inspected">
          <div><b>{opened.info.skin}</b>: {opened.info.sheets} style sheet{opened.info.sheets === 1 ? '' : 's'}, {opened.info.pictures} picture{opened.info.pictures === 1 ? '' : 's'}, {opened.info.fonts} font{opened.info.fonts === 1 ? '' : 's'}.</div>
          <div className="dim small">{v ? `Made with FM Skin Studio ${v.studio_version ?? 'unknown'}${v.game_build ? ` for game build ${v.game_build}` : ''}.` : 'Not made with FM Skin Studio (no versions inside); it is opened the same way.'}</div>
          {opened.info.build_note && <div className="warn small">This skin was {opened.info.build_note}; some of it may look different.</div>}
          {opened.info.refused.length > 0 && <div className="small" data-testid="refused">Left out ({opened.info.refused.length}): {opened.info.refused.map((r) => `${r.file} (${r.why})`).join('; ')}</div>}
          <label>Name of your copy <input aria-label="Name of your copy" value={name} onChange={(e) => setName(e.target.value.trim())} /></label>
          {!NAME_OK.test(name) && <div className="warn small">Use only letters, digits, dots, dashes and underscores.</div>}
          {NAME_OK.test(name) && projects.includes(name) && <div className="warn small">A skin with that name already exists. Choose another name.</div>}
          <div><button className="primary" disabled={!nameOk || !!busy} onClick={makeCopy}>{busy === 'open' ? 'Making the copy ...' : 'Make my copy'}</button> <button onClick={() => setOpened(null)}>Cancel</button></div>
        </div>}
      </section>

      <section>
        <h3>Start over</h3>
        {!project ? <div className="dim small">Open a skin first (Projects).</div> : <>
          <p className="dim small">Back to the game&apos;s look for {project}.</p>
          {!lost && <button disabled={!!busy} onClick={askStartOver}>Start over ...</button>}
          {lost && <div className="share-confirm" role="alertdialog" aria-label="Start over?" data-testid="start-over-confirm">
            {Object.keys(lost.lost).length === 0
              ? <div>{project} has no changes yet; starting over changes nothing you can see.</div>
              : <><div>Starting over takes away:</div><ul>{lostText(lost.lost).map((t) => <li key={t}>{t}</li>)}</ul></>}
            <div className="dim small">Your current skin is moved to the trash folder ({lost.trash}), not erased. The copy already in your skins folder stays as it is until you put the skin in the game again.</div>
            <button className="primary" disabled={!!busy} onClick={startOver}>{busy === 'over' ? 'Starting over ...' : 'Yes, start over'}</button> <button onClick={() => setLost(null)}>Keep my skin</button>
          </div>}
          {done && <div className="ok small" data-testid="started-over">Done: {project} is back to the game&apos;s look. The previous state is in {done}.</div>}
        </>}
      </section>
    </div>
  )
}
