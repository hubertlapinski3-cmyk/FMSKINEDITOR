// @vitest-environment jsdom
// S4 of the Simple mode plan: the gallery and "Make a theme from three colours" on the start screen. The engine is mocked; what is pinned is what the screen sends and says.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Start, { UNCHECKED, pairText } from './Start'
import { MY_COLOURS_KEY } from './myColours'

const { FakeRpcError } = vi.hoisted(() => ({ FakeRpcError: class FakeRpcError extends Error { code: number; data: any; constructor(e: { code: number; message: string; data?: any }) { super(e.message); this.code = e.code; this.data = e.data } } }))
vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: FakeRpcError, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const CRIMSON = { background: '#171717', accent: '#DA0037', text: '#EDEDED', mode: 'dark' }
const OCEAN = { name: 'Ocean', background: '#0F1A24', accent: '#2E86DE', text: '#E6EEF5', mode: 'dark', status: UNCHECKED, ok: true, failures: 0, checked: 36 }
const BROKEN = { name: 'Broken', background: '#16142A', accent: '#8E6CF0', text: '#ECEAF5', mode: 'dark', status: UNCHECKED, ok: false, failures: 2, checked: 36 }
const pass = (inputs: any) => ({ inputs, writes: 82, keeps: 148, status: UNCHECKED, ok: true, preview: {},
  contrast: { minimum: 4.5, pairs: 43, checked: 36, failures: [], game_failures: [], unchecked: new Array(7).fill({ fg: '--cr-white', bg: '--cr-blue' }),
    game_low: [{ fg: '--status-coaching-adjective-ratings-unsuited-text', bg: '--status-coaching-adjective-ratings-unsuited-surface', game_ratio: 3.94, ratio: 4.74, corrected: true }] } })
const fail = (inputs: any) => ({ ...pass(inputs), ok: false, contrast: { ...pass(inputs).contrast, failures: [{ fg: '--global-text-muted', bg: '--colours-ui-soft', ratio: 3.91 }] } })

let generate: (p: any) => any
beforeEach(() => {
  generate = pass
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'theme.gallery') return { themes: [OCEAN, BROKEN], crimson: { ...CRIMSON, source: 'roles.json' } }
    if (m === 'theme.generate') return generate(p)
    return {}
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear() })
const start = () => render(<Start projects={[]} onCreated={async () => {}} onImport={() => {}} say={() => {}} />)
const make = () => screen.getByText('Make it') as HTMLButtonElement

describe('the gallery', () => {
  it('lists Crimson and every gallery theme, each said to be not yet checked in the game', async () => {
    start(); fireEvent.click(screen.getByText('Start from a ready-made theme'))
    expect(await screen.findByText('Ocean')).toBeTruthy()
    expect(screen.getByText('Crimson')).toBeTruthy()
    expect(screen.getAllByText(new RegExp(UNCHECKED)).length).toBeGreaterThanOrEqual(2)
  })

  it('a gallery theme is made by theme.create from its three colours, with the club answer', async () => {
    start(); fireEvent.click(screen.getByText('Start from a ready-made theme'))
    fireEvent.click(await screen.findByLabelText(/Ocean/))
    fireEvent.click(screen.getByLabelText(/one flat look for every club/))
    fireEvent.click(make())
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('theme.create', { name: 'my-first-skin', background: '#0F1A24', accent: '#2E86DE', text: '#E6EEF5', mode: 'dark', keep_club_colours: false }))
  })

  it('a gallery theme that fails on this build cannot be chosen, and says why', async () => {
    start(); fireEvent.click(screen.getByText('Start from a ready-made theme'))
    const b = await screen.findByLabelText(/Broken/) as HTMLInputElement
    expect(b.disabled).toBe(true)
    expect(screen.getByText(/fails the readability check on 2 pair/)).toBeTruthy()
  })

  it('when the list cannot be read, Crimson is still offered and the screen says the others are missing', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => { if (m === 'theme.gallery') throw new FakeRpcError({ code: -32000, message: 'x', data: { plain: 'y' } }); return {} })
    start(); fireEvent.click(screen.getByText('Start from a ready-made theme'))
    expect(await screen.findByTestId('gallery-problem')).toBeTruthy()
    expect(make().disabled).toBe(false)
  })
})

