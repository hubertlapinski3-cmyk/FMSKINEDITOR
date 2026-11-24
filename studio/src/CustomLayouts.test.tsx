// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const api = vi.hoisted(() => ({
  list: vi.fn(), preflight: vi.fn(), apply: vi.fn(), rollback: vi.fn(), recovery_scan: vi.fn(),
}))
vi.mock('./engine', () => ({
  RpcError: class FakeRpcError extends Error { code = -32000; data: any; constructor(e: { message: string; data?: any }) { super(e.message); this.data = e.data } },
  isApplyRefusal: (r: any) => !!r && typeof r.refused === 'string',
  customlayout: api,
}))
import CustomLayouts, { OWNER_FILES, RESET_WARNING } from './CustomLayouts'

const OWNER_A = 'a2c95aa7135088669f392df4b2b596df6861545c2bdf95dbc4bef960cd3bdf51'
const OWNER_B = '8372412d5a2741e2dcb412cf80058d40b5eeab73ec452261ff0d93a4f8440674'
const folder = (files: any[] = [
  { composition: 'PlayerReportOverviewComposition-Large', size: 6400, mtime: '2026-11-21T21:45:20Z', sha256: OWNER_A },
  { composition: 'CompetitionStagesBottomTileComposition', size: 6400, mtime: '2026-11-21T21:45:20Z', sha256: OWNER_B },
]) => ({ folder: 'C:\\game\\CustomGridCompositions', folder_exists: true, badge: 'customised in the game', warning: 'a bundle layout edit will not show', files })
const pf = (over: Record<string, any> = {}) => ({
  ready: true, blocked: [], warnings: [], required_confirmations: [], confirmation_reasons: {},
  file_operations: [{ name: 'SquadComposition-Large', source: 'C:/build/custom-layouts/SquadComposition-Large',
    target_path: 'C:/game/CustomGridCompositions/SquadComposition-Large', size: 64, after_sha256: 'f'.repeat(64), state: 'new' }],
  folder: 'C:\\game\\CustomGridCompositions', folder_exists: true, ...over,
})
const tx = (over: Record<string, any> = {}) => ({
  tx_id: '20261122T000000Z-ab12cd34', state: 'completed', created_utc: '2026-11-22T00:00:00Z', completed_utc: '2026-11-22T00:00:01Z',
  package_dir: 'C:/builds/demo/1', folder: 'C:\\game\\CustomGridCompositions', folder_existed: true, confirmations: [],
  ops: [{ name: 'SquadComposition-Large', after_sha256: 'f'.repeat(64), before_sha256: 'e'.repeat(64), state: 'installed_by_this_app' }],
  backup_sha256: { 'SquadComposition-Large': 'e'.repeat(64) }, ...over,
})
const rollbackTx = (over: Record<string, any> = {}) => tx({
  state: 'rolled_back',
  ops: [{ name: 'SquadComposition-Large', after_sha256: 'f'.repeat(64), state: 'new' }],
  rollback: { utc: '2026-11-22T00:05:00Z', conflicts: [], exact: true, folder_now: {} }, ...over,
})
const unfinished = (over: Record<string, any> = {}) => ({
  tx_id: '20261122T000001Z-unfinished', state: 'writing', error: 'stopped mid-write',
  files: [{ name: 'SquadComposition-Large', status: 'written' }], safe_action: 'rollback', ...over,
})

function engine(opts: { folder?: any; preflight?: any; recovery?: any[]; apply?: any; rollback?: any } = {}) {
  api.list.mockResolvedValue(opts.folder ?? folder())
  api.preflight.mockResolvedValue(opts.preflight ?? pf())
  api.recovery_scan.mockResolvedValue(opts.recovery ?? [])
  api.apply.mockResolvedValue(opts.apply ?? tx())
  api.rollback.mockResolvedValue(opts.rollback ?? rollbackTx())
}
beforeEach(() => { engine(); vi.spyOn(window, 'confirm').mockReturnValue(true) })
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks() })
const go = () => render(<CustomLayouts project="demo" say={() => {}} />)

