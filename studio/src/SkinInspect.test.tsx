// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('./engine', () => ({
  rpc: vi.fn(),
  RpcError: class extends Error {},
}))
import { rpc } from './engine'
import SkinInspect from './SkinInspect'

const SAMPLE_REPORT = {
  skin_dir: 'C:/skins/sample-skin',
  stock_dir: 'C:/game/aa',
  source: { name: 'Sample-Skin', version: '1.0.2', label: 'Sample-Skin v1.0.2' },
  default_screen: 'PlayerReport',
  screen_meta: {
    PlayerReport: { count: 3, variants: ['Large · FMC · V8', 'Large · V8', 'Standard'] },
    SquadScreen: { count: 1, variants: [] },
    'Not tied to a screen': { count: 1, variants: [] },
  },
  totals: { bundles: 24, added: 305, removed: 3, changed: 1049, unchanged: 25612 },
  by_category: {
    composition: { added: 4, removed: 3, changed: 35 },
    style: { added: 0, removed: 0, changed: 7 },
    uxml: { added: 0, removed: 0, changed: 885 },
  },
  by_screen: {
    AboutRulesCard: {
      composition: [],
    },
    PlayerReport: {
      composition: [
        { bundle: 'ui-tileslayouts_assets_all.bundle', kind: 'added', type: 'MonoBehaviour', name: 'PlayerReportOverviewComposition-Large-V8', field_count: 0, variant: 'Large · V8', source_label: 'Sample-Skin v1.0.2', via: 'composition -> tile slot -> panel' },
        { bundle: 'ui-tileslayouts_assets_all.bundle', kind: 'changed', type: 'MonoBehaviour', name: 'PlayerReportOverviewComposition-Standard', field_count: 2, variant: 'Standard', source_label: 'Sample-Skin v1.0.2', via: 'composition -> tile slot -> panel' },
      ],
      style: [
        { bundle: 'ui-styles_assets_default.bundle', kind: 'changed', type: 'StyleClassRules', name: 'AlwaysAppliedStyleSheet (.sample-attr)', field_count: 1, variant: 'Large · FMC · V8', source_label: 'Sample-Skin v1.0.2', via: 'class -> layout -> panel' },
      ],
    },
    SquadScreen: {
      uxml: [
        { bundle: 'ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle', kind: 'changed', type: 'VisualTreeAsset', name: 'VeryLongSquadTileNameThatShouldShowInTooltipWithoutTruncation', field_count: 4, source_label: 'Sample-Skin v1.0.2', via: 'VTA -> layout/composition graph -> panel' },
      ],
    },
    'Not tied to a screen': {
      style: [
        { bundle: 'ui-styles_assets_default.bundle', kind: 'changed', type: 'StyleSheet', name: 'FMColours', field_count: 10, source_label: 'Sample-Skin v1.0.2', unmapped_reason: 'Global stylesheet across all screens' },
      ],
    },
  },
  compositions: [
    { name: 'PlayerReportOverviewComposition-Large-V8', bundle: 'ui-tileslayouts_assets_all.bundle', kind: 'added', screen: 'PlayerReport' },
  ],
  bundles: [],
}

const SAMPLE_PREVIEW = {
  composition: 'PlayerReportOverviewComposition-Large-V8',
  source: 'skin_inspect',
  engine: 'rea',
  confidence: { label: 'measured' },
  design: { cols: 20, rows: 10 },
  grid: { cols: 30, rows: 16 },
  cells: [
    { space: 'main', order: 0, element_id: 'RR_Mid1', x: 0, y: 0, w: 12, h: 6, rect: [27.6, 97.9, 968.0, 476.0] },
  ],
  slots: [],
  problems: [],
}

beforeEach(() => {
  ;(rpc as any).mockImplementation(async (m: string) => {
    if (m === 'skin.inspect') return SAMPLE_REPORT
    if (m === 'skin.preview_composition') return SAMPLE_PREVIEW
    return null
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SkinInspect (SKIN-RR1/RR2, read-only)', () => {
  it('opens on screen with most changes, groups variants, shows tooltips and Source note, filters cleanly, and exposes no write path', async () => {
    const said: string[] = []
    render(<SkinInspect say={(s) => said.push(s)} />)
    fireEvent.change(screen.getByTestId('skin-inspect-path'), { target: { value: 'C:/skins/sample-skin' } })
    fireEvent.click(screen.getByTestId('skin-inspect-run'))

    expect(await screen.findByTestId('skin-inspect-summary')).toBeTruthy()
    expect(screen.getByTestId('skin-inspect-summary').textContent).toContain('24 bundles')
    expect(screen.getByTestId('skin-inspect-source').textContent).toContain('Sample-Skin v1.0.2')

    // Never opens on 0-change AboutRulesCard; opens on PlayerReport (highest non-untied count)
    const rows = screen.getAllByTestId('skin-screen-row')
    expect(rows.length).toBe(3) // AboutRulesCard has count 0 and is omitted
    expect(rows[0].getAttribute('data-screen')).toBe('PlayerReport')
    expect(rows[0].className).toContain('sel')
    expect(rows[2].getAttribute('data-screen')).toBe('Not tied to a screen')

    // Every item shows Source note and full-name tooltip
    const sources = screen.getAllByTestId('skin-item-source')
    expect(sources.length).toBeGreaterThan(0)
    expect(sources[0].textContent).toContain('Sample-Skin v1.0.2')

    // Variant filter groups variants under PlayerReport
    const vbar = screen.getByTestId('skin-variant-filter')
    expect(vbar.textContent).toContain('Standard')
    fireEvent.click(screen.getByRole('button', { name: 'Standard' }))
    expect(screen.getAllByTestId('skin-item-source').length).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: 'All variants' }))

    // Check tooltip on SquadScreen row / item
    fireEvent.click(rows[1])
    expect(screen.getByTitle('VeryLongSquadTileNameThatShouldShowInTooltipWithoutTruncation')).toBeTruthy()

    // Filter to composition category only (re-selects PlayerReport since SquadScreen has 0 compositions)
    fireEvent.click(screen.getByTestId('skin-cat-composition'))
    expect(screen.getAllByTestId('skin-screen-row').length).toBe(1)

    // Preview composition with rea engine
    fireEvent.click(screen.getAllByTestId('skin-inspect-preview-btn')[0])
    const prev = await screen.findByTestId('skin-inspect-preview')
    expect(prev.textContent).toContain('PlayerReportOverviewComposition-Large-V8')
    expect(prev.textContent).toContain('engine: rea')
    expect(screen.getByTestId('skin-preview-tile').textContent).toContain('RR_Mid1')

    // Strictly read-only: no Apply, Install, Save, or Write button anywhere
    const buttons = screen.getAllByRole('button').map((b) => b.textContent || '')
    expect(buttons.some((t) => /\b(apply|install|save|write|rollback)\b/i.test(t))).toBe(false)
    await waitFor(() => expect(said.some((s) => s.includes('inspected skin'))).toBe(true))
  })
})
