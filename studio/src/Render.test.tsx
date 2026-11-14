// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RenderBrowser, RenderCanvas, Explain, styleOf, rulePaths, tokenPaths, ruleAtLine, tokenAt, type LayoutRow, type RNode, type Origins } from './Render'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc, subscribe } from './engine'

const comp = (value: string, status: string, extra: Partial<Record<string, any>> = {}) => ({ value, raw: null, tokens: null, source: { sheet: 'AlwaysAppliedStyleSheet', selector: '.card', specificity: 11 },
  unresolved: null, status, note: status === 'unmapped' ? 'transitions are not animated in the render' : '', css: [], ...extra })

const text: RNode = { type: 'SIText', name: 'title', classes: ['sitext', 'heading-md'], runtime_classes: ['sitext'], style: { 'font-size': '16px', 'line-height': '24.4px' }, text: '​', flag: 'unmapped',
  matched: [{ sheet: 'AlwaysAppliedStyleSheet', rule: 747, selector: '.heading-md', specificity: 11 }],
  computed: { 'font-size': comp('16px', 'mapped', { tokens: ['--heading-md-size', '--typography-size-16'] }), 'transition-duration': comp('0.5s', 'unmapped', { inferred_name_from: '-unity-id-393217' }),
    'margin-top': comp('4px', 'mapped'), 'white-space': comp('normal', 'partial') }, children: [] }
const root: RNode = { type: 'VisualElement', name: 'card', classes: ['card'], runtime_classes: [], style: { 'background-color': '#112233', width: '100px', 'flex-grow': '1' }, text: null, flag: null,
  matched: [{ sheet: 'AlwaysAppliedStyleSheet', rule: 3, selector: '.card', specificity: 11 }], computed: { 'background-color': comp('#112233', 'mapped') }, children: [text] }
const result = { layout: 'LoansTile_4x2', notice: 'Approximation, not the game\'s renderer: bindings and data render as placeholders.', tree: [root], includes: [],
  summary: { elements: 2, properties: 5, by_status: { mapped: 3, unmapped: 1, partial: 1 }, unresolved_variables: {} },
  sheet_order: [{ position: 0, sheet: 'default', why: '' }, { position: 1, sheet: 'AlwaysAppliedStyleSheet', why: '' }], gaps: ['three unnamed sheets are not applied'], timing_ms: { total: 1.4 } }
const rows: LayoutRow[] = [{ name: 'LoansTile_2x1', bundle: 'b.bundle', path_id: '1', elements: 9 }, { name: 'LoansTile_4x2', bundle: 'b.bundle', path_id: '2', elements: 19 }]

