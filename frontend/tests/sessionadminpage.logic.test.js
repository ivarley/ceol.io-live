// Pure logic for the admin session-tunes tab. Today only the tune filter needs direct
// coverage: it gained a notation path, and notation matching is the one thing the
// browser cannot decide for itself (the payload carries no ABC).
import { describe, it, expect } from 'vitest'
import { filterTuneList } from '../src/sessionadminpage/logic.js'

const tunes = [
  { tune_id: 1, tune_name: 'Drowsy Maggie', tune_type: 'reel', session_alias: '', session_key: 'Edor', setting_key: 'Edor' },
  { tune_id: 2, tune_name: 'The Kesh', tune_type: 'jig', session_alias: 'Kesh Jig', session_key: 'Gmaj', setting_key: 'Gmaj' },
]

describe('filterTuneList', () => {
  it('matches name, alias, type and keys', () => {
    expect(filterTuneList(tunes, 'drowsy').map((t) => t.tune_id)).toEqual([1])
    expect(filterTuneList(tunes, 'kesh jig').map((t) => t.tune_id)).toEqual([2])
    expect(filterTuneList(tunes, 'jig').map((t) => t.tune_id)).toEqual([2])
    expect(filterTuneList(tunes, 'edor').map((t) => t.tune_id)).toEqual([1])
  })

  it('matches an exact tune id or a thesession.org link', () => {
    expect(filterTuneList(tunes, 'https://thesession.org/tunes/2').map((t) => t.tune_id)).toEqual([2])
  })

  it('returns everything for an empty query', () => {
    expect(filterTuneList(tunes, '')).toHaveLength(2)
  })

  it('unions notation matches the server resolved', () => {
    expect(filterTuneList(tunes, 'gedbed', new Set([2])).map((t) => t.tune_id)).toEqual([2])
  })

  it('omitting abcIds filters by text exactly as before', () => {
    expect(filterTuneList(tunes, 'gedbed')).toHaveLength(0)
    expect(filterTuneList(tunes, 'gedbed', null)).toHaveLength(0)
  })
})
