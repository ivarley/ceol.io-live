<script>
  // The /sessions directory (spec 035 Step 4a) — ported behavior-for-behavior from
  // the legacy inline script in templates/sessions.html. Same DOM contract
  // (#search-bar, #sessions-table, #sessions-tbody, #no-results — the e2e suite and
  // this bundle's page.css select on these). First paint comes from the embedded
  // payload; a background refetch of the same API keeps it fresh.
  import { untrack } from 'svelte'
  import { SearchField } from '../lib/index.js'

  let { pageData = null, isLoggedIn = false } = $props()

  // Filter states cycle on the toggle button; logged-out users have no "My Sessions".
  const filterStates = isLoggedIn ? ['my', 'active', 'all', 'inactive'] : ['active', 'all', 'inactive']
  const filterButtonLabels = {
    my: 'My Sessions',
    active: 'All Active',
    all: 'All',
    inactive: 'Inactive',
  }
  const countLabels = {
    my: 'sessions in your list',
    active: 'active sessions',
    all: 'sessions',
    inactive: 'inactive sessions',
  }

  let allSessions = $state([])
  let loaded = $state(false)
  let loadError = $state(false)
  let filterIndex = $state(0)
  let rawSearch = $state('')
  // Instant client-side filter (legacy behavior): derive from the bound value.
  const searchTerm = $derived(normalizeQuotes(rawSearch.toLowerCase()))

  const currentFilter = $derived(filterStates[filterIndex])

  // Normalize smart quotes to straight quotes (iOS keyboard compatibility).
  const normalizeQuotes = (str) =>
    str.replace(/[‘’]/g, "'").replace(/[“”]/g, '"')

  function adopt(sessions) {
    allSessions = sessions || []
    // Logged in but not a member of anything: default to "All Active" instead
    // of an empty "My Sessions" view (legacy behavior).
    if (isLoggedIn && filterStates[filterIndex] === 'my' && !allSessions.some((s) => s.user_is_member)) {
      filterIndex = filterStates.indexOf('active')
    }
    loaded = true
  }

  if (pageData && pageData.success) adopt(pageData.sessions)

  $effect(() => {
    // Mount-once background refresh; a failure never blanks an already-shown list.
    untrack(() => {
      fetch('/api/sessions/with-today-status', { credentials: 'same-origin' })
        .then((r) => r.json())
        .then((d) => {
          if (d.success) adopt(d.sessions)
          else if (!loaded) loadError = true
        })
        .catch(() => {
          if (!loaded) loadError = true
        })
    })
  })

  const filtered = $derived.by(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return allSessions.filter((session) => {
      let passes = false
      if (currentFilter === 'my') {
        passes = session.user_is_member
      } else if (currentFilter === 'active') {
        passes = !session.termination_date || new Date(session.termination_date) > today
      } else if (currentFilter === 'all') {
        passes = true
      } else if (currentFilter === 'inactive') {
        passes = !!session.termination_date && new Date(session.termination_date) <= today
      }
      if (!passes) return false
      if (searchTerm) {
        const location = [session.city, session.state, session.country]
          .filter(Boolean)
          .join(', ')
          .toLowerCase()
        return session.name.toLowerCase().includes(searchTerm) || location.includes(searchTerm)
      }
      return true
    })
  })

  function formatTime(timeStr) {
    if (!timeStr) return ''
    const parts = timeStr.split(':')
    let hour = parseInt(parts[0], 10)
    const minute = parts[1]
    const period = hour >= 12 ? 'pm' : 'am'
    hour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour
    return `${hour}:${minute}${period}`
  }

  function formatTimeRange(startTime, endTime) {
    if (!startTime) return ''
    const start = formatTime(startTime)
    return endTime ? `${start}-${formatTime(endTime)}` : start + ' - ?'
  }

  const locationOf = (s) => [s.city, s.state, s.country].filter(Boolean).join(', ') || 'Unknown'

  function instanceLabel(session, instance) {
    const timeStr = formatTimeRange(instance.start_time, instance.end_time)
    const locationStr = instance.location_override || session.location_name || ''
    return [timeStr, locationStr].filter(Boolean).join(' @ ')
  }

  const goto = (url) => (window.location.href = url)
</script>

<h1>Sessions</h1>

<div class="sessions-controls">
  <div class="search-and-toggle">
    <SearchField
      bind:value={rawSearch}
      id="search-bar"
      inputClass="search-bar"
      wrapperClass="search-bar-wrap"
      styled={false}
      placeholder="Search by name or location..." />
    <button
      class="filter-toggle-button"
      id="filter-toggle-button"
      onclick={() => (filterIndex = (filterIndex + 1) % filterStates.length)}>
      {filterButtonLabels[currentFilter]}
    </button>
  </div>

  <div class="session-count" id="session-count">
    Showing <span id="count-number">{filtered.length}</span>
    <span id="count-filter-type">{countLabels[currentFilter] || 'sessions'}</span>.
  </div>
</div>

{#if !loaded}
  <div id="loading-message" class="loading-message">
    {#if loadError}Error loading sessions{:else}Loading<span class="loading-dots">...</span>{/if}
  </div>
{:else if filtered.length === 0}
  <div id="no-results" class="no-sessions">No sessions found.</div>
{:else}
  <table class="sessions-grid" id="sessions-table">
    <thead>
      <tr>
        <th>Name</th>
        <th>Location</th>
        <th></th>
      </tr>
    </thead>
    <tbody id="sessions-tbody">
      {#each filtered as session (session.session_id)}
        <tr>
          <td><a href="/sessions/{session.path}">{session.name}</a></td>
          <td>{locationOf(session)}</td>
          <td class="action-cell">
            {#if session.active_instances && session.active_instances.length === 1}
              <button
                class="today-action-btn btn-goto-today"
                onclick={() => goto(`/sessions/${session.path}/${session.active_instances[0].date}`)}>
                On Now
              </button>
            {:else if session.active_instances && session.active_instances.length > 1}
              <select
                class="today-action-btn btn-goto-today"
                id="dropdown-{session.session_id}"
                onchange={(e) => e.target.value && goto(`/sessions/${session.path}/${e.target.value}`)}>
                <option value="">On Now ...</option>
                {#each session.active_instances as instance (instance.session_instance_id)}
                  <option value={instance.date}>{instanceLabel(session, instance)}</option>
                {/each}
              </select>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<p style="font-size: 0.85rem; color: var(--secondary-text);">
  Don't see your session? <a href="/add-session">Add it!</a>
</p>

<p><a href="/">← Back to home</a></p>
