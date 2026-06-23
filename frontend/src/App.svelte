<script>
  import { onMount, onDestroy } from 'svelte'
  import { SvelteMap, SvelteSet } from 'svelte/reactivity'
  import { bootstrap, sendOp, sendTyping, openStream } from './client.js'
  import { queuePut, queueAll, queueDelete } from './offline.js'

  let { config } = $props()

  // Canonical records keyed by id (tunes + break rows), applied idempotently.
  // SvelteMap (not a plain Map) so .set/.delete are reactive in Svelte 5.
  const byId = new SvelteMap()
  // op_id -> {tempId, name, op_type, payload, status, ts}. status 'sending' = online
  // optimistic in-flight (§A2); 'queued' = offline, persisted to IndexedDB (§G).
  const pending = new SvelteMap()
  const flashing = new SvelteSet() // record ids briefly highlighted on settle (§39)
  let status = $state('connecting')
  let input = $state('')
  let error = $state('')
  let notice = $state('')
  let person = $state(config.currentPerson || {})
  let roster = $state([]) // who's connected right now (ephemeral presence, §F)
  let typers = $state([]) // who's currently composing (ephemeral typing, §F)
  let activity = $state(null) // transient "X did Y" notice for others' changes (§E)
  let activitySeq = 0

  let es = null
  let lastTypingSent = 0 // throttle the "still typing" refresh

  // The UI infers a presence color from the arrival ordinal (spec 024 §F).
  const PALETTE = ['#4f9dff', '#46d27a', '#e0b341', '#e0594b', '#b07cff', '#3fd0c9', '#ff8fab', '#9ab0c0']
  const colorFor = (seq) => PALETTE[((seq % PALETTE.length) + PALETTE.length) % PALETTE.length]
  const initials = (name) => (name || '?').trim().slice(0, 2).toUpperCase()

  function put(record) {
    if (!record) return
    byId.set(record.session_instance_tune_id, record)
  }

  function drop(id) {
    byId.delete(id)
  }

  // Briefly highlight a record when it settles / changes (the §39 settle-flash).
  function flashId(id) {
    if (id == null) return
    flashing.add(id)
    setTimeout(() => flashing.delete(id), 700)
  }

  // Ordered, non-deleted records (tunes + breaks), then segment into sets on breaks.
  const ordered = $derived(
    [...byId.values()]
      .filter((r) => !r.deleted)
      .sort((a, b) => (a.order_position < b.order_position ? -1 : a.order_position > b.order_position ? 1 : 0))
  )
  const sets = $derived.by(() => {
    const out = []
    let cur = []
    for (const r of ordered) {
      if (r.record_type === 'break') {
        if (cur.length) out.push(cur)
        cur = []
      } else {
        cur.push(r)
      }
    }
    if (cur.length) out.push(cur)
    return out
  })
  const lastRecordId = $derived(ordered.length ? ordered[ordered.length - 1].session_instance_tune_id : null)
  const openSet = $derived(ordered.length > 0 && ordered[ordered.length - 1].record_type !== 'break')

  // Sets for display, with optimistic pending rows appended to the open set (or a
  // new trailing set if the last record is a break / there are none yet).
  const displaySets = $derived.by(() => {
    const base = sets.map((s) => s.slice())
    const pend = [...pending.values()]
      .filter((p) => p.op_type === 'add_tune')
      .map((p) => ({
        session_instance_tune_id: p.tempId, name: p.name, record_type: 'tune',
        pending: true, status: p.status,
      }))
    if (!pend.length) return base
    if (base.length && openSet) base[base.length - 1].push(...pend)
    else base.push(pend)
    return base
  })

  const colorForPerson = (pid) => {
    const p = roster.find((r) => r.person_id === pid)
    return p ? colorFor(p.arrival_seq) : 'var(--muted)'
  }

  function remoteLabel(d) {
    const n = d.record?.name || (d.record?.tune_id ? `#${d.record.tune_id}` : 'a tune')
    switch (d.op_type) {
      case 'add_tune': return `added ${n}`
      case 'corroborate': return `also logged ${n}`
      case 'change_tune': return `edited ${n}`
      case 'remove_tune': return `removed ${n}`
      case 'set_break': return d.removed ? 'removed a break' : 'ended a set'
      case 'attribute_set_starter': return `set who started ${n}`
      case 'set_confidence': return `confirmed ${n}`
      default: return null
    }
  }

  // A change made by someone else — surface a brief, attributed activity notice (§E).
  function noteRemote(d) {
    if (!d.actor || d.actor.person_id == null || d.actor.person_id === person.person_id) return
    const label = remoteLabel(d)
    if (!label) return
    const seq = ++activitySeq
    activity = { text: `${d.actor.name || 'Someone'} ${label}`, color: colorForPerson(d.actor.person_id) }
    setTimeout(() => { if (seq === activitySeq) activity = null }, 4000)
  }

  // Apply one server-authoritative op (spec 024). Dispatch by op_type.
  function applyOp(d) {
    if (d.op_id && pending.has(d.op_id)) {
      pending.delete(d.op_id) // settle our optimistic/queued row...
      queueDelete(d.op_id) // ...and drop it from the persisted queue (already applied)
    }
    noteRemote(d)
    switch (d.op_type) {
      case 'add_tune':
      case 'change_tune':
      case 'set_confidence':
      case 'attribute_set_starter':
      case 'corroborate': // server collapsed a duplicate into this record (§H30)
        put(d.record)
        flashId(d.record?.session_instance_tune_id)
        break
      case 'set_break':
        if (d.removed) drop(d.record_id)
        else put(d.record)
        break
      case 'remove_tune':
        if (d.record) (d.record.deleted ? drop(d.record.session_instance_tune_id) : put(d.record))
        break
      case 'edit_notes':
      case 'mark_complete':
      case 'mark_incomplete':
        break // metadata; header-only (not shown in this minimal Phase 1 UI)
    }
  }

  async function op(op_type, payload, label) {
    error = ''
    // Chunk 1 only queues add_tune offline; other ops need connectivity. Fail
    // gracefully with a notice rather than a raw error (full offline support later).
    if (!navigator.onLine) {
      notice = `You're offline — ${label || op_type} isn't available offline yet.`
      return
    }
    try {
      const res = await sendOp(config, op_type, payload)
      if (res.rejected) notice = res.message || `${label || op_type}: ${res.reason}`
    } catch (e) {
      if (e.networkError) notice = `You're offline — ${label || op_type} isn't available offline yet.`
      else error = e.message
    }
  }

  // Hold an op for reconnect replay (persisted to IndexedDB, §G).
  async function markQueued(entry) {
    entry.status = 'queued'
    pending.set(entry.op_id, entry)
    await queuePut({
      op_id: entry.op_id, op_type: entry.op_type, payload: entry.payload,
      name: entry.name, ts: entry.ts, session_instance_id: config.sessionInstanceId,
    })
  }

  // Try to send a pending op. Success -> settle; network failure -> queue it;
  // server error -> surface and drop. Idempotent by op_id.
  async function trySend(entry) {
    entry.status = 'sending'
    pending.set(entry.op_id, entry)
    // Fast-path: if the browser knows it's offline, queue without a doomed fetch
    // (the first such fetch would otherwise hang on a dead keep-alive socket).
    if (!navigator.onLine) {
      await markQueued(entry)
      return
    }
    try {
      const res = await sendOp(config, entry.op_type, entry.payload, entry.op_id)
      pending.delete(entry.op_id)
      await queueDelete(entry.op_id)
      if (res.rejected) notice = res.message || `${entry.op_type}: ${res.reason}`
      else if (res.record) {
        put(res.record) // settle now if the ack beat the SSE echo (idempotent)
        flashId(res.record.session_instance_tune_id)
      }
    } catch (e) {
      if (e.networkError) {
        await markQueued(entry)
      } else {
        pending.delete(entry.op_id)
        await queueDelete(entry.op_id)
        error = e.message
      }
    }
  }

  // Replay queued ops in offline order; stop if we go offline again mid-drain.
  let flushing = false
  async function flush() {
    if (flushing) return
    flushing = true
    try {
      const queued = [...pending.values()].filter((e) => e.status === 'queued').sort((a, b) => a.ts - b.ts)
      for (const entry of queued) {
        await trySend(entry)
        if (entry.status === 'queued') break // still offline
      }
    } finally {
      flushing = false
    }
  }

  function submit() {
    const name = input.trim()
    if (!name) return
    input = ''
    lastTypingSent = 0
    sendTyping(config, false) // clear-on-commit (§F)
    error = ''
    const op_id = crypto.randomUUID()
    trySend({ tempId: `pending-${op_id}`, name, op_id, op_type: 'add_tune', payload: { name }, status: 'sending', ts: Date.now() })
  }

  const queuedCount = $derived([...pending.values()].filter((e) => e.status === 'queued').length)

  // Refresh a typing reservation while composing (throttled); clear it when empty.
  function onInput() {
    if (input.trim()) {
      const now = Date.now()
      if (now - lastTypingSent > 3000) {
        lastTypingSent = now
        sendTyping(config, true, lastRecordId)
      }
    } else if (lastTypingSent) {
      lastTypingSent = 0
      sendTyping(config, false)
    }
  }

  function stopTyping() {
    if (lastTypingSent) {
      lastTypingSent = 0
      sendTyping(config, false)
    }
  }

  const othersTyping = $derived(typers.filter((t) => t.person_id !== person.person_id))

  let connSeq = 0 // guards against overlapping connect() calls leaking a stream
  async function connect() {
    const myGen = ++connSeq
    try {
      if (es) { es.close(); es = null }
      const snap = await bootstrap(config) // resync records + fresh high-water on (re)connect
      if (myGen !== connSeq) return // a newer connect() superseded this one
      byId.clear()
      for (const r of snap.records || []) put(r)
      if (snap.current_person) person = snap.current_person
      const stream = openStream(config, snap.last_event_id, {
        onOp: applyOp,
        onPresence: (r) => (roster = r),
        onTyping: (l) => (typers = l),
        onStatus: (s) => {
          status = s
          if (s === 'live') flush() // back online -> replay anything queued (§G)
        },
      })
      if (myGen !== connSeq) { stream.close(); return } // superseded after we opened
      es = stream
    } catch (e) {
      error = e.message
      status = 'error'
    }
  }

  // Close the stream when the page is hidden/navigated/bfcached so the server sees
  // us leave (an SSE socket kept alive in bfcache would otherwise leave a ghost
  // present); reconnect when the page is restored from bfcache.
  function onPageHide() {
    if (es) { es.close(); es = null }
    status = 'reconnecting'
  }
  function onPageShow(e) {
    // Only reconnect on a bfcache restore; the initial load is handled by onMount
    // (pageshow also fires then, which previously caused a duplicate connection).
    if (e.persisted) connect()
  }

  async function hydrateQueue() {
    try {
      for (const e of await queueAll(config.sessionInstanceId)) {
        pending.set(e.op_id, {
          tempId: `pending-${e.op_id}`, name: e.name, op_id: e.op_id,
          op_type: e.op_type, payload: e.payload, status: 'queued', ts: e.ts,
        })
      }
    } catch (err) {
      /* IndexedDB unavailable (private mode etc.) — degrade to online-only */
    }
  }

  const onOnline = () => flush()

  onMount(async () => {
    await hydrateQueue() // restore ops left queued from a previous offline session
    connect()
    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('pageshow', onPageShow)
    window.addEventListener('online', onOnline)
  })

  onDestroy(() => {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('pageshow', onPageShow)
    window.removeEventListener('online', onOnline)
    if (es) es.close()
  })
