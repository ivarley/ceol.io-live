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
