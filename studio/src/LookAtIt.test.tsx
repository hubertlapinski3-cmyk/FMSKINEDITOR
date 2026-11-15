// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import LookAtIt from './LookAtIt'
import { SHOWCASE } from './showcase'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const comp = (value: string) => ({ value, raw: null, tokens: null, source: { sheet: 'S', selector: '.x', specificity: 1 }, unresolved: null, status: 'mapped', note: '', css: [] })
const node = { type: 'VisualElement', name: 'card', classes: ['card'], runtime_classes: [], style: { 'background-color': '#112233', width: '100px' }, text: null, flag: null, matched: [], computed: { 'background-color': comp('#112233') }, children: [] }
const NOTICE = "Approximation, not the game's renderer: bindings and data render as placeholders."
const result = { layout: 'LoansTile_4x2', notice: NOTICE, tree: [node], includes: [], summary: { elements: 1, properties: 1, by_status: { mapped: 1 }, unresolved_variables: {} }, sheet_order: [], gaps: [], timing_ms: { total: 1 } }
const rows = SHOWCASE.map((s, i) => ({ name: s.name, bundle: 'b.bundle', path_id: String(100 + i), elements: 10 }))
const calls = () => (rpc as any).mock.calls as [string, any][]

beforeEach(() => {
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'render.layouts') return { total: rows.length, layouts: rows.filter((r) => r.name.toLowerCase().includes(String(p.q || '').toLowerCase())) }
    if (m === 'render.layout') return result
    throw new Error('unexpected ' + m)
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Look at it', () => {
  it('without a skin it shows only the game, says how to get the other side, and asks for the layout without a project', async () => {
    render(<LookAtIt project={null} say={() => {}} />)
    expect(await screen.findByText('The game as it ships', { selector: 'figcaption' })).toBeTruthy()
    expect(screen.queryByText(/With my skin:/)).toBeNull()
    expect((screen.getByText('With my skin') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByText('Side by side') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/Open or make a skin/)).toBeTruthy()
    await waitFor(() => expect(calls().filter(([m]) => m === 'render.layout').length).toBe(1))
    expect(calls().find(([m]) => m === 'render.layout')![1]).not.toHaveProperty('project')
  })

  it('with a skin it opens side by side: one render without the skin and one with it, both offline renders', async () => {
    render(<LookAtIt project="mine" say={() => {}} />)
    expect(await screen.findByText('The game as it ships', { selector: 'figcaption' })).toBeTruthy()
    expect(await screen.findByText('With my skin: mine', { selector: 'figcaption' })).toBeTruthy()
    await waitFor(() => expect(calls().filter(([m]) => m === 'render.layout').length).toBe(2))
    const asked = calls().filter(([m]) => m === 'render.layout').map(([, p]) => [p.project, p.skin]).sort()
    expect(asked).toEqual([['mine', false], ['mine', true]])
    expect(screen.getAllByTestId('stage').length).toBe(2)
  })

  it('the switch shows one side at a time, and the approximation notice is the engine\'s own, shown once', async () => {
    render(<LookAtIt project="mine" say={() => {}} />)
    await screen.findByText('With my skin: mine', { selector: 'figcaption' })
    expect((await screen.findAllByRole('note')).length).toBe(1)
    expect(screen.getByRole('note').textContent).toBe(NOTICE)
    fireEvent.click(screen.getByText('The game as it ships', { selector: 'button' }))
    await waitFor(() => expect(screen.queryByText('With my skin: mine', { selector: 'figcaption' })).toBeNull())
    expect(screen.getAllByTestId('stage').length).toBe(1)
    fireEvent.click(screen.getByText('With my skin', { selector: 'button' }))
    await waitFor(() => expect(screen.queryByText('The game as it ships', { selector: 'figcaption' })).toBeNull())
    expect(await screen.findByText('With my skin: mine', { selector: 'figcaption' })).toBeTruthy()
  })

  it('a showcase layout is opened by name, and another can be found by searching', async () => {
    render(<LookAtIt project="mine" say={() => {}} />)
    await screen.findByText('With my skin: mine', { selector: 'figcaption' })
    fireEvent.click(screen.getByText('Training tile'))
    await waitFor(() => expect(calls().some(([m, p]) => m === 'render.layout' && p.path_id === String(100 + SHOWCASE.findIndex((s) => s.name === 'TrainingTile_4x4')))).toBe(true))
    fireEvent.change(screen.getByLabelText('Find another layout'), { target: { value: 'Medical' } })
    fireEvent.click(await screen.findByText('MedicalCentreTile_4x2', { selector: 'li button' }))
    await waitFor(() => expect(calls().some(([m, p]) => m === 'render.layout' && p.path_id === String(100 + SHOWCASE.findIndex((s) => s.name === 'MedicalCentreTile_4x2')))).toBe(true))
  })

  it('NEVER asks for a screenshot of the game: no preview call of any kind, through every interaction', async () => {
    render(<LookAtIt project="mine" say={() => {}} />)
    await screen.findByText('With my skin: mine', { selector: 'figcaption' })
    for (const w of ['The game as it ships', 'With my skin', 'Side by side']) fireEvent.click(screen.getByText(w, { selector: 'button' }))
    fireEvent.click(screen.getByText('Tactics tile'))
    await waitFor(() => expect(calls().filter(([m]) => m === 'render.layout').length).toBeGreaterThan(3))
    expect(calls().map(([m]) => m).filter((m) => /^preview\./.test(m))).toEqual([])
  })

  it('with a skin, clicking a part of a picture opens the recolour panel for that part; without a skin nothing opens', async () => {
    ;(rpc as any).mockImplementation(async (m: string, p: any) => {
      if (m === 'render.layouts') return { total: rows.length, layouts: rows.filter((r) => r.name.toLowerCase().includes(String(p.q || '').toLowerCase())) }
      if (m === 'render.layout') return result
      if (m === 'project.get') return { name: 'mine', options: {}, token_overrides: [], literal_swaps: [] }
      if (m === 'simple.literal_info') return { uses: 3, selectors: 1, copied_rules: 3, limit: 50, offered: true }
      throw new Error('unexpected ' + m)
    })
    render(<LookAtIt project="mine" say={() => {}} />)
    await screen.findByText('With my skin: mine', { selector: 'figcaption' })
    expect(screen.getByText(/Click any part of a picture to change its colours/)).toBeTruthy()
    const nodes = await screen.findAllByTitle(/VisualElement#card/)
    fireEvent.click(nodes[nodes.length - 1])
    expect(await screen.findByTestId('recolour')).toBeTruthy()
    expect(screen.getByText('Background')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Close'))
    expect(screen.queryByTestId('recolour')).toBeNull()
    cleanup()
    render(<LookAtIt project={null} say={() => {}} />)
    const n2 = await screen.findAllByTitle(/VisualElement#card/)
    fireEvent.click(n2[0])
    expect(screen.queryByTestId('recolour')).toBeNull()
  })

  it('a layout the build does not have is said in words, not left blank', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => (m === 'render.layouts' ? { total: 0, layouts: [] } : result))
    render(<LookAtIt project="mine" say={() => {}} />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/no layout called LoansTile_4x2/)
  })
})

