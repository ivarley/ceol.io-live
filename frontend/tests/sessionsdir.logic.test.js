import { describe, it, expect } from 'vitest'
import { locationLabel, normaliseCountry } from '../src/sessionsdir/logic.js'

// A session's place (spec 055): its town's name, area and country.
const at = (name, area, country) => ({ place: { name, area, country } })
const austin = at('Austin', 'TX', 'USA')
const galway = at('Galway', 'Galway', 'Ireland')

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
    expect(locationLabel(at('Austin', 'TX', ' usa '), 'USA')).toBe('Austin, TX')
    expect(locationLabel(austin, ' usa ')).toBe('Austin, TX')
  })

  it('omits parts the session does not have', () => {
    expect(locationLabel(at('Doolin', null, 'Ireland'), 'USA')).toBe('Doolin, Ireland')
    expect(locationLabel(at(null, null, 'USA'), 'USA')).toBe('Unknown')
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

  it('folds the spellings of one country', () => {
    expect(normaliseCountry('United States')).toBe('usa')
    expect(normaliseCountry('USA')).toBe('usa')
    expect(normaliseCountry('Republic of Ireland')).toBe('ireland')
    expect(locationLabel(at('Memphis', 'Tennessee', 'United States'), 'USA')).toBe('Memphis, Tennessee')
  })

  it('treats missing as empty', () => {
    expect(normaliseCountry(undefined)).toBe('')
    expect(normaliseCountry(null)).toBe('')
  })
})
