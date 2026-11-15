// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { groupOf, grouped, hexOf } from './colourGroups'
import Palette, { lightTextContrast } from './Palette'
import { MAX_MY_COLOURS, MY_COLOURS_KEY, addMine, loadMine, removeMine } from './myColours'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const rows = [
  { name: '--global-background', rgb: '#16181D', a: 1, reach: 40 },
  { name: '--layout-modules-block-surface', rgb: '#20242B', a: 1, reach: 12 },
  { name: '--layout-surfaces-cards-surface', rgb: '#1E2128', a: 0.5, reach: 9 },
  { name: '--zzz-unlisted-thing', rgb: '#123456', a: 1, reach: 1 },
]
let model: any
beforeEach(() => {
  localStorage.clear()
  model = { name: 'p', options: {}, token_overrides: [] }
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'project.get') return model
    if (m === 'tokens.browse') return { total: rows.length, rows }
    if (m === 'project.save') { model = p.project; return { project: model } }
    return { rows: [] }
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })
const saved = () => (rpc as any).mock.calls.filter((c: unknown[]) => c[0] === 'project.save').map((c: any) => c[1].project)

describe('grouping', () => {
  it('names groups in plain words from the token names, and puts unknown ones last under their own prefix', () => {
    expect(groupOf('--global-background')).toBe('Page background')
    expect(groupOf('--layout-modules-block-surface')).toBe('Panels, cards and tiles')
    expect(groupOf('--buttons-toggle-active')).toBe('Buttons')
    expect(groupOf('--zzz-unlisted-thing')).toBe('Other: zzz unlisted')
    const g = grouped(rows)
    expect(g[g.length - 1].label).toBe('Other: zzz unlisted')
    expect(g.find((x) => x.label === 'Panels, cards and tiles')!.rows.length).toBe(2)
  })
  it('writes a colour with its alpha only when it is not opaque', () => {
    expect(hexOf('#16181d', 1)).toBe('#16181D'); expect(hexOf('#16181D', 0.5)).toBe('#16181D80')
  })
})

describe('the Colours view', () => {
  it('shows everything the game uses in closed groups with counts, and says nothing is changed yet', async () => {
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    expect(await screen.findByText(/WHAT THE GAME USES \(4\)/)).toBeTruthy()
    expect(screen.getByText(/Panels, cards and tiles/)).toBeTruthy()
    expect(screen.queryByLabelText('Colour of layout-modules-block-surface')).toBeNull()          // closed until opened
    expect(screen.getByText(/Nothing changed yet/)).toBeTruthy()
  })

  it('clicking a colour in an opened group starts a change from the game\'s own value and keeps its alpha; "put back" undoes it', async () => {
    const changed = vi.fn()
    render(<Palette project="p" onChanged={changed} say={() => {}} />)
    fireEvent.click(await screen.findByText(/Panels, cards and tiles/))
    fireEvent.change(screen.getByLabelText('Colour of layout-surfaces-cards-surface'), { target: { value: '#ff0000' } })
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].token_overrides).toEqual([{ token: '--layout-surfaces-cards-surface', value: { rgb: '#FF0000', a: 0.5 }, vanilla: '#1E212880' }])
    expect(changed).toHaveBeenCalled()
    fireEvent.click(await screen.findByText('put back'))
    await waitFor(() => expect(saved().length).toBe(2))
    expect(saved()[1].token_overrides).toEqual([])
  })

  it('a second click on a changed colour edits that change instead of adding another', async () => {
    model.token_overrides = [{ token: '--global-background', value: { rgb: '#112233', a: 1 }, vanilla: '#16181D' }]
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    fireEvent.click(await screen.findByText(/Page background/))
    fireEvent.change(screen.getByLabelText('Colour of global-background'), { target: { value: '#445566' } })
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].token_overrides).toEqual([{ token: '--global-background', value: { rgb: '#445566', a: 1 }, vanilla: '#16181D' }])
  })

  it('the search opens the groups that match, by name or by colour code', async () => {
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    await screen.findByText(/WHAT THE GAME USES/)
    fireEvent.change(screen.getByLabelText('Find a colour'), { target: { value: 'cards' } })
    expect(screen.getByLabelText('Colour of layout-surfaces-cards-surface')).toBeTruthy()
    expect(screen.queryByLabelText('Colour of global-background')).toBeNull()
    fireEvent.change(screen.getByLabelText('Find a colour'), { target: { value: '#123456' } })
    expect(screen.getByLabelText('Colour of zzz-unlisted-thing')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Find a colour'), { target: { value: 'nothing-like-this' } })
    expect(screen.getByText(/No colour matches that/)).toBeTruthy()
  })
})

