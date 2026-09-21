// Recording-segmenter offline store (spec 050 "Offline") — a plain (non-module)
// global, loaded app-wide from base.html like mytunes_offline.js, so marks made
// with no signal replay from whichever page is open when the connection comes
// back, not only when the tool itself is reopened.
//
// Three stores in one IndexedDB database (`ceol-segmenter`):
//
//   ops    — the write queue. ONE entry per (recording, tune), latest wins. A
//            placement is an absolute upsert (PUT start/end) and a clear is an
//            idempotent DELETE, so only the final state of each tune matters and
//            the queue can coalesce instead of replaying every keystroke.
//   mirror — the tool's working truth per recording: the night's log with each
//            tune's placement, written after every change. The service worker
//            snapshots the page as it was LAST LOADED online; the mirror is what
//            happened since, and `generated_at` says which of the two is newer.
//   audio  — a saved copy of one encode (normally the small proxy) as a Blob,
//            played back through a blob: URL. Presigned S3 URLs need a network;
//            a blob URL seeks natively and never expires.
//
// Mirrors MyTunesOffline's shape (submit / flush / pending) so the connection
// indicator can count and drain both queues the same way.
(function (window) {
  'use strict'

  if (window.SegmenterOffline) return

  var DB_NAME = 'ceol-segmenter'
  var DB_VERSION = 1
  var OPS = 'ops'
  var MIRROR = 'mirror'
  var AUDIO = 'audio'
  var dbPromise = null

  function db() {
    if (!dbPromise) {
      dbPromise = new Promise(function (resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VERSION)
        req.onupgradeneeded = function () {
          var d = req.result
          if (!d.objectStoreNames.contains(OPS)) d.createObjectStore(OPS, { keyPath: 'key' })
          if (!d.objectStoreNames.contains(MIRROR)) d.createObjectStore(MIRROR, { keyPath: 'recording_id' })
          if (!d.objectStoreNames.contains(AUDIO)) d.createObjectStore(AUDIO, { keyPath: 'key' })
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
        // A get() with no row resolves undefined, not the request object.
        var isRequest = out && typeof out === 'object' && 'result' in out && 'readyState' in out
        tx.oncomplete = function () { resolve(isRequest ? out.result : out) }
        tx.onerror = function () { reject(tx.error) }
        tx.onabort = function () { reject(tx.error) }
      })
    })
  }

  // Strictly increasing, so two ops in one millisecond still replay in order.
  var _lastTs = 0
  function nextTs() {
    var t = Date.now()
    if (t <= _lastTs) t = _lastTs + 1
    _lastTs = t
    return t
  }

  // --- ops ------------------------------------------------------------------

  function opKey(recordingId, sitId) { return recordingId + ':' + sitId }

  function queuePut(op) { return idb(OPS, 'readwrite', function (s) { s.put(op) }) }
  function queueGet(key) { return idb(OPS, 'readonly', function (s) { return s.get(key) }) }
  function queueDelete(key) { return idb(OPS, 'readwrite', function (s) { s.delete(key) }) }

  // Delete only if the queued entry is still the one we sent. A newer op for the
  // same tune may have landed in the queue while this one was in flight; that one
  // must survive to be replayed.
  function queueDeleteIf(key, ts) {
    return queueGet(key).then(function (cur) {
      if (cur && cur.ts === ts) return queueDelete(key)
    })
  }

  // Queued ops, oldest first; for one recording when an id is given.
  function pending(recordingId) {
    return idb(OPS, 'readonly', function (s) { return s.getAll() }).then(function (all) {
      return (all || [])
        .filter(function (o) { return recordingId == null || o.recording_id === recordingId })
        .sort(function (a, b) { return a.ts - b.ts })
    })
  }

  // --- mirror ---------------------------------------------------------------

  // {recording_id, generated_at, tunes} — the tool's current picture. `generated_at`
  // is the server timestamp of the payload it was built from (edits since are
  // folded in), so a page snapshot with a lower generated_at is the older one.
  function mirrorPut(recordingId, data) {
    return idb(MIRROR, 'readwrite', function (s) {
      s.put({ recording_id: recordingId, generated_at: data.generated_at || null, tunes: data.tunes || [], ts: Date.now() })
    })
  }
  function mirrorGet(recordingId) { return idb(MIRROR, 'readonly', function (s) { return s.get(recordingId) }) }

  // --- audio ----------------------------------------------------------------

  function audioKey(recordingId, sourceId) { return recordingId + ':' + sourceId }

  function audioPut(entry) {
    entry.key = audioKey(entry.recording_id, entry.source_id)
    return idb(AUDIO, 'readwrite', function (s) { s.put(entry) })
  }
  function audioGet(recordingId, sourceId) {
    return idb(AUDIO, 'readonly', function (s) { return s.get(audioKey(recordingId, sourceId)) })
  }
  function audioDelete(recordingId, sourceId) {
    return idb(AUDIO, 'readwrite', function (s) { s.delete(audioKey(recordingId, sourceId)) })
  }
  // Every saved copy for one recording. The blobs come along (they are lazy disk
  // handles, not bytes in memory) so the page can mint blob: URLs straight away.
  function audioList(recordingId) {
    return idb(AUDIO, 'readonly', function (s) { return s.getAll() }).then(function (all) {
      return (all || []).filter(function (a) { return a.recording_id === recordingId })
    })
  }

  // Download one encode in full and keep it. `source` is an entry from the
  // payload's audio_sources ({id, url, mime_type, size_bytes}); the URL is a
  // presigned S3 GET, which the bucket's CORS rule already allows (it is the
  // same rule the <audio> element's range requests need). Progress comes from
  // Content-Length, which is a CORS-safelisted response header.
  function saveAudio(recordingId, source, opts) {
    opts = opts || {}
    var onProgress = opts.onProgress || function () {}
    // Best-effort: ask the browser not to evict the store under us. A 45MB blob
    // is exactly the kind of thing storage pressure reclaims first.
    try {
      if (window.navigator.storage && window.navigator.storage.persist) window.navigator.storage.persist().catch(function () {})
    } catch (e) { /* not available */ }
    return fetch(source.url, { mode: 'cors', cache: 'no-store', signal: opts.signal }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status)
      var type = res.headers.get('Content-Type') || source.mime_type || 'audio/mp4'
      var total = Number(res.headers.get('Content-Length')) || source.size_bytes || 0
      var loaded = 0
      var chunks = []
      var finish = function () {
        var blob = new Blob(chunks, { type: type })
        chunks = null
        var entry = {
          recording_id: recordingId,
          source_id: source.id,
          blob: blob,
          mime_type: type,
          size_bytes: blob.size,
          saved_at: Date.now(),
        }
        return audioPut(entry).then(function () { return entry })
      }
      if (!res.body || !res.body.getReader) {
        // No streaming (old WebKit): one shot, no progress.
        return res.arrayBuffer().then(function (buf) { chunks.push(buf); return finish() })
      }
      var reader = res.body.getReader()
      var pump = function () {
        return reader.read().then(function (step) {
          if (step.done) return finish()
          chunks.push(step.value)
          loaded += step.value.byteLength
          onProgress({ loaded: loaded, total: total })
          return pump()
        })
      }
      return pump()
    })
  }

  // --- network --------------------------------------------------------------

  function endpoint(op) {
    return '/api/recordings/' + op.recording_id + '/segments/' + op.session_instance_tune_id
  }

  // Send one op. Resolves the parsed JSON on a 2xx; rejects with a TypeError on
  // a network failure (offline) and a plain Error on a server-rejected op.
  function send(op) {
    var init = { method: op.kind === 'delete' ? 'DELETE' : 'PUT', credentials: 'same-origin' }
    if (op.kind !== 'delete') {
      init.headers = { 'Content-Type': 'application/json' }
      init.body = JSON.stringify({ start_ms: op.start_ms, end_ms: op.end_ms == null ? null : op.end_ms })
    }
    return fetch(endpoint(op), init).then(function (r) {
      return r.json().then(
        function (j) {
          if (!r.ok || !j.success) {
            var err = new Error((j && j.error) || ('HTTP ' + r.status))
            err.status = r.status
            throw err
          }
          return j
        },
        function () {
          var err = new Error('HTTP ' + r.status)
          err.status = r.status
          throw err
        }
      )
    })
  }

  function isNetworkError(err) {
    return err instanceof TypeError || (window.navigator && window.navigator.onLine === false)
  }

  function emit(name, detail) {
    if (!window.dispatchEvent) return
    try {
      window.dispatchEvent(new CustomEvent(name, { detail: detail || {} }))
    } catch (e) {
      window.dispatchEvent(new Event(name))
    }
  }

  // Submit an op {recording_id, session_instance_tune_id, kind:'put'|'delete',
  // start_ms, end_ms}. Online success -> {online:true, data}. Offline -> queued,
  // resolves {queued:true} (the caller keeps its optimistic mark). A server
  // rejection REJECTS and is not queued: it cannot succeed on replay either.
  function submit(op) {
    op.key = opKey(op.recording_id, op.session_instance_tune_id)
    op.ts = nextTs()
    // Coalesce first: if an older op for this tune is still waiting, this one
    // supersedes it whatever happens next — replaying the old one after a
    // successful send here would put the mark back where it was.
    return queueGet(op.key).then(function (older) {
      var pre = older ? queuePut(op) : Promise.resolve()
      return pre.then(function () {
        return send(op).then(
          function (data) {
            return queueDeleteIf(op.key, op.ts).then(function () {
              return { online: true, queued: false, data: data }
            })
          },
          function (err) {
            if (isNetworkError(err)) {
              return queuePut(op).then(function () {
                emit('segmenter-queued', { recording_id: op.recording_id })
                return { online: false, queued: true }
              })
            }
            // Rejected outright: make sure no superseded copy lingers either.
            return queueDeleteIf(op.key, op.ts).then(function () { throw err })
          }
        )
      })
    })
  }

  var flushing = false
  // Replay queued ops oldest-first. Stops at the first network failure (still
  // offline); drops any op the server rejects, reporting it so the page can put
  // its mark back. Fires 'segmenter-synced' once it has cleared at least one op.
  function flush() {
    if (flushing) return Promise.resolve()
    flushing = true
    var cleared = 0
    var rejected = []
    var touched = {}
    return pending()
      .then(function (ops) {
        return ops.reduce(function (chain, op) {
          return chain.then(function () {
            return send(op).then(
              function () {
                cleared++
                touched[op.recording_id] = true
                return queueDeleteIf(op.key, op.ts)
              },
              function (err) {
                if (isNetworkError(err)) throw err // still offline -> stop
                // A DELETE for a tune the server never had is the queue's own
                // doing (placed then cleared, both offline): nothing to report.
                if (!(op.kind === 'delete' && err.status === 404)) {
                  rejected.push({ key: op.key, recording_id: op.recording_id, session_instance_tune_id: op.session_instance_tune_id, error: err.message })
                }
                cleared++
                touched[op.recording_id] = true
                return queueDeleteIf(op.key, op.ts)
              }
            )
          })
        }, Promise.resolve())
      })
      .catch(function () {})
      .then(function () {
        flushing = false
        if (cleared) {
          emit('segmenter-synced', {
            cleared: cleared,
            rejected: rejected,
            recording_ids: Object.keys(touched).map(Number),
          })
        }
      })
  }

  if (window.addEventListener) window.addEventListener('online', flush)

  window.SegmenterOffline = {
    submit: submit,
    flush: flush,
    pending: pending,
    mirrorPut: mirrorPut,
    mirrorGet: mirrorGet,
    audioList: audioList,
    audioGet: audioGet,
    audioDelete: audioDelete,
    saveAudio: saveAudio,
  }

  // Replay anything left from a previous offline session, once the page settles.
  if (window.addEventListener) {
    window.addEventListener('load', function () { setTimeout(flush, 1500) })
  }
})(window)
