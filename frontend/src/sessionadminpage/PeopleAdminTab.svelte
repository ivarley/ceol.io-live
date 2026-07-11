<script>
  // People (Members) tab: session membership table with regulars/everyone
  // filter, name/email search (smart-quote normalized), and sortable columns.
  import { SearchField } from '../lib/index.js'
  import { normalizeQuotes } from '../shared/parse.js'
  import { compareValues, personSortValue } from './logic.js'

  let { sessionPath, load } = $props()

  let allPeople = $state(null) // null until loaded
  let loadError = $state(null)
  let filter = $state('regulars')
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
    // Apply regular/everyone filter
    if (filter === 'regulars') {
      filtered = filtered.filter((person) => person.is_regular)
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
      <div class="ms-auto">
        <select class="form-select people-filter-select" id="people-filter" bind:value={filter}>
          <option value="regulars">Regulars Only</option>
          <option value="everyone">Everyone</option>
        </select>
      </div>
    </div>
  </div>

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
              <th style="cursor: pointer;" onclick={() => sortPeople('name')}>Name{indicator('name')}</th>
              <th style="cursor: pointer;" onclick={() => sortPeople('email')}>Email{indicator('email')}</th>
              <th>Status</th>
              <th style="cursor: pointer;" onclick={() => sortPeople('attendance')}>Attendance{indicator('attendance')}</th>
              <th style="cursor: pointer;" onclick={() => sortPeople('last_attended')}>Last Attended{indicator('last_attended')}</th>
              <th>Admin</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredPeople as person (person.person_id)}
              <tr>
                <td class="person-name">
                  <a href="/admin/sessions/{sessionPath}/people/{person.person_id}" class="person-link">
                    {person.name}
                  </a>
                </td>
                <td class="person-email">{#if person.email}{person.email}{:else}<span class="text-muted">No email</span>{/if}</td>
                <td class="person-status">
                  {#if person.is_regular}<span class="badge bg-success">Regular</span>{/if}
                  {#if person.username}<span class="badge bg-info">User</span>{/if}
                </td>
                <td class="person-attendance">{person.attendance_count} sessions</td>
                <td class="person-last-attended">
                  {#if person.last_attended}{new Date(person.last_attended).toLocaleDateString()}{:else}<span class="text-muted">Never</span>{/if}
                </td>
                <td class="person-admin">
                  {#if person.is_admin}<span class="badge bg-primary">Session</span>{/if}
                  {#if person.is_system_admin}<span class="badge bg-warning">System</span>{/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>
