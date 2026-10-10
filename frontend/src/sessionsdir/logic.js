/* Pure helpers for the sessions directory (spec 052 §B1).
 *
 * These live outside App.svelte so they can be tested against inputs the seeded
 * database does not contain. Every demo session is in the USA, so the "keep a
 * foreign country" half of the location rule is unreachable from an e2e test —
 * it is covered here instead.
 */

// Spellings of one country that sessions arrive with (thesession.org imports say
// "United States", hand-added sessions "USA"). Folded to one key so a USA viewer
// doesn't see "United States" on every imported row. The iOS app keeps the same
// list (CeolLogic/SessionsRules.swift, countryAliases).
import { t } from '../lib/i18n/index.js'

const COUNTRY_ALIASES = {
  us: 'usa',
  'u.s.': 'usa',
  'u.s.a.': 'usa',
  'united states': 'usa',
  'united states of america': 'usa',
  'united kingdom': 'uk',
  'great britain': 'uk',
  'republic of ireland': 'ireland',
  eire: 'ireland',
  '\u00e9ire': 'ireland',
}

/** A country, normalised for comparison: trimmed, lower-cased, spellings folded. */
export function normaliseCountry(country) {
  const key = (country || '').trim().toLowerCase()
  return COUNTRY_ALIASES[key] || key
}

/**
 * The place shown on the right of a session row.
 *
 * The viewer's own country is noise on every row, so it is dropped when it
 * matches: "Austin, TX" to somebody in the USA, but "Galway, Ireland" to that
 * same person. With no country known for the viewer, nothing is dropped —
 * showing too much beats hiding the one fact that placed the session.
 */
export function locationLabel(session, viewerCountry) {
  // The session's town (spec 055): name, area ("Texas"), country.
  const place = session?.place
  const mine = normaliseCountry(viewerCountry)
  const sameCountry = !!mine && normaliseCountry(place?.country) === mine
  const parts = [place?.name, place?.area, sameCountry ? null : place?.country]
  return parts.filter(Boolean).join(', ') || t('Unknown')
}
