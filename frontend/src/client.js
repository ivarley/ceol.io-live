// Spec 024 client plumbing: bootstrap fetch, the generic op POST, and the SSE
// subscription. Kept framework-free so App.svelte owns only UI + state.

export async function bootstrap(config) {
  // Same 10s abort guard as sendOp: connect() awaits this, so a fetch that hangs
  // on a dead keep-alive socket (common right after a network-interface change on
  // mobile) must fail fast — a hung bootstrap used to wedge reconnection forever.
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 10000)
  let res
  try {
    res = await fetch(`/api/live/instances/${config.sessionInstanceId}/bootstrap`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
      signal: ctrl.signal,
    })
  } catch (e) {
    e.networkError = true // offline — caller can fall back to the cached snapshot
    throw e
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) throw new Error(`bootstrap failed: ${res.status}`)
  return res.json()
}

// Session vocabulary for the local exact-match index (§024). Fetched in the BACKGROUND
// after bootstrap so it never blocks first render. Marks network failures so the caller
// can quietly fall back to the cached snapshot's vocabulary.
export async function vocabulary(config) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 10000)
  let res
  try {
    res = await fetch(`/api/live/instances/${config.sessionInstanceId}/vocabulary`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
      signal: ctrl.signal,
    })
  } catch (e) {
    e.networkError = true
    throw e
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) throw new Error(`vocabulary failed: ${res.status}`)
  return res.json()
}

// Generic op POST (spec 024 §C). Every op carries a client-generated op_id as the
// universal idempotency key — a retried POST whose ack was lost dedupes server-side.
export async function sendOp(config, op_type, payload = {}, op_id = crypto.randomUUID()) {
  // Abort after 10s so a request that hangs on a dead keep-alive socket (common on
  // the first request after going offline) gives up and is treated as a network
  // failure, rather than spinning forever.
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 10000)
  let res
  try {
    res = await fetch(`/api/live/instances/${config.sessionInstanceId}/ops`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ op_id, op_type, ...payload }),
      signal: ctrl.signal,
    })
  } catch (e) {
    // Fetch failed or aborted (offline / unreachable / timed out) — distinct from a
    // server error, so the caller can queue for replay instead of surfacing an error.
    e.networkError = true
    throw e
  } finally {
    clearTimeout(timer)
  }
  const json = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(json.error || `${op_type} failed: ${res.status}`)
  return json // {success, rejected?, reason?, event_id?, record?, ...}
}

// Ephemeral typing signal, POSTed straight to the streaming service (spec 024 §F):
// no DB, no op feed. `typing:false` clears it (on submit/blur); the service also
// times it out after ~10s of silence.
export async function sendTyping(config, typing, anchor = null) {
  const base = config.streamingBaseUrl.replace(/\/$/, '')
  try {
    await fetch(`${base}/live/instances/${config.sessionInstanceId}/typing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ typing, anchor }),
    })
  } catch {
    /* best-effort; typing is non-critical */
  }
}

// Type-ahead tune search (spec 021 §D). Public endpoint; session_id flags/ranks
// tunes already in this session. Returns [] on failure (search is non-critical).
export async function searchTunes(config, q, sessionId, preferType) {
  const params = new URLSearchParams({ q, limit: '8' })
  if (sessionId) params.set('session_id', String(sessionId))
  if (preferType) params.set('prefer_type', preferType)
  try {
    const res = await fetch(`/api/tunes/search?${params}`, { credentials: 'same-origin' })
    if (!res.ok) return []
    const json = await res.json()
    return json.tunes || []
  } catch {
    return []
  }
}

// Type-ahead + Enter-gate matching — the SAME server matcher the legacy pill editor
// uses (find_matching_tune + wildcard), so a string resolves identically in both UIs.
// Returns {exact_match, results:[{tune_id, name, tune_type, in_session_tune}]}.
export async function liveMatch(config, q, preferType) {
  const params = new URLSearchParams({ q, limit: '8' })
  if (preferType) params.set('prefer_type', preferType)
  try {
    const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/match?${params}`, { credentials: 'same-origin' })
    if (!res.ok) return { exact_match: false, results: [] }
    const j = await res.json()
    return {
      exact_match: !!j.exact_match,
      results: (j.results || []).map((r) => ({
        tune_id: r.tune_id, name: r.tune_name, tune_type: r.tune_type, in_session_tune: r.in_session_tune,
      })),
    }
  } catch {
    return { exact_match: false, results: [] }
  }
}

