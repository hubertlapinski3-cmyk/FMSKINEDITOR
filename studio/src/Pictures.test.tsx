// @vitest-environment jsdom
// S6: pictures in three steps. The engine is mocked; what is pinned is what the screen offers, sends and says.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Pictures, { lookFor, type PicCatalog } from './Pictures'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const CAT: PicCatalog = {
  rows: [
    { kind: 'wallpaper', game_kind: 'texture', bundle: 'ui-backgrounds_assets_.bundle', path_id: '9', name: 'fm27_skin_default', w: 1920, h: 1080, where_default: ['report-pages', 'main-screens'] },
    { kind: 'wallpaper', game_kind: 'texture', bundle: 'ui-backgrounds_assets_.bundle', path_id: '10', name: 'start_screen_bg', where_default: ['start-screen'] },
    { kind: 'icon', game_kind: 'icon', bundle: 'ui-icons_assets_2x.bundle', path_id: '5', name: 'tick_small', w: 32, h: 32 },
  ],
  counts: { wallpapers: 2, icons: 1, left_out: 51 },
  places: { 'report-pages': 'Report and tool pages (player ...)', 'main-screens': 'Main screens (portal, squad ...)', 'start-screen': 'Start screen' },
  look_at: { 'main-screens': { name: 'SquadScreen', label: 'Squad screen' } },
}
let swaps: any[] = []
beforeEach(() => {
  swaps = []
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'simple.pictures') return CAT
    if (m === 'project.get') return { image_swaps: swaps }
    if (m === 'images.commit') { swaps = [...swaps, { bundle: p.bundle, path_id: p.path_id, name: p.name, kind: p.kind, source: 'x.png', where: p.where }]; return { project: { image_swaps: swaps } } }
    if (m === 'images.remove') { swaps = swaps.filter((s) => s.path_id !== p.path_id); return { project: { image_swaps: swaps } } }
    if (m === 'images.thumb' || m === 'images.preview_file') return { content_type: 'image/png', base64: 'AA==' }
    return {}
  })
  vi.spyOn(window, 'prompt').mockReturnValue('C:/pics/mine.png')
})
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks() })
const show = (onLook = vi.fn()) => { render(<Pictures project="mine" say={() => {}} onChanged={() => {}} onLook={onLook} />); return onLook }
const use = () => screen.getByText('Use my picture') as HTMLButtonElement

describe('pictures in three steps', () => {
  it('offers only what a native skin can replace, and says how many are left out and why', async () => {
    show()
    expect(await screen.findByText('Wallpapers (2)')).toBeTruthy()
    expect(screen.getByText('fm27_skin_default')).toBeTruthy(); expect(screen.queryByText('tick_small')).toBeNull()
    fireEvent.click(screen.getByText('Icons (1)'))
    expect(screen.getByText('tick_small')).toBeTruthy()
    expect(screen.getByText(/51 more pictures are placed by the game's code/)).toBeTruthy()
  })

  it('a wallpaper: choose it, pick a file, its default places are ticked, use it, then see it on the Squad screen', async () => {
    const onLook = show()
    fireEvent.click(await screen.findByLabelText('Choose fm27_skin_default'))
    expect(use().disabled).toBe(true)
    expect((screen.getByLabelText(/Main screens/) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText(/Report and tool pages/) as HTMLInputElement).checked).toBe(true)
    fireEvent.click(screen.getByText('Pick a file'))
    await waitFor(() => expect(use().disabled).toBe(false))
    fireEvent.click(use())
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('images.commit', { project: 'mine', bundle: 'ui-backgrounds_assets_.bundle', path_id: '9', kind: 'texture', name: 'fm27_skin_default', path: 'C:/pics/mine.png', where: ['report-pages', 'main-screens'] }))
    expect((await screen.findByTestId('pic-done')).textContent).toMatch(/after Put it in the game/)
    fireEvent.click(screen.getByText('See it in Look at it (Squad screen)'))
    expect(onLook).toHaveBeenCalledWith({ name: 'SquadScreen', label: 'Squad screen' })
  })

  it('no place ticked: Use is off and it says so', async () => {
    show()
    fireEvent.click(await screen.findByLabelText('Choose fm27_skin_default'))
    fireEvent.click(screen.getByText('Pick a file'))
    fireEvent.click(screen.getByLabelText(/Main screens/)); fireEvent.click(screen.getByLabelText(/Report and tool pages/))
    expect(screen.getByText('Tick at least one place.')).toBeTruthy()
    await waitFor(() => expect(use().disabled).toBe(true))
  })

  it('a place Look at it cannot draw says so instead of opening a layout it has not checked', async () => {
    show()
    fireEvent.click(await screen.findByLabelText('Choose start_screen_bg'))
    fireEvent.click(screen.getByText('Pick a file'))
    await waitFor(() => expect(use().disabled).toBe(false)); fireEvent.click(use())
    expect((await screen.findByTestId('pic-done')).textContent).toMatch(/screens Look at it can't draw yet/)
    expect(screen.queryByText(/See it in Look at it/)).toBeNull()
  })

  it('an icon has nothing to tick, is sent without places, and opens Look at it plainly', async () => {
    const onLook = show()
    fireEvent.click(await screen.findByText('Icons (1)'))
    fireEvent.click(screen.getByLabelText('Choose tick_small'))
    expect(screen.getByText(/An icon shows wherever the game uses it/)).toBeTruthy()
    fireEvent.click(screen.getByText('Pick a file'))
    await waitFor(() => expect(use().disabled).toBe(false)); fireEvent.click(use())
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('images.commit', { project: 'mine', bundle: 'ui-icons_assets_2x.bundle', path_id: '5', kind: 'icon', name: 'tick_small', path: 'C:/pics/mine.png' }))
    fireEvent.click(await screen.findByText('Open Look at it'))
    expect(onLook).toHaveBeenCalledWith(null)
  })

  it('every replaced picture can be put back', async () => {
    swaps = [{ bundle: 'ui-icons_assets_2x.bundle', path_id: '5', name: 'tick_small', kind: 'icon', source: 'x.png' }]
    show()
    fireEvent.click(await screen.findByText('Put it back'))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('images.remove', { project: 'mine', bundle: 'ui-icons_assets_2x.bundle', path_id: '5' }))
    await waitFor(() => expect(screen.queryByText('Put it back')).toBeNull())
  })

  it('lookFor suggests only a measured layout', () => {
    expect(lookFor(CAT.rows[0], ['main-screens'], CAT)).toEqual({ name: 'SquadScreen', label: 'Squad screen' })
    expect(lookFor(CAT.rows[0], ['report-pages'], CAT)).toBeNull()
    expect(lookFor(CAT.rows[2], [], CAT)).toBeNull()
  })
})
