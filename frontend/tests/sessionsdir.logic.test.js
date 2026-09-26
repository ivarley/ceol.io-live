import { describe, it, expect } from 'vitest'
import { locationLabel, normaliseCountry } from '../src/sessionsdir/logic.js'

const austin = { city: 'Austin', state: 'TX', country: 'USA' }
const galway = { city: 'Galway', state: 'Galway', country: 'Ireland' }

describe('locationLabel', () => {
  it('drops the country when it is the viewer’s own', () => {
    expect(locationLabel(austin, 'USA')).toBe('Austin, TX')
  })

  it('keeps a foreign country, because that is the fact that places the session', () => {
    // Unreachable from e2e: the seeded database is entirely American.
    expect(locationLabel(galway, 'USA')).toBe('Galway, Galway, Ireland')
  })

  it('shows everything when the viewer has no country set', () => {
    expect(locationLabel(austin, '')).toBe('Austin, TX, USA')
    expect(locationLabel(austin, null)).toBe('Austin, TX, USA')
  })

  it('compares countries case- and whitespace-insensitively', () => {
    expect(locationLabel({ ...austin, country: ' usa ' }, 'USA')).toBe('Austin, TX')
    expect(locationLabel(austin, ' usa ')).toBe('Austin, TX')
  })

  it('omits parts the session does not have', () => {
    expect(locationLabel({ city: 'Doolin', country: 'Ireland' }, 'USA')).toBe('Doolin, Ireland')
    expect(locationLabel({ country: 'USA' }, 'USA')).toBe('Unknown')
  })

  it('says Unknown rather than an empty cell when nothing is known', () => {
    expect(locationLabel({}, 'USA')).toBe('Unknown')
    expect(locationLabel(null, 'USA')).toBe('Unknown')
  })
})

describe('normaliseCountry', () => {
  it('folds case and trims', () => {
    expect(normaliseCountry('  Ireland ')).toBe('ireland')
  })

  it('treats missing as empty', () => {
    expect(normaliseCountry(undefined)).toBe('')
    expect(normaliseCountry(null)).toBe('')
  })
})
