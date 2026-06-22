<script>
  import { onMount, onDestroy } from 'svelte'
  import { SvelteMap } from 'svelte/reactivity'
  import { bootstrap, sendOp, openStream } from './client.js'

  let { config } = $props()

  // Canonical records keyed by id (tunes + break rows), applied idempotently.
  // SvelteMap (not a plain Map) so .set/.delete are reactive in Svelte 5.
  const byId = new SvelteMap()
  let status = $state('connecting')
  let input = $state('')
  let error = $state('')
  let notice = $state('')
  let person = $state(config.currentPerson || {})

  let es = null

  function put(record) {
    if (!record) return
    byId.set(record.session_instance_tune_id, record)
  }

  function drop(id) {
    byId.delete(id)
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

  // Apply one server-authoritative op (spec 024). Dispatch by op_type.
  function applyOp(d) {
    switch (d.op_type) {
      case 'add_tune':
      case 'change_tune':
      case 'set_confidence':
      case 'attribute_set_starter':
        put(d.record)
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

  function submit() {
    const name = input.trim()
    if (!name) return
    input = ''
    op('add_tune', { name }) // server-authoritative: the row arrives over SSE
  }

  onMount(async () => {
    try {
      const snap = await bootstrap(config)
      for (const r of snap.records || []) put(r)
      if (snap.current_person) person = snap.current_person
      es = openStream(config, snap.last_event_id, {
        onOp: applyOp,
        onStatus: (s) => (status = s),
      })
    } catch (e) {
      error = e.message
      status = 'error'
    }
  })

  onDestroy(() => es && es.close())
</script>

<main>
  <header>
    <h1>Live logging <span class="beta">beta</span></h1>
    <div class="meta">
      <span class="who">{person.first_name || 'You'}</span>
      <span class="status status-{status}">{status}</span>
    </div>
  </header>

  {#if notice}<p class="notice" onclick={() => (notice = '')}>{notice}</p>{/if}

  <div class="sets">
    {#each sets as set, i (set[0].session_instance_tune_id)}
      <ol class="set">
        {#each set as r (r.session_instance_tune_id)}
          <li class:low={r.confidence != null && r.confidence <= 70}>
            <span class="name">{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}</span>
            <span class="actions">
              {#if r.confidence != null && r.confidence <= 70}
                <button onclick={() => op('set_confidence', { record_id: r.session_instance_tune_id, confidence: 100 }, 'Confirm')}>✓</button>
              {/if}
              <button onclick={() => op('remove_tune', { record_id: r.session_instance_tune_id }, 'Remove')}>✕</button>
            </span>
          </li>
        {/each}
      </ol>
    {:else}
      <p class="empty">No tunes yet — log one below.</p>
    {/each}
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  <div class="composer">
    <input placeholder="Tune name…" bind:value={input} onkeydown={(e) => e.key === 'Enter' && submit()} />
    <button onclick={submit}>Log</button>
    <button
      class="endset"
      title="End the current set"
      disabled={!lastRecordId}
      onclick={() => op('set_break', { after_record_id: lastRecordId }, 'End set')}
    >End set</button>
  </div>
</main>
