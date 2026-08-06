// The segment logic shared by the segmenter (which places marks) and the
// session-instance page (which plays them). resolveSegments is covered by
// segmenterpage.logic.test.js through its re-export; what's new here is
// playbackStep, the frame-by-frame queue advance.

import { describe, it, expect } from 'vitest'
import { resolveSegments, playbackStep, formatClock } from '../src/shared/segments.js'

/** {id: [start, end?]} -> the resolved Map playbackStep consumes. */
function resolvedFrom(spec, durationMs = 600000) {
  return resolveSegments(
    Object.entries(spec).map(([id, [start, end = null]]) => ({
      session_instance_tune_id: Number(id),
      segment: { start_ms: start, end_ms: end },
    })),
    durationMs,
  )
}

describe('playbackStep', () => {
  // A set logged straight through: each tune's implicit end IS the next one's
  // start, so playback must never seek — a seek here would rebuffer mid-set.
  const contiguous = resolvedFrom({ 1: [10000], 2: [130000], 3: [250000] })

  it('leaves the playhead alone in the middle of a tune', () => {
    expect(playbackStep([1, 2, 3], 0, 60000, contiguous)).toEqual({
      idx: 0, seekMs: null, done: false,
    })
  })

  it('advances to the next tune at the boundary without seeking', () => {
    expect(playbackStep([1, 2, 3], 0, 129990, contiguous)).toEqual({
      idx: 1, seekMs: null, done: false,
    })
  })

  it('hands over slightly EARLY so the frame-sampled playhead does not overshoot', () => {
    // 40ms before the end is already the next tune's problem; a whole frame late
    // would play the first instant of whatever follows.
    expect(playbackStep([1, 2, 3], 0, 129970, contiguous).idx).toBe(1)
    expect(playbackStep([1, 2, 3], 0, 129950, contiguous).idx).toBe(0)
  })

  it('ends the queue after the last tune rather than running on', () => {
    expect(playbackStep([1, 2, 3], 2, 600000, contiguous)).toEqual({
      idx: 2, seekMs: null, done: true,
    })
  })

  it('skips the dead air after an explicit end', () => {
    // Tune 1 explicitly ends at 2:10; the next tune doesn't start until 3:00.
    // That 50 seconds is chatting and tuning, and is exactly what we don't play.
    const gapped = resolvedFrom({ 1: [10000, 130000], 2: [180000] })
    expect(playbackStep([1, 2], 0, 130000, gapped)).toEqual({
      idx: 1, seekMs: 180000, done: false,
    })
  })

  it('stops at the end of the QUEUE even when the recording continues', () => {
    // Playing one set of a three-set night: the queue is that set only, so the
    // next set is never spliced onto it, however the last tune's end resolves.
    const night = resolvedFrom({ 1: [10000], 2: [130000, 250000], 3: [900000] })
    expect(playbackStep([1, 2], 1, 250000, night).done).toBe(true)
  })

  it('runs a set-final tune to the NEXT SET when its end was left implicit', () => {
    // Documenting a real limitation rather than papering over it. An implicit end
    // means "runs until the next tune starts" -- inside a set that's exactly right,
    // but on the last tune of a set the next tune is 10 minutes and one conversation
    // away, so playback runs long. The fix is upstream: the segmenter flags exactly
    // these tunes (is_set_end) as the ones needing an EXPLICIT end, and well-marked
    // data therefore never lands here. Guessing a cutoff would be inventing data we
    // don't have.
    const night = resolvedFrom({ 1: [10000], 2: [130000], 3: [900000] })
    expect(night.get(2).endMs).toBe(900000)
    expect(playbackStep([1, 2], 1, 250000, night).done).toBe(false)
  })

  it('is done rather than stuck when a mark disappears underneath it', () => {
    // The log is live: another logger can delete the tune being played.
    expect(playbackStep([1, 99], 1, 5000, contiguous)).toEqual({
      idx: 1, seekMs: null, done: true,
    })
    expect(playbackStep([1, 99], 0, 129990, contiguous).done).toBe(true)
  })

  it('treats a scrub backwards as "still inside this tune"', () => {
    expect(playbackStep([1, 2, 3], 1, 5000, contiguous)).toEqual({
      idx: 1, seekMs: null, done: false,
    })
  })
})

describe('formatClock', () => {
  it('is mm:ss below an hour and h:mm:ss above', () => {
    expect(formatClock(0)).toBe('0:00')
    expect(formatClock(65000)).toBe('1:05')
    expect(formatClock(3725000)).toBe('1:02:05')
  })

  it('says --:-- rather than NaN for nothing', () => {
    expect(formatClock(null)).toBe('--:--')
    expect(formatClock(Infinity)).toBe('--:--')
  })
})
