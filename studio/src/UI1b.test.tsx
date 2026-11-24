// @vitest-environment jsdom
// UI1b step 6: click-through tests. The "project" is a temporary in-memory name (ui1b-tmp); every engine
// call is mocked, so no real folder, save, CustomGridCompositions file or game/BepInEx path is touched.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

vi.mock('@monaco-editor/react', () => ({ default: () => null }))
vi.mock('./monaco', () => ({ lint: vi.fn(), registerQuickFixes: vi.fn(), registerTokenCompletion: vi.fn() }))
vi.mock('./engine', () => ({
  rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(async () => ({})), subscribe: vi.fn(() => () => {}),
  isApplyRefusal: (r: any) => typeof r?.refused === 'string',
  customlayout: { list: vi.fn(), preflight: vi.fn(), apply: vi.fn(), apply_edits: vi.fn(), rollback: vi.fn(), recovery_scan: vi.fn(), base: vi.fn() },
}))
import { rpc, customlayout } from './engine'
import App from './App'
import { rankCompositions } from './GameLayouts'

const TMP = 'ui1b-tmp'
const PROJECTS = [TMP]
const COMPS = ['SquadComposition-Large', 'SquadComposition-Standard', 'SquadComposition-Small', 'CompetitionStagesBottomTileComposition', 'PlayerReportOverviewComposition-Large']
const names = COMPS.map((name) => ({ name, preset: [1600, 900] as [number, number], cells: [] as any[] }))

const state = { install: { game_dir: 'C:/FM27', aa_dir: 'C:/FM27/aa', version: '27.0.1' }, running: false,
  tamper: { state: 'clean' }, snapshot_mismatch: null, vanilla: { game_build: '27.0.1' }, indexed: true }
const PF = { ready: true, blocked: [], warnings: [], required_confirmations: [], confirmation_reasons: {},
  file_operations: [], folder: '<journal>', folder_exists: true }

const tile = (id: string, w = 4) => ({
  cell_index: 0, element_id: id, geometry: { x: 1, y: 1, w, h: 2 },
  px: { left: 20, top: 20, width: 300, height: 150 }, flags: [],
})
const preview = (composition: string) => ({
  screen: composition, composition, breakpoint: 3, confidence: 'MEASURED', width: 1600, height: 900,
  setting: 'Large UI',
  information_display: { setting: 'Large UI', locked: false, reason: '', evidence: 'measured' },
  state_options: [],
  selection: { label: 'measured from the game', evidence: 'MEASURED', measured_points: [], corroborating_points: [],
    source: { kind: 'measured', asset: 'game screenshot' }, cross_check: { status: 'ok', dump_rows: 1, keys_compared: [], gaps: [] }, gaps: [] },
  grid: { cols: 20, rows: 11, pitch: { cell: 82, gap: 0, measured: true, label: 'measured' }, layout_label: 'offline renderer' },
  hosts: [tile('tile-header')], cells: [], slots: [],
  competition: { bundesliga: false, default: true, label: '', sheet: '', bundle: '', rules: 0, evidence: '', note: '' },
  game_states: { scenario: 'default', defaults: {}, values: {}, options: [] },
  operations: { applied: [], pending: [] }, measured: [], estimated: [], notice: '',
})

let problemsResponse: any[] = []
let favouritesStore: string[] = []

beforeEach(() => {
  localStorage.clear()
  problemsResponse = []
  favouritesStore = []
  ;(rpc as any).mockImplementation(async (m: string, p: any = {}) => {
    switch (m) {
      case 'app.state': return { ...state, projects: PROJECTS }
      case 'project.list': return PROJECTS
      case 'project.files': return { folder: true, files: [] }
      case 'project.problems': return { problems: problemsResponse }
      case 'project.get': return { options: { output: 'bundles' } }
      case 'layout.state': return { present: true, staleness: { status: 'fresh' } }
      case 'playground.screens': {
        const win = String(p?.profile || '').includes('windowed')
        const confidences: Record<string, string> = {
          'SquadComposition-Large': 'measured',
          'PlayerReportOverviewComposition-Large': 'measured',
          'CompetitionStagesBottomTileComposition': win ? 'computed' : 'measured mismatch',
          'SquadComposition-Standard': 'unverified',
          'SquadComposition-Small': 'unverified',
        }
        return {
          total: names.length,
          profile: p?.profile || '2560x1440 fullscreen, Small, Larger',
          confidences,
          screens: names.map((s) => ({ ...s, confidence: confidences[s.name] || 'unverified' })),
        }
      }
      case 'playground.favourites': return { favourites: favouritesStore }
      case 'playground.set_favourites': {
        favouritesStore = Array.isArray(p?.favourites) ? p.favourites : []
        return { favourites: favouritesStore }
      }
      case 'render.preview': return preview(p.screen)
      case 'render.screen': return { composition: p.composition, pitch: {}, grid: { cols: 20, rows: 11 }, hosts: [] }
      default: return null
    }
  })
  ;(customlayout.base as any).mockResolvedValue({
    object: { m_gridComponents: [{ m_elementID: 'tile-header', m_location: { x: 1, y: 1, width: 4, height: 2 } }], m_optionalSlices: {} },
    cells: [{ space: 'main', order: 0, element_id: 'tile-header', x: 1, y: 1, width: 4, height: 2, min_w: 1, min_h: 1, max_w: 0, max_h: 0 }],
    design: { cols: 20, rows: 11 }, source: 'bundle',
  })
  ;(customlayout.list as any).mockResolvedValue({ folder: '<game>', folder_exists: true, badge: 'custom', warning: '',
    files: [{ composition: 'SquadComposition-Large', size: 10, mtime: 'today', sha256: 'abc' }] })
  ;(customlayout.preflight as any).mockResolvedValue(PF)
  ;(customlayout.recovery_scan as any).mockResolvedValue([])
  ;(customlayout.apply as any).mockResolvedValue({ tx_id: 'tx-1', state: 'completed', created_utc: 'now',
    package_dir: '<pkg>', folder: '<game>', folder_existed: true, confirmations: [], ops: [], backup_sha256: {} })
  ;(customlayout.rollback as any).mockResolvedValue({ tx_id: 'tx-1', state: 'rolled_back', created_utc: 'now',
    package_dir: '<pkg>', folder: '<game>', folder_existed: true, confirmations: [], ops: [], backup_sha256: {},
    rollback: { utc: 'now', conflicts: [], exact: true, folder_now: {} } })
})
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear() })

