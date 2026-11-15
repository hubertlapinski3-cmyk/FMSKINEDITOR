// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import PutInGame, { NOTHING_CHANGED, REMOVAL_FIRST } from './PutInGame'
import { REMOVAL_KEY, REMOVAL_RELEASED, labsRemoval } from './labs'

const { FakeRpcError } = vi.hoisted(() => ({ FakeRpcError: class FakeRpcError extends Error { code: number; data: any; constructor(e: { code: number; message: string; data?: any }) { super(e.message); this.code = e.code; this.data = e.data } } }))
vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: FakeRpcError, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const pre = (over: Record<string, unknown> = {}) => ({ project: 'mine', skin: 'mine', changes: { colours: 3, 'flat look': 1 }, has_changes: true, skins_folder: 'C:/Docs/skins', skins_folder_found: true, folder: 'C:/Docs/skins/mine', first_time: true, ...over })
const result = (first: boolean) => ({ project: 'mine', skin: 'mine', folder: 'C:/Docs/skins/mine', first_time: first, tokens: 3, rules: 20, images: 0, fonts: 0, skipped: ['class renames (2) cannot be expressed in USS'], problems: [],
  steps_left: first ? ['In Football Manager, open Preferences (the cog). In the drop-down next to "Reload Skin", pick "mine".', 'Press "Reload Skin".'] : ['Press "Reload Skin".'] })

let calls: string[]
function engine(opts: { pre?: any; jobs?: any[]; first?: boolean } = {}) {
  calls = []
  const jobs = [...(opts.jobs ?? [{ state: 'running', label: 'Writing the skin into your skins folder', progress: 0.4 }, { state: 'done', label: 'Checking what was written', progress: 1, result: result(opts.first ?? true) }])]
  ;(rpc as any).mockImplementation(async (m: string) => {
    calls.push(m)
    if (m === 'native.preflight') return opts.pre ?? pre()
    if (m === 'native.put') return { job: 'j1' }
    if (m === 'jobs.get') return jobs.length > 1 ? jobs.shift() : jobs[0]
    if (m === 'app.explain') return { plain: 'Plain sentence for the failure.', details: 'x' }
    if (m === 'native.remove') return { removed: 'C:/Docs/skins/mine' }
    throw new Error('unexpected ' + m)
  })
}
beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear() })
const go = () => render(<PutInGame project="mine" say={() => {}} minShowMs={0} pollMs={5} />)

