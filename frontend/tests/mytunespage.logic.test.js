// Unit tests for the My Tunes page logic (spec 035 Step 2) — the pure module
// behind App.svelte. Ported behaviors are asserted against the legacy semantics.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { extractTuneId } from '../src/shared/parse.js'
import {
  resolveTuneInstrumentStatus,
  buildSortFunction,
  filterAndSort,
  noResultsMessage,
  resultsCountText,
  typeBadgeLabel,
  stateFromParams,
  paramsFromState,
  applyPendingOps,
  nextStatus,
  cycleInstrumentOverride,
  fetchAllTunes,
} from '../src/mytunespage/logic.js'

const tune = (over = {}) => ({
  person_tune_id: 1,
  tune_id: 100,
  tune_name: 'The Test Reel',
  tune_type: 'reel',
  learn_status: 'learning',
  heard_count: 0,
  notes: null,
  tunebook_count: 5,
  session_play_count: 0,
  instrument_status: {},
  ...over,
})

describe('extractTuneId', () => {
  it('parses plain numbers, urls with query/hash, and rejects garbage', () => {
    expect(extractTuneId('123')).toBe(123)
    expect(extractTuneId('https://thesession.org/tunes/123?setting=456')).toBe(123)
    expect(extractTuneId('https://thesession.org/tunes/9#setting9')).toBe(9)
    expect(extractTuneId('cooley')).toBe(null)
    expect(extractTuneId('')).toBe(null)
  })
})

describe('resolveTuneInstrumentStatus', () => {
  const insts = [
    { instrument: 'Fiddle', is_auto: true },
    { instrument: 'Flute', is_auto: false },
  ]
  it('override wins; auto follows learn_status; manual untracked', () => {
    const t = tune({ instrument_status: { Fiddle: 'learned' } })
    expect(resolveTuneInstrumentStatus(t, insts, 'fiddle')).toBe('learned')
    expect(resolveTuneInstrumentStatus(tune(), insts, 'Fiddle')).toBe('learning')
    expect(resolveTuneInstrumentStatus(tune(), insts, 'Flute')).toBe(null)
    expect(resolveTuneInstrumentStatus(tune(), insts, 'Banjo')).toBe(null)
  })
})

describe('sorting', () => {
  const a = tune({ tune_name: 'Apples', tunebook_count: 1, heard_count: 9 })
  const b = tune({ tune_name: 'Bees', tunebook_count: 7, heard_count: 2 })
  it('primary sort respects direction', () => {
    expect([b, a].sort(buildSortFunction({ type: 'alpha', dir: 'asc' }))[0]).toBe(a)
    expect([a, b].sort(buildSortFunction({ type: 'alpha', dir: 'desc' }))[0]).toBe(b)
    expect([a, b].sort(buildSortFunction({ type: 'popularity', dir: 'desc' }))[0]).toBe(b)
  })
  it('secondary sort breaks ties, keeping its own direction', () => {
    const x = tune({ tune_name: 'Same', tunebook_count: 3, heard_count: 1 })
    const y = tune({ tune_name: 'Same', tunebook_count: 3, heard_count: 8 })
    const fn = buildSortFunction({ type: 'popularity', dir: 'desc', type2: 'heard', dir2: 'desc' })
    expect([x, y].sort(fn)[0]).toBe(y)
  })
})

describe('filterAndSort', () => {
  const insts = [
    { instrument: 'Fiddle', is_auto: true },
    { instrument: 'Flute', is_auto: false },
  ]
  const sort = { type: 'alpha', dir: 'asc', type2: null, dir2: null }

  it('searches name AND notes accent-insensitively, and matches tune ids/urls', () => {
    const tunes = [
      tune({ tune_id: 1, tune_name: 'Sí Beag Sí Mór' }),
      tune({ tune_id: 2, tune_name: 'Other', notes: 'learned from Máire' }),
      tune({ tune_id: 3, tune_name: 'Third' }),
    ]
    expect(filterAndSort(tunes, { search: 'si beag', type: '', status: '', instrument: '' }, sort, [])).toHaveLength(1)
    expect(filterAndSort(tunes, { search: 'maire', type: '', status: '', instrument: '' }, sort, [])).toHaveLength(1)
    const byId = filterAndSort(tunes, { search: 'https://thesession.org/tunes/3', type: '', status: '', instrument: '' }, sort, [])
    expect(byId.map((t) => t.tune_id)).toEqual([3])
  })

  it('instrument filter dims non-matching tunes instead of dropping them, matches first', () => {
    const tunes = [
      tune({ tune_id: 1, tune_name: 'A', instrument_status: { Flute: 'learning' } }),
      tune({ tune_id: 2, tune_name: 'B' }), // Flute untracked -> dimmed
    ]
    const out = filterAndSort(tunes, { search: '', type: '', status: '', instrument: 'Flute' }, sort, insts)
    expect(out).toHaveLength(2)
    expect(out[0].tune_id).toBe(1)
    expect(out[0]._instDimmed).toBe(false)
    expect(out[1]._instDimmed).toBe(true)
  })

  it('status filter uses the instrument-resolved status for matches', () => {
    const tunes = [
      tune({ tune_id: 1, learn_status: 'want to learn', instrument_status: { Flute: 'learned' } }),
    ]
    const out = filterAndSort(tunes, { search: '', type: '', status: 'learned', instrument: 'Flute' }, sort, insts)
    expect(out).toHaveLength(1)
  })
})

