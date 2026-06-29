// My-Tunes offline op-queue (Tier 2) — plain (non-module) global for use from
// tune_detail_modal.js and the My Tunes page, including inside the live logger.
//
// Mirrors the live logger's offline.js shape (frontend/src/offline.js) but is a
// standalone vanilla script: that module is ES-module-only and can't be imported by
// the plain <script>s that drive the tune-detail modal. Session-logging ops and
// my-tunes ops are independent queues against different servers (per spec 024 plan),
// so a separate store here is intentional, not a fork to keep in sync.
//
// Ops are tune_id-keyed and idempotent server-side (POST /api/my-tunes/ops), so
// queued ops replay safely after reconnect with no dedup table. heard count is sent
// as an ABSOLUTE target (set_heard), never a delta, so a replayed +1 can't double.
(function (window) {
  'use strict'

  // Some pages include this script more than once (a partial plus a direct tag).
  // Register once so the 'online'/'load' flush listeners aren't double-bound.
  if (window.MyTunesOffline) return

  var DB_NAME = 'ceol-mytunes'
  var DB_VERSION = 1
  var OPS = 'ops'
  var ENDPOINT = '/api/my-tunes/ops'
  var dbPromise = null

  function db() {
    if (!dbPromise) {
      dbPromise = new Promise(function (resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VERSION)
        req.onupgradeneeded = function () {
          var d = req.result
          if (!d.objectStoreNames.contains(OPS)) d.createObjectStore(OPS, { keyPath: 'op_id' })
        }
        req.onsuccess = function () { resolve(req.result) }
        req.onerror = function () { reject(req.error) }
      })
    }
    return dbPromise
  }

  function idb(mode, fn) {
    return db().then(function (d) {
      return new Promise(function (resolve, reject) {
        var tx = d.transaction(OPS, mode)
        var store = tx.objectStore(OPS)
        var out = fn(store)
        tx.oncomplete = function () { resolve(out && out.result !== undefined ? out.result : out) }
        tx.onerror = function () { reject(tx.error) }
        tx.onabort = function () { reject(tx.error) }
      })
    })
  }

  function queuePut(op) { return idb('readwrite', function (s) { s.put(op) }) }
  function queueDelete(op_id) { return idb('readwrite', function (s) { s.delete(op_id) }) }
  function queueAll() {
    return idb('readonly', function (s) { return s.getAll() }).then(function (all) {
      return (all || []).sort(function (a, b) { return a.ts - b.ts })
    })
  }

  function uuid() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID()
    return 'op-' + Date.now() + '-' + Math.random().toString(16).slice(2)
  }

  // POST one op. Resolves the parsed JSON on a 2xx; rejects with a TypeError on a
  // network failure (offline) and a plain Error on a server-rejected op (4xx/5xx).
  function send(op) {
    return fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(op),
    }).then(function (r) {
      return r.json().then(
        function (j) {
          if (!r.ok || !j.success) throw new Error((j && j.error) || ('HTTP ' + r.status))
          return j
        },
        function () { throw new Error('HTTP ' + r.status) }
      )
    })
  }

  // True for a genuine offline/network failure (fetch throws TypeError), as opposed
  // to a server that answered with an error.
  function isNetworkError(err) {
    return err instanceof TypeError || (window.navigator && window.navigator.onLine === false)
  }

  // Submit an op. Online success -> {online:true, data}. Offline -> queues and
  // resolves {queued:true} (caller keeps its optimistic UI). A server rejection
  // REJECTS (caller should revert) and is NOT queued (it can't succeed on replay).
  function submit(op) {
    if (!op.op_id) op.op_id = uuid()
    if (!op.ts) op.ts = Date.now()
    return send(op).then(
      function (data) { return { online: true, queued: false, data: data } },
      function (err) {
        if (isNetworkError(err)) {
          return queuePut(op).then(function () { return { online: false, queued: true } })
        }
        throw err
      }
    )
  }

  var flushing = false
  // Replay queued ops oldest-first. Stops at the first network failure (still
  // offline); drops any op the server rejects (a bad op can't succeed on replay).
  function flush() {
    if (flushing) return Promise.resolve()
    flushing = true
    return queueAll()
      .then(function (ops) {
        return ops.reduce(function (chain, op) {
          return chain.then(function () {
            return send(op).then(
              function () { return queueDelete(op.op_id) },
              function (err) {
                if (isNetworkError(err)) throw err // still offline -> stop
                return queueDelete(op.op_id) // server rejected -> discard
              }
            )
          })
        }, Promise.resolve())
      })
      .catch(function () {})
      .then(function () { flushing = false })
  }

  if (window.addEventListener) window.addEventListener('online', flush)

  window.MyTunesOffline = { submit: submit, flush: flush, pending: queueAll }

  // Replay anything left from a previous offline session, once the page settles.
  if (window.addEventListener) {
    window.addEventListener('load', function () { setTimeout(flush, 1500) })
  }
})(window)
