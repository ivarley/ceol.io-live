<script>
  import { onMount, onDestroy } from 'svelte'
  import { SvelteMap, SvelteSet } from 'svelte/reactivity'
  import { bootstrap, sendOp, sendTyping, openStream } from './client.js'

  let { config } = $props()

  // Canonical records keyed by id (tunes + break rows), applied idempotently.
  // SvelteMap (not a plain Map) so .set/.delete are reactive in Svelte 5.
  const byId = new SvelteMap()
  const pending = new SvelteMap() // op_id -> {tempId, name} optimistic, pre-ack (§A2)
  const flashing = new SvelteSet() // record ids briefly highlighted on settle (§39)
  let status = $state('connecting')
  let input = $state('')
  let error = $state('')
  let notice = $state('')
  let person = $state(config.currentPerson || {})
  let roster = $state([]) // who's connected right now (ephemeral presence, §F)
  let typers = $state([]) // who's currently composing (ephemeral typing, §F)

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
    const pend = [...pending.values()].map((p) => ({
      session_instance_tune_id: p.tempId, name: p.name, record_type: 'tune', pending: true,
    }))
    if (!pend.length) return base
    if (base.length && openSet) base[base.length - 1].push(...pend)
    else base.push(pend)
    return base
  })

  // Apply one server-authoritative op (spec 024). Dispatch by op_type.
  function applyOp(d) {
    if (d.op_id && pending.has(d.op_id)) pending.delete(d.op_id) // settle our optimistic row
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
    try {
      const res = await sendOp(config, op_type, payload)
      if (res.rejected) notice = res.message || `${label || op_type}: ${res.reason}`
    } catch (e) {
      error = e.message
    }
  }

  async function submit() {
    const name = input.trim()
    if (!name) return
    input = ''
    lastTypingSent = 0
    sendTyping(config, false) // clear-on-commit (§F)

    // Optimistic: show the row immediately as pending, reconcile on the server's
    // authoritative result (which arrives via op-ack and/or the SSE echo, by op_id).
    const op_id = crypto.randomUUID()
    pending.set(op_id, { tempId: `pending-${op_id}`, name })
    error = ''
    try {
      const res = await sendOp(config, 'add_tune', { name }, op_id)
      pending.delete(op_id)
      if (res.rejected) notice = res.message || `Add: ${res.reason}`
      else if (res.record) {
        put(res.record) // settle now if the ack beat the SSE echo (idempotent)
        flashId(res.record.session_instance_tune_id)
      }
    } catch (e) {
      pending.delete(op_id)
      error = e.message
    }
  }

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
        onStatus: (s) => (status = s),
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

  onMount(() => {
    connect()
    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('pageshow', onPageShow)
  })

  onDestroy(() => {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('pageshow', onPageShow)
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

  <div class="sets">
    {#each displaySets as set, i (set[0].session_instance_tune_id)}
      <ol class="set">
        {#each set as r (r.session_instance_tune_id)}
          <li
            class:low={!r.pending && r.confidence != null && r.confidence <= 70}
            class:pending={r.pending}
            class:flash={flashing.has(r.session_instance_tune_id)}
          >
            <span class="name">{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}</span>
            {#if r.pending}
              <span class="actions"><span class="hourglass" title="Sending…">⏳</span></span>
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
