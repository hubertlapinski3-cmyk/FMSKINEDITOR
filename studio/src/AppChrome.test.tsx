// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

vi.mock('@monaco-editor/react', () => ({ default: () => null }))
vi.mock('./monaco', () => ({ lint: vi.fn(), registerQuickFixes: vi.fn(), registerTokenCompletion: vi.fn() }))
vi.mock('./engine', () => ({
  rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(async () => ({})), subscribe: vi.fn(() => () => {}),
  customlayout: {
    list: vi.fn(async () => ({ files: [] })), recovery_scan: vi.fn(async () => []),
    preflight: vi.fn(async () => ({ ready: true, blocked: [], warnings: [], required_confirmations: [], file_operations: [] })),
    apply: vi.fn(async () => ({ tx_id: 'tx', state: 'completed' })), rollback: vi.fn(async () => ({ tx_id: 'tx', state: 'rolled_back' })),
    base: vi.fn(async () => ({ object: { m_gridComponents: [], m_optionalSlices: {} }, cells: [], design: { cols: 20, rows: 10 }, source: 'bundle' })),
  },
}))
const invoke = vi.fn()
vi.mock('@tauri-apps/api/core', () => ({ invoke: (...a: unknown[]) => invoke(...a) }))
vi.mock('./Playground', () => ({ default: () => <div data-testid="full-playground">Full Playground</div> }))
import { rpc } from './engine'
import App from './App'

const ready = { install: { game_dir: 'C:/FM27', aa_dir: 'C:/FM27/aa', version: '27.0.1' }, running: false, tamper: { state: 'clean' }, snapshot_mismatch: null, vanilla: { game_build: '27.0.1' }, indexed: true }
beforeEach(() => { localStorage.clear(); (rpc as any).mockImplementation(async (m: string) => (m === 'app.state' ? { ...ready, projects: ['old-skin'] } : m === 'project.list' ? ['old-skin'] : null)) })
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear(); delete (window as any).__TAURI_INTERNALS__ })

