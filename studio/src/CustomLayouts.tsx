// UI1 steps 1, 6, 7, 10: the read-only custom-folder view and the layouttx Apply/Rollback controls.
// Everything that touches the game's CustomGridCompositions folder goes through the four layouttx RPCs in
// engine.ts. The browser never writes a layout file itself and never guesses a hash.

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  customlayout, isApplyRefusal, RpcError,
  type CustomLayoutFolderList, type LayoutPreflight, type LayoutRecovery, type LayoutTx,
} from './engine'

/** Reference files preserved by default in CustomGridCompositions. Matched by SHA-256 prefix for display. */
export const OWNER_FILES: Record<string, string> = {
  'a2c95aa7': 'PlayerReportOverviewComposition-Large',
  '8372412d': 'CompetitionStagesBottomTileComposition',
}
export const RESET_WARNING = 'The game resets layouts too: “reset layout” deletes ONE file from CustomGridCompositions, “reset all” deletes the WHOLE folder. Studio backups survive both.'

const plain = (e: unknown) => (e instanceof RpcError ? e.message : String(e))
const size = (n: number) => (n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`)
const short = (sha: string | undefined) => (sha ? `${sha.slice(0, 12)}…` : '(none)')

/** The unfinished-transaction dialog. Complete clears the busy transaction with rollback and then applies a
 *  fresh transaction; Undo rolls it back. Both paths use the layouttx RPCs, never a direct file write. */
export function LayoutRecoveryDialog({ items, project, say, onDone }: {
  items: LayoutRecovery[]; project: string | null; say: (s: string) => void; onDone: () => void | Promise<void>
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState('')
  const act = async (item: LayoutRecovery, action: 'complete' | 'undo') => {
    setBusy(item.tx_id); setErr('')
    try {
      if (action === 'undo') {
        const r = await customlayout.rollback(item.tx_id)
        say(`recovery undo: ${item.tx_id} (${r.state})`)
      } else {
        if (!project) { setErr('Open a project to complete this transaction.'); return }
        // The engine refuses a new apply while an earlier transaction is busy: settle it first.
        const settled = await customlayout.rollback(item.tx_id)
        say(`recovery settled old transaction ${item.tx_id} (${settled.state})`)
        const pf = await customlayout.preflight(project)
        const r = await customlayout.apply(project, pf?.required_confirmations ?? [])
        if (isApplyRefusal(r)) { setErr(r.refused); say('recovery complete refused: ' + r.refused) }
        else say(`recovery complete: ${r.tx_id} (${r.state})`)
      }
      await onDone()
    } catch (e) { setErr(plain(e)); say('ERROR ' + plain(e)) } finally { setBusy(null) }
  }
  return (
    <section className="pad" data-testid="cl-recovery" role="dialog" aria-label="Unfinished layout transaction">
      <b>UNFINISHED LAYOUT TRANSACTION</b>
      <div className="small dim">Studio found a transaction that did not finish. Settle it before applying new edits.</div>
      {err && <div className="warn small" data-testid="cl-recovery-error">{err}</div>}
      {items.map((t) => <div key={t.tx_id} className="pad" data-testid="cl-recovery-item" data-tx={t.tx_id}>
        <div className="mono small">{t.tx_id} · {t.state}</div>
        {t.error && <div className="warn small">{t.error}</div>}
        <div className="small dim">{t.files.map((f) => `${f.name}: ${f.status}`).join(' · ')}</div>
        <div className="small dim">safe action: {t.safe_action}</div>
        <div className="pad">
          <button type="button" data-testid="cl-recover-complete" disabled={!!busy} onClick={() => act(t, 'complete')}>Complete</button>{' '}
          <button type="button" data-testid="cl-recover-undo" disabled={!!busy} onClick={() => act(t, 'undo')}>Undo</button>
        </div>
      </div>)}
    </section>
  )
}

export default function CustomLayouts({ project, say, recovery: recoveryProp, showRecoveryDialog = true, onRecoveryChange }: {
  project: string | null; say: (s: string) => void; recovery?: LayoutRecovery[]; showRecoveryDialog?: boolean
  onRecoveryChange?: () => void | Promise<void>
}) {
  const [folder, setFolder] = useState<CustomLayoutFolderList | null>(null)
  const [preflight, setPreflight] = useState<LayoutPreflight | null>(null)
  const [pfErr, setPfErr] = useState('')
  const [checked, setChecked] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<LayoutTx | null>(null)
  const [refusal, setRefusal] = useState('')
  const [lastTxId, setLastTxId] = useState('')
  const [txInput, setTxInput] = useState('')
  const [recovery, setRecovery] = useState<LayoutRecovery[]>([])
  const shownRecovery = recoveryProp ?? recovery

  const loadFolder = useCallback(async () => {
    try { setFolder(await customlayout.list()) } catch { setFolder(null) }
  }, [])
  const loadRecovery = useCallback(async () => {
    try { setRecovery(await customlayout.recovery_scan()) } catch { setRecovery([]) }
  }, [])
  const loadPreflight = useCallback(async (p: string): Promise<LayoutPreflight | null> => {
    setPfErr('')
    try {
      const pf = await customlayout.preflight(p)
      setPreflight(pf)
      setChecked([])
      return pf
    } catch (e) {
      setPreflight(null)
      setPfErr(plain(e))
      return null
    }
  }, [])

  // On Studio start (and whenever the project changes) scan for an unfinished transaction and read the folder.
  useEffect(() => { loadRecovery(); loadFolder() }, [loadRecovery, loadFolder])
  useEffect(() => {
    setPreflight(null); setResult(null); setRefusal('')
    if (project) loadPreflight(project)
  }, [project, loadPreflight])

  const refresh = useCallback(async () => {
    await Promise.all([loadFolder(), loadRecovery(), onRecoveryChange?.()]); if (project) await loadPreflight(project)
  }, [loadFolder, loadRecovery, loadPreflight, project, onRecoveryChange])

  /** Which folder files were written by Studio: the preflight marks a file whose hash we ever wrote as
   *  `installed_by_this_app`. This is read-only evidence from the journal, not a guess from the file name. */
  const studioWritten = useMemo(() => {
    const out = new Set<string>()
    for (const op of preflight?.file_operations ?? []) {
      if (op.state === 'installed_by_this_app') out.add(op.name)
    }
    return out
  }, [preflight])

  const needConfirmations = preflight?.required_confirmations ?? []
  const allConfirmed = needConfirmations.every((c) => checked.includes(c))
  const replacementOps = (preflight?.file_operations ?? []).filter((o) => o.state === 'replaces_user_file')

  const apply = async () => {
    if (!project || busy) return
    setBusy(true); setRefusal('')
    try {
      // The preflight is shown before this button can be clicked (and can be refreshed from the same panel).
      const pf = preflight
      if (!pf) { setRefusal('Run the preflight first.'); return }
      if (!pf.ready) { setRefusal('The preflight is blocked: ' + pf.blocked.map((b) => b.message).join('; ')); return }
      if (needConfirmations.length && replacementOps.length && !allConfirmed) {
        setRefusal('Confirm every replacement before applying.'); return
      }
      if (replacementOps.length) {
        const names = replacementOps.map((o) => o.name).join(', ')
        if (!confirm(`Apply will replace ${names}. Each file is backed up first and Rollback restores it byte for byte. Continue?`)) {
          say('apply cancelled: replacement was not confirmed')
          return
        }
      }
      const r = await customlayout.apply(project, needConfirmations.filter((c) => checked.includes(c)))
      if (isApplyRefusal(r)) {
        setRefusal(r.refused)
        say('apply refused: ' + r.refused)
        if (r.required_confirmations) setPreflight((p) => p && { ...p, required_confirmations: r.required_confirmations! })
        return
      }
      setResult(r); setLastTxId(r.tx_id); setTxInput(r.tx_id)
      say(`custom layouts applied: ${r.tx_id} (${r.state})`)
      await refresh()
    } catch (e) { setRefusal(plain(e)); say('ERROR ' + plain(e)) } finally { setBusy(false) }
  }

  const rollback = async (txId: string) => {
    if (!txId || busy) return
    if (!confirm(`Roll back custom-layout transaction ${txId}? Files it created are deleted and your files are restored byte for byte.`)) return
    setBusy(true); setRefusal('')
    try {
      const r = await customlayout.rollback(txId)
      setResult(r)
      say(`custom layouts rolled back: ${txId} (${r.state}, sha256 exact: ${String(r.rollback?.exact)})`)
      await refresh()
    } catch (e) { setRefusal(plain(e)); say('ERROR ' + plain(e)) } finally { setBusy(false) }
  }

  const shownTx = result
  const rollbackNow = lastTxId || txInput

  return (
    <div className="customlayouts" data-testid="cl-root">
      <div className="head">CUSTOM LAYOUT FILES</div>
      <div className="warn pad small" data-testid="cl-reset-warning">{RESET_WARNING}</div>
      {refusal && <div className="warn pad" role="alert" data-testid="cl-refusal">{refusal}</div>}
      {pfErr && <div className="warn pad small" data-testid="cl-preflight-error">{pfErr}</div>}

      {showRecoveryDialog && shownRecovery.length > 0 &&
        <LayoutRecoveryDialog items={shownRecovery} project={project} say={say} onDone={loadRecovery} />}

      <section className="pad" data-testid="cl-folder-section">
        <div className="head">FOLDER (read only)</div>
        <div className="small dim mono" data-testid="cl-folder-path">{folder?.folder || 'not read yet'}{folder && !folder.folder_exists ? ' (folder does not exist)' : ''}</div>
        {folder?.badge && <div className="small dim" data-testid="cl-folder-badge">{folder.badge}</div>}
        {!folder?.files.length && <div className="small dim" data-testid="cl-folder-empty">No custom-layout files in the folder.</div>}
        {!!folder?.files.length && <table className="cl-table" data-testid="cl-folder">
          <thead><tr><th>composition file</th><th>sha256</th><th>size</th><th>modified</th><th>mark</th></tr></thead>
          <tbody>{folder.files.map((f) => {
            const owner = Object.entries(OWNER_FILES).find(([prefix]) => f.sha256?.startsWith(prefix))
            const marks = [
              owner ? `YOURS: ${owner[1]} (${owner[0]}…)` : '',
              studioWritten.has(f.composition) ? 'STUDIO WROTE THIS' : '',
              preflight?.file_operations.some((o) => o.name === f.composition && o.state === 'replaces_user_file') ? 'NEEDS REPLACEMENT CONFIRMATION' : '',
            ].filter(Boolean)
            return <tr key={f.composition} data-testid="cl-folder-row" data-composition={f.composition} data-sha256={f.sha256}
              className={owner ? 'cl-owner' : studioWritten.has(f.composition) ? 'cl-studio' : ''}>
              <td className="mono">{f.composition}</td><td className="mono">{f.sha256}</td><td>{size(f.size)}</td><td>{f.mtime}</td>
              <td data-testid="cl-folder-mark">{marks.join(' · ') || '—'}</td>
            </tr>
          })}</tbody>
        </table>}
      </section>

      <section className="pad" data-testid="cl-apply-section">
        <div className="head">APPLY LAYOUT EDITS</div>
        <div className="small dim">Preflight is read only. It lists every target file, flags the files already in the folder and asks for an explicit confirmation before replacing one.</div>
        <button type="button" data-testid="cl-preflight" disabled={!project || busy} onClick={() => { if (project) loadPreflight(project) }}>Refresh preflight</button>
        {preflight && <div data-testid="cl-preflight-view">
          <div className="small" data-testid="cl-preflight-state">preflight: {preflight.ready ? (needConfirmations.length ? 'needs confirmation' : 'ready') : 'blocked'}</div>
          <div className="small dim">folder: {preflight.folder}{!preflight.folder_exists ? ' (created by Apply)' : ''}</div>
          {preflight.blocked.map((b, i) => <div key={i} className="warn small" data-testid="cl-preflight-blocked">{b.code}: {b.message}</div>)}
          {preflight.warnings.map((w, i) => <div key={i} className="small dim" data-testid="cl-preflight-warning">{w.code}: {w.message}</div>)}
          {!preflight.file_operations.length && <div className="small dim">The build has no custom-layout files.</div>}
          {preflight.file_operations.map((op) => <div key={op.name} className={'small cl-op ' + (op.state === 'replaces_user_file' ? 'cl-user' : op.state === 'installed_by_this_app' ? 'cl-ours' : '')}
            data-testid="cl-preflight-file" data-state={op.state} data-name={op.name}>
            <b className="mono">{op.name}</b> · target <span className="mono">{op.target_path}</span> ·{' '}
            {op.state === 'replaces_user_file' ? <b>REPLACES YOUR FILE</b> : op.state === 'installed_by_this_app' ? 'a file Studio wrote before' : op.state === 'already_this_package' ? 'already this build' : 'new file'} ·{' '}
            {op.before_sha256 ? `replaces existing file (${short(op.before_sha256)})` : 'no file existed before'} → {short(op.after_sha256)}
          </div>)}
          {needConfirmations.map((c) => <label key={c} className="small" style={{ display: 'block' }} data-testid="cl-preflight-confirm">
            <input type="checkbox" checked={checked.includes(c)} onChange={(e) => setChecked((s) => e.target.checked ? [...s, c] : s.filter((x) => x !== c))} />{' '}
            <b className="mono">{c}</b>: {preflight.confirmation_reasons?.[c] || 'confirm replacement'}
          </label>)}
        </div>}
        <button type="button" data-testid="cl-apply" disabled={!project || !preflight?.ready || !allConfirmed || busy} onClick={apply}>
          {busy ? 'Working ...' : 'Apply'}
        </button>
        {replacementOps.length > 0 && <span className="small dim"> {replacementOps.length} file(s) need an explicit replacement confirmation.</span>}
      </section>

      <section className="pad" data-testid="cl-rollback-section">
        <div className="head">ROLLBACK</div>
        <div className="small dim">Restores the exact earlier state and verifies every sha256. A file that did not exist before is deleted and its absence confirmed.</div>
        <label className="small">transaction <input data-testid="cl-rollback-tx" value={txInput} onChange={(e) => setTxInput(e.target.value)} placeholder="tx id (from Apply or Recovery)" style={{ width: 260 }} /></label>{' '}
        <button type="button" data-testid="cl-rollback" disabled={!rollbackNow || busy} onClick={() => rollback(rollbackNow)}>Rollback</button>
      </section>

      {shownTx && <section className="pad" data-testid="cl-transaction">
        <div className="head">TRANSACTION {shownTx.tx_id}</div>
        <div className="small mono" data-testid="cl-tx-state">state: {shownTx.state}</div>
        <div className="small" data-testid="cl-backup">
          backup: <b className="mono">{shownTx.tx_id}/backup</b> (Studio custom-layout journal){' '}
          · verified sha256: {Object.entries(shownTx.backup_sha256 || {}).map(([n, s]) => `${n}=${s.slice(0, 12)}…`).join(', ') || '(empty folder)'}
        </div>
        <div className="small" data-testid="cl-journal">
          journal entry: <b className="mono">{shownTx.tx_id}</b> · state {shownTx.state} · created {shownTx.created_utc}{shownTx.completed_utc ? ` · completed ${shownTx.completed_utc}` : ''}
          {shownTx.confirmations?.length ? ` · confirmations ${shownTx.confirmations.join(', ')}` : ''}
        </div>
        {(shownTx.ops || []).map((op, i) => <div key={i} className="small mono" data-testid="cl-journal-op">
          {op.name}: {op.before_sha256 ? short(op.before_sha256) : '(absent)'} → {short(op.after_sha256)}
        </div>)}
        {shownTx.rollback && <div className="small" data-testid="cl-rollback-verify">
          sha256 verification: <b>{shownTx.rollback.exact ? 'exact match to the backup' : 'NOT exact'}</b> · conflicts: {shownTx.rollback.conflicts.join(', ') || 'none'}
          {(shownTx.ops || []).filter((o) => !o.before_sha256).map((o) => <div key={o.name} data-testid="cl-rollback-absent">
            {o.name} did not exist before: {Object.prototype.hasOwnProperty.call(shownTx.rollback!.folder_now, o.name) ? 'STILL PRESENT' : 'confirmed gone'}
          </div>)}
        </div>}
        {shownTx.error && <div className="warn small">{shownTx.error}</div>}
      </section>}
    </div>
  )
}
