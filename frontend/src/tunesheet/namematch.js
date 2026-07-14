// Tune-name matching (spec 037) — "are these two strings the same name?"
//
// This exists for ONE job: deciding whether the drawer's `aka` subtitle is worth
// showing. The title is the most personal name for a tune; the subtitle names the
// next layer down that MEANINGFULLY differs. Without this we'd print things like
//
//     The Silver Spear
//     aka Silver Spear
//
// which is noise. So the bar is deliberately aggressive: we're not renaming
// anything, only deciding whether a more general alias is worth a line of UI.
//
// What it is NOT: a judgment about whether two *tunes* are the same tune. The same
// name legitimately belongs to several different tunes ("O'Keefe's"), and in the
// product this never comes up anyway — the drawer only ever compares names that all
// belong to one tune_id.
//
// The two errors are not equally bad. Saying "different" when they're really the
// same spelling variant costs a pointless `aka` line (a papercut). Saying "same"
// when they're genuinely different names HIDES from you that the tune has another
// name, which defeats the feature. So the tests hold zero tolerance for the second
// and ~95% for the first. See namematch.fixtures.json and scripts/build_name_fixtures.py.

// Tune-type words. A trailing one is decoration, not identity: "Cooley's Reel" is
// "Cooley's". Multi-word types first so the longest match wins.
const TYPE_WORDS = [
  'slip jig',
  'set dance',
  'hop jig',
  'barndance',
  'hornpipe',
  'strathspey',
  'mazurka',
  'polka',
  'schottische',
  'hornpipes',
  'march',
  'slide',
  'waltz',
  'reel',
  'jig',
]

// Trailing decoration beyond the tune type. "Paddy Fahey's Favourite" is "Paddy Fahey's".
const TRAILING_NOISE = ['favourite', 'favorite', 'fancy', 'delight']

// Spelling substitutions, applied to the de-spaced "meat" string.
//
// MINIMAL BY POLICY: an entry is only ever added because a real labelled pair in the
// fixture set fails without it. Never add one speculatively — every entry is a chance
// to collapse two names that really are different.
//
// These are canonicalizations, not corrections: they're applied identically to both
// sides, so a mangling ("four" -> "for") is harmless as long as it's consistent.
const SUBSTITUTIONS = [
  // Connacht / Connaught / Connaght / Connachtmann — one place, a dozen spellings.
  [/conn(?:aught|aght|acht)/g, 'connacht'],
  [/connachtmann/g, 'connachtman'],
  // British/American -our-/-or-: favour/favor, humour/humor, honour/honor.
  [/our/g, 'or'],
  // -ise/-ize.
  [/ise/g, 'ize'],
  // Doubled consonants that vary freely in transliterated Irish names.
  [/([bcdfgklmnprstz])\1/g, '$1'],
]

/** Digit runs in a name, in order. Two names whose numbers differ are ALWAYS different. */
export function digitRuns(name) {
  return (String(name || '').match(/\d+/g) || []).map((d) => String(parseInt(d, 10)))
}

/**
 * Bracketed asides — "The Silver Spear (Kevin's)". Like numbering, a parenthetical is
 * a DELIBERATE disambiguation, so two names whose parentheticals differ are always
 * different. Without this guard the prefix rule ("a short form of a longer name")
 * would happily swallow "The Silver Spear (Kevin's)" into "The Silver Spear", which
 * is exactly the distinction the parenthetical was added to draw.
 */
export function parentheticals(name) {
  const found = String(name || '').match(/[([{][^)\]}]*[)\]}]/g) || []
  return found
    .map((p) => p.replace(/[^a-zA-Z0-9]+/g, '').toLowerCase())
    .filter(Boolean)
    .sort()
}

/**
 * Reduce a tune name to its "meat" tokens: lowercase, unpunctuated, de-articled,
 * de-pluralized, de-typed, spelling-normalized.
 *
 * The caller joins these two ways, and the difference matters:
 *   - ORDERED (word order kept) is what the prefix test runs on. Sorting first
 *     would let a short shared token float to the front and "prefix" anything that
 *     happens to contain it — "Collins'" would swallow "Daniel Michael Collins's
 *     Father's", which is a genuinely different name.
 *   - SORTED is what the similarity test runs on, so a reordered title
 *     ("Maggie Drowsy" / "Drowsy Maggie") doesn't earn an `aka`.
 *
 * Both are de-spaced, which is what collapses compound splits: "Connacht Man" and
 * "Connachtman" land on the same string.
 */
