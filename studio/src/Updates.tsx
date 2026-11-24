import { useCallback, useEffect, useState } from 'react'
import { rpc, RpcError } from './engine'
import { sayOf, sayOfJobError, type Said } from './plainError'

interface Prof { id: string; game_build: string | null; catalog_hash: string | null; scanned_utc: string; tokens: number; sheets: number; rules: number; note?: string | null }
interface Status { state: string; message: string; next?: string[]; block_bundle_install?: boolean; profile?: string }
interface Item { kind: string; item: string; state: string; detail: string; fix?: unknown }
interface Reread { snapshot: { taken_utc: string; game_build: string | null; catalog_hash: string | null }; index: { sheets: number; tokens: number; literals: number }; quarantined: number }
const STATE_CLASS: Record<string, string> = { ok: 'ok', 'target moved': 'moved', 'target gone': 'gone', 'vanilla value changed': 'review' }
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))
export const REREAD_ADVICE = 'FIRST verify in Steam (right-click Football Manager 27 > Properties > Installed files > Verify integrity of game files) and let it finish, because an update leaves untouched files alone and a skin can still be in them.'

/** Game updates: status of the live game against the active profile, the in-app Re-read-the-game recovery for an
 * updated game, Scan game, profiles, and the diff of two profiles with the state of each project item. */