async function openGameLayouts() {
  render(<App />)
  await screen.findByTestId('start')
  fireEvent.click(screen.getByText(TMP))                       // open the temp project from the explorer
  await waitFor(() => expect(screen.getByText(TMP.toUpperCase())).toBeTruthy())
  fireEvent.click(screen.getByTitle(/Game Layouts \(Playground\)/))
  return await screen.findByTestId('game-layouts')
}

const search = () => screen.getByTestId('gl-q') as HTMLInputElement
const rowFor = (name: string) => screen.getAllByTestId('gl-row').find((r) => r.getAttribute('data-composition') === name)!

describe('UI1b search', () => {
  it('ranks exact prefixes first and ignores case and hyphens', () => {
    expect(rankCompositions(COMPS, 'squadcom').slice(0, 3)).toEqual([
      'SquadComposition-Large', 'SquadComposition-Standard', 'SquadComposition-Small'])
    expect(rankCompositions(COMPS, 'SQUAD-COM').slice(0, 3)).toEqual([
      'SquadComposition-Large', 'SquadComposition-Standard', 'SquadComposition-Small'])
  })

  it('shows the ranked rows in the sidebar, with a breakpoint suffix and a custom badge', async () => {
    await openGameLayouts()
    fireEvent.change(search(), { target: { value: 'squadcom' } })
    const rows = screen.getAllByTestId('gl-row')
    expect(rows.slice(0, 3).map((r) => r.getAttribute('data-composition'))).toEqual([
      'SquadComposition-Large', 'SquadComposition-Standard', 'SquadComposition-Small'])
    expect(rows[0].getAttribute('title')).toBe('SquadComposition-Large')
    expect(within(rows[0]).getByText('Large')).toBeTruthy()
    expect(within(rows[0]).getByText('custom')).toBeTruthy()
  })
})

