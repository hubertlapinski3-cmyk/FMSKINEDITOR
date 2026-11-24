// UI4: one coordinate system for editing. The left pane edits the file's OWN numbers
// (main cells in design space, each optional-slice zone in its own slot space). The
// right pane shows the rea runtime result at 2560x1440, live after every drag, and
// marks a tile the game moves away from where it was dropped. Nothing here writes a
// game file: Apply and Rollback go through customlayout.* in engine.ts.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { customlayout, isApplyRefusal, RpcError, rpc } from './engine'
import BreakpointSelector, { breakpointForResolution, breakpointName, confidenceLabel } from './Breakpoint'

interface SpaceTile {
  key: string
  space: string            // 'main' | 'm_right' | 'm_bottom' | ...
  order: number
  element_id: string
  x: number; y: number; w: number; h: number
  minW: number; minH: number; maxW: number; maxH: number
}
interface Props {
  project: string | null
  composition: string
  profile?: string
  tileRev?: number
  expSlotEdits?: boolean
  onProfileChange?: (profile: string) => void
  onSelect: (tile: any) => void
  say: (s: string) => void
}

const DEFAULT_PROFILE = '2560x1440 fullscreen, Small, Larger'
const MEDIUM_PROFILE = '2560x1440 fullscreen, Medium, Larger'
const LARGE_PROFILE = '2560x1440 fullscreen, Large, Larger'
const WINDOWED_PROFILE = '2560x1440 windowed, Small, Larger'
const PROFILES = [DEFAULT_PROFILE, MEDIUM_PROFILE, LARGE_PROFILE, WINDOWED_PROFILE] as const

const UNIT = 64
const MAIN = 'main'
const ZONE_LABEL: Record<string, string> = {
  m_right: 'RIGHT ZONE',
  m_bottom: 'BOTTOM ZONE',
  m_left: 'LEFT ZONE',
  m_top: 'TOP ZONE',
  m_topLeft: 'TOP-LEFT ZONE',
  m_topRight: 'TOP-RIGHT ZONE',
  m_bottomLeft: 'BOTTOM-LEFT ZONE',
  m_bottomRight: 'BOTTOM-RIGHT ZONE',
}

interface RuntimeCell { element_id: string; x: number; y: number; w: number; h: number; reason?: string }

const spaceTile = (c: any): SpaceTile => ({
  key: `${c.space}:${c.order}`, space: c.space, order: c.order, element_id: c.element_id,
  x: Number(c.x), y: Number(c.y), w: Number(c.width), h: Number(c.height),
  minW: Number(c.min_w ?? 1), minH: Number(c.min_h ?? 1), maxW: Number(c.max_w ?? 0), maxH: Number(c.max_h ?? 0),
})

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

const writeObject = (base: any, cells: SpaceTile[]) => {
  const o = JSON.parse(JSON.stringify(base))
  for (const t of cells.filter((c) => c.space === MAIN)) {
    const arr = o.m_gridComponents
    const c = arr && arr[t.order]
    if (c) {
      if (c.m_elementID !== t.element_id) {
        c.m_elementID = t.element_id
        c.m_configDescriptionKeys = [t.element_id]
      }
      c.m_location = { ...(c.m_location || {}), x: t.x, y: t.y, width: t.w, height: t.h }
      c.m_minSize = { x: Math.min(c.m_minSize?.x ?? t.w, t.w), y: Math.min(c.m_minSize?.y ?? t.h, t.h) }
      c.m_maxSize = { x: Math.max(c.m_maxSize?.x ?? t.w, t.w), y: Math.max(c.m_maxSize?.y ?? t.h, t.h) }
    }
  }
  if (o.m_optionalSlices && Array.isArray(o.m_optionalSlices.m_bottom)) {
    const origById = new Map<string, any>()
    for (const s of o.m_optionalSlices.m_bottom) if (s?.m_elementID) origById.set(String(s.m_elementID), s)
    const bot = cells.filter((c) => c.space === 'm_bottom')
    o.m_optionalSlices.m_bottom = bot.map((t) => {
      const prev = origById.get(t.element_id)
      if (prev) return { ...prev, m_location: { ...(prev.m_location || {}), x: t.x, y: t.y, width: t.w, height: t.h } }
      return {
        m_elementID: t.element_id,
        m_configDescriptions: [{ instanceID: 0 }],
        m_configDescriptionKeys: [t.element_id],
        m_gridElementConfigs: [],
        m_location: { x: t.x, y: t.y, width: t.w, height: t.h },
        m_minSize: { x: t.w, y: t.h },
        m_maxSize: { x: t.w, y: t.h },
        m_isLocked: false, m_isDebug: false, m_isDynamic: false, m_features: 0,
        m_expandToContent: false, m_takesFocus: false, m_isOptional: true,
        m_horizontalAlignment: 0, m_verticalAlignment: 0,
      }
    })
  }
  for (const t of cells.filter((c) => c.space !== MAIN && c.space !== 'm_bottom')) {
    const arr = (o.m_optionalSlices || {})[t.space]
    const c = arr && arr[t.order]
    if (c) c.m_location = { ...(c.m_location || {}), x: t.x, y: t.y, width: t.w, height: t.h }
  }
  return o
}

