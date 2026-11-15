// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { resolveMode } from './mode'
import { GENERIC, sayOf } from './plainError'
import Setup from './Setup'
import Start, { CLUB_REMOVAL_TEXT, suggestName } from './Start'

const { FakeRpcError } = vi.hoisted(() => ({ FakeRpcError: class FakeRpcError extends Error { code: number; data: any; constructor(e: { code: number; message: string; data?: any }) { super(e.message); this.code = e.code; this.data = e.data } } }))
vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: FakeRpcError, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const base = { install: null, running: false, tamper: null, snapshot_mismatch: null, vanilla: null, indexed: false, projects: [] as string[] }
const withGame = { ...base, install: { game_dir: 'C:/FM27', aa_dir: 'C:/FM27/aa', version: '27.0.1' } }
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('mode', () => {
  it('a fresh install (nothing stored, an empty workspace) starts in Simple; one that already holds projects is Advanced', () => {
    expect(resolveMode(null, 0)).toBe('simple')
    expect(resolveMode(null, 3)).toBe('advanced')
  })
  it('a stored choice wins, and the old name expert is advanced', () => {
    expect(resolveMode('expert', 0)).toBe('advanced')
    expect(resolveMode('advanced', 0)).toBe('advanced')
    expect(resolveMode('simple', 7)).toBe('simple')
  })
  it('a stored value that is not a mode is treated as nothing stored', () => {
    expect(resolveMode('garbage', 0)).toBe('simple')
    expect(resolveMode('', 2)).toBe('advanced')
  })
})

describe('plain errors', () => {
  it('uses the engine sentence and keeps the raw text as the details', () => {
    const s = sayOf(new FakeRpcError({ code: -32020, message: 'the game is running or updating; close it first', data: { plain: 'Close Football Manager, and let Steam finish any update, then try again.' } }))
    expect(s.plain).toMatch(/^Close Football Manager/)
    expect(s.details).toContain('running or updating')
  })
  it('never shows an empty sentence', () => {
    expect(sayOf(new FakeRpcError({ code: -32000, message: 'ValueError: x' })).plain).toBe(GENERIC)
    expect(sayOf(new Error('Failed to fetch')).plain).toMatch(/can't reach its engine/)
  })
})

describe('first-run setup', () => {
  it('runs the missing steps in order, shows each one done with its real time, and refreshes', async () => {
    const refresh = vi.fn(async () => {})
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'game.detect') return { ...withGame }
      if (m === 'snapshot.take') return { ...withGame, vanilla: { game_build: '27.0.1' } }
      if (m === 'index.build') return { job: 'j1' }
      if (m === 'jobs.wait') return { state: 'done', error: null }
      throw new Error('unexpected ' + m)
    })
    render(<Setup state={base} refresh={refresh} say={() => {}} />)
    fireEvent.click(screen.getByText('Find my game and read it'))
    await waitFor(() => expect(refresh).toHaveBeenCalled())
    expect((rpc as any).mock.calls.map((c: unknown[]) => c[0])).toEqual(['game.detect', 'snapshot.take', 'index.build', 'jobs.wait'])
    expect(screen.getAllByText(/done in \d/).length).toBe(3)
  })

  it('a step that fails shows the engine sentence, keeps the details, and lets the user try again', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'snapshot.take') throw new FakeRpcError({ code: -32000, message: 'RuntimeError: close the game before taking the vanilla snapshot', data: { plain: 'Close Football Manager first, then try again.' } })
      throw new Error('unexpected ' + m)
    })
    render(<Setup state={withGame} refresh={async () => {}} say={() => {}} />)
    fireEvent.click(screen.getByText('Read the game'))
    expect(await screen.findByText('Close Football Manager first, then try again.')).toBeTruthy()
    expect(screen.getByText(/close the game before taking the vanilla snapshot/)).toBeTruthy()
    await waitFor(() => expect((screen.getByText('Read the game') as HTMLButtonElement).disabled).toBe(false))
  })

  it('asks for the folder when the game is not found, and says so in words when none is chosen', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => (m === 'game.detect' ? { ...base, candidates: [] } : null))
    render(<Setup state={base} refresh={async () => {}} say={() => {}} pickFolder={async () => undefined} />)
    fireEvent.click(screen.getByText('Find my game and read it'))
    expect(await screen.findByText(/No game folder was chosen/)).toBeTruthy()
  })

  it('offers the copies when several are found, and uses the one picked', async () => {
    ;(rpc as any).mockImplementation(async (m: string, p: any) => {
      if (m === 'game.detect') return { ...base, candidates: [{ game_dir: 'C:/A' }, { game_dir: 'D:/B', version: '27.0.2' }] }
      if (m === 'game.select') return { ...withGame, install: { ...withGame.install, game_dir: p.game_dir }, vanilla: { game_build: '1' }, indexed: true }
      return null
    })
    render(<Setup state={base} refresh={async () => {}} say={() => {}} />)
    fireEvent.click(screen.getByText('Find my game and read it'))
    fireEvent.click(await screen.findByText(/D:\/B \(27\.0\.2\)/))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('game.select', { game_dir: 'D:/B' }))
  })

  it('says it is ready when nothing is missing', () => {
    render(<Setup state={{ ...withGame, vanilla: { game_build: '1' }, indexed: true }} refresh={async () => {}} say={() => {}} />)
    expect(screen.getByText('Ready')).toBeTruthy()
  })
})

