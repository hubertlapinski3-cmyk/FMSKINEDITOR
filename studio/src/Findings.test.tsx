// @vitest-environment jsdom
// The Findings view (Advanced mode): the theme-by-screen grid, the screenshot, the compare row and the list of what the themes do not change.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import Findings, { VERDICT_WORDS, type FindingsData } from './Findings'

vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: class extends Error {}, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import { rpc } from './engine'

const DATA: FindingsData = {
  title: 'Session 2 findings', date: '2026-11-15', source: 'By eye.', game: 'game 27',
  themes: [{ id: 'forest', name: 'Forest', inputs: 'a', skin: 'gallery-forest' }, { id: 'ocean', name: 'Ocean', inputs: 'b', skin: 'gallery-ocean' }],
  screens: [{ id: 'squad', name: 'Squad' }, { id: 'competition', name: 'Competition' }],
  verdicts: { 'forest/squad': { v: 'exceptions', note: 'Chips keep the game colours.' }, 'ocean/squad': { v: 'clash', note: 'Teal widget on navy.' }, 'forest/competition': { v: 'works', note: 'ok' }, 'ocean/competition': { v: 'not-done', note: 'dropdown' } },
  findings: [
    { id: 'teal', kind: 'missing', title: 'Teal panels stay teal', screens: ['squad'], themes: ['ocean'], text: 'A gradient the game draws.', fix: 'Not built.' },
    { id: 'gap', kind: 'open', title: 'Competition missing', screens: ['competition'], themes: ['ocean'], text: 'Dropdown.' },
    { id: 'tx', kind: 'works', title: 'Text reaches', screens: ['squad'], themes: ['forest'], text: 'E6EFE9' },
  ],
  shots: { 'forest/squad': 'gallery-forest-squad.png', 'ocean/squad': 'gallery-ocean-squad.png' },
}
let asked: string[] = []
beforeEach(() => {
  asked = []
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'findings.get') return DATA
    if (m === 'screens.image') { asked.push(p.name); return { content_type: 'image/png', base64: 'AA' + p.name.length } }
    return {}
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Findings', () => {
  it('shows a verdict per theme and screen in words, how many screenshots are here, and the privacy line', async () => {
    render(<Findings say={() => {}} />)
    expect(await screen.findByText('Session 2 findings')).toBeTruthy()
    expect(screen.getByLabelText('Forest, Squad: works, with exceptions')).toBeTruthy()
    expect(screen.getByLabelText('Ocean, Squad: clashes')).toBeTruthy()
    expect(screen.getByLabelText('Ocean, Competition: not looked at')).toBeTruthy()
    expect(screen.getByText(/never put in a project or a skin\. 2 of 4 are here/)).toBeTruthy()
    expect(VERDICT_WORDS.works).toBe('works')
  })

  it('opens a cell: its note, its screenshot, the same screen in every theme, and the findings about that screen', async () => {
    render(<Findings say={() => {}} />)
    fireEvent.click(await screen.findByTestId('cell-ocean-squad'))
    expect(screen.getByTestId('verdict-note').textContent).toBe('clashes: Teal widget on navy.')
    expect(await screen.findByAltText('Ocean on Squad')).toBeTruthy()
    expect(screen.getAllByText('Teal panels stay teal').length).toBeGreaterThan(0)
    expect(await screen.findByAltText('Forest on Squad (small)')).toBeTruthy()               // the compare row shows the other theme too (its picture may already be cached)
    expect(screen.getByTestId('compare').querySelectorAll('figure').length).toBe(2)
  })

  it('a screen without a screenshot says so, and a cell not looked at is still listed', async () => {
    render(<Findings say={() => {}} />)
    fireEvent.click(await screen.findByTestId('cell-ocean-competition'))
    expect((await screen.findAllByText('No screenshot for this one')).length).toBeGreaterThan(0)
    expect(screen.getByTestId('verdict-note').textContent).toMatch(/not looked at: dropdown/)
  })

  it('the list of everything found can be filtered by kind, and a finding opens its screen', async () => {
    render(<Findings say={() => {}} />)
    await screen.findByText('Session 2 findings')
    const list = screen.getByTestId('fnd-list')
    expect(list.textContent).toMatch(/Teal panels stay teal/); expect(list.textContent).toMatch(/Competition missing/); expect(list.textContent).not.toMatch(/Text reaches/)
    fireEvent.click(screen.getByLabelText(/^Works \(1\)/))
    expect(screen.getByTestId('fnd-list').textContent).toMatch(/Text reaches/)
    fireEvent.click(screen.getByLabelText(/^Not changed by the theme/))
    expect(screen.getByTestId('fnd-list').textContent).not.toMatch(/Teal panels stay teal/)
    fireEvent.click(screen.getByText('Competition missing'))
    expect(screen.getByRole('heading', { name: 'Ocean on Competition' })).toBeTruthy()
  })

  it('an engine failure is shown as its sentence', async () => {
    ;(rpc as any).mockImplementation(async () => { throw Object.assign(new Error('boom'), { data: { plain: 'The findings could not be read.' } }) })
    render(<Findings say={() => {}} />)
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})
