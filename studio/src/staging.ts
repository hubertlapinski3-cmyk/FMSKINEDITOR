// The staged model of the Images view: picking a file, changing the fit or ticking a place only changes this state. Nothing reaches the
// project until "Override" (commit), which sends the whole staged slot in one engine call. Pure functions, no UI, so they are unit-tested.
export interface Slot { bundle: string; path_id: string; kind: 'texture' | 'svg' | 'icon'; name?: string }
export interface Stored extends Slot { source: string; fit?: string; where?: string[] }
export interface Stage { slot: Slot; path?: string; fit?: string; where?: string[] }
export interface State {
  staged: Record<string, Stage>         // unsaved edits by slot key
  versions: Record<string, number>      // bumps on every commit: thumbnails of the stored replacement are keyed by it
  committed: string[]                   // slots committed in this session (for the "saved" feedback)
}
export type Action =
  | { type: 'stage'; slot: Slot; patch: Partial<Pick<Stage, 'path' | 'fit' | 'where'>> }
  | { type: 'revert'; key: string }
  | { type: 'committed'; key: string }
  | { type: 'reset' }

export const keyOf = (s: Slot) => s.bundle + '|' + s.path_id
export const initial = (): State => ({ staged: {}, versions: {}, committed: [] })

const sameSet = (a: string[] = [], b: string[] = []) => a.length === b.length && a.every((x) => b.includes(x))

/** Does the stage differ from what is stored? A new slot (nothing stored) is dirty as soon as it has a file. */
export function isDirty(st: Stage | undefined, stored: Stored | undefined): boolean {
  if (!st) return false
  if (!stored) return !!st.path
  if (st.path) return true
  if (st.fit !== undefined && st.fit !== (stored.fit || 'cover')) return true
  if (st.where !== undefined && !sameSet(st.where, stored.where)) return true
  return false
}

export function reduce(s: State, a: Action): State {
  switch (a.type) {
    case 'stage': {
      const k = keyOf(a.slot)
      const cur = s.staged[k] ?? { slot: a.slot }
      return { ...s, staged: { ...s.staged, [k]: { ...cur, ...a.patch } }, committed: s.committed.filter((x) => x !== k) }
    }
    case 'revert': {
      const { [a.key]: _gone, ...rest } = s.staged
      return { ...s, staged: rest }
    }
    case 'committed': {
      const { [a.key]: _gone, ...rest } = s.staged
      return { staged: rest, versions: { ...s.versions, [a.key]: (s.versions[a.key] ?? 0) + 1 }, committed: [...s.committed.filter((x) => x !== a.key), a.key] }
    }
    case 'reset':
      return initial()
  }
}

/** The one engine call that commits a staged slot (images.commit). A file is only sent when one was picked. */
export function commitParams(project: string, st: Stage, stored: Stored | undefined) {
  const p: Record<string, unknown> = { project, bundle: st.slot.bundle, path_id: st.slot.path_id, kind: st.slot.kind, name: st.slot.name ?? stored?.name ?? '' }
  if (st.path) p.path = st.path
  if (st.fit !== undefined) p.fit = st.fit
  if (st.where !== undefined) p.where = st.where
  return p
}

/** Commit one staged slot. On success the stage is gone and the slot's version is bumped; when the engine refuses, the stage is kept. */
export async function commit(call: (method: string, params: Record<string, unknown>) => Promise<any>, project: string, s: State, key: string, stored: Stored | undefined) {
  const st = s.staged[key]
  if (!st || !isDirty(st, stored)) return { state: s, result: null as any }
  const result = await call('images.commit', commitParams(project, st, stored))
  return { state: reduce(s, { type: 'committed', key }), result }
}

/** Cache key of the stored replacement's thumbnail; a commit bumps the version, so the picture is fetched again. */
export const thumbKey = (project: string, file: string, version: number) => `m|${project}|${file}|${version}`