describe('a theme from three colours', () => {
  it("starts from Crimson's own three colours as the engine gives them, checks them, and makes the theme", async () => {
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('theme.generate', CRIMSON))
    expect((screen.getByLabelText('Background') as HTMLInputElement).value).toBe('#171717')
    expect(await screen.findByText(/Readable/)).toBeTruthy()
    expect(screen.getByText(/sets 82 of the game's colours and leaves 148/)).toBeTruthy()
    expect(screen.getByTestId('theme-check').textContent).toContain(UNCHECKED)
    expect(screen.getByTestId('theme-check').textContent).toContain("Some surfaces, like the Tactics panels, keep the game's own colours.")
    await waitFor(() => expect(make().disabled).toBe(false))
    fireEvent.click(make())
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('theme.create', { name: 'my-first-skin', ...CRIMSON, keep_club_colours: true }))
  })

  it('a failing check is listed in words, blocks Make it, and nothing is adjusted', async () => {
    generate = fail
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    expect(await screen.findByTestId('theme-failures')).toBeTruthy()
    expect(screen.getByText('global-text-muted on colours-ui-soft: 3.91 to 1, needs 4.5 to 1')).toBeTruthy()
    expect(screen.getByText(/Nothing is adjusted for you/)).toBeTruthy()
    expect(make().disabled).toBe(true)
    fireEvent.click(make())
    expect((rpc as any).mock.calls.some((c: any[]) => c[0] === 'theme.create')).toBe(false)
    expect((screen.getByLabelText('Background') as HTMLInputElement).value).toBe('#171717')
  })

  it('colours this game build no longer has are said, and Make it stays off', async () => {
    generate = (p: any) => ({ ...pass(p), ok: false, missing: ['--gone-1', '--gone-2'] })
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    expect((await screen.findByTestId('theme-missing')).textContent).toMatch(/no longer has 2 of the colours/)
    expect(make().disabled).toBe(true)
  })

  it("the game's own low value is still said, as corrected by the theme; the pairs it can't check are said too", async () => {
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    expect((await screen.findByTestId('theme-corrected')).textContent).toBe("status-coaching-adjective-ratings-unsuited-text on status-coaching-adjective-ratings-unsuited-surface is at 3.94 to 1 in the game's own colours; this theme corrects it to 4.74 to 1.")
    expect(screen.queryByTestId('theme-game-failures')).toBeNull()
    expect(screen.getByTestId('theme-unchecked').textContent).toMatch(/^7 of the 43 pairs can't be checked here/)
  })

  it('a pair the game leaves low and the theme does not touch is still reported apart', async () => {
    generate = (p: any) => ({ ...pass(p), contrast: { ...pass(p).contrast, game_failures: [{ fg: '--x-fg', bg: '--x-bg', ratio: 4.2 }] } })
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    expect((await screen.findByTestId('theme-game-failures')).textContent).toMatch(/in the game itself, and not changed by this theme: x-fg on x-bg/)
  })

  it('there is no Light choice: themes from three colours are dark in 1.2.0', async () => {
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    await screen.findByText(/Readable/)
    expect(screen.queryByLabelText('Light')).toBeNull(); expect(screen.queryByLabelText('Dark')).toBeNull()
    expect(screen.queryByText(/Dark or light/)).toBeNull()
  })

  it('changing a colour checks again with the new values; My colours sits beside each picker', async () => {
    localStorage.setItem(MY_COLOURS_KEY, JSON.stringify(['#224466']))
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    await screen.findByText(/Readable/)
    fireEvent.change(screen.getByLabelText('Accent'), { target: { value: '#2e86de' } })
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('theme.generate', { ...CRIMSON, accent: '#2E86DE' }))
    expect(screen.getByRole('group', { name: 'My colours for the background' })).toBeTruthy()
    fireEvent.click(screen.getAllByLabelText('Use #224466')[0])
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('theme.generate', { ...CRIMSON, background: '#224466', accent: '#2E86DE' }))
    expect((rpc as any).mock.calls.filter((c: any[]) => c[0] === 'theme.generate').every((c: any[]) => c[1].mode === 'dark')).toBe(true)
  })

  it('without the engine giving the starting colours there are no pickers: no invented default', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => { if (m === 'theme.gallery') throw new FakeRpcError({ code: -32000, message: 'RuntimeError: no style index', data: { plain: "The Studio hasn't read the game's styles yet." } }); return {} })
    start(); fireEvent.click(screen.getByText('Make a theme from three colours'))
    expect(await screen.findByText(/hasn't read the game's styles yet/)).toBeTruthy()
    expect(screen.queryByTestId('three')).toBeNull()
    expect(make().disabled).toBe(true)
  })

  it('pairText says which text on which background, the ratio and the minimum', () => {
    expect(pairText({ fg: '--a', bg: '--b', ratio: 4.4 }, 4.5)).toBe('a on b: 4.40 to 1, needs 4.5 to 1')
  })
})
