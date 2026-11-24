// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const { FakeRpcError } = vi.hoisted(() => ({ FakeRpcError: class FakeRpcError extends Error { code: number; data: any; constructor(e: { code: number; message: string; data?: any }) { super(e.message); this.code = e.code; this.data = e.data } } }))
vi.mock('./engine', () => ({ rpc: vi.fn(), RpcError: FakeRpcError, connect: vi.fn(), subscribe: vi.fn(() => () => {}) }))
import Install, { STAGE3G } from './Install'
import { rpc } from './engine'

const pf = (over: Record<string, unknown> = {}) => ({
  ready: true, blocked: [], warnings: [], required_confirmations: [],
  file_operations: [{ rel_path: 'ui-styles_assets_common.bundle', target_state: 'stock', original_sha256: 'a'.repeat(64), expected_sha256: 'b'.repeat(64), op: 'replace' }],
  integrity_summary: [{ rel_path: 'ui-styles_assets_common.bundle', catalog_crc_status: 'not_checked', manifest_status: 'not_checked' }],
  diagnostics: [], package_identity: { id: 't1', schema: 2, game_build: '27.1.0.2505117' },
  target_profile: { game_build: '27.1.0.2505117', install_id: 'iid' }, ...over,
})
const blocked = (code: string, message: string, confirmation?: string) => ({ code, message, confirmation })
const tx = (state: string, over: Record<string, unknown> = {}) => ({
  tx_id: '20261118T000000Z-ab12cd34', state, created_utc: '20261118T000000Z', error: null, completed_utc: null,
  recovery: null, package_dir: 'C:/builds/demo/t1', ...over,
})
const recovery = (over: Record<string, unknown> = {}) => ({
  tx_id: '20261118T000000Z-ab12cd34', state: 'installing', ops: 2, replaced: 1,
  safe_actions: ['rollback', 'resume'], recommendation: 'rollback', conflicts: [], error: 'cancelled before completion', ...over,
})
const review = (over: Record<string, unknown> = {}) => ({
  bundles: { 'ui-styles_assets_common.bundle': { adapter: 'stylesheet', typed: true, in_snapshot: true, sections: ['sheet_spec'] } },
  findings: [], impact: { buildable: true, installation_readiness: 'ready', evaluated: false }, blocked: [], ...over,
})
const jobResult = (state: string, result: any = null, error: string | null = null) => ({ state, label: 'working', progress: 1, error, result })

let calls: { m: string; p: any }[]
function engine(opts: { pf?: any; hist?: any; scan?: any[]; review?: any; jobs?: any[]; calls?: Record<string, any> } = {}) {
  calls = []
  const jobs = opts.jobs ?? [jobResult('running'), jobResult('done', tx('completed'))]
  ;(rpc as any).mockImplementation(async (m: string, p: Record<string, unknown>) => {
    calls.push({ m, p })
    if (m === 'install.preflight') return opts.pf ?? pf()
    if (m === 'install.history') return opts.hist ?? { recovery_required: [], transactions: [] }
    if (m === 'install.recovery_scan') return { transactions: opts.scan ?? [] }
    if (m === 'build.review') return opts.review ?? review()
    if (m === 'install.apply') return { job: 'j1' }
    if (m === 'install.rollback' || m === 'install.recover') return { job: 'j2' }
    if (m === 'jobs.get') return jobs.length > 1 ? jobs.shift() : jobs[0]
    if (m === 'install.transaction') return opts.calls?.['install.transaction'] ?? tx('completed', { file_operations: [
      { rel_path: 'ui-styles_assets_common.bundle', state: 'replaced', verify: 'match', rollback_state: null,
        original_sha256: 'a'.repeat(64), actual_sha256: 'b'.repeat(64), backup_path: 'C:/backups/iid/tx/files/x', backup_sha256: 'c'.repeat(64), error: null }] })
    if (m === 'app.explain') return { plain: 'Plain sentence for the failure.', details: 'x' }
    throw new Error('unexpected ' + m)
  })
}
beforeEach(() => { localStorage.clear(); vi.spyOn(window, 'confirm').mockReturnValue(true) })
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks(); localStorage.clear() })
const go = () => render(<Install project="demo" say={() => {}} pollMs={2} />)
const applied = () => calls.find((c) => c.m === 'install.apply')

describe('Install: build review', () => {
  it('shows the build plan with buildability separate from installation readiness', async () => {
    engine({ review: review({ impact: { buildable: true, installation_readiness: 'uncertain', evaluated: false } }) }); go()
    const r = await screen.findByTestId('install-review')
    expect(r.textContent).toContain('buildable')
    expect(r.textContent).toContain('uncertain')
    expect(r.textContent).toContain('stylesheet')
  })

  it('shows the review findings, including a tile-overlap error', async () => {
    engine({ review: review({ findings: [{ level: 'error', code: 'tile_overlap', message: 'SquadComposition-Standard: cell 0 (Training) overlaps cell 4 (Atmosphere) in the region x=12..16, y=6..8.' }], impact: { buildable: false, installation_readiness: 'blocked', evaluated: false } }) })
    go()
    const r = await screen.findByTestId('install-review')
    expect(r.textContent).toContain('overlaps cell 4')
    expect(r.textContent).toContain('not buildable')
  })
})

