// Spec 024 Phase 0 client plumbing: bootstrap fetch, the add_tune op POST, and
// the SSE subscription. Kept framework-free so App.svelte owns only UI + state.

export async function bootstrap(config) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/bootstrap`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`bootstrap failed: ${res.status}`)
  return res.json()
}

export async function addTune(config, { name, tune_id = null, after_record_id = null }) {
  const res = await fetch(`/api/live/instances/${config.sessionInstanceId}/ops/add_tune`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({
      op_id: crypto.randomUUID(), // universal idempotency key (spec 024 §C)
      name,
      tune_id,
      after_record_id,
      source: 'human',
    }),
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok || !json.success) throw new Error(json.error || `add_tune failed: ${res.status}`)
  return json
}

// Open the downstream SSE stream. The bootstrap high-water mark rides in as a
// query param so the first connect only streams the delta; EventSource sends the
// Last-Event-ID header automatically on reconnect (spec 024 §B). withCredentials
// lets the Flask-Login cookie flow cross-origin to the streaming sidecar.
export function openStream(config, lastEventId, handlers) {
  const base = config.streamingBaseUrl.replace(/\/$/, '')
  const url = `${base}/live/instances/${config.sessionInstanceId}/events?last_event_id=${lastEventId || 0}`
  const es = new EventSource(url, { withCredentials: true })

  es.addEventListener('add_tune', (e) => {
    let data
    try {
      data = JSON.parse(e.data)
    } catch {
      return
    }
    handlers.onAddTune?.(data, Number(e.lastEventId))
  })

  es.onopen = () => handlers.onStatus?.('live')
  es.onerror = () => handlers.onStatus?.('reconnecting')
  return es
}