export default function Updates({ project, say, onChanged }: { project: string | null; say: (s: string) => void; onChanged: () => void }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [profiles, setProfiles] = useState<Prof[]>([])
  const [oldId, setOldId] = useState(''), [newId, setNewId] = useState('')
  const [diff, setDiff] = useState<any>(null)
  const [items, setItems] = useState<Item[]>([])
  const [busy, setBusy] = useState(false)
  const [rereading, setRereading] = useState<{ label: string; progress: number } | null>(null)
  const [reread, setReread] = useState<Reread | null>(null)
  const [problem, setProblem] = useState<Said | null>(null)
  const [err, setErr] = useState('')
  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) }, [say])
  const rereadFail = useCallback((e: unknown) => { const s = e instanceof RpcError ? sayOf(e) : { plain: String(e), details: String(e) }; setProblem(s); say('ERROR ' + s.details) }, [say])

  const load = useCallback(async () => {
    const r = await rpc<{ status: Status; profiles: Prof[] }>('update.status'); setStatus(r.status); setProfiles(r.profiles)
    const ids = r.profiles.map((p) => p.id)
    setNewId((n) => (n && ids.includes(n) ? n : r.status.profile ?? ids[ids.length - 1] ?? ''))
    setOldId((o) => (o && ids.includes(o) ? o : ids.find((i) => i !== (r.status.profile ?? ids[ids.length - 1])) ?? ''))
  }, [])
  useEffect(() => { load().catch(fail) }, [load, fail])

  const reRead = async () => {
    if (!confirm(`Re-read the updated game?\n\n${REREAD_ADVICE}\n\nWith Football Manager closed, this takes a new snapshot of the game's style files and rebuilds the Studio's notes. It only reads the game; nothing in the game folder is changed. If a skin is still installed, the re-read will tell you to verify in Steam first.`)) return
    setProblem(null); setReread(null); setRereading({ label: 'Starting', progress: 0 })
    try {
      const { job } = await rpc<{ job: string }>('snapshot.reread')
      for (;;) {
        const v = await rpc<{ state: string; label: string; progress: number; error: string | null; result: Reread | null }>('jobs.get', { id: job })
        setRereading({ label: v.label || 'Re-reading the game', progress: v.progress })
        if (v.state === 'done' || v.state === 'failed' || v.state === 'cancelled') {
          if (v.state === 'done' && v.result) {
            setReread(v.result)
            say(`re-read the game: catalog ${v.result.snapshot.catalog_hash ?? '?'} · ${v.result.index.sheets} sheets, ${v.result.index.tokens} colours`)
          } else {
            const s = await sayOfJobError(v.error || 'the re-read did not finish')
            setProblem(s); say('ERROR ' + s.details)
          }
          break
        }
        await wait(150)
      }
      await load(); onChanged()                       // the new notes change the project states too
    } catch (e) { rereadFail(e) } finally { setRereading(null) }
  }

  const scan = async () => {
    const build = prompt('Game build of the files being scanned (e.g. 27.0.1.2503222; leave empty if unknown):', profiles.length ? profiles[profiles.length - 1].game_build ?? '' : '')
    if (build === null) return
    setBusy(true); setErr('')
    try { const r = await rpc<{ profile: Prof }>('update.scan', { build: build.trim() }); say(`scanned ${r.profile.id}: ${r.profile.tokens} tokens, ${r.profile.rules} rules`); await load() } catch (e) { fail(e) } finally { setBusy(false) }
  }
  const importOld = async () => {
    let path: string | undefined
    if ('__TAURI_INTERNALS__' in window) { const { open } = await import('@tauri-apps/plugin-dialog'); const r = await open({ directory: true, multiple: false, title: 'Folder with the stock style bundles of the other build' }); path = typeof r === 'string' ? r : undefined }
    else path = prompt('Folder with the stock ui-styles_assets_common/default bundles of the other build:')?.trim()
    if (!path) return
    const build = prompt('Game build of that folder (e.g. 27.0.1.2494769):')?.trim() || ''
    const catalog_hash = prompt('catalog.hash of that build (optional):')?.trim() || ''
    setBusy(true); setErr('')
    try { const r = await rpc<{ profile: Prof }>('update.import_profile', { path, build, catalog_hash }); say(`imported profile ${r.profile.id}`); await load() } catch (e) { fail(e) } finally { setBusy(false) }
  }
  const runDiff = async () => {
    setBusy(true); setErr('')
    try { const r = await rpc<{ diff: any; items?: Item[] }>('update.diff', { old: oldId, new: newId, ...(project ? { project } : {}) }); setDiff(r.diff); setItems(r.items ?? []) } catch (e) { fail(e) } finally { setBusy(false) }
  }
  const autofix = async () => {
    if (!project) return
    try { const r = await rpc<{ applied: string[]; items: Item[] }>('update.autofix', { project, old: oldId, new: newId }); setItems(r.items); say(`auto-fixed: ${r.applied.join('; ') || 'nothing'}`); onChanged() } catch (e) { fail(e) }
  }
  const counts = items.reduce<Record<string, number>>((m, i) => ({ ...m, [i.state]: (m[i.state] ?? 0) + 1 }), {})
  const List = ({ title, rows, fmt }: { title: string; rows: any[]; fmt: (r: any) => string }) => rows.length ? <details><summary>{title} ({rows.length})</summary>{rows.slice(0, 60).map((r, i) => <div key={i} className="mono small">{fmt(r)}</div>)}</details> : null

  return (
    <div className="updates">
      <div className="head">GAME UPDATES <button onClick={() => load().catch(fail)}>refresh</button></div>
      {err && <div className="warn pad">{err}</div>}
      {status && <div className={'ustatus s-' + status.state}><b>{status.state.replace('_', ' ')}</b> {status.message}
        {status.block_bundle_install && <div className="warn">Bundle installs are blocked until this is resolved. Native skins are not affected.</div>}
        {status.state === 'catalog_changed' && (
          <div className="pkg reread" data-testid="reread-card">
            <h3>The game was updated - re-read it from here</h3>
            <p className="dim small">{REREAD_ADVICE}</p>
            <button className="primary" disabled={!!rereading} data-testid="reread-button" onClick={reRead}>{rereading ? 'Re-reading ...' : 'Re-read the game'}</button>
            {rereading && <div className="small dim" data-testid="reread-progress">{rereading.label} ... <progress max={1} value={rereading.progress} aria-label="Progress" /></div>}
            {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}
            {reread && <div className="ok small" data-testid="reread-done">
              Done: a new snapshot of the updated game ({reread.snapshot.catalog_hash ?? 'catalog ?'}) and a rebuilt style index ({reread.index.sheets} sheets, {reread.index.tokens} colours).
              Bundle installs work again; read the diff below before rebuilding a skin.
            </div>}
          </div>)}
        {status.next && <ol>{status.next.map((s) => <li key={s}>{({ restore_check: 'Restore check: put the stock files back (backup or Steam verify)', new_snapshot: 'Re-read the game (the button above)', scan: 'Scan game (below)', diff: 'Diff old against new (below)', restore: 'Restore the changed bundles' } as Record<string, string>)[s] ?? s}</li>)}</ol>}
      </div>}
      <div className="pad"><button disabled={busy} onClick={scan}>Scan game</button> <button disabled={busy} onClick={importOld} title="Scan a folder of an older build's stock style bundles, read-only">Import older build</button></div>
      <div className="pad dim">Profiles</div>
      {profiles.map((p) => <div key={p.id} className="prof"><b>{p.game_build ?? 'build ?'}</b> <small>{p.id.split('-').pop()} · {p.tokens} tokens · {p.rules} rules{p.note ? ' · ' + p.note.slice(0, 40) : ''}</small></div>)}
      {profiles.length >= 2 && <div className="pad">
        <label>old <select value={oldId} onChange={(e) => setOldId(e.target.value)}>{profiles.map((p) => <option key={p.id} value={p.id}>{p.game_build ?? p.id}</option>)}</select></label>{' '}
        <label>new <select value={newId} onChange={(e) => setNewId(e.target.value)}>{profiles.map((p) => <option key={p.id} value={p.id}>{p.game_build ?? p.id}</option>)}</select></label>{' '}
        <button disabled={busy || !oldId || !newId || oldId === newId} onClick={runDiff}>Diff</button>
      </div>}
      {diff && <div className="diff">
        <div className="pad"><b>{diff.old_build ?? diff.old} → {diff.new_build ?? diff.new}</b></div>
        <div className="pad">tokens: +{diff.tokens.added_count} −{diff.tokens.removed_count} changed {diff.tokens.changed_count}; rules: selector vanished {diff.rules.vanished_count}, moved/changed {diff.rules.moved_or_changed_count}, new {diff.rules.added_count}; sheets +{diff.sheets.added.length} −{diff.sheets.removed.length}</div>
        <List title="Tokens added" rows={diff.tokens.added} fmt={(r) => r} />
        <List title="Tokens removed" rows={diff.tokens.removed} fmt={(r) => r} />
        <List title="Tokens changed" rows={diff.tokens.changed} fmt={(r) => `${r.token}: ${r.old} → ${r.new}`} />
        <List title="Tokens renamed (probable)" rows={diff.tokens.renamed} fmt={(r) => `${r.old} → ${r.new}`} />
        <List title="Rules whose selector vanished" rows={diff.rules.vanished} fmt={(r) => `[${r.sheet}] ${r.selector}`} />
        <List title="Rules moved or changed" rows={diff.rules.moved_or_changed} fmt={(r) => `${r.kind} [${r.sheet ?? r.from?.join(',')}] ${r.selector.slice(0, 80)}${r.props ? ' — ' + Object.keys(r.props).join(', ') : ''}`} />
        <div className="pad dim">icons: {diff.icons.available ? `${diff.icons.renamed.length} renamed, ${diff.icons.removed.length} removed, ${diff.icons.added.length} added` : 'not compared — ' + diff.icons.reason}</div>
        <div className="pad dim">layouts: {diff.layouts.available ? `${diff.layouts.changed.length} changed` : 'not compared — ' + diff.layouts.reason}</div>
      </div>}
      {project && items.length > 0 && <div className="items">
        <div className="pad"><b>{project}</b>: {Object.entries(counts).map(([k, n]) => `${n} ${k}`).join(', ')} {counts['target moved'] ? <button onClick={autofix}>Auto-fix {counts['target moved']} moved</button> : null}</div>
        {items.filter((i) => i.state !== 'ok').map((i, k) => <div key={k} className={'item st-' + STATE_CLASS[i.state]}><b>{i.state}</b> {i.kind}: {i.item}<div className="dim small">{i.detail}</div></div>)}
        {items.every((i) => i.state === 'ok') && <div className="pad dim">Every item of this project is still valid on the new build.</div>}
      </div>}
    </div>
  )
}
