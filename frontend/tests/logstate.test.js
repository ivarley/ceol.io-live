import { describe, it, expect } from 'vitest'
import {
  computeOrdered, segmentByBreaks, setsOf, tunesOf,
  pluralType, setLabel, maxPos, cursorPos, remapAnchors,
  normName, normAbc, stripThe, openSetMergeTarget, mergeStable,
} from '../src/logstate.js'

// Compact record builder. Positions are single letters so ordering is obvious.
let _id = 0
function rec(pos, extra = {}) {
  return {
    session_instance_tune_id: extra.id ?? ++_id,
    tune_id: extra.tune_id ?? null,
    name: extra.name ?? null,
    order_position: pos,
    record_type: extra.record_type ?? 'tune',
    deleted: extra.deleted ?? false,
    tune_type: extra.tune_type ?? null,
    ...extra,
  }
}

describe('computeOrdered', () => {
  it('drops deleted rows and sorts by order_position (byte order)', () => {
    const recs = [rec('C', { id: 3 }), rec('A', { id: 1 }), rec('B', { id: 2, deleted: true }), rec('D', { id: 4 })]
    expect(computeOrdered(recs).map((r) => r.session_instance_tune_id)).toEqual([1, 3, 4])
  })

  it('accepts any iterable (e.g. a Map values())', () => {
    const m = new Map([[1, rec('B', { id: 1 })], [2, rec('A', { id: 2 })]])
    expect(computeOrdered(m.values()).map((r) => r.order_position)).toEqual(['A', 'B'])
  })
})

describe('segmentByBreaks', () => {
  it('splits into sets on break boundaries, recording the ending break id', () => {
    const ordered = [
      rec('A', { id: 1 }), rec('B', { id: 2 }),
      rec('C', { id: 3, record_type: 'break' }),
      rec('D', { id: 4 }),
    ]
    const segs = segmentByBreaks(ordered)
    expect(segs).toHaveLength(2)
    expect(segs[0].tunes.map((t) => t.session_instance_tune_id)).toEqual([1, 2])
    expect(segs[0].breakAfter).toBe(3)
    expect(segs[1].tunes.map((t) => t.session_instance_tune_id)).toEqual([4])
    expect(segs[1].breakAfter).toBeNull() // open set at the end
  })

  it('ignores a leading break and a trailing break closes the final set', () => {
    const ordered = [
      rec('A', { id: 1, record_type: 'break' }), // leading break -> ignored
      rec('B', { id: 2 }),
      rec('C', { id: 3, record_type: 'break' }),
    ]
    const segs = segmentByBreaks(ordered)
    expect(segs).toHaveLength(1)
    expect(segs[0].breakAfter).toBe(3) // trailing break explicitly closes the set
  })

  it('setsOf / tunesOf derive from the segmentation', () => {
    const ordered = [rec('A', { id: 1 }), rec('B', { id: 2, record_type: 'break' }), rec('C', { id: 3 })]
    expect(setsOf(segmentByBreaks(ordered))).toHaveLength(2)
    expect(tunesOf(ordered).map((r) => r.session_instance_tune_id)).toEqual([1, 3])
  })
})

describe('setLabel / pluralType', () => {
  it('pluralizes tune types with sibilant handling', () => {
    expect(pluralType('Reel')).toBe('Reels')
    expect(pluralType('Waltz')).toBe('Waltzes')
    expect(pluralType('March')).toBe('Marches')
    expect(pluralType('')).toBe('')
  })

  it('labels a set by shared type, Mixed, or Unknown', () => {
    expect(setLabel([{ tune_type: 'Reel' }, { tune_type: 'Reel' }])).toBe('Reels')
    expect(setLabel([{ tune_type: 'Reel' }, { tune_type: 'Jig' }])).toBe('Mixed')
    expect(setLabel([{ tune_type: null }])).toBe('Unknown')
  })
})

describe('maxPos', () => {
  it('returns the max order_position across ALL records (incl. deleted/temp)', () => {
    const recs = [rec('A'), rec('Z', { deleted: true }), rec('M', { _temp: true })]
    expect(maxPos(recs)).toBe('Z')
  })
  it('returns empty string for no records', () => {
    expect(maxPos([])).toBe('')
  })
})

describe('cursorPos', () => {
  const ordered = [rec('A', { id: 1 }), rec('C', { id: 2 })]
  const all = ordered

  it('appends past the high-water mark when cursor is null', () => {
    const cp = cursorPos(null, ordered, all)
    expect(cp.afterId).toBeNull()
    expect(cp.beforeId).toBeNull()
    expect(cp.position > 'C').toBe(true)
  })

  it('inserts strictly between neighbors for after-anchor', () => {
    const cp = cursorPos(1, ordered, all)
    expect(cp.afterId).toBe(1)
    expect('A' < cp.position && cp.position < 'C').toBe(true)
  })

  it('inserts before a record for a {before} cursor', () => {
    const cp = cursorPos({ before: 2 }, ordered, all)
    expect(cp.beforeId).toBe(2)
    expect('A' < cp.position && cp.position < 'C').toBe(true)
  })

  it('degrades to append when the anchor has vanished', () => {
    const cp = cursorPos(999, ordered, all)
    expect(cp.afterId).toBeNull()
    expect(cp.position > 'C').toBe(true)
  })
})

