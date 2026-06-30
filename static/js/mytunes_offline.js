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
  var DB_VERSION = 2
  var OPS = 'ops'
  var POPULAR = 'popular' // top catalog tunes, cached so you can add them offline
  var ENDPOINT = '/api/my-tunes/ops'
  var dbPromise = null

  function db() {
    if (!dbPromise) {
      dbPromise = new Promise(function (resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VERSION)
        req.onupgradeneeded = function () {
          var d = req.result
          if (!d.objectStoreNames.contains(OPS)) d.createObjectStore(OPS, { keyPath: 'op_id' })
          if (!d.objectStoreNames.contains(POPULAR)) d.createObjectStore(POPULAR, { keyPath: 'tune_id' })
        }
        req.onsuccess = function () { resolve(req.result) }
        req.onerror = function () { reject(req.error) }
      })
    }
    return dbPromise
  }

  function idb(store, mode, fn) {
    return db().then(function (d) {
      return new Promise(function (resolve, reject) {
        var tx = d.transaction(store, mode)
        var os = tx.objectStore(store)
        var out = fn(os)
        tx.oncomplete = function () { resolve(out && out.result !== undefined ? out.result : out) }
        tx.onerror = function () { reject(tx.error) }
        tx.onabort = function () { reject(tx.error) }
      })
    })
  }

  function queuePut(op) { return idb(OPS, 'readwrite', function (s) { s.put(op) }) }
  function queueDelete(op_id) { return idb(OPS, 'readwrite', function (s) { s.delete(op_id) }) }
  function queueAll() {
    return idb(OPS, 'readonly', function (s) { return s.getAll() }).then(function (all) {
      return (all || []).sort(function (a, b) { return a.ts - b.ts })
    })
  }

  // --- Popular tunes (offline add) ---------------------------------------------
  // Smart quotes \u-escaped (project rule: never embed smart-quote literals in source).
  var _norm = function (s) { return (s || '').replace(/[\u2018\u2019\u201B`\u00B4]/g, "'").toLowerCase().trim() }

  // Replace the cached popular set with the given tunes ({tune_id, name, tune_type,
  // tunebook_count, in_person_tune, learn_status}).
  function savePopular(tunes) {
    return idb(POPULAR, 'readwrite', function (s) {
      s.clear()
      ;(tunes || []).forEach(function (t) { if (t && t.tune_id) s.put(t) })
    })
  }

  // Offline name search over the cached popular set: substring match, most-bookmarked
  // first, capped. Returns [] if nothing is cached.
  function searchPopular(query, limit) {
    var q = _norm(query)
    limit = limit || 20
    return idb(POPULAR, 'readonly', function (s) { return s.getAll() }).then(function (all) {
      return (all || [])
        .filter(function (t) { return _norm(t.name).indexOf(q) !== -1 })
        .sort(function (a, b) { return (b.tunebook_count || 0) - (a.tunebook_count || 0) })
        .slice(0, limit)
    })
  }

  function uuid() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID()
    return 'op-' + Date.now() + '-' + Math.random().toString(16).slice(2)
  }

  // Strictly-increasing timestamp. Two ops created in the same millisecond (e.g. two
  // fast heard taps) must still replay in submit order — equal ts sorts unstably and
  // could apply set_heard=2 before set_heard=1, leaving the wrong final count.
  var _lastTs = 0
  function nextTs() {
    var t = Date.now()
    if (t <= _lastTs) t = _lastTs + 1
    _lastTs = t
    return t
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
    if (!op.ts) op.ts = nextTs()
    return send(op).then(
      function (data) { return { online: true, queued: false, data: data } },
      function (err) {
        if (isNetworkError(err)) {
          return queuePut(op).then(function () {
            // Tell the connection indicator we're offline with unsynced work.
            if (window.dispatchEvent) window.dispatchEvent(new Event('mytunes-queued'))
            return { online: false, queued: true }
          })
        }
        throw err
      }
    )
  }

  var flushing = false
  // Replay queued ops oldest-first. Stops at the first network failure (still
  // offline); drops any op the server rejects (a bad op can't succeed on replay).
  // Fires a 'mytunes-synced' window event once it has cleared at least one op, so any
  // open view (e.g. the My Tunes list) can refresh and drop its "pending" markers.
  function flush() {
    if (flushing) return Promise.resolve()
    flushing = true
    var cleared = 0
    return queueAll()
      .then(function (ops) {
        return ops.reduce(function (chain, op) {
          return chain.then(function () {
            return send(op).then(
              function () { cleared++; return queueDelete(op.op_id) },
              function (err) {
                if (isNetworkError(err)) throw err // still offline -> stop
                cleared++
                return queueDelete(op.op_id) // server rejected -> discard
              }
            )
          })
        }, Promise.resolve())
      })
      .catch(function () {})
      .then(function () {
        flushing = false
        if (cleared && window.dispatchEvent) window.dispatchEvent(new Event('mytunes-synced'))
      })
  }

  if (window.addEventListener) window.addEventListener('online', flush)

  window.MyTunesOffline = {
    submit: submit,
    flush: flush,
    pending: queueAll,
    savePopular: savePopular,
    searchPopular: searchPopular,
  }

  // Replay anything left from a previous offline session, once the page settles.
  if (window.addEventListener) {
    window.addEventListener('load', function () { setTimeout(flush, 1500) })
  }
})(window)
