import { describe, it, expect } from 'vitest'
import { computeOrdered, segmentByBreaks } from '../src/logstate.js'
import {
  dragBlock, dropTargets, optimisticMove,
  serializeClipboard, parseClipboard,
  rangeBetween, selectableIds,
} from '../src/selection.js'

// Compact fixture: build live records from a spec like [['A','B'],['C','D']].
// Ids are the names; breaks get ids 'brk0', 'brk1'… Positions are generated in
// listing order using letters so byte-order matches visual order.
function log(sets) {
  const records = []
  let pos = 'A'.charCodeAt(0)
  sets.forEach((names, si) => {
    for (const n of names) {
      records.push({
        session_instance_tune_id: n, tune_id: null, name: `Tune ${n}`,
        order_position: String.fromCharCode(pos++), record_type: 'tune', deleted: false,
      })
    }
    if (si < sets.length - 1) {
      records.push({
        session_instance_tune_id: `brk${si}`, tune_id: null, name: null,
        order_position: String.fromCharCode(pos++), record_type: 'break', deleted: false,
      })
    }
  })
  const ordered = computeOrdered(records)
  return { records, ordered, segments: segmentByBreaks(ordered) }
}

// --------------------------------------------------------------------------- //
// dragBlock: what the grab bar lifts (spec 029 §F)
// --------------------------------------------------------------------------- //

describe('dragBlock', () => {
  it('unselected grabbed row drags just itself, selection untouched', () => {
    const { ordered } = log([['A', 'B', 'C']])
    const b = dragBlock(ordered, new Set(['A', 'C']), 'B')
    expect(b.tuneIds).toEqual(['B'])
    expect(b.recordIds).toEqual(['B'])
    expect(b.setCount).toBe(1)
  })

  it('selected grabbed row drags its contiguous selected run', () => {
    const { ordered } = log([['A', 'B', 'C', 'D']])
    const b = dragBlock(ordered, new Set(['B', 'C']), 'C')
    expect(b.tuneIds).toEqual(['B', 'C'])
  })

  it('non-contiguous selection: only the run containing the grabbed row moves', () => {
    const { ordered } = log([['A', 'B', 'C', 'D', 'E']])
    const b = dragBlock(ordered, new Set(['A', 'B', 'D']), 'D')
    expect(b.tuneIds).toEqual(['D'])
  })

  it('runs extend across breaks and interior breaks travel with the block', () => {
    const { ordered } = log([['A', 'B'], ['C', 'D'], ['E']])
    const b = dragBlock(ordered, new Set(['B', 'C', 'D']), 'C')
    expect(b.tuneIds).toEqual(['B', 'C', 'D'])
    expect(b.recordIds).toEqual(['B', 'brk0', 'C', 'D']) // brk0 is interior to the run
    expect(b.setCount).toBe(2)
  })

  it('grabbing a temp/removing row yields null', () => {
    const { ordered } = log([['A']])
    ordered[0]._temp = true
    expect(dragBlock(ordered, new Set(), 'A')).toBeNull()
  })
})

// --------------------------------------------------------------------------- //
// dropTargets: every eligible drop zone, top to bottom (spec 029 §F)
// --------------------------------------------------------------------------- //

