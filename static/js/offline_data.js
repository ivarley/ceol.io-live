// Offline data mirror (take 2). One predictable payload — the user's whole tunebook
// (with incipit notation) + popular tunes — synced into IndexedDB on load, so the UI can
// read/search the user's own data offline instead of relying on per-endpoint/per-page
// caching that has to be warmed at the right time. See GET /api/offline/bundle.
//
// Exposes window.CeolOffline: { sync, getTune, getTunes, searchTunes }.
(function (window) {
  'use strict'
  if (window.CeolOffline) return

  var DB_NAME = 'ceol-offline'
  var DB_VERSION = 1
  var TUNES = 'tunes' // the user's tunebook (keyPath tune_id)
  var POPULAR = 'popular' // top catalog tunes (keyPath tune_id)
  var META = 'meta' // {key,value}
  var SYNC_MIN_MS = 5 * 60 * 1000 // don't re-sync more than this often
  var dbPromise = null

  function db() {
    if (!dbPromise) {
      dbPromise = new Promise(function (resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VERSION)
        req.onupgradeneeded = function () {
          var d = req.result
          if (!d.objectStoreNames.contains(TUNES)) d.createObjectStore(TUNES, { keyPath: 'tune_id' })
          if (!d.objectStoreNames.contains(POPULAR)) d.createObjectStore(POPULAR, { keyPath: 'tune_id' })
          if (!d.objectStoreNames.contains(META)) d.createObjectStore(META, { keyPath: 'key' })
        }
        req.onsuccess = function () { resolve(req.result) }
        req.onerror = function () { reject(req.error) }
      })
    }
    return dbPromise
  }

  function tx(stores, mode, fn) {
    return db().then(function (d) {
      return new Promise(function (resolve, reject) {
        var t = d.transaction(stores, mode)
        var out = fn(t)
        t.oncomplete = function () { resolve(out) }
        t.onerror = function () { reject(t.error) }
        t.onabort = function () { reject(t.error) }
      })
    })
  }

  function getAll(store) {
    return db().then(function (d) {
      return new Promise(function (resolve, reject) {
        var req = d.transaction(store, 'readonly').objectStore(store).getAll()
        req.onsuccess = function () { resolve(req.result || []) }
        req.onerror = function () { reject(req.error) }
      })
    })
  }

  function getOne(store, key) {
    return db().then(function (d) {
      return new Promise(function (resolve, reject) {
        var req = d.transaction(store, 'readonly').objectStore(store).get(key)
        req.onsuccess = function () { resolve(req.result || null) }
        req.onerror = function () { reject(req.error) }
      })
    })
  }

  function replaceStore(store, items) {
    abcKeyCache = {} // the incipits just changed
    return tx([store], 'readwrite', function (t) {
      var os = t.objectStore(store)
      os.clear()
      ;(items || []).forEach(function (it) { if (it && it.tune_id != null) os.put(it) })
    })
  }

  function normalize(s) {
    return (s || '').replace(/[\u2018\u2019\u201B`\u00B4]/g, "'").toLowerCase().trim().replace(/^the\s+/, '')
  }

  // --- notation (ABC) search ------------------------------------------------
  //
  // Hand-copied from frontend/src/shared/abcquery.js: this file loads from base.html,
  // outside every Vite bundle, so it cannot import. Keep the two in step -- and both in
  // step with SQL abc_search_key() (schema/055_abc_search_index.sql), or a query that
  // matches online stops matching offline.
  var ABC_MIN_QUERY_LEN = 3
  var ABC_ORNAMENT_RE = /\{[^}]*\}|"[^"]*"/g   // grace notes, chord symbols
  var ABC_NOISE_RE = /[\s!]/g                  // whitespace, legacy line breaks
  var ABC_FRIENDLY_RE = /^[A-Ga-gxz0-9|^_=,'/()[\]:<>~-]+$/

  function normAbc(s) {
    return (s || '').replace(ABC_ORNAMENT_RE, '').replace(ABC_NOISE_RE, '').toLowerCase()
  }

  // The needle a notation search should use, or '' when this query isn't note-shaped.
  function abcNeedle(q) {
    var key = normAbc(q)
    return key.length >= ABC_MIN_QUERY_LEN && ABC_FRIENDLY_RE.test(key) ? key : ''
  }

  // Normalizing every incipit on every keystroke is wasteful, and the tunebook only
  // changes on sync -- so memoize by tune_id and drop the cache when a store is replaced.
  var abcKeyCache = {}
  function abcKeyFor(t) {
    var id = t.tune_id
    if (abcKeyCache[id] === undefined) abcKeyCache[id] = normAbc(t.incipit_abc)
    return abcKeyCache[id]
  }

  var syncing = false
  // Pull the bundle and mirror it locally. Skips if synced recently or offline.
  function sync(force) {
    if (syncing) return Promise.resolve()
    return getOne(META, 'synced_at')
      .then(function (m) {
        var last = m ? m.value : 0
        if (!force && Date.now() - last < SYNC_MIN_MS) return
        if (typeof navigator !== 'undefined' && navigator.onLine === false) return
        syncing = true
        return fetch('/api/offline/bundle', { credentials: 'same-origin' })
          .then(function (r) { return r.ok ? r.json() : null })
          .then(function (d) {
            if (!d || !d.success) return
            return replaceStore(TUNES, d.tunes)
              .then(function () { return replaceStore(POPULAR, d.popular) })
              .then(function () { return tx([META], 'readwrite', function (t) { t.objectStore(META).put({ key: 'synced_at', value: Date.now() }) }) })
          })
      })
      .catch(function () {})
      .then(function () { syncing = false })
  }

  // A tune (with incipit notation) by catalog id — from the tunebook first, else popular.
  function getTune(tuneId) {
    var id = Number(tuneId)
    return getOne(TUNES, id).then(function (t) { return t || getOne(POPULAR, id) })
  }

  function getTunes() { return getAll(TUNES) }

  // Offline search: the user's tunes first, then popular (deduped), capped. Names first,
  // then -- for a note-shaped query -- NOTATION matches appended and flagged, mirroring
  // how the server blends them online.
  //
  // Offline notation matching is INCIPIT-ONLY: the bundle deliberately carries only
  // `incipit_abc`, never the full setting ABC, to bound the payload. So offline a query
  // matching bar 20 of a tune finds nothing while online it does -- hence `abc_scope`,
  // which lets the UI say "opening bars" rather than quietly under-answering.
  function searchTunes(query, limit) {
    var q = normalize(query)
    var needle = abcNeedle(query)
    limit = limit || 12
    return Promise.all([getAll(TUNES), getAll(POPULAR)]).then(function (res) {
      var mine = res[0], pop = res[1]
      var seen = {}
      var out = []
      var push = function (list, match, tag) {
        list.forEach(function (t) {
          if (out.length >= limit) return
          if (!t || seen[t.tune_id]) return
          if (!match(t)) return
          seen[t.tune_id] = true
          out.push(tag ? Object.assign({}, t, { abc_only: true, abc_scope: 'incipit' }) : t)
        })
      }
      var byPop = function (a, b) { return (b.tunebook_count || 0) - (a.tunebook_count || 0) }
      var byName = function (t) { return normalize(t.name).indexOf(q) !== -1 }
      var byAbc = function (t) { return abcKeyFor(t).indexOf(needle) !== -1 }
      var sortedMine = mine.slice().sort(byPop)
      var sortedPop = pop.slice().sort(byPop)
      push(sortedMine, byName) // owned name matches first
      push(sortedPop, byName) // then popular name matches
      if (needle) {
        push(sortedMine, byAbc, true) // then notation, same ordering, deduped by `seen`
        push(sortedPop, byAbc, true)
      }
      return out
    })
  }

  window.CeolOffline = { sync: sync, getTune: getTune, getTunes: getTunes, searchTunes: searchTunes }

  // Mirror on load (throttled) so offline reads are fresh-ish.
  if (window.addEventListener) {
    window.addEventListener('load', function () { setTimeout(function () { sync() }, 800) })
    window.addEventListener('online', function () { sync() })
  }
})(window)