describe('UI1b click-through: composition -> layout tab -> canvas -> tile edit -> Apply', () => {
  it('opens a main-area tab with all seven contents', async () => {
    await openGameLayouts()
    fireEvent.change(search(), { target: { value: 'squadcom' } })
    fireEvent.click(rowFor('SquadComposition-Large'))
    const tab = await screen.findByTestId('main-tab')
    expect(tab.getAttribute('data-kind')).toBe('layout')
    expect(within(tab).getByText(/SquadComposition-Large/)).toBeTruthy()
    const canvas = await screen.findByTestId('layout-canvas')
    expect(canvas.getAttribute('data-composition')).toBe('SquadComposition-Large')

    expect(screen.getAllByTestId('layout-tile').length).toBeGreaterThanOrEqual(1)      // 1 canvas with tiles
    expect(screen.getByTestId('layout-confidence').textContent).toContain('measured')  // 2 confidence label
    expect(screen.getByTestId('pg-preview-breakpoint-control')).toBeTruthy()           // 3 breakpoint selector
    expect(screen.getByTestId('layout-engine').textContent).toContain('engine')        // 4 engine label
    expect(screen.getByTestId('layout-apply')).toBeTruthy()                            // 5 Apply
    expect(screen.getByTestId('layout-rollback')).toBeTruthy()                         // 6 Rollback
    expect(screen.getByTestId('layout-inspector')).toBeTruthy()                        // 7 inspector
    expect(screen.queryByTestId('empty-editor')).toBeNull()
  })

  it('selects a tile, changes its width, updates the canvas and enables Apply, then applies', async () => {
    await openGameLayouts()
    fireEvent.change(search(), { target: { value: 'squadcom' } })
    fireEvent.click(rowFor('SquadComposition-Large'))
    await screen.findByTestId('layout-canvas')

    const before = (screen.getAllByTestId('layout-tile')[0] as HTMLElement).style.width
    fireEvent.click(screen.getAllByTestId('layout-tile')[0])
    expect(screen.getByTestId('layout-selected').getAttribute('data-element')).toBe('tile-header')
    expect(screen.getByTestId('gl-element-id').textContent).toContain('tile-header')   // Element pane is in sync

    fireEvent.change(screen.getByTestId('layout-w'), { target: { value: '6' } })
    await waitFor(() => expect((screen.getByTestId('layout-apply') as HTMLButtonElement).disabled).toBe(false))
    expect((screen.getAllByTestId('layout-tile')[0] as HTMLElement).style.width).not.toBe(before)
    expect(screen.getByTestId('layout-history').textContent).toContain('4→6')
    fireEvent.click(screen.getByTestId('layout-apply'))
    await waitFor(() => expect(customlayout.apply_edits).toHaveBeenCalledWith(TMP, 'SquadComposition-Large', expect.any(Array), [], expect.any(Object)))
  })

  it('opens a separate tab for another composition; closing the last tab returns to the editor', async () => {
    await openGameLayouts()
    fireEvent.change(search(), { target: { value: 'squadcom' } })
    fireEvent.click(rowFor('SquadComposition-Large'))
    await screen.findByTestId('layout-canvas')
    fireEvent.click(rowFor('SquadComposition-Standard'))
    await waitFor(() => expect(screen.getAllByTestId('main-tab')).toHaveLength(2))
    expect(screen.getByTestId('layout-canvas').getAttribute('data-composition')).toBe('SquadComposition-Standard')

    const close = screen.getAllByTestId('main-tab')[1].querySelector('button')!
    fireEvent.click(close)
    await waitFor(() => expect(screen.getAllByTestId('main-tab')).toHaveLength(1))
    expect(screen.getByTestId('layout-canvas').getAttribute('data-composition')).toBe('SquadComposition-Large')
    fireEvent.click(screen.getAllByTestId('main-tab')[0].querySelector('button')!)
    await waitFor(() => expect(screen.getByTestId('empty-editor')).toBeTruthy())
  })
})

describe('UI1b stale state and activity bar', () => {
  it('does not show style diagnostics from another mode in Game Layouts', async () => {
    problemsResponse = [{ file: 'styles/SIStyles.uss', line: 3, message: 'stale style error' }]
    render(<App />)
    await screen.findByTestId('start')
    fireEvent.click(screen.getByText(TMP))
    await waitFor(() => expect(screen.getByText(TMP.toUpperCase())).toBeTruthy())
    expect(await screen.findByText(/stale style error/)).toBeTruthy()   // visible in the other mode
    fireEvent.click(screen.getByTitle(/Game Layouts \(Playground\)/))
    await screen.findByTestId('game-layouts')
    expect(screen.queryByText(/stale style error/)).toBeNull()
    expect(screen.getByTestId('gl-element').textContent).toContain('No tile selected')
  })

  it('gives every activity entry an accessible name and tooltip; the label setting is remembered', async () => {
    await openGameLayouts()
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    const buttons = within(nav).getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(10)
    for (const b of buttons) {
      expect(b.getAttribute('aria-label')).toBeTruthy()
      expect(b.getAttribute('title')).toBeTruthy()
    }
    expect(screen.getByTitle(/Game Layouts \(Playground\)/)).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Toggle activity bar labels'))
    expect(localStorage.getItem('studio.activityLabels')).toBe('1')
    expect(within(nav).getByText('Game Layouts (Playground)')).toBeTruthy()
  })

  it('stars screens into the Favourites list at the top with per-profile confidence labels', async () => {
    await openGameLayouts()
    const row = (await screen.findAllByTestId('gl-row')).find((r) => r.getAttribute('data-composition') === 'CompetitionStagesBottomTileComposition')!
    const starBtn = within(row).getByTestId('gl-star')
    fireEvent.click(starBtn)
    const favs = screen.getByTestId('gl-favourites')
    const favRow = within(favs).getByTestId('gl-fav-row')
    expect(favRow.getAttribute('data-composition')).toBe('CompetitionStagesBottomTileComposition')
    expect(within(favRow).getByTestId('gl-fav-confidence').textContent).toBe('measured mismatch')

    fireEvent.change(screen.getByTestId('gl-profile'), { target: { value: '2560x1440 windowed, Small, Larger' } })
    await waitFor(() => expect(within(screen.getByTestId('gl-favourites')).getByTestId('gl-fav-confidence').textContent).toBe('computed'))
  })

  it('persists starred favourites in the workspace even if localStorage is cleared', async () => {
    await openGameLayouts()
    const row = (await screen.findAllByTestId('gl-row')).find((r) => r.getAttribute('data-composition') === 'SquadComposition-Large')!
    fireEvent.click(within(row).getByTestId('gl-star'))
    await waitFor(() => expect(favouritesStore).toEqual(['SquadComposition-Large']))

    cleanup()
    localStorage.clear()
    await openGameLayouts()
    await waitFor(() => {
      const favRow = within(screen.getByTestId('gl-favourites')).getByTestId('gl-fav-row')
      expect(favRow.getAttribute('data-composition')).toBe('SquadComposition-Large')
    })
  })
})
