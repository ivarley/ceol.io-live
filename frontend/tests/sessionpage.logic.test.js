// Pure-logic tests for the session-detail page port (spec 035 Step 4b).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { extractTuneId, normalizeQuotes, parseLocalDate } from '../src/shared/parse.js'
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
  keepInstance,
  filterInstanceGroups,
  matchLoggedTunes,
  tunePlayLinks,
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

  it('attended filter (spec 033 R4) keeps only tunes with attended plays', () => {
    const withAttended = [
      { ...tunes[0], attended_play_count: 2 },
      { ...tunes[1], attended_play_count: 0 },
      { ...tunes[2] }, // field absent (anonymous / stale payload) -> filtered out
    ]
    expect(
      filterAndSortTunes(withAttended, { ...noFilters, attended: true }, sessionDesc, 'all').map((t) => t.tune_id)
    ).toEqual([101])
    expect(filterAndSortTunes(withAttended, { ...noFilters, attended: false }, sessionDesc, 'all')).toHaveLength(3)
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
    expect(s.filters).toEqual({ search: 'fred', type: 'jig', mystatus: 'learned', attended: false })
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
    expect(params.has('attended')).toBe(false)
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

  it('the attended flag (spec 033 R4) round-trips and is logged-in only', () => {
    const params = applyStateToParams(
      new URLSearchParams(),
      { search: '', type: '', mystatus: '', attended: true },
      { type: 'session', dir: 'desc' },
      'all'
    )
    expect(params.get('attended')).toBe('1')
    expect(stateFromParams(params, true).filters.attended).toBe(true)
    expect(stateFromParams(params, false).filters.attended).toBe(false)

    const cleared = applyStateToParams(
      params,
      { search: '', type: '', mystatus: '', attended: false },
      { type: 'session', dir: 'desc' },
      'all'
    )
    expect(cleared.has('attended')).toBe(false)
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

  // Spec 034: members / visitors / archived, not regulars/all.
  const people = [
    { person_id: 1, first_name: 'Ann', last_name: 'Malone', relationship: 'member', archived: false, instruments: ['Fiddle'] },
    { person_id: 2, first_name: 'Bob', last_name: 'Kelly', relationship: 'visitor', archived: false, instruments: ['Flute'] },
    { person_id: 3, first_name: 'Maura', last_name: 'Gone', relationship: 'member', archived: true, instruments: ['Harp'] },
  ]

  it('filterPeople splits members / visitors / archived', () => {
    expect(filterPeople(people, 'members', '').map((p) => p.person_id)).toEqual([1])
    expect(filterPeople(people, 'visitors', '').map((p) => p.person_id)).toEqual([2])
    expect(filterPeople(people, 'archived', '').map((p) => p.person_id)).toEqual([3])
  })

  it('excludes archived people from the members view — they have gone', () => {
    expect(filterPeople(people, 'members', '').map((p) => p.person_id)).not.toContain(3)
  })

  it('but a SEARCH finds archived people regardless of the active filter', () => {
    // Archived means hidden, never unfindable: a member you cannot find is a member someone
    // re-creates as a duplicate person.
    expect(filterPeople(people, 'members', 'maura').map((p) => p.person_id)).toEqual([3])
  })

  it('searches over name and instruments', () => {
    expect(filterPeople(people, 'members', 'flute').map((p) => p.person_id)).toEqual([2])
    expect(filterPeople(people, 'members', 'malone').map((p) => p.person_id)).toEqual([1])
  })
})

describe('parseLocalDate', () => {
  it('parses date-only strings as LOCAL dates (no UTC day shift)', () => {
    const d = parseLocalDate('2026-01-27')
    // Regardless of the machine timezone, the local calendar date must match.
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 0, 27])
    expect(d.toLocaleDateString('en-US', { weekday: 'long' })).toBe('Tuesday')
  })
  it('passes timestamps and Date objects through to new Date()', () => {
    const iso = '2026-01-27T15:30:00Z'
    expect(parseLocalDate(iso).getTime()).toBe(new Date(iso).getTime())
    const d = new Date()
    expect(parseLocalDate(d).getTime()).toBe(d.getTime())
  })
})

