// The notation-search rules shared by every search box in the app. These are mirrored
// in SQL (abc_search_key, schema/055_abc_search_index.sql) and Python (database.py) —
// if they drift, notation search silently stops matching, so the contract is pinned in
// all three. Keep this file in step with tests/unit/test_abc_search.py.
import { describe, it, expect } from 'vitest'
import { ABC_MIN_QUERY_LEN, abcNeedle, looksLikeAbc, normAbc } from '../src/shared/abcquery.js'

describe('normAbc', () => {
  it('drops whitespace', () => {
    expect(normAbc('fdd cAA | B')).toBe('fddcaa|b')
  })

  it('lowercases, so ABC octave case is ignored', () => {
    expect(normAbc('GED')).toBe(normAbc('ged'))
  })

  it('drops grace notes and chord symbols', () => {
    // The reason "AAABc" finds a setting stored as {g}A{d}A{e}A "Am"{g}ABc.
    expect(normAbc('{g}A{d}A{e}A "Am"{g}ABc')).toBe('aaaabc')
  })

  it('drops legacy ! line breaks', () => {
    expect(normAbc('GED!BED')).toBe('gedbed')
  })

  it('handles empty input', () => {
    expect(normAbc('')).toBe('')
    expect(normAbc(null)).toBe('')
    expect(normAbc(undefined)).toBe('')
  })
})

describe('looksLikeAbc', () => {
  it.each(['fdd cAA | B', 'GED', '|:E2BE dEBE:|', '^c3d', '(3EEE'])('accepts %s', (q) => {
    expect(looksLikeAbc(q)).toBe(true)
  })

  it.each(['Drowsy Maggie', 'The Kesh', 'reel', 'silver spear'])('rejects %s', (q) => {
    expect(looksLikeAbc(q)).toBe(false)
  })

  it('accepts note-letter words, and that is fine', () => {
    // "cabbage" is all note letters. Notation matches are BLENDED with name matches and
    // ranked below them, so a false positive costs extra rows, never a wrong answer.
    expect(looksLikeAbc('cabbage')).toBe(true)
  })

  it('rejects a query that normalizes away to nothing', () => {
    expect(looksLikeAbc('"Am"')).toBe(false)
  })
})

describe('abcNeedle', () => {
  it('returns the normalized needle for a qualifying query', () => {
    expect(abcNeedle('fdd cAA | B')).toBe('fddcaa|b')
  })

  it('returns empty for a name query', () => {
    expect(abcNeedle('Drowsy Maggie')).toBe('')
  })

  it('enforces the shared minimum length', () => {
    // Below this a query matches nearly every tune, and pg_trgm cannot use the index.
    expect(ABC_MIN_QUERY_LEN).toBe(3)
    expect(abcNeedle('ab')).toBe('')
    expect(abcNeedle('abc')).toBe('abc')
  })

  it('accepts an explicit lower minimum', () => {
    expect(abcNeedle('ab', 1)).toBe('ab')
  })
})