describe('dropTargets', () => {
  it('enumerates weld + new-set zones and anchors them like the seams', () => {
    const { ordered, segments } = log([['A', 'B'], ['C']])
    const keys = dropTargets(ordered, segments, true, ['C']).map((t) => t.key)
    // moving C: top-new (new set at very start), start of set 1, after A, after B.
    // Excluded: inter (C bounds it), end / end-new (C is the open last set).
    expect(keys).toEqual(['top-new', 'start:A', 'after:A', 'after:B'])
  })

  it('top-new target is new_set anchored before the first tune', () => {
    const { ordered, segments } = log([['A', 'B'], ['C']])
    const top = dropTargets(ordered, segments, true, ['C'])[0]
    expect(top).toMatchObject({ key: 'top-new', before_record_id: 'A', new_set: true })
  })

  it('excludes seams interior to and bounding the block', () => {
    const { ordered, segments } = log([['A', 'B', 'C', 'D']])
    const keys = dropTargets(ordered, segments, true, ['B', 'C']).map((t) => t.key)
    expect(keys).not.toContain('after:A') // bounding (drop = no-op)
    expect(keys).not.toContain('after:B') // interior
    expect(keys).not.toContain('after:C') // bounding
    expect(keys).toContain('end') // D is the open set's last tune → its seam IS the end
    expect(keys).toContain('start:A')
  })

  it('excludes the inter seam when the block is exactly the set above it', () => {
    const { ordered, segments } = log([['A', 'B'], ['C'], ['D']])
    const keys = dropTargets(ordered, segments, true, ['A', 'B']).map((t) => t.key)
    expect(keys).not.toContain('inter:C') // dropping own full set into the gap below = no-op
    expect(keys).not.toContain('top-new') // anchor (A) is inside the block
    expect(keys).toContain('inter:D')
  })

  it('keeps the inter seam when the block is only the tail of the set above', () => {
    const { ordered, segments } = log([['A', 'B'], ['C'], ['D']])
    const keys = dropTargets(ordered, segments, true, ['B']).map((t) => t.key)
    expect(keys).toContain('inter:C') // splits B off as its own set — meaningful
  })

  it('open end offers weld (end) and own-set (end-new) targets', () => {
    const { ordered, segments } = log([['A', 'B'], ['C', 'D']])
    const ts = dropTargets(ordered, segments, true, ['A'])
    const end = ts.find((t) => t.key === 'end')
    const endNew = ts.find((t) => t.key === 'end-new')
    expect(end).toMatchObject({ after_record_id: null, new_set: false })
    expect(endNew).toMatchObject({ after_record_id: null, new_set: true })
  })

  it('closed end offers a single new-set end target', () => {
    // closed end: trailing break after the last set
    const { records } = log([['A', 'B']])
    records.push({ session_instance_tune_id: 'brkEnd', order_position: 'Z', record_type: 'break', deleted: false })
    const ordered = computeOrdered(records)
    const segments = segmentByBreaks(ordered)
    const ts = dropTargets(ordered, segments, false, ['A'])
    const end = ts.find((t) => t.key === 'end')
    expect(end).toMatchObject({ after_record_id: null, new_set: true })
    expect(ts.find((t) => t.key === 'end-new')).toBeUndefined()
  })
})

// --------------------------------------------------------------------------- //
// optimisticMove: client-side preview keys (must mirror the server's
// exclude-the-block rule so the settle doesn't visibly jump)
// --------------------------------------------------------------------------- //

describe('optimisticMove', () => {
  it('generates in-order keys in the destination gap, excluding the block', () => {
    const { records, ordered } = log([['A', 'B', 'C', 'D']])
    const { positions } = optimisticMove(ordered, records, ['C', 'D'],
      { after_record_id: 'A', before_record_id: null, new_set: false })
    const posOf = (id) => positions.get(id) ?? records.find((r) => r.session_instance_tune_id === id).order_position
    // new order: A C D B
    expect(posOf('A') < posOf('C')).toBe(true)
    expect(posOf('C') < posOf('D')).toBe(true)
    expect(posOf('D') < posOf('B')).toBe(true)
  })

  it('block adjacent to the anchor: succ skips the block itself', () => {
    const { records, ordered } = log([['A', 'B', 'C']])
    // move [B] after A — B is already right after A; succ must be C, not B's old slot
    const { positions } = optimisticMove(ordered, records, ['B'],
      { after_record_id: 'A', before_record_id: null, new_set: false })
    const key = positions.get('B')
    const pos = (id) => records.find((r) => r.session_instance_tune_id === id).order_position
    expect(key > pos('A')).toBe(true)
    expect(key < pos('C')).toBe(true)
  })

  it('append target: keys land after everything non-block', () => {
    const { records, ordered } = log([['A', 'B'], ['C']])
    const { positions } = optimisticMove(ordered, records, ['A'],
      { after_record_id: null, before_record_id: null, new_set: false })
    const pos = (id) => records.find((r) => r.session_instance_tune_id === id).order_position
    expect(positions.get('A') > pos('C')).toBe(true)
  })

  it('new_set emits temp boundary break keys only where a live tune would weld', () => {
    const { records, ordered } = log([['A', 'B'], ['C', 'D']])
    // drop [B] before C as a new set: pred side is brk0 (no break needed),
    // succ side is tune C (break needed)
    const { positions, tempBreakKeys } = optimisticMove(ordered, records, ['B'],
      { after_record_id: null, before_record_id: 'C', new_set: true })
    expect(tempBreakKeys.before).toBeNull()
    expect(tempBreakKeys.after).not.toBeNull()
    expect(positions.get('B') < tempBreakKeys.after).toBe(true)
  })
})

