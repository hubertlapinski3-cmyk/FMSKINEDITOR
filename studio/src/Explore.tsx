import { useCallback, useEffect, useState } from 'react'
import { rpc, RpcError } from './engine'
import { sayOf, type Said } from './plainError'

// Stage 4G (Advanced): the asset explorer. READ ONLY - the installation profile, the bundle inventory, the asset
// registry and the dependency graph, plus the typed adapters' editable surface. Nothing here writes the game: the
// buttons that scan or build the graph are jobs that only read the installation.

interface ProfileRow { install_id: string; role?: string; game_dir?: string }
interface Profile {
  install_id: string; game_build: string | null; steam_build_id: string | null; unity_version: string | null
  catalog_sha256: string | null; manifest_dat_sha256: string | null; game_dir: string
}
interface ProfileGet { active: string | null; installs: ProfileRow[]; profile: Profile | null; problems: { message: string }[]; drift: { code: string; message: string }[] }
interface CatStatus { catalog: { status: string; records: number; sha256: string | null }; manifest_dat: { status: string; size: number | null }; counts: { catalog_crc_status: Record<string, number>; manifest_status: Record<string, number> }; identity_stale: boolean; annotated_utc: string | null }
interface InvStatus { bundles: number; states: Record<string, number>; assets: number; last_scan: { state: string; finished_utc: string } | null }
interface AssetRow { bundle: string; cab: string; path_id: string; type: string; name: string | null; guid: string | null; key?: Record<string, string> }
interface Edge { id: number | null; kind: string; relation: string | null; resolution: string; reason: string | null; direct: boolean; count: number; src: { bundle: string; path_id: string | null; name: string | null } | null; dst: { bundle: string; path_id: string | null; name: string | null } | null; candidates?: { bundle: string; path_id: string; role: string | null }[] }
interface Affected { status: string; rebuild_required: string[]; possibly_affected_at_runtime: string[]; unknown: { what: string; bundle?: string; reason?: string }[]; notes: string[] }
interface Adapter { name: string; version: number; asset_types: string[]; edit_kind: string; properties: { name: string; type: string; evidence: string }[]; limitations: string[]; evidence: { status: string; basis: string; stages: string[] } }
interface ReadAsset { adapter: Adapter | null; identity: Record<string, any>; summary: Record<string, any> | null; fingerprint: string | null; note?: string }

export const RES_BADGE: Record<string, string> = { resolved: 'ok', ambiguous: 'warn', unresolved: 'dim' }

/** status -> chip class: a match is good, a mismatch is bad, everything unknown is a plain neutral state (never a pass). */
export function statusClass(s: string | null | undefined): string {
  if (!s || s === 'not_checked' || s === 'not checked') return 'dim'
  if (/match$/.test(s)) return 'ok'
  if (/mismatch/.test(s)) return 'bad'
  if (/stale/.test(s)) return 'bad'
  return 'warn'                       // missing, ambiguous, unsupported, failed, stored_zero
}

