// Spec 057: the bundles' strings exist in Irish.
//
// - Every t('…') and tn(n, '…', '…') in frontend/src has an entry in one of
//   src/lib/i18n/ga/*.json with its Irish filled in (all five forms for a plural),
//   and no two of those files translate the same English differently.
// - A component carrying the marker `i18n-converted` has no English outside t()/tn():
//   no bare text in its markup, no literal placeholder/title/aria-label/alt.
// A drafted entry with "review": true counts as present.
import { describe, it, expect, afterEach } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { ga, t, tn, tc, formatDate } from '../src/lib/i18n/index.js'

const SRC = join(__dirname, '..', 'src')

// Components whose every user-facing string goes through t()/tn(): those carrying the
// marker. A component gains it when it is converted, and then stays converted.
const MARKER = 'i18n-converted'

const PLURAL_FORMS = ['one', 'two', 'few', 'many', 'other']

function sources(dir = SRC) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.(svelte|js)$/.test(name) && !path.includes('/lib/i18n/') ? [path] : []
  })
}

const STR = String.raw`(['"])((?:\\.|(?!\1).)*?)\1`
const T_CALL = new RegExp(String.raw`(?<![\w.])t\(\s*` + STR, 'g')
const TN_CALL = new RegExp(String.raw`(?<![\w.])tn\(\s*[^,]+,\s*` + STR + String.raw`\s*,\s*` + STR.replace('\\1', '\\3').replace('\\1', '\\3'), 'g')
const unescape = (s) => s.replace(/\\(['"\\])/g, '$1')
const TC_CALL = new RegExp(String.raw`(?<![\w.])tc\(\s*` + STR + String.raw`\s*,\s*` + STR.replace('\\1', '\\3').replace('\\1', '\\3'), 'g')

function used() {
  const singles = new Map()
  const plurals = new Map()
  for (const file of sources()) {
    const text = readFileSync(file, 'utf8')
    const where = relative(SRC, file)
    for (const m of text.matchAll(T_CALL)) singles.set(unescape(m[2]), where)
    for (const m of text.matchAll(TC_CALL)) singles.set(`${unescape(m[2])}|${unescape(m[4])}`, where)
    for (const m of text.matchAll(TN_CALL)) plurals.set(unescape(m[4]), where)
  }
  return { singles, plurals }
}

describe('the Irish catalog (ga.json)', () => {
  const { singles, plurals } = used()

  it('has every t() string', () => {
    const missing = [...singles].filter(([key]) => !(typeof ga[key]?.ga === 'string' && ga[key].ga.trim()))
    expect(missing.map(([key, file]) => `${file}: ${key}`)).toEqual([])
  })

  it('has every tn() plural, in all five Irish forms', () => {
    const missing = [...plurals].filter(([key]) => {
      const forms = ga[key]?.ga
      return !forms || typeof forms !== 'object' || !PLURAL_FORMS.every((f) => forms[f]?.trim())
    })
    expect(missing.map(([key, file]) => `${file}: ${key}`)).toEqual([])
  })

  it('is well formed', () => {
    for (const [key, entry] of Object.entries(ga)) {
      expect(typeof key).toBe('string')
      expect(entry && typeof entry === 'object', key).toBe(true)
      expect(['string', 'object'].includes(typeof entry.ga), key).toBe(true)
      if ('review' in entry) expect(typeof entry.review, key).toBe('boolean')
    }
  })
})

// Text a person would read in a component's markup that isn't inside {…}.
function bareEnglish(source) {
  let s = source
    .replace(/<script[\s\S]*?<\/script>/g, ' ')
    .replace(/<style[\s\S]*?<\/style>/g, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
  const attrs = [...s.matchAll(/\b(?:aria-label|title|placeholder|alt)="([^"{]*[A-Za-z][^"{]*)"/g)].map((m) => m[1])
  // Drop {…} expressions, nesting included, then tags.
  let out = ''
  let depth = 0
  for (const ch of s) {
    if (ch === '{') depth++
    else if (ch === '}') depth = Math.max(0, depth - 1)
    else if (depth === 0) out += ch
  }
  out = out.replace(/<[^>]*>/g, ' ')
  return [...out.split(/\s+/).filter((w) => /[A-Za-z]/.test(w)), ...attrs]
}

const converted = sources()
  .filter((f) => f.endsWith('.svelte') && readFileSync(f, 'utf8').includes(MARKER))
  .map((f) => relative(SRC, f))

describe('converted components', () => {
  it('include the language setting', () => {
    expect(converted).toContain('personpage/LanguageSetting.svelte')
  })

  it.each(converted)('%s has no English outside t()', (path) => {
    expect(bareEnglish(readFileSync(join(SRC, path), 'utf8'))).toEqual([])
  })
})

describe('the catalog files', () => {
  it('never translate the same English two ways', () => {
    const dir = join(SRC, 'lib', 'i18n', 'ga')
    const seen = new Map()
    const clashes = []
    for (const file of readdirSync(dir).filter((f) => f.endsWith('.json')).sort()) {
      const part = JSON.parse(readFileSync(join(dir, file), 'utf8'))
      for (const [key, entry] of Object.entries(part)) {
        const value = JSON.stringify(entry.ga)
        if (seen.has(key) && seen.get(key).value !== value) clashes.push(`${key}: ${seen.get(key).file} vs ${file}`)
        else seen.set(key, { file, value })
      }
    }
    expect(clashes).toEqual([])
  })
})

describe('t() and tn()', () => {
  afterEach(() => {
    delete window.__CEOL_LANG__
  })

  it('English is the key, with placeholders filled', () => {
    expect(t('Language')).toBe('Language')
    expect(t('Hello {name}', { name: 'Ian' })).toBe('Hello Ian')
  })

  it('Irish comes from the catalog', () => {
    window.__CEOL_LANG__ = 'ga'
    expect(t('Language')).toBe('Teanga')
    expect(t('Not in the catalog')).toBe('Not in the catalog')
  })

  it('tc() keeps one English word apart by context', () => {
    expect(tc('area', 'Admin')).toBe('Admin')
    window.__CEOL_LANG__ = 'ga'
    expect(tc('area', 'Admin')).toBe('Riarachán')
    expect(t('Admin')).toBe('Bainisteoir')
  })

  it('formatDate() speaks the page language', () => {
    expect(formatDate('2026-10-23', { weekday: 'long' })).toBe('Friday')
    window.__CEOL_LANG__ = 'ga'
    expect(formatDate('2026-10-23', { weekday: 'long' })).toMatch(/Aoine/)
  })

  it("tn() picks Irish's five forms", () => {
    ga['{n} tunes (test)'] = { ga: { one: '{n} fhonn', two: '{n} fhonn (2)', few: '{n} fhonn (3-6)', many: '{n} bhfonn', other: '{n} fonn' } }
    window.__CEOL_LANG__ = 'ga'
    expect([1, 2, 3, 7, 11, 20].map((n) => tn(n, '{n} tune', '{n} tunes (test)'))).toEqual([
      '1 fhonn', '2 fhonn (2)', '3 fhonn (3-6)', '7 bhfonn', '11 fonn', '20 fonn',
    ])
    delete window.__CEOL_LANG__
    expect(tn(1, '{n} tune', '{n} tunes (test)')).toBe('1 tune')
    expect(tn(2, '{n} tune', '{n} tunes (test)')).toBe('2 tunes (test)')
    delete ga['{n} tunes (test)']
  })
})
