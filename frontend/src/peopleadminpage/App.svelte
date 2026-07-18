<script>
  // The /admin/people table (spec 035 final migration) — ported behavior-for-
  // behavior from the inline script in the legacy templates/admin_people.html.
  // Same DOM contract (#people-search, #add-person-btn, #people-tbody,
  // #addPersonModal, #person-input — the e2e suite selects on these). First
  // paint comes from the embedded payload; search/sort are client-side; the
  // 2-step add-person wizard is a pair of kit Sheets (the PeopleTab pattern).
  import { toast, SearchField, Chip, Sheet } from '../lib/index.js'
  import { normalizeQuotes } from '../shared/parse.js'

  let { pageData = null } = $props()

  let people = $state(pageData?.success ? pageData.people : [])
  let searchText = $state('')
  const searchTerm = $derived(normalizeQuotes(searchText.toLowerCase().trim()))

  // ---- display formatting (raw payload values -> the legacy strings) ----------
  // Timestamps arrive as naive-local ISO strings; slice instead of constructing
  // a Date so there is no timezone re-interpretation at all (see shared/parse.js
  // parseLocalDate for why Date-parsing serialized dates is a trap).
  const fmtTimestamp = (iso) => (iso ? `${iso.slice(0, 10)} ${iso.slice(11, 16)}` : null)

  const locationOf = (p) => {
    const parts = [p.city, p.state, p.country].filter(Boolean)
    return parts.length > 0 ? parts.join(', ') : 'Unknown'
  }

  // A person with blank first+last name still needs a clickable label.
  const displayName = (p) => (p.name || '').trim() || p.username || '(unnamed)'

  // ---- account filter (droplist: all people vs. only those with a login) --------
  let accountFilter = $state('all') // 'all' | 'users'
  // ---- active filter (droplist; deactivated people are hidden by default) -------
  let activeFilter = $state('active') // 'active' | 'all'

  // ---- search (same fields the legacy data-person-* attributes carried) --------
  const filtered = $derived(
    people.filter((p) => {
      if (accountFilter === 'users' && !p.username) return false
      if (activeFilter === 'active' && p.active === false) return false
      if (!searchTerm) return true
      const haystack = [
        p.name,
        p.email || '',
        p.username || 'no account',
        [p.city, p.state, p.country].filter(Boolean).join(' '),
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(searchTerm)
    })
  )

  // ---- sort ---------------------------------------------------------------------
  const COLUMNS = [
    { id: 'name', label: 'Name', type: 'text', key: (p) => displayName(p).toLowerCase() },
    { id: 'location', label: 'Location', type: 'text', key: (p) => (p.city || '').toLowerCase() },
    { id: 'thesession', label: 'TheSession.org', type: 'number', key: (p) => p.thesession_user_id || 0 },
    { id: 'username', label: 'Username', type: 'text', key: (p) => (p.username || 'no account').toLowerCase() },
    { id: 'sessions', label: 'Sessions', type: 'number', key: (p) => p.session_count },
    { id: 'instances', label: 'Checked In', type: 'number', key: (p) => p.session_instance_count },
    { id: 'tunes', label: 'Tunes', type: 'number', key: (p) => p.tune_count },
    { id: 'latest', label: 'Latest Session', type: 'date', key: (p) => p.latest_session_date || '' },
    { id: 'logged', label: 'Last Logged A Tune', type: 'date', key: (p) => p.last_logged_tune || '' },
    { id: 'tunebook', label: 'Last Updated Their Tunebook', type: 'date', key: (p) => p.last_tunebook_update || '' },
    { id: 'login', label: 'Last Login', type: 'date', key: (p) => p.last_login || '' },
  ]

  let sortColumn = $state(null)
  let sortDirection = $state('asc')

  function sortBy(column) {
    if (sortColumn === column) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc'
    } else {
      sortColumn = column
      sortDirection = 'asc'
    }
  }

  const rows = $derived.by(() => {
    if (!sortColumn) return filtered
    const col = COLUMNS.find((c) => c.id === sortColumn)
    const dir = sortDirection === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => {
      const aVal = col.key(a)
      const bVal = col.key(b)
      if (col.type === 'date') {
        // Empty means no date (Never / N/A / None): always sort last,
        // regardless of direction.
        if (!aVal && !bVal) return 0
        if (!aVal) return 1
        if (!bVal) return -1
      }
      if (col.type === 'number') return (aVal - bVal) * dir
      if (aVal < bVal) return -dir
      if (aVal > bVal) return dir
      return 0
    })
  })

  function refetchPeople() {
    fetch('/api/admin/people')
      .then((r) => r.json())
      .then((data) => {
        if (data.success) people = data.people
      })
      .catch((error) => console.error('Error refreshing people:', error))
  }

  // ---- add-person wizard (2 kit Sheets, the PeopleTab pattern) --------------------
  let step1Open = $state(false)
  let step2Open = $state(false)
  let personInput = $state('')
  let step1Error = $state('')
  let step2Error = $state('')
  let step1Busy = $state(false)
  let saving = $state(false)

  // step-2 form fields
  let firstName = $state('')
  let lastName = $state('')
  let email = $state('')
  let smsNumber = $state('')
  let city = $state('')
  let stateArea = $state('')
  let country = $state('')
  let thesessionUserId = $state('')
  let sessionId = $state('')
  let sessions = $state([])

  function openAddPerson() {
    personInput = ''
    step1Error = ''
    step1Open = true
    loadSessions()
  }

  function loadSessions() {
    fetch('/api/sessions/list')
      .then((r) => r.json())
      .then((data) => {
        if (data.success) sessions = data.sessions
      })
      .catch((error) => console.error('Error loading sessions:', error))
  }

  function processStep1() {
    const input = personInput.trim()
    if (!input) {
      step1Error = 'Please enter a name or TheSession.org URL/ID'
      return
    }
    step1Error = ''
    step1Busy = true
    // TheSession.org entity (member URL or bare ID) vs a regular name
    const isTheSession = /^\d+$/.test(input) || input.startsWith('https://thesession.org/')
    const endpoint = isTheSession ? '/api/validate-thesession-user' : '/api/parse-person-name'
    const body = isTheSession ? { user_input: input } : { name: input }

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then((r) => r.json())
      .then((data) => {
        step1Busy = false
        if (data.success) {
          firstName = data.first_name || ''
          lastName = data.last_name || ''
          thesessionUserId = data.thesession_user_id || ''
          email = ''
          smsNumber = ''
          city = ''
          stateArea = ''
          country = ''
          sessionId = ''
          step2Error = ''
          step1Open = false
          step2Open = true
        } else {
          step1Error = data.message
        }
      })
      .catch((error) => {
        step1Busy = false
        step1Error = 'Error looking up person: ' + error.message
      })
  }

  function backToStep1() {
    step2Open = false
    step1Open = true
  }

  function saveNewPerson() {
    if (!firstName.trim()) {
      step2Error = 'First name is required'
      return
    }
    saving = true
    fetch('/api/create-person', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        email,
        sms_number: smsNumber,
        city,
        state: stateArea,
        country,
        thesession_user_id: thesessionUserId || null,
        session_id: sessionId || null,
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        saving = false
        if (data.success) {
          step2Open = false
          toast(data.message, 'success')
          // The legacy page reloaded; refetching the same payload endpoint
          // updates the table in place.
          refetchPeople()
        } else {
          step2Error = data.message
        }
      })
      .catch((error) => {
        saving = false
        step2Error = 'Error creating person: ' + error.message
      })
  }
