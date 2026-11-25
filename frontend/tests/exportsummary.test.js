// The filter summaries that travel with an export: one line per filter that is set.
// These mirror the filter state of the My Tunes page and the session page's two
// exporting tabs — a filter added there needs a line here (the files say so too).
import { describe, it, expect } from 'vitest'
import { myTunesExportSummary } from '../src/mytunespage/exportsummary.js'
import { sessionLogsExportSummary, sessionTunesExportSummary } from '../src/sessionpage/exportsummary.js'

const labels = {
  statusLabel: (s) => ({ learning: 'Learning' })[s] || s,
  typeName: (s) => s[0].toUpperCase() + s.slice(1),
  instrumentName: (s) => s,
  relLabel: (s) => ({ member: 'At my sessions', attended: 'While I was there' })[s] || s,
  sortModeLabel: (s) => ({ alpha: 'Name (a-z)', popularity: 'Popularity', plays: 'My plays' })[s] || s,
}

describe('myTunesExportSummary', () => {
  it('names every set filter and always the sort', () => {
    const lines = myTunesExportSummary(
      {
        search: 'spear',
        type: 'reel',
        status: 'learning',
        instrument: 'Fiddle',
        rel: 'attended',
        tag: 'pub-set',
        addedDate: '2026-01-01',
        addedDir: 'before',
      },
      { type: 'popularity', dir: 'desc', type2: 'alpha', dir2: 'asc' },
      labels
    )
    expect(lines).toEqual([
      'Status: Learning',
      'Type: Reel',
      'Instrument: Fiddle',
      'Tag: pub-set',
      'Played: While I was there',
      'Added before 2026-01-01',
      'Search: spear',
      'Sort: Popularity, descending',
      'Then by: Name (a-z), ascending',
    ])
  })

  it('with nothing set, says only how the list is sorted', () => {
    expect(myTunesExportSummary({ search: '', type: '', status: '', instrument: '', rel: '', tag: '', addedDate: '' }, { type: 'alpha', dir: 'asc' }, labels)).toEqual([
      'Sort: Name (a-z), ascending',
    ])
  })

  it('an added date defaults to "after"', () => {
    const lines = myTunesExportSummary({ addedDate: '2026-03-04', addedDir: 'after' }, { type: 'alpha', dir: 'asc' }, labels)
    expect(lines[0]).toBe('Added after 2026-03-04')
  })
})

describe('sessionTunesExportSummary', () => {
  const l = {
    sortLabel: (s) => s,
    typeName: (s) => s[0].toUpperCase() + s.slice(1),
    statusWord: (s) => s,
    instrumentName: (s) => s,
  }
  it('names type, attended, my-tunebook status with its instrument, search, and sort', () => {
    expect(
      sessionTunesExportSummary({ type: 'jig', attended: true, mystatus: 'learned', search: 'kesh' }, { type: 'session', dir: 'desc' }, 'Flute', l)
    ).toEqual(['Type: Jig', 'Nights I attended', 'My Tunebook: learned', 'Instrument: Flute', 'Search: kesh', 'Sort: session, descending'])
  })
  it('leaves the instrument out when the scope is all, or the tunebook filter is off', () => {
    expect(sessionTunesExportSummary({ mystatus: 'learned' }, { type: 'alpha', dir: 'asc' }, 'all', l)).toEqual(['My Tunebook: learned', 'Sort: alpha, ascending'])
    expect(sessionTunesExportSummary({ mystatus: '' }, { type: 'alpha', dir: 'asc' }, 'Flute', l)).toEqual(['Sort: alpha, ascending'])
  })
})

describe('sessionLogsExportSummary', () => {
  const l = { viewLabel: (id) => ({ logged: 'Logged', attended: 'Attended', all: 'All' })[id] }
  it('names the view, or the tune filter that supersedes it', () => {
    expect(sessionLogsExportSummary('attended', null, l)).toEqual(['Nights: Attended'])
    expect(sessionLogsExportSummary('logged', { tune_id: 1, name: 'The Kesh' }, l)).toEqual(['Nights with The Kesh'])
  })
})
