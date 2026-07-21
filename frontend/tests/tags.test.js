// Tag normalization (spec 042) — the client mirror of the server's
// normalize_tags. These rules must stay in lockstep with
// services/person_tune_service.normalize_tags.
import { describe, it, expect } from 'vitest'
import { normalizeTag, normalizeTags, tagsEqual } from '../src/tunesheet/logic.js'

describe('normalizeTag', () => {
  it('trims, lowercases, and hyphenates internal whitespace', () => {
    expect(normalizeTag('Session')).toBe('session')
    expect(normalizeTag('  Reel  ')).toBe('reel')
    expect(normalizeTag('to learn')).toBe('to-learn')
    expect(normalizeTag('spaced   out')).toBe('spaced-out')
  })
  it('keeps # and hyphens, and handles empties', () => {
    expect(normalizeTag('#practice')).toBe('#practice')
    expect(normalizeTag('half-learned')).toBe('half-learned')
    expect(normalizeTag('')).toBe('')
    expect(normalizeTag('   ')).toBe('')
    expect(normalizeTag(null)).toBe('')
    expect(normalizeTag(undefined)).toBe('')
  })
})

describe('normalizeTags', () => {
  it('normalizes each, drops empties, dedupes keeping first-occurrence order', () => {
    expect(normalizeTags(['Session', 'session', 'to learn', '', '#Reel', '#reel'])).toEqual([
      'session',
      'to-learn',
      '#reel',
    ])
  })
  it('is null-safe', () => {
    expect(normalizeTags(null)).toEqual([])
    expect(normalizeTags(undefined)).toEqual([])
    expect(normalizeTags([])).toEqual([])
  })
})

describe('tagsEqual', () => {
  it('is order- and dupe-insensitive', () => {
    expect(tagsEqual(['a', 'b'], ['b', 'a'])).toBe(true)
    expect(tagsEqual(['a', 'a', 'b'], ['a', 'b'])).toBe(true)
    expect(tagsEqual(['A', 'b'], ['a', 'B'])).toBe(true) // normalized before compare
  })
  it('detects real differences', () => {
    expect(tagsEqual(['a'], ['a', 'b'])).toBe(false)
    expect(tagsEqual(['a'], ['b'])).toBe(false)
    expect(tagsEqual([], ['a'])).toBe(false)
  })
})