const sources = import.meta.glob(['./LookAtIt.tsx', './Palette.tsx', './Start.tsx', './Setup.tsx', './PutInGame.tsx', './Pictures.tsx', './pickImage.ts', './Recolour.tsx', './MyColoursStrip.tsx', './colourGroups.ts', './myColours.ts', './showcase.ts', './Preview.tsx'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>
const src = (f: string) => sources['./' + f]

describe('Simple mode shows no screenshot of the game anywhere (source check)', () => {
  const SIMPLE = ['LookAtIt.tsx', 'Palette.tsx', 'Start.tsx', 'Setup.tsx', 'PutInGame.tsx', 'Pictures.tsx', 'pickImage.ts', 'Recolour.tsx', 'MyColoursStrip.tsx', 'colourGroups.ts', 'myColours.ts', 'showcase.ts']
  it('none of the Simple mode components names a preview call, which are the only calls that return a picture of the game', () => {
    for (const f of SIMPLE) { expect(src(f), f + ' was read').toBeTruthy(); expect(src(f), f).not.toMatch(/preview\.(image|live_image|evaluate|models|model_names|live|suggest)\b/) }
  })
  it('only the Advanced Preview tab names them', () => {
    expect(src('Preview.tsx')).toMatch(/preview\.image/)
  })
})