</script>

<section class="admin-section" id="people">
  <!-- Search and Add Button -->
  <div class="people-toolbar">
    <SearchField
      bind:value={searchText}
      id="people-search"
      inputClass="form-control people-search-input"
      wrapperClass="people-search-wrap"
      styled={false}
      placeholder="Search by name, email, username, or location..." />
    <select
      id="people-account-filter"
      class="form-control people-account-filter"
      aria-label="Filter by account"
      bind:value={accountFilter}>
      <option value="users">Site Users Only</option>
      <option value="all">All People</option>
    </select>
    <select
      id="people-active-filter"
      class="form-control people-account-filter"
      aria-label="Filter by active status"
      bind:value={activeFilter}>
      <option value="active">Active Only</option>
      <option value="all">All</option>
    </select>
    <button id="add-person-btn" class="btn btn-primary btn-add-person" onclick={openAddPerson}>Add Person</button>
  </div>

  <div id="people-content">
    {#if people.length === 0}
      <div class="alert alert-info" role="alert">
        <h4 class="alert-heading">No People Found</h4>
        <p>There are currently no people records in the system.</p>
      </div>
    {:else}
      <div class="table-responsive">
        <table class="table table-striped">
          <thead>
            <tr>
              {#each COLUMNS as col (col.id)}
                <th
                  class="sortable"
                  class:asc={sortColumn === col.id && sortDirection === 'asc'}
                  class:desc={sortColumn === col.id && sortDirection === 'desc'}
                  data-column={col.id}
                  data-type={col.type}
                  onclick={() => sortBy(col.id)}>
                  {col.label} <span class="sort-indicator"></span>
                </th>
              {/each}
            </tr>
          </thead>
          <tbody id="people-tbody">
            {#each rows as person (person.person_id)}
              <tr class:person-inactive={person.active === false}>
                <td class="person-name">
                  <a href="/admin/people/{person.person_id}" class="person-link">{displayName(person)}</a>
                </td>
                <td class="person-location" title={locationOf(person)}>{person.city || 'Unknown'}</td>
                <td class="person-thesession">
                  {#if person.thesession_user_id}
                    <a href="https://thesession.org/members/{person.thesession_user_id}" target="_blank" rel="noopener noreferrer">
                      {person.thesession_user_id}
                    </a>
                  {:else}
                    <span class="text-muted">No member</span>
                  {/if}
                </td>
                <td class="person-username">
                  {#if person.username}
                    <strong>{person.username}</strong>
                    {#if person.is_system_admin}
                      <span class="admin-indicator">(admin)</span>
                    {/if}
                  {:else}
                    <span class="text-muted">No account</span>
                  {/if}
                </td>
                <td class="person-session-count">
                  {#if person.session_count > 0}
                    <Chip label={String(person.session_count)} styled={false} chipClass="badge bg-primary" />
                  {:else}
                    <span class="text-muted">0</span>
                  {/if}
                </td>
                <td class="person-instance-count">
                  {#if person.session_instance_count > 0}
                    <Chip label={String(person.session_instance_count)} styled={false} chipClass="badge bg-success" />
                  {:else}
                    <span class="text-muted">0</span>
                  {/if}
                </td>
                <td class="person-tune-count">
                  {#if person.tune_count > 0}
                    <Chip label={String(person.tune_count)} styled={false} chipClass="badge bg-info" />
                  {:else}
                    <span class="text-muted">0</span>
                  {/if}
                </td>
                <td class="person-latest-session">
                  {#if person.latest_session_date}
                    <span class="latest-session-info">{person.latest_session_date} - {person.latest_session_name}</span>
                  {:else}
                    <span class="text-muted">None</span>
                  {/if}
                </td>
                <td class="person-last-logged">
                  {#if person.last_logged_tune}
                    {fmtTimestamp(person.last_logged_tune)}
                  {:else}
                    <span class="text-muted">Never</span>
                  {/if}
                </td>
                <td class="person-last-tunebook">
                  {#if person.last_tunebook_update}
                    {fmtTimestamp(person.last_tunebook_update)}
                  {:else}
                    <span class="text-muted">Never</span>
                  {/if}
                </td>
                <td class="person-last-login">
                  {#if person.last_login}
                    {fmtTimestamp(person.last_login)}
                  {:else if person.username}
                    <span class="text-warning">Never</span>
                  {:else}
                    <span class="text-muted">N/A</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if rows.length === 0 && (searchTerm || accountFilter !== 'all' || activeFilter !== 'all')}
        <div id="no-search-results" class="alert alert-info">
          <p class="mb-0">No people match your search criteria.</p>
        </div>
      {/if}
    {/if}
  </div>
</section>

<!-- Add Person, step 1: name or thesession.org URL/ID -->
<Sheet bind:open={step1Open} title="Add Person">
  <div id="addPersonModal" class="add-person-step">
    <div class="mb-3">
      <label for="person-input" class="form-label">Enter the person's name, or URL or ID from thesession.org:</label>
      <input
        type="text"
        id="person-input"
        class="form-control"
        placeholder="e.g. 'John Smith' or 'https://thesession.org/members/12345' or '12345'"
        bind:value={personInput}
        onkeydown={(e) => e.key === 'Enter' && processStep1()} />
      {#if step1Error}
        <div id="step1-error" class="step-error" role="alert">{step1Error}</div>
      {/if}
    </div>
  </div>
  {#snippet footer()}
    <div class="add-person-actions">
      <button id="step1-next" class="btn btn-primary" disabled={step1Busy} onclick={processStep1}>
        {step1Busy ? 'Looking up...' : 'Next'}
      </button>
    </div>
  {/snippet}
</Sheet>

<!-- Add Person, step 2: details form (commit lives in the footer so a failed
     POST keeps the form open; the back chevron returns to step 1) -->
<Sheet bind:open={step2Open} title="Add Person" back="Back" onCancel={backToStep1}>
  <form id="add-person-form" class="add-person-step" onsubmit={(e) => e.preventDefault()}>
    <div class="add-person-grid">
      <div>
        <div class="mb-3">
          <label for="add-first-name" class="form-label">First Name</label>
          <input type="text" class="form-control" id="add-first-name" required bind:value={firstName} />
        </div>
        <div class="mb-3">
          <label for="add-last-name" class="form-label">Last Name</label>
          <input type="text" class="form-control" id="add-last-name" required bind:value={lastName} />
        </div>
        <div class="mb-3">
          <label for="add-email" class="form-label">Email</label>
          <input type="email" class="form-control" id="add-email" bind:value={email} />
        </div>
        <div class="mb-3">
          <label for="add-sms-number" class="form-label">SMS Number</label>
          <input type="text" class="form-control" id="add-sms-number" bind:value={smsNumber} />
        </div>
      </div>
      <div>
        <div class="mb-3">
          <label for="add-city" class="form-label">City</label>
          <input type="text" class="form-control" id="add-city" bind:value={city} />
        </div>
        <div class="mb-3">
          <label for="add-state" class="form-label">State</label>
          <input type="text" class="form-control" id="add-state" bind:value={stateArea} />
        </div>
        <div class="mb-3">
          <label for="add-country" class="form-label">Country</label>
          <input type="text" class="form-control" id="add-country" bind:value={country} />
        </div>
        <div class="mb-3">
          <label for="add-thesession-user-id" class="form-label">TheSession User ID</label>
          <input type="number" class="form-control" id="add-thesession-user-id" readonly value={thesessionUserId} />
        </div>
      </div>
    </div>
    <div class="mb-3">
      <label for="add-session-select" class="form-label">Add to Session (optional)</label>
      <select class="form-control" id="add-session-select" bind:value={sessionId}>
        <option value="">Do not add to any sessions</option>
        {#each sessions as session (session.session_id)}
          <option value={session.session_id}>{session.display_name}</option>
        {/each}
      </select>
    </div>
    {#if step2Error}
      <div id="step2-error" class="step-error" role="alert">{step2Error}</div>
    {/if}
  </form>
  {#snippet footer()}
    <div class="add-person-actions">
      <button id="step2-save" class="btn btn-success" disabled={saving} onclick={saveNewPerson}>
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  {/snippet}
</Sheet>
