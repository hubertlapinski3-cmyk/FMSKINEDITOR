// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Recolour, { entriesOf, kindOf, parseColour, screensText } from './Recolour'
import { MY_COLOURS_KEY } from './myColours'
import type { Computed, RNode } from './Render'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const tok = (value: string, tokens: string[]): Computed => ({ value, raw: 'var(' + tokens[0] + ')', tokens, source: { sheet: 'S', selector: '.x', specificity: 1 }, unresolved: null, status: 'mapped', note: '', css: [] })
const lit = (value: string): Computed => ({ value, raw: null, tokens: null, source: { sheet: 'S', selector: '.card', specificity: 11 }, unresolved: null, status: 'mapped', note: '', css: [] })
const other = (value: string, source: Record<string, any>): Computed => ({ value, raw: null, tokens: null, source, unresolved: null, status: 'mapped', note: '', css: [] })
const mk = (computed: Record<string, Computed>, children: RNode[] = []): RNode => ({ type: 'VisualElement', name: 'card', classes: ['card'], runtime_classes: [], style: {}, text: null, flag: null, matched: [], computed, children })

let model: any
let screens = { screens: 3, of: 8 }
let literal = { uses: 12, selectors: 4, copied_rules: 12, limit: 50, offered: true }
beforeEach(() => {
  localStorage.clear()
  model = { name: 'p', options: {}, token_overrides: [], literal_swaps: [] }
  screens = { screens: 3, of: 8 }; literal = { uses: 12, selectors: 4, copied_rules: 12, limit: 50, offered: true }
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'project.get') return model
    if (m === 'project.save') { model = p.project; return { project: model } }
    if (m === 'simple.token_screens') return { token: p.token, names: [], ...screens }
    if (m === 'simple.literal_info') return { rgb: p.rgb, a: p.a, ...literal }
    throw new Error('unexpected ' + m)
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear() })
const saved = () => (rpc as any).mock.calls.filter((c: unknown[]) => c[0] === 'project.save').map((c: any) => c[1].project)
const show = (n: RNode, tree: RNode[] = [n]) => render(<Recolour node={n} tree={tree} project="p" say={() => {}} onClose={() => {}} />)

describe('reading a clicked part', () => {
  it('parses colours with and without alpha, and tells the sources apart', () => {
    expect(parseColour('#1e2129')).toEqual({ rgb: '#1E2129', a: 1 })
    expect(parseColour('#FFFFFF59')).toEqual({ rgb: '#FFFFFF', a: 0.349 })
    expect(parseColour('linear-gradient(red, blue)')).toBeNull()
    expect(kindOf(tok('#112233', ['--a', '--b']))).toBe('token')
    expect(kindOf(lit('#112233'))).toBe('literal')
    expect(kindOf(other('#112233', { inline: true }))).toBe('inline')
    expect(kindOf(other('#112233', { inherited: true }))).toBe('inherited')
    expect(kindOf(other('#112233', {}))).toBe('unknown')
    expect(kindOf(other('url(x)', {}))).toBe('notcolour')
  })
  it('offers background, text and border; four equal sides are one border; an invisible border is left out', () => {
    const n = mk({ 'background-color': tok('#112233', ['--bg']), color: tok('#EEEEEE', ['--text']),
      'border-top-color': tok('#FFFFFF29', ['--line']), 'border-right-color': tok('#FFFFFF29', ['--line']), 'border-bottom-color': tok('#FFFFFF29', ['--line']), 'border-left-color': tok('#FFFFFF29', ['--line']) })
    expect(entriesOf(n).map((e) => e.label)).toEqual(['Background', 'Text', 'Border'])
    const m = mk({ 'border-top-color': tok('#FFFFFF00', ['--none']), 'border-left-color': tok('#FF0000', ['--red']) })
    expect(entriesOf(m).map((e) => e.label)).toEqual(['Border (left)'])
  })
  it('the screen count wording: N of the 8, and 0 never reads as "nothing changes"', () => {
    expect(screensText({ screens: 3, of: 8 })).toBe('used on 3 of the 8 measured screens we have models for')
    expect(screensText({ screens: 0, of: 8 })).toBe('not used on the 8 screens we have models for; it may still change screens we have not measured')
    expect(screensText({ screens: 0, of: 8 })).not.toMatch(/nothing changes/)
  })
})