beforeEach(() => {
  ;(rpc as any).mockImplementation(async (m: string) => (m === 'render.layouts' ? { total: 13, layouts: rows } : m === 'render.layout' ? result : null))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('style mapping', () => {
  it('draws with the UI Toolkit defaults, the node style on top, kebab to camel case', () => {
    const s = styleOf(root)
    expect(s.backgroundColor).toBe('#112233'); expect(s.width).toBe('100px'); expect(s.flexGrow).toBe('1')
    expect(s.flexDirection).toBe('column'); expect(s.alignContent).toBe('flex-start'); expect(s.minWidth).toBe(0)       // Yoga defaults, not CSS's
  })
})

describe('browser', () => {
  it('lists layouts, says how many match, and picks one', async () => {
    const picked = vi.fn()
    render(<RenderBrowser picked={null} onPick={picked} say={() => {}} />)
    expect(await screen.findByText(/GAME LAYOUTS \(13\)/)).toBeTruthy()
    expect(screen.getByText(/Showing the first 2 of 13/)).toBeTruthy()
    fireEvent.click(screen.getByText('LoansTile_4x2'))
    expect(picked).toHaveBeenCalledWith(rows[1])
  })
  it('filters through the engine after a short delay', async () => {
    render(<RenderBrowser picked={null} onPick={() => {}} say={() => {}} />)
    await screen.findByText('LoansTile_2x1')
    fireEvent.change(screen.getByPlaceholderText(/Filter by name/), { target: { value: 'Loans' } })
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('render.layouts', { q: 'Loans', limit: 200 }))
  })
})

describe('canvas and explain', () => {
  it('shows the permanent approximation notice, the fidelity counts and the drawn tree', async () => {
    render(<RenderCanvas layout={rows[1]} say={() => {}} />)
    expect(await screen.findByRole('note')).toBeTruthy()
    expect(screen.getByRole('note').textContent).toContain('placeholders')
    expect(screen.getByText('unmapped 1')).toBeTruthy(); expect(screen.getByText('partial 1')).toBeTruthy()
    const stage = screen.getByTestId('stage')
    expect(stage.querySelectorAll('.rnode').length).toBe(2)
    expect((stage.querySelector('[data-path="0"]') as HTMLElement).style.backgroundColor).toBeTruthy()
    expect(rpc).toHaveBeenCalledWith('render.layout', { bundle: 'b.bundle', path_id: '2' })
  })

  it('a flagged element carries a corner marker that the toggle removes', async () => {
    render(<RenderCanvas layout={rows[1]} say={() => {}} />)
    await screen.findByRole('note')
    const stage = screen.getByTestId('stage')
    expect(stage.querySelector('[data-path="0/0"]')!.getAttribute('data-flag')).toBe('unmapped')
    expect(stage.querySelector('[data-path="0"]')!.getAttribute('data-flag')).toBeNull()          // a clean element has none
    fireEvent.click(screen.getByLabelText(/markers/))
    expect(stage.querySelector('[data-path="0/0"]')!.getAttribute('data-flag')).toBeNull()
  })

  it('clicking an element explains it: matched rules in order, each property with its status, token chain, source and inferred names', async () => {
    render(<RenderCanvas layout={rows[1]} say={() => {}} />)
    await screen.findByRole('note')
    expect(screen.getByText(/Click an element to see/)).toBeTruthy()
    fireEvent.click(screen.getByTestId('stage').querySelector('[data-path="0/0"]')!)
    expect(await screen.findByText('.heading-md')).toBeTruthy()                                  // the matched rule
    expect(screen.getByText('--heading-md-size')).toBeTruthy(); expect(screen.getByText('--typography-size-16')).toBeTruthy()           // the token chain, one clickable chip per token
    expect(screen.getAllByText('unmapped').length).toBeGreaterThan(0)
    expect(screen.getByTitle('transitions are not animated in the render')).toBeTruthy()         // the reason is one hover away
    expect(screen.getByText('inferred')).toBeTruthy()                                           // a name inferred from a property id is marked
    expect(screen.getByText(/runtime classes \(learned\): sitext/)).toBeTruthy()
  })

  it('"flagged only" hides the properties that are drawn faithfully', async () => {
    render(<Explain n={text} />)
    expect(screen.getByText('margin-top')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/flagged only/))
    expect(screen.queryByText('margin-top')).toBeNull()
    expect(screen.getByText('transition-duration')).toBeTruthy(); expect(screen.getByText('white-space')).toBeTruthy()
  })

  it('shows the gaps and sheet order, and an engine failure as text', async () => {
    render(<RenderCanvas layout={rows[1]} say={() => {}} />)
    await screen.findByRole('note')
    expect(screen.getByText(/What this render does not know \(1\)/)).toBeTruthy()
    expect(screen.getByText(/default → AlwaysAppliedStyleSheet/)).toBeTruthy()
    cleanup()
    ;(rpc as any).mockRejectedValue(new Error('no layout bundle'))
    render(<RenderCanvas layout={rows[0]} say={() => {}} />)
    expect(await screen.findByText(/no layout bundle/)).toBeTruthy()
  })

  it('nothing picked: an invitation, no request', () => {
    render(<RenderCanvas layout={null} say={() => {}} />)
    expect(screen.getByText(/Pick a game layout/)).toBeTruthy()
    expect(rpc).not.toHaveBeenCalled()
  })
})

