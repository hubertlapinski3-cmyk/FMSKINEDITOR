// UI1b step 2, 5: the Game Layouts sidebar. One full-width list of compositions (search, breakpoint suffix,
// "custom" badge from the engine's read-only customlayout.list), with Hierarchy and Element as collapsible
// sections below it. It lives in the App sidebar, not inside the Playground's own multi-pane grid, so names
// are never squeezed into a horizontally scrolling strip.

import { useEffect, useMemo, useState } from 'react'
import { customlayout, rpc, type CustomLayoutFolderList } from './engine'
import type { LayoutSelection, LayoutTile } from './layoutShared'

/** Search normalisation: case and hyphens (and any other punctuation) are ignored. */
export const normName = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')
export const breakpointSuffix = (name: string) => name.match(/-(Large|Standard|Small)$/i)?.[1] ?? ''

/** Rank by exact prefix first, then word prefix, then the game's breakpoint order Large / Standard / Small.
 *  "squadcom" therefore puts SquadComposition-Large, -Standard, -Small ahead of incidental substring hits. */
export function rankCompositions(names: string[], query: string): string[] {
  const q = normName(query.trim())
  if (!q) return names.slice()
  const scored: { name: string; score: number }[] = []
  names.forEach((name, i) => {
    const n = normName(name)
    if (!n.includes(q)) return
    let score = 0
    if (n.startsWith(q)) score += 1000
    const base = n.replace(/(large|standard|small)$/, '')
    if (base.startsWith(q)) score += 500
    const suffix = breakpointSuffix(name)
    score += suffix === 'Large' ? 30 : suffix === 'Standard' ? 20 : suffix === 'Small' ? 10 : 0
    score -= n.length / 100
    score -= i / 10000                      // keep the engine's order for exact ties
    scored.push({ name, score })
  })
  scored.sort((a, b) => b.score - a.score)
  return scored.map((x) => x.name)
}

interface Props {
  project: string | null
  activeComposition: string | null
  selection: LayoutSelection | null
  profile?: string
  onProfileChange?: (profile: string) => void
  onOpenLayout: (name: string) => void
  onSelectTile: (tile: LayoutTile) => void
}

const DEFAULT_PROFILE = '2560x1440 fullscreen, Small, Larger'
const WINDOWED_PROFILE = '2560x1440 windowed, Small, Larger'
const PROFILES = [DEFAULT_PROFILE, WINDOWED_PROFILE] as const
const FAVS_STORAGE_KEY = 'fm27.gameLayouts.favourites'

