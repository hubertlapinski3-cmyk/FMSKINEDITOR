import { useCallback, useEffect, useRef, useState } from 'react'
import { rpc, RpcError } from './engine'
import { sayOf, sayOfJobError, type Said } from './plainError'
import { statusClass } from './Explore'

// Stage 4G (Advanced): the transactional installation and recovery view, on the Stage 4F API. Install is ONLY ever
// `install.apply` after a successful preflight with the required explicit confirmations; the legacy native route
// stays on "Put it in the game". Nothing is installed, rolled back or recovered without the button press here, and
// the preflight and the recovery scan shown are read-only.

interface FileOp { rel_path: string; target_state: string; original_sha256: string | null; expected_sha256: string; op: string }
interface Block { code: string; message: string; confirmation?: string }
interface Warning { code: string; message: string }
interface Integrity { rel_path: string; catalog_crc_status: string | null; manifest_status: string | null }
interface Preflight {
  ready: boolean; no_build?: boolean; blocked: Block[]; warnings: Warning[]; required_confirmations: string[]
  file_operations: FileOp[]; integrity_summary: Integrity[]; diagnostics: string[]
  package_identity: { id?: string; schema?: number; game_build?: string | null }; target_profile: Record<string, any>
}
interface Tx {
  tx_id: string; state: string; created_utc: string; error: string | null; completed_utc: string | null
  recovery: string | null; package_dir: string | null; overrides?: string[] | null
  file_operations?: { rel_path: string; state: string | null; verify: string | null; rollback_state: string | null; original_sha256: string | null; actual_sha256: string | null; backup_path: string | null; backup_sha256: string | null; error: string | null }[]
}
interface Recovery { tx_id: string; state: string; ops: number; replaced: number; safe_actions: string[]; recommendation: string; conflicts: string[]; error: string | null }
interface BuildReview { bundles: Record<string, { adapter: string | null; typed: boolean; in_snapshot: boolean; sections: string[]; note?: string }>; findings: { level: string; code: string; message: string }[]; impact: { buildable: boolean; installation_readiness: string; evaluated: boolean }; blocked: Block[] }

export const STAGE3G = 'observed, not guaranteed'
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