describe('project overlay and the skin toggle', () => {
  it('without a project the render asks for the vanilla layout and shows no toggle', async () => {
    render(<RenderCanvas layout={rows[1]} say={() => {}} />)
    await screen.findByRole('note')
    expect(rpc).toHaveBeenCalledWith('render.layout', { bundle: 'b.bundle', path_id: '2' })
    expect(screen.queryByLabelText(/skin:/)).toBeNull()
  })
  it('with a project the toggle sends skin on and off, and the overlay notes are listed', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => (m === 'render.layout' ? { ...result, overlay: { project: 'demo', output: 'bundles', layout_patch_ops_applied: 2, notes: ['token --x has no definition'], not_applied: ['class renames'] } } : null))
    render(<RenderCanvas layout={rows[1]} say={() => {}} project="demo" />)
    await screen.findByRole('note')
    expect(rpc).toHaveBeenCalledWith('render.layout', { bundle: 'b.bundle', path_id: '2', project: 'demo', skin: true })
    expect(screen.getByText(/Project overlay: demo/)).toBeTruthy()
    expect(screen.getByText('token --x has no definition')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/skin: demo/))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('render.layout', { bundle: 'b.bundle', path_id: '2', project: 'demo', skin: false }))
  })
  it('an invalidate event of the open project repaints, one of another project does not', async () => {
    let on: (t: string, d: any) => void = () => {}
    ;(subscribe as any).mockImplementation((f: any) => { on = f; return () => {} })
    render(<RenderCanvas layout={rows[1]} say={() => {}} project="demo" />)
    await screen.findByRole('note')
    const before = (rpc as any).mock.calls.filter((c: any[]) => c[0] === 'render.layout').length
    on('render.invalidate', { project: 'other', reason: 'tokens' })
    await new Promise((r) => setTimeout(r, 50))
    expect((rpc as any).mock.calls.filter((c: any[]) => c[0] === 'render.layout').length).toBe(before)
    on('render.invalidate', { project: 'demo', reason: 'tokens' })
    await waitFor(() => expect((rpc as any).mock.calls.filter((c: any[]) => c[0] === 'render.layout').length).toBe(before + 1))
  })
})

const card: RNode = { ...root, name: 'card', matched: [{ sheet: 'AlwaysAppliedStyleSheet', rule: 3, selector: '.card', specificity: 11 }, { sheet: 'proj', rule: 0, selector: '.card', specificity: 11, origin: { kind: 'project', sheet: 'AlwaysAppliedStyleSheet', selector: '.card' } } as any],
  computed: { 'background-color': comp('#112233', 'mapped', { tokens: ['--surface', '--colours-ui-soft'], source: { sheet: 'proj', rule: 0, selector: '.card', specificity: 11 } }) }, children: [text] }
const origins: Origins = { rules: [{ file: 'styles/AlwaysAppliedStyleSheet.uss', line: 2, end: 4, selector: '.card', sheet: 'AlwaysAppliedStyleSheet', ids: [{ sheet: 'proj', rule: 0 }] }], tokens: { '--surface': { file: 'styles/tokens.uss', line: 3 } } }

