<script>
  // People (Members) tab: session membership table with members/everyone (spec 034:
  // is_regular is gone -- the meaningful split is member vs visitor)
  // filter, name/email search (smart-quote normalized), and sortable columns.
  import { SvelteSet } from 'svelte/reactivity'
  import { SearchField, Dialog, toast } from '../lib/index.js'
  import PersonFlags from './PersonFlags.svelte'
  import { normalizeQuotes, parseLocalDate } from '../shared/parse.js'
  import { compareValues, personSortValue } from './logic.js'

  // trackAttendance (spec 039): membership management stays regardless, but the two
  // attendance-derived columns are dropped when the session isn't tracking attendance.
  let { sessionPath, load, trackAttendance = true } = $props()

  let allPeople = $state(null) // null until loaded
  let loadError = $state(null)
  let filter = $state('members')
  let search = $state('')
  let sortColumn = $state('name')
  let sortDirection = $state('asc')
  let started = false

  $effect(() => {
    if (load && !started) {
      started = true
      fetch(`/api/admin/sessions/${sessionPath}/people`)
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            loadError = data.error
            return
          }
          allPeople = data.players
        })
        .catch((error) => {
          loadError = `Failed to load members: ${error}`
        })
    }
  })

  function sortPeople(column) {
    if (sortColumn === column) {
      // Toggle direction if same column
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc'
    } else {
      // New column, default to ascending
      sortColumn = column
      sortDirection = 'asc'
    }
  }

  const filteredPeople = $derived.by(() => {
    if (!allPeople) return []
    let filtered = allPeople
    // Members-vs-everyone. Archived people are the ones who've genuinely gone, so they only
    // show under "Everyone".
    if (filter === 'members') {
      filtered = filtered.filter(
        (person) => person.relationship !== 'visitor' && !person.archived
      )
    }
    // Apply name search
    const q = normalizeQuotes(search.toLowerCase())
    if (q) {
      filtered = filtered.filter(
        (person) => person.name.toLowerCase().includes(q) || (person.email || '').toLowerCase().includes(q)
      )
    }
    return [...filtered].sort((a, b) =>
      compareValues(personSortValue(a, sortColumn), personSortValue(b, sortColumn), sortDirection)
    )
  })

  const indicator = (column) => (sortColumn !== column ? '' : sortDirection === 'asc' ? ' ↑' : ' ↓')

  // ---- select / act (spec 034) -------------------------------------------------
  // Roster hygiene is a BULK job -- an admin tidying up after a few years is archiving a
  // dozen people who moved away, not one. Doing that one person-page at a time is the kind
  // of chore nobody does, which is how rosters rot in the first place.
  let selectMode = $state(false)
  let selected = $state(new SvelteSet()) // plain Sets aren't reactive in $state
  let busy = $state(false)
  let confirmOpen = $state(false)

  const selectedPeople = $derived(filteredPeople.filter((p) => selected.has(p.person_id)))
  const allVisibleSelected = $derived(
    filteredPeople.length > 0 && filteredPeople.every((p) => selected.has(p.person_id))
  )

  function toggleSelectMode() {
    selectMode = !selectMode
    if (!selectMode) selected.clear()
  }
  function toggleOne(id) {
    if (selected.has(id)) selected.delete(id)
    else selected.add(id)
  }
  function toggleAll() {
    if (allVisibleSelected) filteredPeople.forEach((p) => selected.delete(p.person_id))
    else filteredPeople.forEach((p) => selected.add(p.person_id))
  }

  /** PUT one field across every selected person, then patch the rows in place. */
  async function applyToSelected(field, value, label) {
    const ids = selectedPeople.map((p) => p.person_id)
    if (!ids.length) return
    busy = true
    try {
      const results = await Promise.all(
        ids.map((id) =>
          fetch(`/api/sessions/${sessionPath}/people/${id}/${field}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [field]: value }),
          })
            .then((r) => r.json())
            .then((d) => (d.success ? id : null))
            .catch(() => null)
        )
      )
      const ok = results.filter((id) => id !== null)
      // Patch only the rows that actually saved -- never claim a write that didn't happen.
      allPeople = allPeople.map((p) => (ok.includes(p.person_id) ? { ...p, [field]: value } : p))

      if (ok.length === ids.length) {
        toast(`${label}: ${ok.length} ${ok.length === 1 ? 'person' : 'people'}.`, 'success')
      } else {
        toast(`${label}: ${ok.length} of ${ids.length} saved — ${ids.length - ok.length} failed.`, 'error')
      }
      selected.clear()
    } finally {
      busy = false
    }
  }

  // Confirming in bulk hands the roster to everyone selected, so it asks first. The other
  // actions are reversible in one click and don't grant anything, so they just run.
  const askConfirm = () => (confirmOpen = true)
</script>

<section class="docs-section">
  <!-- Controls -->
  <div class="mb-3">
    <div class="d-flex align-items-center gap-3">
      <div class="flex-grow-1">
        <SearchField
          bind:value={search}
          id="people-search"
          inputClass="form-control"
          styled={false}
          placeholder="Search by name..." />
      </div>
      <div>
        <a href="/admin/sessions/{sessionPath}/bulk-import" class="btn btn-outline-primary btn-sm">
          <i class="fas fa-upload me-1"></i>Bulk Import
        </a>
      </div>
      <div>
        <!--
          Styled explicitly rather than with .btn-outline-*: this page's theme gives those
          colour but NO border, so they render as bare links. A mode toggle nobody can see is
          a mode nobody uses -- the first thing asked about this feature was "how do I enter
          select mode?". (FontAwesome isn't loaded here either, hence no icon.)
        -->
        <button
          type="button"
          class="people-select-btn"
          class:active={selectMode}
          id="people-select-btn"
          onclick={toggleSelectMode}>
          {selectMode ? '\u2715 Cancel' : '\u2611 Select'}
        </button>
      </div>
      <div class="ms-auto">
        <select class="form-select people-filter-select" id="people-filter" bind:value={filter}>
          <option value="members">Members Only</option>
          <option value="everyone">Everyone</option>
        </select>
      </div>
    </div>
  </div>

  {#if selectMode}
    <div class="people-actions mb-3" id="people-actions">
      <span class="people-actions-count">
        {selected.size} selected
      </span>
      <div class="people-actions-btns">
        <button class="pa-btn pa-btn-primary" disabled={!selected.size || busy} onclick={askConfirm}>
          Confirm
        </button>
        <button class="pa-btn" disabled={!selected.size || busy}
          onclick={() => applyToSelected('confirmed', false, 'Un-confirmed')}>
          Un-confirm
        </button>
        <span class="people-actions-sep"></span>
        <button class="pa-btn" disabled={!selected.size || busy}
          onclick={() => applyToSelected('archived', true, 'Archived')}>
          Archive
        </button>
        <button class="pa-btn" disabled={!selected.size || busy}
          onclick={() => applyToSelected('archived', false, 'Restored')}>
          Restore
        </button>
        <span class="people-actions-sep"></span>
        <button class="pa-btn" disabled={!selected.size || busy}
          onclick={() => applyToSelected('relationship', 'member', 'Set to member')}>
          Member
        </button>
        <button class="pa-btn" disabled={!selected.size || busy}
          onclick={() => applyToSelected('relationship', 'visitor', 'Set to visitor')}>
          Visitor
        </button>
      </div>
    </div>
  {/if}

  <div id="people-content">
    {#if loadError}
      <div class="alert alert-danger">{loadError}</div>
    {:else if !allPeople}
      <p class="text-muted">Loading members...</p>
    {:else if allPeople.length === 0}
      <div class="alert alert-info">No members found for this session.</div>
    {:else if filteredPeople.length === 0}
      <div class="alert alert-info">No members match the current filter.</div>
    {:else}
      <div class="table-responsive">
        <table class="table table-striped">
          <thead>
            <tr>
              {#if selectMode}
                <th class="people-check">
                  <input
                    type="checkbox"
                    class="form-check-input"
                    aria-label="Select all"
                    checked={allVisibleSelected}
                    onchange={toggleAll} />
                </th>
              {/if}
              <th style="cursor: pointer;" onclick={() => sortPeople('name')}>Name{indicator('name')}</th>
              <th style="cursor: pointer;" onclick={() => sortPeople('email')}>Email{indicator('email')}</th>
              <th class="person-flags-h" title="User · Confirmed · Member · Visitor · Archived · Session admin · System admin">Status</th>
              {#if trackAttendance}
                <th style="cursor: pointer;" onclick={() => sortPeople('attendance')}>Attendance{indicator('attendance')}</th>
                <th style="cursor: pointer;" onclick={() => sortPeople('last_attended')}>Last Attended{indicator('last_attended')}</th>
              {/if}
            </tr>
          </thead>
          <tbody>
            {#each filteredPeople as person (person.person_id)}
              <tr class:selected={selectMode && selected.has(person.person_id)}>
                {#if selectMode}
                  <td class="people-check">
                    <input
                      type="checkbox"
                      class="form-check-input"
                      aria-label={`Select ${person.name}`}
                      checked={selected.has(person.person_id)}
                      onchange={() => toggleOne(person.person_id)} />
                  </td>
                {/if}
                <td class="person-name">
                  <a href="/admin/sessions/{sessionPath}/people/{person.person_id}" class="person-link">
                    {person.name}
                  </a>
                </td>
                <td class="person-email">{#if person.email}{person.email}{:else}<span class="text-muted">No email</span>{/if}</td>
                <td class="person-status"><PersonFlags {person} /></td>
                {#if trackAttendance}
                  <td class="person-attendance">{person.attendance_count} sessions</td>
                  <td class="person-last-attended">
                    {#if person.last_attended}{parseLocalDate(person.last_attended).toLocaleDateString()}{:else}<span class="text-muted">Never</span>{/if}
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>

<!-- Confirming is the ONE action here that grants something, so it asks. -->
<Dialog
  bind:open={confirmOpen}
  title={`Confirm ${selected.size} ${selected.size === 1 ? 'person' : 'people'}?`}
  description="They will be able to see this session's people list and attendance records."
  confirmLabel="Confirm them"
  onConfirm={() => applyToSelected('confirmed', true, 'Confirmed')} />

<style>
  .people-select-btn {
    white-space: nowrap;
    padding: 0.3rem 0.7rem;
    font-size: 0.86rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--hover-bg);
    color: var(--text-color);
    cursor: pointer;
  }
  .people-select-btn:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
  .people-select-btn.active {
    background: var(--primary);
    border-color: var(--primary);
    color: #fff;
  }
  .people-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--hover-bg);
    color: var(--text-color);
  }
  .people-actions-count { font-size: 0.86rem; opacity: 0.8; white-space: nowrap; }
  .people-actions-btns { display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap; }
  /* Same reason as the Select button: this page's .btn-outline-* have colour but no border,
     so they render as bare links. An action bar of links doesn't read as an action bar. */
  .pa-btn {
    padding: 0.25rem 0.6rem;
    font-size: 0.82rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-color);
    color: var(--text-color);
    cursor: pointer;
    white-space: nowrap;
  }
  .pa-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
  .pa-btn:disabled { opacity: 0.45; cursor: default; }
  .pa-btn-primary:not(:disabled) {
    background: var(--primary);
    border-color: var(--primary);
    color: #fff;
  }
  .pa-btn-primary:hover:not(:disabled) { color: #fff; opacity: 0.9; }
  .people-actions-sep {
    width: 1px;
    height: 1.2rem;
    background: var(--border-color);
    margin: 0 0.25rem;
  }
  .people-check { width: 2.5rem; }
  .person-flags-h, :global(td.person-status) { width: 1%; white-space: nowrap; }
  tr.selected { background: var(--hover-bg); }
</style>
