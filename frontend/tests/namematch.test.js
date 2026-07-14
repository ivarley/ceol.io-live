import { describe, it, expect } from 'vitest'
import {
  sameName,
  meaningfullyDiffers,
  normalizeName,
  normalizeNameOrdered,
  digitRuns,
  diceCoefficient,
  pickAka,
  DICE_THRESHOLD,
} from '../src/tunesheet/namematch.js'
import fixtures from '../src/tunesheet/namematch.fixtures.json'

// The matcher decides whether the drawer's `aka` subtitle is worth showing.
// See namematch.fixtures.json for how the labelled set was built and why the two
// error types get different bars.

describe('normalizeName', () => {
  it('strips articles, punctuation, type words and possessives', () => {
    expect(normalizeName('The Silver Spear')).toBe(normalizeName('Silver Spear'))
    expect(normalizeName("Cooley's Reel")).toBe(normalizeName('Cooley'))
    expect(normalizeName('Butterfly, The')).toBe(normalizeName('The Butterfly'))
  })

  it('folds diacritics rather than deleting them', () => {
    // The bug this guards: a naive [^a-z0-9] strip DELETES 'É' instead of folding
    // it, so every accented Irish title diverges from its unaccented spelling.
    expect(normalizeName('Éirinn')).toBe(normalizeName('Eirinn'))
    expect(normalizeName('Laridé')).toBe(normalizeName('Laride'))
  })

  it('folds the U+2019 smart quote, which is what thesession.org actually stores', () => {
    expect(normalizeName('The Swallow’s Tail')).toBe(normalizeName("The Swallow's Tail"))
  })

  it('sorts tokens so word order carries no identity', () => {
    expect(normalizeName('Maggie Drowsy')).toBe(normalizeName('Drowsy Maggie'))
  })
})

describe('compound splits', () => {
  // De-spacing is what collapses "Rye Grass" into "Ryegrass" — but only in the
  // ORDERED form, since sorting shuffles the halves of a split compound apart
  // ("Rye Grass" sorts to gras|rye). The prefix rule reads the ordered form, so
  // this is where compound-splitting actually pays off.
  it('collapse in the ordered form', () => {
    expect(normalizeNameOrdered('Ryegrass')).toBe(normalizeNameOrdered('Rye Grass'))
    expect(normalizeNameOrdered('Connachtman')).toBe(normalizeNameOrdered('Connacht Man'))
  })

  it('and that is enough for sameName', () => {
    expect(sameName('Rolling In The Ryegrass', 'Rolling In The Rye Grass')).toBe(true)
    expect(sameName('The Swallowtail', "The Swallow's Tail")).toBe(true)
  })
})

describe('sameName — the parenthetical guard', () => {
  it('keeps a bracketed aside significant, even against the prefix rule', () => {
    expect(sameName("The Silver Spear (Kevin's)", 'The Silver Spear')).toBe(false)
    expect(sameName('The Kesh (slow)', 'The Kesh (fast)')).toBe(false)
  })

  it('but two names with the SAME aside still match', () => {
    expect(sameName("Silver Spear (Kevin's)", "The Silver Spear (Kevin's)")).toBe(true)
  })
})

describe('normalizeNameOrdered', () => {
  it('keeps word order — this is what the prefix test runs on', () => {
    expect(normalizeNameOrdered('Drowsy Maggie')).not.toBe(normalizeNameOrdered('Maggie Drowsy'))
  })

  it('is why a shared token cannot masquerade as a prefix', () => {
    // Sorted, "collins" floats to the front of both and would "prefix" the longer
    // name. Ordered, it cannot. This is the false-collapse the ordered form exists
    // to prevent.
    const short = normalizeNameOrdered("Collins'")
    const long = normalizeNameOrdered("Daniel Michael Collins's Father's")
    expect(long.startsWith(short)).toBe(false)
  })
})

describe('digitRuns', () => {
  it('extracts numbers, normalized', () => {
    expect(digitRuns("Paddy Fahey's No. 3")).toEqual(['3'])
    expect(digitRuns('Brosna #2, The')).toEqual(['2'])
    expect(digitRuns('The Kesh')).toEqual([])
  })
})