describe('start screen', () => {
  beforeEach(() => { ;(rpc as any).mockImplementation(async () => ({})) })

  it('offers the three ways to begin, and labels the ready-made theme as not yet checked in the game', () => {
    render(<Start projects={[]} onCreated={async () => {}} onImport={() => {}} say={() => {}} />)
    expect(screen.getByText('Start from a ready-made theme')).toBeTruthy()
    expect(screen.getByText('Open a skin I downloaded')).toBeTruthy()
    expect(screen.getByText("Start from the game's look")).toBeTruthy()
    expect(screen.getByText(/Not yet checked in the game in this form/)).toBeTruthy()
  })

  it('the theme asks about club colours, and says what removing them does without calling it proven', async () => {
    const created = vi.fn(async () => {})
    render(<Start projects={[]} onCreated={created} onImport={() => {}} say={() => {}} />)
    fireEvent.click(screen.getByText('Start from a ready-made theme'))
    expect((screen.getByLabelText('Name of your skin') as HTMLInputElement).value).toBe('my-first-skin')
    expect(screen.queryByTestId('club-removal-text')).toBeNull()
    fireEvent.click(screen.getByLabelText(/one flat look for every club/))
    expect(screen.getByTestId('club-removal-text').textContent).toBe(CLUB_REMOVAL_TEXT)
    expect(CLUB_REMOVAL_TEXT).not.toMatch(/proven/i)
    expect(CLUB_REMOVAL_TEXT).toMatch(/not been looked at in the game/)
    fireEvent.click(screen.getByText('Make it'))
    await waitFor(() => expect(created).toHaveBeenCalledWith('my-first-skin'))
    expect(rpc).toHaveBeenCalledWith('project.create_folder', { name: 'my-first-skin', target: 'native', preset: 'crimson', keep_club_colours: false })
  })

  it('keeping the club colours is the default', async () => {
    render(<Start projects={[]} onCreated={async () => {}} onImport={() => {}} say={() => {}} />)
    fireEvent.click(screen.getByText('Start from a ready-made theme'))
    fireEvent.click(screen.getByText('Make it'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('project.create_folder', { name: 'my-first-skin', target: 'native', preset: 'crimson', keep_club_colours: true }))
  })

  it("the game's look makes an empty native project with no preset", async () => {
    render(<Start projects={[]} onCreated={async () => {}} onImport={() => {}} say={() => {}} />)
    fireEvent.click(screen.getByText("Start from the game's look"))
    fireEvent.click(screen.getByText('Make it'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('project.create_folder', { name: 'my-first-skin', target: 'native', keep_club_colours: true }))
  })

  it("the game's look asks the club-colour question too, and the answer goes with it", async () => {
    render(<Start projects={[]} onCreated={async () => {}} onImport={() => {}} say={() => {}} />)
    fireEvent.click(screen.getByText("Start from the game's look"))
    expect(screen.getByText('The club\'s own colours')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/one flat look for every club/))
    expect(screen.getByTestId('club-removal-text')).toBeTruthy()
    fireEvent.click(screen.getByText('Make it'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('project.create_folder', { name: 'my-first-skin', target: 'native', keep_club_colours: false }))
  })

  it('opening a downloaded skin goes to the import, and a taken or bad name cannot be made', () => {
    const imp = vi.fn()
    render(<Start projects={['my-first-skin']} onCreated={async () => {}} onImport={imp} say={() => {}} />)
    fireEvent.click(screen.getByText('Open a skin I downloaded')); expect(imp).toHaveBeenCalled()
    fireEvent.click(screen.getByText("Start from the game's look"))
    expect((screen.getByLabelText('Name of your skin') as HTMLInputElement).value).toBe('my-first-skin-2')   // a free name is suggested
    fireEvent.change(screen.getByLabelText('Name of your skin'), { target: { value: 'my-first-skin' } })
    expect(screen.getByText(/already exists/)).toBeTruthy(); expect((screen.getByText('Make it') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Name of your skin'), { target: { value: 'bad name!' } })
    expect(screen.getByText(/Use only letters/)).toBeTruthy(); expect((screen.getByText('Make it') as HTMLButtonElement).disabled).toBe(true)
  })

  it('an engine refusal is shown as its sentence with the details kept', async () => {
    ;(rpc as any).mockImplementation(async () => { throw new FakeRpcError({ code: -32000, message: 'RuntimeError: no style index; take a vanilla snapshot and index first', data: { plain: 'The Studio hasn\'t read the game\'s styles yet.' } }) })
    render(<Start projects={[]} onCreated={async () => {}} onImport={() => {}} say={() => {}} />)
    fireEvent.click(screen.getByText('Start from a ready-made theme')); fireEvent.click(screen.getByText('Make it'))
    expect(await screen.findByText(/hasn't read the game's styles yet/)).toBeTruthy()
    expect(screen.getByText(/no style index/)).toBeTruthy()
  })

  it('suggestName picks the first free name', () => {
    expect(suggestName([])).toBe('my-first-skin')
    expect(suggestName(['my-first-skin', 'my-first-skin-2'])).toBe('my-first-skin-3')
  })
})
