// Main-app service worker — Tier 0 offline resilience.
//
// Served from /sw.js (see app.py) so its scope is the whole origin: it controls
// every navigation EXCEPT the live logger, which has its own /live/-scoped worker
// (static/live-sw.js) that wins for /live/* by scope specificity.
//
// Policy (mirrors live-sw.js): NETWORK-FIRST, cache fallback. Asset filenames are
// fixed (no fingerprint), so cache-first would strand users on a stale build —
// online always gets the latest and the cache is purely the offline fallback.
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
// Data is never stored here.

const VERSION = 'v1'
const SHELL = `ceol-io-shell-${VERSION}` // shared, non-personalized assets + public/help pages
const pagesCache = (uid) => `ceol-io-pages-${uid}` // per-user HTML snapshots (no cross-user leak)
const UID_MARKER = '/__ceol_uid__'

// Non-personalized shell, precached (from the 'init' message) best-effort.
const PRECACHE = [
  '/offline',
  '/help',
  '/help/sessions',
  '/help/my-tunes',
  '/help/session-tracking/tunes',
  '/help/session-tracking/logs',
  '/help/session-tracking/members',
  '/static/css/theme.css',
  '/static/css/hamburger_menu.css',
  '/static/css/tune_detail_modal.css',
  '/static/js/hamburger_menu.js',
  '/static/js/utils/unaccent.js',
  '/static/js/tune_detail_modal.js',
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
          keys.filter((k) => k.startsWith('ceol-io-shell-') && k !== SHELL).map((k) => caches.delete(k))
        )
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
  if (data.type === 'init') {
    const uid = String(data.uid == null ? 'anon' : data.uid)
    uidPromise = Promise.resolve(uid)
    precache() // post-load, off the lifecycle critical path
    event.waitUntil(
      (async () => {
        const shell = await caches.open(SHELL)
        await shell.put(UID_MARKER, new Response(uid))
        // Drop every other user's cached pages so a shared device can't leak them.
        const keys = await caches.keys()
        await Promise.all(
          keys
            .filter((k) => k.startsWith('ceol-io-pages-') && k !== pagesCache(uid))
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
    // Straight to network, never cached/intercepted.
    if (url.pathname.startsWith('/api/')) return
    if (url.pathname.startsWith('/live/')) return
    if (url.pathname.startsWith('/admin')) return
    if (url.pathname === '/logout') return

    if (req.mode === 'navigate') {
      event.respondWith(handleNav(req))
      return
    }
    if (url.pathname.startsWith('/static/')) {
      event.respondWith(networkFirst(req, SHELL))
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
async function handleNav(req) {
  const uid = await currentUid()
  const cache = await caches.open(pagesCache(uid))
  try {
    const res = await fetch(req)
    if (res && res.ok && !res.redirected && res.headers.get('X-Offline-Exclude') == null) {
      cache.put(req, res.clone())
    }
    return res
  } catch (e) {
    const hit =
      (await cache.match(req)) ||
      (await (await caches.open(SHELL)).match(req)) ||
      (await caches.match('/offline'))
    if (hit) return hit
    throw e
  }
}

async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName)
  try {
    const res = await fetch(req)
    if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone())
    return res
  } catch (e) {
    const hit = await cache.match(req)
    if (hit) return hit
    throw e
  }
}
