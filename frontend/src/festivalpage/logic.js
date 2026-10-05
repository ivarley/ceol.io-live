// Pure formatting for the festival picker (spec 056).

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function parts(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  return { y, m, d }
}

/** "Oct 23 – 26, 2025", "Dec 30, 2025 – Jan 2, 2026", "Oct 23, 2025", or "" with
 * no first day. ISO strings in, no timezone involved. */
export function formatRange(start, end) {
  if (!start) return ''
  const a = parts(start)
  const one = (p, withYear) => `${MONTHS[p.m - 1]} ${p.d}${withYear ? `, ${p.y}` : ''}`
  if (!end || end === start) return one(a, true)
  const b = parts(end)
  if (a.y !== b.y) return `${one(a, true)} – ${one(b, true)}`
  if (a.m !== b.m) return `${one(a, false)} – ${one(b, false)}, ${a.y}`
  return `${MONTHS[a.m - 1]} ${a.d} – ${b.d}, ${a.y}`
}
