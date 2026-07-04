import { describe, it, expect } from 'vitest'
import { listStatus, statusClass, planStatusOps, applyStatusLocally, NOT_ON_LIST } from '../src/mylist.js'

// Shorthand fixtures. Instruments mirror /api/my-tunes: [{instrument, is_auto}].
const FIDDLE = { instrument: 'Fiddle', is_auto: true }
const FLUTE = { instrument: 'Flute', is_auto: true }
const BANJO = { instrument: 'Banjo', is_auto: false } // manual: tracked only via override
const entry = (learn_status, instrument_status = {}) => ({ learn_status, instrument_status })

// --------------------------------------------------------------------------- //
// listStatus: the modal's roll-up + per-instrument resolution
// --------------------------------------------------------------------------- //

describe('listStatus', () => {
  it('no entry -> not on list, regardless of scope', () => {
    expect(listStatus(undefined, [FIDDLE, FLUTE], 'all')).toBe(NOT_ON_LIST)
    expect(listStatus(undefined, [FIDDLE, FLUTE], 'Fiddle')).toBe(NOT_ON_LIST)
  })

  it('0 or 1 instrument: the roll-up IS the base learn_status', () => {
    expect(listStatus(entry('learning'), [], 'all')).toBe('learning')
    expect(listStatus(entry('learning'), [FIDDLE], 'all')).toBe('learning')
  })

  it('single instrument: an instrument scope still reads the base status', () => {
    // scope only engages at 2+ instruments (mirrors the modal, which hides the
    // per-instrument panel below that)
    expect(listStatus(entry('learned', { Fiddle: 'learning' }), [FIDDLE], 'Fiddle')).toBe('learned')
  })

  it('roll-up = furthest-along across instruments that have a status', () => {
    // base learning; Flute overridden to learned -> learned wins
    expect(listStatus(entry('learning', { Flute: 'learned' }), [FIDDLE, FLUTE], 'all')).toBe('learned')
    // overrides can only be <= base too: max still wins
    expect(listStatus(entry('learned', { Flute: 'want to learn' }), [FIDDLE, FLUTE], 'all')).toBe('learned')
  })

  it('manual instrument without an override contributes nothing to the roll-up', () => {
    // only Banjo (manual, untracked) + Fiddle (auto follows base)
    expect(listStatus(entry('learning'), [FIDDLE, BANJO], 'all')).toBe('learning')
  })

  it('instrument scope: override wins; auto follows base; manual untracked -> not on list', () => {
    const e = entry('learning', { Flute: 'learned' })
    expect(listStatus(e, [FIDDLE, FLUTE, BANJO], 'Flute')).toBe('learned') // override
    expect(listStatus(e, [FIDDLE, FLUTE, BANJO], 'Fiddle')).toBe('learning') // auto -> base
    expect(listStatus(e, [FIDDLE, FLUTE, BANJO], 'Banjo')).toBe(NOT_ON_LIST) // manual, no row
  })

  it('unknown scope name falls back to the roll-up', () => {
    expect(listStatus(entry('learning'), [FIDDLE, FLUTE], 'Harp')).toBe('learning')
  })
})

describe('statusClass', () => {
  it('hyphenates statuses into css tokens', () => {
    expect(statusClass('want to learn')).toBe('ls-want-to-learn')
    expect(statusClass(NOT_ON_LIST)).toBe('ls-not-on-list')
    expect(statusClass('learned')).toBe('ls-learned')
  })
})

// --------------------------------------------------------------------------- //
// planStatusOps: the /api/my-tunes/ops calls for a bulk set
// --------------------------------------------------------------------------- //