describe('the top bar and headers', () => {
  it('is one flat colour for every club, off by default, and says it is unchecked in the game', async () => {
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    const box = (await screen.findByText(/One flat colour instead of each club/)).querySelector('input') as HTMLInputElement
    expect(box.checked).toBe(false)
    expect(screen.queryByLabelText('Top bar colour')).toBeNull()
    expect(screen.getByTestId('topbar-section').textContent).toMatch(/Not yet checked in the game/)
    expect(screen.getByTestId('topbar-section').textContent).toMatch(/no single colour to change/)
  })

  it('turning it on writes the option, its colour can be chosen, and turning it off puts the club colours back', async () => {
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    const box = (await screen.findByText(/One flat colour instead of each club/)).querySelector('input') as HTMLInputElement
    fireEvent.click(box)
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].options.club_colours).toBe(false)
    fireEvent.change(await screen.findByLabelText('Top bar colour'), { target: { value: '#0a0a0a' } })
    await waitFor(() => expect(saved().length).toBe(2))
    expect(saved()[1].options.club_colours_replacement).toEqual({ rgb: '#0A0A0A', a: 1 })
    expect(saved()[1].options.club_colours).toBe(false)
    fireEvent.click((screen.getByText(/One flat colour instead of each club/)).querySelector('input')!)
    await waitFor(() => expect(saved().length).toBe(3))
    expect(saved()[2].options.club_colours).toBe(true)
  })

  it('a project that already uses the flat look shows it on, with its colour', async () => {
    model.options = { club_colours: false, club_colours_replacement: { rgb: '#202020', a: 1 } }
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    expect(((await screen.findByLabelText('Top bar colour')) as HTMLInputElement).value).toBe('#202020')
  })
})

describe('the bar colour and its light text', () => {
  it('the game keeps light text on the bar, so a light colour is warned about and a dark one is not', async () => {
    expect(lightTextContrast('#171717')).toBeGreaterThan(10)
    expect(lightTextContrast('#FFFFFF')).toBeLessThan(1.1)
    model.options = { club_colours: false, club_colours_replacement: { rgb: '#E0E0E0', a: 1 } }
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    expect((await screen.findByTestId('bar-contrast')).textContent).toMatch(/hard to read/)
    cleanup()
    model.options = { club_colours: false, club_colours_replacement: { rgb: '#202020', a: 1 } }
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    await screen.findByLabelText('Top bar colour')
    expect(screen.queryByTestId('bar-contrast')).toBeNull()
  })
})

