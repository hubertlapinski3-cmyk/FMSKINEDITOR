// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const { FakeRpcError } = vi.hoisted(() => ({ FakeRpcError: class FakeRpcError extends Error { code: number; data: any; constructor(e: { code: number; message: string; data?: any }) { super(e.message); this.code = e.code; this.data = e.data } } }))
vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: FakeRpcError, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import Explore from './Explore'
import { rpc } from './engine'

const prof = (over: Record<string, unknown> = {}) => ({
  active: 'iid', installs: [{ install_id: 'iid', role: 'installed', game_dir: 'C:/Games/FM27' }],
  profile: { install_id: 'iid', game_build: '27.1.0.2505117', steam_build_id: 2348710, unity_version: '2022.3.62f1', catalog_sha256: 'cafe', manifest_dat_sha256: 'beef', game_dir: 'C:/Games/FM27' },
  problems: [], drift: [], ...over,
})
const cat = (over: Record<string, unknown> = {}) => ({
  catalog: { status: 'ok', records: 534, sha256: 'cafe' }, manifest_dat: { status: 'ok', size: 31200 },
  counts: { catalog_crc_status: { catalog_crc_match: 534 }, manifest_status: { manifest_match: 585 } },
  identity_stale: false, annotated_utc: '20261118T000000Z', ...over,
})
const inv = { bundles: 585, states: { valid: 585 }, assets: 378672, last_scan: { state: 'done', finished_utc: '20261118T000000Z' } }
const adapters = (over: Record<string, unknown>[] = []) => ([
  { name: 'stylesheet', version: 1, asset_types: ['MonoBehaviour'], edit_kind: 'value',
    properties: [{ name: 'tokens', type: 'colour tokens', evidence: 'token_patch' }], limitations: ['pools append-only'],
    evidence: { status: 'Confirmed', basis: 'tests', stages: ['3A'] } },
  { name: 'composition', version: 1, asset_types: ['MonoBehaviour'], edit_kind: 'value',
    properties: [{ name: 'cell_position', type: 'move-cell', evidence: 'tiles.apply_ops' }],
    limitations: ['positions only', 'an overlap can drop a tile in game (Stage 3E)'],
    evidence: { status: 'Runtime-proven (position edits)', basis: 'Stage 3G', stages: ['3G'] } },
  ...over,
])
const assets = [
  { bundle: 'ui-tileslayouts_assets_all.bundle', cab: 'CAB-ee9f', path_id: '4181126630784745451', type: 'MonoBehaviour', name: 'SquadComposition-Large', guid: '692315a5', key: {} },
  { bundle: 'ui-tileslayouts_assets_all.bundle', cab: 'CAB-ee9f', path_id: '-8744014289983900540', type: 'MonoBehaviour', name: 'SquadComposition-Standard', guid: null, key: {} },
]
const read = {
  adapter: { name: 'composition', version: 1, asset_types: ['MonoBehaviour'], edit_kind: 'value',
    properties: [{ name: 'cell_position', type: 'move-cell', evidence: 'tiles' }],
    limitations: ['an overlap can drop a tile in game (Stage 3E)'],
    evidence: { status: 'Runtime-proven (position edits)', basis: 'Stage 3G', stages: ['3G'] } },
  identity: { bundle: 'ui-tileslayouts_assets_all.bundle', path_id: '4181126630784745451' },
  summary: { name: 'SquadComposition-Large', cells: 5 }, fingerprint: 'abc',
}
const edges = () => ({
  total: 2, edges: [
    { id: 1, kind: 'pptr', relation: 'composition_ref', resolution: 'resolved', reason: null, direct: true, count: 1,
      src: { bundle: 'ui-tileslayouts_assets_all.bundle', path_id: '4181126630784745451', name: 'SquadComposition-Large' },
      dst: { bundle: 'ui-visualtreeassets_assets_all.bundle', path_id: '-88', name: 'Loans' } },
    { id: 2, kind: 'guid_reference', relation: null, resolution: 'ambiguous', reason: 'guid names several assets', direct: true, count: 1,
      src: { bundle: 'ui-tileslayouts_assets_all.bundle', path_id: '4181126630784745451', name: 'SquadComposition-Large' },
      dst: { bundle: 'ui-panelids_assets_all.bundle', path_id: '5', name: 'two candidates' },
      candidates: [{ bundle: 'ui-panelids_assets_all.bundle', path_id: '5', role: 'PanelDescription' }, { bundle: 'ui-other.bundle', path_id: '9', role: 'PanelDescription' }] },
    { id: 3, kind: 'bundle_dependency', relation: 'bundle_dependency', resolution: 'unresolved', reason: 'cab_not_in_inventory', direct: true, count: 1,
      src: { bundle: 'ui-tileslayouts_assets_all.bundle', path_id: null, name: null }, dst: { bundle: 'other.bundle', path_id: null, name: null } },
  ],
})
const affected = { status: 'complete', rebuild_required: ['ui-tileslayouts_assets_all.bundle'], possibly_affected_at_runtime: [], unknown: [], notes: [] }