describe('messages and badges', () => {
  it('noResultsMessage mirrors legacy wording, including the tune-id special case', () => {
    expect(noResultsMessage({ search: '456', type: '', status: '' })).toBe('No tune with ID 456 found')
    expect(noResultsMessage({ search: 'foo', type: 'reel', status: 'learned' })).toBe(
      "No Reels containing 'foo' in 'Learned' status found"
    )
  })
  it('resultsCountText covers all three forms', () => {
    const list = [tune(), tune({ _instDimmed: true })]
    expect(resultsCountText(list, 2, { instrument: '' })).toBe('2 tunes')
    expect(resultsCountText([list[0]], 2, { instrument: '' })).toBe('Showing 1 of 2 tunes')
    expect(resultsCountText(list, 2, { instrument: 'Fiddle' })).toBe('1 of 2 tunes on Fiddle')
  })
  it('typeBadgeLabel switches meaning with sort mode', () => {
    const t = tune({ tunebook_count: 7, heard_count: 3, session_play_count: 2 })
    expect(typeBadgeLabel(t, 'alpha')).toBe('reel')
    expect(typeBadgeLabel(t, 'popularity')).toBe('7')
    expect(typeBadgeLabel(t, 'heard')).toBe('3')
    expect(typeBadgeLabel(t, 'plays')).toBe('2')
  })
})

describe('URL state round-trip', () => {
  it('restores filters + primary/secondary sort and omits defaults', () => {
    const params = paramsFromState(
      { search: 'x', type: 'jig', status: 'learned', instrument: 'Fiddle' },
      { type: 'heard', dir: 'desc', type2: 'alpha', dir2: 'asc' }
    )
    const { filters, sort } = stateFromParams(params)
    expect(filters).toEqual({ search: 'x', type: 'jig', status: 'learned', instrument: 'Fiddle' })
    expect(sort).toEqual({ type: 'heard', dir: 'desc', type2: 'alpha', dir2: 'asc' })
    // alpha-asc default writes nothing
    expect(paramsFromState({ search: '', type: '', status: '', instrument: '' }, { type: 'alpha', dir: 'asc', type2: null, dir2: null }).toString()).toBe('')
  })
})

describe('applyPendingOps (offline overlay)', () => {
  it('synthesizes pending adds, applies edits, drops removes', () => {
    const server = [tune({ tune_id: 1, heard_count: 1 }), tune({ tune_id: 2, person_tune_id: 9 })]
    const ops = [
      { type: 'add', tune_id: 50, name: 'Queued Jig', tune_type: 'jig', ts: 1 },
      { type: 'set_heard', tune_id: 1, heard_count: 4, ts: 2 },
      { type: 'remove', tune_id: 2, ts: 3 },
      { type: 'set_instrument_status', tune_id: 1, instrument: 'Fiddle', status: 'learned', ts: 4 },
    ]
    const out = applyPendingOps(server, ops)
    expect(out).toHaveLength(2)
    const added = out.find((t) => t.tune_id === 50)
    expect(added.person_tune_id).toBe('pending-50')
    expect(added.pending_sync).toBe(true)
    const edited = out.find((t) => t.tune_id === 1)
    expect(edited.heard_count).toBe(4)
    expect(edited.instrument_status.Fiddle).toBe('learned')
    expect(edited.pending_sync).toBe(true)
    expect(out.find((t) => t.tune_id === 2)).toBeUndefined()
  })

  it('a null instrument status clears the override', () => {
    const server = [tune({ tune_id: 1, instrument_status: { Fiddle: 'learned' } })]
    const out = applyPendingOps(server, [
      { type: 'set_instrument_status', tune_id: 1, instrument: 'Fiddle', status: null, ts: 1 },
    ])
    expect(out[0].instrument_status).toEqual({})
  })
})

describe('status cycling', () => {
  it('cycles want to learn -> learning -> learned -> want to learn', () => {
    expect(nextStatus('want to learn')).toBe('learning')
    expect(nextStatus('learning')).toBe('learned')
    expect(nextStatus('learned')).toBe('want to learn')
  })
  it('auto instrument set back to the base status stores NO override (snap-back)', () => {
    const t = tune({ learn_status: 'learning', instrument_status: { Fiddle: 'learned' } })
    const auto = { instrument: 'Fiddle', is_auto: true }
    expect(cycleInstrumentOverride(t, auto, 'learning')).toEqual({})
    expect(cycleInstrumentOverride(t, auto, 'learned')).toEqual({ Fiddle: 'learned' })
    const manual = { instrument: 'Flute', is_auto: false }
    expect(cycleInstrumentOverride(tune(), manual, 'learning')).toEqual({ Flute: 'learning' })
  })
})

describe('fetchAllTunes', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()))
  afterEach(() => vi.unstubAllGlobals())

  it('follows pagination past the 2000-row cap (the legacy truncation fix)', async () => {
    const pageResp = (tunes, hasNext, instruments) => ({
      ok: true,
      json: async () => ({ success: true, tunes, instruments, pagination: { has_next: hasNext } }),
    })
    fetch
      .mockResolvedValueOnce(pageResp([tune({ tune_id: 1 })], true, [{ instrument: 'Fiddle', is_auto: true }]))
      .mockResolvedValueOnce(pageResp([tune({ tune_id: 2 })], false))
    const out = await fetchAllTunes('alpha-asc')
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(fetch.mock.calls[1][0]).toContain('page=2')
    expect(out.tunes.map((t) => t.tune_id)).toEqual([1, 2])
    expect(out.instruments).toEqual([{ instrument: 'Fiddle', is_auto: true }])
  })
})
