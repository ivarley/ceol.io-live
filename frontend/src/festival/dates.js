// Moving a festival's dates to another year (spec 056 "Copy to a new year").
//
// The same calendar dates, nudged to the same weekday: a Thursday-to-Sunday
// festival stays Thursday-to-Sunday. Oct 23-26 2025 (Thu-Sun) -> Oct 22-25 2026,
// and Oct 24-27 2024. Correct in both directions at any distance, where "shift 52
// weeks" drifts a day or two a year. Dates are ISO strings (yyyy-mm-dd) and all the
// arithmetic is in UTC, so no timezone can move a day.

const DAY_MS = 86400000

function parse(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  return { y, m, d }
}

function toIso(date) {
  return date.toISOString().slice(0, 10)
}

function isLeap(year) {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
}

/** `iso` moved to `year`: the same month and day (Feb 29 -> Feb 28 off a leap
 * year), then to the nearest date with the original's weekday (at most 3 away). */
export function nudgeToYear(iso, year) {
  const { y, m, d } = parse(iso)
  const weekday = new Date(Date.UTC(y, m - 1, d)).getUTCDay()
  const day = m === 2 && d === 29 && !isLeap(year) ? 28 : d
  const target = new Date(Date.UTC(year, m - 1, day))
  let shift = weekday - target.getUTCDay()
  if (shift > 3) shift -= 7
  if (shift < -3) shift += 7
  return toIso(new Date(target.getTime() + shift * DAY_MS))
}

/** A first-to-last-day range moved to `year`: the first day nudged, the length
 * kept. A missing last day stays missing. */
export function nudgeRange(start, end, year) {
  if (!start) return { start: null, end: null }
  const newStart = nudgeToYear(start, year)
  if (!end) return { start: newStart, end: null }
  const length = Math.round((Date.parse(end) - Date.parse(start)) / DAY_MS)
  return { start: newStart, end: toIso(new Date(Date.parse(newStart) + length * DAY_MS)) }
}
