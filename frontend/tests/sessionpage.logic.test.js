// Pure-logic tests for the session-detail page port (spec 035 Step 4b).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { extractTuneId, normalizeQuotes } from '../src/shared/parse.js'
import { formatTime } from '../src/shared/format.js'
import {
  sortFunctions,
  filterAndSortTunes,
  resultsCountLabel,
  stateFromParams,
  applyStateToParams,
  basePathOf,
  instanceTimeLabel,
  isEmptyLog,
  instanceUrlId,
  parseTheSessionId,
  filterPeople,
} from '../src/sessionpage/logic.js'

const tune = (id, name, type, plays, tunebook) => ({
  tune_id: id,
  tune_name: name,
  tune_type: type,
  play_count: plays,
  tunebook_count: tunebook,
  setting_id: null,
})

describe('extractTuneId', () => {
  it('parses bare ids and thesession URLs, rejects names', () => {
    expect(extractTuneId('123')).toBe(123)
    expect(extractTuneId(' 45 ')).toBe(45)
    expect(extractTuneId('https://thesession.org/tunes/678#setting1')).toBe(678)
    expect(extractTuneId("Cooley's")).toBeNull()
    expect(extractTuneId('')).toBeNull()
  })
})

describe('sortFunctions', () => {
  const tunes = [tune(1, 'Banish', 'jig', 5, 100), tune(2, 'Ashplant', 'reel', 9, 50)]
  it('alpha sorts by name', () => {
    expect([...tunes].sort(sortFunctions.alpha.asc)[0].tune_name).toBe('Ashplant')
    expect([...tunes].sort(sortFunctions.alpha.desc)[0].tune_name).toBe('Banish')
  })
  it('session sorts by play_count, everywhere by tunebook_count', () => {
    expect([...tunes].sort(sortFunctions.session.desc)[0].tune_id).toBe(2)
    expect([...tunes].sort(sortFunctions.everywhere.desc)[0].tune_id).toBe(1)
  })
})

describe('filterAndSortTunes', () => {
  const tunes = [
    tune(101, "Cooley's", 'reel', 5, 900),
    tune(102, 'Banish Misfortune', 'jig', 2, 300),
    tune(103, 'The Ashplant', 'reel', 9, 100),
  ]
  const noFilters = { search: '', type: '', mystatus: '' }
  const sessionDesc = { type: 'session', dir: 'desc' }

  it('no filters: sorted by play count desc', () => {
    const out = filterAndSortTunes(tunes, noFilters, sessionDesc, 'all')
    expect(out.map((t) => t.tune_id)).toEqual([103, 101, 102])
  })

  it('search matches names (fallback matcher) and tune ids', () => {
    expect(
      filterAndSortTunes(tunes, { ...noFilters, search: 'banish' }, sessionDesc, 'all').map((t) => t.tune_id)
    ).toEqual([102])
    expect(
      filterAndSortTunes(tunes, { ...noFilters, search: '101' }, sessionDesc, 'all').map((t) => t.tune_id)
    ).toEqual([101])
  })

  it('type filter narrows to one tune type', () => {
    expect(
      filterAndSortTunes(tunes, { ...noFilters, type: 'reel' }, sessionDesc, 'all').map((t) => t.tune_id)
    ).toEqual([103, 101])
  })

  describe('my-tunebook status filter', () => {
    beforeEach(() => {
      window.TunebookStatus = {
        isLoaded: () => true,
        statusFor: (id) => (id === 101 ? 'learned' : 'not on list'),
        classFor: (st) => 'ls-' + st.replace(/ /g, '-'),
        getInstruments: () => [],
      }
    })
    afterEach(() => {
      delete window.TunebookStatus
    })
    it("'all' colors without filtering; a status filters", () => {
      expect(filterAndSortTunes(tunes, { ...noFilters, mystatus: 'all' }, sessionDesc, 'all')).toHaveLength(3)
      expect(
        filterAndSortTunes(tunes, { ...noFilters, mystatus: 'learned' }, sessionDesc, 'all').map((t) => t.tune_id)
      ).toEqual([101])
    })
  })
})

describe('resultsCountLabel', () => {
  it('shows filtered-of-total or a plain count', () => {
    expect(resultsCountLabel(2, 5)).toBe('Showing 2 of 5 tunes')
    expect(resultsCountLabel(5, 5)).toBe('5 tunes')
    expect(resultsCountLabel(1, 1)).toBe('1 tune')
  })
})