export default function LayoutCanvas({ project, composition, profile, tileRev, expSlotEdits = false, onProfileChange, onSelect, say }: Props) {
  const [localProfile, setLocalProfile] = useState<string>(DEFAULT_PROFILE)
  const activeProfile = profile ?? localProfile
  const setProfile = (next: string) => {
    setLocalProfile(next)
    onProfileChange?.(next)
  }
  const [base, setBase] = useState<any>(null)
  const [baseSource, setBaseSource] = useState<'game_folder' | 'bundle'>('bundle')
  const [baseConfidence, setBaseConfidence] = useState<any>(null)
  const [design, setDesign] = useState<{ cols: number; rows: number }>({ cols: 20, rows: 10 })
  const [cells, setCells] = useState<SpaceTile[]>([])
  const [baseCells, setBaseCells] = useState<Record<string, SpaceTile>>({})
  const [bundleCells, setBundleCells] = useState<SpaceTile[]>([])
  const [compareBundle, setCompareBundle] = useState(false)
  const [runtime, setRuntime] = useState<any>(null)
  const [runtimeKey, setRuntimeKey] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [lastTx, setLastTx] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [err, setErr] = useState('')
  const [applyBreakpoints, setApplyBreakpoints] = useState(false)
  const [conflict, setConflict] = useState<{ tx: string; files: { name: string; now_sha256: string | null }[] } | null>(null)
  const [zoom, setZoom] = useState(100)
  const [pane, setPane] = useState<'design' | 'runtime'>('design')
  const [bpMode, setBpMode] = useState('auto')
  const [tileSet, setTileSet] = useState<{ tiles: { id: string; sizes: [number, number][]; added_by_project?: boolean }[] } | null>(null)
  const [swapTile, setSwapTile] = useState('')
  const [swapSize, setSwapSize] = useState('')
  const drag = useRef<{ key: string; mode: 'move' | 'resize'; sx: number; sy: number; tile: SpaceTile } | null>(null)
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const currentKey = useMemo(() => (base ? `${activeProfile}|${JSON.stringify(writeObject(base, cells))}` : ''), [base, cells, activeProfile])
  const runtimeFresh = !!runtime && runtimeKey === currentKey

  const sentRef = useRef<{ key: string; id: number }>({ key: '', id: 0 })
  const loadRuntime = useCallback((obj: any) => {
    const key = `${activeProfile}|${JSON.stringify(obj)}`
    if (sentRef.current.key === key) return
    const id = sentRef.current.id + 1
    sentRef.current = { key, id }
    ;(async () => {
      let p: any = null
      if (typeof (customlayout as any).runtime === 'function') {
        p = await (customlayout as any).runtime(composition, obj, undefined, project, activeProfile)
      }
      if (!p) {
        p = await rpc('customlayout.runtime', { composition, object: obj, project: project || undefined, profile: activeProfile })
      }
      if (!p) {
        p = await rpc('render.preview', {
          screen: composition, width: 2560, height: 1440, setting: 'Large UI', states: [], seed: 'preview',
          project, simulated_visible: true, game_states: {},
          custom_layouts: { [composition]: obj },
        })
      }
      if (sentRef.current.id === id) {
        setRuntime(p)
        setRuntimeKey(key)
      }
    })().catch((e) => {
      console.warn('runtime preview failed', e)
      if (sentRef.current.id === id) {
        setRuntime(null)
        setRuntimeKey('')
      }
    })
  }, [composition, project, activeProfile])

  const loadBase = useCallback(async (resetHistory = false) => {
    sentRef.current = { key: '', id: sentRef.current.id + 1 }
    if (resetHistory) {
      setBase(null); setBaseSource('bundle'); setBaseConfidence(null); setCells([]); setBaseCells({}); setBundleCells([]); setCompareBundle(false)
      setSelected(null); setErr(''); setLastTx(''); setHistory([]); setRuntime(null); setRuntimeKey('')
    }
    const r: any = await customlayout.base(composition, activeProfile)
    const ts = (r.cells || []).map(spaceTile)
    const by: Record<string, SpaceTile> = {}
    ts.forEach((t: SpaceTile) => { by[t.key] = t })
    setBase(r.object)
    setBaseSource(r.source === 'game_folder' ? 'game_folder' : 'bundle')
    setBaseConfidence(r.confidence ?? null)
    if (r.design?.cols && r.design?.rows) setDesign({ cols: Number(r.design.cols), rows: Number(r.design.rows) })
    setCells(ts); setBaseCells(by)
    setBundleCells((r.bundle_cells || []).map(spaceTile))
    if (r.source !== 'game_folder') setCompareBundle(false)
    if (r.last_tx) setLastTx(String(r.last_tx))
    else if (r.source !== 'game_folder') setLastTx('')
    if (r.object) loadRuntime(writeObject(r.object, ts))
    return r
  }, [composition, activeProfile, loadRuntime])

  useEffect(() => {
    let live = true
    loadBase(true).catch((e) => { if (live) setErr(e instanceof RpcError ? e.message : String(e)) })
    return () => { live = false }
  }, [composition, project, loadBase])

  useEffect(() => {
    setSwapTile('')
    setSwapSize('')
  }, [selected])

  useEffect(() => {
    let live = true
    rpc<any>('playground.tile_set', { composition, ...(project ? { project } : {}) })
      .then((r) => {
        if (!live || !r || !Array.isArray(r.tiles)) return
        const sorted = [...r.tiles].sort(
          (a: any, b: any) => Number(!!b.added_by_project) - Number(!!a.added_by_project) || String(a.id).localeCompare(String(b.id))
        )
        setTileSet({ ...r, tiles: sorted })
      })
      .catch(() => { if (live) setTileSet(null) })
    return () => { live = false }
  }, [composition, project, selected, tileRev])

  // live runtime after every staged edit
  useEffect(() => {
    if (!base) return
    loadRuntime(writeObject(base, cells))
  }, [base, cells, loadRuntime])

  const runtimeCells = useMemo<RuntimeCell[]>(() => {
    const raw: any[] = runtime?.hosts || [...(runtime?.cells || []), ...(runtime?.slots || [])]
    return raw.map((item: any) => {
      const h = item?.host || item
      if (!h) return null
      return {
        element_id: String(h.element_id ?? item?.element_id),
        x: Number(h.geometry?.x ?? item?.x),
        y: Number(h.geometry?.y ?? item?.y),
        w: Number(h.geometry?.w ?? item?.w),
        h: Number(h.geometry?.h ?? item?.h),
        reason: typeof item?.reason === 'string' ? item.reason : undefined,
      }
    }).filter(Boolean) as RuntimeCell[]
  }, [runtime])
  const rcols = Number(runtime?.grid?.cols) || 30
  const rrows = Number(runtime?.grid?.rows) || 16
  const surplus = Math.max(0, rcols - design.cols)

  const expected = (t: SpaceTile) => {
    if (t.space !== MAIN) return { x: zoneRuntimeBase(t.space).x + t.x, y: zoneRuntimeBase(t.space).y + t.y }
    // only a cell anchored to the design right strip shifts with the growth surplus;
    // cells that grow (FirstTeamOverview, the top bar) keep their design x.
    const strip = t.x + t.w >= design.cols
    return { x: t.x + (strip ? surplus : 0), y: t.y }
  }
  const actual = (t: SpaceTile) => (runtimeFresh ? runtimeCells.find((r) => r.element_id === t.element_id) : undefined)
  const reason = (t: SpaceTile) => {
    const a = actual(t); if (!a) return ''
    if (a.reason) return a.reason
    const e = expected(t)
    if (a.y < e.y) return `compacted up to row ${a.y}`
    if (a.x !== e.x) return `placed at column ${a.x} (runtime strip)`
    if (a.y !== e.y) return `placed at row ${a.y}`
    return ''
  }
  const moved = (t: SpaceTile) => !!reason(t)

  function zoneRuntimeBase(space: string) {
    const dw = design.cols, dh = design.rows
    if (space === 'm_right') return { x: dw, y: 0 }
    if (space === 'm_bottom') return { x: surplus, y: dh }
    if (space === 'm_top') return { x: surplus, y: 0 }
    if (space === 'm_topRight') return { x: dw, y: 0 }
    if (space === 'm_bottomLeft') return { x: 0, y: dh }
    if (space === 'm_bottomRight') return { x: dw, y: dh }
    return { x: 0, y: 0 }
  }

  const main = cells.filter((t) => t.space === MAIN)
  const zones = useMemo(() => {
    const z: Record<string, SpaceTile[]> = {}
    for (const t of cells) if (t.space !== MAIN) (z[t.space] ||= []).push(t)
    return z
  }, [cells])

  const overlaps = (list: SpaceTile[]) => {
    const out: { a: string; b: string }[] = []
    for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
      const a = list[i], b = list[j]
      if (a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h) continue
      if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) out.push({ a: a.element_id, b: b.element_id })
    }
    return out
  }
  const spaceOverlaps = useMemo(() => {
    const out: string[] = []
    for (const o of overlaps(main)) out.push(`design: ${o.a} / ${o.b}`)
    for (const [zone, list] of Object.entries(zones)) for (const o of overlaps(list)) out.push(`${zone}: ${o.a} / ${o.b}`)
    return out
  }, [main, zones])
  const runtimeProblems = useMemo(() => {
    if (!runtimeFresh) return []
    const out: string[] = []
    for (const r of runtimeCells) {
      if (r.x < 0 || r.y < 0 || r.x + r.w > rcols || r.y + r.h > rrows) out.push(`${r.element_id} outside the runtime grid`)
    }
    const list = runtimeCells.map((r) => ({ element_id: r.element_id, x: r.x, y: r.y, w: r.w, h: r.h, minW: 0, minH: 0, maxW: 0, maxH: 0 }))
    for (const o of overlaps(list as any)) out.push(`runtime: ${o.a} / ${o.b}`)
    return out
  }, [runtimeFresh, runtimeCells, rcols, rrows])

  const legal = (t: SpaceTile): SpaceTile => {
    const maxW = t.maxW > 0 ? t.maxW : 40, maxH = t.maxH > 0 ? t.maxH : 40
    const w = clamp(t.w, t.minW, maxW), h = clamp(t.h, t.minH, maxH)
    const [cols, rows] = t.space === MAIN ? [design.cols, design.rows] : [design.cols, Math.max(design.rows, 24)]
    return { ...t, w, h, x: clamp(t.x, 0, Math.max(0, cols - w)), y: clamp(t.y, 0, Math.max(0, rows - h)) }
  }

  const stage = (t: SpaceTile, what: string) => {
    setCells((cs) => cs.map((x) => (x.key === t.key ? t : x)))
    setSelected(t.key)
    onSelect({ key: t.key, cell_index: t.order, element_id: t.element_id, x: t.x, y: t.y, w: t.w, h: t.h })
    const b = baseCells[t.key]
    if (b && (b.x !== t.x || b.y !== t.y || b.w !== t.w || b.h !== t.h || b.element_id !== t.element_id)) {
      setHistory((h) => [`${composition}: ${t.space} ${t.element_id} ${what}`, ...h.filter((x) => !x.includes(`${t.space} ${t.element_id} `))].slice(0, 24))
    }
  }

  const setField = (t: SpaceTile, field: 'x' | 'y' | 'w' | 'h', raw: number) => {
    const v = Math.max(field === 'w' || field === 'h' ? 1 : 0, Math.round(raw) || 0)
    const next = legal({ ...t, [field]: v })
    stage(next, `${field} ${t[field]}→${next[field]} (staged)`)
  }

  /** BND2: slot-reorder, slot-add, and slot-remove all confirmed Empirical on m_bottom. */
  const reorderBottomSlot = (tile: SpaceTile, dir: -1 | 1) => {
    const siblings = cells.filter((t) => t.space === 'm_bottom').sort((a, b) => a.y - b.y || a.order - b.order)
    const idx = siblings.findIndex((t) => t.key === tile.key)
    const swapIdx = idx + dir
    if (idx < 0 || swapIdx < 0 || swapIdx >= siblings.length) return
    const a = siblings[idx]
    const b = siblings[swapIdx]
    const ay = a.y
    const by = b.y
    setCells((cs) => cs.map((t) => t.key === a.key ? { ...t, y: by } : t.key === b.key ? { ...t, y: ay } : t))
  }

  const addBottomSlot = () => {
    const raw = window.prompt('Tile element ID to add to bottom slots (e.g. Happiness):', 'Happiness')
    const eid = (raw || '').trim()
    if (!eid) return
    if (cells.some((t) => t.space === 'm_bottom' && t.element_id === eid)) {
      setErr(`${eid} is already in m_bottom`)
      return
    }
    const siblings = cells.filter((t) => t.space === 'm_bottom')
    const nextY = siblings.reduce((mx, s) => Math.max(mx, s.y + s.h), 0)
    const nextX = siblings[0]?.x ?? Math.max(0, design.cols - 4)
    const nt: SpaceTile = {
      key: `m_bottom:add:${eid}:${Date.now()}`,
      space: 'm_bottom',
      order: siblings.length,
      element_id: eid,
      x: nextX, y: nextY, w: 4, h: 2,
      minW: 4, minH: 2, maxW: 4, maxH: 2,
    }
    setCells((cs) => [...cs, nt])
    setSelected(nt.key)
    setHistory((h) => [`${composition}: m_bottom +${eid} at y=${nextY} (staged)`, ...h].slice(0, 24))
  }

  const removeBottomSlot = (tile: SpaceTile) => {
    if (tile.space !== 'm_bottom') return
    setCells((cs) => cs.filter((t) => t.key !== tile.key))
    setSelected('')
    setHistory((h) => [`${composition}: m_bottom -${tile.element_id} (staged)`, ...h].slice(0, 24))
  }

  const onDown = (e: React.PointerEvent, t: SpaceTile, mode: 'move' | 'resize' = 'move') => {
    e.preventDefault(); e.stopPropagation()
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    drag.current = { key: t.key, mode, sx: e.clientX, sy: e.clientY, tile: { ...t } }
    setSelected(t.key); onSelect({ key: t.key, cell_index: t.order, element_id: t.element_id, x: t.x, y: t.y, w: t.w, h: t.h })
  }
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current; if (!d) return
    const step = Math.max(1, UNIT * zoom / 100)
    const dx = Math.round((e.clientX - d.sx) / step), dy = Math.round((e.clientY - d.sy) / step)
    if (d.mode === 'resize') {
      const next = legal({ ...d.tile, w: d.tile.w + dx, h: d.tile.h + dy })
      stage(next, `w/h ${d.tile.w},${d.tile.h}→${next.w},${next.h} (staged)`)
    } else {
      const next = legal({ ...d.tile, x: d.tile.x + dx, y: d.tile.y + dy })
      stage(next, `x/y ${d.tile.x},${d.tile.y}→${next.x},${next.y} (staged)`)
    }
  }
  const onUp = (e: React.PointerEvent) => {
    if (drag.current) {
      try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId) } catch { /* gone */ }
      const d = drag.current
      say(`layout drag: ${d.tile.space} ${d.tile.element_id} moved`)
    }
    drag.current = null
  }

  const edits = useMemo(() => {
    const out: Array<{ space: string; order: number; element_id: string; new_element_id?: string; x: number; y: number; w: number; h: number; op?: 'add' | 'remove' | 'swap' }> = []
    for (const t of cells) {
      const b = baseCells[t.key]
      if (!b) out.push({ space: t.space, order: t.order, element_id: t.element_id, x: t.x, y: t.y, w: t.w, h: t.h, op: 'add' })
      else if (b.element_id !== t.element_id) out.push({ space: t.space, order: t.order, element_id: b.element_id, new_element_id: t.element_id, x: t.x, y: t.y, w: t.w, h: t.h, op: 'swap' })
      else if (b.x !== t.x || b.y !== t.y || b.w !== t.w || b.h !== t.h) out.push({ space: t.space, order: t.order, element_id: t.element_id, x: t.x, y: t.y, w: t.w, h: t.h })
    }
    for (const b of Object.values(baseCells)) {
      if (!cells.some((t) => t.key === b.key)) out.push({ space: b.space, order: b.order, element_id: b.element_id, x: b.x, y: b.y, w: b.w, h: b.h, op: 'remove' })
    }
    return out
  }, [cells, baseCells])

  const apply = async () => {
    if (!project || busy || !edits.length || spaceOverlaps.length || runtimeProblems.length) return
    setBusy(true); setErr('')
    try {
      const payload = edits
      let r = applyBreakpoints
        ? await customlayout.apply_edits(project, composition, payload, [], { cols: rcols, rows: rrows }, true)
        : await customlayout.apply_edits(project, composition, payload, [], { cols: rcols, rows: rrows })
      if (isApplyRefusal(r) && (r as any).required_confirmations?.length) {
        const need = (r as any).required_confirmations as string[]
        if (!confirm(`Apply will replace ${need.join(', ')}. Every file is backed up first and Rollback restores it byte for byte. Continue?`)) return
        r = applyBreakpoints
          ? await customlayout.apply_edits(project, composition, payload, need, { cols: rcols, rows: rrows }, true)
          : await customlayout.apply_edits(project, composition, payload, need, { cols: rcols, rows: rrows })
      }
      if (isApplyRefusal(r)) { setErr(r.refused); say('layout apply refused: ' + r.refused); return }
      setLastTx((r as any).tx_id)
      const skipped = ((r as any).breakpoint_skipped as { composition: string; reason: string }[] | undefined) ?? []
      const skipNote = skipped.length ? `; skipped: ${skipped.map((s) => `${s.composition} (${s.reason})`).join(', ')}` : ''
      say(`layout applied: ${(r as any).tx_id} (${(r as any).state})${skipNote}`)
      setHistory((h) => [`${composition}: applied ${(r as any).tx_id}${skipNote}`, ...h].slice(0, 24))
      setBaseSource('game_folder')
      setBase(writeObject(base, cells))
      setBaseCells(Object.fromEntries(cells.map((t) => [t.key, t])))
      try { await loadBase(false); setLastTx((r as any).tx_id) } catch { /* keep applied state if reload unavailable */ }
    } catch (e) {
      const m = e instanceof RpcError ? e.message : String(e)
      setErr(m); say('ERROR ' + m)
    } finally { setBusy(false) }
  }

  const rollback = async () => {
    if (!lastTx || busy) return
    if (!confirm(`Roll back layout transaction ${lastTx}?`)) return
    setBusy(true); setErr(''); setConflict(null)
    try {
      const r = await customlayout.rollback(lastTx)
      if (r.state === 'rollback_failed' && r.rollback?.conflicts?.length) {
        setConflict({ tx: lastTx, files: (r.rollback.changed ?? []).map((c) => ({ name: c.name, now_sha256: c.now_sha256 })) })
        say(`rollback refused: ${r.rollback.conflicts.join(', ')} changed since Apply — choose Restore to before Apply`)
        return
      }
      say(`layout rolled back: ${lastTx} (${r.state}, exact: ${String(r.rollback?.exact)})`)
      setHistory((h) => [`${composition}: rolled back ${lastTx}`, ...h].slice(0, 24))
      try { await loadBase(false) } catch { /* ignore reload errors in mocks */ }
    } catch (e) {
      const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m)
    } finally { setBusy(false) }
  }

  const restoreBefore = async () => {
    if (!conflict || busy) return
    if (!confirm(`Restore ${conflict.files.map((f) => f.name).join(', ')} to the state before Apply?`)) return
    setBusy(true); setErr('')
    try {
      const r = await customlayout.restore_before(conflict.tx, true)
      say(`restored to before Apply: ${r.tx_id} (${r.state})`)
      setHistory((h) => [`${composition}: restored to before Apply ${r.tx_id}`, ...h].slice(0, 24))
      setConflict(null)
      try { await loadBase(false) } catch { /* ignore reload errors in mocks */ }
    } catch (e) {
      const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m)
    } finally { setBusy(false) }
  }

  const step = UNIT * zoom / 100
  const sel = cells.find((t) => t.key === selected) ?? null
  const zoneRowsFor = (list: SpaceTile[]) => Math.max(design.rows, ...list.map((t) => t.y + t.h), 1) + 1
  const fit = () => {
    const el = wrapRef.current
    if (!el) return
    const w = el.clientWidth || 0
    const h = el.clientHeight || 0
    if (!w) return
    if (pane === 'runtime') {
      const sx = (w - 48) / (Math.max(rcols, 20) * UNIT)
      const sy = h > 0 ? (h - 48) / (Math.max(rrows, 10) * UNIT) : sx
      setZoom(clamp(Math.round(Math.min(sx, sy) * 100), 25, 150))
      return
    }
    const zoneList = Object.values(zones)
    const totalRows = design.rows + zoneList.reduce((acc, list) => acc + zoneRowsFor(list), 0)
    const chromeH = 84 + zoneList.length * 68
    const sx = (w - 56) / (Math.max(design.cols, 20) * UNIT)
    const sy = h > chromeH ? (h - chromeH) / (Math.max(totalRows, 10) * UNIT) : sx
    setZoom(clamp(Math.floor(Math.min(sx, sy) * 100), 25, 150))
  }

  const tile = (t: SpaceTile) => {
    const tw = Math.max(28, t.w * step - 8)
    const th = Math.max(24, t.h * step - 8)
    const compact = th < 38
    return (
      <div key={t.key} className={'layout-tile' + (compact ? ' compact' : '') + (selected === t.key ? ' on' : '') + (moved(t) ? ' moved' : '')}
        data-testid="layout-tile" data-element={t.element_id} data-cell={t.order} data-space={t.space}
        title={`${t.element_id} (${t.space} · x${t.x} y${t.y} ${t.w}×${t.h})`}
        style={{ left: 12 + t.x * step, top: 12 + t.y * step, width: tw, height: th }}
        onClick={() => { setSelected(t.key); onSelect({ key: t.key, cell_index: t.order, element_id: t.element_id, x: t.x, y: t.y, w: t.w, h: t.h }) }}
        onPointerDown={(e) => onDown(e, t)} onPointerMove={onMove} onPointerUp={onUp}>
        <span className="tile-name mono small" title={t.element_id}>{t.element_id}</span>
        {(!compact || tw >= 160) && <small className="dim">x{t.x} y{t.y} · {t.w}×{t.h}</small>}
        <span className="resize-handle" data-testid="layout-resize" title="Drag to resize"
          onPointerDown={(e) => onDown(e, t, 'resize')} onPointerMove={onMove} onPointerUp={onUp} />
      </div>
    )
  }

  const ghostTile = (t: SpaceTile) => {
    const tw = Math.max(28, t.w * step - 8)
    const th = Math.max(24, t.h * step - 8)
    return (
      <div key={`ghost:${t.key}`} className={'layout-tile bundle-ghost' + (th < 38 ? ' compact' : '')}
        data-testid="layout-bundle-ghost" data-element={t.element_id} data-space={t.space}
        title={`stock bundle: ${t.element_id} · x${t.x} y${t.y} ${t.w}×${t.h}`}
        style={{ left: 12 + t.x * step, top: 12 + t.y * step, width: tw, height: th }}>
        <span className="tile-name mono small">stock: {t.element_id}</span>
      </div>
    )
  }

  const effectiveBp = bpMode === 'auto' ? breakpointForResolution(2560, 1440) : Number(bpMode)
  const effectiveBpLabel = breakpointName(effectiveBp)
  const confSource = runtime ?? (baseConfidence ? { confidence: baseConfidence } : base)
  const confValue = confidenceLabel(confSource)

  return (
    <div className="layouttab" data-testid="layout-canvas" data-composition={composition} data-runtime-fresh={runtimeFresh ? 'true' : 'false'} data-base-source={baseSource}>
      <div className="layouttab-top">
        <b>{composition}</b>
        <span className="layout-confidence" data-testid="layout-confidence" data-confidence={confValue}
          title={(confSource as any)?.confidence?.tooltip || (confSource as any)?.confidence?.reason || confValue}>
          preview confidence: <b>{confValue}</b>
        </span>
        <span className="small dim" data-testid="layout-viewport">
          viewport:{' '}
          <select className="gl-profile-select" data-testid="layout-viewport-profile" aria-label="Viewport profile"
            value={activeProfile} onChange={(e) => setProfile(e.target.value)}>
            {PROFILES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          {' · '}{activeProfile === WINDOWED_PROFILE ? '2560×1440 windowed' : '2560×1440 fullscreen'} · Small · Larger · breakpoint: <b>{effectiveBpLabel}</b>
        </span>
        <span className="small dim" data-testid="layout-engine">engine: rea · {baseSource === 'game_folder' ? 'custom file base' : 'bundle base'}</span>
        {baseSource === 'game_folder' && bundleCells.length > 0 && (
          <label className="small dim">
            <input type="checkbox" data-testid="layout-compare-bundle" checked={compareBundle} onChange={(e) => setCompareBundle(e.target.checked)} /> compare with bundle
          </label>
        )}
        <span className="small dim">view <button data-testid="layout-zoom-out" onClick={() => setZoom((z) => Math.max(25, z - 25))}>−</button> {zoom}% <button data-testid="layout-zoom-in" onClick={() => setZoom((z) => Math.min(150, z + 25))}>+</button> <button data-testid="layout-zoom-fit" onClick={fit}>Fit</button></span>
      </div>
      {err && <div className="warn pad small" role="alert" data-testid="layout-error">{err}</div>}
      <div className="layouttab-body">
        <div className="layouttab-main">
          <div className="layout-pane-tabs">
            <button className={pane === 'design' ? 'on' : ''} data-testid="pane-design" onClick={() => setPane('design')}>EDIT (file space)</button>
            <button className={pane === 'runtime' ? 'on' : ''} data-testid="pane-runtime" onClick={() => setPane('runtime')}>RUNTIME (game result)</button>
            <span className="small dim">design {design.cols}×{design.rows} → runtime {rcols}×{rrows}</span>
          </div>
          <div className="layout-bp-bar">
            <BreakpointSelector width={2560} height={1440} mode={bpMode} onModeChange={setBpMode}
              composition={composition} confidence={confSource} />
          </div>
          <div className="layout-canvas-wrap" ref={wrapRef}>
            {pane === 'runtime' ? (
              <div className="layout-canvas" data-testid="layout-runtime"
                style={{ width: Math.round(rcols * step + 24), height: Math.round(rrows * step + 24) }}>
                {runtimeCells.map((r: any) => {
                  const t = cells.find((c) => c.element_id === r.element_id)
                  const why = t ? reason(t) : ''
                  const rw = Math.max(24, r.w * step - 8)
                  const rh = Math.max(20, r.h * step - 8)
                  const compact = rh < 38
                  return <div key={r.element_id} className={'layout-tile runtime' + (compact ? ' compact' : '') + (why ? ' moved' : '')}
                    data-testid="layout-runtime-tile" data-element={r.element_id}
                    title={`${r.element_id} · runtime x${r.x} y${r.y} ${r.w}×${r.h}${why ? ' · ' + why : ''}`}
                    style={{ left: 12 + r.x * step, top: 12 + r.y * step, width: rw, height: rh }}>
                    <span className="tile-name mono small" title={r.element_id}>{r.element_id}</span>
                    {(!compact || rw >= 160) && <small className="dim">x{r.x} y{r.y} · {r.w}×{r.h}</small>}
                    {why && !compact && <small className="warn moved-why">{why}</small>}
                  </div>
                })}
                {!runtimeCells.length && <div className="dim small pad">No runtime result yet.</div>}
              </div>
            ) : (
              <div className="layout-design">
                <div className="layout-zone-label">MAIN GRID · design {design.cols}×{design.rows}</div>
                <div className="layout-canvas" data-testid="layout-tiles"
                  style={{ width: Math.round(design.cols * step + 24), height: Math.round(design.rows * step + 24) }}>
                  {compareBundle && bundleCells.filter((b) => b.space === MAIN).map(ghostTile)}
                  {main.map(tile)}
                  {!main.length && <div className="dim small pad">No tiles.</div>}
                </div>
                {Object.entries(zones).map(([zone, list]) => {
                  const rows = zoneRowsFor(list)
                  return <div key={zone} className="layout-zone">
                    <div className="layout-zone-label">{ZONE_LABEL[zone] || zone} · stored slot coords</div>
                    <div className="layout-canvas" data-testid={`layout-zone-${zone}`}
                      style={{ width: Math.round(design.cols * step + 24), height: Math.round(rows * step + 24) }}>
                      {compareBundle && bundleCells.filter((b) => b.space === zone).map(ghostTile)}
                      {list.map(tile)}
                    </div>
                  </div>
                })}
              </div>
            )}
          </div>
          <div className="layout-controls">
            <button type="button" className="primary" data-testid="layout-apply" disabled={!project || !edits.length || busy || spaceOverlaps.length > 0 || runtimeProblems.length > 0} onClick={apply}>
              {busy ? 'Working ...' : `Apply${edits.length ? ` (${edits.length})` : ''}`}
            </button>
            <button type="button" data-testid="layout-rollback" disabled={!lastTx || busy} onClick={rollback}>Rollback</button>
            {composition.endsWith('-Large') && (
              <label className="small" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <input type="checkbox" data-testid="layout-apply-breakpoints" checked={applyBreakpoints}
                  onChange={(e) => setApplyBreakpoints(e.target.checked)} />
                Apply to Standard &amp; Small
              </label>
            )}
            {spaceOverlaps.length > 0 && <span className="warn small" data-testid="layout-overlaps">Overlaps: {spaceOverlaps.join(', ')}. Move them apart.</span>}
            {runtimeProblems.length > 0 && <span className="warn small" data-testid="layout-runtime-problems">Runtime: {runtimeProblems.join(', ')}.</span>}
            {!spaceOverlaps.length && !runtimeProblems.length && <span className="small dim">{!project ? 'Open a project.' : !edits.length ? 'Drag a tile in its own pane; check RUNTIME before Apply.' : `${edits.length} staged edit(s).`}</span>}
          </div>
          {conflict && <div className="warn pad small" data-testid="layout-restore-before">
            Rollback refused: {conflict.files.map((f) => f.name).join(', ')} changed since Apply.
            <button type="button" data-testid="layout-restore-before-btn" disabled={busy} onClick={restoreBefore}>Restore to before Apply</button>
          </div>}
        </div>
        <aside className="layout-inspector" data-testid="layout-inspector">
          <div className="head">ELEMENT</div>
          {sel ? <>
            <div className="small mono" data-testid="layout-selected" data-element={sel.element_id}>{sel.space} · {sel.element_id}</div>
            <div className="layout-fields">
              {(['x', 'y', 'w', 'h'] as const).map((f) => <label key={f} className="small">{f}
                <input data-testid={`layout-${f}`} type="number" min={f === 'w' || f === 'h' ? 1 : 0} max={40} value={sel[f]}
                  onChange={(e) => setField(sel, f, Number(e.target.value))} />
              </label>)}
            </div>
            <div className="small dim">stored {sel.space}: x{sel.x} y{sel.y} {sel.w}×{sel.h}; runtime expected x{expected(sel).x} y{expected(sel).y}
              {runtimeFresh && actual(sel)
                ? <span data-testid="layout-last-rendered" data-fresh="true">, last rendered x{actual(sel)!.x} y{actual(sel)!.y}</span>
                : <span className="stale dim" data-testid="layout-last-rendered" data-fresh="false" style={{ opacity: 0.45 }}>, last rendered …</span>}</div>
            {reason(sel) && <div className="small warn" data-testid="layout-moved-reason">{reason(sel)}</div>}
            {sel.space === 'm_bottom' && (
              <div className="layout-slot-actions" data-testid="layout-slot-actions" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                {!expSlotEdits && <div className="small warn" data-testid="slot-edits-experimental-note" style={{ width: '100%' }}>
                  Slot editing is experimental (not confirmed in-game in v1.5): enable &apos;experimental: slot edits&apos; in BUILD to use it.
                </div>}
                <button type="button" data-testid="layout-slot-up" disabled={!expSlotEdits} onClick={() => reorderBottomSlot(sel, -1)}>Move slot up</button>
                <button type="button" data-testid="layout-slot-down" disabled={!expSlotEdits} onClick={() => reorderBottomSlot(sel, 1)}>Move slot down</button>
                <button type="button" data-testid="layout-slot-add" disabled={!expSlotEdits} onClick={addBottomSlot}>Add bottom slot</button>
                <button type="button" data-testid="layout-slot-remove" disabled={!expSlotEdits} onClick={() => removeBottomSlot(sel)}>Remove slot</button>
              </div>
            )}
            {sel.space === MAIN && tileSet && tileSet.tiles.length > 0 && (() => {
              const tid = swapTile || sel.element_id
              const tinfo = tileSet.tiles.find((t) => t.id === tid) || tileSet.tiles[0]
              const sizes = tinfo?.sizes || []
              const sameSize = sizes.some((s) => s[0] === sel.w && s[1] === sel.h) ? `${sel.w}x${sel.h}` : ''
              const curSize = swapSize && sizes.some((s) => `${s[0]}x${s[1]}` === swapSize)
                ? swapSize
                : (sameSize || (sizes[0] ? `${sizes[0][0]}x${sizes[0][1]}` : `${sel.w}x${sel.h}`))
              return (
                <div className="layout-swap-actions" data-testid="layout-swap-actions" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                  <select data-testid="layout-swap-tile" value={tinfo?.id || ''} onChange={(e) => { setSwapTile(e.target.value); setSwapSize('') }}>
                    {tileSet.tiles.map((t) => <option key={t.id} value={t.id}>{t.id}{t.added_by_project ? ' (added)' : ''}</option>)}
                  </select>
                  <select data-testid="layout-swap-size" value={curSize} onChange={(e) => setSwapSize(e.target.value)}>
                    {sizes.map((s) => <option key={`${s[0]}x${s[1]}`} value={`${s[0]}x${s[1]}`}>{s[0]}×{s[1]}</option>)}
                  </select>
                  <button type="button" data-testid="layout-swap-apply" onClick={() => {
                    const [nw, nh] = curSize.split('x').map(Number)
                    if (!tinfo || !nw || !nh) return
                    const updated: SpaceTile = {
                      ...sel,
                      element_id: tinfo.id,
                      w: nw, h: nh,
                      minW: Math.min(sel.minW, nw), minH: Math.min(sel.minH, nh),
                      maxW: Math.max(sel.maxW, nw), maxH: Math.max(sel.maxH, nh),
                    }
                    stage(updated, `swap/size ${sel.element_id}→${tinfo.id} ${nw}×${nh} (staged)`)
                  }}>Swap / Apply size</button>
                </div>
              )
            })()}
            <div className="small dim">Only Apply writes (layouttx + validate_before_write).</div>
          </> : <div className="small dim pad">Select a tile in either pane.</div>}
          <div className="layout-history" data-testid="layout-history">
            <b className="small">LAYOUT HISTORY</b>
            {!history.length && <div className="small dim">No layout edits yet.</div>}
            {history.map((h, i) => <div key={i} className="small mono">{h}</div>)}
          </div>
        </aside>
      </div>
    </div>
  )
}
