// Spec 024 client plumbing: bootstrap fetch, the generic op POST, and the SSE
// subscription. Kept framework-free so App.svelte owns only UI + state.

export async function bootstrap(config) {
  let res
  try {
    res = await fetch(`/api/live/instances/${config.sessionInstanceId}/bootstrap`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
  } catch (e) {
    e.networkError = true // offline — caller can fall back to the cached snapshot
    throw e
  }
  if (!res.ok) throw new Error(`bootstrap failed: ${res.status}`)
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

// Tune detail for the info drawer (spec 021 §18).
export async function tuneDetail(config, tuneId) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/tune/${tuneId}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`tune detail failed: ${res.status}`)
  return res.json()
}

// Candidate people for the "started by" picker (§19): instance attendees.
export async function livePeople(config) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/people`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`people failed: ${res.status}`)
  const json = await res.json()
  return json.people || []
}

// Deep catalog search (§D "search deeper"): rich cards + incipit ABC, optional type filter.
export async function deepSearch(config, q, type, preferType, mode) {
  const params = new URLSearchParams({ limit: '30' })
  if (q) params.set('q', q)
  if (type) params.set('type', type)
  if (preferType) params.set('prefer_type', preferType)
  if (mode === 'abc') params.set('mode', 'abc')
  try {
    const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/deep-search?${params}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
    if (!res.ok) return []
    const json = await res.json()
    return json.results || []
  } catch {
    return []
  }
}

// Incipit image (base64) for a tune — rendered+cached server-side on demand if
// missing. `kind='both'` also renders the full image. Returns null if no notation.
export async function fetchIncipit(config, tuneId, kind) {
  const q = kind ? `?kind=${kind}` : ''
  try {
    const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/incipit/${tuneId}${q}`, {
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

// Search people to add to attendance (§F editor); flags who's already checked in.
export async function peopleSearch(config, q) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/people/search?q=${encodeURIComponent(q)}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) return []
  const json = await res.json()
  return json.people || []
}

// Open the downstream SSE stream. The bootstrap high-water mark rides in as a
// query param so the first connect only streams the delta; EventSource sends the
// Last-Event-ID header automatically on reconnect (spec 024 §B). withCredentials
// lets the Flask-Login cookie flow to the streaming sidecar.
// The server emits an observable `event: ping` on every idle keepalive (~15s) and,
// of course, real ops/presence/typing when active. If NOTHING arrives for this long,
// the socket is silently half-open (a dead connection EventSource didn't error on) —
// force a full reconnect via onDead. 45s tolerates ~2 missed pings without false alarms.
const SSE_WATCHDOG_MS = 45000

export function openStream(config, lastEventId, handlers) {
  const base = config.streamingBaseUrl.replace(/\/$/, '')
  const url = `${base}/live/instances/${config.sessionInstanceId}/events?last_event_id=${lastEventId || 0}`
  const es = new EventSource(url, { withCredentials: true })

  // Liveness watchdog: reset on any byte we observe from the server; if it ever
  // fires, the stream is dead-but-not-errored — close it and ask for a reconnect.
  let watchdog = null
  const kick = () => {
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
  return es
}