describe('UI1b follow-up: focused expert bar and launch update check', () => {
  it('shows a short expert bar with a More menu holding the less-used tools', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    render(<App />)
    await waitFor(() => expect(localStorage.getItem('studio.mode')).toBe('advanced'))
    const bar = document.querySelector('nav.activity')!
    expect(bar.querySelectorAll('button').length).toBeLessThanOrEqual(12)
    expect(screen.getByTitle('Game Layouts (Playground): reconstruct a game screen, navigate its hierarchy, inspect every element with its evidence')).toBeTruthy()
    expect(screen.queryByLabelText('UXML layouts')).toBeNull()
    fireEvent.click(screen.getByTestId('activity-more'))
    expect(await screen.findByTestId('activity-more-menu')).toBeTruthy()
    expect(screen.getByLabelText('UXML layouts')).toBeTruthy()
  })

  it('exposes a launch update status in the browser (no installer, so no blocking)', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    render(<App />)
    await waitFor(() => expect(screen.getByTestId('app-update-status')).toBeTruthy())
    expect(screen.getByTestId('app-update-status').textContent).toMatch(/app up to date|app update check unavailable|checking for app updates/)
  })

  it('puts Install skin into the game at the end of the expert activity bar', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    render(<App />)
    const more = await screen.findByTestId('activity-more')
    const entry = await screen.findByLabelText('Install skin into the game')
    const buttons = Array.from(document.querySelectorAll('nav.activity > button'))
    expect(buttons.indexOf(entry)).toBe(buttons.indexOf(more) - 1)   // install is the last tool before More
  })

  it('lets the build panel switch to the bundle target so tile edits are not dropped', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'app.state') return { ...ready, projects: ['old-skin'] }
      if (m === 'project.list') return ['old-skin']
      if (m === 'project.get') return { name: 'old-skin', options: { output: 'native' } }
      if (m === 'project.files') return { folder: false, files: [] }
      if (m === 'project.problems') return { problems: [] }
      if (m === 'project.save') return { project: { name: 'old-skin', options: { output: 'bundles' } } }
      if (m === 'build.plan') return { target: 'bundles', operations: [], dropped: [], warnings: [] }
      return null
    })
    render(<App />)
    fireEvent.click(await screen.findByText('old-skin'))
    await waitFor(() => expect((rpc as any).mock.calls.some((c: unknown[]) =>
      c[0] === 'project.get' && (c[1] as any).name === 'old-skin')).toBe(true))
    fireEvent.click(await screen.findByText('BUILD'))
    const sel = await screen.findByTestId('build-target') as HTMLSelectElement
    expect(sel.value).toBe('native')
    fireEvent.change(sel, { target: { value: 'bundles' } })
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('project.save', {
      project: { name: 'old-skin', options: { output: 'bundles' } },
    }))
  })

  it('keeps the install actions together so they stay reachable in the build panel', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    render(<App />)
    fireEvent.click(await screen.findByText('BUILD'))
    const actions = await screen.findByTestId('build-actions')
    expect(within(actions).getByText('Install build')).toBeTruthy()
    expect(within(actions).getByText('Build bundles')).toBeTruthy()
  })

  it('Install build shows a final confirmation listing the bundles it will replace', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'app.state') return { ...ready, projects: ['old-skin'] }
      if (m === 'project.list') return ['old-skin']
      if (m === 'project.get') return { name: 'old-skin', options: { output: 'bundles' } }
      if (m === 'project.files') return { folder: true, files: [] }
      if (m === 'project.problems') return { problems: [] }
      if (m === 'build.plan') return { target: 'bundles', operations: [], dropped: [], warnings: [] }
      if (m === 'install.preflight') return {
        ready: true, blocked: [], warnings: [], required_confirmations: [],
        file_operations: [
          { rel_path: 'ui-styles_assets_common.bundle', target_state: 'stock' },
          { rel_path: 'ui-styles_assets_default.bundle', target_state: 'stock' },
        ],
      }
      if (m === 'install.bundles') return { copied: ['ui-styles_assets_common.bundle', 'ui-styles_assets_default.bundle'], backup: 'b1' }
      return null
    })
    render(<App />)
    fireEvent.click(await screen.findByText('old-skin'))
    await waitFor(() => expect((rpc as any).mock.calls.some((c: unknown[]) => c[0] === 'project.get')).toBe(true))
    fireEvent.click(await screen.findByText('BUILD'))
    const actions = await screen.findByTestId('build-actions')
    fireEvent.click(within(actions).getByText('Install build'))
    await waitFor(() => expect(confirmSpy).toHaveBeenCalled())
    const msg = confirmSpy.mock.calls[0][0]
    expect(msg).toContain('ui-styles_assets_common.bundle')
    expect(msg).toContain('ui-styles_assets_default.bundle')
    expect(msg).toContain('verified stock backup first')
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('install.bundles', { name: 'old-skin' }))
    confirmSpy.mockRestore()
  })

  it('keeps Install into game in the panel header on non-layout tabs, hides it on layout tabs, and states it never installs layout edits', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    render(<App />)
    const btn = await screen.findByTestId('panel-install')
    expect(btn.getAttribute('title')).toMatch(/Never installs layout edits/i)
    for (const tab of ['OUTPUT', 'BUILD', 'PROBLEMS']) {
      fireEvent.click(screen.getByText(tab, { exact: true }))
      expect(screen.getByTestId('panel-install')).toBe(btn)
    }
    expect(screen.queryByText('PREVIEW', { exact: true })).toBeNull()
  })

  it('hides Install into game when a layout tab is active so layout tabs show only Apply and Rollback', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'app.state') return { ...ready, projects: ['old-skin'] }
      if (m === 'project.list') return ['old-skin']
      if (m === 'project.files') return { folder: true, files: [] }
      if (m === 'project.problems') return { problems: [] }
      if (m === 'project.get') return { name: 'old-skin', options: { output: 'bundles' } }
      return null
    })
    localStorage.setItem('studio.mode', 'advanced')
    localStorage.setItem('studio.session', JSON.stringify({ project: 'old-skin', tabs: ['layout:SquadComposition-Large'], active: 'layout:SquadComposition-Large', view: 'play' }))
    render(<App />)
    await screen.findByTestId('layout-canvas')
    expect(screen.queryByTestId('panel-install')).toBeNull()
    expect(screen.getByTestId('layout-apply')).toBeTruthy()
    expect(screen.getByTestId('layout-rollback')).toBeTruthy()
  })

  it('keeps the full Playground reachable as its own activity entry', async () => {
    localStorage.setItem('studio.mode', 'advanced')
    render(<App />)
    const entry = await screen.findByLabelText('Playground')
    fireEvent.click(entry)
    expect(await screen.findByTestId('full-playground')).toBeTruthy()
  })

  it('shows a centred update popup on launch, dismissible for this session, and keeps the footer action', async () => {
    ;(window as any).__TAURI_INTERNALS__ = {}
    invoke.mockImplementation(async (cmd: string) => cmd === 'app_update_check' ? { version: '1.5.1', current: '1.5.0' } : undefined)
    localStorage.setItem('studio.mode', 'advanced')
    render(<App />)
    const dialog = await screen.findByTestId('app-update-dialog')
    expect(dialog.querySelector('[role="dialog"]')).toBeTruthy()
    expect((await screen.findByTestId('app-update-status')).textContent).toContain('1.5.1')
    fireEvent.click(screen.getByTestId('app-update-dialog-later'))
    await waitFor(() => expect(screen.queryByTestId('app-update-dialog')).toBeNull())
    expect(screen.getByTestId('app-update-install')).toBeTruthy()
    fireEvent.click(screen.getByTestId('app-update-install'))
    await waitFor(() => expect(invoke).toHaveBeenCalledWith('app_update_install'))
  })

  it('restores layout tabs and the active view from the saved session', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'app.state') return { ...ready, projects: ['old-skin'] }
      if (m === 'project.list') return ['old-skin']
      if (m === 'project.files') return { folder: true, files: [] }
      return null
    })
    localStorage.setItem('studio.mode', 'advanced')
    localStorage.setItem('studio.session', JSON.stringify({ project: 'old-skin', tabs: ['layout:SquadComposition-Large'], active: 'layout:SquadComposition-Large', view: 'play' }))
    render(<App />)
    await waitFor(() => expect(screen.queryByTestId('main-tab')).toBeTruthy())
    expect(screen.getByTestId('main-tab').textContent).toContain('SquadComposition-Large')
  })
})
