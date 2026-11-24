// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('./engine', () => ({
  rpc: vi.fn(),
  RpcError: class extends Error {},
}))
import { rpc } from './engine'
import InjectedStyles from './InjectedStyles'

const INIT_STATE = {
  project: 'demo-skin',
  sheet: 'AlwaysAppliedStyleSheet',
  file: 'styles/AlwaysAppliedStyleSheet.uss',
  uss_text: ':root {\n    --my-accent: #3B8FE1;\n}\n.my-card {\n    background-color: var(--my-accent);\n}\n',
  classes: [{ name: 'my-card', rules: 1, selectors: ['.my-card'], source: null }],
  variables: [{ name: '--my-accent', value: '#3B8FE1', scope: 'AlwaysAppliedStyleSheet', source: null }],
  rules: [],
}

const AFTER_IMPORT_STATE = {
  ...INIT_STATE,
  uss_text: INIT_STATE.uss_text + '/* meta: {"source": {"skin": "Sample-Skin", "version": "1.0.2"}} */\n.sample-pill {\n    border-radius: 6px;\n}\n',
  classes: [
    ...INIT_STATE.classes,
    { name: 'sample-pill', rules: 1, selectors: ['.sample-pill'], source: { skin: 'Sample-Skin', version: '1.0.2' } },
  ],
  variables: [
    ...INIT_STATE.variables,
    { name: '--sample-surface', value: '#123456', scope: 'AlwaysAppliedStyleSheet', source: { skin: 'Sample-Skin', version: '1.0.2' } },
  ],
}

beforeEach(() => {
  ;(rpc as any).mockImplementation(async (m: string, p: any) => {
    if (m === 'styles.injected_get') return INIT_STATE
    if (m === 'uss.diagnostics') return { diagnostics: [{ line: 4, col: 1, end_col: 8, severity: 'info', code: 'class-unused', message: 'class .my-card not in game sheets' }] }
    if (m === 'layouts.class_usage') return { class: p.class, layouts: [{ bundle: 'ui-vta.bundle', name: 'SquadTile', path_id: '10', elements: 12, uses: 2 }], rules: [] }
    if (m === 'render.layout') return {
      layout: p.name || 'SquadTile', notice: 'approx', tree: [{ type: 'VisualElement', name: 'Root', classes: ['my-card'], runtime_classes: [], style: {}, text: null, flag: null, matched: [{ sheet: 'AlwaysAppliedStyleSheet', rule: 1, selector: '.my-card', specificity: 11, origin: { file: 'styles/AlwaysAppliedStyleSheet.uss', selector: '.my-card' } }], computed: {}, children: [] }],
      includes: [], summary: { elements: 5, properties: 2, by_status: {}, unresolved_variables: {} }, sheet_order: [], gaps: [], timing_ms: { total: 1 },
      origins: { rules: [{ file: 'styles/AlwaysAppliedStyleSheet.uss', line: 4, end: 6, selector: '.my-card', sheet: 'AlwaysAppliedStyleSheet', ids: [] }], tokens: {} },
    }
    if (m === 'styles.injected_save') return { diagnostics: [], problems: [], injected: INIT_STATE }
    if (m === 'skin.style_definitions') return {
      skin_dir: 'C:/skins/sample-skin', sheet: 'AlwaysAppliedStyleSheet', source: { name: 'Sample-Skin', version: '1.0.2', label: 'Sample-Skin v1.0.2' },
      personal_use_notice: 'Personal use only', variables_total: 1, rules_total: 1,
      variables: [{ name: '--sample-surface', value: '#123456', is_new: true, uss_text: ':root { --sample-surface: #123456; }' }],
      rules: [{ selector: '.sample-pill', classes: ['sample-pill'], props: { 'border-radius': '6px' }, is_new: true, uss_text: '.sample-pill {\n border-radius: 6px;\n}' }],
    }
    if (m === 'styles.import_from_skin') return {
      source: { name: 'Sample-Skin', version: '1.0.2', label: 'Sample-Skin v1.0.2' },
      notice: 'Third-party skin rules and variables are imported for personal use and study only.',
      injected: AFTER_IMPORT_STATE,
    }
    return null
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InjectedStyles (SKIN-RR2 Part C)', () => {
  it('lists classes and variables, checks USS diagnostics, shows reach & cascade preview, exports, and imports tagged skin rules', async () => {
    const onNative = vi.fn()
    const onBundles = vi.fn()
    render(<InjectedStyles project="demo-skin" say={() => {}} onExportNative={onNative} onBuildBundles={onBundles} />)

    expect(await screen.findByTestId('injected-classes-list')).toBeTruthy()
    expect(screen.getByTestId('injected-classes-list').textContent).toContain('.my-card')
    expect(screen.getByTestId('injected-vars-list').textContent).toContain('--my-accent')

    await waitFor(() => expect(screen.getByTestId('injected-diagnostics').textContent).toContain('class-unused'))
    await waitFor(() => expect(screen.getByTestId('injected-reach').textContent).toContain('SquadTile'))

    // Cascade preview via render.layout
    fireEvent.click(screen.getByTestId('injected-preview-btn'))
    expect((await screen.findByTestId('injected-cascade-preview')).textContent).toContain('AlwaysAppliedStyleSheet')

    // Export hooks
    fireEvent.click(screen.getByTestId('injected-export-native'))
    expect(onNative).toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('injected-build-bundles'))
    expect(onBundles).toHaveBeenCalled()

    // Import from inspected skin with personal-use reminder and Source tag
    fireEvent.click(screen.getByTestId('injected-open-import'))
    expect(screen.getByTestId('injected-personal-use-notice').textContent).toContain('author')
    fireEvent.change(screen.getByTestId('injected-skin-path'), { target: { value: 'C:/skins/sample-skin' } })
    fireEvent.click(screen.getByTestId('injected-skin-scan'))
    const impBtn = await screen.findByTestId('import-class-sample-pill')
    fireEvent.click(impBtn)
    await waitFor(() => expect(screen.getByTestId('injected-import-toast').textContent).toContain('personal use'))
    expect(screen.getAllByTestId('injected-source-badge').some((el) => el.textContent?.includes('Sample-Skin v1.0.2'))).toBe(true)
  })
})
