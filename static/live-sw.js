// Spec 024 §H — service worker for the live-logging screen ONLY.
//
// Served from /live/sw.js so its scope is /live/ — it controls the live page and
// its fetches, and does NOT touch the main app (whose own /static/-scoped SW
// controls nothing and is just a PWA-install shim).
//
// Caching policy (§H):
//   - shell assets with a content-hash version (?v=, stamped by Flask's url_for)
//                                             -> CACHE-FIRST (exact URL is immutable)
//   - unversioned shell assets               -> network-first, cache fallback
//   - the screen navigation (/live/instances/*) -> network-first, cache fallback
//   - dynamic API (/api/*), op-POST, SSE      -> NETWORK-ONLY, never cached/intercepted
// Data lives in IndexedDB, never the SW cache.
//
// The bundle's FILENAME is fixed (app.js), so cache-first is only safe on the
// versioned URL — its query hash changes with the content, so an exact-URL hit can
// never be a stale build. Unversioned requests stay network-first for that reason.

const CACHE = 'ceol-live-shell-v11'
// The Svelte bundle PLUS the shared shell assets the live page pulls in directly
// (the floated hamburger menu + the tune-detail modal). Without these in the cache,
// an offline reload renders the menu unstyled (no CSS) and inert (no JS).
const ASSETS = [
  '/static/live/app.js',
  '/static/live/app.css',
  '/static/css/hamburger_menu.css',
  '/static/js/hamburger_menu.js',
  '/static/tunesheet/sheet.js',
  '/static/js/mytunes_offline.js', // offline queue for the modal's add-to-my-tunes / heard ops
  '/static/images/logo3-1.png', // the brand logo in the Svelte header — else a broken-image icon offline
  '/offline', // shared offline fallback page (shown for an uncached live screen offline)
]
// Same-origin shell assets outside /static/live/ that we still own offline (precached
// above). Matched exactly in the fetch handler so they get network-first + cache fallback.
const SHELL_ASSETS = new Set(ASSETS.filter((p) => !p.startsWith('/static/live/')))

self.addEventListener('install', (event) => {
  // Precache with {cache:'reload'} so we seed FRESH copies, not whatever the HTTP cache
  // happens to hold (c.addAll() would honor the 4h max-age and could cache a stale build).
  event.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.all(ASSETS.map((url) =>
        fetch(url, { cache: 'reload', credentials: 'same-origin' })
          .then((res) => { if (res && res.ok) return c.put(url, res) })
          .catch(() => {}) // a single missing asset must not abort the whole install
      )))
      .then(() => self.skipWaiting())
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
    // Versioned asset URLs are immutable -> cache-first; everything else network-first.
    event.respondWith(
      req.mode !== 'navigate' && url.searchParams.has('v') ? cacheFirstVersioned(req) : networkFirst(req)
    )
  }
  // anything else: default network
})

// Content-hash versioned asset: an exact-URL hit can never be stale. First fetch of a
// new version prunes superseded versions of the same file; offline with no exact hit,
// an older version (ignoreSearch — including the unversioned install-precache copy)
// beats a broken screen.
async function cacheFirstVersioned(req) {
  const cache = await caches.open(CACHE)
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

async function networkFirst(req) {
  const cache = await caches.open(CACHE)
  try {
    // For our fixed-filename shell assets (app.js etc.), {cache:'reload'} bypasses the
    // HTTP cache so they're ALWAYS revalidated against the server when online — otherwise
    // the asset's Cache-Control: max-age (4h in prod) lets plain fetch() return a stale
    // build, defeating the whole point of network-first. Navigation requests can't be
    // reconstructed (new Request throws on mode:'navigate'), so they keep plain fetch().
    const res = req.mode === 'navigate'
      ? await fetch(req)
      : await fetch(req.url, { cache: 'reload', credentials: 'same-origin' })
    if (res && res.ok) cache.put(req, res.clone())
    return res
  } catch (e) {
    let cached = await cache.match(req)
    // Offline: an asset cached under a different ?v= (or the unversioned precache copy)
    // still beats a broken screen. Navigations keep exact matching (distinct paths).
    if (!cached && req.mode !== 'navigate') {
      cached = await cache.match(req, { ignoreSearch: true })
    }
    if (cached) return cached
    // Offline + never cached: for a page navigation, show the shared offline page
    // (precached above) instead of a browser error.
    if (req.mode === 'navigate') {
      const offline = await caches.match('/offline')
      if (offline) return offline
    }
    throw e
  }
}
