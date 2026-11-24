// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import BreakpointSelector, {
  BREAKPOINT_TABLE, breakpointForResolution, breakpointName, compositionForBreakpoint, confidenceLabel,
} from './Breakpoint'

describe('UI1 breakpoint table and comparator (REA-WIN-2 §W3)', () => {
  it('carries the GridLayoutSettings asset records in serialized order', () => {
    expect(BREAKPOINT_TABLE.map((r) => r.breakpoint)).toEqual([1, 2, 3, 0, 5])
    expect(BREAKPOINT_TABLE[0].fullscreenGrid).toEqual([12, 8])
    expect(BREAKPOINT_TABLE[2].fullscreenGrid).toEqual([20, 11])
  })

  it('reproduces the empirical resolution table, including 2560x1440 -> breakpoint 3 = Large', () => {
    expect(breakpointForResolution(2560, 1440)).toBe(3)
    expect(breakpointForResolution(1920, 1080)).toBe(3)
    expect(breakpointForResolution(1920, 1200)).toBe(3)
    expect(breakpointForResolution(1440, 900)).toBe(2)
    expect(breakpointForResolution(1024, 768)).toBe(1)
    expect(breakpointName(breakpointForResolution(2560, 1440))).toBe('Large')
  })

  it('labels the composition file whose breakpoint is being edited', () => {
    expect(compositionForBreakpoint('SquadComposition-Large', 3)).toBe('SquadComposition-Large')
    expect(compositionForBreakpoint('SquadComposition-Large', 2)).toBe('SquadComposition-Standard')
    expect(compositionForBreakpoint('SquadComposition-Large', 1)).toBe('SquadComposition-Small')
  })

  it('maps the additive confidence label (both object and string forms), falling back to the existing selection evidence', () => {
    expect(confidenceLabel({ confidence: { label: 'measured' } })).toBe('measured')
    expect(confidenceLabel({ confidence: { label: 'measured mismatch' } })).toBe('measured mismatch')
    expect(confidenceLabel({ confidence: { label: 'computed' } })).toBe('computed')
    expect(confidenceLabel({ confidence: { label: 'unverified' } })).toBe('unverified')
    expect(confidenceLabel({ confidence: 'measured' })).toBe('measured')
    expect(confidenceLabel({ confidence: 'measured mismatch' })).toBe('measured mismatch')
    expect(confidenceLabel({ confidence: 'computed' })).toBe('computed')
    expect(confidenceLabel({ confidence: 'unverified' })).toBe('unverified')
    expect(confidenceLabel({ selection: { evidence: 'MEASURED' } })).toBe('measured')
    expect(confidenceLabel({ selection: { evidence: 'ESTIMATE' } })).toBe('computed')
    expect(confidenceLabel(null)).toBe('unverified')
  })
})

describe('UI1 breakpoint selector', () => {
  it('defaults to auto and shows Large / -Large at the project resolution 2560x1440', () => {
    render(<BreakpointSelector width={2560} height={1440} mode="auto" onModeChange={() => {}} composition="SquadComposition-Large" confidence={{ confidence: 'measured' }} />)
    expect((screen.getByTestId('pg-preview-breakpoint') as HTMLSelectElement).value).toBe('auto')
    expect(screen.getByTestId('pg-preview-breakpoint-value').getAttribute('data-breakpoint')).toBe('3')
    expect(screen.getByTestId('pg-preview-breakpoint-value').textContent).toContain('breakpoint 3 = Large')
    expect(screen.getByTestId('pg-preview-breakpoint-value').textContent).toContain('auto from 2560x1440')
    expect(screen.getByTestId('pg-preview-composition-file').getAttribute('data-composition')).toBe('SquadComposition-Large')
    expect(screen.getByTestId('pg-preview-composition-file').textContent).toContain('SquadComposition-Large')
    expect(screen.getByTestId('pg-preview-confidence').getAttribute('data-confidence')).toBe('measured')
    cleanup()
  })

  it('lets the owner pin Small/Standard/Large and relabels the composition file', () => {
    const change = vi.fn()
    render(<BreakpointSelector width={2560} height={1440} mode="auto" onModeChange={change} composition="SquadComposition-Large" confidence={null} />)
    const sel = screen.getByTestId('pg-preview-breakpoint') as HTMLSelectElement
    expect(Array.from(sel.options).map((o) => o.value)).toEqual(['auto', '1', '2', '3'])
    fireEvent.change(sel, { target: { value: '1' } })
    expect(change).toHaveBeenCalledWith('1')
    cleanup()
    render(<BreakpointSelector width={2560} height={1440} mode="1" onModeChange={() => {}} composition="SquadComposition-Large" confidence={null} />)
    expect(screen.getByTestId('pg-preview-breakpoint-value').textContent).toContain('breakpoint 1 = Small (chosen)')
    expect(screen.getByTestId('pg-preview-composition-file').getAttribute('data-composition')).toBe('SquadComposition-Small')
    expect(screen.getByTestId('pg-preview-confidence').getAttribute('data-confidence')).toBe('unverified')
  })
})
