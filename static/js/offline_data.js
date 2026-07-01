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
    return tx([store], 'readwrite', function (t) {
      var os = t.objectStore(store)
      os.clear()
      ;(items || []).forEach(function (it) { if (it && it.tune_id != null) os.put(it) })
    })
  }

  function normalize(s) {
    return (s || '').replace(/[\u2018\u2019\u201B`\u00B4]/g, "'").toLowerCase().trim().replace(/^the\s+/, '')
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

  // Offline name search: the user's tunes first, then popular (deduped), capped.
  function searchTunes(query, limit) {
    var q = normalize(query)
    limit = limit || 12
    return Promise.all([getAll(TUNES), getAll(POPULAR)]).then(function (res) {
      var mine = res[0], pop = res[1]
      var seen = {}
      var out = []
      var push = function (list) {
        list.forEach(function (t) {
          if (out.length >= limit) return
          if (!t || seen[t.tune_id]) return
          if (normalize(t.name).indexOf(q) === -1) return
          seen[t.tune_id] = true
          out.push(t)
        })
      }
      var byPop = function (a, b) { return (b.tunebook_count || 0) - (a.tunebook_count || 0) }
      push(mine.slice().sort(byPop)) // owned matches first
      push(pop.slice().sort(byPop)) // then popular
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