describe('Put it in the game', () => {
  it('says what the skin carries, and where it will be written, and that no game file changes', async () => {
    engine(); go()
    expect(await screen.findByText(/carries 3 colours, the flat top bar and headers/)).toBeTruthy()
    expect(screen.getByText(/It does not change any game file/)).toBeTruthy()
    expect((screen.getByText('Put it in the game', { selector: 'button' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('a project that changes nothing is refused with the plain sentence and the button is off', async () => {
    engine({ pre: pre({ changes: {}, has_changes: false }) }); go()
    expect((await screen.findByTestId('put-guard')).textContent).toBe(NOTHING_CHANGED)
    expect((screen.getByText('Put it in the game', { selector: 'button' }) as HTMLButtonElement).disabled).toBe(true)
    expect(calls).not.toContain('native.put')
  })

  it('no skins folder: the button is off and the sentence says why', async () => {
    engine({ pre: pre({ skins_folder: null, skins_folder_found: false, folder: null }) }); go()
    expect(await screen.findByText(/can't find your Football Manager 27 documents folder/)).toBeTruthy()
    expect((screen.getByText('Put it in the game', { selector: 'button' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('while it runs the middle of the screen names the step in words, then the result and the two steps left appear with the skin name filled in', async () => {
    engine(); go()
    fireEvent.click(await screen.findByText('Put it in the game', { selector: 'button' }))
    expect((await screen.findByTestId('put-progress')).textContent).toMatch(/Writing the skin into your skins folder \.\.\./)
    expect(await screen.findByTestId('put-done')).toBeTruthy()
    expect(screen.queryByTestId('put-progress')).toBeNull()
    const steps = screen.getAllByRole('listitem').map((l) => l.textContent)
    expect(steps).toEqual(['In Football Manager, open Preferences (the cog). In the drop-down next to "Reload Skin", pick "mine".', 'Press "Reload Skin".'])
    expect(calls.filter((c) => c === 'native.put').length).toBe(1)
  })

  it('a later put shows only the second step', async () => {
    engine({ first: false }); go()
    fireEvent.click(await screen.findByText('Put it in the game', { selector: 'button' }))
    await screen.findByTestId('put-done')
    expect(screen.getAllByRole('listitem').map((l) => l.textContent)).toEqual(['Press "Reload Skin".'])
    expect(screen.getByText(/already chosen/)).toBeTruthy()
  })

  it('a quick job still shows its step for the minimum time', async () => {
    engine()
    render(<PutInGame project="mine" say={() => {}} minShowMs={300} pollMs={5} />)
    fireEvent.click(await screen.findByText('Put it in the game', { selector: 'button' }))
    const t0 = Date.now()
    await screen.findByTestId('put-done')
    expect(Date.now() - t0).toBeGreaterThanOrEqual(250)
  })

  it('a failed job is shown as a plain sentence with the details, the progress goes away, and the button comes back', async () => {
    engine({ jobs: [{ state: 'failed', label: 'Writing the skin into your skins folder', progress: 0.4, error: 'ValueError: something odd' }] }); go()
    fireEvent.click(await screen.findByText('Put it in the game', { selector: 'button' }))
    expect(await screen.findByText('Plain sentence for the failure.')).toBeTruthy()
    expect(screen.queryByTestId('put-progress')).toBeNull(); expect(screen.queryByTestId('put-done')).toBeNull()
    await waitFor(() => expect((screen.getByText('Put it in the game', { selector: 'button' }) as HTMLButtonElement).disabled).toBe(false))
  })

  it('checks that did not pass are shown, not hidden', async () => {
    engine({ jobs: [{ state: 'done', label: 'x', progress: 1, result: { ...result(true), problems: ['sheet missing: rules.uss'] } }] }); go()
    fireEvent.click(await screen.findByText('Put it in the game', { selector: 'button' }))
    expect(await screen.findByText(/1 check\(s\) did not pass: sheet missing: rules\.uss/)).toBeTruthy()
  })
})

describe('Take it out of the game (built, not released)', () => {
  it('the release flag is off, so an installed build never offers it', () => {
    expect(REMOVAL_RELEASED).toBe(false)           // flips only in the commit that records the in-game observation (Session 1, item e) showing no breakage
  })
  it('is not shown by default, even for a skin that was put there before', async () => {
    engine({ pre: pre({ first_time: false }) }); go()
    await screen.findByText(/carries/)
    expect(screen.queryByTestId('put-remove')).toBeNull()
    expect(labsRemoval()).toBe(false)
  })
  it('in a development build with the setting on it is shown only once the skin exists, says to switch to the default skin first, and asks before it removes', async () => {
    localStorage.setItem(REMOVAL_KEY, '1')
    engine({ pre: pre({ first_time: true }) }); const first = go(); await screen.findByText(/carries/)
    expect(screen.queryByTestId('put-remove')).toBeNull()                              // nothing to take out before the first put
    first.unmount()
    engine({ pre: pre({ first_time: false }) }); go()
    const box = await screen.findByTestId('put-remove')
    expect(box.textContent).toContain(REMOVAL_FIRST)
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false)
    fireEvent.click(screen.getByText('Take it out of the game', { selector: 'button' }))
    expect(ask).toHaveBeenCalled(); expect(ask.mock.calls[0][0]).toContain("switch to the default skin")
    expect(calls).not.toContain('native.remove')
    ask.mockReturnValue(true)
    fireEvent.click(screen.getByText('Take it out of the game', { selector: 'button' }))
    expect(await screen.findByTestId('put-removed')).toBeTruthy()
    expect(rpc).toHaveBeenCalledWith('native.remove', { project: 'mine', confirm: true })
  })
})
