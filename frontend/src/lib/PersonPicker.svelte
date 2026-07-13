<script>
  /**
   * PersonPicker (spec 034) — the ONE flow for finding and adding a person to a session.
   *
   * Replaces three separate UIs: the logger's starter picker (which could only see people
   * already checked in), the logger's bespoke attendance drawer, and the session People
   * tab's stacked search/create sheets. Its whole reason to exist is to collapse the
   * "leave the picker, open the drawer, come back" hop:
   *
   *   I notice Sarah's here. I log the tune, tap "Started by", type "Sar", tap her —
   *   she is checked in AND credited with the set, in one gesture.
   *
   * THERE IS NO GLOBAL PERSON SEARCH. The picker's entire universe is this session's own
   * roster, handed to it whole in `people`. You can never discover people from other
   * sessions; anyone else is typed in fresh (and deduped on email server-side). That is why
   * filtering is local and instant — there is nothing to fetch.
   *
   * Tiers, by scope:
   *
   *   instance   tier 1  checked in
   *              tier 2  on the roster, not yet checked in  (dimmed) — ordered by computed
   *                      regular-ness, so who usually comes is who you see first
   *   session    tier 1  the roster (one flat list)
   *
   * ARCHIVED people are hidden from the default list but ALWAYS findable by typing (dimmed,
   * marked "archived"). Never omit them: a member back for one night who can't be found is a
   * member someone re-creates as a duplicate person, which is far worse than seeing her name.
   */
  // Direct imports, not the barrel: index.js exports THIS component, so going through it
  // would be a cycle.
  import Sheet from './Sheet.svelte'
  import SearchField from './SearchField.svelte'
  import List from './List.svelte'
  import Chip from './Chip.svelte'

  let {
    open = $bindable(false),
    scope = 'instance',        // 'instance' | 'session'
    mode = 'attendance',       // 'attendance' (stay open, toggle check-ins) | 'starter' (pick one, close)
    title = null,
    people = [],               // the session roster; see load_session_people()
    canonicalInstruments = [],
    currentStarterName = null, // starter mode: enables the "— Clear —" row
    busy = false,
    onSelect = () => {},       // (person) — tapped a row
    onCheckOut = () => {},     // (person) — ✕ on a checked-in row (attendance mode)
    onClear = () => {},        // starter mode: clear the set's starter
    onCreate = () => {},       // ({first_name, last_name, email, instruments})
    onClose = () => {},
  } = $props()

  let query = $state('')
  let active = $state(-1)
  let showCreate = $state(false)
  let newFirst = $state('')
  let newLast = $state('')
  let newEmail = $state('')
  let newInstruments = $state([])
  let newOther = $state('')

  const heading = $derived(title || (mode === 'starter' ? 'Who started this set?' : 'Attendance'))

  const q = $derived(query.trim().toLowerCase())
  const matches = (p) => !q || (p.display_name || '').toLowerCase().includes(q)

  /**
   * Flattened tiers. One List (it owns keyboard focus, and two would fight over it), with a
   * section label carried on the first row of each tier.
   */
  const items = $derived.by(() => {
    const out = []
    const push = (rows, tier, label) => {
      rows.forEach((p, i) => out.push({ ...p, _tier: tier, _label: i === 0 ? label : null }))
    }

    // Archived people are hidden from the DEFAULT list — but two things un-hide them: typing
    // their name (hidden must never mean unfindable), and BEING CHECKED IN TONIGHT.
    //
    // That second one matters. `archived` says "not currently around", so the moment someone
    // checks Maura in she IS around, and she belongs under "Checked in". Without the
    // `p.attending` clause she got checked in and then instantly vanished from the list —
    // the write succeeded, but the UI swallowed her, which reads to the user as a no-op.
    const visible = people.filter((p) => matches(p) && (!p.archived || q || p.attending))

    if (scope === 'instance') {
      // Attending wins over archived: if they're here, they're here.
      push(visible.filter((p) => p.attending), 'here', 'Checked in')
      const away = visible.filter((p) => !p.attending)
      push(away.filter((p) => !p.archived), 'roster', 'Not checked in')
      push(away.filter((p) => p.archived), 'archived', 'Archived')
    } else {
      push(visible.filter((p) => !p.archived), 'roster', null)
      push(visible.filter((p) => p.archived), 'archived', 'Archived')
    }
    return out
  })

  // "No results — add James Quinn". Split what they typed into a first/last name guess.
  const canCreate = $derived(q.length > 0)
  const noMatches = $derived(items.length === 0)

  function openCreate() {
    const parts = query.trim().split(/\s+/)
    newFirst = parts[0] || ''
    newLast = parts.slice(1).join(' ')
    newEmail = ''
    newInstruments = []
    newOther = ''
    showCreate = true
  }
  function resetCreate() {
    showCreate = false
    newFirst = newLast = newEmail = newOther = ''
    newInstruments = []
  }
  function toggleInstrument(name) {
    newInstruments = newInstruments.includes(name)
      ? newInstruments.filter((i) => i !== name)
      : [...newInstruments, name]
  }
  function addOther() {
    const v = newOther.trim()
    if (v && !newInstruments.some((i) => i.toLowerCase() === v.toLowerCase())) {
      newInstruments = [...newInstruments, v]
    }
    newOther = ''
  }
  function submitCreate() {
    const first = newFirst.trim()
    if (!first) return
    const instruments = [...newInstruments]
    if (newOther.trim()) instruments.push(newOther.trim())
    onCreate({
      first_name: first,
      last_name: newLast.trim(),
      email: newEmail.trim() || null,
      instruments,
    })
    resetCreate()
    query = ''
  }

  function pick(p) {
    onSelect(p)
    // Starter mode commits and leaves; attendance mode is a session of several check-ins,
    // so it stays open and just clears the box for the next name.
    if (mode === 'starter') close()
    else query = ''
  }

  function close() {
    resetCreate()
    query = ''
    open = false
    onClose()
  }

  export function reset() {
    resetCreate()
    query = ''
    active = -1
  }
