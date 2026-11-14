// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import Gutter, { clamp, useStoredSize } from './Gutter'

function Host({ axis = 'x', invert = false, storeKey = 'test.size' }: { axis?: 'x' | 'y'; invert?: boolean; storeKey?: string }) {
  const [v, set] = useStoredSize(storeKey, 250, 100, 400)
  return <div><Gutter axis={axis} value={v} min={100} max={400} def={250} onChange={set} label="Sidebar width" invert={invert} /><span data-testid="v">{v}</span></div>
}
const value = () => Number(screen.getByTestId('v').textContent)

beforeEach(() => { try { localStorage.clear() } catch { /* ignore */ } })
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('Gutter', () => {
  it('is a separator with its value and limits, for assistive technology', () => {
    render(<Host />)
    const g = screen.getByRole('separator')
    expect(g.getAttribute('aria-valuenow')).toBe('250'); expect(g.getAttribute('aria-valuemin')).toBe('100'); expect(g.getAttribute('aria-valuemax')).toBe('400')
    expect(g.getAttribute('aria-orientation')).toBe('vertical')
  })

  it('dragging with the mouse changes the size, clamped to the limits, and releases the page', () => {
    render(<Host />)
    const g = screen.getByRole('separator')
    fireEvent.mouseDown(g, { clientX: 300 })
    expect(document.body.style.cursor).toBe('col-resize')
    fireEvent.mouseMove(window, { clientX: 340 }); expect(value()).toBe(290)
    fireEvent.mouseMove(window, { clientX: 900 }); expect(value()).toBe(400)         // upper limit
    fireEvent.mouseMove(window, { clientX: -900 }); expect(value()).toBe(100)        // lower limit
    fireEvent.mouseUp(window)
    expect(document.body.style.cursor).toBe('')
    fireEvent.mouseMove(window, { clientX: 350 }); expect(value()).toBe(100)         // a released drag no longer follows the mouse
  })

  it('a pane after the bar (invert) gets smaller when dragged towards it, on the y axis too', () => {
    render(<Host axis="y" invert />)
    const g = screen.getByRole('separator')
    expect(g.getAttribute('aria-orientation')).toBe('horizontal')
    fireEvent.mouseDown(g, { clientY: 500 })
    fireEvent.mouseMove(window, { clientY: 450 }); expect(value()).toBe(300)         // moved up 50: the bottom panel grows
    fireEvent.mouseUp(window)
  })

  it('keyboard: arrows, shift, Home, End, Enter resets, other keys are ignored', () => {
    render(<Host />)
    const g = screen.getByRole('separator')
    fireEvent.keyDown(g, { key: 'ArrowRight' }); expect(value()).toBe(260)
    fireEvent.keyDown(g, { key: 'ArrowLeft', shiftKey: true }); expect(value()).toBe(210)
    fireEvent.keyDown(g, { key: 'End' }); expect(value()).toBe(400)
    fireEvent.keyDown(g, { key: 'Home' }); expect(value()).toBe(100)
    fireEvent.keyDown(g, { key: 'x' }); expect(value()).toBe(100)
    fireEvent.keyDown(g, { key: 'Enter' }); expect(value()).toBe(250)
  })

  it('double-click resets to the default', () => {
    render(<Host />)
    const g = screen.getByRole('separator')
    fireEvent.keyDown(g, { key: 'End' }); expect(value()).toBe(400)
    fireEvent.doubleClick(g); expect(value()).toBe(250)
  })

  it('the size is remembered, an out-of-range stored value is clamped, and failing storage does not break it', () => {
    localStorage.setItem('test.size', '9999')
    const { unmount } = render(<Host />)
    expect(value()).toBe(400)
    fireEvent.keyDown(screen.getByRole('separator'), { key: 'Home' })
    expect(localStorage.getItem('test.size')).toBe('100')
    unmount()
    expect(Object.keys(localStorage)).toContain('test.size')
    cleanup()
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    render(<Host storeKey="other" />)
    expect(value()).toBe(250)
    fireEvent.keyDown(screen.getByRole('separator'), { key: 'ArrowRight' }); expect(value()).toBe(260)
  })

  it('clamp', () => { expect(clamp(5, 10, 20)).toBe(10); expect(clamp(15, 10, 20)).toBe(15); expect(clamp(25, 10, 20)).toBe(20) })
})