export default function Explore({ say }: { say: (s: string) => void }) {
  const [prof, setProf] = useState<ProfileGet | null>(null)
  const [cat, setCat] = useState<CatStatus | null>(null)
  const [inv, setInv] = useState<InvStatus | null>(null)
  const [adapters, setAdapters] = useState<Adapter[]>([])
  const [q, setQ] = useState('')
  const [type, setType] = useState('')
  const [rows, setRows] = useState<AssetRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [sel, setSel] = useState<AssetRow | null>(null)
  const [read, setRead] = useState<ReadAsset | null>(null)
  const [uses, setUses] = useState<Edge[]>([])
  const [usedBy, setUsedBy] = useState<Edge[]>([])
  const [affected, setAffected] = useState<Affected | null>(null)
  const [problem, setProblem] = useState<Said | null>(null)
  const [busy, setBusy] = useState('')

  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); say('ERROR ' + m); setProblem(e instanceof RpcError ? sayOf(e) : { plain: String(m), details: String(m) }) }, [say])

  useEffect(() => {
    rpc<ProfileGet>('install.profile_get').then((p) => { setProf(p); if (p.profile) { rpc<CatStatus>('catalog.status').then(setCat).catch(() => {}); rpc<InvStatus>('inventory.status').then(setInv).catch(() => {}) } }).catch(fail)
    rpc<{ adapters: Adapter[] }>('edit.adapters').then((r) => setAdapters(r.adapters)).catch(() => {})
  }, [fail])

  async function search() {
    setProblem(null); setBusy('searching')
    try {
      const p: Record<string, unknown> = { limit: 50 }
      if (q) p.q = q
      if (type) p.type = type
      const r = await rpc<{ total: number; assets: AssetRow[] }>('registry.search', p)
      setRows(r.assets); setTotal(r.total); setSel(null); setRead(null); setUses([]); setUsedBy([]); setAffected(null)
    } catch (e) { fail(e) } finally { setBusy('') }
  }

  async function pick(a: AssetRow) {
    setSel(a); setRead(null); setUses([]); setUsedBy([]); setAffected(null); setProblem(null)
    try {
      const [r, u, b, f] = await Promise.all([
        rpc<ReadAsset>('edit.read', { bundle: a.bundle, path_id: a.path_id }),
        rpc<{ edges: Edge[] }>('graph.uses', { bundle: a.bundle, cab: a.cab, path_id: a.path_id }),
        rpc<{ edges: Edge[] }>('graph.used_by', { bundle: a.bundle, cab: a.cab, path_id: a.path_id }),
        rpc<Affected>('graph.affected', { bundle: a.bundle, cab: a.cab, path_id: a.path_id, edit_kind: 'value' }),
      ])
      setRead(r); setUses(u.edges); setUsedBy(b.edges); setAffected(f)
    } catch (e) { fail(e) }
  }

  async function runJob(method: string, label: string) {
    setProblem(null); setBusy(label)
    try {
      const { job } = await rpc<{ job: string }>(method, {})
      for (;;) {
        const v = await rpc<{ state: string; label: string; progress: number; error: string | null }>('jobs.get', { id: job })
        setBusy(`${label}: ${v.label}`)
        if (v.state === 'done' || v.state === 'failed' || v.state === 'cancelled') break
        await new Promise((r) => setTimeout(r, 150))
      }
      say(`${label} finished`)
      const s = await rpc<InvStatus>('inventory.status').then((i) => i).catch(() => inv)
      setInv(s)
    } catch (e) { fail(e) } finally { setBusy('') }
  }

  return (
    <div className="explore" data-testid="explore">
      <h2>Assets and dependencies</h2>
      {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}

      <div className="pkg">
        <b>Installation</b>{' '}
        {prof?.profile
          ? <span data-testid="explore-profile">
              <span className="mono small">{prof.profile.game_dir}</span>
              <span className="small dim"> · build {prof.profile.game_build ?? '?'}{prof.profile.steam_build_id ? ` · Steam ${prof.profile.steam_build_id}` : ''} · id <span className="mono">{prof.profile.install_id}</span></span>
            </span>
          : <span className="dim">no installation selected yet</span>}
        {prof?.problems.map((p, i) => <div key={i} className="warn">{p.message}</div>)}
        {prof?.drift.map((d, i) => <div key={i} className="warn" data-testid="explore-stale">The game folder no longer matches its profile: <span className="mono small">{d.message}</span></div>)}
        {inv && <div className="small dim" data-testid="explore-inv">inventory: {inv.bundles} bundles ({Object.entries(inv.states).map(([k, v]) => `${v} ${k}`).join(', ')}), {inv.assets} assets{inv.last_scan ? ` · last scan ${inv.last_scan.state} ${inv.last_scan.finished_utc}` : ''}</div>}
        {cat && <div className="small dim" data-testid="explore-cat">
          catalog <span className={cat.catalog.status === 'ok' ? 'ok' : 'bad'}>{cat.catalog.status}</span> ({cat.catalog.records} records){cat.annotated_utc ? ` · CRC statuses checked ${cat.annotated_utc}` : ' · CRC statuses not checked yet'}
          {cat.identity_stale && <span className="badge st bad"> stale identity</span>}
        </div>}
        <div>
          <button disabled={!prof?.profile || !!busy} onClick={() => runJob('inventory.scan', 'scanning the installation')}>Scan the installation (read-only)</button>{' '}
          <button disabled={!prof?.profile || !inv?.bundles || !!busy} onClick={() => runJob('graph.build', 'building the dependency graph')}>Build the graph (read-only)</button>
        </div>
      </div>

      <div className="pkg">
        <b>Typed adapters</b> <span className="dim small">what can be edited, and the evidence for it</span>
        {adapters.map((a) => (
          <details key={a.name} className="adapter">
            <summary><span className="mono">{a.name}</span> <span className="small dim">{a.properties.map((p) => p.name).join(', ') || 'no editable property'}</span> <span className={'badge st ' + (a.edit_kind === 'value' ? 'ok' : 'bad')}>{a.edit_kind}</span></summary>
            <div className="small">{a.properties.map((p) => <div key={p.name}><b>{p.name}</b> <span className="dim">{p.type}</span></div>)}</div>
            <ul className="small dim">{a.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            <div className="small dim">evidence: <span className={a.evidence.status.startsWith('Confirmed') || a.evidence.status.startsWith('Runtime') ? 'ok' : 'warn'}>{a.evidence.status}</span> · {a.evidence.basis} <span className="mono">{a.evidence.stages.join(', ')}</span></div>
          </details>
        ))}
      </div>

      <div className="pkg">
        <b>Search assets</b>{' '}
        <input placeholder="name contains" value={q} onChange={(e) => setQ(e.target.value)} />{' '}
        <input placeholder="type (e.g. Texture2D)" value={type} onChange={(e) => setType(e.target.value)} />{' '}
        <button disabled={!!busy} onClick={search}>Search</button>
        {rows && <span className="small dim"> {rows.length} of {total} matches</span>}
        {rows && rows.length === 0 && <div className="dim">Nothing matches. Clear a filter and search again.</div>}
        {rows && rows.length > 0 && (
          <table className="tbl" data-testid="explore-rows">
            <thead><tr><th>name</th><th>type</th><th>bundle</th><th>PathID</th></tr></thead>
            <tbody>{rows.map((a, i) => (
              <tr key={i} className={sel === a ? 'sel' : ''} onClick={() => pick(a)}>
                <td>{a.name || <span className="dim">(unnamed)</span>}</td><td>{a.type}</td>
                <td className="mono small">{a.bundle}</td><td className="mono small">{a.path_id}</td>
              </tr>))}</tbody>
          </table>)}
      </div>

      {sel && (
        <div className="pkg" data-testid="explore-detail">
          <b>{sel.name || sel.type}</b> <span className="mono small">{sel.bundle} · {sel.cab} · {sel.path_id}</span>
          {sel.guid && <span className="small dim"> · GUID <span className="mono">{sel.guid}</span></span>}
          {read && (read.adapter
            ? <div>
                <div>adapter <span className="mono">{read.adapter!.name}</span> <span className="small dim">{read.adapter!.evidence.status}</span></div>
                <pre className="doc small">{JSON.stringify(read.summary, null, 1)}</pre>
                <ul className="small dim">{read.adapter!.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
              </div>
            : <div className="dim small" data-testid="explore-no-adapter">{read.note}</div>)}
          {affected && (
            <div data-testid="explore-affected">
              <b>value edit affects:</b> <span className={'badge st ' + statusClass(affected.status === 'complete' ? 'match' : 'warn')}>{affected.status}</span>
              <span className="small"> rebuilds {affected.rebuild_required.join(', ')}</span>
              {affected.possibly_affected_at_runtime.length > 0 && <span className="small dim"> · possibly at runtime: {affected.possibly_affected_at_runtime.join(', ')}</span>}
              {affected.unknown.map((u, i) => <div key={i} className="small dim">unknown: {u.what}{u.bundle ? ` (${u.bundle})` : ''}{u.reason ? ` - ${u.reason}` : ''}</div>)}
            </div>)}
          {(['uses', 'usedBy'] as const).map((dirn) => {
            const edges = dirn === 'uses' ? uses : usedBy
            return (
              <details key={dirn} open={edges.length > 0}>
                <summary>{dirn === 'uses' ? 'uses' : 'used by'} ({edges.length})</summary>
                {edges.length === 0 && <div className="dim small">no edges</div>}
                {edges.map((e) => (
                  <div key={`${e.id}-${e.kind}`} className="edge small">
                    <span className={'badge st ' + (RES_BADGE[e.resolution] || 'dim')} data-testid="edge-resolution">{e.resolution}</span>{' '}
                    <span className="dim">{e.kind}</span>{e.relation && <i> {e.relation}</i>}{' '}
                    <span className="mono">{(dirn === 'uses' ? e.dst : e.src)?.bundle}{(dirn === 'uses' ? e.dst : e.src)?.path_id ? `#${(dirn === 'uses' ? e.dst : e.src)!.path_id}` : ''}</span>
                    {e.resolution !== 'resolved' && e.reason && <span className="dim small"> ({e.reason})</span>}
                    {e.candidates && e.candidates.length > 0 && <span className="dim small"> candidates: {e.candidates.map((c) => `${c.bundle}#${c.path_id}`).join(', ')}</span>}
                    {!e.direct && <span className="dim small"> [derived]</span>}
                  </div>))}
              </details>)
          })}
        </div>)}
    </div>
  )
}
