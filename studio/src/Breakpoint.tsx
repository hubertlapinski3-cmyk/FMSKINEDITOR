// UI1 step 2: the preview's breakpoint selector. "auto from resolution" runs the same comparator the game's
// GridLayoutSettings asset uses (REA-WIN-2 §W3 / REA-WIN-1), so at 2560x1440 it yields breakpoint 3 = Large.
//
// The numeric table is game-derived, not fitted: globalobjects_assets_all.bundle ::
// GridLayoutSettings.m_gridBreakpointWidthData, path id 7732983250881643699, in serialized order. The comparator
// scores the FullscreenGridSize fields (record +0x20/+0x24), NOT referenceWidth/referenceHeight: only that
// reading reproduces the empirical table (2560x1440->3, 1920x1080->3, 1440x900->2, 1024x768->1).

export interface BreakpointRecord {
  breakpoint: number
  label: string
  referenceWidth: number
  referenceHeight: number
  fullscreenGrid: [number, number]
}

export const BREAKPOINT_TABLE: BreakpointRecord[] = [
  { breakpoint: 1, label: 'Small', referenceWidth: 1024, referenceHeight: 768, fullscreenGrid: [12, 8] },
  { breakpoint: 2, label: 'Standard', referenceWidth: 1366, referenceHeight: 768, fullscreenGrid: [16, 9] },
  { breakpoint: 3, label: 'Large', referenceWidth: 1680, referenceHeight: 945, fullscreenGrid: [20, 11] },
  { breakpoint: 0, label: 'All breakpoints', referenceWidth: 1680, referenceHeight: 945, fullscreenGrid: [20, 11] },
  { breakpoint: 5, label: 'Small (alternate)', referenceWidth: 1024, referenceHeight: 512, fullscreenGrid: [12, 8] },
]

// m_cellSize=(66,66), m_padding=(12,12), m_spacing=(16,16) => one grid unit is 66+16 = 82 px.
const GRID_UNIT = 82
const EDGE = 8
export const normWidth = (width: number) => (width - EDGE) / GRID_UNIT
export const normHeight = (height: number) => (height - EDGE) / GRID_UNIT

/** The game's comparator: highest scoring fitting record wins (ties keep serialized order). When nothing fits,
 *  the product of the two shortfalls decides. Exported so the Studio can show the same result as the asset. */
export function breakpointForResolution(width: number, height: number): number {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return 1
  const nw = normWidth(width), nh = normHeight(height)
  const fitting = BREAKPOINT_TABLE.map((r) => ({ r, score: r.fullscreenGrid[0] * r.fullscreenGrid[1] }))
    .filter((x) => x.r.fullscreenGrid[0] <= nw && x.r.fullscreenGrid[1] <= nh)
  if (fitting.length) {
    let best = fitting[0]
    for (const x of fitting) if (x.score > best.score) best = x   // strict: ties keep serialized order
    return best.r.breakpoint
  }
  let best = BREAKPOINT_TABLE[0]
  let bestScore = -1
  for (const r of BREAKPOINT_TABLE) {
    const shortW = Math.max(0, r.fullscreenGrid[0] - nw)
    const shortH = Math.max(0, r.fullscreenGrid[1] - nh)
    const score = shortW * shortH
    if (score > bestScore) { bestScore = score; best = r }
  }
  return best.breakpoint
}

export const breakpointName = (bp: number): string =>
  BREAKPOINT_TABLE.find((r) => r.breakpoint === bp)?.label ?? String(bp)

/** The composition file that is edited at a breakpoint: SquadComposition -> SquadComposition-Large. */
export function compositionForBreakpoint(composition: string | undefined | null, bp: number): string {
  const base = (composition || 'Composition').replace(/-(Small|Standard|Large)$/, '')
  return `${base}-${breakpointName(bp).split(' ')[0] || 'Large'}`
}

export type Confidence = 'measured' | 'measured mismatch' | 'computed' | 'unverified'

export const VIEWPORT_FULLSCREEN = '2560x1440 fullscreen, Small, Larger'
export const VIEWPORT_FULLSCREEN_MEDIUM = '2560x1440 fullscreen, Medium, Larger'
export const VIEWPORT_FULLSCREEN_LARGE = '2560x1440 fullscreen, Large, Larger'
export const VIEWPORT_WINDOWED = '2560x1440 windowed, Small, Larger'
export const VIEWPORT_PROFILES = [VIEWPORT_FULLSCREEN, VIEWPORT_FULLSCREEN_MEDIUM, VIEWPORT_FULLSCREEN_LARGE, VIEWPORT_WINDOWED] as const

/** Consumes the confidence label the backend supplies additively (either `{ label: 'measured', ... }`
 *  from `preview.confidence_for` or a plain string); falls back to the existing MEASURED/ESTIMATE
 *  selection evidence. */
export function confidenceLabel(
  p: { label?: string; confidence?: string | { label?: string }; selection?: { evidence?: string } } | string | null | undefined
): Confidence {
  const c = typeof p === 'string'
    ? p
    : typeof p?.confidence === 'string'
      ? p.confidence
      : p?.confidence?.label ?? p?.label ?? p?.selection?.evidence ?? ''
  const raw = String(c).toLowerCase()
  if (raw.includes('mismatch')) return 'measured mismatch'
  if (raw.includes('measured')) return 'measured'
  if (raw.includes('computed') || raw.includes('estimate')) return 'computed'
  if (raw.includes('unverified')) return 'unverified'
  return 'unverified'
}

export interface BreakpointSelectorProps {
  width: number; height: number
  mode: string; onModeChange: (mode: string) => void
  composition?: string | null
  confidence?: { label?: string; confidence?: string | { label?: string }; selection?: { evidence?: string } } | null
}

/** The selector itself, kept separate so it can be tested without mounting the whole Playground. */
export default function BreakpointSelector({ width, height, mode, onModeChange, composition, confidence }: BreakpointSelectorProps) {
  const auto = breakpointForResolution(width, height)
  const effective = mode === 'auto' ? auto : Number(mode)
  const confidenceValue = confidenceLabel(confidence)
  return (
    <div className="breakpoint-selector" data-testid="pg-preview-breakpoint-control">
      <label className="small">breakpoint{' '}
        <select data-testid="pg-preview-breakpoint" value={mode} onChange={(e) => onModeChange(e.target.value)}>
          <option value="auto">auto from resolution</option>
          <option value="1">Small</option>
          <option value="2">Standard</option>
          <option value="3">Large</option>
        </select>
      </label>
      <div className="small mono" data-testid="pg-preview-breakpoint-value" data-breakpoint={effective}>
        breakpoint {effective} = {breakpointName(effective)}{mode === 'auto' ? ` (auto from ${width}x${height})` : ' (chosen)'}
      </div>
      <div className="small" data-testid="pg-preview-composition-file" data-composition={compositionForBreakpoint(composition, effective)}>
        editing composition file <b>{compositionForBreakpoint(composition, effective)}</b>
      </div>
      <div className="small" data-testid="pg-preview-confidence" data-confidence={confidenceValue}>
        preview confidence: <b>{confidenceValue}</b>
      </div>
    </div>
  )
}
