// @vitest-environment jsdom
/* Stage 5C: the Playground canvas (studio/src/Playground.tsx) and its evidence model. All tests mock the engine's
   render result; no game file is read. The canvas is an inspection and visualisation surface first: per the owner
   finding 5, element addressing is by render position and is NOT a stable operation address until the UiDocument
   join generalises - the view says so on screen. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import Playground, { diagnostics } from './Playground'
import type { InspectResponse, JoinResponse, JoinRow, SessionResponse } from './Playground'
import { rpc } from './engine'
import type { RNode, RResult } from './Render'

const node = (over: Partial<RNode> = {}): RNode => ({
  type: 'VisualElement', name: 'Header', classes: ['dashboard-tile'], runtime_classes: [], style: {}, text: null,
  flag: null, matched: [{ sheet: 'AlwaysAppliedStyleSheet', rule: 4, selector: '.dashboard-tile', specificity: 110 }],
  computed: { background_color: { value: '#171717', raw: null, tokens: ['--surface'], source: { sheet: 'AlwaysAppliedStyleSheet', selector: '.dashboard-tile' }, unresolved: null, status: 'mapped', note: '', css: [['background-color', '#171717']] } },
  children: [], ...over,
})

const tree: RNode[] = [
  node({ name: 'Root', children: [
    node({ name: 'Content', children: [
      node({ name: 'Body', flag: 'unmapped', computed: { color: { value: '#ebebeb', raw: null, tokens: null, source: {}, unresolved: ['--missing'], status: 'unmapped', note: '', css: [] } } }),
    ] }),
  ] }),
]

const result = (): RResult => ({
  layout: 'Loans', notice: 'This render is an approximation; it is not the game.', tree,
  includes: [], truncated: null, summary: { elements: 3, properties: 2, by_status: { mapped: 1, unmapped: 1 }, unresolved_variables: { '--missing': 1 } },
  sheet_order: [{ position: 0, sheet: 'AlwaysAppliedStyleSheet', why: 'base' }], gaps: ['fonts are drawn with stand-in glyphs'],
  timing_ms: { total: 4 }, origins: null, overlay: null,
})

const layouts = { total: 1, layouts: [{ name: 'Loans', bundle: 'ui-tileslayouts_assets_all.bundle', path_id: '11', elements: 3 }] }

const joinRow = (over: Partial<JoinRow> = {}): JoinRow => ({
  logical_id: 'guid1/VisualElement#Header', m_id: '1039390893', bundle: 'ui-tileslayouts_assets_all.bundle', path_id: '11',
  layout: 'Loans', state: 'joined', ...over,
})
const joinOk = (): JoinResponse => ({
  joinable: true, composition: 'SquadComposition-Standard',
  counts: { joined: 3, not_drawn: { root: 1, non_visual: 0 }, unmatched_doc: [], unmatched_render: [] },
  instances: [{ rows: { '0': joinRow(), '0/0': joinRow({ logical_id: 'guid1/VisualElement#Content', m_id: '7' }), '0/0/0': joinRow({ logical_id: 'guid1/VisualElement#Body', m_id: '9' }) }, not_drawn: {} }],
})
const joinNo = (): JoinResponse => ({ joinable: false, reason: 'the layout is reached only as an included layout' })
const inspectOk = (): InspectResponse => ({
  composition: 'SquadComposition-Standard',
  node: { logical_id: 'guid1/VisualElement#Body', structural_key: 'guid1/VisualElement/VisualElement/Body', type: 'VisualElement', name: 'Body', classes: ['dashboard-tile'], locator: { bundle: 'b.bundle', path_id: '11', m_id: '9' }, bundle_sha256: 'ab', render_pos: '0/0/0' },
  properties: [
    { name: 'background-color', value: '#171717', evidence: 'mapped', tokens: ['--surface'], source: { sheet: 'AlwaysAppliedStyleSheet', selector: '.dashboard-tile' }, editable: 'colour', runtime_caveat: false },
    { name: 'padding', value: '12px', evidence: 'mapped', tokens: null, source: { sheet: 'AlwaysAppliedStyleSheet', selector: '.dashboard-tile' }, editable: 'spacing', runtime_caveat: false },
    { name: 'visibility', value: 'visible', evidence: 'mapped', tokens: null, source: null, editable: 'visibility', runtime_caveat: true },
  ],
  selector: { selector: '.dashboard-tile', reason: "the element's own class", reach: { elements: 8, layouts: 4, screens: 4, measured_by: 'layout.reach (static lower bound)', note: 'measured by layout.reach' } },
  colour_routes: { through_token: { token: '--surface', chain: ['--surface'], effect: 'every user of the token changes' }, through_scoped_rule: { selector: '.dashboard-tile', reach: {}, effect: 'only what the selector matches' } },
  visibility_caveat: 'a sheet visibility rule can be overridden at runtime - RUNTIME-DEPENDENT',
})

beforeEach(() => {
  ;(rpc as any).mockImplementation(async (m: string) => {
    if (m === 'render.layouts') return layouts
    if (m === 'render.layout') return result()
    throw new Error('unexpected ' + m)
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const open = async () => {
  render(<Playground project={null} say={() => {}} />)
  const pick = await screen.findAllByText(/Loans/)
  fireEvent.click(pick[0])
  await screen.findAllByTestId('pg-node')
}

describe('Playground: open and navigate', () => {
  it('opens a layout from the browser, draws its elements, and states the approximation and the identity limitation', async () => {
    await open()
    expect(await screen.findAllByTestId('pg-node')).toHaveLength(3)
    expect(screen.getByText(/approximation; it is not the game/)).toBeTruthy()
    expect((await screen.findByTestId('pg-identity-note')).textContent).toContain('render position')
    expect((await screen.findByTestId('pg-tree')).textContent).toContain('VisualElement#Root')
  })

  it('selecting on the canvas selects in the hierarchy; selecting in the tree selects on the canvas', async () => {
    await open()
    const nodes = screen.getAllByTestId('pg-node')
    fireEvent.click(nodes[2])                                                     // the deepest element
    expect(nodes[2].className).toContain('sel')
    const rows = screen.getAllByTestId('pg-row')
    expect(rows[2].className).toContain('sel')
    const other = rows[1]
    fireEvent.click(other)                                                        // the tree drives the canvas
    expect(screen.getAllByTestId('pg-node')[1].className).toContain('sel')
    expect(screen.getByTestId('pg-inspector').textContent).toContain('VisualElement#Content')
  })

  it('hover outlines the element under the pointer (the deepest one, not its ancestors), and a selected element outlines its ancestors', async () => {
    await open()
    const nodes = screen.getAllByTestId('pg-node')
    fireEvent.mouseOver(nodes[2])                                                 // one delegated handler: the deepest node wins
    await waitFor(() => expect(screen.getByTestId('pg-hoverbox')).toBeTruthy())
    expect(screen.getByTestId('pg-hoverinfo').textContent).toContain('0/0/0')
    expect(nodes[0].className).not.toContain('pgh')                              // the ancestors are NOT the hovered element
    fireEvent.click(nodes[2])
    expect(nodes[0].className).toContain('pghl')                                  // parent chain highlighted
    expect(screen.getByTestId('pg-selbox')).toBeTruthy()                          // the selected box overlay
    expect(screen.getByTestId('pg-box').textContent).toContain('offline layout')
  })

  it('hides an element without removing it: the canvas dims it, the tree keeps it, and it comes back', async () => {
    await open()
    const nodes = screen.getAllByTestId('pg-node')
    fireEvent.click(nodes[2])
    fireEvent.click(screen.getByTestId('pg-hide'))
    expect(nodes[2].getAttribute('data-hidden')).toBe('true')
    expect(screen.getAllByTestId('pg-row')).toHaveLength(3)                      // the hierarchy still lists it
    fireEvent.click(screen.getByTestId('pg-hide'))                                // show again
    expect(nodes[2].getAttribute('data-hidden')).toBeNull()
  })

  it('hide/show is a VIEW toggle: it writes no operation - no engine call, no session write (review point 2026-11-18)', async () => {
    await open()
    const afterOpen = (rpc as any).mock.calls.length
    const nodes = screen.getAllByTestId('pg-node')
    fireEvent.click(nodes[2])
    fireEvent.click(screen.getByTestId('pg-hide'))
    fireEvent.click(screen.getByTestId('pg-hide'))
    fireEvent.click(screen.getByTestId('pg-hide'))
    fireEvent.click(screen.getByTestId('pg-hide'))                                // hide, show, hide, show
    expect((rpc as any).mock.calls.length).toBe(afterOpen)                       // no rpc at all, so no session write
    const kinds = (rpc as any).mock.calls.map((c: any[]) => c[0])
    expect(kinds).not.toContain('playground.save')
    expect(kinds).not.toContain('playground.operation')
    expect(screen.getByTestId('pg-hide').getAttribute('title')).toContain('never writes an operation')
  })

  it('zoom in/out/fit and pan change the stage transform', async () => {
    await open()
    fireEvent.click(screen.getByTestId('pg-zoom-in'))
    expect(screen.getByTestId('pg-stage').style.transform).toContain('scale(1.25)')
    fireEvent.click(screen.getByTestId('pg-zoom-out'))
    expect(screen.getByTestId('pg-stage').style.transform).toContain('scale(1)')
    const canvas = screen.getByTestId('pg-canvas')
    fireEvent.mouseDown(canvas, { clientX: 10, clientY: 10 })
    fireEvent.mouseMove(canvas, { clientX: 60, clientY: 40 })
    fireEvent.mouseUp(canvas)
    expect(screen.getByTestId('pg-stage').style.transform).toContain('translate(50px, 30px)')
    fireEvent.click(screen.getByTestId('pg-fit'))
    const t = screen.getByTestId('pg-stage').style.transform                     // jsdom re-serialises the reset pan
    expect(t).toContain('scale(0.15)')                                           // fitted to the (zero-size) container
    expect(t).not.toContain('50px')                                              // and the pan is back at the origin
  })

  it('the tree expands and collapses', async () => {
    await open()
    expect(screen.getAllByTestId('pg-row')).toHaveLength(3)
    fireEvent.click(screen.getAllByText('▾')[0])                                  // collapse the root
    expect(screen.getAllByTestId('pg-row')).toHaveLength(1)
    fireEvent.click(screen.getAllByText('▸')[0])
    expect(screen.getAllByTestId('pg-row')).toHaveLength(3)
  })
})

describe('Playground: diagnostics separate errors from limitations', () => {
  it('unresolved variables and includes are errors; flags, placeholders and gaps are limitations', () => {
    const r = result()
    r.tree[0].children[0].children[0].include = { alias: 'Tile', resolved: false, problem: 'the template was not found' }
    const d = diagnostics(r)
    expect(d.filter((x) => x.level === 'error').map((x) => x.message)).toEqual(expect.arrayContaining([
      expect.stringContaining('unresolved variable (--missing)'),
      expect.stringContaining('did not resolve'),
    ]))
    expect(d.filter((x) => x.level === 'limitation').map((x) => x.message)).toEqual(expect.arrayContaining([
      expect.stringContaining('unmapped - the value is shown as a best effort'),
      expect.stringContaining('stand-in'),
    ]))
  })

  it('clicking a node diagnostic selects the node it belongs to', async () => {
    await open()
    const error = screen.getAllByTestId('pg-diag').find((x) => x.dataset.level === 'error')
    fireEvent.click(error!)
    const nodes = screen.getAllByTestId('pg-node')
    expect(nodes[2].className).toContain('sel')
  })

  it('a failed render shows the engine error instead of a blank screen', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') throw new Error('no vanilla snapshot; take one first')
    })
    render(<Playground project={null} say={() => {}} />)
    fireEvent.click((await screen.findAllByText(/Loans/))[0])
    await waitFor(() => expect(screen.getByText(/no vanilla snapshot/)).toBeTruthy())
  })
})

describe('Playground: the UiDocument join (step 3)', () => {
  it('on a joined screen the canvas addresses by UiDocument identity and says so', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinOk()
      throw new Error('unexpected ' + m)
    })
    await open()
    const note = await screen.findByTestId('pg-identity-note')
    expect(note.textContent).toContain('UiDocument identity')
    expect(note.textContent).toContain('SquadComposition-Standard')
    expect(note.textContent).toContain('3 joined')
    const nodes = screen.getAllByTestId('pg-node')
    fireEvent.click(nodes[2])
    expect((await screen.findByTestId('pg-identity-id')).textContent).toContain('guid1/VisualElement#Body')
    expect(screen.getByTestId('pg-identity-locator').textContent).toContain('m_Id 9')
  })

  it('the hover line names the UiDocument identity on a joined screen', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinOk()
      throw new Error('unexpected ' + m)
    })
    await open()
    const nodes = screen.getAllByTestId('pg-node')
    fireEvent.click(nodes[2])
    fireEvent.mouseOver(nodes[2])
    await waitFor(() => expect(screen.getByTestId('pg-hoverinfo').textContent).toContain('guid1/VisualElement#Body'))
  })

  it('without a built join the render-path caveat stands', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinNo()
      throw new Error('unexpected ' + m)
    })
    await open()
    const note = await screen.findByTestId('pg-identity-note')
    expect(note.textContent).toContain('render position')
    expect(note.textContent).not.toContain('SquadComposition-Standard')
    const nodes = screen.getAllByTestId('pg-node')
    fireEvent.click(nodes[2])
    expect(screen.getByTestId('pg-identity').textContent).toContain('not joined on this screen')
  })

  it('a failed join call is silent: the caveat stays, no error is shown', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') throw new Error('no layout dump is imported')
      throw new Error('unexpected ' + m)
    })
    await open()
    const note = await screen.findByTestId('pg-identity-note')
    expect(note.textContent).toContain('render position')
    expect(screen.queryByText(/no layout dump/)).toBeNull()
  })
})

describe('Playground: the 5D editable inspector (joined nodes only, backend-classified)', () => {

  const withInspect = async () => {
    await open()
    fireEvent.click(screen.getAllByTestId('pg-node')[2])
    await screen.findByTestId('pg-edit')
  }

  it('a joined node gets the editable surface: evidence, measured reach, the scope warning and the runtime caveat', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinOk()
      if (m === 'uidoc.inspect') return inspectOk()
      throw new Error('unexpected ' + m)
    })
    await withInspect()
    expect(screen.getByTestId('pg-edit-selector').textContent).toContain('measured reach 8 element(s)')
    expect(screen.getByTestId('pg-edit-scope').textContent).toContain('scope change')
    expect(screen.getByTestId('pg-edit-caveat').textContent).toContain('RUNTIME-DEPENDENT')
    expect(screen.getAllByTestId('pg-edit-prop').length).toBe(3)
  })

  it('the backend refuses a colour edit without its route, and the refusal is shown verbatim', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinOk()
      if (m === 'uidoc.inspect') return inspectOk()
      if (m === 'uidoc.classify') return { refused: 'SetColor needs its route recorded: chosen None with a reason. ...' }
      throw new Error('unexpected ' + m)
    })
    await withInspect()
    fireEvent.click(screen.getAllByTestId('pg-edit-prop')[0])
    fireEvent.change(screen.getByTestId('pg-edit-value'), { target: { value: '#112233' } })
    fireEvent.click(screen.getByTestId('pg-classify'))
    const verdict = await screen.findByTestId('pg-verdict')
    expect(verdict.textContent).toContain('refused by the backend')
    expect(verdict.textContent).toContain('needs its route recorded')
  })

  it('a classified edit shows the backend verdict: the scope class and the writer, never a local decision', async () => {
    let sent: any = null
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinOk()
      if (m === 'uidoc.inspect') return inspectOk()
      if (m === 'uidoc.classify') { sent = b; return { validation: { ok: true, safety: 'scope', translation: { fragment: 'scoped_rules', writer: 'patcher.patch_sheet (append or the declared replace); the structural gate checks every rule' }, scope: { elements: 8, scope_change: true }, findings: ['scope change: the selector .dashboard-tile reaches more than the selected element'] } } }
      throw new Error('unexpected ' + m)
    })
    await withInspect()
    fireEvent.click(screen.getAllByTestId('pg-edit-prop')[0])
    fireEvent.change(screen.getByTestId('pg-edit-value'), { target: { value: '#112233' } })
    fireEvent.click(screen.getByTestId('pg-classify'))
    const verdict = await screen.findByTestId('pg-verdict')
    expect(verdict.textContent).toContain('scope change')
    expect(verdict.textContent).toContain('patcher.patch_sheet')
    expect(sent.kind).toBe('SetColor')
    expect(sent.props).toEqual({ 'background-color': '#112233' })
    expect(sent.route.chosen).toBe('scoped_rule')
  })

  it('the token route sends ReplaceToken with the token the inspector named', async () => {
    let sent: any = null
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinOk()
      if (m === 'uidoc.inspect') return inspectOk()
      if (m === 'uidoc.classify') { sent = b; return { validation: { ok: true, safety: 'value', translation: { fragment: 'token_overrides', writer: 'token_patch.SheetPatcher' } } } }
      throw new Error('unexpected ' + m)
    })
    await withInspect()
    fireEvent.click(screen.getAllByTestId('pg-edit-prop')[0])
    fireEvent.change(screen.getByTestId('pg-edit-value'), { target: { value: '#112233' } })
    fireEvent.click(screen.getAllByRole('radio')[1])                  // the token route
    fireEvent.click(screen.getByTestId('pg-classify'))
    await screen.findByTestId('pg-verdict')
    expect(sent.kind).toBe('ReplaceToken')
    expect(sent.token).toBe('--surface')
  })

  it('a node without a join gets no editor at all', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinNo()
      throw new Error('unexpected ' + m)
    })
    await open()
    fireEvent.click(screen.getAllByTestId('pg-node')[2])
    await waitFor(() => expect(screen.getByTestId('pg-identity').textContent).toContain('not joined on this screen'))
    expect(screen.queryByTestId('pg-edit')).toBeNull()
  })
})

describe('Playground: 5E gestures and the session', () => {
  const screensList = { total: 1, screens: [{ name: 'SquadComposition-Standard', preset: [16, 10], cells: [
    { cell_index: 0, element_id: 'Training', x: 12, y: 4, w: 4, h: 2, flags: [] },
    { cell_index: 1, element_id: 'Atmosphere', x: 12, y: 6, w: 4, h: 2, flags: [] },
  ] }] }
  const screenResult = {
    composition: 'SquadComposition-Standard', pitch: { stride: 82, gap: 16 },
    grid: { cols: 20, rows: 10 },
    hosts: [
      { element_id: 'Training', col: 12, row: 4, w: 4, h: 2, px: { left: 12 + 82 * 12, top: 12 + 82 * 4, width: 82 * 4 - 16, height: 82 * 2 - 16 }, tile_layout: 'TrainingTile', tile_how: 'MEASURED', mode: ['fixed'] },
      { element_id: 'Atmosphere', col: 12, row: 6, w: 4, h: 2, px: { left: 12 + 82 * 12, top: 12 + 82 * 6, width: 82 * 4 - 16, height: 82 * 2 - 16 }, tile_layout: 'AtmosphereTile', tile_how: 'MEASURED', mode: ['fixed'] },
    ],
  }
  const sessionOf = (n: number): SessionResponse => ({
    session: { schema: 'fm-playsession/1', project: 'pg', screen: null, game_build: '27.1', operations: n ? [{ id: 'op-1', kind: 'MoveNode', state: 'applied' }] : [] },
    projection: n ? { placements: [{ composition: 'SquadComposition-Standard' }] } : { token_overrides: [], scoped_rules: [], image_swaps: [], placements: [] },
    counts: { total: n, applied: n },
  })

  const openScreen = async () => {
    render(<Playground project="pg" say={vi.fn()} />)
    fireEvent.click(screen.getByTestId('pg-mode-screen'))
    await screen.findByTestId('pg-screen-row')
    fireEvent.click(screen.getByTestId('pg-screen-row'))
    await screen.findAllByTestId('pg-tile')
  }

  it('the screen mode draws the composition\u2019s tiles and the session history appears', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return sessionOf(0)
      throw new Error('unexpected ' + m)
    })
    await openScreen()
    expect(screen.getAllByTestId('pg-tile')).toHaveLength(2)
    expect(screen.getByTestId('pg-screen-name').textContent).toContain('SquadComposition-Standard')
    expect(screen.getByTestId('pg-session').textContent).toContain('0 applied / 0 total')
  })

  it('a tile drag snaps to the grid stride, the backend gate runs as it moves, and a valid drop records a MoveNode', async () => {
    const ops: any[] = []
    let applied = 0
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return sessionOf(applied)
      if (m === 'playground.validate_move') return { valid: true, blocks: [], warnings: [], collisions: [], cell_element_id: 'Training', x: b.geometry.x, y: b.geometry.y }
      if (m === 'playground.build_operation') return { gate: { valid: true }, operation: { schema: 'fm-playop/1', id: 'op-backend', kind: 'MoveNode', target: { cell: { composition: b.composition, cell_index: b.cell_index, cell_element_id: 'Training', geometry: b.geometry } } }, validation: { ok: true, safety: 'value' } }
      if (m === 'playground.add_operation') { ops.push(b.operation); applied = 1; return sessionOf(1) }
      throw new Error('unexpected ' + m)
    })
    await openScreen()
    const tile = screen.getAllByTestId('pg-tile')[0]
    fireEvent.mouseDown(tile)
    fireEvent.mouseMove(tile, { clientX: 82, clientY: 82 })          // exactly one stride right and down
    await waitFor(() => expect(screen.getAllByTestId('pg-tile')[0].style.left).toBe((12 + 82 * 13) + 'px'))
    fireEvent.mouseUp(tile)
    await waitFor(() => expect(ops).toHaveLength(1))
    expect(ops[0].kind).toBe('MoveNode')
    expect(ops[0].target.cell).toEqual({ composition: 'SquadComposition-Standard', cell_index: 0, cell_element_id: 'Training', geometry: { x: 13, y: 5, w: 4, h: 2 } })
    await waitFor(() => expect(screen.getByTestId('pg-session').textContent).toContain('1 applied / 1 total'))
  })

  it('an overlapping drag shows the gate refusal at the tile and records nothing', async () => {
    const ops: any[] = []
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return sessionOf(0)
      if (m === 'playground.validate_move') return { valid: false, blocks: [], warnings: [], collisions: [{ cell_index: 1, element_id: 'Atmosphere', geometry: { x: 12, y: 5, w: 4, h: 2 } }], cell_element_id: 'Training', x: b.geometry.x, y: b.geometry.y }
      if (m === 'playground.add_operation') { ops.push(b.operation); return sessionOf(1) }
      throw new Error('unexpected ' + m)
    })
    await openScreen()
    const tile = screen.getAllByTestId('pg-tile')[0]
    fireEvent.mouseDown(tile)
    fireEvent.mouseMove(tile, { clientX: 82, clientY: 0 })
    await waitFor(() => expect(screen.getAllByTestId('pg-gate').length).toBeGreaterThan(0))
    expect(screen.getByTestId('pg-gate').textContent).toContain('Atmosphere')
    fireEvent.mouseUp(tile)
    await waitFor(() => expect(screen.queryByTestId('pg-gate')).toBeNull())
    expect(ops).toHaveLength(0)
  })

  it('the resize handle is a BUILDABLE enlargement now (Test C): the gate runs and a valid drop records a ResizeNode', async () => {
    const ops: any[] = []
    let applied = 0
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return sessionOf(applied)
      if (m === 'playground.validate_move') return { valid: true, blocks: [], warnings: ['limits change with the edit'], collisions: [], cell_element_id: 'Training', x: b.geometry.x, y: b.geometry.y, w: b.geometry.w, h: b.geometry.h }
      if (m === 'playground.build_operation') return { gate: { valid: true }, operation: { schema: 'fm-playop/1', id: 'op-backend-rz', kind: 'ResizeNode', label: 'Resize Training 4x2 -> 5x2 in SquadComposition-Standard', target: { cell: { composition: b.composition, cell_index: b.cell_index, cell_element_id: 'Training', geometry: b.geometry, max_size: b.max_size } } }, validation: { ok: true, safety: 'value' } }
      if (m === 'playground.add_operation') { ops.push(b.operation); applied = 1; return sessionOf(1) }
      throw new Error('unexpected ' + m)
    })
    await openScreen()
    const tile = screen.getAllByTestId('pg-tile')[0]
    fireEvent.mouseDown(screen.getAllByTestId('pg-resize')[0])
    fireEvent.mouseMove(tile, { clientX: 82, clientY: 0 })          // one grid unit wider
    await waitFor(() => expect(screen.getAllByTestId('pg-tile')[0].style.width).toBe((82 * 5 - 16) + 'px'))
    fireEvent.mouseUp(tile)
    await waitFor(() => expect(ops).toHaveLength(1))
    expect(ops[0].kind).toBe('ResizeNode')
    expect(ops[0].target.cell).toEqual({ composition: 'SquadComposition-Standard', cell_index: 0, cell_element_id: 'Training',
                                         geometry: { x: 12, y: 4, w: 5, h: 2 }, max_size: { x: 5, y: 2 } })
    expect(ops[0].id).toBe('op-backend-rz')            // the record is the BACKEND's build, not a browser assembly
  })

  it('the session history labels a resize with its composition and marks it inactive at another preview size', async () => {
    const resizeSession = {
      session: { schema: 'fm-playsession/1', project: 'pg', screen: null, game_build: '27.1', operations: [
        { id: 'op-rz', kind: 'ResizeNode', state: 'applied',
          label: 'Resize Atmosphere 4x2 -> 4x4 in SquadComposition-Large',
          target: { cell: { composition: 'SquadComposition-Large', cell_index: 0 } } },
      ] },
      projection: { token_overrides: [], scoped_rules: [], image_swaps: [], placements: [] },
      counts: { total: 1, applied: 1 },
    }
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return resizeSession
      if (m === 'render.preview') return {
        screen: 'SquadComposition-Standard', composition: 'SquadComposition-Standard', breakpoint: 2,
        width: 1600, height: 900, setting: 'Large UI',
        information_display: { setting: 'Large UI', locked: false, reason: 'available', evidence: 'MEASURED' },
        state_options: [], selection: { label: 'estimate', evidence: 'ESTIMATE', measured_points: [],
          corroborating_points: [], source: { kind: 'serialized', asset: 'x' },
          cross_check: { status: 'AGREE', dump_rows: 0, keys_compared: [], gaps: [] }, gaps: [] },
        grid: { cols: 20, rows: 11, pitch: { cell: 67.1, gap: 14.4, measured: true, label: 'MEASURED' } },
        competition: { bundesliga: false, default: false, label: '', sheet: '', bundle: '', rules: 0, evidence: '', note: '' },
        hosts: [], cells: [], slots: [],
        game_states: { scenario: '', defaults: {}, values: {}, options: [] },
        operations: { applied: [], pending: [] }, measured: [], estimated: [], notice: '',
      }
      throw new Error('unexpected ' + m)
    })
    await openScreen()
    const op = await screen.findByTestId('pg-op')
    expect(op.textContent).toContain('Resize Atmosphere 4x2 -> 4x4 in SquadComposition-Large')
    expect(screen.getByTestId('pg-op-scope').textContent).toContain('SquadComposition-Large')
    await waitFor(() => expect(screen.getByTestId('pg-op-inactive').textContent).toContain('SquadComposition-Standard'))
  })

  it('add-tile is a CANDIDATE gesture: the backend gate checks uniqueness, overlap and the description, and a valid place records an AddCell', async () => {
    const ops: any[] = []
    let applied = 0
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return sessionOf(applied)
      if (m === 'uidoc.join') return { joinable: true, composition: 'SquadComposition-Standard', cell_configurations: [{ cell_index: 0, element_id: 'Training', min_size: { x: 4, y: 2 }, max_size: { x: 4, y: 2 }, descriptions: [{ path_id: '77', read: true, name: 'TrainingTileDescription', id: 'TrainingTile', configurations: [{ size: { x: 4, y: 2 }, type: 0, asset_guid: 'aaaaaaaaaaaaaaaa' }] }] }] }
      if (m === 'playground.validate_add') return { valid: true, blocks: [], warnings: [], collisions: [], configuration: { description_id: 'TrainingTile', path_id: '77', config_index: 0, size: { x: 4, y: 2 } } }
      if (m === 'playground.build_operation') return { gate: { valid: true }, operation: { schema: 'fm-playop/1', id: 'op-backend-add', kind: 'AddCell', target: { cell: { composition: b.composition, cell_index: b.cell_index, cell_element_id: b.element_id, geometry: b.geometry, description: { path_id: '77', config_index: 0 } } } }, validation: { ok: true, safety: 'candidate' } }
      if (m === 'playground.add_operation') { ops.push(b.operation); applied = 1; return sessionOf(1) }
      throw new Error('unexpected ' + m)
    })
    await openScreen()
    fireEvent.click(screen.getByTestId('pg-add-toggle'))
    fireEvent.change(screen.getByTestId('pg-add-desc'), { target: { value: '77' } })
    fireEvent.click(screen.getByTestId('pg-stage'))
    await waitFor(() => expect(ops).toHaveLength(1))
    expect(ops[0].kind).toBe('AddCell')
    expect(ops[0].target.cell.cell_element_id).toBe('AddedTile2')
    expect(ops[0].target.cell.description).toEqual({ path_id: '77', config_index: 0 })
    expect(ops[0].id).toBe('op-backend-add')           // the record is the BACKEND's build, not a browser assembly
  })

  it('undo goes through the 5B history', async () => {
    const undos: any[] = []
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return sessionOf(1)
      if (m === 'playground.undo') { undos.push(b); return { undone: 'op-1' } }
      throw new Error('unexpected ' + m)
    })
    await openScreen()
    fireEvent.click(screen.getByTestId('pg-undo'))
    await waitFor(() => expect(undos).toHaveLength(1))
    expect(undos[0].project).toBe('pg')
  })

  it('a classified edit can be recorded as an operation (undoable)', async () => {
    const ops: any[] = []
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      if (m === 'render.layouts') return layouts
      if (m === 'render.layout') return result()
      if (m === 'uidoc.join') return joinOk()
      if (m === 'uidoc.inspect') return inspectOk()
      if (m === 'uidoc.classify') return { validation: { ok: true, safety: 'scope', translation: { fragment: 'scoped_rules', writer: 'patcher.patch_sheet' } }, operation: { id: 'op-x', schema: 'fm-playop/1' } }
      if (m === 'playground.session') return sessionOf(0)
      if (m === 'playground.add_operation') { ops.push(b.operation); return sessionOf(1) }
      throw new Error('unexpected ' + m)
    })
    render(<Playground project="pg" say={vi.fn()} />)
    fireEvent.click((await screen.findAllByText(/Loans/))[0])
    await screen.findAllByTestId('pg-node')
    fireEvent.click(screen.getAllByTestId('pg-node')[2])
    await screen.findByTestId('pg-edit')
    fireEvent.click(screen.getAllByTestId('pg-edit-prop')[0])
    fireEvent.change(screen.getByTestId('pg-edit-value'), { target: { value: '#112233' } })
    fireEvent.click(screen.getByTestId('pg-classify'))
    const record = await screen.findByTestId('pg-record')
    fireEvent.click(record)
    await waitFor(() => expect(ops).toHaveLength(1))
    expect(ops[0].id).toBe('op-x')
    expect(screen.getByTestId('pg-verdict').textContent).toContain('recorded in the session')
  })
})

describe('Playground: 5F preview controls (the browser renders what the backend returns)', () => {
  const screensList = { total: 1, screens: [{ name: 'SquadComposition-Standard', preset: [16, 10], cells: [
    { cell_index: 0, element_id: 'Training', x: 12, y: 4, w: 4, h: 2, flags: [] },
  ] }] }
  const screenResult = {
    composition: 'SquadComposition-Standard', pitch: { stride: 82, gap: 16 }, grid: { cols: 20, rows: 10 },
    hosts: [{ element_id: 'Training', col: 12, row: 4, w: 4, h: 2, px: { left: 996, top: 340, width: 312, height: 148 },
              tile_layout: 'TrainingTile', tile_how: 'MEASURED', mode: ['fixed'] }],
  }
  const sessionEmpty = { session: { schema: 'fm-playsession/1', project: 'pg', screen: null, game_build: '27.1', operations: [] },
                         projection: { token_overrides: [], scoped_rules: [], image_swaps: [], placements: [] },
                         counts: { total: 0, applied: 0 } }

  const previewOf = (over: any = {}) => ({
    screen: 'SquadComposition-Standard', composition: 'SquadComposition-Standard', breakpoint: 2,
    width: 1600, height: 900, setting: 'Large UI',
    information_display: { setting: 'Large UI', locked: false, reason: 'available', evidence: 'MEASURED' },
    state_options: [
      { state: 'normal', label: 'normal', evidence: 'always offered' },
      { state: 'hover', label: 'hover', evidence: 'offered: a normal interaction state' },
      { state: 'pressed', label: 'pressed / active', evidence: 'offered: a normal interaction state' },
      { state: 'checked', label: 'checked', evidence: 'the sheets declare a :checked rule' },
    ],
    selection: {
      label: 'MEASURED at 1440x900 (windowed, Large UI): Stage 3E', evidence: 'MEASURED',
      measured_points: [
        { width: 1024, height: 768, window_mode: null, ui_setting: null, composition: 'Small', attempt: 'a' },
        { width: 1440, height: 900, window_mode: 'windowed', ui_setting: 'Large UI', composition: 'Standard', attempt: 'b' },
      ],
      corroborating_points: [],
      source: { kind: 'serialized', asset: 'm_gridBreakpointCompositionData', set: 'SquadTileCompositionSet' },
      cross_check: { status: 'AGREE', dump_rows: 3, keys_compared: [1, 2, 3], gaps: [] },
      gaps: [],
    },
    grid: { cols: 20, rows: 11, pitch: { cell: 67.1, gap: 14.4, measured: true, label: 'MEASURED' } },
    competition: { bundesliga: false, default: false, label: 'preview data', sheet: 'Bundesliga',
                   bundle: 'ui-styles_assets_default.bundle', rules: 22,
                   evidence: 'measured on archived set C', note: 'preview data, off by default' },
    hosts: [], cells: [], slots: [
      { id: 'binding:ClubTeamReport', kind: 'placement_binding', element_id: 'ClubTeamReport', direction: 'placement_binding',
        location: null, conditions: ['game.IsFantasyDraftGame (inverse check)'], config_conditions: [],
        default: true, visible: true, label: 'preview data: visibility follows the game states, inverse flags applied' },
    ],
    game_states: { scenario: 'ordinary career game, not in a match',
                   defaults: { 'game.IsDuringMatch': false, 'game.IsFantasyDraftGame': false },
                   values: { 'game.IsDuringMatch': false, 'game.IsFantasyDraftGame': false },
                   options: [{ state: 'game.IsFantasyDraftGame', value: false, default: false,
                               evidence: 'preview data: the state values the slot conditions are evaluated with' }] },
    operations: { applied: [], pending: [] },
    measured: ['the breakpoint keys are the composition set\'s serialized m_gridBreakpointCompositionData'],
    estimated: [], notice: 'deterministic',
    ...over,
  })
  const compareOf = () => ({
    a: { width: 1600, height: 900, composition: 'SquadComposition-Standard', selection: 'ESTIMATE', evidence: 'ESTIMATE' },
    b: { width: 1920, height: 1080, composition: 'SquadComposition-Large', selection: 'MEASURED', evidence: 'MEASURED' },
    cells: { appear: [{ element_id: 'Extra' }], disappear: [{ element_id: 'Gone' }],
             changed: [{ element_id: 'Training', from: { x: 1 }, to: { x: 2 } }] },
  })

  const setup = (over: any = {}) => {
    const calls: any[] = []
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      calls.push([m, b])
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'playground.session') return sessionEmpty
      if (m === 'render.preview') return previewOf({ width: b.width, height: b.height, ...over })
      if (m === 'render.preview_compare') return compareOf()
      if (m === 'project.routing') return {
        project: 'pg', route_preference: 'bundle', route_preference_explicit: false,
        edit_competition_sheets: false, edit_competition_sheets_explicit: false, default: 'bundle',
        tradeoffs: { bundle: 'changes the game files; can move tiles and edit the winning declaration',
                     skin_folder: 'writes only the skin folder and changes no game file',
                     edit_competition_sheets: 'off by default; a separate explicit choice' },
        note: 'bundle is the default; skin-folder is an explicit choice' }
      if (m === 'project.set_routing') return {
        project: 'pg', route_preference: b.route_preference ?? 'bundle', route_preference_explicit: true,
        edit_competition_sheets: b.edit_competition_sheets ?? false, edit_competition_sheets_explicit: true,
        default: 'bundle',
        tradeoffs: { bundle: 'changes the game files; can move tiles and edit the winning declaration',
                     skin_folder: 'writes only the skin folder and changes no game file',
                     edit_competition_sheets: 'off by default; a separate explicit choice' },
        note: 'bundle is the default; skin-folder is an explicit choice' }
      throw new Error('unexpected ' + m)
    })
    return calls
  }

  const openPreview = async () => {
    render(<Playground project="pg" say={vi.fn()} />)
    fireEvent.click(screen.getByTestId('pg-mode-screen'))
    fireEvent.click(await screen.findByTestId('pg-screen-row'))
    await screen.findByTestId('pg-preview')
  }

  it('renders the backend preview and every control', async () => {
    setup()
    await openPreview()
    expect(screen.getByTestId('pg-preview-selection').textContent).toContain('MEASURED at 1440x900')
    expect(screen.getByTestId('pg-preview-source').textContent).toContain('m_gridBreakpointCompositionData')
    expect(screen.getByTestId('pg-preview-preset')).toBeTruthy()
    expect(screen.getByTestId('pg-preview-width')).toBeTruthy()
    expect(screen.getByTestId('pg-preview-height')).toBeTruthy()
    expect(screen.getByTestId('pg-preview-state')).toBeTruthy()
    expect(screen.getByTestId('pg-preview-setting')).toBeTruthy()
    expect(screen.getByTestId('pg-preview-sim')).toBeTruthy()
    expect(screen.getAllByTestId('pg-preview-slot')).toHaveLength(1)
  })

  it('the build routing control states the trade-off and saves an explicit choice', async () => {
    const calls = setup()
    await openPreview()
    expect(screen.getByTestId('pg-build-routing').textContent).toContain('changes the game files')
    fireEvent.click(screen.getByTestId('pg-build-route-skin'))
    await waitFor(() => expect(calls.filter((c) => c[0] === 'project.set_routing').some(
      (c) => c[1].route_preference === 'skin_folder')).toBe(true))
    fireEvent.click(screen.getByTestId('pg-build-edit-competition'))
    await waitFor(() => expect(calls.filter((c) => c[0] === 'project.set_routing').some(
      (c) => c[1].edit_competition_sheets === true)).toBe(true))
    expect(screen.getByTestId('pg-build-routing').textContent).toContain('off by default')
  })

  it('the state switch offers only the states the backend returns', async () => {
    setup()
    await openPreview()
    const sel = screen.getByTestId('pg-preview-state') as HTMLSelectElement
    const values = Array.from(sel.options).map((o) => o.value)
    expect(values).toEqual(['normal', 'hover', 'pressed', 'checked'])
    expect(values).not.toContain('selected')                 // no :selected rule on this screen
    expect(values).not.toContain('focus')
  })

  it('a locked Information Display combination is shown as locked by the game', async () => {
    setup({ information_display: { setting: 'Large UI', locked: true, reason: 'locked by the game: the unlock is a game runtime patch',
                                   evidence: 'ESTIMATE (B-build fact)' } })
    await openPreview()
    expect(screen.getByTestId('pg-preview-info').textContent).toContain('locked by the game')
  })

  it('a resolution preset switches the backend preview and sends no session-changing call', async () => {
    const calls = setup()
    await openPreview()
    fireEvent.change(screen.getByTestId('pg-preview-preset'), { target: { value: '1024x768' } })
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').some((c) => c[1].width === 1024 && c[1].height === 768)).toBe(true))
    const kinds = calls.map((c) => c[0])
    expect(kinds).not.toContain('playground.add_operation')
    expect(kinds).not.toContain('playground.save')
    expect(kinds).not.toContain('playground.undo')
  })

  it('a custom width and height are sent as entered', async () => {
    const calls = setup()
    await openPreview()
    fireEvent.change(screen.getByTestId('pg-preview-width'), { target: { value: '1300' } })
    fireEvent.change(screen.getByTestId('pg-preview-height'), { target: { value: '820' } })
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').some((c) => c[1].width === 1300 && c[1].height === 820)).toBe(true))
  })

  it('the state switch sends the chosen state and no session-changing call', async () => {
    const calls = setup()
    await openPreview()
    fireEvent.change(screen.getByTestId('pg-preview-state'), { target: { value: 'hover' } })
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').some((c) => JSON.stringify(c[1].states) === '["hover"]')).toBe(true))
    expect(calls.map((c) => c[0])).not.toContain('playground.add_operation')
  })

  it('the seed changes placeholders only (no session-changing call)', async () => {
    const calls = setup()
    await openPreview()
    fireEvent.change(screen.getByTestId('pg-preview-seed'), { target: { value: 'another' } })
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').some((c) => c[1].seed === 'another')).toBe(true))
    expect(calls.map((c) => c[0])).not.toContain('playground.add_operation')
  })

  it('in an ordinary career the inverse-conditioned slot is visible, and the game-state toggle drives it', async () => {
    const calls = setup()
    await openPreview()
    const slot = screen.getByTestId('pg-preview-slot')
    expect(slot.getAttribute('data-visible')).toBe('true')       // career: IsFantasyDraftGame false + inverse
    const box = screen.getByTestId('pg-preview-game-state') as HTMLInputElement
    expect(box.checked).toBe(false)
    fireEvent.click(box)                                         // now a Fantasy Draft game
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').some(
      (c) => c[1].game_states && c[1].game_states['game.IsFantasyDraftGame'] === true)).toBe(true))
  })

  it('changing a game state sends the preview call only, never a session-changing call', async () => {
    const calls = setup()
    await openPreview()
    const before = calls.filter((c) => c[0] === 'render.preview').length
    fireEvent.click(screen.getByTestId('pg-preview-game-state'))
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').length).toBeGreaterThan(before))
    const latest = calls.filter((c) => c[0] === 'render.preview').pop()
    expect(latest![1].game_states['game.IsFantasyDraftGame']).toBe(true)
    const kinds = calls.map((c) => c[0])
    expect(kinds).not.toContain('playground.add_operation')
    expect(kinds).not.toContain('playground.save')
    expect(kinds).not.toContain('playground.undo')
    expect(kinds).not.toContain('playground.validate_move')
  })

  it('slot visibility is rendered exactly as the backend returns it', async () => {
    setup({ slots: [
      { id: 'binding:ClubTeamReport', kind: 'placement_binding', element_id: 'ClubTeamReport', direction: 'placement_binding',
        location: null, conditions: ['game.IsFantasyDraftGame (inverse check)'], config_conditions: [],
        default: true, visible: true, label: 'preview data' },
      { id: 'm_top:MatchOnly', kind: 'optional_slice', element_id: 'MatchOnly', direction: 'm_top',
        location: { x: 8, y: 0, width: 4, height: 2 }, conditions: ['game.IsDuringMatch'], config_conditions: [],
        default: false, visible: false, label: 'preview data' },
    ] })
    await openPreview()
    const slots = screen.getAllByTestId('pg-preview-slot')
    expect(slots).toHaveLength(2)
    expect(slots[0].getAttribute('data-visible')).toBe('true')
    expect(slots[0].textContent).toContain('ClubTeamReport')
    expect(slots[1].getAttribute('data-visible')).toBe('false')
    expect(slots[1].textContent).toContain('MatchOnly')
  })

  it('the simulated-content toggle hides simulated content in the backend preview', async () => {
    const calls = setup()
    await openPreview()
    fireEvent.click(screen.getByTestId('pg-preview-sim'))
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').some((c) => c[1].simulated_visible === false)).toBe(true))
  })

  it('the Bundesliga competition context is off by default, preview data, and sent with preview calls only', async () => {
    const calls = setup()
    await openPreview()
    const box = screen.getByTestId('pg-preview-competition') as HTMLInputElement
    expect(box.checked).toBe(false)
    expect(screen.getByTestId('pg-preview-competition-context').textContent).toMatch(/off/)
    fireEvent.click(box)
    await waitFor(() => expect(calls.filter((c) => c[0] === 'render.preview').some((c) => c[1].competition === true)).toBe(true))
    const kinds = calls.map((c) => c[0])
    expect(kinds).not.toContain('playground.add_operation')
    expect(kinds).not.toContain('playground.save')
    expect(kinds).not.toContain('playground.undo')
  })

  it('the side-by-side comparison renders both compositions and the backend cell report', async () => {
    setup()
    await openPreview()
    fireEvent.click(screen.getByTestId('pg-preview-compare'))
    fireEvent.change(screen.getByTestId('pg-preview-compare-preset'), { target: { value: '1920x1080' } })
    await screen.findByTestId('pg-compare')
    expect(screen.getByTestId('pg-compare-a').textContent).toContain('SquadComposition-Standard')
    expect(screen.getByTestId('pg-compare-b').textContent).toContain('SquadComposition-Large')
    expect(screen.getByTestId('pg-compare-appear').textContent).toContain('Extra')
    expect(screen.getByTestId('pg-compare-disappear').textContent).toContain('Gone')
    expect(screen.getByTestId('pg-compare-changed').textContent).toContain('Training')
  })
})

describe('Playground: the 5G build panel (routes, cell layer, readiness)', () => {
  const screensList = { total: 1, screens: [{ name: 'SquadComposition-Large', preset: [16, 10], cells: [] }] }
  const screenResult = {
    composition: 'SquadComposition-Large', pitch: { stride: 82, gap: 16 }, grid: { cols: 20, rows: 10 },
    hosts: [],
  }
  const sessionEmpty = { session: { schema: 'fm-playsession/1', project: 'pg', screen: null, game_build: '27.1', operations: [] },
                         projection: { token_overrides: [], scoped_rules: [], image_swaps: [], placements: [] },
                         counts: { total: 0, applied: 0 } }
  const report = (over: any = {}) => ({
    schema: 'fm-buildsession/1', project: 'pg',
    operations: [
      { id: 'op-1', kind: 'MoveNode', route: 'bundle', reason: 'the composition asset is rebuilt', refused: false,
        translation: { fragment: 'placement', composition: 'SquadComposition-Large' }, target_bundle: 'ui-tileslayouts_assets_all.bundle' },
      { id: 'op-2', kind: 'AddCell', route: 'refused', reason: 'candidate operation: runtime test has not passed', refused: true,
        translation: { fragment: 'placement' } },
    ],
    refusals: [{ id: 'op-2', kind: 'AddCell', reason: 'candidate operation: runtime test has not passed' }],
    conflicts: [],
    targets: ['ui-tileslayouts_assets_all.bundle'],
    referrers: { source: '4C dependency graph used_by', affected: ['ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle'],
                 by_bundle: { 'ui-tileslayouts_assets_all.bundle': ['ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle'] } },
    cell_check: { ok: true, differences: [], by_bundle: { 'ui-tileslayouts_assets_all.bundle': {
      intended: { '4181126630784745451': [{ element_id: 'Atmosphere', to: { x: 16, y: 10 } }] },
      built_cell_changes: { '4181126630784745451': { changed_m_location: [{ element_id: 'Atmosphere' }] } } } } },
    outputs: { built_dir: 'C:/tmp/build', skin_folder: 'C:/tmp/build/skin/demo', package: 'C:/tmp/build/package.json',
               manifest: 'C:/tmp/build/build-manifest.json', bundles: { 'ui-tileslayouts_assets_all.bundle': 'ab' } },
    buildability: { buildable: true, reason: 'every applied operation was routed and built' },
    installation_ready: { ready: false, reason: '5G installs nothing; installation and the runtime tests are 5H' },
    integrity: [{ bundle: 'ui-tileslayouts_assets_all.bundle', status: 'install-time check (Stage 3G): CRC mismatch warns' }],
    ...over,
  })
  const setup = (over: any = {}) => {
    const calls: any[] = []
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      calls.push([m, b])
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'render.preview') throw new Error('no preview in this test')
      if (m === 'playground.session') return sessionEmpty
      if (m === 'build.session') return report(over)
      throw new Error('unexpected ' + m)
    })
    return calls
  }
  const open = async () => {
    render(<Playground project="pg" say={vi.fn()} onOpenInstall={vi.fn()} />)
    fireEvent.click(screen.getByTestId('pg-mode-screen'))
    fireEvent.click(await screen.findByTestId('pg-screen-row'))
    await screen.findByTestId('pg-build-panel')
  }

  it('shows per operation the route and its reason, and the refusals with their text', async () => {
    setup()
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    const ops = await screen.findAllByTestId('pg-build-op')
    expect(ops).toHaveLength(2)
    expect(ops[0].getAttribute('data-route')).toBe('bundle')
    expect(ops[0].textContent).toContain('the composition asset is rebuilt')
    expect(ops[1].getAttribute('data-route')).toBe('refused')
    expect(screen.getByTestId('pg-build-refusals').textContent).toContain('runtime test has not passed')
  })

  it('shows the optional tiles an add or resize hides at this setting', async () => {
    setup({ optional_slot_effects: [{ op_id: 'op-2', kind: 'AddCell', element_id: 'Happiness',
      composition: 'SquadComposition-Large', hidden: ['SquadHierachy', 'MedicalCentre'], moved: [],
      summary: 'adding Happiness hides SquadHierachy, MedicalCentre at the measured 16-row grid' }] })
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    const panel = await screen.findByTestId('pg-build-optional-slots')
    expect(panel.textContent).toContain('adding Happiness hides SquadHierachy, MedicalCentre')
    expect(panel.textContent).toContain('16-row grid')
  })

  it('offers the add-tile placement that hides the fewest optional tiles', async () => {
    setup({ addcell_placement_options: [{ op_id: 'op-2', element_id: 'Happiness', composition: 'SquadComposition-Large',
      recommended: { label: 'lowest impact' }, options: [
        { label: 'requested', geometry: { x: 16, y: 12, w: 4, h: 4 }, design_bottom: 16,
          hidden: ['SquadHierachy', 'MedicalCentre', 'Loans'], summary: 'requested at row 12: design bottom 16, hides SquadHierachy, MedicalCentre, Loans' },
        { label: 'lowest impact', geometry: { x: 16, y: 10, w: 4, h: 4 }, design_bottom: 14,
          hidden: ['MedicalCentre', 'Loans'], summary: 'aligned at row 10: design bottom 14, hides MedicalCentre, Loans' },
      ] }] })
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    const panel = await screen.findByTestId('pg-build-addcell-options')
    expect(panel.textContent).toContain('requested at row 12')
    expect(panel.textContent).toContain('aligned at row 10')
    expect(panel.textContent).toContain('fewest optional tiles hidden')
  })

  it('shows buildability and installation readiness separately', async () => {
    setup()
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    expect((await screen.findByTestId('pg-buildability')).textContent).toContain('buildable: yes')
    expect(screen.getByTestId('pg-build-ready').textContent).toContain('installation ready: no')
    expect(screen.getByTestId('pg-build-ready').textContent).toContain('5G installs nothing')
  })

  it('shows the cell-layer comparison, the affected referrers and the integrity note', async () => {
    setup()
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    const cells = await screen.findByTestId('pg-build-cells')
    expect(cells.getAttribute('data-ok')).toBe('true')
    expect(cells.textContent).toContain('Atmosphere')
    expect(screen.getByTestId('pg-build-outputs').textContent).toContain('affected (referrers): ui-visualtreeassets')
    expect(screen.getByTestId('pg-build-integrity').textContent).toContain('CRC mismatch warns')
    expect(screen.getByTestId('pg-build-open-install')).toBeTruthy()
  })

  it('a refused build shows its blocked reasons and no cell comparison', async () => {
    setup({ cell_check: null, blocked: ['the source has no ui-tactics_assets_all.bundle'], buildability: undefined,
            installation_ready: undefined, integrity: [] })
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    expect((await screen.findByTestId('pg-buildability')).textContent).toContain('no')
    expect(screen.queryByTestId('pg-build-cells')).toBeNull()
  })

  it('building sends no session-changing call', async () => {
    const calls = setup()
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    await screen.findAllByTestId('pg-build-op')
    const kinds = calls.map((c) => c[0])
    expect(kinds).toContain('build.session')
    expect(kinds).not.toContain('playground.add_operation')
    expect(kinds).not.toContain('playground.save')
    expect(kinds).not.toContain('playground.undo')
    expect(kinds).not.toContain('playground.validate_move')
  })
})


describe('Playground: ST1, the custom-layout route (badge, warning, layout route, build panel, SwapTile)', () => {
  const SQUAD = 'SquadComposition-Large'
  const screensList = { total: 1, screens: [{ name: SQUAD, preset: [16, 10], cells: [
    { cell_index: 0, element_id: 'Atmosphere', x: 16, y: 8, w: 4, h: 2, flags: [] },
  ] }] }
  const screenResult = {
    composition: SQUAD, pitch: { stride: 82, gap: 16 }, grid: { cols: 30, rows: 16 },
    hosts: [{ element_id: 'Atmosphere', col: 26, row: 8, w: 4, h: 2, px: { left: 12 + 82 * 26, top: 12 + 82 * 8, width: 82 * 4 - 16, height: 82 * 2 - 16 }, tile_layout: 'AtmosphereTile', tile_how: 'MEASURED', mode: ['fixed'] }],
  }
  const sessionEmpty = { session: { schema: 'fm-playsession/1', project: 'pg', screen: null, game_build: '27.1', operations: [] },
                         projection: { token_overrides: [], scoped_rules: [], image_swaps: [], placements: [] }, counts: { total: 0, applied: 0 } }
  const routing = (over: any = {}) => ({ project: 'pg', route_preference: 'bundle', route_preference_explicit: false, edit_competition_sheets: false, edit_competition_sheets_explicit: false,
    layout_route: 'custom_layout', layout_route_explicit: false, layout_route_default: 'custom_layout', layout_route_note: 'layout operations go to the custom-layout files',
    default: 'bundle', tradeoffs: { bundle: 'b', skin_folder: 's', edit_competition_sheets: 'c' }, note: 'n', ...over })
  const customList = (files: string[]) => ({ folder: 'C:/game/CustomGridCompositions', folder_exists: true,
    badge: 'customised in the game: this file is used instead of the bundle', warning: 'a bundle layout edit on a customised screen will not show',
    files: files.map((n) => ({ composition: n, size: 100, mtime: '2026-11-16 14:13:00', sha256: 'ab' })) })
  const tileSet = { composition: SQUAD, tiles: [{ id: 'Atmosphere', object: 'SquadAtmosphereTileDescription', sizes: [[2, 2], [4, 2]] },
                                                  { id: 'Happiness', object: 'SquadHappinessTileDescription', sizes: [[2, 2], [4, 4]] }] }
  const setup = (opts: { custom?: string[]; routingOver?: any; report?: any; built?: any } = {}) => {
    const calls: any[] = []
    ;(rpc as any).mockImplementation(async (m: string, b?: any) => {
      calls.push([m, b])
      if (m === 'playground.screens') return screensList
      if (m === 'render.screen') return screenResult
      if (m === 'render.preview') throw new Error('no preview in this test')
      if (m === 'playground.session') return sessionEmpty
      if (m === 'project.routing') return routing(opts.routingOver)
      if (m === 'project.set_routing') return routing({ ...(opts.routingOver ?? {}), ...b })
      if (m === 'customlayout.list') return customList(opts.custom ?? [])
      if (m === 'playground.tile_set') return tileSet
      if (m === 'playground.build_operation') return opts.built ?? { gate: { valid: true }, operation: { id: 'op-9', kind: 'SwapTile', label: 'Swap the tile' }, validation: { ok: true } }
      if (m === 'playground.add_operation') return { added: 'op-9' }
      if (m === 'build.session') return opts.report
      throw new Error('unexpected ' + m)
    })
    return calls
  }
  const open = async () => {
    const say = vi.fn()
    render(<Playground project="pg" say={say} onOpenInstall={vi.fn()} />)
    fireEvent.click(screen.getByTestId('pg-mode-screen'))
    fireEvent.click(await screen.findByTestId('pg-screen-row'))
    await screen.findByTestId('pg-build-panel')
    return say
  }

  it('marks a screen customised in the game with the badge text, and a screen without a file gets none', async () => {
    setup({ custom: [SQUAD] })
    await open()
    expect((await screen.findByTestId('pg-customised-badge')).textContent).toBe('customised in the game: this file is used instead of the bundle')
    cleanup()
    setup({ custom: ['SomethingElse'] })
    await open()
    await screen.findByTestId('pg-screen-name')
    expect(screen.queryByTestId('pg-customised-badge')).toBeNull()
  })

  it('warns that a BUNDLE layout edit on a customised screen will not show, and only then', async () => {
    setup({ custom: [SQUAD], routingOver: { layout_route: 'bundle', layout_route_explicit: true } })
    await open()
    expect((await screen.findByTestId('pg-customised-warning')).textContent).toContain('will not show')
    cleanup()
    setup({ custom: [SQUAD] })
    await open()
    await screen.findByTestId('pg-customised-badge')
    expect(screen.queryByTestId('pg-customised-warning')).toBeNull()
  })

  it('the layout route is custom-layout files by default and the choice is saved explicitly', async () => {
    const calls = setup()
    await open()
    const custom = await screen.findByTestId('pg-layout-route-custom') as HTMLInputElement
    expect(custom.checked).toBe(true)
    expect(screen.getByTestId('pg-layout-route').textContent).toContain('default: custom_layout')
    fireEvent.click(screen.getByTestId('pg-layout-route-bundle'))
    await waitFor(() => expect(calls.some((c) => c[0] === 'project.set_routing' && c[1].layout_route === 'bundle')).toBe(true))
    await waitFor(() => expect((screen.getByTestId('pg-layout-route-bundle') as HTMLInputElement).checked).toBe(true))
  })

  it('the build panel shows each operation route and reason and the custom-layout files that will be written', async () => {
    setup({ custom: [SQUAD], report: {
      schema: 'fm-buildsession/1', project: 'pg', layout_route: 'custom_layout', customised_in_game: [SQUAD], warnings: [],
      operations: [
        { id: 'op-1', kind: 'MoveNode', route: 'custom_layout', reason: 'the game custom-layout file; proven: JX X1', refused: false, translation: { fragment: 'custom_layout' }, custom_layout_file: SQUAD, replaces_user_file: true },
        { id: 'op-2', kind: 'SetOptionalSlots', route: 'refused', reason: 'SetOptionalSlots add-slot alone is proven on the bundle route only', refused: true, translation: { fragment: null } },
      ],
      refusals: [{ id: 'op-2', kind: 'SetOptionalSlots', reason: 'SetOptionalSlots add-slot alone is proven on the bundle route only' }], conflicts: [], targets: [],
      referrers: { source: 'x', affected: [], by_bundle: {} }, cell_check: null,
      custom_layouts: { layout_route: 'custom_layout', files: [{ name: SQUAD, size: 5612, sha256: 'ab' }] },
      outputs: { built_dir: 'C:/tmp/b', skin_folder: null, package: 'C:/tmp/b/package.json', manifest: null, bundles: {} },
    } })
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    const ops = await screen.findAllByTestId('pg-build-op')
    expect(ops[0].getAttribute('data-route')).toBe('custom_layout')
    expect(ops[0].textContent).toContain('proven: JX X1')
    expect(screen.getByTestId('pg-build-op-file').textContent).toContain('replaces the file you already have')
    expect(ops[1].getAttribute('data-route')).toBe('refused')
    expect(screen.getByTestId('pg-build-refusals').textContent).toContain('proven on the bundle route only')
    const files = screen.getByTestId('pg-build-custom-files')
    expect(files.textContent).toContain('5612 bytes')
    expect(files.textContent).toContain('replaces your file')
  })

  it('a bundle layout operation on a customised screen carries the backend warning into the build panel', async () => {
    setup({ report: {
      schema: 'fm-buildsession/1', project: 'pg', layout_route: 'bundle', customised_in_game: [SQUAD],
      warnings: [{ id: 'op-1', kind: 'MoveNode', warning: 'this screen is customised in the game: its custom-layout file is used instead of the bundle, so this bundle layout edit will not show' }],
      operations: [{ id: 'op-1', kind: 'MoveNode', route: 'bundle', reason: 'the composition asset is rebuilt', refused: false, translation: {}, warning: 'this screen is customised in the game: it will not show' }],
      refusals: [], conflicts: [], targets: [], referrers: { source: 'x', affected: [], by_bundle: {} }, cell_check: null,
      outputs: { built_dir: 'C:/tmp/b', skin_folder: null, package: null, manifest: null, bundles: {} },
    } })
    await open()
    fireEvent.click(screen.getByTestId('pg-build'))
    expect((await screen.findByTestId('pg-build-warnings')).textContent).toContain('will not show')
    expect(screen.getByTestId('pg-build-op-warning').textContent).toContain('customised in the game')
  })

  it('SwapTile: the inspector lists the tiles of the composition own set and records the swap through the backend', async () => {
    const calls = setup()
    const say = await open()
    await screen.findAllByTestId('pg-tile')
    fireEvent.click(screen.getByTestId('pg-swap'))
    await screen.findByTestId('pg-swap-panel')
    await waitFor(() => expect(calls.some((c) => c[0] === 'playground.tile_set' && c[1].composition === SQUAD)).toBe(true))
    const tiles = await screen.findByTestId('pg-swap-tile') as HTMLSelectElement
    expect(Array.from(tiles.options).map((o) => o.value)).toEqual(['', 'Atmosphere', 'Happiness'])
    fireEvent.change(tiles, { target: { value: 'Happiness' } })
    const size = screen.getByTestId('pg-swap-size') as HTMLSelectElement
    expect(Array.from(size.options).map((o) => o.value)).toEqual(['', '2x2', '4x4'])
    expect((screen.getByTestId('pg-swap-record') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(size, { target: { value: '4x4' } })
    fireEvent.click(screen.getByTestId('pg-swap-record'))
    await waitFor(() => expect(calls.some((c) => c[0] === 'playground.add_operation')).toBe(true))
    const built = calls.find((c) => c[0] === 'playground.build_operation')!
    expect(built[1]).toMatchObject({ kind: 'SwapTile', composition: SQUAD, element_id: 'Atmosphere', tile: { name: 'Happiness', size: { x: 4, y: 4 } } })
    expect(say).toHaveBeenCalled()
  })

  it('SwapTile: a swap the backend refuses records nothing and the refusal is shown', async () => {
    const calls = setup({ built: { gate: null, operation: null, validation: null, refused: 'NoSuchTile with a 2x2 configuration is not in the own tile set' } })
    const say = await open()
    await screen.findAllByTestId('pg-tile')
    fireEvent.click(screen.getByTestId('pg-swap'))
    fireEvent.change(await screen.findByTestId('pg-swap-tile'), { target: { value: 'Atmosphere' } })
    fireEvent.change(screen.getByTestId('pg-swap-size'), { target: { value: '4x2' } })
    fireEvent.click(screen.getByTestId('pg-swap-record'))
    await waitFor(() => expect(say).toHaveBeenCalledWith(expect.stringContaining('refused by the backend')))
    expect(calls.some((c) => c[0] === 'playground.add_operation')).toBe(false)
  })
})
