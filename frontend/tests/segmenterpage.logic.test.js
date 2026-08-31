// Unit tests for the segmenter's pure logic (spec 050). The end-resolution rule
// is implemented twice — here for the live display, and in SQL for the export —
// so it is worth pinning both. The SQL side is covered by
// tests/integration/test_recording_segmenter_050.py.
import { describe, it, expect } from 'vitest'
import {
  edgeLimits,
  envelopeForRange,
  formatDuration,
  formatTime,
  groupIntoSets,
  MIN_SEGMENT_MS,
  nextUnplacedIndex,
  resolveSegments,
  snapToOnset,
} from '../src/segmenterpage/logic.js'

const tune = (id, setNumber, segment = null) => ({
  session_instance_tune_id: id,
  name: `tune-${id}`,
  set_number: setNumber,
  segment,
})

describe('formatTime', () => {
  it('drops the hour component below an hour and keeps it above', () => {
    expect(formatTime(0)).toBe('0:00')
    expect(formatTime(65000)).toBe('1:05')
    expect(formatTime(3725000)).toBe('1:02:05')
  })

  it('shows tenths only when asked', () => {
    expect(formatTime(65400)).toBe('1:05')
    expect(formatTime(65400, { millis: true })).toBe('1:05.4')
  })

  it('renders a placeholder rather than NaN for missing values', () => {
    expect(formatTime(null)).toBe('--:--')
    expect(formatTime(Infinity)).toBe('--:--')
  })
})

describe('formatDuration', () => {
  it('uses seconds under a minute and m:ss above', () => {
    expect(formatDuration(42000)).toBe('42s')
    expect(formatDuration(125000)).toBe('2:05')
  })
})

describe('resolveSegments', () => {
  it('runs an implicit end to the next placed start', () => {
    const tunes = [
      tune(1, 1, { start_ms: 1000, end_ms: null }),
      tune(2, 1, { start_ms: 40000, end_ms: null }),
    ]
    const resolved = resolveSegments(tunes, 600000)
    expect(resolved.get(1)).toMatchObject({ endMs: 40000, explicitEnd: false })
  })

  it('runs a trailing implicit end to the end of the recording', () => {
    const tunes = [tune(1, 1, { start_ms: 1000, end_ms: null })]
    expect(resolveSegments(tunes, 600000).get(1).endMs).toBe(600000)
  })

  it('keeps an explicit end and reports the gap that follows it', () => {
    const tunes = [
      tune(1, 1, { start_ms: 1000, end_ms: 20000 }),
      tune(2, 2, { start_ms: 50000, end_ms: null }),
    ]
    const resolved = resolveSegments(tunes, 600000)
    expect(resolved.get(1)).toMatchObject({ endMs: 20000, explicitEnd: true, gapAfterMs: 30000 })
  })

  it('skips over unplaced tunes rather than ending on them', () => {
    // The tune between them was never marked; the first must still run to the
    // next tune that WAS marked, not stop short.
    const tunes = [
      tune(1, 1, { start_ms: 1000, end_ms: null }),
      tune(2, 1, null),
      tune(3, 1, { start_ms: 90000, end_ms: null }),
    ]
    expect(resolveSegments(tunes, 600000).get(1).endMs).toBe(90000)
  })

  it('orders by time, not by log position', () => {
    const tunes = [
      tune(1, 1, { start_ms: 90000, end_ms: null }),
      tune(2, 1, { start_ms: 10000, end_ms: null }),
    ]
    const resolved = resolveSegments(tunes, 600000)
    expect(resolved.get(2).endMs).toBe(90000)
    expect(resolved.get(1).endMs).toBe(600000)
  })

  it('returns nothing for an untouched log', () => {
    expect(resolveSegments([tune(1, 1), tune(2, 1)], 600000).size).toBe(0)
  })
})

describe('nextUnplacedIndex', () => {
  it('finds the first gap at or after the given index', () => {
    const tunes = [tune(1, 1, { start_ms: 0, end_ms: null }), tune(2, 1), tune(3, 1)]
    expect(nextUnplacedIndex(tunes, 0)).toBe(1)
    expect(nextUnplacedIndex(tunes, 2)).toBe(2)
  })

  it('reports -1 when everything is placed', () => {
    expect(nextUnplacedIndex([tune(1, 1, { start_ms: 0, end_ms: null })], 0)).toBe(-1)
  })
})

describe('groupIntoSets', () => {
  it('groups consecutive tunes sharing a set number', () => {
    const sets = groupIntoSets([tune(1, 1), tune(2, 1), tune(3, 2)])
    expect(sets.map((s) => [s.setNumber, s.tunes.length])).toEqual([
      [1, 2],
      [2, 1],
    ])
  })
})