// --------------------------------------------------------------------------- //
// clipboard (spec 029 §D): old-pill-logger-compatible plain text + rich internal
// --------------------------------------------------------------------------- //

describe('serializeClipboard', () => {
  it('groups selected tunes by set: lines = sets, commas = tunes', () => {
    const { segments } = log([['A', 'B'], ['C', 'D'], ['E']])
    const { text, rich } = serializeClipboard(segments, new Set(['A', 'B', 'D']))
    expect(text).toBe('Tune A, Tune B\nTune D')
    expect(rich).toEqual([
      [{ tune_id: null, name: 'Tune A', tune_type: null }, { tune_id: null, name: 'Tune B', tune_type: null }],
      [{ tune_id: null, name: 'Tune D', tune_type: null }],
    ])
  })

  it('empty selection yields null', () => {
    const { segments } = log([['A']])
    expect(serializeClipboard(segments, new Set())).toBeNull()
  })
})

describe('parseClipboard', () => {
  it('own last copy → internal rich data (tune_id links survive)', () => {
    const last = { text: 'X, Y', rich: [[{ tune_id: 7, name: 'X' }, { tune_id: 8, name: 'Y' }]] }
    const r = parseClipboard('X, Y', last)
    expect(r).toEqual({ kind: 'internal', sets: last.rich })
  })

  it('old-logger JSON pill format → mapped sets', () => {
    const json = JSON.stringify([[{ tuneId: 42, tuneName: 'The Kesh' }], [{ tuneId: null, tuneName: 'Mystery' }]])
    const r = parseClipboard(json, null)
    expect(r.kind).toBe('json')
    expect(r.sets).toEqual([[{ tune_id: 42, name: 'The Kesh' }], [{ tune_id: null, name: 'Mystery' }]])
  })

  it('old-old flat pill array counts as one set', () => {
    const json = JSON.stringify([{ tuneId: 1, tuneName: 'A' }, { tuneId: 2, tuneName: 'B' }])
    const r = parseClipboard(json, null)
    expect(r.sets).toEqual([[{ tune_id: 1, name: 'A' }, { tune_id: 2, name: 'B' }]])
  })

  it('plain text: lines = sets, commas = tunes, whitespace trimmed', () => {
    const r = parseClipboard(' The Kesh, Morrisons \n\nBanish Misfortune \n', null)
    expect(r.kind).toBe('text')
    expect(r.sets).toEqual([
      [{ tune_id: null, name: 'The Kesh' }, { tune_id: null, name: 'Morrisons' }],
      [{ tune_id: null, name: 'Banish Misfortune' }],
    ])
  })

  it('empty / whitespace clipboard → null', () => {
    expect(parseClipboard('   \n ', null)).toBeNull()
    expect(parseClipboard('', null)).toBeNull()
  })
})

// --------------------------------------------------------------------------- //
// range select + filter-aware select all (spec 029 §B)
// --------------------------------------------------------------------------- //

describe('rangeBetween', () => {
  it('selects tunes between anchor and target inclusive, across breaks', () => {
    const { ordered } = log([['A', 'B'], ['C', 'D']])
    expect(rangeBetween(ordered, 'B', 'D')).toEqual(['B', 'C', 'D'])
    expect(rangeBetween(ordered, 'D', 'B')).toEqual(['B', 'C', 'D']) // either direction
  })

  it('missing anchor or target → just the target', () => {
    const { ordered } = log([['A', 'B']])
    expect(rangeBetween(ordered, 'ghost', 'B')).toEqual(['B'])
  })
})

describe('selectableIds', () => {
  it('no filter: every settled tune', () => {
    const { segments } = log([['A', 'B'], ['C']])
    expect(selectableIds(segments, '')).toEqual(['A', 'B', 'C'])
  })

  it('with filter: only matching tunes (not their whole sets)', () => {
    const { segments } = log([['A', 'B'], ['C']])
    expect(selectableIds(segments, 'tune b')).toEqual(['B'])
  })

  it('skips temp rows', () => {
    const { segments } = log([['A', 'B']])
    segments[0].tunes[0]._temp = true
    expect(selectableIds(segments, '')).toEqual(['B'])
  })
})
