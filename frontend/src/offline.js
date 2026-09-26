// Spec 024 §G — offline storage in IndexedDB:
//   - `ops`:       the op queue (pending ops, keyed by op_id, ordered by ts)
//   - `snapshots`: a per-instance snapshot of the records so the screen can render
//                  offline (bootstrap is network-only and fails with no connection)
//
// A thin promise wrapper over the raw IndexedDB API; the only import is logstate's
// pure name normalizer, so the cache keys fold names the way the matcher does.

import { normName, stripThe } from './logstate.js'

const DB_NAME = 'ceol-live'
const DB_VERSION = 3
const OPS = 'ops'
const SNAPS = 'snapshots'
const MATCH = 'matchcache' // recent name->tune match results, so offline typing can still link (#5c)

let dbPromise = null

function db() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION)
      req.onupgradeneeded = () => {
        const d = req.result
        if (!d.objectStoreNames.contains(OPS)) d.createObjectStore(OPS, { keyPath: 'op_id' })
        if (!d.objectStoreNames.contains(SNAPS)) d.createObjectStore(SNAPS, { keyPath: 'session_instance_id' })
        if (!d.objectStoreNames.contains(MATCH)) d.createObjectStore(MATCH, { keyPath: 'key' })
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  }
  return dbPromise
}

function write(store, value) {
  return db().then(
    (d) =>
      new Promise((resolve, reject) => {
        const tx = d.transaction(store, 'readwrite')
        tx.objectStore(store).put(value)
        tx.oncomplete = () => resolve()
        tx.onerror = () => reject(tx.error)
        tx.onabort = () => reject(tx.error)
      })
  )
}

function del(store, key) {
  return db().then(
    (d) =>
      new Promise((resolve, reject) => {
        const tx = d.transaction(store, 'readwrite')
        tx.objectStore(store).delete(key)
        tx.oncomplete = () => resolve()
        tx.onerror = () => reject(tx.error)
      })
  )
}

function read(store, key) {
  return db().then(
    (d) =>
      new Promise((resolve, reject) => {
        const req = d.transaction(store, 'readonly').objectStore(store)[key === undefined ? 'getAll' : 'get'](key)
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })
  )
}

// --- Op queue --------------------------------------------------------------

// Persist (or update) a queued op: {op_id, op_type, payload, name, ts, session_instance_id}.
export const queuePut = (entry) => write(OPS, entry)
export const queueDelete = (op_id) => del(OPS, op_id)

// Queued ops for ONE instance, oldest first. Scoping by instance is essential: an
// op must only ever replay to the instance it was made for.
export function queueAll(sessionInstanceId) {
  return read(OPS).then((all) => queueOrder(all, sessionInstanceId))
}

// The pure core of queueAll, split out so offline.fixtures.json can pin it. `all` is
// the store's getAll(), which IndexedDB returns in op_id order — so a ts tie replays in
// op_id order (the sort is stable). nextTs() exists so that tie never happens.
export function queueOrder(all, sessionInstanceId) {
  return (all || []).filter((e) => e.session_instance_id === sessionInstanceId).sort((a, b) => a.ts - b.ts)
}

// --- Instance snapshot (for offline render) --------------------------------

// data: {records, last_event_id, person, ts}
export const snapshotPut = (sessionInstanceId, data) =>
  write(SNAPS, { session_instance_id: sessionInstanceId, ...data })
export const snapshotGet = (sessionInstanceId) => read(SNAPS, sessionInstanceId)

// --- Match cache (#5c) -----------------------------------------------------
// Remember online match results so offline typing can still LINK a tune instead of
// always logging unlinked. Keyed per (instance, query) AND per (instance, tune name)
// so an offline exact-name match works even for a query string not typed verbatim
// before. Match results are session-specific (aliases/preferences), hence per-instance.

// The cache key's normalizer: the logger's own name normalizer (smart quotes folded,
// diacritics stripped, lowercased — the server matcher's rules), then a leading "the "
// dropped so "The Silver Spear" and "Silver Spear" share an entry. It used to fold
// fewer quotes and keep accents, so an offline "Sligo Maid" missed a cached "Sligo Maíd".
// Entries written under the old keys are simply never hit again; the next online
// lookup rewrites them.
export const normMatchQuery = (s) => stripThe(normName(s))

// `${instance}|q|${query}` for a whole verdict, `${instance}|n|${name}` for one tune.
export const matchCacheKey = (sessionInstanceId, kind, s) => `${sessionInstanceId}|${kind}|${normMatchQuery(s)}`

// The rows matchCachePut writes for one verdict: the verdict under its query, plus each
// linked result tune under its own normalized name. Pure (the caller passes `now`).
export function matchCacheRows(sessionInstanceId, q, verdict, now) {
  const rows = [{ key: matchCacheKey(sessionInstanceId, 'q', q), verdict, ts: now }]
  for (const t of verdict.results || []) {
    if (t.tune_id && t.name) {
      rows.push({
        key: matchCacheKey(sessionInstanceId, 'n', t.name),
        tune: { tune_id: t.tune_id, name: t.name, tune_type: t.tune_type ?? null }, ts: now,
      })
    }
  }
  return rows
}

// Cache a verdict ({exact_match, results:[{tune_id,name,tune_type,...}]}) for a query,
// plus each linked result tune by its normalized name. Best-effort (never throws).
export function matchCachePut(sessionInstanceId, q, verdict) {
  const writes = matchCacheRows(sessionInstanceId, q, verdict, Date.now()).map((row) => write(MATCH, row))
  return Promise.all(writes).catch(() => {})
}

// Look up a query offline: exact query-string hit returns the stored verdict; else an
// exact normalized-name hit returns a single exact match. null if nothing cached.
export async function matchCacheGet(sessionInstanceId, q) {
  const byQ = await read(MATCH, matchCacheKey(sessionInstanceId, 'q', q)).catch(() => null)
  if (byQ && byQ.verdict && (byQ.verdict.results || []).length) return byQ.verdict
  const byN = await read(MATCH, matchCacheKey(sessionInstanceId, 'n', q)).catch(() => null)
  if (byN && byN.tune) return { exact_match: true, results: [byN.tune], fromCache: true }
  return null
}