describe('planStatusOps', () => {
  const mapOf = (obj) => (tid) => obj[tid]

  it('not on list, overall scope -> a single add at the target status', () => {
    const plans = planStatusOps([1, 2], mapOf({}), [FIDDLE], 'all', 'want to learn')
    expect(plans).toEqual([
      { tune_id: 1, ops: [{ type: 'add', learn_status: 'want to learn' }] },
      { tune_id: 2, ops: [{ type: 'add', learn_status: 'want to learn' }] },
    ])
  })

  it('not on list, instrument scope -> add (default base) + the override', () => {
    const plans = planStatusOps([1], mapOf({}), [FIDDLE, FLUTE], 'Flute', 'learning')
    expect(plans).toEqual([
      { tune_id: 1, ops: [
        { type: 'add' },
        { type: 'set_instrument_status', instrument: 'Flute', status: 'learning' },
      ] },
    ])
  })

  it('on list, overall scope -> set_status + realign auto overrides (modal semantics)', () => {
    const e = entry('learning', { Fiddle: 'want to learn', Banjo: 'learned' })
    const plans = planStatusOps([1], mapOf({ 1: e }), [FIDDLE, BANJO], 'all', 'learned')
    // the auto Fiddle override is cleared; the manual Banjo override is curated -> untouched
    expect(plans).toEqual([
      { tune_id: 1, ops: [
        { type: 'set_status', learn_status: 'learned' },
        { type: 'set_instrument_status', instrument: 'Fiddle', status: null },
      ] },
    ])
  })

  it('overall scope skips only when base matches AND no auto override exists', () => {
    // base already at target, but an auto override lingers -> still realigns
    const lingering = entry('learned', { Fiddle: 'learning' })
    expect(planStatusOps([1], mapOf({ 1: lingering }), [FIDDLE, FLUTE], 'all', 'learned')).toHaveLength(1)
    // clean match -> skipped
    expect(planStatusOps([1], mapOf({ 1: entry('learned') }), [FIDDLE, FLUTE], 'all', 'learned')).toEqual([])
    // manual override doesn't force a rewrite
    expect(planStatusOps([1], mapOf({ 1: entry('learned', { Banjo: 'learning' }) }), [FIDDLE, BANJO], 'all', 'learned')).toEqual([])
  })

  it('on list, instrument scope -> one absolute set_instrument_status; skips when already shown', () => {
    const e = entry('learning', { Flute: 'learned' })
    expect(planStatusOps([1], mapOf({ 1: e }), [FIDDLE, FLUTE], 'Flute', 'learned')).toEqual([]) // already learned there
    expect(planStatusOps([1], mapOf({ 1: e }), [FIDDLE, FLUTE], 'Fiddle', 'learned')).toEqual([
      { tune_id: 1, ops: [{ type: 'set_instrument_status', instrument: 'Fiddle', status: 'learned' }] },
    ])
  })

  it('single-instrument player: an instrument scope operates on the base status', () => {
    const plans = planStatusOps([1], mapOf({}), [FIDDLE], 'Fiddle', 'learning')
    expect(plans).toEqual([{ tune_id: 1, ops: [{ type: 'add', learn_status: 'learning' }] }])
  })

  it('mixed batch: skips up-to-date tunes, plans the rest', () => {
    const entries = { 1: entry('learned'), 3: entry('want to learn') }
    const plans = planStatusOps([1, 2, 3], mapOf(entries), [FIDDLE], 'all', 'learned')
    expect(plans.map((p) => p.tune_id)).toEqual([2, 3])
  })
})

// --------------------------------------------------------------------------- //
// applyStatusLocally: the optimistic mirror of the server's end state
// --------------------------------------------------------------------------- //

describe('applyStatusLocally', () => {
  it('creates a fresh entry at target (overall scope)', () => {
    expect(applyStatusLocally(undefined, [FIDDLE], 'all', 'learning')).toEqual(
      entry('learning'),
    )
  })

  it('creates a default-base entry + override (instrument scope)', () => {
    expect(applyStatusLocally(undefined, [FIDDLE, FLUTE], 'Flute', 'learned')).toEqual(
      entry('want to learn', { Flute: 'learned' }),
    )
  })

  it('overall set realigns autos and keeps manual overrides — does not mutate the input', () => {
    const before = entry('learning', { Fiddle: 'want to learn', Banjo: 'learned' })
    const after = applyStatusLocally(before, [FIDDLE, BANJO], 'all', 'learned')
    expect(after).toEqual(entry('learned', { Banjo: 'learned' }))
    expect(before.instrument_status).toEqual({ Fiddle: 'want to learn', Banjo: 'learned' }) // untouched
  })

  it('auto instrument set back to the base snaps the override away (server snap-back)', () => {
    const before = entry('learning', { Fiddle: 'learned' })
    expect(applyStatusLocally(before, [FIDDLE, FLUTE], 'Fiddle', 'learning')).toEqual(entry('learning'))
  })

  it('the status of the local mirror matches what was just set', () => {
    // end-to-end sanity: after applying, listStatus under the same scope == target.
    // (Not asserted for 'all' + a lingering MANUAL override: an outranking manual
    // status legitimately keeps the roll-up above the base — modal behavior.)
    const insts = [FIDDLE, FLUTE, BANJO]
    for (const target of ['want to learn', 'learning', 'learned']) {
      for (const scope of ['Fiddle', 'Banjo']) {
        const e = applyStatusLocally(entry('learning', { Banjo: 'learned' }), insts, scope, target)
        expect(listStatus(e, insts, scope)).toBe(target)
      }
      const clean = applyStatusLocally(entry('learning', { Fiddle: 'learned' }), insts, 'all', target)
      expect(listStatus(clean, insts, 'all')).toBe(target)
    }
  })
})
