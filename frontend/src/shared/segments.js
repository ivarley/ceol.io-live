// Recording-segment logic shared by the two pages that care about it: the
// segmenter, which PLACES the marks (spec 050), and the session-instance page,
// which PLAYS them. End resolution in particular must not fork — a tune whose
// extent differs between the tool that marked it and the page that plays it is
// a bug nobody would think to look for.

/** mm:ss (h:mm:ss past an hour) for a millisecond offset. `--:--` for nothing. */
export function formatClock(ms, { millis = false } = {}) {
  if (ms == null || !isFinite(ms)) return '--:--'
  const sign = ms < 0 ? '-' : ''
  let t = Math.abs(Math.round(ms))
  const msPart = t % 1000
  t = Math.floor(t / 1000)
  const s = t % 60
  const m = Math.floor(t / 60) % 60
  const h = Math.floor(t / 3600)
  const base = h
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`
  return sign + base + (millis ? `.${String(msPart).padStart(3, '0')[0]}` : '')
}

/**
 * Resolve every placed tune's end time.
 *
 * An implicit end (end_ms == null) runs to the next PLACED tune's start -- not
 * the next tune in the log, which may never be placed at all. The last placed
 * tune, left implicit, runs to the end of the recording. This mirrors the
 * recording_tune_segment_resolved view exactly; the client re-runs it on every
 * change so the display never waits on a round trip.
 *
 * Returns a Map: session_instance_tune_id -> { startMs, endMs, explicitEnd, gapAfterMs }
 */
export function resolveSegments(tunes, durationMs) {
  const placed = tunes
    .filter((t) => t.segment)
    .map((t) => ({ id: t.session_instance_tune_id, seg: t.segment }))
    .sort((a, b) => a.seg.start_ms - b.seg.start_ms)

  const out = new Map()
  placed.forEach((entry, i) => {
    const next = placed[i + 1]
    const implicitEnd = next ? next.seg.start_ms : durationMs
    const explicit = entry.seg.end_ms != null
    const endMs = explicit ? entry.seg.end_ms : implicitEnd
    out.set(entry.id, {
      startMs: entry.seg.start_ms,
      endMs,
      explicitEnd: explicit,
      // Dead air between this tune's explicit end and the next tune's start.
      // Only meaningful after an explicit end -- otherwise there is none by
      // construction.
      gapAfterMs: explicit && next ? next.seg.start_ms - entry.seg.end_ms : 0,
    })
  })
  return out
}

// How far before a tune's end to hand over to the next one. The playhead is
// sampled once a frame, so without a lead the handover lands a frame LATE and
// the first instant of the gap gets played.
export const HANDOVER_LEAD_MS = 40
// Seek only when the next tune doesn't begin where this one ended. An implicit
// end IS the next start, so the common case is a no-op -- and it must be, since
// seeking on every tune boundary would rebuffer mid-set.
export const CONTIGUOUS_MS = 200

/**
 * One frame of queue playback: given where the playhead is, say what to do.
 *
 * The queue is session_instance_tune_ids in play order. Returns the index that
 * should now be playing, the position to seek to (null = let it run on), and
 * whether the queue is finished. Pure, so the awkward parts -- skipping the dead
 * air between an explicit end and the next tune's start, and the two transport
 * modes -- are testable without an <audio> element.
 *
 * Options:
 *   repeatOne    loop the current tune instead of moving on. Wins over
 *                autoContinue: "repeat this" is the more specific instruction.
 *   autoContinue false stops at the end of the current tune rather than running
 *                into the next one. Defaults true -- the behaviour before there
 *                was a toggle.
 */
export function playbackStep(queue, idx, nowMs, resolved, opts = {}) {
  const lead = opts.leadMs ?? HANDOVER_LEAD_MS
  const contiguous = opts.contiguousMs ?? CONTIGUOUS_MS
  const repeatOne = opts.repeatOne ?? false
  const autoContinue = opts.autoContinue ?? true
  const cur = resolved.get(queue[idx])
  if (!cur) return { idx, seekMs: null, done: true }

  // Still inside this tune. Also covers a playhead that has somehow run BEFORE
  // the current tune (a user scrub), which is not this function's business.
  if (nowMs < cur.endMs - lead) return { idx, seekMs: null, done: false }

  // Loop: back to this tune's own start, never "done". The caller must ignore
  // steps while the element is still seeking, or the stale playhead re-triggers
  // this branch for the frame or two the seek takes to land.
  if (repeatOne) return { idx, seekMs: cur.startMs, done: false }
  if (!autoContinue) return { idx, seekMs: null, done: true }

  const nextIdx = idx + 1
  if (nextIdx >= queue.length) return { idx, seekMs: null, done: true }
  const next = resolved.get(queue[nextIdx])
  if (!next) return { idx, seekMs: null, done: true }

  return {
    idx: nextIdx,
    seekMs: Math.abs(next.startMs - nowMs) > contiguous ? next.startMs : null,
    done: false,
  }
}
