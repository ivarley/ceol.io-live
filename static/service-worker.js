// Main-app service worker — Tier 0 offline resilience.
//
// Served from /sw.js (see app.py) so its scope is the whole origin: it controls
// every navigation EXCEPT the live logger, which has its own /live/-scoped worker
// (static/live-sw.js) that wins for /live/* by scope specificity.
//
// Policy (mirrors live-sw.js): NETWORK-FIRST, cache fallback — EXCEPT static assets
// carrying a content-hash version (?v=<hash>, stamped by Flask's url_for): their URL
// changes whenever their content changes, so an exact-URL cache hit can never be a
// stale build and they're served CACHE-FIRST (the site-wide slow-network win: a page
// load waits only for the HTML document). Unversioned requests keep network-first —
// a fixed-name asset served cache-first could strand users on a stale build.
// Never our concern (straight to network): /api/*, /live/*, /admin*, non-GET and the
// logout flow. The legacy word-processor editor is fetched live but never snapshotted
// (the server marks it X-Offline-Exclude).
//
// TWO non-obvious correctness rules, both learned from breaking the logout e2e test:
//   1. handleNav AWAITS a cache handle BEFORE issuing the navigation fetch. That await
//      yields long enough for SW activation (clients.claim) to settle; firing fetch()
//      synchronously while the worker is still claiming makes Chromium drop the
//      navigation's Set-Cookie and mangle auth redirects.
//   2. Activation must stay INSTANT — precache is done from a post-load 'init' message,
//      NEVER in install's waitUntil. A slow install delays claim so it lands mid-burst
//      and corrupts an in-flight navigation the same way.
// Navigation preload (enabled in activate) is what makes rule 1 cheap: the browser
// issues the document request itself, in parallel with booting this worker, so the
// awaits in rule 1 no longer sit in front of the network. It does NOT violate rule 1 —
// the preload is browser-managed (cookies handled natively), and handleNav still
// performs those awaits before consuming the response.
// Data is never stored here.

const VERSION = 'v33'
const SHELL = `ceol-io-shell-${VERSION}` // shared, non-personalized assets + public/help pages
// Page/api caches are VERSION-scoped too, so a VERSION bump (e.g. a deploy) invalidates
// stale page snapshots + cached API data, not just the shell.
const pagesCache = (uid) => `ceol-io-pages-${VERSION}-${uid}` // per-user HTML snapshots (no cross-user leak)
const apiCache = (uid) => `ceol-io-api-${VERSION}-${uid}` // per-user GET /api/* responses (Tier 1)
const UID_MARKER = '/__ceol_uid__'

// Non-personalized shell, precached (from the 'init' message) best-effort.
const PRECACHE = [
  '/offline',
  '/help',
  '/help/sessions',
  '/help/offline',
  '/help/my-tunes',
  '/help/session-tracking/tunes',
  '/help/session-tracking/logs',
  '/help/session-tracking/members',
  '/static/css/theme.css',
  '/static/css/hamburger_menu.css',
  '/static/css/tune_detail_modal.css',
  '/static/css/tune-search.css',
  '/static/js/hamburger_menu.js',
  '/static/js/connection_status.js',
  '/static/js/offline_data.js',
  '/static/js/prefetch.js',
  '/static/js/utils/unaccent.js',
  '/static/tunesheet/sheet.js',
  '/static/js/tunebook_status.js',
  '/static/js/mytunes_offline.js',
  '/static/js/components/TuneSearchComponent.js',
  '/static/manifest.json',
  '/static/images/logo3-1.png',
  '/static/images/favicon.ico',
  '/static/images/apple-touch-icon.png',
  '/static/images/android-chrome-192x192.png',
  '/static/images/android-chrome-512x512.png',
  // Cross-origin CDN shell deps (cached opaque; served on the offline fallback).
  'https://fonts.googleapis.com/css?family=Poppins:300,400,500,600,700&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/lz-string/1.5.0/lz-string.min.js',
]
const CDN = new Set(PRECACHE.filter((u) => u.startsWith('http')))

