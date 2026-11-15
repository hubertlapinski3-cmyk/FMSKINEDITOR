// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Tiles from './Tiles'
import Tables from './Tables'
import { Guard } from './App'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const cell = (i: number, id: string, x: number, w: number) => ({ cell_index: i, element_id: id, x, y: 0, w, h: 7, min_w: 0, min_h: 0, max_w: 0, max_h: 0, flags: [] as string[], configs: [], h_align: '0', v_align: '0' })
const SCREEN = { panel_id: 'TacticalPlannerTool', layout: 'TacticalPlannerRoot', area: 'tactics_panel', sets: [{ set_name: 'TeamInstructionsTabCompositionSet', host: { layout: 'TacticalPlannerTeamInstructions' }, variants: [
  { breakpoint: 2, variant_idx: 0, composition: 'TabComposition-Standard', composition_info: { preset_w: 0, preset_h: 0, layout_mode: 'Standard', preset_name: '' }, cells: [cell(0, 'TeamInstructionsPitch', 0, 6), cell(1, 'TeamInstructionsBlock', 6, 6)] }] }] }
let calls: [string, any][] = []
const answer = (extra: Record<string, any> = {}) => (rpc as any).mockImplementation(async (m: string, p: any) => {
  calls.push([m, p])
  if (m in extra) return typeof extra[m] === 'function' ? extra[m](p) : extra[m]
  return ({ 'layout.state': { present: true, staleness: { status: 'fresh', message: '' } }, 'layout.screens': { screens: [{ panel_id: 'TacticalPlannerTool', area: 'tactics_panel', tiles: 12 }] },
    'layout.screen': SCREEN, 'placement.list': { edits: [] }, 'placement.check': { blocks: [], warnings: [], collisions: [] }, 'placement.add': { edit: {} } } as any)[m]
})
afterEach(() => { cleanup(); vi.clearAllMocks(); calls = [] })

