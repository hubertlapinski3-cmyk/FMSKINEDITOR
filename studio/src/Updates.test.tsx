// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import Updates from './Updates'
import { Guard } from './App'

vi.mock('./engine', () => ({
  rpc: vi.fn(),
  RpcError: class extends Error {},
  connect: vi.fn(), subscribe: vi.fn(() => () => {}),
}))
import { rpc } from './engine'

const prof = (id: string, build: string) => ({ id, game_build: build, catalog_hash: 'aa', scanned_utc: 'x', tokens: 2059, sheets: 49, rules: 13028, note: null })
const status = { state: 'same', message: 'The game matches the profile.', profile: 'b' }
afterEach(() => { cleanup(); vi.clearAllMocks() })

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