describe('a colour from a game token', () => {
  it('names the token, counts the other parts of this picture and the measured screens, and changes the token keeping its alpha', async () => {
    const n = mk({ 'background-color': tok('#1E212880', ['--layout-card', '--colours-ui-soft']) })
    const sib = mk({ 'background-color': tok('#1E212880', ['--layout-card']) })
    show(n, [mk({}, [n, sib])])
    expect(await screen.findByText(/used on 3 of the 8 measured screens we have models for/)).toBeTruthy()
    expect(screen.getByText('layout-card')).toBeTruthy()
    expect(screen.getByText(/also changes 1 other part of this picture/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText('New background colour'), { target: { value: '#ff0000' } })
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].token_overrides).toEqual([{ token: '--layout-card', value: { rgb: '#FF0000', a: 0.502 }, vanilla: '#1E212880' }])
  })
  it('a token on no measured screen says it may still change screens we have not measured', async () => {
    screens = { screens: 0, of: 8 }
    show(mk({ 'background-color': tok('#101010', ['--global-background-test']) }))
    expect(await screen.findByText(/it may still change screens we have not measured/)).toBeTruthy()
  })
  it('My colours sit beside the picker, and Put it back returns the game colour by removing the change', async () => {
    localStorage.setItem(MY_COLOURS_KEY, JSON.stringify(['#00AA55']))
    model.token_overrides = [{ token: '--t', value: { rgb: '#123456', a: 1 }, vanilla: '#101010' }]
    show(mk({ color: tok('#123456', ['--t']) }))
    fireEvent.click(await screen.findByLabelText('Use #00AA55'))
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].token_overrides).toEqual([{ token: '--t', value: { rgb: '#00AA55', a: 1 }, vanilla: '#101010' }])
    fireEvent.click(screen.getByText('Put it back'))
    await waitFor(() => expect(saved().length).toBe(2))
    expect(saved()[1].token_overrides).toEqual([])
  })
})

describe('a colour written directly into a game rule', () => {
  it('shows what it would copy BEFORE anything is changed, then swaps exactly this colour; repeated picks keep one swap', async () => {
    show(mk({ 'background-color': lit('#21C67FCC') }))
    expect((await screen.findByTestId('literal-cost')).textContent).toMatch(/copies 12 game rules into your skin \(4 selectors\)/)
    expect(saved().length).toBe(0)
    fireEvent.change(screen.getByLabelText('New background colour'), { target: { value: '#ff8800' } })
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].literal_swaps).toEqual([{ from: { rgb: '#21C67F', a: 0.8 }, to: { rgb: '#FF8800', a: 0.8 }, mode: 'rgba' }])
    fireEvent.change(screen.getByLabelText('New background colour'), { target: { value: '#ff8811' } })
    await waitFor(() => expect(saved().length).toBe(2))
    expect(saved()[1].literal_swaps).toEqual([{ from: { rgb: '#21C67F', a: 0.8 }, to: { rgb: '#FF8811', a: 0.8 }, mode: 'rgba' }])
  })
  it('over the limit it says it is an Advanced job, with the count, and offers no picker', async () => {
    literal = { uses: 147, selectors: 96, copied_rules: 147, limit: 50, offered: false }
    show(mk({ color: lit('#FFFFFF') }))
    expect((await screen.findByTestId('literal-advanced')).textContent).toMatch(/used in many places \(147 game rules\); changing it here is an Advanced job/)
    expect(screen.queryByLabelText('New text colour')).toBeNull()
  })
  it('a colour I swapped in can be changed again or put back', async () => {
    model.literal_swaps = [{ from: { rgb: '#21C67F', a: 1 }, to: { rgb: '#FF8800', a: 1 }, mode: 'rgba' }]
    show(mk({ 'background-color': lit('#FF8800') }))
    expect(await screen.findByText(/You changed this colour from/)).toBeTruthy()
    fireEvent.click(screen.getByText('Put it back'))
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].literal_swaps).toEqual([])
  })
})

describe('colours the panel cannot change say so', () => {
  it('from the layout file, from the part around it, painted while running, or not a plain colour: words, and no picker', async () => {
    show(mk({ 'background-color': other('#21C67F', { inline: true, layout: 'x' }), color: other('#EEEEEE', { inherited: true }),
      'border-top-color': other('#FF0000', {}), 'border-right-color': other('#FF0000', {}), 'border-bottom-color': other('#FF0000', {}), 'border-left-color': other('#FF0000', {}) }))
    expect(await screen.findByText(/written into the game's layout file itself/)).toBeTruthy()
    expect(screen.getByText(/takes its colour from the part around it/)).toBeTruthy()
    expect(screen.getByText(/The game paints this while running; it can't be changed here/)).toBeTruthy()
    expect(screen.queryAllByRole('textbox').length + document.querySelectorAll('input[type=color]').length).toBe(0)
  })
  it('a part with no colour of its own says to click another part', async () => {
    show(mk({}))
    expect(await screen.findByText(/no colour of its own/)).toBeTruthy()
  })
})
