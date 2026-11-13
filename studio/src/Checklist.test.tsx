// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Checklist from './Checklist'
import { Guard } from './App'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const pkg = (project: string, id: string, passed: boolean, latest: boolean) => ({ project, id, built_utc: id, game_build: '27.0.1.2503222', plan_digest: 'ac498b6aa1e7b3319f2ff2287e4b880999689f8c0d56dca7fbbc39b30ace0c54',
  plan: [{ op: 'MoveCell', count: 4 }], files: { 'ui-tactics_assets_all.bundle': { sha256: '9559d5968e9d9e686d55c752b4a11c291aa3e68aed733e7969a8835ec7c918b2', vanilla_sha256: '2026d469e0ef' } },
  gate: { passed, failures: passed ? [] : ['x'], checked: { tile_moves_checked: 4 } }, installable: passed, latest, dir: 'C:/b' })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Checklist view', () => {
  it('shows the checklist text and the packages with gate result, digest and file hash; the latest one is marked', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => m === 'docs.checklist' ? { path: 'docs/INGAME-CHECKLIST.md', text: '# In-game checklist: one uninterrupted session', results: 'RESULTS BLOCK' }
      : { packages: [pkg('p7-tile-test', '20261113T180410Z', true, true), pkg('p7-tile-test', '20261113T172840Z', false, false)] })
    render(<Guard name="In-game checklist"><Checklist say={() => {}} /></Guard>)
    expect(await screen.findByText(/In-game checklist: one uninterrupted session/)).toBeTruthy()
    expect(screen.getAllByText('p7-tile-test').length).toBe(2)
    expect(screen.getByText('latest')).toBeTruthy(); expect(screen.getByText('gate passed')).toBeTruthy(); expect(screen.getByText('gate FAILED')).toBeTruthy()
    expect(screen.getAllByText(/9559d5968e9d/).length).toBeGreaterThan(0); expect(screen.getAllByText(/plan ac498b6aa1e7b331/).length).toBeGreaterThan(0)
  })

  it('copies the results block', async () => {
    const write = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText: write } })
    ;(rpc as any).mockImplementation(async (m: string) => m === 'docs.checklist' ? { path: 'p', text: 't', results: 'RESULTS BLOCK' } : { packages: [] })
    render(<Checklist say={() => {}} />)
    const btn = await screen.findByText('Copy the results message')
    await waitFor(() => expect((btn as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(btn)
    await waitFor(() => expect(write).toHaveBeenCalledWith('RESULTS BLOCK'))
  })

  it('an engine failure is shown as text', async () => {
    ;(rpc as any).mockRejectedValue(new Error('method not found: docs.checklist'))
    render(<Checklist say={() => {}} />)
    expect(await screen.findAllByText(/method not found/)).toBeTruthy()
  })
})
