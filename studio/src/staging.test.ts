import { describe, expect, it, vi } from 'vitest'
import { commit, commitParams, initial, isDirty, keyOf, reduce, thumbKey, type Slot, type Stored } from './staging'

const slot: Slot = { bundle: 'ui-backgrounds_assets_.bundle', path_id: '274891149646581386', kind: 'texture', name: 'wall' }
const key = keyOf(slot)
const stored: Stored = { ...slot, source: 'wall.png', fit: 'cover', where: ['main-screens'] }

describe('staging', () => {
  it('stage: picking a file, a fit or a place only changes the staged state', () => {
    let s = initial()
    s = reduce(s, { type: 'stage', slot, patch: { path: 'C:/pics/new.png' } })
    s = reduce(s, { type: 'stage', slot, patch: { fit: 'contain' } })
    s = reduce(s, { type: 'stage', slot, patch: { where: ['loading'] } })
    expect(s.staged[key]).toEqual({ slot, path: 'C:/pics/new.png', fit: 'contain', where: ['loading'] })
    expect(isDirty(s.staged[key], stored)).toBe(true)
    expect(s.versions).toEqual({})                                 // nothing was committed
  })

  it('a stage equal to what is stored is not dirty; any real difference is', () => {
    expect(isDirty(undefined, stored)).toBe(false)
    expect(isDirty({ slot, fit: 'cover', where: ['main-screens'] }, stored)).toBe(false)
    expect(isDirty({ slot, fit: 'stretch' }, stored)).toBe(true)
    expect(isDirty({ slot, where: ['main-screens', 'loading'] }, stored)).toBe(true)
    expect(isDirty({ slot, fit: 'contain' }, undefined)).toBe(false) // a new slot needs a file first
    expect(isDirty({ slot, path: 'x.png' }, undefined)).toBe(true)
  })

  it('revert: discards the staging and touches nothing else', () => {
    let s = reduce(initial(), { type: 'stage', slot, patch: { path: 'a.png', fit: 'stretch' } })
    s = reduce(s, { type: 'revert', key })
    expect(s.staged).toEqual({})
    expect(isDirty(s.staged[key], stored)).toBe(false)
  })

  it('commit: one images.commit call with file, fit and places together; then the stage is cleared and the version bumped', async () => {
    const call = vi.fn().mockResolvedValue({ project: {} })
    let s = reduce(initial(), { type: 'stage', slot, patch: { path: 'C:/pics/new.png', fit: 'contain', where: ['loading'] } })
    const r = await commit(call, 'Mine', s, key, stored)
    expect(call).toHaveBeenCalledTimes(1)
    expect(call).toHaveBeenCalledWith('images.commit', { project: 'Mine', bundle: slot.bundle, path_id: slot.path_id, kind: 'texture', name: 'wall', path: 'C:/pics/new.png', fit: 'contain', where: ['loading'] })
    expect(r.state.staged).toEqual({}); expect(r.state.versions[key]).toBe(1); expect(r.state.committed).toEqual([key])
  })

  it('commit sends only what was staged (no file when only the fit changed) and does nothing for a clean slot', async () => {
    const call = vi.fn().mockResolvedValue({})
    expect(commitParams('Mine', { slot, fit: 'stretch' }, stored)).toEqual({ project: 'Mine', bundle: slot.bundle, path_id: slot.path_id, kind: 'texture', name: 'wall', fit: 'stretch' })
    const clean = await commit(call, 'Mine', reduce(initial(), { type: 'stage', slot, patch: { fit: 'cover' } }), key, stored)
    expect(call).not.toHaveBeenCalled(); expect(clean.result).toBeNull()
  })

  it('a refused commit keeps the staging so nothing is lost', async () => {
    const call = vi.fn().mockRejectedValue(new Error('boom'))
    const s = reduce(initial(), { type: 'stage', slot, patch: { path: 'a.png' } })
    await expect(commit(call, 'Mine', s, key, stored)).rejects.toThrow('boom')
    expect(s.staged[key]).toBeDefined()
  })

  it('thumbnail refresh after save: the stored picture is fetched again because its cache key changes, even for the same file name', async () => {
    const before = thumbKey('Mine', stored.source, 0)
    const s = reduce(initial(), { type: 'stage', slot, patch: { path: 'a.png' } })
    const after = (await commit(vi.fn().mockResolvedValue({}), 'Mine', s, key, stored)).state
    expect(thumbKey('Mine', stored.source, after.versions[key] ?? 0)).not.toBe(before)
    const again = reduce(reduce(after, { type: 'stage', slot, patch: { path: 'b.png' } }), { type: 'committed', key })
    expect(again.versions[key]).toBe(2)
  })

  it('staging again after a commit clears the saved feedback for that slot', () => {
    let s = reduce(initial(), { type: 'committed', key })
    expect(s.committed).toEqual([key])
    s = reduce(s, { type: 'stage', slot, patch: { fit: 'stretch' } })
    expect(s.committed).toEqual([])
  })
})