// Recording playback for this night (spec 050 read side): the recording and one
// {start_ms, end_ms} per timestamped tune. Fetched in the BACKGROUND after first
// paint, like the vocabulary — nothing on the page waits for it, and the play
// buttons simply appear when it lands. Refetched on an audio load error too,
// since the URL inside is a presigned S3 link that expires.
export async function instanceAudio(config) {
  const res = await fetch(`/api/session-instances/${config.sessionInstanceId}/audio`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`instance audio failed: ${res.status}`)
  return res.json()
}

// Tune detail for the info drawer (spec 021 §18).
export async function tuneDetail(config, tuneId) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/tune/${tuneId}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`tune detail failed: ${res.status}`)
  return res.json()
}

// This session's whole roster, with tonight's check-in flags (spec 034). ONE fetch drives
// the entire PersonPicker: since there is no global person search any more, the picker's
// universe IS the roster, so it is small enough to filter locally with zero latency.
export async function livePeople(config) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/people`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`people failed: ${res.status}`)
  const json = await res.json()
  return json.people || []
}

// Catalog-search API base: session-scoped on the live screen, personal
// (/api/my-tunes) on the Add-to-My-Tunes pane. Only the search family
// (deep-search / thesession-search / incipit) is dual-homed this way.
const searchBase = (config) =>
  config.searchApiBase || `/api/live/instances/${config.sessionInstanceId}`

// Deep catalog search (§D "search deeper"): rich cards + incipit ABC, optional type filter.
export async function deepSearch(config, q, type, preferType, mode) {
  const params = new URLSearchParams({ limit: '30' })
  if (q) params.set('q', q)
  if (type) params.set('type', type)
  if (preferType) params.set('prefer_type', preferType)
  if (mode) params.set('mode', mode)
  try {
    const res = await fetch(`${searchBase(config)}/deep-search?${params}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
    // 503 is the main-app service worker's offline cache-miss response.
    if (!res.ok) return res.status === 503 ? offlineDeepSearch(config, q) : []
    const json = await res.json()
    return json.results || []
  } catch {
    return offlineDeepSearch(config, q)
  }
}

// Offline fallback for the deep search, opted into per-surface (the Add-to-My-Tunes
// pane — the same parity the folded-away legacy add page had): name-search the
// CeolOffline bundle mirror (your tunebook first, then popular) and reshape the hits
// into deep-search result cards. Name-only — the type filter and ABC mode need the
// server. The live logger never opts in (it has its own offline model).
async function offlineDeepSearch(config, q) {
  if (!config.offlineSearchFallback || !window.CeolOffline) return []
  try {
    const hits = await window.CeolOffline.searchTunes(q || '', 30)
    return (hits || []).map((t) => ({
      tune_id: t.tune_id,
      name: t.name || t.tune_name,
      tune_type: t.tune_type || null,
      incipit_image: t.incipit_image || null,
      can_render: false, // rendering needs the server; show the cached incipit only
      tunebook_count: t.tunebook_count ?? null,
      on_list: t.person_tune_id != null || t.learn_status != null,
    }))
  } catch {
    return []
  }
}

