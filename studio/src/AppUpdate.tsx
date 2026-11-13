import { useEffect, useState } from 'react'

interface Info { version: string; current: string; notes?: string | null; date?: string | null }
const inTauri = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
const call = async <T,>(cmd: string): Promise<T> => { const { invoke } = await import('@tauri-apps/api/core'); return invoke<T>(cmd) }

/** App updates from GitHub Releases. The shell (Rust) does the check and the install; the page only asks. The install refuses while FM27 is running,
 *  stops the engine, runs the signed installer and restarts the app. Only the installed app can update; in a browser or in dev there is nothing to do. */
export default function AppUpdate({ say }: { say: (s: string) => void }) {
  const [cur, setCur] = useState('')
  const [info, setInfo] = useState<Info | null | undefined>(undefined)     // undefined = not checked yet, null = up to date
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  useEffect(() => { if (inTauri()) import('@tauri-apps/api/app').then((m) => m.getVersion()).then(setCur).catch(() => {}) }, [])
  if (!inTauri()) return <div className="pad dim small">App updates work in the installed FM Skin Studio, not in the browser.</div>
  const fail = (e: unknown) => { const m = String(e); setErr(m); say('ERROR ' + m) }
  const check = async () => { setBusy(true); setErr(''); try { setInfo(await call<Info | null>('app_update_check')) } catch (e) { fail(e) } finally { setBusy(false) } }
  const install = async () => { setBusy(true); setErr(''); say('downloading the update, the app restarts when it is installed'); try { await call<void>('app_update_install') } catch (e) { fail(e); setBusy(false) } }
  return (
    <div className="appupdate pad">
      <b>App updates</b> <small className="dim">FM Skin Studio {cur || '?'}</small>{' '}
      <button onClick={check} disabled={busy}>{busy && info === undefined ? 'checking ...' : 'Check for updates'}</button>
      {info === null && <span className="ok"> up to date</span>}
      {info && <span> version <b>{info.version}</b> is available <button className="primary" onClick={install} disabled={busy} title="Closes the game's tools, installs and restarts. Refused while FM27 is running.">Install and restart</button></span>}
      {info?.notes && <div className="small dim">{info.notes}</div>}
      {err && <div className="warn small">{err}</div>}
    </div>
  )
}
