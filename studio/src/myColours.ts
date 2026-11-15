// "My colours" (owner requirement, 2026-11-15): up to 10 colours a person keeps as a personal palette, offered as one-click choices wherever Simple mode picks a colour.
// Kept in the browser's own storage on this PC (a per-person convenience, like the window size), as plain #RRGGBB: a saved colour carries no transparency, and applying one keeps the transparency of the colour it replaces.
// Adding and removing are explicit actions; nothing is added by using a colour.
export const MAX_MY_COLOURS = 10
export const MY_COLOURS_KEY = 'studio.myColours'
const HEX = /^#[0-9A-F]{6}$/

export const normalise = (rgb: string): string => rgb.trim().toUpperCase()

export function loadMine(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(MY_COLOURS_KEY) || '[]')
    if (!Array.isArray(v)) return []
    const out: string[] = []
    for (const x of v) { const c = typeof x === 'string' ? normalise(x) : ''; if (HEX.test(c) && !out.includes(c)) out.push(c) }
    return out.slice(0, MAX_MY_COLOURS)
  } catch { return [] }                                   // no storage, or a value that is not ours: start empty
}

export function saveMine(list: string[]): void {
  try { localStorage.setItem(MY_COLOURS_KEY, JSON.stringify(list.slice(0, MAX_MY_COLOURS))) } catch { /* no storage: the list lasts for this run */ }
}

export type AddResult = { list: string[]; ok: boolean; why?: string }

export function addMine(list: string[], rgb: string): AddResult {
  const c = normalise(rgb)
  if (!HEX.test(c)) return { list, ok: false, why: 'That is not a colour.' }
  if (list.includes(c)) return { list, ok: false, why: `${c} is already in My colours.` }
  if (list.length >= MAX_MY_COLOURS) return { list, ok: false, why: `My colours holds ${MAX_MY_COLOURS}. Remove one first.` }
  return { list: [...list, c], ok: true }
}

export function removeMine(list: string[], rgb: string): string[] {
  const c = normalise(rgb)
  return list.filter((x) => x !== c)
}