// Remote tune search on thesession.org (spec 026 "Search on thesession.org"). Online-only,
// run ONLY on explicit user action (never per keystroke). Proxied server-side; each result is
// flagged is_local / in_session so the UI can dedup against the local list. thesession's single
// `q=` handles name and ABC queries; `type` filters by tune type. Returns [] on any failure.
export async function thesessionSearch(config, q, type) {
  const params = new URLSearchParams({ q })
  if (type) params.set('type', type)
  try {
    const res = await fetch(`${searchBase(config)}/thesession-search?${params}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
    if (!res.ok) return []
    const json = await res.json()
    return json.success ? (json.results || []) : []
  } catch {
    return []
  }
}

// Incipit image (base64) for a tune — rendered+cached server-side on demand if
// missing. `kind='both'` also renders the full image. Returns null if no notation.
export async function fetchIncipit(config, tuneId, kind) {
  const q = kind ? `?kind=${kind}` : ''
  try {
    const res = await fetch(`${searchBase(config)}/incipit/${tuneId}${q}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
    if (!res.ok) return null
    const json = await res.json()
    return json.image || null
  } catch {
    return null
  }
}

// ---- tune preview (deep-search "look before you log" screen) ----------------
// Notation images resolve through a MODULE-LEVEL cache + in-flight registry so a
// pending render survives navigating to another setting/result and back (the
// spinner keeps spinning and the image fills in wherever it's showing when the
// render lands), and so the modal and the pane share one request per image.
const _imgCache = new Map() // key -> base64 | null
const _imgInflight = new Map() // key -> Promise<base64|null>

function _sharedImage(key, fetcher) {
  if (_imgCache.has(key)) return Promise.resolve(_imgCache.get(key))
  let p = _imgInflight.get(key)
  if (!p) {
    p = fetcher()
      .catch(() => null)
      .then((img) => {
        _imgInflight.delete(key)
        if (img) _imgCache.set(key, img) // don't cache failures — a retry can succeed
        return img
      })
    _imgInflight.set(key, p)
  }
  return p
}

// Full preview data for a LOCAL catalog tune: settings (abc + incipit abc + any
// cached incipit image), session aliases, stats. Throws on failure.
export async function tunePreview(config, tuneId) {
  const res = await fetch(`${searchBase(config)}/tune-preview/${tuneId}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok || !json.success) throw new Error(json.error || `tune preview failed: ${res.status}`)
  return json
}

// One setting's incipit/full notation image, rendered+cached server-side on demand.
export function settingImage(config, settingId, kind) {
  return _sharedImage(`s:${settingId}:${kind}`, async () => {
    const res = await fetch(`${searchBase(config)}/setting-image/${settingId}?kind=${kind}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
    if (!res.ok) return null
    const json = await res.json()
    return json.image || null
  })
}

// Preview data for a not-yet-imported thesession.org tune (or {is_local, tune_id}
// if it turns out we already have it). `full` skips the server's local short-circuit
// and always fetches the complete settings/aliases — used to backfill a LOCAL tune's
// preview beyond the setting(s) the import brought over. Cached per id+variant for
// the page's lifetime so stepping away and back doesn't refetch. Throws on failure.
const _tsPreviewCache = new Map()
export async function thesessionPreview(config, thesessionId, full = false) {
  const key = `${thesessionId}:${full ? 1 : 0}`
  if (_tsPreviewCache.has(key)) return _tsPreviewCache.get(key)
  const res = await fetch(`${searchBase(config)}/thesession-preview/${thesessionId}${full ? '?full=1' : ''}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok || !json.success) throw new Error(json.error || `thesession preview failed: ${res.status}`)
  _tsPreviewCache.set(key, json)
  return json
}

// Ephemeral ABC render for a remote setting's notes mode (nothing imported/cached
// server-side; cacheKey dedups client-side like settingImage).
export function renderRemoteAbc(config, cacheKey, body) {
  return _sharedImage(cacheKey, async () => {
    const res = await fetch(`${searchBase(config)}/render-abc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const json = await res.json()
    return json.image || null
  })
}