describe('My colours (a personal palette)', () => {
  const stored = () => JSON.parse(localStorage.getItem(MY_COLOURS_KEY) || '[]')
  const add = (hex: string) => { fireEvent.change(screen.getByLabelText('A colour to add to My colours'), { target: { value: hex } }); fireEvent.click(screen.getByText('Add to My colours')) }

  it('the storage rules: up to ten, no duplicates, upper case, nothing that is not a colour', () => {
    let l: string[] = []
    for (let i = 0; i < MAX_MY_COLOURS; i++) { const r = addMine(l, '#0000' + (i < 10 ? '0' + i : i)); expect(r.ok).toBe(true); l = r.list }
    expect(l.length).toBe(10)
    expect(addMine(l, '#FFFFFF')).toMatchObject({ ok: false }); expect(addMine(l, '#FFFFFF').why).toMatch(/holds 10/)
    expect(addMine(['#AABBCC'], '#aabbcc')).toMatchObject({ ok: false }); expect(addMine([], 'red').ok).toBe(false)
    expect(addMine([], '#aabbcc').list).toEqual(['#AABBCC'])
    expect(removeMine(['#AABBCC', '#112233'], '#aabbcc')).toEqual(['#112233'])
  })

  it('a stored value that is not ours, or storage that throws, starts empty and never crashes', () => {
    localStorage.setItem(MY_COLOURS_KEY, '{"not":"a list"}'); expect(loadMine()).toEqual([])
    localStorage.setItem(MY_COLOURS_KEY, JSON.stringify(['#aabbcc', 'nope', '#AABBCC', 7, '#112233'])); expect(loadMine()).toEqual(['#AABBCC', '#112233'])
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') }); expect(loadMine()).toEqual([]); spy.mockRestore()
  })

  it('starts empty and says what it is for; adding is an explicit action that is remembered', async () => {
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    expect((await screen.findByTestId('my-colours')).textContent).toMatch(/Nothing saved yet/)
    expect(screen.getByText('MY COLOURS (0/10)')).toBeTruthy()
    add('#ff8800')
    expect(await screen.findByLabelText('Remove #FF8800 from My colours')).toBeTruthy()
    expect(stored()).toEqual(['#FF8800'])
    expect(saved().length).toBe(0)                                  // saving a colour to My colours never touches the project
  })

  it('refuses a duplicate and an eleventh colour, in words, and removal is explicit', async () => {
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    await screen.findByTestId('my-colours')
    add('#112233'); add('#112233')
    expect(screen.getByRole('status').textContent).toMatch(/already in My colours/)
    for (let i = 1; i < 10; i++) add('#00000' + i)
    expect(screen.getByText('MY COLOURS (10/10)')).toBeTruthy()
    expect((screen.getByText('Add to My colours') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('status').textContent).toBe('My colours holds 10. Remove one to add another.')       // a disabled button says why (found by the walkthrough)
    fireEvent.click(screen.getByLabelText('Remove #112233 from My colours'))
    expect(screen.getByText('MY COLOURS (9/10)')).toBeTruthy(); expect(stored().includes('#112233')).toBe(false)
  })

  it('a saved colour is one click beside the raw picker of a row: it applies the colour and keeps the alpha, and put back still returns to the game', async () => {
    localStorage.setItem(MY_COLOURS_KEY, JSON.stringify(['#FF8800']))
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    fireEvent.click(await screen.findByText(/Panels, cards and tiles/))
    fireEvent.click(screen.getByLabelText('My colours for layout-surfaces-cards-surface'))
    fireEvent.click(screen.getByLabelText('Use #FF8800'))
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].token_overrides).toEqual([{ token: '--layout-surfaces-cards-surface', value: { rgb: '#FF8800', a: 0.5 }, vanilla: '#1E212880' }])
    expect(screen.queryByLabelText('Use #FF8800')).toBeNull()                 // the choices close after a pick
    fireEvent.click(await screen.findByText('put back'))
    await waitFor(() => expect(saved().length).toBe(2))
    expect(saved()[1].token_overrides).toEqual([])                           // back to the game's own colour, not to a previous pick
  })

  it('a row can save its own current colour with the star, and the top bar colour has the same two controls', async () => {
    model.options = { club_colours: false, club_colours_replacement: { rgb: '#202020', a: 1 } }
    render(<Palette project="p" onChanged={() => {}} say={() => {}} />)
    fireEvent.click(await screen.findByText(/Page background/))
    fireEvent.click(screen.getByLabelText('Save the colour of global-background to My colours'))
    expect(stored()).toEqual(['#16181D'])
    fireEvent.click(screen.getByLabelText('Save the top bar colour to My colours'))
    expect(stored()).toEqual(['#16181D', '#202020'])
    fireEvent.click(screen.getByLabelText('Use #16181D', { selector: 'button' }))
    await waitFor(() => expect(saved().length).toBe(1))
    expect(saved()[0].options.club_colours_replacement).toEqual({ rgb: '#16181D', a: 1 })
  })
})