self.addEventListener('install', () => {
  // Instant — NO precache here (see rule 2 in the header).
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  // Prune ONLY our own old shell caches. Never a blanket caches.delete() — that would
  // wipe the live logger's ceol-live-shell-* cache. Per-user page caches are pruned on
  // user change (the 'init' message), not here.
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          // Delete every ceol-io-* cache from a previous VERSION (shell, pages, api).
          keys
            .filter((k) => k.startsWith('ceol-io-') && k !== SHELL && !k.includes(`-${VERSION}-`))
            .map((k) => caches.delete(k))
        )
      )
      // Navigation preload: let the browser start the document request in
      // PARALLEL with booting this worker, instead of after it. The worker gets
      // idle-killed after ~30s, so most clicks were paying a cold start before
      // handleNav could even call fetch() — dead time where the old page just
      // sits there. Not supported everywhere; guard it.
      .then(() =>
        self.registration.navigationPreload
          ? self.registration.navigationPreload.enable().catch(() => {})
          : undefined
      )
      .then(() => self.clients.claim())
  )
})

// The current user id, persisted in a cache marker so it survives SW restarts.
let uidPromise = null
function currentUid() {
  if (!uidPromise) {
    uidPromise = caches
      .open(SHELL)
      .then((c) => c.match(UID_MARKER))
      .then((r) => (r ? r.text() : 'anon'))
      .catch(() => 'anon')
  }
  return uidPromise
}

let precached = false
function precache() {
  if (precached) return
  precached = true
  // Deferred (~2s): precache fires its many requests AFTER the user's initial navigation
  // burst, so a flood of background fetches can't starve / race an in-flight navigation
  // (which corrupts that navigation's cookies on a loaded server). Best-effort; if the
  // worker is killed first it simply retries on the next load.
  self.setTimeout(() => {
    caches.open(SHELL).then((c) =>
      Promise.all(
        PRECACHE.map((u) =>
          c.add(new Request(u, { mode: u.startsWith('http') ? 'no-cors' : 'same-origin' })).catch(() => {})
        )
      )
    )
  }, 2000)
}

self.addEventListener('message', (event) => {
  const data = event.data || {}
  if (data.type === 'SKIP_WAITING') {
    self.skipWaiting()
    return
  }
  if (data.type === 'cache-page' && data.url) {
    // Snapshot another same-origin page into this user's page cache so it's reachable
    // offline even if never directly visited (e.g. the prefetch warm-up snapshotting /sessions).
    // Uses the worker's own credentialed fetch, so it stores the authed page, not a
    // login redirect.
    event.waitUntil(
      (async () => {
        try {
          const u = new URL(data.url, self.location.origin)
          if (u.origin !== self.location.origin) return
          const res = await fetch(u.href, { credentials: 'same-origin' })
          if (!res || !res.ok || res.redirected || res.headers.get('X-Offline-Exclude') != null) return
          const cache = await caches.open(pagesCache(await currentUid()))
          await cache.put(u.href, res)
        } catch (e) {
          /* best-effort */
        }
      })()
    )
    return
  }
  if (data.type === 'init') {
    const uid = String(data.uid == null ? 'anon' : data.uid)
    uidPromise = Promise.resolve(uid)
    precache() // post-load, off the lifecycle critical path
    event.waitUntil(
      (async () => {
        const shell = await caches.open(SHELL)
        await shell.put(UID_MARKER, new Response(uid))
        // Drop every other user's cached pages AND api responses so a shared device
        // can't leak one user's personalized data (e.g. /api/my-tunes) to the next.
        const keys = await caches.keys()
        await Promise.all(
          keys
            .filter(
              (k) =>
                (k.startsWith('ceol-io-pages-') && k !== pagesCache(uid)) ||
                (k.startsWith('ceol-io-api-') && k !== apiCache(uid))
            )
            .map((k) => caches.delete(k))
        )
      })()
    )
  }
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  if (url.origin === self.location.origin) {
    // The live logger owns its own data + worker — never touch it.
    if (url.pathname.startsWith('/api/live/')) return
    if (url.pathname.startsWith('/live/')) return
    if (url.pathname === '/logout') return
    // NOTE: /admin is intentionally NOT bypassed — admin navigations still go through
    // handleNav so they show the offline page (rather than a browser error) when
    // offline. handleNav skips snapshotting them, so admin is never cached for offline.

    // Tier 1: GET /api/* — network-first into a per-user cache so the AJAX-driven
    // pages (My Tunes, Common Tunes, session-detail tabs) have data offline. Writes
    // are POST/PUT/DELETE and already bypassed above (method !== GET).
    if (url.pathname.startsWith('/api/')) {
      event.respondWith(handleApi(req))
      return
    }

    if (req.mode === 'navigate') {
      event.respondWith(handleNav(req, event))
      return
    }
    if (url.pathname.startsWith('/static/')) {
      // Content-hash versioned (?v=) -> immutable, cache-first. Anything else keeps
      // network-first (its filename can be reused across builds).
      event.respondWith(url.searchParams.has('v') ? cacheFirstVersioned(req, SHELL) : networkFirst(req, SHELL))
      return
    }
    return
  }

  // Cross-origin: only the CDN shell deps we precached.
  if (CDN.has(req.url)) {
    event.respondWith(networkFirst(req, SHELL))
  }
})

