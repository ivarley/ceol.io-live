// Pure formatting for the festival picker (spec 056).
import { currentLang, formatDate } from '../lib/i18n/index.js'

function parts(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  return { y, m, d }
}

/** "Oct 23 – 26, 2025", "Dec 30, 2025 – Jan 2, 2026", "Oct 23, 2025", or "" with
 * no first day; in Irish day first ("23 – 26 DFómh 2025"). ISO strings in, no
 * timezone involved (formatDate reads yyyy-mm-dd as that calendar day). */
export function formatRange(start, end) {
  if (!start) return ''
  const a = parts(start)
  const month = (iso) => formatDate(iso, { month: 'short' })
  if (currentLang() === 'ga') {
    const one = (iso, withYear) => formatDate(iso, withYear
      ? { day: 'numeric', month: 'short', year: 'numeric' }
      : { day: 'numeric', month: 'short' })
    if (!end || end === start) return one(start, true)
    const b = parts(end)
    if (a.y !== b.y) return `${one(start, true)} – ${one(end, true)}`
    if (a.m !== b.m) return `${one(start, false)} – ${one(end, true)}`
    return `${a.d} – ${one(end, true)}`
  }
  const one = (iso, p, withYear) => `${month(iso)} ${p.d}${withYear ? `, ${p.y}` : ''}`
  if (!end || end === start) return one(start, a, true)
  const b = parts(end)
  if (a.y !== b.y) return `${one(start, a, true)} – ${one(end, b, true)}`
  if (a.m !== b.m) return `${one(start, a, false)} – ${one(end, b, false)}, ${a.y}`
  return `${month(start)} ${a.d} – ${b.d}, ${a.y}`
}
