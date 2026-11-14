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