describe('diceCoefficient', () => {
  it('is 1 for identical and 0 for disjoint', () => {
    expect(diceCoefficient('abcd', 'abcd')).toBe(1)
    expect(diceCoefficient('abcd', 'wxyz')).toBe(0)
  })
})

describe('sameName — the digit guard', () => {
  it('overrides the prefix rule', () => {
    // "paddyfahey" IS a prefix of "paddyfaheyno3". Numbers win anyway.
    expect(sameName("Paddy Fahey's", "Paddy Fahey's No. 3")).toBe(false)
  })

  it('overrides a high similarity score', () => {
    const a = normalizeName("Paddy Fahey's No. 2")
    const b = normalizeName("Paddy Fahey's No. 3")
    expect(diceCoefficient(a, b)).toBeGreaterThan(DICE_THRESHOLD)
    expect(sameName("Paddy Fahey's No. 2", "Paddy Fahey's No. 3")).toBe(false)
  })
})

describe('sameName — identical strings', () => {
  it('is true even though the same name belongs to several different tunes', () => {
    // "O'Keefe's" names several unrelated tunes. That is not this function's problem:
    // it answers "are these the same NAME", and in the product it only ever compares
    // names belonging to a single tune_id.
    expect(sameName("O'Keefe's", "O'Keefe's")).toBe(true)
  })

  it('is false for empty input', () => {
    expect(sameName('', 'The Kesh')).toBe(false)
    expect(sameName(null, undefined)).toBe(false)
  })
})

describe('the labelled calibration set', () => {
  // Bar 1: a spurious `aka The Silver Spear` is a papercut. >= 95%.
  it('suppresses at least 95% of true spelling variants', () => {
    const misses = fixtures.variants.filter((p) => !sameName(p.a, p.b))
    const rate = (fixtures.variants.length - misses.length) / fixtures.variants.length
    expect(
      misses.map((m) => `${m.a} || ${m.b}  (${m.why})`),
      `variant pass rate ${(rate * 100).toFixed(1)}%`
    ).toEqual([])
    expect(rate).toBeGreaterThanOrEqual(0.95)
  })

  // Bar 2: collapsing a genuinely different name HIDES it from the user, which
  // defeats the feature. Zero tolerance — no percentage, no exceptions.
  it('never collapses a genuinely different name', () => {
    const collapsed = fixtures.distinct.filter((p) => sameName(p.a, p.b))
    expect(collapsed.map((c) => `${c.a} || ${c.b}  (${c.why})`)).toEqual([])
  })
})

describe('pickAka', () => {
  // chain is most-personal-first: [mine, instance, session, global]
  it('returns the first name below the title that meaningfully differs', () => {
    expect(pickAka(['The Burren', null, "Michael Creamer's", "Michael Creamer's Favourite"])).toBe(
      "Michael Creamer's"
    )
  })

  it('walks past layers that are only spelling variants of the title', () => {
    // Session calls it the same thing I do (bar an article), so the walk skips it
    // and surfaces the genuinely different global name.
    expect(pickAka(['The Burren', null, 'Burren', "Michael Creamer's"])).toBe("Michael Creamer's")
  })

  it('returns null when nothing below the title meaningfully differs', () => {
    expect(pickAka(['The Silver Spear', null, 'Silver Spear', 'The Silver Spear'])).toBeNull()
  })

  it('takes the title from the first non-empty layer', () => {
    // No personal alias: the instance name becomes the title, and the walk starts below it.
    expect(pickAka([null, 'Silver Spear (fast one)', null, 'The Silver Spear'])).toBe('The Silver Spear')
  })

  it('returns null for an empty chain', () => {
    expect(pickAka([null, null, null, null])).toBeNull()
    expect(pickAka([])).toBeNull()
  })

  it('meaningfullyDiffers is the inverse of sameName', () => {
    expect(meaningfullyDiffers('The Kesh', 'The Castle')).toBe(true)
    expect(meaningfullyDiffers('The Kesh', 'Kesh')).toBe(false)
  })
})
