<script>
  // The People tab (session members only): lazy-loaded list with regulars/all
  // filter + search, the add-person flow (search existing people → add, or create
  // a new person), and the person-detail modal with its /people/<id> deep link.
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { toast, SearchField } from '../lib/index.js'
  import { normalizeQuotes } from '../shared/parse.js'
  import { parseTheSessionId, filterPeople } from './logic.js'

  let {
    active,
    sessionPath,
    sessionType,
    canonicalInstruments = [],
    currentUserId = null,
    initialPersonId = null,
  } = $props()

  // ---- people list -----------------------------------------------------------
  let peopleData = $state([])
  let peopleLoaded = $state(false)
  let peopleError = $state('')
  let currentPeopleFilter = $state('all') // 'all' | 'regulars'
  let searchText = $state('')

  const searchQuery = $derived(normalizeQuotes(searchText.toLowerCase().trim()))
  const filteredPeople = $derived(filterPeople(peopleData, currentPeopleFilter, searchQuery))

  // Fetch when the tab first becomes active (or immediately when it's the
  // landing tab) — legacy initializePeopleTab semantics.
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

  function togglePeopleFilter() {
    currentPeopleFilter = currentPeopleFilter === 'regulars' ? 'all' : 'regulars'
  }

  // ---- modal show/hide plumbing (display + .show class, legacy timings) --------
  let detailVisible = $state(false)
  let detailShow = $state(false)
  let searchVisible = $state(false)
  let searchShow = $state(false)
  let createVisible = $state(false)
  let createShow = $state(false)

  function openSearchModalState() {
    searchVisible = true
    setTimeout(() => (searchShow = true), 10)
  }
  function closeSearchPersonModal() {
    searchShow = false
    setTimeout(() => (searchVisible = false), 300)
  }
  function closeAddPersonModal() {
    createShow = false
    setTimeout(() => (createVisible = false), 300)
  }

  // ---- person detail modal -----------------------------------------------------
  let personModalShowTime = 0
  let detailLoading = $state(false)
  let detailFailed = $state(false)
  let detailPerson = $state(null)

  export function showPersonDetail(personId) {
    // Deep-linkable URL: .../people/<id>
    let basePath = window.location.pathname
    basePath = basePath.replace(/\/people\/\d+$/, '').replace(/\/(tunes|logs|people)$/, '')
    window.history.pushState({}, '', `${basePath}/people/${personId}`)

    detailLoading = true
    detailFailed = false
    detailPerson = null
    detailVisible = true
    setTimeout(() => (detailShow = true), 10)
    personModalShowTime = Date.now()

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

  function closePersonDetailModal() {
    const newPath = window.location.pathname.replace(/\/people\/\d+$/, '/people')
    window.history.pushState({}, '', newPath)
    detailShow = false
    setTimeout(() => (detailVisible = false), 300)
  }

  const locationStringOf = (person) => {
    const parts = []
    if (person.city) parts.push(person.city)
    if (person.state) parts.push(person.state)
    if (person.country) parts.push(person.country)
    return parts
  }

  // ---- add person: search step ---------------------------------------------------
  let personSearchText = $state('')
  let searchResults = $state(null) // null until a search ran
  let searchMessage = $state('Type to search for existing people')
  let addingPersonId = $state(null)

  function openAddPersonModal() {
    personSearchText = ''
    searchResults = null
    searchMessage = 'Type to search for existing people'
    openSearchModalState()
  }


  function performPersonSearch() {
    const query = personSearchText.trim()
    if (query.length === 0) {
      searchResults = null
      searchMessage = 'Type to search for existing people'
      return
    }
    if (query.length < 2) {
      searchResults = null
      searchMessage = 'Type at least 2 characters to search'
      return
    }
    searchResults = null
    searchMessage = 'Searching...'
    fetch(`/api/sessions/${sessionPath}/people/search?q=${encodeURIComponent(query)}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          searchResults = data.people
          if (data.people.length === 0) searchMessage = 'No matching people found'
        } else {
          searchMessage = `Error: ${data.message}`
        }
      })
      .catch((error) => {
        console.error('Search error:', error)
        searchMessage = 'Error searching people'
      })
  }

  function addExistingPersonToSession(personId) {
    addingPersonId = personId
    const isRegular = sessionType === 'festival'
    fetch(`/api/sessions/${sessionPath}/people/add-existing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person_id: personId, is_regular: isRegular }),
    })
      .then((response) => response.json())
      .then((result) => {
        addingPersonId = null
        if (result.success) {
          closeSearchPersonModal()
          peopleData = []
          fetchPeople()
        } else {
          toast('Failed to add person: ' + (result.message || 'Unknown error'), 'error')
        }
      })
      .catch((error) => {
        console.error('Error adding person:', error)
        addingPersonId = null
        toast('Error adding person', 'error')
      })
  }

  // ---- add person: create step ---------------------------------------------------
  let newFirstName = $state('')
  let newLastName = $state('')
  let newEmail = $state('')
  let newTheSession = $state('')
  let newOtherInstrument = $state('')
  let newIsRegular = $state(false)
  const newInstruments = new SvelteSet()
  let savingPerson = $state(false)

  function openCreatePersonModal() {
    closeSearchPersonModal()
    setTimeout(() => {
      newFirstName = ''
      newLastName = ''
      newEmail = ''
      newTheSession = ''
      newOtherInstrument = ''
      newIsRegular = false
      newInstruments.clear()
      createVisible = true
      setTimeout(() => (createShow = true), 10)
    }, 350)
  }

  function saveNewPerson() {
    const firstName = newFirstName.trim()
    const lastName = newLastName.trim()
    if (!firstName || !lastName) {
      toast('First name and last name are required', 'error')
      return
    }

    const instruments = [...newInstruments]
    // Any "Other" free-text instrument(s), comma-separated; server re-canonicalizes.
    if (newOtherInstrument.trim()) {
      newOtherInstrument.split(',').forEach((inst) => {
        const trimmed = inst.trim()
        if (trimmed) instruments.push(trimmed)
      })
    }

    const isRegular = sessionType === 'festival' ? true : newIsRegular

    savingPerson = true
    fetch(`/api/sessions/${sessionPath}/people/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        email: newEmail.trim() || null,
        instruments: instruments,
        thesession_user_id: parseTheSessionId(newTheSession),
        is_regular: isRegular,
      }),
    })
      .then((response) => response.json())
      .then((result) => {
        if (result.success) {
          closeAddPersonModal()
          peopleData = []
          fetchPeople()
        } else {
          toast('Failed to add person: ' + (result.message || 'Unknown error'), 'error')
        }
      })
      .catch((error) => {
        console.error('Error adding person:', error)
        toast('Error adding person', 'error')
      })
      .finally(() => {
        savingPerson = false
      })
  }

  // ---- deep link + escape/backdrop handling ---------------------------------------
  $effect(() => {
    untrack(() => {
      if (initialPersonId) {
        setTimeout(() => showPersonDetail(initialPersonId), 100)
      }
    })
  })

  function onKeydown(event) {
    if (event.key !== 'Escape') return
    if (createVisible) {
      closeAddPersonModal()
      return
    }
    if (searchVisible) {
      closeSearchPersonModal()
      return
    }
    if (detailVisible) {
      closePersonDetailModal()
    }
  }

  function detailBackdropClick(event) {
    // Grace period so the opening tap can't immediately close the modal.
    if (Date.now() - personModalShowTime < 500) return
    if (event.target === event.currentTarget) closePersonDetailModal()
  }
</script>

<svelte:window onkeydown={onKeydown} />

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
      {#if sessionType !== 'festival'}
        <button id="people-filter-btn" class="people-filter-btn" onclick={togglePeopleFilter}>
          {currentPeopleFilter === 'regulars' ? 'Regulars' : 'All'}
        </button>
      {/if}
      <button class="people-add-btn" onclick={openAddPersonModal}>Add</button>
    </div>
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
            {searchQuery
              ? 'No people found matching your search'
              : currentPeopleFilter === 'regulars'
                ? 'No regulars in this session yet'
                : 'No people in this session yet'}
          </p>
          {#if searchQuery}
            <button
              onclick={openAddPersonModal}
              style="margin-top: 16px; padding: 10px 20px; background-color: var(--primary); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">
              Add Someone To This Session
            </button>
          {/if}
        </div>
      {:else}
        {#each filteredPeople as person (person.person_id)}
          <div class="person-row" onclick={() => showPersonDetail(person.person_id)}>
            <div class="person-icon {person.has_user_account ? 'has-account' : 'no-account'}">
              <i class="fa fa-user-circle"></i>
            </div>
            <div class="person-info">
              <div class="person-name">{person.first_name} {person.last_name}</div>
              <div class="person-instruments">
                {person.instruments && person.instruments.length > 0 ? person.instruments.join(', ') : 'No instruments listed'}
              </div>
            </div>
            <div class="person-meta">
              <span class="person-attendance-badge">{person.attendance_count || 0}</span>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Person Detail Modal -->
  {#if detailVisible}
    <div id="person-detail-modal" class="modal-overlay" class:show={detailShow} style="display: flex;" onclick={detailBackdropClick}>
      <div class="modal-dialog">
        <div id="person-detail-content">
          <button class="modal-close-btn" onclick={closePersonDetailModal} title="Close">&times;</button>
          {#if detailLoading}
            <div style="padding: 40px 20px; text-align: center;">
              <i class="loading-dots">Loading...</i>
            </div>
          {:else if detailFailed || !detailPerson}
            <div style="padding: 40px 20px; text-align: center; color: var(--text-muted);">
              <p>Failed to load person details</p>
            </div>
          {:else}
            <h2 class="person-detail-title">{detailPerson.first_name} {detailPerson.last_name}</h2>
            {#if detailPerson.person_id === currentUserId}
              <div style="margin-bottom: 16px;"><a href="/me" class="person-detail-link">View my profile</a></div>
            {/if}
            {#if detailPerson.has_user_account && detailPerson.person_id !== currentUserId}
              <div style="margin-bottom: 16px;"><a href="/me/and/{detailPerson.person_id}" class="person-detail-link">Common Tunes?</a></div>
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
                    <span class="person-instrument-badge">{inst}</span>
                  {/each}
                </div>
              {:else}
                <span style="color: var(--text-muted);">No instruments listed</span>
              {/if}
            </div>
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
        </div>
      </div>
    </div>
  {/if}

  <!-- Search Person Modal -->
  {#if searchVisible}
    <div
      id="search-person-modal"
      class="modal-overlay"
      class:show={searchShow}
      style="display: flex;"
      onclick={(e) => {
        if (e.target === e.currentTarget) closeSearchPersonModal()
      }}>
      <div class="modal-dialog">
        <div style="padding: 20px;">
          <button class="modal-close-btn" onclick={closeSearchPersonModal} title="Close">&times;</button>
          <h2 style="margin: 0 32px 20px 0; color: var(--text-color); font-size: 20px; font-weight: 600;">Add Person to Session</h2>
          <p style="margin: 0 0 16px 0; color: var(--secondary-text); font-size: 14px;">Search people who are members of other sessions, or add someone new.</p>

<SearchField
            bind:value={personSearchText}
            id="search-person-input"
            inputClass="search-person-input"
            styled={false}
            placeholder="Search by name..."
            autocomplete="off"
            debounce={1000}
            onSearch={performPersonSearch} />

          <div class="search-results-container" id="search-results-container">
            {#if searchResults && searchResults.length > 0}
              {#each searchResults as person (person.person_id)}
                <div class="search-result-row" data-person-id={person.person_id} onclick={() => addExistingPersonToSession(person.person_id)}>
                  <div class="search-result-content">
                    <div class="search-result-name">{person.first_name} {person.last_name}</div>
                    {#if [person.city, person.state, person.country].filter(Boolean).length > 0}
                      <div class="search-result-details">{[person.city, person.state, person.country].filter(Boolean).join(', ')}</div>
                    {/if}
                    {#if person.instruments && person.instruments.length > 0}
                      <div class="search-result-instruments">{person.instruments.join(', ')}</div>
                    {/if}
                  </div>
                  {#if addingPersonId === person.person_id}
                    <div class="search-result-spinner"></div>
                  {/if}
                </div>
              {/each}
            {:else}
              <div class="search-no-results">{searchMessage}</div>
            {/if}
          </div>

          <div class="search-person-actions">
            <button class="add-person-btn-cancel" onclick={closeSearchPersonModal}>Cancel</button>
            <button class="add-person-btn-save" onclick={openCreatePersonModal}>Add New Person</button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Add Person Modal -->
  {#if createVisible}
    <div
      id="add-person-modal"
      class="modal-overlay"
      class:show={createShow}
      style="display: flex;"
      onclick={(e) => {
        if (e.target === e.currentTarget) closeAddPersonModal()
      }}>
      <div class="modal-dialog">
        <div style="padding: 20px;">
          <button class="modal-close-btn" onclick={closeAddPersonModal} title="Close">&times;</button>
          <h2 style="margin: 0 32px 20px 0; color: var(--text-color); font-size: 20px; font-weight: 600;">Add Person to Session</h2>

          <div class="add-person-form-group">
            <label for="add-person-first-name">First Name *</label>
            <input type="text" id="add-person-first-name" required bind:value={newFirstName} />
          </div>

          <div class="add-person-form-group">
            <label for="add-person-last-name">Last Name *</label>
            <input type="text" id="add-person-last-name" required bind:value={newLastName} />
          </div>

          <div class="add-person-form-group">
            <label for="add-person-email">Email (optional)</label>
            <input type="email" id="add-person-email" bind:value={newEmail} />
          </div>

          <div class="add-person-form-group">
            <label>Instruments</label>
            <div class="instruments-checkboxes" id="add-person-instruments">
              {#each canonicalInstruments as instrument, i (instrument)}
                <div class="instrument-checkbox-item">
                  <input
                    type="checkbox"
                    id="add-person-inst-{i + 1}"
                    value={instrument}
                    checked={newInstruments.has(instrument)}
                    onchange={(e) => {
                      if (e.target.checked) newInstruments.add(instrument)
                      else newInstruments.delete(instrument)
                    }} />
                  <label for="add-person-inst-{i + 1}">{instrument}</label>
                </div>
              {/each}
            </div>
            <input type="text" id="add-person-other-instrument" placeholder="Other instrument(s)..." style="margin-top: 8px;" bind:value={newOtherInstrument} />
          </div>

          <div class="add-person-form-group">
            <label for="add-person-thesession">TheSession.org ID or URL (optional)</label>
            <input type="text" id="add-person-thesession" placeholder="e.g. 12345 or thesession.org URL" bind:value={newTheSession} />
          </div>

          {#if sessionType !== 'festival'}
            <div class="add-person-form-group">
              <div class="instrument-checkbox-item">
                <input type="checkbox" id="add-person-is-regular" bind:checked={newIsRegular} />
                <label for="add-person-is-regular">Regular?</label>
              </div>
            </div>
          {/if}

          <div class="add-person-actions">
            <button class="add-person-btn-cancel" onclick={closeAddPersonModal}>Cancel</button>
            <button class="add-person-btn-save" disabled={savingPerson} onclick={saveNewPerson}>
              {savingPerson ? 'Adding...' : 'Add Person'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
