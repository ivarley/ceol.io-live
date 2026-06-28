// Spec 024 §H — service worker for the live-logging screen ONLY.
//
// Served from /live/sw.js so its scope is /live/ — it controls the live page and
// its fetches, and does NOT touch the main app (whose own /static/-scoped SW
// controls nothing and is just a PWA-install shim).
//
// Caching policy (§H):
//   - shell assets (/static/live/*)          -> network-first, cache fallback
//   - the screen navigation (/live/instances/*) -> network-first, cache fallback
//   - dynamic API (/api/*), op-POST, SSE      -> NETWORK-ONLY, never cached/intercepted
// Data lives in IndexedDB, never the SW cache.
//
// Network-first (not cache-first/SWR) because the bundle has a FIXED filename
// (app.js) — cache-first would strand users on a stale build until a later load.
// Online always gets the latest; the cache is purely the offline fallback.

const CACHE = 'ceol-live-shell-v4'
// The Svelte bundle PLUS the shared shell assets the live page pulls in directly
// (the floated hamburger menu + the tune-detail modal). Without these in the cache,
// an offline reload renders the menu unstyled (no CSS) and inert (no JS).
const ASSETS = [
  '/static/live/app.js',
  '/static/live/app.css',
  '/static/css/hamburger_menu.css',
  '/static/js/hamburger_menu.js',
  '/static/js/tune_detail_modal.js',
  '/static/images/logo3-1.png', // the brand logo in the Svelte header — else a broken-image icon offline
]
// Same-origin shell assets outside /static/live/ that we still own offline (precached
// above). Matched exactly in the fetch handler so they get network-first + cache fallback.
const SHELL_ASSETS = new Set(ASSETS.filter((p) => !p.startsWith('/static/live/')))

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => k.startsWith('ceol-live-shell-') && k !== CACHE).map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  )
})

// The page navigation URL is dynamic (/live/instances/<id>), so it can't be in the
// install precache. The client posts {type:'cache-shell', url} on every online load
// so the shell is reliably cached for offline reloads (independent of cache-version
// churn or whether a prior navigation happened to be cached).
self.addEventListener('message', (event) => {
  const data = event.data || {}
  if (data.type === 'cache-shell' && data.url) {
    event.waitUntil(caches.open(CACHE).then((c) => c.add(data.url).catch(() => {})))
  }
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  const url = new URL(req.url)

  // Let everything we don't explicitly own go straight to network: non-GET
  // (op-POST), cross-origin (the SSE stream lives on the streaming service), and
  // the dynamic API. A SW must never cache/intercept the stream or the op queue.
  if (req.method !== 'GET' || url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return

  if (
    url.pathname.startsWith('/static/live/') ||
    SHELL_ASSETS.has(url.pathname) ||
    (req.mode === 'navigate' && url.pathname.startsWith('/live/instances/'))
  ) {
    event.respondWith(networkFirst(req))
  }
  // anything else: default network
})

async function networkFirst(req) {
  const cache = await caches.open(CACHE)
  try {
    const res = await fetch(req)
    if (res && res.ok) cache.put(req, res.clone())
    return res
  } catch (e) {
    const cached = await cache.match(req)
    if (cached) return cached
    throw e
  }
}
