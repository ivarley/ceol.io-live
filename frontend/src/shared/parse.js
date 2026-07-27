// Shared input-parsing helpers (kit-adoption follow-up to spec 035). One tested
// copy replaces the per-bundle duplicates in mytunespage/sessionpage/
// sessionadminpage logic.js — semantics are exactly the legacy ones.

/**
 * Extract a tune ID from a bare number or a thesession.org tune URL
 * ("123", "https://thesession.org/tunes/123?setting=456"); null otherwise.
 */
export function extractTuneId(input) {
  if (!input) return null
  const trimmed = input.trim()
  if (/^\d+$/.test(trimmed)) return parseInt(trimmed, 10)
  const urlMatch = trimmed.match(/thesession\.org\/tunes\/(\d+)/i)
  if (urlMatch) return parseInt(urlMatch[1], 10)
  return null
}

// --- thesession.org id parsing (spec 026/028; moved here from logstate.js so the
// tunesheet/mytunes bundles can share it — logstate re-exports for its consumers).

/**
 * Detect a thesession.org tune URL or bare numeric id -> its integer id, else null.
 * Mirrors the server's _parse_thesession_id. Used by every paste-a-URL entry point:
 * the composer's paste detection, the deep search's field + paste box, and the
 * hamburger "Find a tune" overlay.
 */
export function parseThesessionId(raw) {
  if (raw == null) return null
  const s = String(raw).trim()
  const m = s.match(/thesession\.org\/tunes\/(\d+)/)
  if (m) return parseInt(m[1], 10)
  return /^\d+$/.test(s) ? parseInt(s, 10) : null
}

/**
 * The SESSION sibling of parseThesessionId: a thesession.org *session* URL
 * (/sessions/<id>) or a bare numeric id -> its integer id, else null. Sessions and
 * tunes both live under thesession.org with numeric ids, so keep the two parsers
 * apart — a tune URL must not pass as a session id, or a session ends up linked to
 * a tune's page. Mirrors the server's _parse_thesession_session_id.
 */
export function parseThesessionSessionId(raw) {
  if (raw == null) return null
  const s = String(raw).trim()
  const m = s.match(/thesession\.org\/sessions\/(\d+)/)
  if (m) return parseInt(m[1], 10)
  return /^\d+$/.test(s) ? parseInt(s, 10) : null
}

/**
 * The optional setting deep-link in a thesession tune URL — ?setting=NNN and/or
 * #settingNNN (thesession uses both, e.g. /tunes/1716?setting=15143#setting15143).
 * Only meaningful alongside a URL; a bare numeric id carries no setting.
 */
export function parseThesessionSettingId(raw) {
  if (raw == null) return null
  const s = String(raw).trim()
  if (!s.includes('thesession.org')) return null
  const qm = s.match(/[?&]setting=(\d+)/)
  if (qm) return parseInt(qm[1], 10)
  const hm = s.match(/#setting(\d+)/)
  return hm ? parseInt(hm[1], 10) : null
}

/**
 * Parse a payload date as a LOCAL date. Date-only strings ("2026-01-27", the
 * shape serializers emit for DATE columns) hit the Date(y, m, d) constructor —
 * `new Date("2026-01-27")` is UTC midnight, which renders as the PREVIOUS day
 * anywhere west of UTC. Anything else (timestamps, Date objects) passes through
 * to `new Date(value)` unchanged.
 */
export function parseLocalDate(value) {
  if (typeof value === 'string') {
    const m = value.match(/^(\d{4})-(\d{2})-(\d{2})$/)
    if (m) return new Date(+m[1], +m[2] - 1, +m[3])
  }
  return new Date(value)
}

/**
 * Normalize smart quotes to straight quotes (iOS keyboard compatibility).
 * NB: the smart-quote characters are \u-escaped on purpose — never write the
 * literals in source (see the normalize_apostrophes incident).
 */
export function normalizeQuotes(str) {
  return str
    .replace(/[\u2018\u2019]/g, "'") // Smart single quotes -> straight
    .replace(/[\u201C\u201D]/g, '"') // Smart double quotes -> straight
}
