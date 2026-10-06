// The interface language (spec 057): every string a person reads goes through t() or
// tn(), keyed by its English text, with the Irish in ./ga.json. The page carries the
// language in window.__CEOL_LANG__ (templates/base.html, from the profile setting or
// the visitor's switch). The rule (CLAUDE.md): every string exists in both languages,
// and frontend/tests/i18n.test.js fails when one has no Irish entry. A converted file
// carries the marker `i18n-converted` in a comment; the test then checks it has no
// English outside t()/tn().
//
// The Irish lives in ./ga/*.json, one file per area of the app (so areas can be
// translated side by side), merged here: { "<English>": { "ga": "<Irish>", "review": true } }.
// A plural entry's "ga" is { one, two, few, many, other } (Irish has five forms) and is
// keyed by the English plural form passed to tn(). "review": true until approved.
// Terms follow specs/current/ui/irish-glossary.md.
const parts = import.meta.glob('./ga/*.json', { eager: true, import: 'default' })
export const ga = Object.assign({}, ...Object.keys(parts).sort().map((k) => parts[k]))

export function currentLang() {
  return typeof window !== 'undefined' && window.__CEOL_LANG__ === 'ga' ? 'ga' : 'en'
}

function fill(text, vars) {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (whole, name) => (name in vars ? String(vars[name]) : whole))
}

/** `text` in the page's language, with {name} placeholders filled from `vars`. */
export function t(text, vars) {
  const entry = currentLang() === 'ga' ? ga[text] : null
  return fill(entry && typeof entry.ga === 'string' && entry.ga ? entry.ga : text, vars)
}

/** Language names, each written in its own language whatever the page's language:
 * the one place in the interface that is deliberately not translated. */
export const LANGUAGE_NAMES = { en: 'English', ga: 'Gaeilge' }

const gaPlurals = typeof Intl !== 'undefined' ? new Intl.PluralRules('ga') : null

/** A count: `one` or `other` in English; in Irish the form Irish uses for `n`.
 * {n} in either form is replaced by the number. */
export function tn(n, one, other, vars) {
  const all = { n, ...(vars || {}) }
  if (currentLang() === 'ga') {
    const forms = ga[other]?.ga
    if (forms && typeof forms === 'object') {
      const form = forms[gaPlurals ? gaPlurals.select(n) : 'other'] || forms.other
      if (form) return fill(form, all)
    }
  }
  return fill(n === 1 ? one : other, all)
}

const LOCALES = { en: 'en-US', ga: 'ga-IE' }

/** Dates and times in the page's language ("Dé hAoine 23 Deireadh Fómhair"). `value`
 * is a Date or an ISO date (yyyy-mm-dd, read as that calendar day, not UTC midnight);
 * `options` are Intl.DateTimeFormat's. */
export function formatDate(value, options) {
  const d = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(Number(value.slice(0, 4)), Number(value.slice(5, 7)) - 1, Number(value.slice(8, 10)))
    : value instanceof Date ? value : new Date(value)
  return new Intl.DateTimeFormat(LOCALES[currentLang()], options).format(d)
}

/** Numbers in the page's language (Irish groups thousands the same way). */
export function formatNumber(n, options) {
  return new Intl.NumberFormat(LOCALES[currentLang()], options).format(n)
}

// Vocabulary the server sends as English values (tune.tune_type, the canonical
// instruments in instruments.py) but which the interface shows as words. Each is a
// literal t() here so the catalog test sees it; anything unknown shows as sent.
const TUNE_TYPES = {
  Barndance: () => t('Barndance'),
  Hornpipe: () => t('Hornpipe'),
  Jig: () => t('Jig'),
  March: () => t('March'),
  Mazurka: () => t('Mazurka'),
  Polka: () => t('Polka'),
  Reel: () => t('Reel'),
  Slide: () => t('Slide'),
  'Slip Jig': () => t('Slip Jig'),
  Strathspey: () => t('Strathspey'),
  'Three-Two': () => t('Three-Two'),
  Waltz: () => t('Waltz'),
  Air: () => t('Air'),
}

/** A tune type ("Reel") as the interface word in the page's language. */
export function tuneTypeName(type) {
  if (!type) return type
  const key = Object.keys(TUNE_TYPES).find((k) => k.toLowerCase() === String(type).toLowerCase())
  return key ? TUNE_TYPES[key]() : type
}

const INSTRUMENTS = {
  Banjo: () => t('Banjo'),
  'Bodhrán': () => t('Bodhrán'),
  Bouzouki: () => t('Bouzouki'),
  'Button Accordion': () => t('Button Accordion'),
  Concertina: () => t('Concertina'),
  Fiddle: () => t('Fiddle'),
  Flute: () => t('Flute'),
  Guitar: () => t('Guitar'),
  Harp: () => t('Harp'),
  'Low Whistle': () => t('Low Whistle'),
  Mandolin: () => t('Mandolin'),
  Piano: () => t('Piano'),
  'Piano Accordion': () => t('Piano Accordion'),
  'Uilleann Pipes': () => t('Uilleann Pipes'),
  Whistle: () => t('Whistle'),
}

/** A canonical instrument name ("Fiddle") in the page's language. */
export function instrumentName(name) {
  if (!name) return name
  const key = Object.keys(INSTRUMENTS).find((k) => k.toLowerCase() === String(name).toLowerCase())
  return key ? INSTRUMENTS[key]() : name
}

