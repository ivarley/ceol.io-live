// Spec 024 client plumbing: bootstrap fetch, the generic op POST, and the SSE
// subscription. Kept framework-free so App.svelte owns only UI + state.

export async function bootstrap(config) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/bootstrap`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`bootstrap failed: ${res.status}`)
  return res.json()
}

// Generic op POST (spec 024 §C). Every op carries a client-generated op_id as the
// universal idempotency key — a retried POST whose ack was lost dedupes server-side.
export async function sendOp(config, op_type, payload = {}) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/ops`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ op_id: crypto.randomUUID(), op_type, ...payload }),
  })
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
