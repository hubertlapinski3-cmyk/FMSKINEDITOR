// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RenderScreenView, RenderTableView, type ScreenRes, type TableRes } from './RenderScreens'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const screenRes: ScreenRes = { composition: 'SquadComposition-Large', pitch: { cell: 65.5, gap: 16.5, measured: true, flag: null }, grid: { columns: 30, rows: 16 }, flags: ['tile configs chosen by the largest-fit assumption: Loans'],
  hosts: [{ element_id: 'Atmosphere', col: 26, row: 8, w: 4, h: 2, px: { left: 2144, top: 668, width: 312, height: 148 }, tile_layout: 'SquadAtmosphereTile_4x2', tile_how: 'config of exactly this size' },
          { element_id: 'Tactics', col: 26, row: 0, w: 4, h: 4, px: { left: 2144, top: 12, width: 312, height: 312 }, tile_layout: 'SquadTacticsTile_4x4', tile_how: 'config of exactly this size' }], runtime_slots: [] }
const estimate: ScreenRes = { ...screenRes, composition: 'SomeOtherComposition', pitch: { cell: 66, gap: 16, measured: false, flag: 'ESTIMATE: no measured pitch for composition \'SomeOtherComposition\'; excluded from pixel-faithful claims' } }
const tableRes: TableRes = { view: 'SquadKeyPlayersTableSmall', path_id: '7', edited: false, ops: 0, notes: [], breakpoint: 3, label: "placeholder table: the header row is the view's column order, the cells hold no data",
  columns: [{ id: 'portrait-name-position', width: 180 }, { id: 'current-ability-stars-with-subtitle', width: 90 }] }

beforeEach(() => {
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'layout.screens') return { screens: [{ panel_id: 'SquadOverview', area: 'Squad', tiles: 5 }] }
    if (m === 'layout.screen') return { sets: [{ variants: [{ breakpoint: 0, composition: 'SquadComposition-Large' }, { breakpoint: 1, composition: 'SomeOtherComposition' }] }] }
    if (m === 'render.screen') return p.composition === 'SomeOtherComposition' ? estimate : screenRes
    if (m === 'tables.list') return { total: 1, views: [{ name: 'SquadKeyPlayersTableSmall', path_id: '7', columns: 2 }] }
    if (m === 'render.table') return tableRes
    return null
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('screen view', () => {
  it('lists screens, picks a composition and draws the cells with the tile layout the engine chose', async () => {
    render(<RenderScreenView project={null} say={() => {}} />)
    fireEvent.click(await screen.findByText('SquadOverview'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('render.screen', { composition: 'SquadComposition-Large', width: 2468.8, height: 1319.3, reserved_right: 0, padding: 12 }))
    const stage = await screen.findByTestId('screenstage')
    await waitFor(() => expect(stage.querySelectorAll('.rcell').length).toBe(2))
    expect(stage.querySelector('[data-element="Atmosphere"]')!.textContent).toContain('SquadAtmosphereTile_4x2')
    expect(screen.getByRole('note').textContent).toContain('Approximation')
    expect(screen.getByText(/largest-fit assumption/)).toBeTruthy()
  })
  it('says so when the composition has no measured pitch (an estimate)', async () => {
    render(<RenderScreenView project={null} say={() => {}} />)
    fireEvent.click(await screen.findByText('SquadOverview'))
    await screen.findByTestId('screenstage')
    fireEvent.change(await screen.findByDisplayValue('SquadComposition-Large'), { target: { value: 'SomeOtherComposition' } })
    expect((await screen.findAllByRole('alert')).some((a) => a.textContent!.startsWith('ESTIMATE'))).toBe(true)
  })
  it('sends the project and the skin toggle when a project is open', async () => {
    render(<RenderScreenView project="demo" say={() => {}} />)
    fireEvent.click(await screen.findByText('SquadOverview'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('render.screen', expect.objectContaining({ project: 'demo', skin: true })))
    fireEvent.click(screen.getByLabelText(/skin: demo/))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('render.screen', expect.objectContaining({ project: 'demo', skin: false })))
  })
})

describe('table view', () => {
  it('draws the header row in column order with labelled placeholder cells', async () => {
    render(<RenderTableView project={null} say={() => {}} />)
    fireEvent.click(await screen.findByText('SquadKeyPlayersTableSmall'))
    const t = await screen.findByTestId('placeholdertable')
    expect(Array.from(t.querySelectorAll('th')).map((x) => x.textContent!.startsWith('portrait-name-position') || x.textContent!.startsWith('current-ability'))).toEqual([true, true])
    expect(t.querySelectorAll('td')[0].textContent).toBe('placeholder')
    expect(screen.getByRole('note').textContent).toContain('placeholder table')
    expect(rpc).toHaveBeenCalledWith('render.table', { path_id: '7' })
  })
  it('passes the breakpoint when one is typed', async () => {
    render(<RenderTableView project={null} say={() => {}} />)
    fireEvent.click(await screen.findByText('SquadKeyPlayersTableSmall'))
    await screen.findByTestId('placeholdertable')
    fireEvent.change(screen.getByLabelText(/breakpoint/), { target: { value: '3' } })
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('render.table', { path_id: '7', breakpoint: 3 }))
  })
})