describe('UI1 read-only custom folder view', () => {
  it('lists every file with sha256, size and modified date and marks the two owner files', async () => {
    expect(Object.keys(OWNER_FILES)).toEqual(['a2c95aa7', '8372412d'])
    go()
    expect((await screen.findByTestId('cl-reset-warning')).textContent).toBe(RESET_WARNING)
    const table = await screen.findByTestId('cl-folder')
    expect(table.textContent).toContain(OWNER_A)
    expect(table.textContent).toContain('6.3 KB')
    expect(table.textContent).toContain('2026-11-21T21:45:20Z')
    const rows = screen.getAllByTestId('cl-folder-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].getAttribute('data-composition')).toBe('PlayerReportOverviewComposition-Large')
    expect(rows[0].textContent).toContain('YOURS: PlayerReportOverviewComposition-Large')
    expect(rows[1].textContent).toContain('YOURS: CompetitionStagesBottomTileComposition')
    expect(screen.queryByTestId('cl-apply')).toBeTruthy()
    expect(screen.queryByTestId('cl-rollback')).toBeTruthy()
  })

  it('marks files Studio wrote using the preflight journal verdict', async () => {
    engine({
      folder: folder([{ composition: 'SquadComposition-Large', size: 64, mtime: '2026-11-22T00:00:01Z', sha256: 'c'.repeat(64) }]),
      preflight: pf({ file_operations: [{ name: 'SquadComposition-Large', target_path: 'x', after_sha256: 'c'.repeat(64), state: 'installed_by_this_app' }] }),
    })
    go()
    await screen.findByTestId('cl-folder')
    const mark = screen.getByTestId('cl-folder-mark')
    expect(mark.textContent).toContain('STUDIO WROTE THIS')
  })
})

describe('UI1 Apply preflight and explicit replacement confirmation', () => {
  const replacing = () => pf({
    required_confirmations: ['replace:Mine'],
    confirmation_reasons: { 'replace:Mine': 'the folder already holds Mine: this file is used by the game instead of the bundle' },
    file_operations: [{ name: 'Mine', source: 'C:/build/custom-layouts/Mine', target_path: 'C:/game/CustomGridCompositions/Mine',
      size: 64, after_sha256: 'b'.repeat(64), before_sha256: 'a'.repeat(64), state: 'replaces_user_file' }],
  })

  it('shows the target, that it replaces an existing file, and highlights the user file; Apply waits for confirmation', async () => {
    engine({ preflight: replacing() }); go()
    const view = await screen.findByTestId('cl-preflight-view')
    expect(view.textContent).toContain('C:/game/CustomGridCompositions/Mine')
    expect(view.textContent).toContain('REPLACES YOUR FILE')
    expect(view.textContent).toContain('replaces existing file')
    expect(view.textContent).toContain('used by the game instead of the bundle')
    const btn = screen.getByTestId('cl-apply') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
    await waitFor(() => expect(screen.getByTestId('cl-preflight-file').getAttribute('data-state')).toBe('replaces_user_file'))
    fireEvent.click(screen.getByTestId('cl-preflight-confirm').querySelector('input')!)
    await waitFor(() => expect((screen.getByTestId('cl-apply') as HTMLButtonElement).disabled).toBe(false))
  })

  it('never applies when the replacement dialog is declined, and sends the confirmation when agreed', async () => {
    engine({ preflight: replacing() }); go()
    fireEvent.click(await screen.findByTestId('cl-preflight-confirm').then((n) => n.querySelector('input')!))
    await waitFor(() => expect((screen.getByTestId('cl-apply') as HTMLButtonElement).disabled).toBe(false))
    vi.mocked(window.confirm).mockReturnValue(false)
    fireEvent.click(screen.getByTestId('cl-apply'))
    await waitFor(() => expect(api.apply).not.toHaveBeenCalled())
    vi.mocked(window.confirm).mockReturnValue(true)
    fireEvent.click(screen.getByTestId('cl-apply'))
    await waitFor(() => expect(api.apply).toHaveBeenCalledWith('demo', ['replace:Mine']))
    expect((await screen.findByTestId('cl-backup')).textContent).toContain('20261122T000000Z-ab12cd34/backup')
    expect((await screen.findByTestId('cl-journal')).textContent).toContain('20261122T000000Z-ab12cd34')
    expect(screen.getByTestId('cl-journal-op').textContent).toContain('eeeeeeeeeeee')
  })

  it('shows a refusal verbatim instead of pretending the apply happened', async () => {
    engine({ apply: { refused: 'the game is running; close it first', required_confirmations: [] } }); go()
    fireEvent.click(await screen.findByTestId('cl-apply'))
    expect((await screen.findByTestId('cl-refusal')).textContent).toContain('the game is running; close it first')
  })
})

describe('UI1 Rollback verification', () => {
  it('restores byte-exact, verifies sha256 and confirms a created file is gone', async () => {
    go()
    fireEvent.change(await screen.findByTestId('cl-rollback-tx'), { target: { value: 'tx-1' } })
    fireEvent.click(screen.getByTestId('cl-rollback'))
    await waitFor(() => expect(api.rollback).toHaveBeenCalledWith('tx-1'))
    const verify = await screen.findByTestId('cl-rollback-verify')
    expect(verify.textContent).toContain('exact match to the backup')
    expect(screen.getByTestId('cl-rollback-absent').textContent).toContain('confirmed gone')
  })
})

describe('UI1 recovery dialog', () => {
  it('shows an unfinished transaction with Complete and Undo, and Undo rolls it back', async () => {
    engine({ recovery: [unfinished()] }); go()
    const dialog = await screen.findByTestId('cl-recovery')
    expect(dialog.getAttribute('role')).toBe('dialog')
    expect(dialog.textContent).toContain('writing')
    expect(dialog.textContent).toContain('stopped mid-write')
    expect(dialog.textContent).toContain('SquadComposition-Large: written')
    const undo = screen.getByTestId('cl-recover-undo')
    const complete = screen.getByTestId('cl-recover-complete')
    expect(undo.textContent).toBe('Undo')
    expect(complete.textContent).toBe('Complete')
    fireEvent.click(undo)
    await waitFor(() => expect(api.rollback).toHaveBeenCalledWith('20261122T000001Z-unfinished'))
  })

  it('Complete applies the transaction through the apply RPC', async () => {
    engine({ recovery: [unfinished()] }); go()
    fireEvent.click(await screen.findByTestId('cl-recover-complete'))
    await waitFor(() => expect(api.apply).toHaveBeenCalled())
    expect(api.apply.mock.calls[0][0]).toBe('demo')
  })
})
