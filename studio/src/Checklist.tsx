import { useCallback, useEffect, useState } from 'react'
import { rpc, RpcError } from './engine'
import AppUpdate from './AppUpdate'

interface Pkg { project: string; id: string; built_utc: string; game_build: string | null; plan_digest: string | null; plan: { op: string; count: number }[]; files: Record<string, { sha256: string; vanilla_sha256: string }>; gate: { passed: boolean; failures: string[]; checked: Record<string, number> }; installable: boolean; latest: boolean; dir: string }
interface Doc { path: string; text: string; results: string }

/** The in-game checklist and the prepared packages (builds with a package.json). Read-only: installing stays in the Build panel. */
export default function Checklist({ say }: { say: (s: string) => void }) {
  const [doc, setDoc] = useState<Doc | null>(null)
  const [pk, setPk] = useState<Pkg[]>([])
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(false)
  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) }, [say])
  useEffect(() => {
    rpc<Doc>('docs.checklist').then(setDoc).catch(fail)
    rpc<{ packages: Pkg[] }>('builds.list').then((r) => setPk(r.packages)).catch(fail)
  }, [fail])
  const copy = async () => { try { await navigator.clipboard.writeText(doc?.results ?? ''); setCopied(true); setTimeout(() => setCopied(false), 2000) } catch (e) { fail(e) } }
  return (
    <div className="checklist">
      <div className="head">IN-GAME CHECKLIST</div>
      <AppUpdate say={say} />
      {err && <div className="warn pad">{err}</div>}
      <div className="pad"><b>Packages</b> <small className="dim">(builds with a package.json; Install build in the Build panel installs the one marked latest)</small></div>
      {pk.length === 0 && <div className="dim pad">No packages yet. Build bundles creates one.</div>}
      {pk.map((p) => (
        <div key={p.project + p.id} className={'pkg' + (p.latest ? ' latest' : '')}>
          <b>{p.project}</b> <span className="mono small">{p.id}</span> {p.latest && <span className="badge saved">latest</span>} <span className={p.gate.passed ? 'ok' : 'bad'}>{p.gate.passed ? 'gate passed' : 'gate FAILED'}</span>
          <div className="small dim">{Object.keys(p.files).join(', ') || 'no bundle changed'} · {p.plan.map((o) => `${o.op}×${o.count}`).join(', ') || 'no operations'}</div>
          <div className="mono small" title={p.plan_digest ?? ''}>plan {p.plan_digest ? p.plan_digest.slice(0, 16) : '-'} · build {p.game_build ?? '?'}{Object.entries(p.files).map(([n, f]) => <span key={n}> · {n.replace(/^ui-|_assets_.*$/g, '')} {f.sha256.slice(0, 12)}</span>)}</div>
        </div>))}
      <div className="pad"><button onClick={copy} disabled={!doc?.results}>{copied ? 'copied' : 'Copy the results message'}</button> <small className="dim">{doc?.path}</small></div>
      {doc && <pre className="doc">{doc.text}</pre>}
    </div>
  )
}