// The current user's whole tune list — instruments (with is_auto) + every
// person_tune row's learn_status and sparse per-instrument overrides — for the
// my-list highlight mode. Pages through /api/my-tunes (2000/page covers nearly
// everyone in one call).
export async function myTunesList() {
  let instruments = []
  const tunes = []
  for (let page = 1; ; page++) {
    const res = await fetch(`/api/my-tunes?per_page=2000&page=${page}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
    if (!res.ok) throw new Error(`my-tunes failed: ${res.status}`)
    const j = await res.json()
    if (page === 1) instruments = j.instruments || []
    tunes.push(...(j.tunes || []))
    if (!j.pagination?.has_next) break
  }
  return { instruments, tunes }
}

// One idempotent my-tunes op (add / set_status / set_instrument_status …) —
// the same endpoint the tune-detail modal saves through.
export async function myTunesOp(op) {
  const res = await fetch('/api/my-tunes/ops', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(op),
  })
  const j = await res.json().catch(() => ({}))
  if (!res.ok || j.success === false) throw new Error(j.error || `my-tunes op failed: ${res.status}`)
  return j
}

// (Spec 034 deleted peopleSearch: /people/search ILIKE'd across every active person in the
// database, so anyone could type three letters and enumerate people from sessions they had
// nothing to do with. The PersonPicker filters the roster locally instead.)

// Open the downstream SSE stream. The bootstrap high-water mark rides in as a
// query param so the first connect only streams the delta; EventSource sends the
// Last-Event-ID header automatically on reconnect (spec 024 §B). withCredentials
// lets the Flask-Login cookie flow to the streaming sidecar.
// The server emits an observable `event: ping` on every idle keepalive (~15s) and,
// of course, real ops/presence/typing when active. If NOTHING arrives for this long,
// the socket is silently half-open (a dead connection EventSource didn't error on) —
// force a full reconnect via onDead. 45s tolerates ~2 missed pings without false alarms.
const SSE_WATCHDOG_MS = 45000

// `mode` ('view' | 'edit') tells the server whether this connection asserts presence:
// a view-only connection still receives ops/presence but is left out of the roster
// (spec 024 §presence — connecting to read touches nothing).
export function openStream(config, lastEventId, handlers, mode) {
  const base = config.streamingBaseUrl.replace(/\/$/, '')
  const m = mode === 'view' ? 'view' : 'edit'
  const url = `${base}/live/instances/${config.sessionInstanceId}/events?last_event_id=${lastEventId || 0}&mode=${m}`
  const es = new EventSource(url, { withCredentials: true })

  // Liveness watchdog: reset on any byte we observe from the server; if it ever
  // fires, the stream is dead-but-not-errored — close it and ask for a reconnect.
  // `alive` distinguishes real server bytes (reported via onAlive, so the UI can show
  // "last update Xs ago") from the arming call below, which proves nothing arrived.
  let watchdog = null
  const kick = (alive = true) => {
    if (alive) handlers.onAlive?.()
    if (watchdog) clearTimeout(watchdog)
    watchdog = setTimeout(() => {
      handlers.onStatus?.('reconnecting')
      es.close() // clears the watchdog (overridden below) and stops this dead stream
      handlers.onDead?.()
    }, SSE_WATCHDOG_MS)
  }
  // Ensure the timer never outlives the stream (the app calls es.close() on pagehide/
  // supersede; the watchdog also calls it).
  const origClose = es.close.bind(es)
  es.close = () => { if (watchdog) { clearTimeout(watchdog); watchdog = null }; origClose() }

  // All ops arrive as a single 'op' event; op_type is inside the data.
  es.addEventListener('op', (e) => {
    kick()
    let data
    try {
      data = JSON.parse(e.data)
    } catch {
      return
    }
    handlers.onOp?.(data)
  })

  // Ephemeral presence (no id:, never advances Last-Event-ID).
  es.addEventListener('presence', (e) => {
    kick()
    try {
      handlers.onPresence?.(JSON.parse(e.data).roster || [])
    } catch {
      /* ignore */
    }
  })

  es.addEventListener('typing', (e) => {
    kick()
    try {
      handlers.onTyping?.(JSON.parse(e.data).typing || [])
    } catch {
      /* ignore */
    }
  })

  // Observable keepalive — no payload to handle, just proof the stream is alive.
  es.addEventListener('ping', () => kick())

  es.onopen = () => { kick(); handlers.onStatus?.('live') }
  es.onerror = () => handlers.onStatus?.('reconnecting')
  // Arm the watchdog NOW, not on first byte: a stream that never opens (stalled
  // connect, or a non-200 that makes EventSource give up permanently with no native
  // retry) would otherwise sit in CONNECTING forever with no timer to kill it.
  kick(false)
  return es
}

// Reachability probe for the connection-dot popover: can we reach (a) the Flask app
// and (b) the streaming sidecar? These fail independently — locally a localhost vs
// 127.0.0.1 mismatch in streamingBaseUrl kills only the stream — so probe both.
// /sw.js is network-passthrough (never SW-cached); the sidecar's /health has no CORS
// headers, so fetch it no-cors: an opaque response still proves the server answered,
// and only a real network failure rejects.
export async function probeServers(config) {
  const base = config.streamingBaseUrl.replace(/\/$/, '')
  const [app, stream] = await Promise.all([
    fetch('/sw.js', { method: 'HEAD', cache: 'no-store' }).then(() => true).catch(() => false),
    fetch(`${base}/health`, { mode: 'no-cors', cache: 'no-store' }).then(() => true).catch(() => false),
  ])
  return { app, stream }
}