</script>

<main>
  <header>
    <h1>Live logging <span class="beta">beta</span></h1>
    <div class="meta">
      <span class="roster">
        {#each roster as p (p.person_id)}
          <span class="avatar" style="background:{colorFor(p.arrival_seq)}" title="{p.name}{p.devices > 1 ? ` (${p.devices} devices)` : ''}">
            {initials(p.name)}{#if p.devices > 1}<sup>{p.devices}</sup>{/if}
          </span>
        {/each}
      </span>
      <span class="status status-{status}">{status}</span>
    </div>
  </header>

  {#if notice}<p class="notice" onclick={() => (notice = '')}>{notice}</p>{/if}
  {#if activity}
    <p class="activity"><span class="dot" style="background:{activity.color}"></span>{activity.text}</p>
  {/if}
  {#if queuedCount > 0}
    <p class="offline-banner">
      ⏳ {queuedCount} change{queuedCount === 1 ? '' : 's'} queued{status === 'live' ? ', syncing…' : ' — offline'}
    </p>
  {/if}

  <div class="sets">
    {#each displaySets as set, i (set[0].session_instance_tune_id)}
      <ol class="set">
        {#each set as r (r.session_instance_tune_id)}
          <li
            class:low={!r.pending && r.confidence != null && r.confidence <= 70}
            class:pending={r.pending}
            class:queued={r.pending && r.status === 'queued'}
            class:flash={flashing.has(r.session_instance_tune_id)}
          >
            <span class="name">{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}</span>
            {#if r.pending}
              <span class="actions"><span class="hourglass" title={r.status === 'queued' ? 'Queued (offline)' : 'Sending…'}>⏳</span></span>
            {:else}
              <span class="actions">
                {#if r.confidence != null && r.confidence <= 70}
                  <button onclick={() => op('set_confidence', { record_id: r.session_instance_tune_id, confidence: 100 }, 'Confirm')}>✓</button>
                {/if}
                <button onclick={() => op('remove_tune', { record_id: r.session_instance_tune_id }, 'Remove')}>✕</button>
              </span>
            {/if}
          </li>
        {/each}
      </ol>
    {:else}
      <p class="empty">No tunes yet — log one below.</p>
    {/each}
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  {#if othersTyping.length}
    <div class="typing">
      {#each othersTyping as t (t.person_id)}<span class="t-name" style="color:{colorFor(t.arrival_seq)}">{t.name}</span>{/each}
      <span class="t-verb">{othersTyping.length === 1 ? 'is' : 'are'} typing…</span>
    </div>
  {/if}

  <div class="composer">
    <input
      placeholder="Tune name…"
      bind:value={input}
      oninput={onInput}
      onblur={stopTyping}
      onkeydown={(e) => e.key === 'Enter' && submit()}
    />
    <button onclick={submit}>Log</button>
    <button
      class="endset"
      title="End the current set"
      disabled={!lastRecordId}
      onclick={() => op('set_break', { after_record_id: lastRecordId }, 'End set')}
    >End set</button>
  </div>
</main>
