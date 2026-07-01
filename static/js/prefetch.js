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
  var WARM_INTERVAL_MS = 10 * 60 * 1000 // 10 min — refresh offline caches while browsing
  var SESSION_CAP = 25
  var GAP_MS = 250 // small gap between requests so we never hammer the server

  function recentlyWarmed() {
    try { return Date.now() - (parseInt(window.localStorage.getItem(WARM_KEY) || '0', 10)) < WARM_INTERVAL_MS } catch (e) { return false }
  }
  function markWarmed() { try { window.localStorage.setItem(WARM_KEY, String(Date.now())) } catch (e) {} }

  function skip() {
    if (typeof navigator === 'undefined' || navigator.onLine === false) return true
    if (navigator.webdriver) return true // don't fan out background fetches under automation (e2e)
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

  // Fetch a GET so the Tier 1 / static SW cache stores it (best-effort; ignore failures).
  function warmApi(url) { return fetch(url, { credentials: 'same-origin' }).then(function () {}, function () {}) }

  // Cache a page's static subresources (its stylesheets + scripts) so the warmed page
  // renders styled/interactive offline — cache-page only stores the HTML, not its assets.
  function warmPageAssets(url) {
    return fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.ok && !r.redirected ? r.text() : '' })
      .then(function (html) {
        if (!html) return
        var doc = new DOMParser().parseFromString(html, 'text/html')
        var urls = []
        doc.querySelectorAll('link[rel="stylesheet"][href], script[src]').forEach(function (el) {
          var u = el.getAttribute('href') || el.getAttribute('src')
          if (u && u.indexOf('/static/') === 0 && urls.indexOf(u) === -1) urls.push(u)
        })
        var chain = Promise.resolve()
        urls.forEach(function (u) { chain = chain.then(function () { return warmApi(u) }) })
        return chain
      })
      .catch(function () {})
  }

  // Snapshot a page (HTML) AND cache its static assets so it renders properly offline.
  function warmPage(url) {
    return cachePage(url).then(function () { return warmPageAssets(url) })
  }

  function warmSession(path) {
    return warmPage('/sessions/' + path)
      .then(function () { return warmApi('/api/sessions/' + path + '/people') })
      .then(function () { return warmApi('/api/sessions/' + path + '/logs') })
      .then(function () { return warmApi('/api/sessions/' + path + '/tunes/remaining') })
  }

  // The core personal pages (+ the exact data those pages fetch) so they work offline
  // without being visited. My Tunes first — the most common next hop from home.
  function warmCorePages() {
    return warmPage('/my-tunes')
      .then(function () { return warmApi('/api/my-tunes?per_page=2000&sort=alpha-asc') })
      .then(function () { return warmPage('/') })
      .then(function () { return warmPage('/my-tunes/add') })
      .then(function () { return warmPage('/sessions') })
      .then(function () { return warmApi('/api/sessions/with-today-status') }) // what /sessions renders from
      .then(function () { return window.CeolOffline ? window.CeolOffline.sync(true) : null }) // tunebook + notation + popular
  }

  var warming = false
  function warm() {
    if (warming || skip() || recentlyWarmed()) return
    warming = true
    warmCorePages()
      .then(function () {
        return fetch('/api/my-sessions?limit=' + SESSION_CAP, { credentials: 'same-origin' })
          .then(function (r) { return r.ok ? r.json() : null })
          .then(function (d) {
            if (!d || !d.sessions) return
            var chain = cachePage('/sessions')
            d.sessions.slice(0, SESSION_CAP).forEach(function (s) {
              chain = chain.then(function () { return delay(GAP_MS) }).then(function () { return warmSession(s.path) })
            })
            return chain
          })
      })
      .then(function () { markWarmed() }) // only mark done once it actually completed
      .catch(function () {})
      .then(function () { warming = false })
  }

  function schedule() {
    if (skip()) return
    // Fire on any authed page load (deduped ~10 min via WARM_KEY), a couple of seconds
    // after load — long enough not to compete with the user's initial navigation, short
    // enough to be cached before they click on. (Not requestIdleCallback: right after a
    // hard reload / SW install the page may never report "idle" for a while.)
    setTimeout(warm, 2000)
  }

  window.CeolPrefetch = { warm: warm, warmPage: warmPage }

  if (document.readyState === 'complete') schedule()
  else window.addEventListener('load', schedule)
})(window, document)
