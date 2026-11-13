import { describe, expect, it } from 'vitest'
import { collisions, commitEdits, dirty, extent, movable, snap, stage, type Cell } from './tileStage'

const cell = (i: number, x: number, y: number, w: number, h: number, extra: Partial<Cell> = {}): Cell => ({ cell_index: i, element_id: 'C' + i, x, y, w, h, min_w: 0, min_h: 0, max_w: 0, max_h: 0, flags: [], ...extra })
// the real TacticalPlannerTeamInstructionsTabComposition-Standard: pitch (0,0 6x7) next to the instructions block (6,0 6x7)
const cells = [cell(0, 0, 0, 6, 7), cell(1, 6, 0, 6, 7)]

describe('tile canvas logic', () => {
  it('extent: the preset size when there is one, else the cells (staged positions included)', () => {
    expect(extent(cells, null)).toEqual({ cols: 12, rows: 7 })
    expect(extent(cells, { w: 16, h: 9 })).toEqual({ cols: 16, rows: 9 })
    expect(extent(cells, null, { 0: { x: 10, y: 0 } })).toEqual({ cols: 16, rows: 7 })
  })

  it('snap: a drag rounds to whole grid units and stays inside the grid', () => {
    const c = cells[0]
    expect(snap(c, { x: 0, y: 0 }, 100, 3, 40, 12, 7)).toEqual({ x: 3, y: 0 })          // 100 px at 40 px/unit = 2.5 -> 3
    expect(snap(c, { x: 0, y: 0 }, 900, 900, 40, 12, 7)).toEqual({ x: 6, y: 0 })          // clamped: x <= cols - w, y <= rows - h
    expect(snap(c, { x: 3, y: 0 }, -900, -900, 40, 12, 7)).toEqual({ x: 0, y: 0 })
  })

  it('locked cells and auto-placed cells (x or y of -1) cannot be moved', () => {
    expect(movable(cell(0, 0, 0, 2, 2))).toBe(true)
    expect(movable(cell(0, 0, 0, 2, 2, { flags: ['locked'] }))).toBe(false)
    expect(movable(cell(0, -1, -1, 2, 2))).toBe(false)
  })

  it('stage: a move is staged, moving back un-stages it; nothing else changes', () => {
    let s = stage({}, cells[0], { x: 6, y: 0 })
    expect(dirty(cells, s)).toEqual([0])
    s = stage(s, cells[0], { x: 0, y: 0 })
    expect(s).toEqual({}); expect(dirty(cells, s)).toEqual([])
  })

  it('collisions: dropping on a neighbour flags both; completing the swap clears them', () => {
    let s = stage({}, cells[0], { x: 6, y: 0 })
    expect(collisions(cells, s)).toEqual([0, 1])
    s = stage(s, cells[1], { x: 0, y: 0 })
    expect(collisions(cells, s)).toEqual([])
  })

  it('commit: one edit per moved cell with the new x/y and the unchanged size', () => {
    const s = { 1: { x: 0, y: 0 }, 0: { x: 6, y: 0 } }
    expect(commitEdits('Comp-Standard', cells, s)).toEqual([
      { composition: 'Comp-Standard', cell_index: 0, geometry: { x: 6, y: 0, w: 6, h: 7 }, note: 'moved in the tile canvas' },
      { composition: 'Comp-Standard', cell_index: 1, geometry: { x: 0, y: 0, w: 6, h: 7 }, note: 'moved in the tile canvas' },
    ])
  })
})
