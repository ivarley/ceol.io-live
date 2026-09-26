// Notation (ABC) search: is a typed query notes rather than a name, and what does it
// match? These rules are mirrored in three places and MUST agree, or notation search
// silently stops matching:
//
//   - SQL:     abc_search_key()      schema/055_abc_search_index.sql (backs the index)
//   - Python:  abc_query_key() etc.  database.py
//   - Browser: this file
//
// (static/js/offline_data.js carries a hand-copy too — it loads outside every Vite
// bundle. Its comment points here.)

// Blended search needs at least this many normalized characters. Two reasons, and they
// happen to be the same number: shorter queries match almost every tune in the catalog,
// and pg_trgm cannot use the trigram index below 3 characters.
export const ABC_MIN_QUERY_LEN = 3

// Ornaments a player types the notes of but not the notation of: grace notes {...} and
// chord symbols / annotations "...". Dropped from both sides so `{g}A{d}A{e}A {g}ABc`
// is findable by typing `AAABc`.
const ORNAMENT_RE = /\{[^}]*\}|"[^"]*"/g
// Whitespace is meaningless in ABC; '!' is thesession's legacy line break.
const NOISE_RE = /[\s!]/g

// Characters a typed melody can legitimately contain: note letters, rests, durations,
// accidentals (^ _ =), octave marks (' ,), bar/repeat marks, tuplets, ties.
const FRIENDLY_RE = /^[A-Ga-gxz0-9|^_=,'/()[\]:<>~-]+$/

// Normalize a query — or a stored ABC body — the way abc_search_key() does in SQL.
export const normAbc = (s) => (s || '').replace(ORNAMENT_RE, '').replace(NOISE_RE, '').toLowerCase()

// True when the query is plausibly notation rather than a name. Deliberately permissive:
// plenty of real tune names ("Cabbage", "Bee") are made only of note letters. That is
// fine — notation matches are BLENDED with name matches and ranked below them, so a
// false positive costs a few extra rows, never a wrong answer.
export const looksLikeAbc = (q) => {
  const key = normAbc(q)
  return key.length > 0 && FRIENDLY_RE.test(key)
}

// The needle a blended notation search should use, or '' when this query doesn't qualify.
// One call replaces the looksLikeAbc + normAbc + length-check trio at every call site.
export function abcNeedle(q, min = ABC_MIN_QUERY_LEN) {
  const key = normAbc(q)
  return key.length >= min && FRIENDLY_RE.test(key) ? key : ''
}
