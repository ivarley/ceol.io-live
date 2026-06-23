// Spec 024 §G — the offline op queue, backed by IndexedDB so it survives reloads
// and true app restarts. Each entry is a self-contained, idempotent op (keyed by
// op_id) waiting to be POSTed; `ts` preserves the offline order for replay.
//
// Dependency-free: a thin promise wrapper over the raw IndexedDB API.

const DB_NAME = 'ceol-live'
const DB_VERSION = 1
const STORE = 'ops'

let dbPromise = null

function db() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION)
      req.onupgradeneeded = () => {
        const d = req.result
        if (!d.objectStoreNames.contains(STORE)) {
          d.createObjectStore(STORE, { keyPath: 'op_id' }) // ordered in JS by `ts`
        }
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  }
  return dbPromise
}

function run(mode, fn) {
  return db().then(
    (d) =>
      new Promise((resolve, reject) => {
        const tx = d.transaction(STORE, mode)
        const store = tx.objectStore(STORE)
        const result = fn(store)
        tx.oncomplete = () => resolve(result && result.value !== undefined ? result.value : result)
        tx.onerror = () => reject(tx.error)
        tx.onabort = () => reject(tx.error)
      })
  )
}

// Persist (or update) a queued op: {op_id, op_type, payload, name, ts}.
export function queuePut(entry) {
  return run('readwrite', (store) => store.put(entry))
}

// Queued ops for ONE instance, oldest first (offline replay order). Scoping by
// instance is essential: an op must only ever replay to the instance it was made
// for, never to whatever instance happens to be open next.
export function queueAll(sessionInstanceId) {
  return db().then(
    (d) =>
      new Promise((resolve, reject) => {
        const req = d.transaction(STORE, 'readonly').objectStore(STORE).getAll()
        req.onsuccess = () =>
          resolve(
            (req.result || [])
              .filter((e) => e.session_instance_id === sessionInstanceId)
              .sort((a, b) => a.ts - b.ts)
          )
        req.onerror = () => reject(req.error)
      })
  )
}

export function queueDelete(op_id) {
  return run('readwrite', (store) => store.delete(op_id))
}