function loadFavourites(): string[] {
  try {
    const raw = window.localStorage.getItem(FAVS_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

function saveFavourites(favs: string[]) {
  try { window.localStorage.setItem(FAVS_STORAGE_KEY, JSON.stringify(favs)) } catch { /* ignore */ }
}

interface CellRow { cell_index: number; element_id: string; x: number; y: number; w: number; h: number; flags: string[] }
interface ScreenItem {
  name: string
  panel?: string
  composition_set?: string
  breakpoint?: string
  variant?: string
  editable_by_file?: boolean
  editability_label?: string
  confidence?: string
  cells: CellRow[]
}

export default function GameLayouts({ project, activeComposition, selection, profile, onProfileChange, onOpenLayout, onSelectTile }: Props) {
  const [localProfile, setLocalProfile] = useState<string>(DEFAULT_PROFILE)
  const activeProfile = profile ?? localProfile
  const setProfile = (next: string) => {
    setLocalProfile(next)
    onProfileChange?.(next)
  }
  const [screens, setScreens] = useState<ScreenItem[]>([])
  const [confMap, setConfMap] = useState<Record<string, string>>({})
  const [favourites, setFavourites] = useState<string[]>(loadFavourites)
  const [dump, setDump] = useState<{ present?: boolean } | null>(null)
  const [q, setQ] = useState('')
  const [custom, setCustom] = useState<CustomLayoutFolderList | null>(null)
  const [hierarchyOpen, setHierarchyOpen] = useState(true)
  const [elementOpen, setElementOpen] = useState(true)

  useEffect(() => {
    let live = true
    rpc<{ present?: boolean }>('layout.state').then((d) => {
      if (!live) return
      setDump(d)
      if (d?.present) rpc<{ screens: ScreenItem[]; confidences?: Record<string, string> }>('playground.screens', { profile: activeProfile })
        .then((r) => {
          if (!live) return
          const list = r.screens || []
          setScreens(list)
          const map: Record<string, string> = { ...(r.confidences || {}) }
          list.forEach((s) => { if (s.confidence && !map[s.name]) map[s.name] = s.confidence })
          setConfMap(map)
        }).catch(() => {})
    }).catch(() => {})
    return () => { live = false }
  }, [activeProfile])

  useEffect(() => {
    let live = true
    customlayout.list().then((r) => { if (live) setCustom(r) }).catch(() => {})
    return () => { live = false }
  }, [project])

  useEffect(() => {
    let live = true
    rpc<{ favourites?: string[] }>('playground.favourites').then((r) => {
      if (!live || !r || !Array.isArray(r.favourites)) return
      const remote = r.favourites.filter((x): x is string => typeof x === 'string')
      if (remote.length > 0) {
        setFavourites(remote)
        saveFavourites(remote)
      } else {
        const local = loadFavourites()
        if (local.length > 0) {
          rpc('playground.set_favourites', { favourites: local }).catch(() => {})
        }
      }
    }).catch(() => {})
    return () => { live = false }
  }, [])

  const names = useMemo(() => screens.map((s) => s.name), [screens])
  const results = useMemo(() => rankCompositions(names, q), [names, q])
  const byName = useMemo(() => new Map(screens.map((s) => [s.name, s])), [screens])
  const favSet = useMemo(() => new Set(favourites), [favourites])

  const toggleFavourite = (name: string) => {
    setFavourites((prev) => {
      const next = prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]
      saveFavourites(next)
      rpc('playground.set_favourites', { favourites: next }).catch(() => {})
      return next
    })
  }

  const confidenceOf = (name: string) => confMap[name] || byName.get(name)?.confidence || 'unverified'

  const isCustom = (name: string) => {
    const n = normName(name)
    return !!custom?.files.some((f) => {
      const fn = normName(String(f.composition).replace(/\.[a-z0-9]+$/i, ''))
      return fn.length > 0 && (n === fn || n.startsWith(fn) || fn.startsWith(n))
    })
  }

  const activeCells = activeComposition ? (byName.get(activeComposition)?.cells ?? []) : []
  // UI1 step 3: only the selection belonging to the active Game Layout is shown; nothing from another mode.
  const shownSelection = selection && selection.composition === activeComposition ? selection.tile : null

  return (
    <div className="glist" data-testid="game-layouts">
      <div className="head">GAME LAYOUTS <span>{screens.length}</span></div>
      <div className="gl-profile-row">
        <select className="gl-profile-select" data-testid="gl-profile" aria-label="Viewport profile"
          value={activeProfile} onChange={(e) => setProfile(e.target.value)}>
          {PROFILES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div className="gl-favs" data-testid="gl-favourites">
        <div className="gl-favs-head">FAVOURITES <span>{favourites.length}</span></div>
        {!favourites.length && <div className="small dim pad">Star screens below to pin them here.</div>}
        {favourites.length > 0 && (
          <ul className="gl-rows gl-fav-rows" data-testid="gl-fav-rows">
            {favourites.map((name) => {
              const conf = confidenceOf(name)
              const mark = isCustom(name)
              return <li key={`fav:${name}`} data-testid="gl-fav-row" data-composition={name}
                className={name === activeComposition ? 'sel' : ''} onClick={() => onOpenLayout(name)}>
                <div className="gl-row-top">
                  <button type="button" className="gl-star on" data-testid="gl-fav-unstar"
                    aria-label={`Unstar ${name}`} aria-pressed={true}
                    onClick={(e) => { e.stopPropagation(); toggleFavourite(name) }}>★</button>
                  <span className="gl-name">{name}</span>
                </div>
                <span className="gl-meta">
                  <small className="gl-conf" data-testid="gl-fav-confidence" data-confidence={conf}>{conf}</small>
                  {mark && <small className="gl-custom">custom</small>}
                </span>
              </li>
            })}
          </ul>
        )}
      </div>
      <input className="search" data-testid="gl-q" value={q} placeholder="Search compositions (e.g. squadcom)"
        aria-label="Search game layouts" onChange={(e) => setQ(e.target.value)} />
      {dump && !dump.present && <div className="small dim pad">No layout dump is imported yet; the composition list needs the game's own layouts.</div>}
      {dump?.present && !screens.length && <div className="small dim pad">No compositions with tiles were found.</div>}
      <ul className="gl-rows" data-testid="gl-rows">
        {results.map((name) => {
          const item = byName.get(name)
          const suffix = breakpointSuffix(name) || item?.breakpoint || ''
          const cells = item?.cells.length ?? 0
          const mark = isCustom(name)
          const starred = favSet.has(name)
          const conf = confidenceOf(name)
          const editable = item?.editable_by_file !== false
          const variant = item?.variant && item.variant !== 'FM' ? item.variant : ''
          return <li key={name} data-testid="gl-row" data-composition={name} title={name}
            className={(name === activeComposition ? 'sel ' : '') + (!editable ? 'gl-template' : '')}
            onClick={() => { if (editable) onOpenLayout(name) }}>
            <div className="gl-row-top">
              <button type="button" className={'gl-star' + (starred ? ' on' : '')} data-testid="gl-star"
                aria-label={`${starred ? 'Unstar' : 'Star'} ${name}`} aria-pressed={starred}
                onClick={(e) => { e.stopPropagation(); toggleFavourite(name) }}>{starred ? '★' : '☆'}</button>
              <span className="gl-name">{item?.panel ? `${item.panel} · ${name}` : name}</span>
            </div>
            <span className="gl-meta">
              <small className="gl-conf" data-testid="gl-row-confidence" data-confidence={conf}>{conf}</small>
              {suffix && <small className="gl-bp" title={`breakpoint ${suffix}`}>{suffix}</small>}
              {variant && <small className="gl-variant" data-testid="gl-variant">{variant}</small>}
              {!editable && <small className="gl-not-editable" data-testid="gl-not-editable">template, not editable by file</small>}
              {mark && <small className="gl-custom" title="This composition has an existing custom-layout file (customlayout.list / journal)">custom</small>}
              <small className="dim">{cells} cells</small>
            </span>
          </li>
        })}
      </ul>
      <button type="button" className="gl-section" data-testid="gl-hierarchy-toggle" aria-expanded={hierarchyOpen}
        onClick={() => setHierarchyOpen((v) => !v)}>{hierarchyOpen ? '▾' : '▸'} Hierarchy</button>
      {hierarchyOpen && <div className="gl-section-body" data-testid="gl-hierarchy">
        {!activeComposition && <div className="small dim">Open a composition to see its tile hierarchy.</div>}
        {activeComposition && !activeCells.length && <div className="small dim">No tiles listed for {activeComposition}.</div>}
        {activeCells.map((c) => <button type="button" key={c.cell_index} className={'gl-tile' + (shownSelection?.cell_index === c.cell_index ? ' on' : '')}
          data-testid="gl-hierarchy-tile" title={c.element_id}
          onClick={() => onSelectTile({ key: `hierarchy:${c.cell_index}`, cell_index: c.cell_index, element_id: c.element_id, x: c.x, y: c.y, w: c.w, h: c.h })}>
          <span className="mono small">{c.element_id}</span><small className="dim">cell {c.cell_index}</small>
        </button>)}
      </div>}
      <button type="button" className="gl-section" data-testid="gl-element-toggle" aria-expanded={elementOpen}
        onClick={() => setElementOpen((v) => !v)}>{elementOpen ? '▾' : '▸'} Element</button>
      {elementOpen && <div className="gl-section-body" data-testid="gl-element">
        {!shownSelection && <div className="small dim">No tile selected in Game Layouts.</div>}
        {shownSelection && <>
          <div className="small mono" data-testid="gl-element-id">{shownSelection.element_id}</div>
          <div className="small dim">cell {shownSelection.cell_index} · width {shownSelection.w} · height {shownSelection.h}</div>
        </>}
      </div>}
    </div>
  )
}
