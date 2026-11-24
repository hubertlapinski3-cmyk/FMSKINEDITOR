// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Updates from './Updates'
import { Guard } from './App'

const { FakeRpcError } = vi.hoisted(() => ({ FakeRpcError: class FakeRpcError extends Error { code: number; data: any; constructor(e: { code: number; message: string; data?: any }) { super(e.message); this.code = e.code; this.data = e.data } } }))
vi.mock('./engine', () => ({
  rpc: vi.fn(),
  RpcError: FakeRpcError,
  connect: vi.fn(), subscribe: vi.fn(() => () => {}),
}))
import { rpc } from './engine'

const prof = (id: string, build: string) => ({ id, game_build: build, catalog_hash: 'aa', scanned_utc: 'x', tokens: 2059, sheets: 49, rules: 13028, note: null })
const status = { state: 'same', message: 'The game matches the profile.', profile: 'b' }
const updated = { state: 'catalog_changed', message: 'The game was updated (catalog.hash new123, the profile b was scanned at aa). Restore the stock files if a skin is installed, take a new snapshot, scan, then read the diff before building again.', block_bundle_install: true, next: ['restore_check', 'new_snapshot', 'scan', 'diff'], profile: 'b' }
const rereadResult = { snapshot: { taken_utc: 't', game_build: '27.1.0.2505117', catalog_hash: 'new123' }, index: { sheets: 49, tokens: 2059, literals: 100 }, quarantined: 0 }
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks() })
beforeEach(() => { vi.spyOn(window, 'confirm').mockReturnValue(true) })

describe('Updates view', () => {
  it('shows the status and the profiles', async () => {
    ;(rpc as any).mockResolvedValue({ status, profiles: [prof('a', '27.0.1.2494769'), prof('b', '27.0.1.2503222')] })
    render(<Updates project={null} say={() => {}} onChanged={() => {}} />)
    await waitFor(() => expect(screen.getByText(/The game matches the profile/)).toBeTruthy())
    expect(screen.getAllByText(/27\.0\.1\.2494769/).length).toBeGreaterThan(0)
  })

  it('a malformed profile row (a stray file in profiles/ with an object as tokens) must not blank the window: the guard shows the error', async () => {
    ;(rpc as any).mockResolvedValue({ status, profiles: [prof('a', '27.0.1.2494769'), { id: null, game_build: null, tokens: { old: 1, new: 2 }, sheets: { added: [] }, rules: { old: 1 } }] })
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<Guard name="Game updates"><Updates project={null} say={() => {}} onChanged={() => {}} /></Guard>)
    await waitFor(() => expect(screen.getByText(/Game updates could not be shown/)).toBeTruthy())
    expect(screen.getByText('Try again')).toBeTruthy()
    spy.mockRestore()
  })

  it('shows an engine error as text instead of crashing', async () => {
    ;(rpc as any).mockRejectedValue(new Error('method not found: update.status'))
    render(<Updates project={null} say={() => {}} onChanged={() => {}} />)
    await waitFor(() => expect(screen.getByText(/method not found/)).toBeTruthy())
  })
})

describe('Updates: the in-app re-read of an updated game', () => {
  const updatedEngine = (jobs: any[]) => {
    const j = [...jobs]
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'update.status') return { status: updated, profiles: [prof('b', '27.1.0.2505117')] }
      if (m === 'snapshot.reread') return { job: 'j9' }
      if (m === 'jobs.get') return j.length > 1 ? j.shift() : j[0]
      if (m === 'app.explain') return { plain: 'Plain sentence for the failure.', details: 'x' }
      throw new Error('unexpected ' + m)
    })
  }

  it('an updated game shows the verify-first advice and the Re-read button; one click runs the whole recovery and reports it', async () => {
    updatedEngine([
      { state: 'running', label: 'reading the game\'s files', progress: 0.2, error: null, result: null },
      { state: 'done', label: 'reading the game\'s colours and rules', progress: 1, error: null, result: rereadResult },
    ])
    render(<Updates project={null} say={() => {}} onChanged={() => {}} />)
    const card = await screen.findByTestId('reread-card')
    expect(card.textContent).toContain('Verify integrity of game files')            // the advice stays verify-first
    expect(screen.getByText(/Bundle installs are blocked/)).toBeTruthy()
    fireEvent.click(await screen.findByTestId('reread-button'))
    expect((await screen.findByTestId('reread-done')).textContent).toContain('new123')
    expect((screen.getByTestId('reread-done') as HTMLElement).textContent).toContain('49 sheets')
    const called = (rpc as any).mock.calls.find((c: any[]) => c[0] === 'snapshot.reread')
    expect(called).toBeTruthy()
  })

  it('nothing runs when the confirmation is refused', async () => {
    updatedEngine([{ state: 'done', label: 'x', progress: 1, error: null, result: rereadResult }])
    render(<Updates project={null} say={() => {}} onChanged={() => {}} />)
    await screen.findByTestId('reread-button')
    vi.mocked(window.confirm).mockReturnValue(false)
    fireEvent.click(screen.getByTestId('reread-button'))
    await waitFor(() => expect((rpc as any).mock.calls.find((c: any[]) => c[0] === 'snapshot.reread')).toBeUndefined())
  })

  it('a skin still in the game folder refuses the re-read with the verify-first plain sentence', async () => {
    updatedEngine([{ state: 'failed', label: 're-reading', progress: 1, error: "InstallError: not re-read: ui-styles_assets_common.bundle is still a file this app installed (a skin). Run Steam's Verify integrity of game files first (Steam, right-click Football Manager 27 > Properties > Installed files), let it finish, then use the Re-read the game button again.", result: null }])
    render(<Updates project={null} say={() => {}} onChanged={() => {}} />)
    fireEvent.click(await screen.findByTestId('reread-button'))
    expect(await screen.findByText(/Plain sentence for the failure/)).toBeTruthy()   // the engine's plain words for the refusal
  })

  it('a game that matches its profile shows no re-read card', async () => {
    ;(rpc as any).mockResolvedValue({ status, profiles: [prof('b', '27.1.0.2505117')] })
    render(<Updates project={null} say={() => {}} onChanged={() => {}} />)
    await waitFor(() => expect(screen.getByText(/The game matches the profile/)).toBeTruthy())
    expect(screen.queryByTestId('reread-card')).toBeNull()
  })
})