describe('URL state round-trip', () => {
  it('reads legacy params (mystatus only when logged in)', () => {
    const params = new URLSearchParams('search=Fred&type=jig&mystatus=learned&myinst=Fiddle&sortType=alpha&sortDir=asc')
    const s = stateFromParams(params, true)
    expect(s.filters).toEqual({ search: 'fred', type: 'jig', mystatus: 'learned' })
    expect(s.rawSearch).toBe('Fred')
    expect(s.myStatusInstrument).toBe('Fiddle')
    expect(s.sort).toEqual({ type: 'alpha', dir: 'asc' })

    const anon = stateFromParams(params, false)
    expect(anon.filters.mystatus).toBe('')
  })

  it('writes state back, omitting the default sort and preserving foreign params', () => {
    const params = applyStateToParams(
      new URLSearchParams('show=101&tune=5'),
      { search: 'fred', type: 'jig', mystatus: 'learned' },
      { type: 'session', dir: 'desc' },
      'Fiddle'
    )
    expect(params.get('search')).toBe('fred')
    expect(params.get('type')).toBe('jig')
    expect(params.get('mystatus')).toBe('learned')
    expect(params.get('myinst')).toBe('Fiddle')
    expect(params.has('sortType')).toBe(false)
    expect(params.get('show')).toBe('101')
    expect(params.get('tune')).toBe('5')

    const cleared = applyStateToParams(
      params,
      { search: '', type: '', mystatus: '' },
      { type: 'alpha', dir: 'asc' },
      'all'
    )
    expect(cleared.has('search')).toBe(false)
    expect(cleared.has('myinst')).toBe(false)
    expect(cleared.get('sortType')).toBe('alpha')
    expect(cleared.get('sortDir')).toBe('asc')
  })
})

describe('basePathOf', () => {
  it('strips tab suffixes and deep-linked ids', () => {
    expect(basePathOf('/sessions/austin/mueller')).toBe('/sessions/austin/mueller')
    expect(basePathOf('/sessions/austin/mueller/tunes')).toBe('/sessions/austin/mueller')
    expect(basePathOf('/sessions/austin/mueller/tunes/123')).toBe('/sessions/austin/mueller')
    expect(basePathOf('/sessions/austin/mueller/people/9')).toBe('/sessions/austin/mueller')
    expect(basePathOf('/sessions/austin/mueller/logs/')).toBe('/sessions/austin/mueller/logs') // trailing slash first
  })
})

describe('logs helpers', () => {
  it('formats times as 12-hour with am/pm', () => {
    expect(formatTime('19:30:00')).toBe('7:30pm')
    expect(formatTime('00:05:00')).toBe('12:05am')
    expect(instanceTimeLabel({ start_time: '19:00:00', end_time: '22:00:00' })).toBe('7:00pm-10:00pm')
    expect(instanceTimeLabel({ start_time: '19:00:00', end_time: null })).toBe('7:00pm - ?')
    expect(instanceTimeLabel({ start_time: null, end_time: null })).toBe('')
  })
  it('marks empty logs and picks the instance URL id', () => {
    expect(isEmptyLog({ tune_count: 0 })).toBe(true)
    expect(isEmptyLog({ tune_count: 2 })).toBe(false)
    expect(instanceUrlId({ multiple_on_date: false, date: '2025-06-01', session_instance_id: 9 })).toBe('2025-06-01')
    expect(instanceUrlId({ multiple_on_date: true, date: '2025-06-01', session_instance_id: 9 })).toBe(9)
  })
})

describe('people helpers', () => {
  it('parseTheSessionId handles ids and member/session URLs', () => {
    expect(parseTheSessionId('12345')).toBe(12345)
    expect(parseTheSessionId('https://thesession.org/members/678')).toBe(678)
    expect(parseTheSessionId('https://thesession.org/sessions/99')).toBe(99)
    expect(parseTheSessionId('bogus')).toBeNull()
    expect(parseTheSessionId('')).toBeNull()
  })

  it('normalizeQuotes straightens smart quotes', () => {
    expect(normalizeQuotes('O’Neill “the”')).toBe('O\'Neill "the"')
  })

  it('filterPeople applies regulars + search over name/instruments', () => {
    const people = [
      { person_id: 1, first_name: 'Ann', last_name: 'Malone', is_regular: true, instruments: ['Fiddle'] },
      { person_id: 2, first_name: 'Bob', last_name: 'Kelly', is_regular: false, instruments: ['Flute'] },
    ]
    expect(filterPeople(people, 'regulars', '')).toHaveLength(1)
    expect(filterPeople(people, 'all', 'flute').map((p) => p.person_id)).toEqual([2])
    expect(filterPeople(people, 'all', 'malone').map((p) => p.person_id)).toEqual([1])
  })
})