function meatTokens(name) {
  let s = String(name || '').toLowerCase()

  // Fold diacritics BEFORE stripping punctuation, or accented letters get deleted
  // rather than folded and every Irish title diverges from its unaccented spelling:
  // "Is Ar Eirinn Ni Neosfainn Ce Hi" vs "Is Ar Éirinn Ní Neosfainn Cé Hí".
  s = s.normalize('NFD').replace(/[̀-ͯ]/g, '')

  // Apostrophes: the ASCII one, and U+2019, which is what thesession.org actually
  // stores. Written \u-escaped on purpose — a previous normalizer in this codebase
  // was silently a no-op because a smart quote got mangled in source.
  s = s.replace(/[’ʼ`´']/g, '')

  // Everything that isn't a letter, a digit, or a space becomes a space.
  s = s.replace(/[^a-z0-9]+/g, ' ').replace(/\s+/g, ' ').trim()

  // Leading "the", and the trailing ", the" form (the comma is already gone).
  s = s.replace(/^the\s+/, '')
  s = s.replace(/\s+the$/, '')

  // Peel trailing decoration until nothing peels: types and noise words can stack
  // ("Paddy Fahey's Favourite Reel"). Never peel down to nothing.
  let peeled = true
  while (peeled) {
    peeled = false
    for (const w of [...TYPE_WORDS, ...TRAILING_NOISE]) {
      const suffix = ' ' + w
      if (s.endsWith(suffix) && s.length > suffix.length) {
        s = s.slice(0, -suffix.length).trim()
        peeled = true
        break
      }
    }
  }

  const canon = (t) => {
    let x = t
    for (const [pattern, replacement] of SUBSTITUTIONS) {
      x = x.replace(pattern, replacement)
    }
    return x
  }

  return s
    .split(' ')
    .filter(Boolean)
    // Trailing "s" on EVERY token, not just the last — this is what makes
    // "swallow's tail" / "swallow tail" / "swallows tail" agree. Short tokens are
    // left alone so "is"/"as" don't erode to a single letter.
    .map((t) => (t.length > 2 ? t.replace(/s$/, '') : t))
    // Token-final -y / -ie / -ey all spell the same sound and vary freely in
    // transcribed titles: Drowsy / Drowsie / Drowsey, Maggie / Maggy.
    .map((t) => (t.length > 2 ? t.replace(/(?:ey|ie|y)$/, 'i') : t))
    .map(canon)
    .filter(Boolean)
}

/** The prefix form: word order preserved. */
export function normalizeNameOrdered(name) {
  return meatTokens(name).join('')
}

/** The similarity form: tokens sorted, so word order carries no identity. */
export function normalizeName(name) {
  return [...meatTokens(name)].sort().join('')
}

/** Dice coefficient over character bigrams. 1 = identical, 0 = nothing in common. */
export function diceCoefficient(a, b) {
  if (a === b) return 1
  if (a.length < 2 || b.length < 2) return 0

  const bigrams = new Map()
  for (let i = 0; i < a.length - 1; i++) {
    const g = a.slice(i, i + 2)
    bigrams.set(g, (bigrams.get(g) || 0) + 1)
  }
  let hits = 0
  for (let i = 0; i < b.length - 1; i++) {
    const g = b.slice(i, i + 2)
    const n = bigrams.get(g) || 0
    if (n > 0) {
      bigrams.set(g, n - 1)
      hits++
    }
  }
  return (2 * hits) / (a.length - 1 + (b.length - 1))
}

// Tuned against the labelled fixture set; see namematch.test.js.
export const DICE_THRESHOLD = 0.8
// Below this, a "prefix" is meaningless — every string starts with something short.
const MIN_PREFIX_LEN = 5

/**
 * Are these two names the same name? (Not: are they the same tune.)
 *
 * Same if the normalized forms are equal, or one is a prefix of the other (a name
 * that drops a trailing word — "Connaughtman's" vs "Connaughtman's Rambles"), or
 * they're close enough by bigram overlap (a name that drops an INTERIOR word —
 * "Connaught Rambles" vs "Connaughtman's Rambles"), which no rule can catch.
 *
 * Overridden in every case by the digit guard: "Paddy Fahey's" and "Paddy Fahey's
 * No. 3" are prefixes of one another and are emphatically not the same tune.
 */
export function sameName(a, b) {
  const rawA = String(a || '').trim()
  const rawB = String(b || '').trim()
  if (!rawA || !rawB) return false
  if (rawA === rawB) return true

  // The two hard guards. Both mark a DELIBERATE distinction, so both outrank every
  // similarity rule below — including prefix, which would otherwise treat the
  // undecorated name as "a short form of" the decorated one.
  if (digitRuns(rawA).join(',') !== digitRuns(rawB).join(',')) return false
  if (parentheticals(rawA).join(',') !== parentheticals(rawB).join(',')) return false

  const na = normalizeName(rawA)
  const nb = normalizeName(rawB)
  if (!na || !nb) return rawA.toLowerCase() === rawB.toLowerCase()
  if (na === nb) return true

  // Prefix on the ORDERED form: a short form of a longer name ("Connaughtman's" /
  // "The Connaughtman's Rambles"). Testing this on the sorted form instead would
  // collapse names that merely share a word.
  const oa = normalizeNameOrdered(rawA)
  const ob = normalizeNameOrdered(rawB)
  const shortO = oa.length <= ob.length ? oa : ob
  const longO = oa.length <= ob.length ? ob : oa
  if (shortO.length >= MIN_PREFIX_LEN && longO.startsWith(shortO)) return true

  // Similarity on the sorted form: catches a name that drops an INTERIOR word
  // ("Connaught Rambles" / "Connaughtman's Rambles"), which no rule can.
  return diceCoefficient(na, nb) >= DICE_THRESHOLD
}

/** The inverse, named for how the drawer reads. */
export function meaningfullyDiffers(a, b) {
  return !sameName(a, b)
}

/**
 * The `aka` line: walk DOWN the name chain from the title and return the first name
 * that meaningfully differs from it. Exactly one, or null.
 *
 * `chain` is most-personal-first — [mine, instance, session, global] — with nulls for
 * the layers that don't apply. The title is the first non-empty entry; the candidates
 * are everything below it.
 */
export function pickAka(chain) {
  const names = (chain || []).map((n) => (n == null ? '' : String(n).trim()))
  const titleIdx = names.findIndex((n) => n !== '')
  if (titleIdx === -1) return null
  const title = names[titleIdx]

  for (let i = titleIdx + 1; i < names.length; i++) {
    const candidate = names[i]
    if (candidate && meaningfullyDiffers(title, candidate)) return candidate
  }
  return null
}
