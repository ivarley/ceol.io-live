// Pure helpers for the recording segmenter (spec 050). Kept out of the
// components so the fiddly parts -- end resolution, onset snapping, the cursor
// rules -- are unit-testable without a DOM.
//
// Clock formatting and end resolution now live in ../shared/segments.js, because
// the session-instance page plays back what this tool marks and the two must
// resolve a tune's extent identically. Re-exported under the names this page has
// always used.

export { formatClock as formatTime, resolveSegments } from '../shared/segments.js'

export function formatDuration(ms) {
  if (ms == null) return ''
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
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
 * How much of a tune a boundary drag must leave standing.
 *
 * The API refuses end <= start outright; this is the friendlier floor, so a
 * dragged edge stops short of its neighbour instead of being rejected by the
 * server at the end of the gesture.
 */
export const MIN_SEGMENT_MS = 500

/**
 * How far a boundary may be dragged before it would collide with something.
 *
 * `resolved` is the Map from resolveSegments -- resolved ends included, which is
 * what makes an implicit end usable as a limit without special-casing it here.
 * Returns {lo, hi} in ms, or null when the tune isn't placed.
 *
 * The neighbours in play never move during a drag, so these limits are stable
 * for the whole gesture: recomputing them per frame can't walk the edge along
 * in front of the finger.
 */
export function edgeLimits(resolved, id, edge, durationMs) {
  const order = [...resolved.entries()]
    .map(([tuneId, seg]) => ({ id: tuneId, seg }))
    .sort((a, b) => a.seg.startMs - b.seg.startMs)
  const i = order.findIndex((e) => e.id === id)
  if (i < 0) return null
  const me = order[i].seg
  const prev = order[i - 1]
  const next = order[i + 1]

  if (edge === 'end') {
    // Only an EXPLICIT end is its own boundary; an implicit one is the next
    // tune's start, and that start is the handle you get instead.
    return {
      lo: me.startMs + MIN_SEGMENT_MS,
      hi: next ? next.seg.startMs : durationMs,
    }
  }

  return {
    // Backwards: into the gap after the previous tune's explicit end, or into
    // the previous tune itself when its end is implicit -- because then this
    // start IS that end, and dragging it is how you move their shared edge.
    lo: prev ? (prev.seg.explicitEnd ? prev.seg.endMs : prev.seg.startMs + MIN_SEGMENT_MS) : 0,
    // Forwards: never past this tune's own end, wherever that end comes from.
    hi: Math.max(0, (me.explicitEnd ? me.endMs : next ? next.seg.startMs : durationMs) - MIN_SEGMENT_MS),
  }
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