export default function Install({ project, say, pollMs = 120 }: { project: string | null; say: (s: string) => void; pollMs?: number }) {
  const [pf, setPf] = useState<Preflight | null>(null)
  const [review, setReview] = useState<BuildReview | null>(null)
  const [approved, setApproved] = useState<string[]>([])
  const [busy, setBusy] = useState<{ label: string; progress: number } | null>(null)
  const [problem, setProblem] = useState<Said | null>(null)
  const [hist, setHist] = useState<{ recovery_required: Tx[]; transactions: Tx[] } | null>(null)
  const [scan, setScan] = useState<Recovery[]>([])
  const [tx, setTx] = useState<Tx | null>(null)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  const fail = useCallback((e: unknown) => { const s = e instanceof RpcError ? sayOf(e) : { plain: String(e), details: String(e) }; setProblem(s); say('ERROR ' + s.details) }, [say])

  const refresh = useCallback(async () => {
    if (!project) return
    try {
      const pfPromise = rpc<Preflight>('install.preflight', { project }).catch((e) => {
        const msg = e instanceof RpcError ? e.message : String(e)
        if (/no build for this project/i.test(msg)) {
          return {
            ready: false, no_build: true, blocked: [], warnings: [], required_confirmations: [],
            file_operations: [], integrity_summary: [], diagnostics: [],
            package_identity: {}, target_profile: {},
          } as Preflight
        }
        throw e
      })
      const [p, h, s] = await Promise.all([
        pfPromise,
        rpc<{ recovery_required: Tx[]; transactions: Tx[] }>('install.history', { limit: 20 }),
        rpc<{ transactions: Recovery[] }>('install.recovery_scan', {}),
      ])
      if (!alive.current) return
      setPf(p); setApproved([]); setHist(h); setScan(s.transactions)
      rpc<BuildReview>('build.review', { project }).then(setReview).catch(() => setReview(null))
    } catch (e) { fail(e) }
  }, [project, fail])
  useEffect(() => { setPf(null); setReview(null); setScan([]); setTx(null); setProblem(null); refresh() }, [refresh])

  async function runJob(method: string, params: Record<string, unknown>, label: string) {
    let v: { state: string; label: string; progress: number; error: string | null; result: Tx | null }
    const { job } = await rpc<{ job: string }>(method, params)
    for (;;) {
      v = await rpc<typeof v>('jobs.get', { id: job })
      if (!alive.current) return null
      setBusy({ label: v.label || label, progress: v.progress })
      if (v.state === 'done' || v.state === 'failed' || v.state === 'cancelled') break
      await wait(pollMs)
    }
    return v
  }

  async function after(label: string, v: Awaited<ReturnType<typeof runJob>>) {
    setBusy(null)
    if (v && v.state === 'done') { say(`${label} finished`); setTx(v.result ?? null) }
    else {
      const s = await sayOfJobError(v?.error || `${label} did not finish`)
      if (alive.current) { setProblem(s); say('ERROR ' + s.details) }
      if (v && v.state === 'cancelled') setProblem({ plain: `${label} was cancelled. The transaction is recorded unfinished; recover it below.`, details: v.error || '' })
    }
    await refresh()
  }

  async function apply() {
    if (!pf || !project) return
    const hard = pf.blocked.filter((b) => !b.confirmation)
    if (hard.length > 0) return                                  // never install over a hard block
    if (pf.required_confirmations.some((c) => !approved.includes(c))) return   // never without every confirmation
    const names = pf.file_operations.map((o) => o.rel_path)
    const listText = names.length ? `\n\nBundles to replace (${names.length}):\n- ${names.join('\n- ')}` : ''
    if (!confirm(`Install the latest build of "${project}" into the game?${listText}\n\nEvery replaced file is backed up and verified first; on any failure the originals are restored. The transaction is recorded and can be rolled back.`)) return
    setProblem(null); setBusy({ label: 'Starting', progress: 0 })
    try { await after('install', await runJob('install.apply', { project, confirmations: approved }, 'installing')) }
    catch (e) { fail(e) } finally { if (alive.current) setBusy(null) }
  }

  async function act(method: string, params: Record<string, unknown>, label: string, warn: string) {
    if (!confirm(warn)) return
    setProblem(null); setBusy({ label: 'Starting', progress: 0 })
    try { await after(label.split(' ')[0], await runJob(method, params, label)) }
    catch (e) { fail(e) } finally { if (alive.current) setBusy(null) }
  }

  const hard = pf?.blocked.filter((b) => !b.confirmation) ?? []
  const overridable = pf?.blocked.filter((b) => b.confirmation) ?? []
  const allConfirmed = !!pf && pf.required_confirmations.every((c) => approved.includes(c))
  const installable = !!pf && hard.length === 0 && allConfirmed
  const state = hard.length > 0 ? 'blocked'
    : overridable.length > 0 || (pf?.required_confirmations.length ?? 0) > 0 ? 'needs confirmation'
    : pf?.ready ? 'ready' : 'blocked'

  return (
    <div className="installview" data-testid="install">
      <h2>Install into the game (transactional)</h2>
      <p className="dim small">The game must be closed. Every replaced file is backed up, the install is journalled, and an interrupted install can be recovered below. The native skins route stays on “Put it in the game”.</p>
      {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}

      {review && (
        <div className="pkg" data-testid="install-review">
          <b>Build plan</b>{' '}
          <span className={'badge st ' + (review.impact.buildable ? 'ok' : 'bad')}>{review.impact.buildable ? 'buildable' : 'not buildable'}</span>{' '}
          <span className="small dim">installation readiness: <b className={review.impact.installation_readiness === 'ready' ? 'ok' : review.impact.installation_readiness === 'uncertain' ? 'warn' : 'bad'}>{review.impact.installation_readiness}</b></span>
          {Object.entries(review.bundles).map(([n, b]) => (
            <div key={n} className="small">{b.adapter ? <span className="mono">{b.adapter}</span> : <span className="dim">(existing pipeline)</span>} {n} <span className="dim">{b.sections.join(', ')}</span>{!b.in_snapshot && <span className="warn small"> not in the snapshot yet</span>}{b.note && <span className="dim small"> · {b.note}</span>}</div>))}
          {review.findings.map((f, i) => <div key={i} className={f.level === 'error' ? 'warn' : 'small dim'} data-testid="install-review-finding">{f.level === 'error' ? '' : ''}{f.message}</div>)}
        </div>)}

      {pf && pf.no_build && (
        <div className="pkg" data-testid="install-no-build">
          <b>Preflight</b> <span className="badge st dim">no build</span>{' '}
          <span className="small dim">No bundle build exists for this project yet. Layout edits do not require a bundle build.</span>
        </div>)}

      {pf && !pf.no_build && (
        <div className="pkg" data-testid="install-preflight">
          <b>Preflight</b>{' '}
          <span className={'badge st ' + (hard.length === 0 && overridable.length === 0 ? 'ok' : 'bad')} data-testid="preflight-state">{state}</span>{' '}
          <span className="small dim">package {pf.package_identity.id ?? '?'} (schema {pf.package_identity.schema}) for build {pf.package_identity.game_build ?? '?'} · target {pf.target_profile.game_build ?? '?'}</span>

          {hard.map((b, i) => <div key={i} className="warn" data-testid="preflight-blocked">{b.message}</div>)}
          {overridable.map((b, i) => <div key={i} className="warn">{b.message}</div>)}
          {pf.warnings.map((w, i) => (
            <div key={i} className="small warn" data-testid="preflight-warning">{w.message}</div>))}
          {pf.warnings.some((w) => w.code === 'catalog_crc_mismatch') && (
            <div className="small dim" data-testid="preflight-caveat">The game logged a CRC mismatch and still used the modified bundle in the ONE tested scenario (Stage 3G): {STAGE3G}. It is not a promise.</div>)}

          {pf.required_confirmations.length > 0 && (
            <div data-testid="preflight-confirm">
              <b className="small">Confirm each warning to install:</b>
              {pf.required_confirmations.map((c) => (
                <label key={c} className="confirm"><input type="checkbox" checked={approved.includes(c)} onChange={(e) => setApproved((a) => e.target.checked ? [...a, c] : a.filter((x) => x !== c))} /> {c}</label>))}
            </div>)}

          <div>
            <button className="primary" disabled={!installable || !!busy} data-testid="install-apply" onClick={apply}>Install into the game</button>
            {pf.required_confirmations.length > 0 && !allConfirmed && <span className="small dim"> every confirmation above is required</span>}
          </div>

          {pf.file_operations.length > 0 && (
            <details open><summary>Files ({pf.file_operations.length})</summary>
              <table className="tbl"><thead><tr><th>bundle</th><th>target is</th><th>catalog</th><th>manifest</th></tr></thead><tbody>
                {pf.file_operations.map((o) => {
                  const integ = pf.integrity_summary.find((s) => s.rel_path === o.rel_path)
                  return (
                    <tr key={o.rel_path}>
                      <td className="mono small">{o.rel_path}</td>
                      <td className="small">{o.target_state}</td>
                      <td className={'small ' + statusClass(integ?.catalog_crc_status)} data-testid="integrity-catalog">{integ?.catalog_crc_status ?? 'not checked'}</td>
                      <td className={'small ' + statusClass(integ?.manifest_status)}>{integ?.manifest_status ?? 'not checked'}</td>
                    </tr>)
                })}
              </tbody></table>
            </details>)}
        </div>)}

      {!pf && !problem && <p className="dim">Reading the package ...</p>}

      {busy && <div className="busy-overlay" role="status" aria-live="polite" data-testid="install-progress">
        <div className="busy-card"><div className="busy-step">{busy.label} ...</div><progress max={1} value={busy.progress} aria-label="Progress" /></div>
      </div>}

      {scan.length > 0 && (
        <div className="pkg" data-testid="install-recovery">
          <h3>Recovery required</h3>
          <p className="dim small">An earlier installation was left unfinished. Nothing runs by itself: choose an action for each transaction. “Roll back” restores the exact originals; “resume” continues only where the journal proves it is safe.</p>
          {scan.map((t) => (
            <div key={t.tx_id} className="recovery" data-testid="recovery-tx">
              <span className="mono small">{t.tx_id}</span> <span className="badge st bad">{t.state}</span>
              <span className="small dim"> {t.replaced} of {t.ops} files replaced</span>
              {t.error && <div className="small dim">{t.error}</div>}
              {t.conflicts.map((c, i) => <div key={i} className="warn small">{c}</div>)}
              <div className="small">recommended: <b>{t.recommendation}</b></div>
              <div>
                <button disabled={!!busy} onClick={() => act('install.recover', { tx_id: t.tx_id, action: 'rollback' }, 'rollback', `Roll transaction ${t.tx_id} back to its exact pre-installation state?\n\nEvery file is restored from its verified backup.`)}>Roll back</button>{' '}
                <button disabled={!!busy || !t.safe_actions.includes('resume')} onClick={() => act('install.recover', { tx_id: t.tx_id, action: 'resume' }, 'resume', `Resume transaction ${t.tx_id}?\n\nOnly the files the journal proves unfinished are installed; already-verified files are left as they are.`)}>Resume</button>{' '}
                <button disabled={!!busy} onClick={() => act('install.recover', { tx_id: t.tx_id, action: 'manual' }, 'manual marking', `Mark transaction ${t.tx_id} for manual intervention?\n\nNothing is modified. It stays on this list until it is rolled back.`)}>Needs a person</button>
              </div>
            </div>))}
        </div>)}

      {hist && (
        <div className="pkg" data-testid="install-history">
          <h3>Transactions</h3>
          {hist.transactions.length === 0 && <div className="dim small">No installation has been run from here yet.</div>}
          {hist.transactions.map((t) => (
            <div key={t.tx_id} className={'tx ' + (hist.recovery_required.some((r) => r.tx_id === t.tx_id) ? 'unresolved' : '')}>
              <button className="linkish" onClick={async () => { try { setTx(await rpc<Tx>('install.transaction', { tx_id: t.tx_id })) } catch (e) { fail(e) } }}>
                <span className="mono small">{t.tx_id}</span>
              </button>{' '}
              <span className={'badge st ' + (t.state === 'completed' ? 'ok' : t.state === 'rolled_back' ? 'dim' : t.state === 'failed' ? 'bad' : 'warn')}>{t.state}</span>
              <span className="small dim"> {t.created_utc}{t.completed_utc ? ` -> ${t.completed_utc}` : ''}</span>
              {t.error && <div className="small dim">{t.error}</div>}
              {t.state === 'completed' && <button className="small" disabled={!!busy} onClick={() => act('install.rollback', { tx_id: t.tx_id }, 'rollback', `Roll back ${t.tx_id}?\n\nRestores every file this transaction changed to its exact original, verified by hash.`)}>Roll back</button>}
            </div>))}
        </div>)}

      {tx && (
        <div className="pkg" data-testid="install-transaction">
          <h3>Transaction <span className="mono small">{tx.tx_id}</span></h3>
          {(tx.file_operations ?? []).map((o) => (
            <div key={o.rel_path} className="small">
              <span className="mono">{o.rel_path}</span>
              <span className={'badge st ' + (o.state === 'replaced' && o.verify === 'match' ? 'ok' : 'warn')}>{o.state}{o.verify ? `/${o.verify}` : ''}</span>
              {o.rollback_state && <span className="badge st dim">{o.rollback_state}</span>}
              <div className="mono small dim">original {o.original_sha256?.slice(0, 12)} → installed {o.actual_sha256?.slice(0, 12)} · backup {o.backup_path ? <span className="ok">{o.backup_sha256?.slice(0, 12)} verified</span> : <span className="dim">none</span>}</div>
              {o.error && <div className="warn small">{o.error}</div>}
            </div>))}
          {tx.recovery && <div className="small dim">{tx.recovery}</div>}
        </div>)}
    </div>
  )
}
