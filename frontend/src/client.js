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
export function openStream(config, lastEventId, handlers) {
  const base = config.streamingBaseUrl.replace(/\/$/, '')
  const url = `${base}/live/instances/${config.sessionInstanceId}/events?last_event_id=${lastEventId || 0}`
  const es = new EventSource(url, { withCredentials: true })

  // All ops arrive as a single 'op' event; op_type is inside the data.
  es.addEventListener('op', (e) => {
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
    try {
      handlers.onPresence?.(JSON.parse(e.data).roster || [])
    } catch {
      /* ignore */
    }
  })

  es.addEventListener('typing', (e) => {
    try {
      handlers.onTyping?.(JSON.parse(e.data).typing || [])
    } catch {
      /* ignore */
    }
  })

  es.onopen = () => handlers.onStatus?.('live')
  es.onerror = () => handlers.onStatus?.('reconnecting')
  return es
}
