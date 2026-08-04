// Unit tests for the segmenter's pure logic (spec 050). The end-resolution rule
// is implemented twice — here for the live display, and in SQL for the export —
// so it is worth pinning both. The SQL side is covered by
// tests/integration/test_recording_segmenter_050.py.
import { describe, it, expect } from 'vitest'
import {
  envelopeForRange,
  formatDuration,
  formatTime,
  groupIntoSets,
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
    // Marked 500ms late by eye — snapping should land on the step.
    expect(snapToOnset(peaks, HZ, 10500)).toBe(10000)
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