describe('Tiles view', () => {
  it('shows a real screen as a canvas, stages a numeric move, validates it and stores it on commit', async () => {
    answer()
    render(<Guard name="Tile layout"><Tiles project="p" target="bundles" onChanged={() => {}} say={() => {}} /></Guard>)
    fireEvent.click(await screen.findByText(/TacticalPlannerTool/))
    await screen.findByTestId('cell-0')
    expect(screen.getByTestId('cell-0')).toBeTruthy(); expect(screen.getByTestId('cell-1')).toBeTruthy()
    fireEvent.pointerDown(screen.getByTestId('cell-0'))                                  // selects it (shows the numeric fields)
    const x = (await screen.findAllByRole('spinbutton'))[0] as HTMLInputElement
    fireEvent.change(x, { target: { value: '6' } })
    await waitFor(() => expect(calls.some(([m]) => m === 'placement.check')).toBe(true))
    expect(calls.find(([m]) => m === 'placement.check')![1].edit).toEqual({ composition: 'TabComposition-Standard', cell_index: 0, geometry: { x: 6, y: 0, w: 6, h: 7 } })
    expect(await screen.findByText(/Overlap: cells 0, 1/)).toBeTruthy()                  // dropped on its neighbour: flagged, not refused
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(screen.getByText(/Store 1 edit/))
    await waitFor(() => expect(calls.filter(([m]) => m === 'placement.add').length).toBe(1))
    expect(calls.find(([m]) => m === 'placement.add')![1]).toEqual({ project: 'p', confirm: true, edit: { composition: 'TabComposition-Standard', cell_index: 0, geometry: { x: 6, y: 0, w: 6, h: 7 }, note: 'moved in the tile canvas' } })
  })

  it('a game screenshot can be drawn behind the grid (opacity, fit), and a new one is added through the engine', async () => {
    const shots = [{ name: 'forest-squad.png', width: 2500, height: 1406 }]
    answer({ 'screens.list': { folder: 'C:/ws/game-screens', screens: shots }, 'screens.image': { content_type: 'image/png', base64: 'AAAA' }, 'screens.add': (p: any) => ({ name: 'club.png', width: 10, height: 10, _p: p }) })
    vi.spyOn(window, 'prompt').mockReturnValue('C:/caps/club.png')
    render(<Guard name="Tile layout"><Tiles project="p" target="bundles" onChanged={() => {}} say={() => {}} /></Guard>)
    fireEvent.click(await screen.findByText(/TacticalPlannerTool/))
    await screen.findByTestId('cell-0')
    expect(screen.queryByTestId('shot-image')).toBeNull()
    fireEvent.change(screen.getByLabelText('Game screenshot behind the grid'), { target: { value: 'forest-squad.png' } })
    const img = await screen.findByTestId('shot-image')
    expect(img.getAttribute('href')).toBe('data:image/png;base64,AAAA'); expect(img.getAttribute('preserveAspectRatio')).toBe('none')
    expect(calls.some(([m, p]) => m === 'screens.image' && p.name === 'forest-squad.png')).toBe(true)
    fireEvent.change(screen.getByLabelText('Screenshot opacity'), { target: { value: '0.8' } })
    expect(screen.getByTestId('shot-image').getAttribute('opacity')).toBe('0.8')
    fireEvent.change(screen.getByLabelText('Screenshot fit'), { target: { value: 'contain' } })
    expect(screen.getByTestId('shot-image').getAttribute('preserveAspectRatio')).toBe('xMidYMid meet')
    expect(screen.getByTestId('shotbar').textContent).toMatch(/stay on this PC/)
    fireEvent.click(screen.getByText('Add a screenshot ...'))
    await waitFor(() => expect(calls.some(([m, p]) => m === 'screens.add' && p.path === 'C:/caps/club.png')).toBe(true))
    await waitFor(() => expect((screen.getByLabelText('Game screenshot behind the grid') as HTMLSelectElement).value).toBe('club.png'))
    fireEvent.change(screen.getByLabelText('Game screenshot behind the grid'), { target: { value: '' } })
    await waitFor(() => expect(screen.queryByTestId('shot-image')).toBeNull())
  })

  it('a refused move (blocks) disables the store button and says why; Revert drops the staging', async () => {
    answer({ 'placement.check': { blocks: ['locked: this cell has the \'locked\' flag'], warnings: [], collisions: [] } })
    render(<Tiles project="p" target="bundles" onChanged={() => {}} say={() => {}} />)
    fireEvent.click(await screen.findByText(/TacticalPlannerTool/)); await screen.findByTestId('cell-0')
    fireEvent.pointerDown(screen.getByTestId('cell-1'))
    fireEvent.change((await screen.findAllByRole('spinbutton'))[0], { target: { value: '0' } })
    expect(await screen.findByText(/blocked: locked/)).toBeTruthy()
    expect((screen.getByText(/Store 1 edit/) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByText('Revert'))
    await waitFor(() => expect(screen.queryByText(/blocked: locked/)).toBeNull())
  })

  it('without a layout index it offers to load it, and says nothing is imported', async () => {
    answer({ 'layout.state': { present: false } })
    render(<Tiles project="p" target="bundles" onChanged={() => {}} say={() => {}} />)
    expect(await screen.findByText(/No layout index is imported yet/)).toBeTruthy(); expect(screen.getByText('Load the layout index')).toBeTruthy()
  })

  it('an engine failure is shown as text, and a broken payload shows the guard instead of a black window', async () => {
    answer({ 'layout.state': () => { throw new Error('engine is down') } })
    render(<Tiles project="p" target="bundles" onChanged={() => {}} say={() => {}} />)
    expect(await screen.findByText(/engine is down/)).toBeTruthy()
    cleanup()
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    answer({ 'layout.screen': { panel_id: 'X', layout: 'X', area: 'a', sets: [{ set_name: 'S', host: { layout: 'H' }, variants: [{ breakpoint: 2, variant_idx: 0, composition: 'C', composition_info: null, cells: [{ cell_index: 0, element_id: null, x: 0, y: 0, w: 2, h: 2, flags: [] }] }] }] } })
    render(<Guard name="Tile layout"><Tiles project="p" target="bundles" onChanged={() => {}} say={() => {}} /></Guard>)
    fireEvent.click(await screen.findByText(/TacticalPlannerTool/))
    expect(await screen.findByText(/Tile layout could not be shown/)).toBeTruthy()
    spy.mockRestore()
  })
})

describe('Tables view', () => {
  const VIEW = { name: 'SquadKeyPlayersTableSmall', path_id: '-9', factory: { name: 'PlayerTableFactory', coverage: 1, cells: 622 }, patches: null,
    columns: [{ index: 0, id: 'portrait-name-position', width: 180, min_width: 180, required: false, sorting_disabled: false, priority: 0, breakpoints: -1, conditions: 0, cell: { default_width: 200, minimum_width: 200, cell_layout: 'PlayerPortraitNamePositionCell', cell_layout_guid: 'g', header_text_id: 1, sortable: true } },
              { index: 1, id: 'age', width: 0, min_width: 0, required: true, sorting_disabled: false, priority: 0, breakpoints: -1, conditions: 0, cell: null }],
    available: [{ id: 'club', default_width: 200, minimum_width: 200, cell_layout: 'ClubCell', cell_layout_guid: 'c', header_text_id: 2, sortable: true }] }
  it('lists columns with what they draw, sends width, hide and add edits; a required column cannot be hidden', async () => {
    answer({ 'tables.list': { total: 1, views: [{ name: VIEW.name, path_id: '-9', columns: 2 }] }, 'tables.view': VIEW, 'tables.edit': { project: {} } })
    render(<Guard name="Table views"><Tables project="p" target="bundles" onChanged={() => {}} say={() => {}} /></Guard>)
    fireEvent.click(await screen.findByText(/SquadKeyPlayersTableSmall/))
    expect(await screen.findByText('PlayerPortraitNamePositionCell')).toBeTruthy(); expect(screen.getByText(/not in this factory/)).toBeTruthy()
    const w = screen.getAllByRole('spinbutton')[0] as HTMLInputElement
    fireEvent.change(w, { target: { value: '300' } }); fireEvent.blur(w)
    await waitFor(() => expect(calls.some(([m, p]) => m === 'tables.edit' && p.op.op === 'set-width' && p.op.width === 300 && p.op.column === 'portrait-name-position')).toBe(true))
    const hides = screen.getAllByText('hide') as HTMLButtonElement[]
    expect(hides[1].disabled).toBe(true)                                                   // 'age' is required here
    fireEvent.click(hides[0])
    await waitFor(() => expect(calls.some(([m, p]) => m === 'tables.edit' && p.op.op === 'hide-column')).toBe(true))
    fireEvent.click(screen.getByText('+ club'))
    await waitFor(() => expect(calls.some(([m, p]) => m === 'tables.edit' && p.op.op === 'show-column' && p.op.column === 'club' && p.op.after === 'age')).toBe(true))
  })
})