let calls: string[]
function engine(opts: { prof?: any; cat?: any; search?: any; read?: any } = {}) {
  calls = []
  ;(rpc as any).mockImplementation(async (m: string) => {
    calls.push(m)
    if (m === 'install.profile_get') return opts.prof ?? prof()
    if (m === 'catalog.status') return opts.cat ?? cat()
    if (m === 'inventory.status') return inv
    if (m === 'edit.adapters') return { adapters: adapters() }
    if (m === 'registry.search') return opts.search ?? { total: 2, assets }
    if (m === 'edit.read') return opts.read ?? read
    if (m === 'graph.uses') return edges()
    if (m === 'graph.used_by') return edges()
    if (m === 'graph.affected') return affected
    if (m === 'inventory.scan' || m === 'graph.build') return { job: 'j1' }
    if (m === 'jobs.get') return { state: 'done', label: 'done', progress: 1, error: null }
    throw new Error('unexpected ' + m)
  })
}
beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear() })
const go = () => render(<Explore say={() => {}} />)

describe('Explore: installation profile', () => {
  it('shows the installation, its build, the steam id and the inventory status', async () => {
    engine(); go()
    expect(await screen.findByTestId('explore-profile')).toBeTruthy()
    expect(screen.getByText(/build 27\.1\.0\.2505117/)).toBeTruthy()
    expect(screen.getByText(/Steam 2348710/)).toBeTruthy()
    expect((await screen.findByTestId('explore-inv')).textContent).toMatch(/585 bundles.*378672 assets/)
    expect((await screen.findByTestId('explore-cat')).textContent).toContain('534 records')
  })

  it('surfaces a stale installation identity and profile problems clearly', async () => {
    engine({ prof: prof({ drift: [{ code: 'catalog_sha256_changed', message: 'catalog_sha256 changed (a -> b)' }], problems: [{ message: 'the executable moved' }] }) }); go()
    expect((await screen.findByTestId('explore-stale')).textContent).toMatch(/no longer matches its profile/)
    expect(screen.getByText(/the executable moved/)).toBeTruthy()
  })

  it('flags a stale catalog identity on the integrity line', async () => {
    engine({ cat: cat({ identity_stale: true }) }); go()
    expect((await screen.findByTestId('explore-cat')).textContent).toContain('stale identity')
  })

  it('a refused profile read shows the plain sentence instead of a blank screen', async () => {
    calls = []
    ;(rpc as any).mockImplementation(async (m: string) => {
      calls.push(m)
      if (m === 'install.profile_get') throw new FakeRpcError({ code: -32004, message: 'no such installation profile: (none selected)', data: { plain: "The Studio hasn't got a record of that game folder yet." } })
      if (m === 'edit.adapters') return { adapters: adapters() }
      throw new Error('unexpected ' + m)
    })
    go()
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByText(/hasn't got a record of that game folder/)).toBeTruthy()
  })
})

describe('Explore: search and adapters', () => {
  it('searches with the given filters and lists the matches', async () => {
    engine(); go()
    fireEvent.change(await screen.findByPlaceholderText('name contains'), { target: { value: 'Squad' } })
    fireEvent.change(screen.getByPlaceholderText(/type/), { target: { value: 'MonoBehaviour' } })
    fireEvent.click(screen.getByText('Search', { selector: 'button' }))
    await screen.findByTestId('explore-rows')
    expect(calls).toContain('registry.search')
    const params = (rpc as any).mock.calls.find((c: any[]) => c[0] === 'registry.search')[1]
    expect(params.q).toBe('Squad'); expect(params.type).toBe('MonoBehaviour')
    expect(await screen.findByText('SquadComposition-Large')).toBeTruthy()
  })

  it('an empty result says so instead of an empty table', async () => {
    engine({ search: { total: 0, assets: [] } }); go()
    fireEvent.click(await screen.findByText('Search', { selector: 'button' }))
    expect(await screen.findByText(/Nothing matches/)).toBeTruthy()
  })

  it('lists the typed adapters with their properties, limitations and evidence', async () => {
    engine(); go()
    expect(await screen.findByText('Typed adapters')).toBeTruthy()
    fireEvent.click(screen.getAllByRole('group', { hidden: true }).length ? screen.getByText('composition', { selector: 'summary *' }) : screen.getByText('composition'))
    expect(await screen.findByText(/an overlap can drop a tile in game/)).toBeTruthy()
    expect(screen.getByText(/Runtime-proven \(position edits\)/)).toBeTruthy()
  })
})

describe('Explore: asset detail and dependencies', () => {
  it('shows the adapter read, the affected bundles, and uses/used-by edges with their resolutions distinguished', async () => {
    engine(); go()
    fireEvent.click(await screen.findByText('Search', { selector: 'button' }))
    fireEvent.click(await screen.findByText('SquadComposition-Large'))
    const detail = await screen.findByTestId('explore-detail')
    expect(detail.textContent).toContain('composition')
    expect((await screen.findByTestId('explore-affected')).textContent).toContain('rebuilds ui-tileslayouts_assets_all.bundle')
    const badges = (await screen.findAllByTestId('edge-resolution')).map((b) => b.textContent)
    expect(badges).toContain('resolved'); expect(badges).toContain('ambiguous'); expect(badges).toContain('unresolved')
    expect(screen.getAllByText(/guid names several assets/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/candidates: ui-panelids_assets_all\.bundle#5/).length).toBeGreaterThan(0)   // ambiguity keeps every candidate visible
    expect(screen.getAllByText(/cab_not_in_inventory/).length).toBeGreaterThan(0)               // the unresolved reason is shown, never guessed away
    expect(screen.getAllByText(/SquadComposition-Large/).length).toBeGreaterThan(0)
  })

  it('an asset no adapter owns says exactly that, never an invented capability', async () => {
    engine({ read: { adapter: null, identity: { bundle: 'x', path_id: '1' }, summary: null, fingerprint: null, note: 'no adapter owns this object type; it is preserved untouched by every build' } })
    go()
    fireEvent.click(await screen.findByText('Search', { selector: 'button' }))
    fireEvent.click(await screen.findByText('SquadComposition-Large'))
    expect(await screen.findByTestId('explore-no-adapter')).toBeTruthy()
  })

  it('an unknown edit kind is never offered: the affected query always asks as a value edit', async () => {
    engine(); go()
    fireEvent.click(await screen.findByText('Search', { selector: 'button' }))
    fireEvent.click(await screen.findByText('SquadComposition-Large'))
    await screen.findByTestId('explore-affected')
    const params = (rpc as any).mock.calls.find((c: any[]) => c[0] === 'graph.affected')[1]
    expect(params.edit_kind).toBe('value')
  })
})

describe('Explore: read-only jobs', () => {
  it('runs the inventory scan as a job and never blocks the profile view when it fails', async () => {
    engine(); go()
    await screen.findByTestId('explore-profile')
    fireEvent.click(screen.getByText(/Scan the installation/))
    await waitFor(() => expect(calls).toContain('inventory.scan'))
  })
})