describe('remapAnchors', () => {
  const t2r = new Map([['temp-a', 100], ['temp-b', 200]])

  it('rewrites temp after/before anchors to real ids', () => {
    const { payload, skip } = remapAnchors({ after_record_id: 'temp-a', before_record_id: 'temp-b' }, t2r)
    expect(skip).toBe(false)
    expect(payload).toMatchObject({ after_record_id: 100, before_record_id: 200 })
  })

  it('falls back an unresolved anchor to null (append), not an error', () => {
    const { payload } = remapAnchors({ after_record_id: 'temp-unknown' }, t2r)
    expect(payload.after_record_id).toBeNull()
  })

  it('leaves non-temp anchors untouched', () => {
    const { payload } = remapAnchors({ after_record_id: 55 }, t2r)
    expect(payload.after_record_id).toBe(55)
  })

  it('resolves a temp record_id target', () => {
    const { payload, skip } = remapAnchors({ record_id: 'temp-a' }, t2r)
    expect(skip).toBe(false)
    expect(payload.record_id).toBe(100)
  })

  it('skips an op whose temp record_id never reached the server', () => {
    const { skip } = remapAnchors({ record_id: 'temp-orphan' }, t2r)
    expect(skip).toBe(true)
  })

  it('does not mutate the input payload (returns a copy)', () => {
    const input = { after_record_id: 'temp-a' }
    remapAnchors(input, t2r)
    expect(input.after_record_id).toBe('temp-a')
  })
})

describe('normalization', () => {
  it('normName folds smart quotes, strips accents, lowercases, trims', () => {
    expect(normName('  Cooley’s  ')).toBe("cooley's")
    expect(normName('Sligo Maíd')).toBe('sligo maid') // accented í -> i
    expect(normName('The Silver Spear')).toBe('the silver spear') // normName does NOT strip "the"
  })

  it('stripThe removes a leading "the "', () => {
    expect(stripThe('the silver spear')).toBe('silver spear')
    expect(stripThe('silver spear')).toBe('silver spear')
  })

  it('normAbc strips whitespace and lowercases', () => {
    expect(normAbc('FDD cAA | B2A')).toBe('fddcaa|b2a')
  })
})

describe('openSetMergeTarget', () => {
  it('finds a same-tune duplicate in the OPEN set (by tune_id)', () => {
    const ordered = [rec('A', { id: 1, tune_id: 7 }), rec('B', { id: 2, tune_id: 9 })]
    expect(openSetMergeTarget({ tune_id: 9 }, ordered).session_instance_tune_id).toBe(2)
  })

  it('matches an unlinked duplicate by normalized name', () => {
    const ordered = [rec('A', { id: 1, name: "Cooley’s" })]
    expect(openSetMergeTarget({ name: "cooley's" }, ordered).session_instance_tune_id).toBe(1)
  })

  it('does NOT match a duplicate in a CLOSED set (before the last break)', () => {
    const ordered = [
      rec('A', { id: 1, tune_id: 7 }),
      rec('B', { id: 2, record_type: 'break' }), // last break — open set starts after this
      rec('C', { id: 3, tune_id: 9 }),
    ]
    expect(openSetMergeTarget({ tune_id: 7 }, ordered)).toBeNull()
  })

  it('skips temp/deleted rows and returns null when nothing matches', () => {
    const ordered = [rec('A', { id: 1, tune_id: 7, _temp: true }), rec('B', { id: 2, tune_id: 8, deleted: true })]
    expect(openSetMergeTarget({ tune_id: 7 }, ordered)).toBeNull()
  })
})

describe('mergeStable', () => {
  it('pins local results, enriches with server fields, appends server-only, caps at 8', () => {
    const local = [{ tune_id: 1, name: 'A' }, { tune_id: 2, name: 'B' }]
    const server = [
      { tune_id: 2, name: 'B', in_session_tune: true, abc: 'xyz' }, // enriches local #2
      { tune_id: 3, name: 'C' }, // server-only -> appended
    ]
    const out = mergeStable(local, server)
    expect(out.map((r) => r.tune_id)).toEqual([1, 2, 3])
    expect(out[1].in_session_tune).toBe(true)
    expect(out[1].abc).toBe('xyz')
  })

  it('never exceeds 8 rows', () => {
    const local = Array.from({ length: 6 }, (_, i) => ({ tune_id: i + 1, name: `L${i}` }))
    const server = Array.from({ length: 6 }, (_, i) => ({ tune_id: i + 100, name: `S${i}` }))
    expect(mergeStable(local, server)).toHaveLength(8)
  })
})
