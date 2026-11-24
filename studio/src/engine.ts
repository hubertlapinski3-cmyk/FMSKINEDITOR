// Client of the engine's JSON-RPC API (docs/API.md). Inside the desktop shell the Rust side finds or starts the engine and returns its
// URL and session token; in a plain browser pass ?engine=http://127.0.0.1:PORT&token=TOKEN.
export interface Conn { url: string; token: string }
export interface ProblemItem { file: string; line?: number; message: string }
let conn: Conn | null = null
let nextId = 1

export class RpcError extends Error {
  code: number
  data: any
  constructor(e: { code: number; message: string; data?: any }) {
    super(e.message)
    this.code = e.code
    this.data = e.data
  }
}

export async function connect(): Promise<Conn> {
  const q = new URLSearchParams(location.search)
  if (q.get('engine') && q.get('token')) {
    conn = { url: q.get('engine')!, token: q.get('token')! }
  } else if ((window as any).__TAURI_INTERNALS__) {
    const { invoke } = await import('@tauri-apps/api/core')
    const i = await invoke<{ url: string; token: string }>('engine_info')
    conn = { url: i.url, token: i.token }
  } else {
    throw new Error('Open this page with ?engine=http://127.0.0.1:PORT&token=TOKEN, or run it in the desktop shell.')
  }
  return conn
}

export async function rpc<T = any>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  if (!conn) throw new Error('not connected')
  const r = await fetch(conn.url + '/rpc', {
    method: 'POST',
    headers: { 'X-Token': conn.token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: nextId++, method, params }),
  })
  if (!r.ok) throw new Error('engine answered HTTP ' + r.status)
  const j = await r.json()
  if (j.error) throw new RpcError(j.error)
  return j.result as T
}

export function subscribe(on: (type: string, data: any) => void): () => void {
  if (!conn) return () => {}
  const es = new EventSource(`${conn.url}/events?t=${encodeURIComponent(conn.token)}`)
  for (const t of ['job.queued', 'job.started', 'job.progress', 'job.done', 'job.failed', 'job.cancelled', 'render.invalidate'])
    es.addEventListener(t, (ev) => on(t, JSON.parse((ev as MessageEvent).data).data))
  return () => es.close()
}

export interface EngineState {
  app_version?: string
  unitypy?: string
  install: { game_dir: string; aa_dir: string; version: string | null } | null
  running: boolean | null
  tamper: { state: string; message?: string } | null
  snapshot_mismatch: string | null
  vanilla: { game_build?: string | null } | null
  indexed: boolean
  projects: string[]
}
export interface FileItem { path: string; kind: 'text' | 'image' | 'other'; bytes: number }
export interface Job { id: string; title: string; label: string; state: string; progress: number; error: string | null }

// ---- UI1: the custom-layout transaction (layouttx.py) -------------------------------------------------
/** One file in a custom-layout preflight. `state` is the backend's verdict: a user's file needs a
 *  `replace:<name>` confirmation; a file we wrote before is `installed_by_this_app`. */
export interface LayoutFileOp {
  name: string; source: string; target_path: string; size: number; after_sha256: string
  state: 'new' | 'already_this_package' | 'installed_by_this_app' | 'replaces_user_file'
  before_sha256?: string; before_size?: number; written?: boolean
}
export interface LayoutPreflight {
  ready: boolean
  blocked: { code: string; message: string }[]
  warnings: { code: string; message: string }[]
  required_confirmations: string[]
  confirmation_reasons: Record<string, string>
  file_operations: LayoutFileOp[]
  folder: string; folder_exists: boolean
}
export interface LayoutTx {
  tx_id: string; state: string; created_utc: string; completed_utc?: string | null
  package_dir: string; folder: string; folder_existed: boolean; confirmations: string[]
  ops: LayoutFileOp[]; backup_sha256: Record<string, string>; error?: string | null
  rollback?: { utc: string; conflicts: string[]; exact: boolean; folder_now: Record<string, string>
    changed?: { name: string; before_sha256: string | null; after_sha256: string; now_sha256: string | null }[] }
}
/** The engine turns a refused customlayout.apply into a plain result instead of an RPC error. */
export interface LayoutApplyRefusal { refused: string; blocked?: unknown[]; required_confirmations?: string[] }
export interface LayoutRecovery {
  tx_id: string; state: string; files: { name: string; status: string }[]; error?: string | null; safe_action: string
}
export interface CustomLayoutFolderList {
  folder: string; folder_exists: boolean; badge: string; warning: string
  files: { composition: string; size: number; mtime: string; sha256: string }[]
}

/** The four layouttx RPCs plus the read-only folder listing, in one typed place. */
export const customlayout = {
  list: () => rpc<CustomLayoutFolderList>('customlayout.list', {}),
  preflight: (project: string) => rpc<LayoutPreflight>('customlayout.preflight', { project }),
  apply: (project: string, confirmations: string[] = []) =>
    rpc<LayoutTx | LayoutApplyRefusal>('customlayout.apply', { project, confirmations }),
  rollback: (tx_id: string) => rpc<LayoutTx>('customlayout.rollback', { tx_id }),
  restore_before: (tx_id: string, confirm = false) =>
    rpc<any>('customlayout.restore_before', { tx_id, confirm }),
  recovery_scan: () => rpc<LayoutRecovery[]>('customlayout.recovery_scan', {}),
  base: (composition: string, profile?: string) =>
    rpc<any>('customlayout.base', { composition, ...(profile ? { profile } : {}) }),
  runtime: (composition: string, object?: unknown, edits?: unknown[], project?: string | null, profile?: string) =>
    rpc<any>('customlayout.runtime', { composition, object, edits, project: project || undefined, ...(profile ? { profile } : {}) }),
  apply_edits: (project: string, composition: string, edits: unknown[], confirmations: string[] = [], runtime?: { cols: number; rows: number }, applyToBreakpoints = false) =>
    rpc<LayoutTx | LayoutApplyRefusal>('customlayout.apply_edits', { project, composition, edits, confirmations, runtime, ...(applyToBreakpoints ? { apply_to_breakpoints: true } : {}) }),
}
export const customLayoutPreflight = (project: string) => customlayout.preflight(project)
export const customLayoutApply = (project: string, confirmations: string[] = []) => customlayout.apply(project, confirmations)
export const customLayoutRollback = (tx_id: string) => customlayout.rollback(tx_id)
export const customLayoutRecoveryScan = () => customlayout.recovery_scan()
export const customLayoutList = () => customlayout.list()

/** True when an apply result is the refusal object (not a committed transaction). */
export const isApplyRefusal = (r: LayoutTx | LayoutApplyRefusal): r is LayoutApplyRefusal =>
  typeof (r as LayoutApplyRefusal)?.refused === 'string'
