// Things that are built but are NOT part of a release yet (docs/SIMPLE-MODE-PLAN.md, S2). A lab is reachable only in a development build (`npm run tauri dev`), by setting a browser value,
// and only while its release flag is false. The release flag flips in the commit that records the in-game observation that clears it.

/** "Take it out of the game": it deletes a skin folder, and what the game does when the SELECTED skin's folder is deleted has never been observed (Session 1, item (e)).
 *  Until that observation is recorded and shows no breakage, this stays false and no release candidate carries the control. */
export const REMOVAL_RELEASED = false
export const REMOVAL_KEY = 'studio.labs.removal'

export function labsRemoval(): boolean {
  if (REMOVAL_RELEASED) return true
  if (!import.meta.env.DEV) return false                       // an installed build never offers it
  try { return localStorage.getItem(REMOVAL_KEY) === '1' } catch { return false }
}
