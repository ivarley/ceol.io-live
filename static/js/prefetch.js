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
  // Gap between warmed sessions. Generous on purpose: a full cycle is ~30 page
  // renders + ~35 API calls, and every one of them competes with the user's
  // next click for a server worker. Warming is never urgent; navigation is.
  var GAP_MS = 1000

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

  // Read a page's HTML back out of Cache Storage after cachePage() stored it.
  // CacheStorage.match searches every cache for this origin, so this finds the
  // worker's per-user page snapshot without knowing its name. Polls briefly
  // because cachePage() is a postMessage — fire-and-forget, so the entry lands
  // some time after the call returns.
  function cachedHtml(url, tries) {
    if (!window.caches) return Promise.resolve('')
    return caches.match(new Request(url, { credentials: 'same-origin' }))
      .then(function (res) {
        if (res) return res.text()
        if ((tries || 0) >= 10) return ''
        return delay(200).then(function () { return cachedHtml(url, (tries || 0) + 1) })
      })
      .catch(function () { return '' })
  }

  // Cache a page's static subresources (its stylesheets + scripts) so the warmed page
  // renders styled/interactive offline — cache-page only stores the HTML, not its assets.
  //
  // The HTML comes from the snapshot the worker just cached, NOT from a second
  // network fetch. The old version re-fetched every warmed URL purely to read its
  // <link>/<script> tags, so each warmed page cost two full server renders instead
  // of one — on a warm-up that already covers ~30 pages.
  //
  // seenAssets skips assets already requested this cycle: /static/ URLs are
  // content-hash stamped and mostly shared via base.html, so without it nearly
  // every warmed page would re-request the same two dozen files.
  var seenAssets = Object.create(null)
  function warmPageAssets(url) {
    return cachedHtml(url)
      .then(function (html) {
        if (!html) return
        var doc = new DOMParser().parseFromString(html, 'text/html')
        var urls = []
        doc.querySelectorAll('link[rel="stylesheet"][href], script[src]').forEach(function (el) {
          var u = el.getAttribute('href') || el.getAttribute('src')
          if (u && u.indexOf('/static/') === 0 && !seenAssets[u] && urls.indexOf(u) === -1) urls.push(u)
        })
        var chain = Promise.resolve()
        urls.forEach(function (u) {
          seenAssets[u] = true
          chain = chain.then(function () { return warmApi(u) })
        })
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
      .then(function () { return warmPage('/sessions') })
      .then(function () { return warmApi('/api/sessions/with-today-status') }) // what /sessions renders from
      // Not sync(true): the force flag bypassed offline_data.js's own 5-minute
      // throttle, so the whole tunebook + notation bundle was re-pulled on every
      // warm cycle. Let that throttle do its job.
      .then(function () { return window.CeolOffline ? window.CeolOffline.sync() : null })
  }

  var warming = false
  function warm() {
    if (warming || skip() || recentlyWarmed()) return
    warming = true
    // Claim the 10-minute window UP FRONT, not on completion.
    //
    // This used to be called only after the entire chain resolved — which takes
    // minutes for 25 sessions — while `warming` is a module-level flag that every
    // full page navigation resets. So the marker was essentially never written:
    // each click scheduled another complete warm-up, and the user's next
    // navigation queued behind dozens of background requests. That was the
    // 3-10s "nothing happens when I click a link".
    //
    // The trade-off is that an interrupted cycle waits out the window instead of
    // resuming. That's the right way round: warming is best-effort and repeats,
    // navigation latency is not.
    markWarmed()
    warmCorePages()
      .then(function () {
        return fetch('/api/my-sessions?limit=' + SESSION_CAP, { credentials: 'same-origin' })
          .then(function (r) { return r.ok ? r.json() : null })
          .then(function (d) {
            if (!d || !d.sessions) return
            var chain = Promise.resolve() // /sessions already warmed by warmCorePages
            d.sessions.slice(0, SESSION_CAP).forEach(function (s) {
              chain = chain.then(function () { return delay(GAP_MS) }).then(function () { return warmSession(s.path) })
            })
            return chain
          })
      })
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