// HTML navigations, network-first. The leading awaits (currentUid + caches.open) are
// LOad-bearing — they settle SW activation before the fetch (header rule 1). Online:
// return the live page and snapshot it per-user for offline. Offline: this user's
// snapshot, then the shared shell, then the offline page.
async function handleNav(req, event) {
  // Kick off the preloaded response (started before this worker booted) BEFORE
  // the two awaits below, so those settle concurrently with the network rather
  // than in front of it.
  const preload = event && event.preloadResponse ? event.preloadResponse : null
  const uid = await currentUid()
  const cache = await caches.open(pagesCache(uid))
  try {
    const res = (preload && (await preload)) || (await fetch(req))
    // Snapshot for offline — but never cache admin (excluded from offline support) or
    // pages the server marks X-Offline-Exclude (the legacy editor). They still get the
    // offline page on failure below; they just aren't stored.
    if (
      res && res.ok && !res.redirected &&
      res.headers.get('X-Offline-Exclude') == null &&
      !new URL(req.url).pathname.startsWith('/admin')
    ) {
      cache.put(req, res.clone())
    }
    return res
  } catch (e) {
    const shell = await caches.open(SHELL)
    // ignoreSearch so query-param variants of a page (e.g. My Tunes filter/sort URLs,
    // which the route ignores and the page applies client-side) share one snapshot.
    const hit =
      (await cache.match(req)) ||
      (await cache.match(req, { ignoreSearch: true })) ||
      (await shell.match(req)) ||
      (await shell.match(req, { ignoreSearch: true })) ||
      (await caches.match('/offline'))
    if (hit) return hit
    throw e
  }
}

// GET /api/* — network-first into the per-user API cache. Online always returns fresh
// (so a page never shows stale data while connected); offline returns the last response
// seen. Only successful, non-redirected responses are cached.
async function handleApi(req) {
  const uid = await currentUid()
  const cache = await caches.open(apiCache(uid))
  try {
    const res = await fetch(req)
    if (res && res.ok && !res.redirected) cache.put(req, res.clone())
    return res
  } catch (e) {
    let hit = await cache.match(req)
    // The My Tunes list is the whole collection, fetched with varying sort/pagination
    // params but filtered/sorted CLIENT-side, so any cached variant serves offline.
    if (!hit && new URL(req.url).pathname === '/api/my-tunes') {
      hit = await cache.match(req, { ignoreSearch: true })
    }
    if (hit) return hit
    // Nothing cached and offline: resolve with a 503 (not a thrown network error) so the
    // page's own catch handles it cleanly and the SW doesn't log an uncaught rejection.
    return new Response(JSON.stringify({ success: false, error: 'offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName)
  try {
    const res = await fetch(req)
    if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone())
    return res
  } catch (e) {
    let hit = await cache.match(req)
    // Offline fallback for an UNVERSIONED static request: a versioned copy of the same
    // file (cached from a page's ?v= reference) is at least as fresh as anything else
    // we could serve, so don't fail just because the query strings differ.
    if (!hit && new URL(req.url).pathname.startsWith('/static/')) {
      hit = await cache.match(req, { ignoreSearch: true })
    }
    if (hit) return hit
    throw e
  }
}

// Content-hash versioned static asset (?v=<hash>): the exact URL is immutable, so a
// cache hit is always correct — no revalidation, no network wait. On first fetch of a
// new version, superseded versions of the same file are pruned so the cache doesn't
// accumulate one entry per deploy. Offline with no exact hit, any older version of the
// file (ignoreSearch) beats a broken page — same staleness the offline fallback always had.
async function cacheFirstVersioned(req, cacheName) {
  const cache = await caches.open(cacheName)
  const hit = await cache.match(req)
  if (hit) return hit
  try {
    const res = await fetch(req)
    if (res && res.ok) {
      const path = new URL(req.url).pathname
      const keys = await cache.keys()
      await Promise.all(
        keys
          .filter((k) => k.url !== req.url && new URL(k.url).pathname === path && new URL(k.url).searchParams.has('v'))
          .map((k) => cache.delete(k))
      )
      cache.put(req, res.clone())
    }
    return res
  } catch (e) {
    const stale = await cache.match(req, { ignoreSearch: true })
    if (stale) return stale
    throw e
  }
}
