<script>
  /**
   * The People tab — this session's roster (spec 034).
   *
   * Gated on can_view_people (is_admin OR confirmed), NOT membership: joining a session must
   * not hand you its roster. The tab isn't even rendered for an unconfirmed member.
   *
   * What changed in 034:
   *  - The All/Regulars toggle is gone with is_regular. Ordering is computed from actual
   *    attendance (server-side), so who actually turns up is who you see first; nobody is
   *    hidden by a filter, and nobody is labelled with a rank.
   *  - The two stacked sheets (search-all-people → create-person) became ONE PersonPicker.
   *    Its search is local, because there is nothing to search but this roster: 034 removed
   *    global person search entirely, so you can't discover people from other sessions.
   *  - Visitors and archived people are behind filter chips rather than in your face.
   *  - The person sheet gained the admin controls: Confirm (which grants people-visibility,
   *    and says so at the point of click) and Archive (roster hygiene).
   */
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { toast, SearchField, Chip, Sheet, Seg, PersonPicker } from '../lib/index.js'
  import { normalizeQuotes } from '../shared/parse.js'
  import { filterPeople } from './logic.js'

  let {
    active,
    sessionPath,
    sessionType,
    canonicalInstruments = [],
    currentUserId = null,
    initialPersonId = null,
    isSessionAdmin = false,
    // Spec 039: when the session isn't tracking attendance the roster still shows (this
    // is the members list, gated separately by show_people_list), but with no attendance
    // counts or attended-nights table — there's nothing to show.
    trackAttendance = true,
  } = $props()

  // ---- people list -----------------------------------------------------------
  let peopleData = $state([])
  let peopleLoaded = $state(false)
  let peopleError = $state('')
  let currentPeopleFilter = $state('members') // 'members' | 'visitors' | 'archived'
  let searchText = $state('')

  const searchQuery = $derived(normalizeQuotes(searchText.toLowerCase().trim()))
  const filteredPeople = $derived(filterPeople(peopleData, currentPeopleFilter, searchQuery))

  const FILTERS = [
    { id: 'members', label: 'Members' },
    { id: 'visitors', label: 'Visitors' },
    { id: 'archived', label: 'Archived' },
  ]

  // People an admin has yet to vouch for. Until they're confirmed they can't see anyone here.
  const awaitingConfirmation = $derived(
    peopleData.filter((p) => !p.confirmed && !p.archived && p.has_user_account)
  )

  let fetchStarted = false
  $effect(() => {
    if (active && !fetchStarted) {
      fetchStarted = true
      fetchPeople()
    }
  })

  function fetchPeople() {
    fetch(`/api/sessions/${sessionPath}/people`)
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          peopleData = data.people
          peopleLoaded = true
          peopleError = ''
        } else {
          peopleError = `Failed to load people: ${data.message || 'Unknown error'}`
          peopleLoaded = true
        }
      })
      .catch((error) => {
        console.error('Error loading people:', error)
        peopleError = 'Error loading people'
        peopleLoaded = true
      })
  }

  // ---- add person (ONE PersonPicker; no global search — see the header comment) ----
  let pickerOpen = $state(false)
  let saving = $state(false)

  function openAddPerson() {
    pickerOpen = true
  }

  async function createPerson({ first_name, last_name, email, instruments }) {
    saving = true
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/people/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name,
          last_name,
          email,
          instruments,
          relationship: 'member',
        }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new Error(data.message || 'Could not add person')
      toast(`${first_name} ${last_name} added to session`, 'success')
      pickerOpen = false
      fetchPeople()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      saving = false
    }
  }

  // ---- person detail sheet -----------------------------------------------------
  let detailOpen = $state(false)
  let detailLoading = $state(false)
  let detailFailed = $state(false)
  let detailPerson = $state(null)
  let detailBusy = $state(false)

  // The roster row for the person in the sheet — carries relationship/confirmed/archived,
  // which the /people/<id> detail endpoint doesn't return.
  const detailRow = $derived(
    detailPerson ? peopleData.find((p) => p.person_id === detailPerson.person_id) : null
  )

  export function showPersonDetail(personId) {
    let basePath = window.location.pathname
    basePath = basePath.replace(/\/people\/\d+$/, '').replace(/\/(tunes|logs|people)$/, '')
    window.history.pushState({}, '', `${basePath}/people/${personId}`)

    detailLoading = true
    detailFailed = false
    detailPerson = null
    detailOpen = true

    fetch(`/api/sessions/${sessionPath}/people/${personId}`)
      .then((response) => response.json())
      .then((data) => {
        detailLoading = false
        if (data.success) detailPerson = data.person
        else detailFailed = true
      })
      .catch((error) => {
        console.error('Error loading person details:', error)
        detailLoading = false
        detailFailed = true
      })
  }

  function onDetailClosed() {
    const newPath = window.location.pathname.replace(/\/people\/\d+$/, '/people')
    window.history.pushState({}, '', newPath)
  }

  const locationStringOf = (person) => {
    const parts = []
    if (person.city) parts.push(person.city)
    if (person.state) parts.push(person.state)
    if (person.country) parts.push(person.country)
    return parts
  }

  const nameOf = (p) => `${p.first_name} ${p.last_name}`.trim()

  async function setField(personId, field, value) {
    detailBusy = true
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/people/${personId}/${field}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new Error(data.message || 'Could not save')
      // Patch the roster row in place so the list and the sheet agree without a refetch.
      peopleData = peopleData.map((p) =>
        p.person_id === personId ? { ...p, [field]: value } : p
      )
      return true
    } catch (e) {
      toast(e.message, 'error')
      return false
    } finally {
      detailBusy = false
    }
  }

  async function toggleConfirmed() {
    if (!detailRow) return
    const next = !detailRow.confirmed
    if (await setField(detailRow.person_id, 'confirmed', next)) {
      toast(
        next
          ? `${nameOf(detailRow)} can now see this session's people and attendance.`
          : `${nameOf(detailRow)} can no longer see this session's people.`,
        'success'
      )
    }
  }

  async function toggleArchived() {
    if (!detailRow) return
    const next = !detailRow.archived
    if (await setField(detailRow.person_id, 'archived', next)) {
      toast(next ? `${nameOf(detailRow)} archived.` : `${nameOf(detailRow)} restored.`, 'success')
    }
  }

  async function setRelationship(value) {
    if (!detailRow || detailRow.relationship === value) return
    await setField(detailRow.person_id, 'relationship', value)
  }

  const RELATIONSHIPS = [
    { id: 'member', label: 'Member' },
    { id: 'visitor', label: 'Visitor' },
  ]

  // ---- deep link ---------------------------------------------------------------
  $effect(() => {
    untrack(() => {
      if (initialPersonId) {
        setTimeout(() => showPersonDetail(initialPersonId), 100)
      }
    })
  })