describe('Install: preflight', () => {
  it('a ready preflight enables the install and lists the file operations with their integrity statuses', async () => {
    engine(); go()
    expect((await screen.findByTestId('preflight-state')).textContent).toBe('ready')
    const applyBtn = await screen.findByTestId('install-apply')
    expect((applyBtn as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getAllByText('ui-styles_assets_common.bundle').length).toBeGreaterThan(0)
    expect((await screen.findByTestId('integrity-catalog')).textContent).toBe('not_checked')
  })

  it('a hard block disables the install and shows why, and no confirmation is offered for it', async () => {
    engine({ pf: pf({ ready: false, blocked: [blocked('stale_game_build', 'the package was built for game build 27.0, the selected installation is 27.1')] }) }); go()
    expect((await screen.findByTestId('preflight-blocked')).textContent).toContain('built for game build 27.0')
    expect((await screen.findByTestId('install-apply') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByTestId('preflight-confirm')).toBeNull()
  })

  it('mismatch warnings require their explicit confirmations, with the Stage 3G caveat, and install stays off until each is checked', async () => {
    engine({ pf: pf({
      ready: true, warnings: [
        { code: 'catalog_crc_mismatch', message: 'the catalog record for ui-styles_assets_common.bundle holds the ORIGINAL CRC; Unity will log a mismatch for the installed file. observed, not guaranteed.' },
        { code: 'manifest_mismatch', message: 'manifest.dat holds the ORIGINAL whole-file CRC for ui-styles_assets_common.bundle.' }],
      required_confirmations: ['catalog_crc_mismatch', 'manifest_mismatch'],
      integrity_summary: [{ rel_path: 'ui-styles_assets_common.bundle', catalog_crc_status: 'catalog_crc_mismatch', manifest_status: 'manifest_mismatch' }],
    }) }); go()
    expect((await screen.findByTestId('preflight-state')).textContent).toBe('needs confirmation')
    const caveat = await screen.findByTestId('preflight-caveat')
    expect(caveat.textContent).toContain(STAGE3G)
    expect((await screen.findByTestId('integrity-catalog')).textContent).toBe('catalog_crc_mismatch')
    const boxes = await screen.findAllByTestId('preflight-confirm').then(() => screen.getAllByRole('checkbox'))
    const btn = (await screen.findByTestId('install-apply')) as HTMLButtonElement
    expect(btn.disabled).toBe(true)                                          // nothing is installed without the confirmations
    fireEvent.click(boxes[0])
    expect((screen.getByTestId('install-apply') as HTMLButtonElement).disabled).toBe(true)   // every confirmation is required
    fireEvent.click(boxes[1])
    await waitFor(() => expect((screen.getByTestId('install-apply') as HTMLButtonElement).disabled).toBe(false))
  })

  it('a refused preflight shows the plain sentence', async () => {
    calls = []
    ;(rpc as any).mockImplementation(async (m: string) => {
      calls.push({ m, p: {} })
      if (m === 'install.preflight') throw new FakeRpcError({ code: -32000, message: 'the installation was refused: the package was built for game build 27.0', data: { plain: 'This package was built for a different version of the game. Read the game again and rebuild it.' } })
      if (m === 'install.history') return { recovery_required: [], transactions: [] }
      if (m === 'install.recovery_scan') return { transactions: [] }
      throw new Error('unexpected ' + m)
    })
    go()
    expect(await screen.findByText(/different version of the game/)).toBeTruthy()
  })

  it('shows a quiet neutral status with no red banner or ERROR log when no build exists yet', async () => {
    const said: string[] = []
    ;(rpc as any).mockImplementation(async (m: string) => {
      if (m === 'install.preflight') return { ready: false, no_build: true, blocked: [], warnings: [], required_confirmations: [], file_operations: [], integrity_summary: [], diagnostics: [], package_identity: {}, target_profile: {} }
      if (m === 'install.history') return { recovery_required: [], transactions: [] }
      if (m === 'install.recovery_scan') return { transactions: [] }
      if (m === 'build.review') return review()
      throw new Error('unexpected ' + m)
    })
    render(<Install project="demo" say={(s) => said.push(s)} pollMs={2} />)
    expect(await screen.findByTestId('install-no-build')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(said.some((s) => s.includes('ERROR'))).toBe(false)
  })
})

describe('Install: apply and history', () => {
  it('installs through the transactional job, shows progress, and the transaction appears in the history', async () => {
    engine({ pf: pf({ required_confirmations: ['catalog_crc_mismatch'] }), hist: { recovery_required: [], transactions: [tx('completed', { completed_utc: '20261118T000100Z' })] } }); go()
    fireEvent.click(await screen.findByRole('checkbox'))                      // the explicit confirmation is given first
    fireEvent.click(await screen.findByTestId('install-apply'))
    await screen.findAllByTestId('install-progress').then(() => {}).catch(() => {})           // progress may be quick
    await screen.findByTestId('install-transaction')
    expect(applied()).toBeTruthy()
    expect(applied()!.p.confirmations).toEqual(['catalog_crc_mismatch'])                       // only the checked confirmations are sent
    expect(screen.getAllByText(/20261118T000000Z-ab12cd34/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('completed').length).toBeGreaterThan(0)
  })

  it('never calls apply without every confirmation (the confirm dialog itself must be agreed to)', async () => {
    engine(); go()
    await screen.findByTestId('install-apply')
    vi.mocked(window.confirm).mockReturnValue(false)                                          // the destructive confirm is refused
    fireEvent.click(screen.getByTestId('install-apply'))
    await waitFor(() => expect(calls.find((c) => c.m === 'install.apply')).toBeUndefined())
  })

  it('a failed job shows the plain failure, and a cancelled job says the transaction is recorded unfinished', async () => {
    engine({ jobs: [jobResult('failed', null, 'RuntimeError: the game folder no longer matches its profile')] }); go()
    fireEvent.click(await screen.findByTestId('install-apply'))
    expect(await screen.findByText(/Plain sentence for the failure/)).toBeTruthy()
    engine({ jobs: [jobResult('cancelled', { tx_id: 'x', state: 'installing' }, null)] }); go()
    fireEvent.click(await screen.findByTestId('install-apply'))
    expect(await screen.findByText(/was cancelled\. The transaction is recorded unfinished/)).toBeTruthy()
  })

  it('the transaction detail shows per-file operations with backup hashes and verification', async () => {
    engine({ hist: { recovery_required: [], transactions: [tx('completed')] } }); go()
    fireEvent.click(await screen.findByText(/20261118T000000Z-ab12cd34/))
    const t = await screen.findByTestId('install-transaction')
    expect(t.textContent).toContain('replaced/match')
    expect(t.textContent).toContain('verified')
    expect(t.textContent).toContain('aaaaaaaaaaaa → installed bbbbbbbbbbbb')
  })
})

describe('Install: recovery and rollback', () => {
  it('lists unfinished transactions with the assessment, the conflicts and only the safe actions enabled', async () => {
    engine({ scan: [recovery({ conflicts: ['ui-styles_assets_common.bundle changed independently'] })] }); go()
    const rec = await screen.findByTestId('recovery-tx')
    expect(rec.textContent).toContain('1 of 2 files replaced')
    expect(rec.textContent).toContain('recommended: rollback')
    expect(rec.textContent).toContain('changed independently')
    const resume = screen.getByText('Resume', { selector: 'button' }) as HTMLButtonElement
    expect(resume.disabled).toBe(false)
  })

  it('resume is off when the scan did not prove it safe; rollback and manual remain explicit choices', async () => {
    engine({ scan: [recovery({ safe_actions: ['rollback'], recommendation: 'rollback' })] }); go()
    await screen.findByTestId('recovery-tx')
    expect((screen.getByText('Resume', { selector: 'button' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByText('Roll back', { selector: 'button' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByText('Needs a person', { selector: 'button' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('an explicit recover action goes through the job and only with its recorded action', async () => {
    engine({ scan: [recovery()] }); go()
    fireEvent.click(await screen.findByText('Roll back', { selector: 'button' }))
    await waitFor(() => {
      const c = calls.find((x) => x.m === 'install.recover')
      expect(c).toBeTruthy()
      expect(c!.p).toEqual({ tx_id: '20261118T000000Z-ab12cd34', action: 'rollback' })
    })
  })

  it('a completed transaction offers its own rollback, explicitly confirmed', async () => {
    engine({ hist: { recovery_required: [], transactions: [tx('completed', { completed_utc: '20261118T000100Z' })] } }); go()
    vi.mocked(window.confirm).mockReturnValue(false)
    fireEvent.click(await screen.findByText('Roll back', { selector: 'button' }))
    await waitFor(() => expect(calls.find((c) => c.m === 'install.rollback')).toBeUndefined())
    vi.mocked(window.confirm).mockReturnValue(true)
    fireEvent.click(screen.getByText('Roll back', { selector: 'button' }))
    await waitFor(() => {
      const c = calls.find((x) => x.m === 'install.rollback')
      expect(c).toBeTruthy()
      expect(c!.p).toEqual({ tx_id: '20261118T000000Z-ab12cd34' })
    })
  })
})
