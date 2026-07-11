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
 * Normalize smart quotes to straight quotes (iOS keyboard compatibility).
 * NB: the smart-quote characters are \u-escaped on purpose — never write the
 * literals in source (see the normalize_apostrophes incident).
 */
export function normalizeQuotes(str) {
  return str
    .replace(/[\u2018\u2019]/g, "'") // Smart single quotes -> straight
    .replace(/[\u201C\u201D]/g, '"') // Smart double quotes -> straight
}