</script>

<!-- People Tab Content -->
<div class="tab-content" class:active id="people-tab">
  <div class="people-container">
    <div class="people-controls">
      <SearchField
        bind:value={searchText}
        id="people-search-box"
        inputClass="people-search-box"
        wrapperClass="people-search-wrap"
        styled={false}
        placeholder="Search people..." />
      <button class="people-add-btn" onclick={openAddPerson}>Add</button>
      <a href="/help/session-tracking/members" class="help-icon" title="About session people">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
      </a>
    </div>

    <Seg
      options={FILTERS}
      value={currentPeopleFilter}
      onSelect={(id) => (currentPeopleFilter = id)}
      idAttr="data-people-filter"
      aria-label="Filter people" />

    {#if isSessionAdmin && awaitingConfirmation.length > 0}
      <!-- Confirming is the ONLY way people-visibility is granted, so an admin needs to know
           someone is waiting on it. -->
      <p class="people-nudge">
        {awaitingConfirmation.length}
        {awaitingConfirmation.length === 1 ? 'person has' : 'people have'} joined and can't see
        who plays here yet. Open them to confirm.
      </p>
    {/if}

    <div class="people-list" id="people-list">
      {#if !peopleLoaded}
        <div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);">
          <i class="loading-dots">Loading people...</i>
        </div>
      {:else if peopleError}
        <div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);">
          <p>{peopleError}</p>
        </div>
      {:else if filteredPeople.length === 0}
        <div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);">
          <p>
            {#if searchQuery}
              No people found matching your search
            {:else if currentPeopleFilter === 'visitors'}
              No visitors to this session yet
            {:else if currentPeopleFilter === 'archived'}
              Nobody archived
            {:else}
              No people in this session yet
            {/if}
          </p>
          {#if searchQuery}
            <button class="people-empty-add" onclick={openAddPerson}>
              Add Someone To This Session
            </button>
          {/if}
        </div>
      {:else}
        {#each filteredPeople as person (person.person_id)}
          <div class="person-row" class:archived={person.archived} onclick={() => showPersonDetail(person.person_id)}>
            <div class="person-icon {person.has_user_account ? 'has-account' : 'no-account'}">
              <i class="fa fa-user-circle"></i>
            </div>
            <div class="person-info">
              <!-- Badges are SIBLINGS of .person-name, not children: the name element's text
                   content should be the name, nothing else. -->
              <div class="person-name">{person.first_name} {person.last_name}</div>
              {#if person.relationship === 'visitor' || person.archived || (!person.confirmed && person.has_user_account)}
                <div class="person-badges">
                  {#if person.relationship === 'visitor'}
                    <Chip label="Visitor" variant="warning" />
                  {/if}
                  {#if person.archived}
                    <Chip label="Archived" />
                  {/if}
                  {#if !person.confirmed && person.has_user_account}
                    <Chip label="Unconfirmed" variant="warning" title="Can't see this session's people yet" />
                  {/if}
                </div>
              {/if}
              <div class="person-instruments">
                {person.instruments && person.instruments.length > 0 ? person.instruments.join(', ') : 'No instruments listed'}
              </div>
            </div>
            {#if trackAttendance}
              <div class="person-meta">
                <Chip label={String(person.attendance_count || 0)} styled={false} chipClass="person-attendance-badge" title="Nights attended" />
              </div>
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Person Detail Sheet -->
  <Sheet bind:open={detailOpen} title={detailPerson ? nameOf(detailPerson) : ''} onCancel={onDetailClosed}>
    <div id="person-detail-content">
      {#if detailLoading}
        <div style="padding: 40px 20px; text-align: center;">
          <i class="loading-dots">Loading...</i>
        </div>
      {:else if detailFailed || !detailPerson}
        <div style="padding: 40px 20px; text-align: center; color: var(--text-muted);">
          <p>Failed to load person details</p>
        </div>
      {:else}
        {#if detailPerson.person_id === currentUserId}
          <div style="margin-bottom: 16px;"><a href="/me" class="person-detail-link">View my profile</a></div>
        {/if}
        {#if detailPerson.has_user_account && detailPerson.person_id !== currentUserId}
          <div style="margin-bottom: 16px;"><a href="/me/and/{detailPerson.person_id}" class="person-detail-link">Common Tunes?</a></div>
        {/if}

        {#if detailRow && (isSessionAdmin || detailPerson.person_id === currentUserId)}
          <div class="person-detail-section">
            <h3>Relationship to this session</h3>
            <Seg
              options={RELATIONSHIPS}
              value={detailRow.relationship}
              onSelect={setRelationship}
              idAttr="data-relationship" />
            <p class="pd-hint">
              {#if detailRow.relationship === 'visitor'}
                Came here, but this isn't one of their sessions.
              {:else}
                This is one of their sessions — its tunes count towards their stats.
              {/if}
            </p>
          </div>
        {/if}

        {#if detailRow && isSessionAdmin}
          <div class="person-detail-section">
            <h3>Session admin</h3>
            <!-- The copy has to say what confirming DOES, at the point of click. A bare
                 "Confirmed" toggle would be an admin handing over the roster without
                 realising it. -->
            <button class="pd-action" disabled={detailBusy} onclick={toggleConfirmed}>
              {#if detailRow.confirmed}
                Un-confirm {nameOf(detailPerson)} — they'll no longer see this session's
                people list and attendance records
              {:else}
                Confirm {nameOf(detailPerson)} — they'll be able to see this session's people
                list and attendance records
              {/if}
            </button>
            <button class="pd-action" disabled={detailBusy} onclick={toggleArchived}>
              {#if detailRow.archived}
                Restore {nameOf(detailPerson)} to the roster
              {:else}
                Archive {nameOf(detailPerson)} — hide them from lists (still findable by name)
              {/if}
            </button>
          </div>
        {/if}

        <div class="person-detail-location">
          {locationStringOf(detailPerson).length > 0 ? locationStringOf(detailPerson).join(', ') : 'No location specified'}
        </div>
        <div class="person-detail-section">
          <h3>TheSession.org</h3>
          {#if detailPerson.thesession_user_id}
            <a href="https://thesession.org/members/{detailPerson.thesession_user_id}" target="_blank" class="person-detail-link">View on TheSession.org</a>
          {:else}
            <span style="color: var(--text-muted);">Not linked</span>
          {/if}
        </div>
        <div class="person-detail-section">
          <h3>Instruments</h3>
          {#if detailPerson.instruments && detailPerson.instruments.length > 0}
            <div class="person-instruments-list">
              {#each detailPerson.instruments as inst (inst)}
                <Chip label={inst} styled={false} chipClass="person-instrument-badge" />
              {/each}
            </div>
          {:else}
            <span style="color: var(--text-muted);">No instruments listed</span>
          {/if}
        </div>
        {#if trackAttendance}
        <div class="person-detail-section">
          <h3>Sessions Attended</h3>
          {#if detailPerson.attended_instances && detailPerson.attended_instances.length > 0}
            <table class="attendance-table">
              <thead>
                <tr><th>Date</th></tr>
              </thead>
              <tbody>
                {#each detailPerson.attended_instances as instance (instance.date)}
                  <tr>
                    <td>
                      <a href="/sessions/{sessionPath}/{instance.date}" class="person-detail-link">{instance.date}</a>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <p style="color: var(--text-muted); margin-top: 12px;">No sessions attended yet</p>
          {/if}
        </div>
        {/if}
      {/if}
    </div>
  </Sheet>

  <!--
    ONE add flow. Filtering is over this session's roster only; anyone else is typed in fresh
    and deduped on email server-side. (Before 034 this was two stacked sheets, the first of
    which searched every person in the database.)
  -->
  <PersonPicker
    bind:open={pickerOpen}
    scope="session"
    mode="attendance"
    title="Add someone to this session"
    people={peopleData}
    {canonicalInstruments}
    busy={saving}
    onSelect={(p) => showPersonDetail(p.person_id)}
    onCreate={createPerson}
    onClose={() => (pickerOpen = false)} />
</div>

<style>
  .people-nudge {
    margin: 8px 0;
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--warning-bg);
    color: var(--text-color);
    font-size: 0.86rem;
  }
  .person-row.archived { opacity: 0.55; }
  .person-badges { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 2px; }
  .pd-hint { font-size: 0.82rem; color: var(--text-muted, #6c757d); margin: 8px 0 0; }
  .pd-action {
    display: block;
    width: 100%;
    text-align: left;
    margin-top: 8px;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--hover-bg);
    color: inherit;
    font: inherit;
    font-size: 0.86rem;
    cursor: pointer;
  }
  .pd-action:hover { border-color: var(--primary); }
  .pd-action:disabled { opacity: 0.5; cursor: default; }
  .people-empty-add {
    margin-top: 16px;
    padding: 10px 20px;
    background-color: var(--primary);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  }
</style>
