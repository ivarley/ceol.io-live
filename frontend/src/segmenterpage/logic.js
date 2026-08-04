// Pure helpers for the recording segmenter (spec 050). Kept out of the
// components so the fiddly parts -- end resolution, onset snapping, the cursor
// rules -- are unit-testable without a DOM.

export function formatTime(ms, { millis = false } = {}) {
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

export function formatDuration(ms) {
  if (ms == null) return ''
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
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

/** Index of the first tune with no segment, at or after `from`. -1 if none. */
export function nextUnplacedIndex(tunes, from = 0) {
  for (let i = Math.max(0, from); i < tunes.length; i++) {
    if (!tunes[i].segment) return i
  }
  return -1
}

/** Tunes grouped into their sets, preserving log order. */
export function groupIntoSets(tunes) {
  const sets = []
  let current = null
  for (const tune of tunes) {
    if (!current || current.setNumber !== tune.set_number) {
      current = { setNumber: tune.set_number, tunes: [] }
      sets.push(current)
    }
    current.tunes.push(tune)
  }
  return sets
}

/**
 * Nudge a mark to the nearest onset -- where the envelope actually rises.
 *
 * Marking by eye lands a bit off, and the training corpus wants the cut on the
 * note. Scans a window around `ms` for the steepest rise measured over ~250ms
 * and moves the mark there, returning `ms` unchanged when nothing in the window
 * looks like an onset (mid-tune marks, applause).
 *
 * The window is deliberately SMALL. It started at +/-1.5s, which was wide enough
 * to walk a carefully-placed mark forward to the next loud phrase inside a tune
 * that had already begun -- snapping confidently past the thing being marked.
 * A correction is all this should ever apply: at +/-500ms it still fixes an
 * eyeball error, but a deliberate placement stays put.
 */
export const SNAP_WINDOW_MS = 500

export function snapToOnset(peaks, peaksHz, ms, windowMs = SNAP_WINDOW_MS) {
  if (!peaks || !peaks.length || !peaksHz) return ms
  const perMs = peaksHz / 1000
  const centre = Math.round(ms * perMs)
  const half = Math.round(windowMs * perMs)
  const lo = Math.max(0, centre - half)
  const hi = Math.min(peaks.length - 1, centre + half)
  if (hi - lo < 4) return ms

  const span = Math.max(2, Math.round(0.25 * peaksHz)) // rise measured over 250ms
  let bestIdx = -1
  let bestRise = 0
  for (let i = lo; i + span <= hi; i++) {
    const rise = peaks[i + span] - peaks[i]
    if (rise > bestRise) {
      bestRise = rise
      bestIdx = i
    }
  }
  // A real tune start climbs hard out of the between-tune murmur. This floor is
  // what keeps a mid-tune mark (where the envelope only wobbles) from sliding.
  if (bestIdx < 0 || bestRise < 25) return ms

  // bestIdx is where the steepest 250ms window BEGINS, which for a sharp attack
  // sits up to 250ms before the note. Walk into the window to the half-way
  // crossing so the mark lands on the rise itself rather than in the quiet
  // before it.
  const midpoint = (peaks[bestIdx] + peaks[bestIdx + span]) / 2
  let onset = bestIdx
  for (let i = bestIdx; i <= bestIdx + span; i++) {
    if (peaks[i] >= midpoint) {
      onset = i
      break
    }
  }
  return Math.round(onset / perMs)
}

/**
 * Reduce the envelope to one bar per pixel column.
 * Returns a Float32Array of 0..1 heights, length `width`.
 */
export function envelopeForRange(peaks, peaksHz, startMs, endMs, width) {
  const out = new Float32Array(Math.max(0, width))
  if (!peaks || !peaks.length || width <= 0) return out
  const perMs = peaksHz / 1000
  const msPerCol = (endMs - startMs) / width
  for (let x = 0; x < width; x++) {
    const a = Math.floor((startMs + x * msPerCol) * perMs)
    const b = Math.floor((startMs + (x + 1) * msPerCol) * perMs)
    let max = 0
    for (let i = Math.max(0, a); i <= Math.min(peaks.length - 1, Math.max(a, b)); i++) {
      if (peaks[i] > max) max = peaks[i]
    }
    out[x] = max / 255
  }
  return out
}

/** Stable per-set colour so adjacent sets read as distinct blocks. */
export function setColor(setNumber, alpha = 1) {
  const hue = (setNumber * 47) % 360
  return `hsla(${hue}, 62%, 55%, ${alpha})`
}

export const SPEEDS = [1, 1.25, 1.5, 2, 2.5, 3]

/** Zoom stops for the detail view, in milliseconds of visible audio. */
export const ZOOM_LEVELS = [5000, 10000, 20000, 40000, 90000, 180000, 480000]
