import { describe, it, expect } from 'vitest'
import {
  queuePut, queueDelete, queueAll,
  snapshotPut, snapshotGet,
  matchCachePut, matchCacheGet,
} from '../src/offline.js'

// fake-indexeddb (loaded in tests/setup.js) backs a single process-wide DB, and
// offline.js caches its connection — so tests isolate by using unique instance ids
// rather than resetting the store.

let nextInst = 1000
const freshInst = () => ++nextInst

describe('op queue', () => {
  it('returns queued ops for one instance, oldest first', async () => {
    const inst = freshInst()
    await queuePut({ op_id: 'a', session_instance_id: inst, ts: 30, op_type: 'add_tune' })
    await queuePut({ op_id: 'b', session_instance_id: inst, ts: 10, op_type: 'add_tune' })
    await queuePut({ op_id: 'c', session_instance_id: inst, ts: 20, op_type: 'add_tune' })
    const all = await queueAll(inst)
    expect(all.map((e) => e.op_id)).toEqual(['b', 'c', 'a']) // sorted by ts
  })

  it('scopes strictly to the requested instance', async () => {
    const inst = freshInst()
    const other = freshInst()
    await queuePut({ op_id: 'x', session_instance_id: inst, ts: 1 })
    await queuePut({ op_id: 'y', session_instance_id: other, ts: 1 })
    const all = await queueAll(inst)
    expect(all.map((e) => e.op_id)).toEqual(['x'])
  })

  it('deletes a queued op by op_id', async () => {
    const inst = freshInst()
    await queuePut({ op_id: 'd1', session_instance_id: inst, ts: 1 })
    await queuePut({ op_id: 'd2', session_instance_id: inst, ts: 2 })
    await queueDelete('d1')
    const all = await queueAll(inst)
    expect(all.map((e) => e.op_id)).toEqual(['d2'])
  })

  it('updates (upserts) an op with the same op_id', async () => {
    const inst = freshInst()
    await queuePut({ op_id: 'u', session_instance_id: inst, ts: 1, status: 'queued' })
    await queuePut({ op_id: 'u', session_instance_id: inst, ts: 1, status: 'sending' })
    const all = await queueAll(inst)
    expect(all).toHaveLength(1)
    expect(all[0].status).toBe('sending')
  })
})

describe('instance snapshot', () => {
  it('round-trips a snapshot keyed by instance', async () => {
    const inst = freshInst()
    await snapshotPut(inst, { records: [{ id: 1 }], last_event_id: 42, person: { name: 'Ian' } })
    const snap = await snapshotGet(inst)
    expect(snap.session_instance_id).toBe(inst)
    expect(snap.last_event_id).toBe(42)
    expect(snap.records).toEqual([{ id: 1 }])
  })

  it('returns undefined for an unknown instance', async () => {
    expect(await snapshotGet(freshInst())).toBeUndefined()
  })
})

describe('match cache', () => {
  it('returns a cached verdict on an exact (normalized) query hit', async () => {
    const inst = freshInst()
    const verdict = { exact_match: true, results: [{ tune_id: 7, name: 'The Silver Spear', tune_type: 'Reel' }] }
    await matchCachePut(inst, 'The Silver Spear', verdict)
    // "the " prefix and case are normalized away -> same key
    const hit = await matchCacheGet(inst, 'silver spear')
    expect(hit.results[0].tune_id).toBe(7)
  })

  it('falls back to an exact tune-name hit for a query never typed verbatim', async () => {
    const inst = freshInst()
    // Cache under query "xyz" but the RESULT is Cooleys; a later query of the tune
    // name resolves via the per-name index, not the per-query one.
    await matchCachePut(inst, 'xyz', { exact_match: false, results: [{ tune_id: 9, name: 'Cooleys', tune_type: 'Reel' }] })
    const hit = await matchCacheGet(inst, 'Cooleys')
    expect(hit).toMatchObject({ exact_match: true, fromCache: true })
    expect(hit.results[0].tune_id).toBe(9)
  })

  it('returns null when nothing is cached', async () => {
    expect(await matchCacheGet(freshInst(), 'nothing here')).toBeNull()
  })

  it('does not return an empty verdict as a hit', async () => {
    const inst = freshInst()
    await matchCachePut(inst, 'empty', { exact_match: false, results: [] })
    expect(await matchCacheGet(inst, 'empty')).toBeNull()
  })
})
