// Spec 024 §G — offline storage in IndexedDB:
//   - `ops`:       the op queue (pending ops, keyed by op_id, ordered by ts)
//   - `snapshots`: a per-instance snapshot of the records so the screen can render
//                  offline (bootstrap is network-only and fails with no connection)
//
// Dependency-free: a thin promise wrapper over the raw IndexedDB API.

const DB_NAME = 'ceol-live'
const DB_VERSION = 2
const OPS = 'ops'
const SNAPS = 'snapshots'

let dbPromise = null

function db() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION)
      req.onupgradeneeded = () => {
        const d = req.result
        if (!d.objectStoreNames.contains(OPS)) d.createObjectStore(OPS, { keyPath: 'op_id' })
        if (!d.objectStoreNames.contains(SNAPS)) d.createObjectStore(SNAPS, { keyPath: 'session_instance_id' })
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
  return read(OPS).then((all) =>
    (all || []).filter((e) => e.session_instance_id === sessionInstanceId).sort((a, b) => a.ts - b.ts)
  )
}

// --- Instance snapshot (for offline render) --------------------------------

// data: {records, last_event_id, person, ts}
export const snapshotPut = (sessionInstanceId, data) =>
  write(SNAPS, { session_instance_id: sessionInstanceId, ...data })
export const snapshotGet = (sessionInstanceId) => read(SNAPS, sessionInstanceId)
