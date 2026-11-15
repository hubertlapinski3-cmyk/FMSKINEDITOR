// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('@monaco-editor/react', () => ({ default: () => null }))
vi.mock('./monaco', () => ({ lint: vi.fn(), registerQuickFixes: vi.fn(), registerTokenCompletion: vi.fn() }))
vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(async () => ({})), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'
import App from './App'

const ready = { install: { game_dir: 'C:/FM27', aa_dir: 'C:/FM27/aa', version: '27.0.1' }, running: false, tamper: { state: 'clean' }, snapshot_mismatch: null, vanilla: { game_build: '27.0.1' }, indexed: true }
function engine(state: Record<string, unknown>, projects: string[]) {
  ;(rpc as any).mockImplementation(async (m: string) => (m === 'app.state' ? { ...state, projects } : m === 'project.list' ? projects : null))
}
beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear() })

describe('the mode a run starts in', () => {
  it('a fresh install (empty workspace, nothing stored) starts in Simple, with the labelled navigation and the start screen, and remembers it', async () => {
    engine(ready, [])
    render(<App />)
    expect(await screen.findByTestId('start')).toBeTruthy()
    for (const w of ['Projects', 'Colours', 'Pictures', 'Look at it', 'Advanced']) expect(await screen.findByText(w)).toBeTruthy()
    expect(localStorage.getItem('studio.mode')).toBe('simple')
  })

  it('an install that already has projects (nothing stored) becomes Advanced: the letters, and the start choices are the landing page there too while no project is open', async () => {
    engine(ready, ['old-skin'])
    render(<App />)
    await waitFor(() => expect(localStorage.getItem('studio.mode')).toBe('advanced'))
    expect(screen.getByTitle('Explorer')).toBeTruthy()
    expect(await screen.findByTestId('start')).toBeTruthy()
    expect(screen.queryByText('Colours')).toBeNull()
  })

  it('the other views work without a project in both modes: the start choices only take the landing page', async () => {
    engine(ready, [])
    render(<App />)
    await screen.findByTestId('start')
    fireEvent.click(await screen.findByText('Look at it'))
    await waitFor(() => expect(screen.queryByTestId('start')).toBeNull())
  })

  it('a stored "expert" is migrated to "advanced"', async () => {
    localStorage.setItem('studio.mode', 'expert')
    engine(ready, [])
    render(<App />)
    await waitFor(() => expect(localStorage.getItem('studio.mode')).toBe('advanced'))
    expect(screen.getByTitle('Explorer')).toBeTruthy()
  })

  it('Simple mode has "Put it in the game" as a labelled sidebar item, switched off until a project is open', async () => {
    engine(ready, [])
    render(<App />)
    const item = await screen.findByText('Put it in the game')
    expect(item.tagName).toBe('BUTTON')
    expect((item as HTMLButtonElement).disabled).toBe(true)
  })

  it('a stored "simple" is kept even with projects', async () => {
    localStorage.setItem('studio.mode', 'simple')
    engine(ready, ['a', 'b'])
    render(<App />)
    expect(await screen.findByText('Look at it')).toBeTruthy()
    expect(localStorage.getItem('studio.mode')).toBe('simple')
  })

  it('a fresh install whose game has not been read yet shows the setup, in either mode, and no start screen', async () => {
    engine({ ...ready, install: null, vanilla: null, indexed: false }, [])
    render(<App />)
    expect(await screen.findByTestId('setup')).toBeTruthy()
    expect(screen.queryByTestId('start')).toBeNull()
  })
})