describe('logs tab filters', () => {
  const inst = (id, count) => ({ session_instance_id: id, date: '2026-01-01', tune_count: count })
  const groups = {
    2026: [inst(1, 5), inst(2, 0)],
    2025: [inst(3, 0)],
    2024: [inst(4, 2)],
  }
  const years = [2026, 2025, 2024]

  it('keepInstance: "logged" drops the placeholder nights, "all" keeps them', () => {
    expect(keepInstance(inst(1, 5), 'logged', null)).toBe(true)
    expect(keepInstance(inst(2, 0), 'logged', null)).toBe(false)
    expect(keepInstance(inst(2, 0), 'all', null)).toBe(true)
  })

  it('keepInstance: a tune filter SUPERSEDES the toggle (its nights are logged by definition)', () => {
    const ids = new Set([2])
    expect(keepInstance(inst(2, 0), 'logged', ids)).toBe(true)
    expect(keepInstance(inst(1, 5), 'all', ids)).toBe(false)
  })

  it('filterInstanceGroups drops sections left empty rather than showing a bare header', () => {
    const view = filterInstanceGroups(years, groups, 'logged', null)
    expect(view.sortedKeys).toEqual([2026, 2024]) // 2025 held only an empty night
    expect(view.byKey[2026].map((i) => i.session_instance_id)).toEqual([1])
    expect(view.total).toBe(2)
  })

  it('filterInstanceGroups keeps everything under "all"', () => {
    const view = filterInstanceGroups(years, groups, 'all', null)
    expect(view.sortedKeys).toEqual(years)
    expect(view.total).toBe(4)
  })

  it('filterInstanceGroups narrows to the tune filter across years', () => {
    const view = filterInstanceGroups(years, groups, 'logged', new Set([3, 4]))
    expect(view.sortedKeys).toEqual([2025, 2024])
    expect(view.total).toBe(2)
  })

  const tunes = [
    { tune_id: 1, name: 'The Butterfly', log_count: 3 },
    { tune_id: 2, name: 'Butterfly Whirl', log_count: 9 },
    { tune_id: 3, name: "Cooley's", log_count: 40 },
  ]

  it('matchLoggedTunes: empty query matches nothing (no dropdown on an empty box)', () => {
    expect(matchLoggedTunes(tunes, '')).toEqual([])
    expect(matchLoggedTunes(tunes, '   ')).toEqual([])
  })

  it('matchLoggedTunes: substring match, prefix hits first, then the most-played', () => {
    const names = matchLoggedTunes(tunes, 'butterfly').map((t) => t.name)
    expect(names).toEqual(['Butterfly Whirl', 'The Butterfly'])
  })

  it('matchLoggedTunes: case-insensitive and capped by the limit', () => {
    expect(matchLoggedTunes(tunes, 'COOL').map((t) => t.tune_id)).toEqual([3])
    expect(matchLoggedTunes(tunes, 'butterfly', 1)).toHaveLength(1)
  })
})

describe('tunePlayLinks', () => {
  const plays = new Map([
    [
      10,
      [
        { session_instance_tune_id: 900, name: "Cooley's", set_number: 2, position_in_set: 1 },
        { session_instance_tune_id: 907, name: "Cooley's", set_number: 5, position_in_set: 3 },
      ],
    ],
  ])

  it('links each play at its own record, with Set N / tune M coordinates', () => {
    const links = tunePlayLinks(plays, { session_instance_id: 10 }, 'austin/mueller', 101)
    expect(links).toHaveLength(2)
    expect(links[0]).toEqual({
      key: 900,
      name: "Cooley's",
      where: 'set 2, tune 1',
      href: '/sessions/austin/mueller/10?highlight=900&tune=101',
    })
    expect(links[1].href).toBe('/sessions/austin/mueller/10?highlight=907&tune=101')
  })

  it('is empty for an instance with no plays, and with no map at all', () => {
    expect(tunePlayLinks(plays, { session_instance_id: 11 }, 'p', 1)).toEqual([])
    expect(tunePlayLinks(null, { session_instance_id: 10 }, 'p', 1)).toEqual([])
  })
})
