// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('./engine', () => ({
  rpc: vi.fn(), RpcError: class extends Error {}, isApplyRefusal: (r: any) => typeof r?.refused === 'string',
  customlayout: { preflight: vi.fn(async () => ({ required_confirmations: [] })), apply: vi.fn(), apply_edits: vi.fn(async () => ({ tx_id: 'tx', state: 'completed' })), rollback: vi.fn(), base: vi.fn() },
}))
vi.mock('./Breakpoint', () => ({
  default: () => <div data-testid="breakpoint-selector">bp</div>,
  breakpointForResolution: () => 3,
  breakpointName: (bp: number) => (bp === 3 ? 'Large' : bp === 2 ? 'Standard' : 'Small'),
  confidenceLabel: (p: any) => {
    const c = typeof p?.confidence === 'string' ? p.confidence : p?.confidence?.label ?? ''
    const low = String(c).toLowerCase()
    if (low.includes('mismatch')) return 'measured mismatch'
    if (low.includes('measured')) return 'measured'
    if (low.includes('computed')) return 'computed'
    return 'unverified'
  },
}))
import { rpc, customlayout } from './engine'
import LayoutCanvas from './LayoutCanvas'

const host = (x: number, y: number, w: number, h: number) => ({
  cell_index: 0, element_id: 'Atmosphere', geometry: { x, y, w, h }, flags: [],
})
const baseFor = (hosts: any[]) => ({
  object: { m_gridComponents: hosts.map((h) => ({ m_elementID: h.element_id, m_location: { x: h.geometry.x, y: h.geometry.y, width: h.geometry.w, height: h.geometry.h } })), m_optionalSlices: {} },
  cells: hosts.map((h, i) => ({ space: 'main', order: i, element_id: h.element_id, x: h.geometry.x, y: h.geometry.y,
    width: h.geometry.w, height: h.geometry.h, min_w: h.limits?.min_w ?? 1, min_h: h.limits?.min_h ?? 1,
    max_w: h.limits?.max_w ?? 0, max_h: h.limits?.max_h ?? 0 })),
  design: { cols: 30, rows: 16 }, source: 'bundle',
})
beforeEach(() => {
  const hosts = [host(16, 8, 4, 2), { ...host(0, 0, 16, 1), element_id: 'OverviewTitleBar' },
                 { ...host(16, 0, 4, 4), element_id: 'Tactics' }]
  ;(customlayout.base as any).mockResolvedValue(baseFor(hosts))
  ;(rpc as any).mockImplementation(async (m: string) => m === 'render.preview'
    ? { hosts, width: 1600, height: 900, grid: { cols: 20, rows: 10, layout_label: 'engine: rea' } }
    : null)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Game Layouts canvas drag, resize and zoom', () => {
  it('keeps every tile when one is selected (unique keys for hosts without distinct cell_index)', async () => {
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    const tiles = await screen.findAllByTestId('layout-tile')
    expect(tiles).toHaveLength(3)
    fireEvent.click(tiles[1])
    expect(screen.getAllByTestId('layout-tile')).toHaveLength(3)
    expect(screen.getByTestId('layout-selected').getAttribute('data-element')).toBe('OverviewTitleBar')
  })

  it('drags a tile to a new grid position and stages the edit', async () => {
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    const tile = (await screen.findAllByTestId('layout-tile'))[0]
    Object.defineProperty(tile, 'setPointerCapture', { value: vi.fn() })
    Object.defineProperty(tile, 'releasePointerCapture', { value: vi.fn() })
    fireEvent.pointerDown(tile, { clientX: 100, clientY: 100, pointerId: 1, currentTarget: tile })
    fireEvent.pointerMove(tile, { clientX: 182, clientY: 182, pointerId: 1, currentTarget: tile })
    fireEvent.pointerUp(tile, { pointerId: 1, currentTarget: tile })
    await waitFor(() => expect(screen.getByTestId('layout-apply').textContent).toContain('(1)'))
    expect(screen.getByTestId('layout-x').getAttribute('value')).toBe('17')
  })

  it('resizes with the corner handle and has zoom in, out and fit', async () => {
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    await screen.findAllByTestId('layout-tile')
    const handle = screen.getAllByTestId('layout-resize')[0]
    Object.defineProperty(handle, 'setPointerCapture', { value: vi.fn() })
    Object.defineProperty(handle, 'releasePointerCapture', { value: vi.fn() })
    fireEvent.pointerDown(handle, { clientX: 100, clientY: 100, pointerId: 2, currentTarget: handle })
    fireEvent.pointerMove(handle, { clientX: 182, clientY: 182, pointerId: 2, currentTarget: handle })
    fireEvent.pointerUp(handle, { pointerId: 2, currentTarget: handle })
    await waitFor(() => expect(screen.getByTestId('layout-w').getAttribute('value')).toBe('5'))
    fireEvent.click(screen.getByTestId('layout-zoom-out'))
    fireEvent.click(screen.getByTestId('layout-zoom-fit'))
    expect(screen.getByTestId('layout-zoom-in')).toBeTruthy()
  })

  it('blocks Apply when two tiles partially overlap', async () => {
    const hosts = [{ cell_index: 0, element_id: 'Atmosphere', geometry: { x: 0, y: 0, w: 2, h: 2 } },
                   { cell_index: 1, element_id: 'FirstTeamOverview', geometry: { x: 2, y: 0, w: 2, h: 2 } }]
    ;(customlayout.base as any).mockResolvedValue(baseFor(hosts))
    ;(rpc as any).mockImplementation(async (m: string) => m === 'render.preview'
      ? { hosts, width: 1600, height: 900, grid: { cols: 20, rows: 10 } }
      : null)
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    const tile = (await screen.findAllByTestId('layout-tile'))[0]
    Object.defineProperty(tile, 'setPointerCapture', { value: vi.fn() })
    Object.defineProperty(tile, 'releasePointerCapture', { value: vi.fn() })
    fireEvent.pointerDown(tile, { clientX: 100, clientY: 100, pointerId: 4, currentTarget: tile })
    fireEvent.pointerMove(tile, { clientX: 182, clientY: 100, pointerId: 4, currentTarget: tile })
    fireEvent.pointerUp(tile, { pointerId: 4, currentTarget: tile })
    expect(await screen.findByTestId('layout-overlaps')).toBeTruthy()
    expect((screen.getByTestId('layout-apply') as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows the runtime pane and explains a tile the game moved', async () => {
    const hosts = [{ host: { cell_index: 0, element_id: 'Atmosphere', geometry: { x: 27, y: 4, w: 4, h: 2 } } }]
    ;(customlayout.base as any).mockResolvedValue(baseFor([
      { ...host(16, 6, 4, 2), element_id: 'Atmosphere' }]))
    ;(rpc as any).mockImplementation(async (m: string) => m === 'render.preview'
      ? { hosts, width: 1600, height: 900, grid: { cols: 20, rows: 10 } } : null)
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    await screen.findByTestId('layout-tile')
    fireEvent.click(screen.getByTestId('pane-runtime'))
    expect(await screen.findByTestId('layout-runtime')).toBeTruthy()
    expect(screen.getByTestId('layout-runtime-tile').textContent).toContain('compacted up to row 4')
    fireEvent.click(screen.getByTestId('pane-design'))
    fireEvent.click(screen.getByTestId('layout-tile'))
    expect(screen.getByTestId('layout-moved-reason').textContent).toContain('compacted up to row 4')
  })

  it('will not resize a fixed-size tile below the game minimum', async () => {
    const hosts = [{ cell_index: 0, element_id: 'Atmosphere', geometry: { x: 16, y: 8, w: 4, h: 2 },
                    limits: { min_w: 4, min_h: 2, max_w: 4, max_h: 2 } }]
    ;(customlayout.base as any).mockResolvedValue(baseFor(hosts))
    ;(rpc as any).mockImplementation(async (m: string) => m === 'render.preview'
      ? { hosts, width: 1600, height: 900, grid: { cols: 20, rows: 10 } }
      : null)
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    await screen.findByTestId('layout-tile')
    const handle = screen.getByTestId('layout-resize')
    Object.defineProperty(handle, 'setPointerCapture', { value: vi.fn() })
    Object.defineProperty(handle, 'releasePointerCapture', { value: vi.fn() })
    fireEvent.pointerDown(handle, { clientX: 100, clientY: 100, pointerId: 3, currentTarget: handle })
    fireEvent.pointerMove(handle, { clientX: 0, clientY: 0, pointerId: 3, currentTarget: handle })
    fireEvent.pointerUp(handle, { pointerId: 3, currentTarget: handle })
    expect(screen.getByTestId('layout-h').getAttribute('value')).toBe('2')
    expect(screen.getByTestId('layout-w').getAttribute('value')).toBe('4')
  })

  it('shows the pinned viewport in the header, stock Squad at 30x16 with Atmosphere at col 26, and greys out last rendered until the current edit resolves', async () => {
    const stockCells = [{ space: 'main', order: 0, element_id: 'Atmosphere', x: 16, y: 8, width: 4, height: 2, min_w: 4, min_h: 2, max_w: 4, max_h: 2 }]
    const baseObj = { m_gridComponents: [{ m_elementID: 'Atmosphere', m_location: { x: 16, y: 8, width: 4, height: 2 } }], m_optionalSlices: {} }
    ;(customlayout.base as any).mockResolvedValue({
      object: baseObj, cells: stockCells, design: { cols: 20, rows: 10 }, source: 'bundle',
      confidence: { label: 'measured' },
    })
    let resolveEdit!: (v: any) => void
    let callCount = 0
    ;(rpc as any).mockImplementation((m: string) => {
      if (m !== 'customlayout.runtime') return Promise.resolve(null)
      callCount++
      if (callCount === 1) {
        return Promise.resolve({
          confidence: { label: 'measured' },
          grid: { cols: 30, rows: 16 },
          cells: [{ space: 'main', order: 0, element_id: 'Atmosphere', x: 26, y: 8, w: 4, h: 2, reason: '' }],
          slots: [],
        })
      }
      return new Promise((res) => { resolveEdit = res })
    })
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    const tile = await screen.findByTestId('layout-tile')
    await waitFor(() => expect(screen.getByTestId('layout-canvas').getAttribute('data-runtime-fresh')).toBe('true'))
    expect(screen.getByTestId('layout-confidence').getAttribute('data-confidence')).toBe('measured')
    expect(screen.getByTestId('layout-viewport').textContent).toContain('2560×1440 fullscreen · Small · Larger')
    expect(screen.getByTestId('layout-viewport').textContent).toContain('Large')

    fireEvent.click(tile)
    const lastRendered = screen.getByTestId('layout-last-rendered')
    expect(lastRendered.getAttribute('data-fresh')).toBe('true')
    expect(lastRendered.textContent).toContain('last rendered x26 y8')

    // Stage an edit: before the runtime response arrives, last rendered must grey out and never show stale x26 y8
    fireEvent.change(screen.getByTestId('layout-y'), { target: { value: '4' } })
    const pending = screen.getByTestId('layout-last-rendered')
    expect(pending.getAttribute('data-fresh')).toBe('false')
    expect(pending.textContent).not.toContain('x26 y8')

    // Resolve the current edit's runtime response
    resolveEdit({
      confidence: { label: 'measured' },
      grid: { cols: 30, rows: 16 },
      cells: [{ space: 'main', order: 0, element_id: 'Atmosphere', x: 26, y: 4, w: 4, h: 2, reason: '' }],
      slots: [],
    })
    await waitFor(() => expect(screen.getByTestId('layout-last-rendered').getAttribute('data-fresh')).toBe('true'))
    expect(screen.getByTestId('layout-last-rendered').textContent).toContain('last rendered x26 y4')
  })

  it('loads custom file base when applied, offers compare with bundle toggle, and returns to bundle base on rollback', async () => {
    const customCells = [{ space: 'main', order: 0, element_id: 'Atmosphere', x: 16, y: 4, width: 4, height: 2, min_w: 4, min_h: 2, max_w: 4, max_h: 2 }]
    const stockCells = [{ space: 'main', order: 0, element_id: 'Atmosphere', x: 16, y: 8, width: 4, height: 2, min_w: 4, min_h: 2, max_w: 4, max_h: 2 }]
    const mkObj = (y: number) => ({ m_gridComponents: [{ m_elementID: 'Atmosphere', m_location: { x: 16, y, width: 4, height: 2 } }], m_optionalSlices: {} })
    let rolledBack = false
    ;(customlayout.base as any).mockImplementation(async () => rolledBack
      ? { object: mkObj(8), cells: stockCells, bundle_cells: stockCells, design: { cols: 20, rows: 10 }, source: 'bundle', last_tx: null }
      : { object: mkObj(4), cells: customCells, bundle_cells: stockCells, design: { cols: 20, rows: 10 }, source: 'game_folder', last_tx: 'tx-applied-1' })
    ;(customlayout.rollback as any).mockImplementation(async () => { rolledBack = true; return { tx_id: 'tx-applied-1', state: 'rolled_back', rollback: { exact: true } } })
    ;(rpc as any).mockResolvedValue({ confidence: { label: 'measured' }, grid: { cols: 30, rows: 16 }, cells: [], slots: [] })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    await screen.findByTestId('layout-tile')
    expect(screen.getByTestId('layout-engine').textContent).toContain('custom file base')
    const cmp = screen.getByTestId('layout-compare-bundle') as HTMLInputElement
    expect(cmp.checked).toBe(false)
    expect(screen.queryByTestId('layout-bundle-ghost')).toBeNull()
    fireEvent.click(cmp)
    expect(screen.getByTestId('layout-bundle-ghost').textContent).toContain('stock: Atmosphere')

    fireEvent.click(screen.getByTestId('layout-rollback'))
    await waitFor(() => expect(screen.getByTestId('layout-engine').textContent).toContain('bundle base'))
    expect(screen.queryByTestId('layout-compare-bundle')).toBeNull()
    confirmSpy.mockRestore()
  })

  it('keeps 1-row tile names visible with ellipsis and tooltip at 50% zoom', async () => {
    const cells = [{ space: 'main', order: 0, element_id: 'HumanActionsControlPanelBlock', x: 0, y: 0, width: 16, height: 1, min_w: 1, min_h: 1, max_w: 20, max_h: 1 }]
    ;(customlayout.base as any).mockResolvedValue({
      object: { m_gridComponents: [{ m_elementID: 'HumanActionsControlPanelBlock', m_location: { x: 0, y: 0, width: 16, height: 1 } }], m_optionalSlices: {} },
      cells, design: { cols: 20, rows: 10 }, source: 'bundle',
    })
    ;(rpc as any).mockResolvedValue({ confidence: { label: 'measured' }, grid: { cols: 30, rows: 16 }, cells: [], slots: [] })
    render(<LayoutCanvas project="tmp" composition="SquadComposition-Large" onSelect={() => {}} say={() => {}} />)
    await screen.findByTestId('layout-tile')
    fireEvent.click(screen.getByTestId('layout-zoom-out'))
    fireEvent.click(screen.getByTestId('layout-zoom-out'))
    const tile = screen.getByTestId('layout-tile')
    expect(tile.className).toContain('compact')
    expect(tile.getAttribute('title')).toContain('HumanActionsControlPanelBlock')
    expect(tile.querySelector('.tile-name')?.textContent).toBe('HumanActionsControlPanelBlock')
  })

  it('switches viewport profile from fullscreen to windowed and reflects per-profile confidence', async () => {
    ;(customlayout.base as any).mockImplementation(async (_c: string, profile?: string) => ({
      object: { m_gridComponents: [{ m_elementID: 'CellA', m_location: { x: 0, y: 0, width: 4, height: 2 } }], m_optionalSlices: {} },
      cells: [{ space: 'main', order: 0, element_id: 'CellA', x: 0, y: 0, width: 4, height: 2, min_w: 1, min_h: 1, max_w: 4, max_h: 2 }],
      design: { cols: 20, rows: 10 },
      source: 'bundle',
      confidence: { label: profile?.includes('windowed') ? 'measured' : 'measured mismatch' },
    }))
    ;(rpc as any).mockImplementation(async (m: string, p: any) => {
      if (m !== 'customlayout.runtime') return null
      return {
        confidence: { label: String(p?.profile).includes('windowed') ? 'measured' : 'measured mismatch' },
        grid: { cols: 30, rows: 16 },
        cells: [{ space: 'main', order: 0, element_id: 'CellA', x: 0, y: 0, w: 4, h: 2, reason: '' }],
        slots: [],
      }
    })
    render(<LayoutCanvas project="tmp" composition="InjuryHistoryCardGridComposition" onSelect={() => {}} say={() => {}} />)
    await screen.findByTestId('layout-tile')
    await waitFor(() => expect(screen.getByTestId('layout-confidence').getAttribute('data-confidence')).toBe('measured mismatch'))
    expect(screen.getByTestId('layout-viewport').textContent).toContain('2560×1440 fullscreen')

    fireEvent.change(screen.getByTestId('layout-viewport-profile'), { target: { value: '2560x1440 windowed, Small, Larger' } })
    await waitFor(() => expect(screen.getByTestId('layout-confidence').getAttribute('data-confidence')).toBe('measured'))
    expect(screen.getByTestId('layout-viewport').textContent).toContain('2560×1440 windowed')
  })
})
