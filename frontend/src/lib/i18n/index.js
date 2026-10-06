// The interface language (spec 057): every string a person reads goes through t() or
// tn(), keyed by its English text, with the Irish in ./ga.json. The page carries the
// language in window.__CEOL_LANG__ (templates/base.html, from the profile setting or
// the visitor's switch). The rule (CLAUDE.md): every string exists in both languages,
// and frontend/tests/i18n.test.js fails when one has no Irish entry.
//
// ga.json: { "<English>": { "ga": "<Irish>", "review": true } }. A plural entry's
// "ga" is { one, two, few, many, other } (Irish has five forms) and is keyed by the
// English plural form passed to tn(). "review": true until the Irish is approved.
import ga from './ga.json'

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
