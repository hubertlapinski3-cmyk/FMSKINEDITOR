import { useState } from 'react'
import { rpc, RpcError } from './engine'

interface JobView { state: string; label: string; progress: number; error: string | null; result: any }
export interface ScanResult { imported?: unknown; counts?: Record<string, number>; source_bundles?: number; fingerprint?: string }

/** The plain message + button the Playground, the 5F preview and the Tiles view show when no layout dump is
 *  imported. The button reads the user's own game bundles as a cancellable job; the backend imports the finished
 *  dump only, so a cancel or a failure leaves the stored dump alone. */
export default function ReadLayoutDump({ say, onDone, detail }: { say: (s: string) => void; onDone?: () => void; detail?: string }) {
  const [job, setJob] = useState<string | null>(null)
  const [label, setLabel] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true); setErr(''); setLabel('reading the game ...')
    try {
      const r = await rpc<{ job: string }>('layout.scan')
      setJob(r.job)
      for (;;) {
        const v = await rpc<JobView>('jobs.get', { id: r.job })
        setLabel(v.label || 'reading the game ...')
        if (v.state === 'done') {
          const n = v.result?.counts?.tiles
          say(`layout dump read: ${n ?? '?'} tiles from ${v.result?.source_bundles ?? '?'} bundles`)
          onDone?.()
          break
        }
        if (v.state === 'failed') { setErr(v.error || 'reading the game failed'); break }
        if (v.state === 'cancelled') { setErr('cancelled: nothing was imported'); break }
        await new Promise((r) => setTimeout(r, 350))
      }
    } catch (e) {
      setErr(e instanceof RpcError ? e.message : String(e))
    } finally {
      setBusy(false); setJob(null)
    }
  }
  const cancel = async () => {
    if (!job) return
    try { await rpc('jobs.cancel', { id: job }) } catch (e) { setErr(e instanceof RpcError ? e.message : String(e)) }
  }

  return (
    <div className="pad" data-testid="layout-dump-missing">
      <p>No layout dump is imported yet. {detail || 'The Studio needs to read the game’s own layout files once; it only reads, and it never changes your game.'}</p>
      <div className="row">
        {!busy && <button className="primary" data-testid="read-game-layouts" onClick={run}>Read the game</button>}
        {busy && <button data-testid="cancel-read-game-layouts" onClick={cancel}>Cancel</button>}
        {busy && <span className="dim">{label}</span>}
      </div>
      {err && <div className="warn small" role="alert">{err}</div>}
    </div>
  )
}
