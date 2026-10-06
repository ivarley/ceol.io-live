// spec 056: the weekday nudge behind "Copy to a new year".
import { describe, it, expect } from 'vitest'
import { nudgeToYear, nudgeRange } from '../src/festival/dates.js'

const weekday = (iso) => new Date(`${iso}T00:00:00Z`).getUTCDay()

describe('nudgeRange', () => {
  it('forward a year keeps Thursday to Sunday (the spec example)', () => {
    expect(nudgeRange('2025-10-23', '2025-10-26', 2026)).toEqual({ start: '2026-10-22', end: '2026-10-25' })
  })

  it('back a year', () => {
    expect(nudgeRange('2025-10-23', '2025-10-26', 2024)).toEqual({ start: '2024-10-24', end: '2024-10-27' })
  })

  it('a range across a year boundary keeps its length', () => {
    const r = nudgeRange('2025-12-30', '2026-01-02', 2026)
    expect(r).toEqual({ start: '2026-12-29', end: '2027-01-01' })
    expect(weekday(r.start)).toBe(weekday('2025-12-30'))
  })

  it('a missing last day stays missing', () => {
    expect(nudgeRange('2025-10-23', null, 2026)).toEqual({ start: '2026-10-22', end: null })
  })
})

describe('nudgeToYear', () => {
  it('a leap day to a common year', () => {
    const out = nudgeToYear('2024-02-29', 2025) // a Thursday
    expect(weekday(out)).toBe(weekday('2024-02-29'))
    expect(out).toBe('2025-02-27')
  })

  it('keeps the weekday at a distance, never more than three days off', () => {
    for (const year of [2015, 2019, 2030, 2041]) {
      const out = nudgeToYear('2025-10-23', year)
      expect(weekday(out)).toBe(4)
      const gap = Math.abs(Date.parse(out) - Date.parse(`${year}-10-23`)) / 86400000
      expect(gap).toBeLessThanOrEqual(3)
    }
  })

  it('the same year is unchanged', () => {
    expect(nudgeToYear('2025-10-23', 2025)).toBe('2025-10-23')
  })
})
