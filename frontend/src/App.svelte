<script>
  import { onMount, onDestroy } from 'svelte'
  import { bootstrap, addTune, openStream } from './client.js'

  let { config } = $props()

  let records = $state([]) // canonical tune/break rows, sorted by order_position
  let status = $state('connecting')
  let input = $state('')
  let error = $state('')
  let person = $state(config.currentPerson || {})

  let es = null

  // Idempotent upsert keyed by session_instance_tune_id, so bootstrap state and
  // any SSE replay overlap converge instead of duplicating (spec 024 §A2).
  function upsert(record) {
    const id = record.session_instance_tune_id
    const i = records.findIndex((r) => r.session_instance_tune_id === id)
    if (i === -1) records.push(record)
    else records[i] = record
    // order_position is a base-62 fractional string; ASCII code-unit sort matches
    // the DB's COLLATE "C" byte order.
    records.sort((a, b) => (a.order_position < b.order_position ? -1 : a.order_position > b.order_position ? 1 : 0))
  }

  async function submit() {
    const name = input.trim()
    if (!name) return
    input = ''
    error = ''
    try {
      // Server-authoritative: the new row arrives (for every client, including
      // this one) over SSE. Phase 0 keeps it simple — no optimistic row yet.
      await addTune(config, { name })
    } catch (e) {
      error = e.message
    }
  }

  function onKeydown(e) {
    if (e.key === 'Enter') submit()
  }

  onMount(async () => {
    try {
      const snap = await bootstrap(config)
      records = snap.records || []
      records.sort((a, b) => (a.order_position < b.order_position ? -1 : 1))
      if (snap.current_person) person = snap.current_person
      es = openStream(config, snap.last_event_id, {
        onAddTune: (data) => data.record && upsert(data.record),
        onStatus: (s) => (status = s),
      })
    } catch (e) {
      error = e.message
      status = 'error'
    }
  })

  onDestroy(() => es && es.close())

  const tunes = $derived(records.filter((r) => r.record_type === 'tune'))
</script>

<main>
  <header>
    <h1>Live logging <span class="beta">beta</span></h1>
    <div class="meta">
      <span class="who">{person.first_name || 'You'}</span>
      <span class="status status-{status}">{status}</span>
    </div>
  </header>

  <ul class="tunes">
    {#each tunes as r (r.session_instance_tune_id)}
      <li>{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}</li>
    {:else}
      <li class="empty">No tunes yet — log one below.</li>
    {/each}
  </ul>

  {#if error}<p class="error">{error}</p>{/if}

  <div class="composer">
    <input
      placeholder="Tune name…"
      bind:value={input}
      onkeydown={onKeydown}
      autofocus
    />
    <button onclick={submit}>Log</button>
  </div>
</main>