</script>

<Sheet bind:open title={heading} desktop="dock" onCancel={close} doneLabel="Done" onDone={close}>
  {#if showCreate}
    <div class="pp-create">
      <button class="pp-back" onclick={resetCreate}>‹ Back to list</button>
      <label class="pp-field">
        <span>First name</span>
        <input bind:value={newFirst} placeholder="First name" />
      </label>
      <label class="pp-field">
        <span>Last name</span>
        <input bind:value={newLast} placeholder="Last name" />
      </label>
      <label class="pp-field">
        <span>Email <em>(optional)</em></span>
        <input bind:value={newEmail} type="email" placeholder="name@example.com" />
      </label>
      <!-- Email is the ONLY cross-session identity key (spec 034): supply it and we attach the
           existing person instead of creating a duplicate. Names never match across sessions —
           two different John Smiths are two different people. -->
      <p class="pp-hint">If they already have an account, their email links them to it.</p>

      {#if canonicalInstruments.length}
        <div class="pp-instruments">
          <span class="pp-field-label">Instruments <em>(optional)</em></span>
          <div class="pp-inst-grid">
            {#each canonicalInstruments as inst (inst)}
              <label class="pp-inst">
                <input
                  type="checkbox"
                  checked={newInstruments.includes(inst)}
                  onchange={() => toggleInstrument(inst)}
                />
                <span>{inst}</span>
              </label>
            {/each}
          </div>
          <div class="pp-other">
            <input
              bind:value={newOther}
              placeholder="Other instrument…"
              onkeydown={(e) => e.key === 'Enter' && (e.preventDefault(), addOther())}
            />
            <button onclick={addOther} disabled={!newOther.trim()}>Add</button>
          </div>
          {#each newInstruments.filter((i) => !canonicalInstruments.some((c) => c.toLowerCase() === i.toLowerCase())) as extra (extra)}
            <Chip label={extra} dismissible onDismiss={() => toggleInstrument(extra)} />
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <SearchField
      bind:value={query}
      placeholder={scope === 'session' ? 'Filter people…' : 'Filter or add someone…'}
      debounce={0}
    />

    {#if mode === 'starter' && currentStarterName && !q}
      <button class="pp-clear" onclick={() => { onClear(); close() }}>— Clear —</button>
    {/if}

    <List items={items} bind:active onSelect={pick}>
      {#snippet row(item, isActive)}
        {#if item._label}
          <span class="pp-tier">{item._label}</span>
        {/if}
        <!-- Greying keys off the TIER, not the raw archived flag: someone archived who is
             checked in sits under "Checked in" and should read as present. She
             keeps the chip (it's still true) but not the greyed-out, they're-gone styling. -->
        <span class="pp-row" class:dim={item._tier !== 'here' && scope === 'instance'} class:archived={item._tier === 'archived'}>
          <span class="pp-name">{item.display_name}</span>

          {#if item.archived}
            <Chip label="archived" />
          {/if}
          {#if item.relationship === 'visitor'}
            <Chip label="visitor" />
          {/if}
          {#if item.attending && mode === 'attendance'}
            <button
              class="pp-out"
              title="Check out"
              aria-label={`Check out ${item.display_name}`}
              onclick={(e) => { e.stopPropagation(); onCheckOut(item) }}
            >✕</button>
          {/if}
        </span>
      {/snippet}
    </List>

    {#if noMatches}
      <p class="pp-empty">
        {#if q}No one here by that name.{:else}No one on this session's list yet.{/if}
      </p>
    {/if}

    {#if canCreate}
      <button class="pp-add" onclick={openCreate} disabled={busy}>
        ＋ Add <strong>{query.trim()}</strong>
      </button>
    {/if}
  {/if}

  {#snippet footer()}
    {#if showCreate}
      <button class="pp-commit" onclick={submitCreate} disabled={!newFirst.trim() || busy}>
        Add person
      </button>
    {/if}
  {/snippet}
</Sheet>

<style>
  .pp-tier {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.6;
    margin: 0.6rem 0 0.15rem;
  }
  .pp-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    width: 100%;
  }
  /* Dimming carries the meaning: "this person isn't checked in yet — tapping adds them." */
  .pp-row.dim .pp-name { opacity: 0.62; }
  .pp-row.archived .pp-name { opacity: 0.45; font-style: italic; }
  .pp-name { flex: 1; text-align: left; }
  .pp-out {
    border: 0;
    background: none;
    cursor: pointer;
    opacity: 0.55;
    padding: 0 0.3rem;
    font-size: 0.9rem;
    color: inherit;
  }
  .pp-out:hover { opacity: 1; }
  .pp-clear,
  .pp-add,
  .pp-back {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: 0;
    padding: 0.55rem 0.2rem;
    cursor: pointer;
    color: inherit;
    font: inherit;
  }
  .pp-add { opacity: 0.9; }
  .pp-add:hover, .pp-clear:hover, .pp-back:hover { opacity: 1; text-decoration: underline; }
  .pp-empty { opacity: 0.6; padding: 0.8rem 0.2rem; margin: 0; }
  .pp-field { display: block; margin-bottom: 0.6rem; }
  .pp-field span, .pp-field-label {
    display: block;
    font-size: 0.78rem;
    opacity: 0.75;
    margin-bottom: 0.2rem;
  }
  .pp-field input, .pp-other input {
    width: 100%;
    padding: 0.45rem 0.55rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-color);
    color: inherit;
    font: inherit;
  }
  .pp-hint { font-size: 0.78rem; opacity: 0.6; margin: 0 0 0.8rem; }
  .pp-inst-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
    gap: 0.2rem 0.6rem;
    margin-bottom: 0.5rem;
  }
  .pp-inst { display: flex; align-items: center; gap: 0.35rem; font-size: 0.86rem; }
  .pp-other { display: flex; gap: 0.4rem; margin-bottom: 0.5rem; }
  .pp-other button, .pp-commit {
    padding: 0.45rem 0.8rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--hover-bg);
    color: inherit;
    cursor: pointer;
    font: inherit;
  }
  .pp-commit { width: 100%; }
  .pp-commit:disabled, .pp-other button:disabled { opacity: 0.45; cursor: default; }
</style>
