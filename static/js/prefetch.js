// Background offline warm-up: proactively cache the shells (+ tab data) of the major
// pages so they work offline without having visited each one. Bounded and throttled:
//   - runs on idle, online only, and skips when data-saver is on
//   - at most once every WARM_INTERVAL_MS (tracked in localStorage)
//   - caps how many sessions it warms
//
// Reuses existing plumbing: the service worker's 'cache-page' message snapshots a page
// (authed) into the per-user cache, and a plain fetch() of an /api/* GET lands in the
// Tier 1 cache. So warming a session = snapshot its page + fetch its tab endpoints.
(function (window, document) {
  'use strict'
  if (window.CeolPrefetch) return

  var WARM_KEY = 'ceol_prefetch_at'
  var WARM_INTERVAL_MS = 6 * 60 * 60 * 1000 // 6h
  var SESSION_CAP = 25
  var GAP_MS = 250 // small gap between sessions so we never hammer the server

  function recentlyWarmed() {
    try { return Date.now() - (parseInt(window.localStorage.getItem(WARM_KEY) || '0', 10)) < WARM_INTERVAL_MS } catch (e) { return false }
  }
  function markWarmed() { try { window.localStorage.setItem(WARM_KEY, String(Date.now())) } catch (e) {} }

  function skip() {
    if (typeof navigator === 'undefined' || navigator.onLine === false) return true
    if (navigator.connection && navigator.connection.saveData) return true // respect data-saver
    return !('serviceWorker' in navigator)
  }

  function delay(ms) { return new Promise(function (r) { setTimeout(r, ms) }) }

  // Ask the worker to snapshot a same-origin page into the per-user cache.
  function cachePage(url) {
    if (!navigator.serviceWorker || !navigator.serviceWorker.ready) return Promise.resolve()
    return navigator.serviceWorker.ready
      .then(function (reg) {
        var sw = reg.active || navigator.serviceWorker.controller
        if (sw) sw.postMessage({ type: 'cache-page', url: url })
      })
      .catch(function () {})
  }

  // Fetch a GET so the Tier 1 SW cache stores it (best-effort; ignore failures).
  function warmApi(url) { return fetch(url, { credentials: 'same-origin' }).then(function () {}, function () {}) }

  function warmSession(path) {
    return cachePage('/sessions/' + path)
      .then(function () { return warmApi('/api/sessions/' + path + '/people') })
      .then(function () { return warmApi('/api/sessions/' + path + '/logs') })
      .then(function () { return warmApi('/api/sessions/' + path + '/tunes/remaining') })
  }

  function warm() {
    if (skip() || recentlyWarmed()) return
    fetch('/api/my-sessions?limit=' + SESSION_CAP, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null })
      .then(function (d) {
        if (!d || !d.sessions) return // not logged in / nothing to warm
        markWarmed()
        var chain = cachePage('/sessions')
        d.sessions.slice(0, SESSION_CAP).forEach(function (s) {
          chain = chain.then(function () { return delay(GAP_MS) }).then(function () { return warmSession(s.path) })
        })
        return chain
      })
      .catch(function () {})
  }

  // Only warm from a "hub" page the user tends to land on, and only after a delay — so
  // the burst of background fetches never competes with the user's initial navigation
  // (which, on a loaded server, can disrupt in-flight requests like the logout redirect).
  function isHub() {
    var p = window.location.pathname
    return p === '/' || p === '/sessions' || p === '/sessions/'
  }
  function schedule() {
    if (skip() || !isHub()) return
    setTimeout(function () {
      if (skip()) return
      if (window.requestIdleCallback) window.requestIdleCallback(warm, { timeout: 5000 })
      else warm()
    }, 5000)
  }

  window.CeolPrefetch = { warm: warm }

  if (document.readyState === 'complete') schedule()
  else window.addEventListener('load', schedule)
})(window, document)