describe('click to rule to token, and back', () => {
  it('finds elements by rule id and by token, and the rule or token under an editor caret', () => {
    expect(rulePaths([card], [{ sheet: 'proj', rule: 0 }])).toEqual(['0'])
    expect(rulePaths([card], [{ sheet: 'proj', rule: 9 }])).toEqual([])
    expect(tokenPaths([card], '--colours-ui-soft')).toEqual(['0'])
    expect(tokenPaths([card], '--other')).toEqual([])
    expect(ruleAtLine(origins, 'styles/AlwaysAppliedStyleSheet.uss', 3)?.selector).toBe('.card')
    expect(ruleAtLine(origins, 'styles/AlwaysAppliedStyleSheet.uss', 5)).toBeNull()
    expect(ruleAtLine(origins, 'styles/other.uss', 3)).toBeNull()
    expect(tokenAt('  color: var(--surface-1);', 15)).toBe('--surface-1')
    expect(tokenAt('  color: red;', 5)).toBeNull()
  })
  it("a project rule opens in the editor at its line; a game rule shows read-only text and offers an override that saves a scoped rule", async () => {
    const open = vi.fn(); const say = vi.fn()
    ;(rpc as any).mockImplementation(async (m: string, p: any) => {
      if (m === 'render.rule') return p.sheet === 'proj' ? { sheet: 'proj', rule: 0, text: '.card {\n  color: red;\n}', vanilla: false, origin: { file: 'styles/AlwaysAppliedStyleSheet.uss', line: 2, end: 4 }, properties: [], token_rule: false }
        : { sheet: p.sheet, rule: p.rule, text: '.card {\n  padding-left: 4px;\n}', vanilla: true, origin: null, properties: [{ name: 'padding-left', value: '4px' }], token_rule: false }
      if (m === 'project.get') return { name: 'demo', scoped_rules: [] }
      return null
    })
    render(<Explain n={card} project="demo" skin origins={origins} onOpenFile={open} say={say} />)
    fireEvent.click(screen.getAllByText('.card')[1])                                         // the project's rule (second row)
    expect(await screen.findByText(/Open styles\/AlwaysAppliedStyleSheet.uss:2 in the editor/)).toBeTruthy()
    fireEvent.click(screen.getByText(/Open styles\/AlwaysAppliedStyleSheet.uss:2/))
    expect(open).toHaveBeenCalledWith('styles/AlwaysAppliedStyleSheet.uss', 2)
    expect(rpc).toHaveBeenCalledWith('render.rule', { sheet: 'proj', rule: 0, project: 'demo', skin: true })
    fireEvent.click(screen.getAllByText('.card')[0])                                         // the game's rule
    expect(await screen.findByText(/game \(read-only\)/)).toBeTruthy()
    fireEvent.click(screen.getByText('Override in demo'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('project.save', { project: { name: 'demo', scoped_rules: [{ sheet: 'AlwaysAppliedStyleSheet', selector: '.card', props: { 'padding-left': '4px' }, why: 'override started from the render' }] } }))
    expect(open).toHaveBeenLastCalledWith('styles/AlwaysAppliedStyleSheet.uss')
  })
  it('a token chip shows its chain and definitions, opens the project override when there is one, and sets one when there is not', async () => {
    const open = vi.fn()
    ;(rpc as any).mockImplementation(async (m: string, p: any) => {
      if (m === 'tokens.get') return { name: p.name, value: '#1E2129', chain: [p.name, '--base'], defs: { AlwaysAppliedStyleSheet: '#1E2129' } }
      if (m === 'project.get') return { name: 'demo', token_overrides: [{ token: '--old', value: '#000000' }] }
      return null
    })
    render(<Explain n={card} project="demo" skin origins={origins} onOpenFile={open} say={() => {}} />)
    fireEvent.click(screen.getByText('--surface'))                                          // has a project override: opens it at its line
    fireEvent.click(await screen.findByText(/Open the project's override \(styles\/tokens.uss:3\)/))
    expect(open).toHaveBeenCalledWith('styles/tokens.uss', 3)
    fireEvent.click(screen.getByText('--colours-ui-soft'))                                  // none yet: set one
    fireEvent.change(await screen.findByPlaceholderText(/new value/), { target: { value: '#FF0000' } })
    fireEvent.click(screen.getByText('Override in demo'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('project.save', { project: { name: 'demo', token_overrides: [{ token: '--old', value: '#000000' }, { token: '--colours-ui-soft', value: '#FF0000' }] } }))
  })
  it('the nodes the editor asks for are outlined in the render', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => (m === 'render.layout' ? { ...result, tree: [card] } : null))
    render(<RenderCanvas layout={rows[1]} say={() => {}} highlight={['0']} />)
    await screen.findByRole('note')
    expect(screen.getByTestId('stage').querySelector('[data-path="0"]')!.className).toContain('hl')
    expect(screen.getByTestId('stage').querySelector('[data-path="0/0"]')!.className).not.toContain('hl')
  })
})
