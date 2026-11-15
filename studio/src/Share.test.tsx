// @vitest-environment jsdom
// S7: share and undo. The engine is mocked; what is pinned is what the screen sends and says, and that nothing happens without the person's go.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Share, { lostText, type Inspected } from './Share'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const INFO: Inspected = { skin: 'Their Skin', folder: 'Their Skin', sheets: 3, pictures: 2, fonts: 1, files: 7, build_note: 'made for game build 27.0.1; this game is 27.1.0',
  manifest: { format: 'fm-skin-studio-share/1', studio_version: '1.2.0', game_build: '27.0.1' }, refused: [{ file: 'Their Skin/run.exe', why: 'not a file type a skin uses' }] }
let prompts: string[] = []
beforeEach(() => {
  prompts = []
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'share.save') return { file: p.path, files: 4, bytes: 4096 }
    if (m === 'share.inspect') return INFO
    if (m === 'share.open') return { name: p.name }
    if (m === 'project.start_over_preview') return { project: 'mine', lost: { colours: 82, pictures: 1, 'flat look': 1 }, trash: 'C:/ws/trash' }
    if (m === 'project.start_over') return { trash: 'C:/ws/trash/mine-20261115-120000', lost: {} }
    return {}
  })
  vi.spyOn(window, 'prompt').mockImplementation(() => prompts.shift() ?? null)
})
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks() })
const show = (project: string | null = 'mine', extra: Partial<{ onOpened: any; onChanged: any }> = {}) => {
  const onOpened = extra.onOpened ?? vi.fn(async () => {}); const onChanged = extra.onChanged ?? vi.fn()
  render(<Share project={project} projects={['mine', 'Their-Skin']} say={() => {}} onOpened={onOpened} onChanged={onChanged} />)
  return { onOpened, onChanged }
}

describe('share and undo', () => {
  it('saves the skin as one file, with the Studio version sent along', async () => {
    prompts = ['C:/out/mine.zip']; show()
    fireEvent.click(screen.getByText('Save my skin as a file', { selector: 'button' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('share.save', { project: 'mine', path: 'C:/out/mine.zip', studio_version: 'development', overwrite: false }))
    expect((await screen.findByTestId('saved')).textContent).toBe('Saved: C:/out/mine.zip (4 files, 4 KB).')
  })

  it('opening a skin file shows what is inside first and makes nothing until "Make my copy"', async () => {
    prompts = ['C:/dl/their.zip']; const { onOpened } = show()
    fireEvent.click(screen.getByText('Open a skin file', { selector: 'button' }))
    const box = await screen.findByTestId('inspected')
    expect(box.textContent).toMatch(/Their Skin: 3 style sheets, 2 pictures, 1 font\./)
    expect(box.textContent).toMatch(/Made with FM Skin Studio 1\.2\.0 for game build 27\.0\.1/)
    expect(box.textContent).toMatch(/made for game build 27\.0\.1; this game is 27\.1\.0/)
    expect(screen.getByTestId('refused').textContent).toMatch(/run\.exe \(not a file type a skin uses\)/)
    expect((rpc as any).mock.calls.some((c: any[]) => c[0] === 'share.open')).toBe(false)
    expect((screen.getByLabelText('Name of your copy') as HTMLInputElement).value).toBe('Their-Skin-2')
    fireEvent.click(screen.getByText('Make my copy'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('share.open', { path: 'C:/dl/their.zip', name: 'Their-Skin-2' }))
    await waitFor(() => expect(onOpened).toHaveBeenCalledWith('Their-Skin-2'))
  })

  it('a file not made with the Studio is said so, and a taken name blocks the copy', async () => {
    ;(rpc as any).mockImplementation(async (m: string) => (m === 'share.inspect' ? { ...INFO, manifest: null, build_note: null, refused: [] } : {}))
    prompts = ['C:/dl/x.zip']; show()
    fireEvent.click(screen.getByText('Open a skin file', { selector: 'button' }))
    expect((await screen.findByTestId('inspected')).textContent).toMatch(/Not made with FM Skin Studio/)
    fireEvent.change(screen.getByLabelText('Name of your copy'), { target: { value: 'mine' } })
    expect(screen.getByText(/already exists/)).toBeTruthy()
    expect((screen.getByText('Make my copy') as HTMLButtonElement).disabled).toBe(true)
  })

  it('Start over says what is lost and where it goes, and does nothing until "Yes, start over"', async () => {
    const { onChanged } = show()
    fireEvent.click(screen.getByText('Start over ...'))
    const box = await screen.findByTestId('start-over-confirm')
    expect(box.textContent).toMatch(/82 colour changes/); expect(box.textContent).toMatch(/1 picture(?!s)/); expect(box.textContent).toMatch(/flat look/)
    expect(box.textContent).toMatch(/moved to the trash folder \(C:\/ws\/trash\), not erased/)
    expect((rpc as any).mock.calls.some((c: any[]) => c[0] === 'project.start_over')).toBe(false)
    fireEvent.click(screen.getByText('Keep my skin'))
    expect(screen.queryByTestId('start-over-confirm')).toBeNull()
    fireEvent.click(screen.getByText('Start over ...'))
    fireEvent.click(await screen.findByText('Yes, start over'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('project.start_over', { project: 'mine', confirm: true }))
    expect((await screen.findByTestId('started-over')).textContent).toMatch(/back to the game's look/)
    expect(onChanged).toHaveBeenCalled()
  })

  it('without an open skin only "Open a skin file" is offered', () => {
    show(null)
    expect(screen.queryByText('Save my skin as a file', { selector: 'button' })).toBeNull()
    expect(screen.queryByText('Start over ...')).toBeNull()
    expect(screen.getByText('Open a skin file', { selector: 'button' })).toBeTruthy()
  })

  it('lostText puts every kind in words', () => {
    expect(lostText({ colours: 1, 'colour swaps': 2, rules: 1, pictures: 2, fonts: 1, 'imported files': 3, 'flat look': 1 })).toEqual([
      '1 colour change', "2 colours swapped in the game's rules", '1 rule written in Advanced mode', '2 pictures', '1 font', '3 files of a skin you opened', 'the flat look for every club (club colours removed)'])
  })
})