describe('snapToOnset', () => {
  const HZ = 20

  it('pulls a mark back onto a sharp rise', () => {
    // 10s of quiet then loud; the step is at index 200 (= 10 000ms).
    const peaks = new Uint8Array(400)
    peaks.fill(10, 0, 200)
    peaks.fill(200, 200, 400)
    // Marked 400ms late by eye — snapping should land on the step.
    expect(snapToOnset(peaks, HZ, 10400)).toBe(10000)
  })

  it('leaves a mark alone when the window has no real onset', () => {
    // Uniform loud audio: mid-tune, nothing to snap to.
    const peaks = new Uint8Array(400).fill(180)
    expect(snapToOnset(peaks, HZ, 10500)).toBe(10500)
  })

  it('will not drag a mark across a distant onset outside its window', () => {
    const peaks = new Uint8Array(2000)
    peaks.fill(10, 0, 1000)
    peaks.fill(200, 1000, 2000) // onset at 50 000ms
    // Marked at 10s, far from the rise: unchanged.
    expect(snapToOnset(peaks, HZ, 10000)).toBe(10000)
  })

  it('leaves a deliberate mark alone when the next attack is a second away', () => {
    // The regression this window size exists for: the tune has already begun at
    // the mark, and a louder phrase follows 1.3s later. Snap must not walk the
    // mark forward onto it.
    const peaks = new Uint8Array(600).fill(120)
    peaks.fill(240, 246, 600) // step 1.3s after a mark at 10 000ms
    expect(snapToOnset(peaks, HZ, 10000)).toBe(10000)
  })

  it('still corrects a small eyeball error', () => {
    const peaks = new Uint8Array(600)
    peaks.fill(10, 0, 208)
    peaks.fill(200, 208, 600) // onset at 10 400ms
    // Marked 300ms early: inside the window, so it snaps onto the note.
    expect(snapToOnset(peaks, HZ, 10100)).toBe(10400)
  })

  it('is a no-op without a waveform', () => {
    expect(snapToOnset(null, HZ, 1234)).toBe(1234)
    expect(snapToOnset(new Uint8Array(0), HZ, 1234)).toBe(1234)
  })
})

describe('envelopeForRange', () => {
  it('reduces to one normalised value per column, taking the peak in each', () => {
    const peaks = new Uint8Array([0, 255, 0, 0, 128, 0, 0, 0])
    const env = envelopeForRange(peaks, 20, 0, 400, 2)
    expect(env.length).toBe(2)
    expect(env[0]).toBeCloseTo(1, 5) // the 255 dominates its column
    expect(env[1]).toBeCloseTo(128 / 255, 5)
  })

  it('returns an empty array for a zero width', () => {
    expect(envelopeForRange(new Uint8Array([1, 2]), 20, 0, 100, 0).length).toBe(0)
  })
})

describe('edgeLimits', () => {
  // A dragged boundary must not be able to swallow its neighbour, cross its own
  // opposite edge, or leave the file -- all of which the API would reject at the
  // END of the gesture, when the operator has already let go.
  const seg = (startMs, endMs, explicitEnd) => ({ startMs, endMs, explicitEnd, gapAfterMs: 0 })

  //  A: 10s -> 20s implicit (so its end IS B's start)
  //  B: 20s -> 30s explicit, then a gap
  //  C: 40s -> 60s implicit to the end of the file
  const resolved = () =>
    new Map([
      [1, seg(10000, 20000, false)],
      [2, seg(20000, 30000, true)],
      [3, seg(40000, 60000, false)],
    ])

  it('stops a start short of its own end', () => {
    const { hi } = edgeLimits(resolved(), 2, 'start', 60000)
    expect(hi).toBe(30000 - MIN_SEGMENT_MS)
  })

  it('lets a start run back into the gap left by an explicit end', () => {
    // C follows B's explicit end at 30s, so C's start may move back to 30s --
    // the dead air is nobody's, and reclaiming it is the point of dragging.
    expect(edgeLimits(resolved(), 3, 'start', 60000).lo).toBe(30000)
  })

  it('lets a start eat into the previous tune when that end is implicit', () => {
    // B's start IS A's end, so moving it moves their shared edge -- bounded only
    // by leaving A something to be.
    expect(edgeLimits(resolved(), 2, 'start', 60000).lo).toBe(10000 + MIN_SEGMENT_MS)
  })

  it('bounds a start by the NEXT start when its own end is implicit', () => {
    expect(edgeLimits(resolved(), 1, 'start', 60000).hi).toBe(20000 - MIN_SEGMENT_MS)
  })

  it('bounds an explicit end by its own start and the next tune', () => {
    expect(edgeLimits(resolved(), 2, 'end', 60000)).toEqual({
      lo: 20000 + MIN_SEGMENT_MS,
      hi: 40000,
    })
  })

  it('uses the file for the outer edges', () => {
    expect(edgeLimits(resolved(), 1, 'start', 60000).lo).toBe(0)
    expect(edgeLimits(resolved(), 3, 'start', 60000).hi).toBe(60000 - MIN_SEGMENT_MS)
  })

  it('has nothing to say about a tune that is not placed', () => {
    expect(edgeLimits(resolved(), 99, 'start', 60000)).toBeNull()
  })
})
