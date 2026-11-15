// Plain names for the game's colour tokens, for the Simple palette. The labels are NAMED FROM THE GAME'S OWN TOKEN NAMES (a token called layout-modules-block-surface is a
// panel surface); they are a reading aid, not a measurement, and a token no rule matches falls into a group named after its own prefix.
const RULES: [RegExp, string][] = [
  [/^--global-background/, 'Page background'],
  [/^--(global|modal)-text|^--colours-ui-text/, 'Text'],
  [/^--brand-theme|^--colours-brand/, 'Theme and brand colours'],
  [/^--layout-(modules|surfaces|tiles|ui)|^--tiles-|^--modal-/, 'Panels, cards and tiles'],
  [/^--data-tables/, 'Tables'],
  [/^--(buttons|continue-button|core-controls)/, 'Buttons'],
  [/^--colours-tactics/, 'Tactics screen'],
  [/^--colours-calendar/, 'Calendar and training'],
  [/^--(colours-(player|data|linear|chart)|linear-ranges|status-linear|data-(player|average))/, 'Player, rating and chart colours'],
  [/^--colours-base/, 'Base colour ramps'],
  [/^--colours-alpha/, 'See-through overlays'],
  [/^--staff-/, 'Staff screens'],
  [/^--status-/, 'Status marks'],
  [/^--theme-/, 'Theme colours'],
]

export function groupOf(token: string): string {
  for (const [rx, label] of RULES) if (rx.test(token)) return label
  const parts = token.replace(/^--/, '').split('-')
  const head = parts.slice(0, 2).join(' ')
  return 'Other: ' + head
}

export function shortName(token: string): string { return token.replace(/^--/, '') }

export interface BrowseRow { name: string; rgb: string; a: number; reach: number }

/** Rows grouped for display: groups with the most colours first, "Other" groups last, names sorted inside. */
export function grouped(rows: BrowseRow[]): { label: string; rows: BrowseRow[] }[] {
  const m = new Map<string, BrowseRow[]>()
  for (const r of rows) { const g = groupOf(r.name); (m.get(g) ?? m.set(g, []).get(g)!).push(r) }
  return [...m.entries()].map(([label, rs]) => ({ label, rows: rs.sort((a, b) => a.name.localeCompare(b.name)) }))
    .sort((a, b) => Number(a.label.startsWith('Other')) - Number(b.label.startsWith('Other')) || b.rows.length - a.rows.length || a.label.localeCompare(b.label))
}

export function hexOf(rgb: string, a: number): string {
  const h = rgb.toUpperCase()
  return a >= 0.999 ? h : h + Math.round(a * 255).toString(16).padStart(2, '0').toUpperCase()
}
