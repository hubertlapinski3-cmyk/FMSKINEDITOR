// The interface mode (docs/SIMPLE-MODE-PLAN.md S1). "advanced" is what the first versions called "expert".
export type Mode = 'simple' | 'advanced'
export const MODE_KEY = 'studio.mode'

/** The mode to start in. A stored choice wins ('expert', the old name, is 'advanced'). With nothing stored, a FRESH install is told apart by an EMPTY workspace
 *  (no projects), not by the missing setting: only then is Simple the default; an install that already holds projects becomes Advanced, as it was. */
export function resolveMode(stored: string | null, projectCount: number): Mode {
  if (stored === 'simple') return 'simple'
  if (stored === 'advanced' || stored === 'expert') return 'advanced'
  return projectCount === 0 ? 'simple' : 'advanced'
}

export function readStoredMode(): string | null {
  try { return localStorage.getItem(MODE_KEY) } catch { return null }
}

export function storeMode(m: Mode): void {
  try { localStorage.setItem(MODE_KEY, m) } catch { /* no storage: the mode lasts for this run */ }
}
