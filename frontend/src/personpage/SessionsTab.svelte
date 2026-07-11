<script>
  // Sessions tab: the person's session memberships (filterable), leave-session
  // (user profile) / admin-toggle (system admin) affordances, and the
  // add-to-session modal (search + role pick + add). The modal was driven by
  // ModalManager in the legacy page; it's plain Svelte state now (same markup,
  // same .modal CSS, body.modal-open kept for scroll-lock parity).
  let { initialSessions, person, personId, isUserProfile, isSystemAdmin } = $props()

  const toast = (msg, type) => window.showMessage && window.showMessage(msg, type)

  let sessions = $state([...initialSessions])
  let sessionFilter = $state('all')

  // Legacy filterSessions matched the card's small text ("<location> · <role>")
  // against 'Regular', so an Admin row hides under the Regular filter.
  const isVisible = (s) => sessionFilter === 'all' || `${s.location} · ${s.role}`.includes('Regular')

  function leaveSession(s) {
    if (
      !confirm(
        `Are you sure you want to leave "${s.session_name}"?\n\nThis will remove you from the session's member list. Your attendance history will be preserved.`
      )
    ) {
      return
    }

    fetch(`/api/sessions/${s.session_path}/leave`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          sessions = sessions.filter((x) => x.session_path !== s.session_path)
          toast(data.message, 'success')
        } else {
          toast('Error: ' + data.message, 'error')
        }
      })
      .catch((error) => {
        toast('Error leaving session: ' + error.message, 'error')
      })
  }

  function toggleAdmin(s, e) {
    const isAdmin = e.currentTarget.checked
    const el = e.currentTarget
    fetch(`/api/admin/sessions/${s.session_path}/people/${personId}/admin`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_admin: isAdmin }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          // Update the role badge
          s.role = isAdmin ? 'Admin' : s.is_regular ? 'Regular' : 'Attendee'
          s.is_admin = isAdmin
          sessions = [...sessions]
        } else {
          el.checked = !isAdmin
          toast('Error: ' + (data.error || data.message), 'error')
        }
      })
      .catch((error) => {
        el.checked = !isAdmin
        toast('Error updating admin status: ' + error.message, 'error')
      })
  }

  // --- Add to Session Modal ---------------------------------------------------
  let modalOpen = $state(false)
  let searchValue = $state('')
  let modalLoading = $state(false)
  let modalError = $state(null)
  let modalSessions = $state(null) // null until first load
  let noSessionsVisible = $state(false)
  let selectedRole = $state('regular')
  let searchTimeout

  function openSessionModal() {
    searchValue = ''
    loadInitialSessions()
    modalOpen = true
    document.body.classList.add('modal-open')
  }

  function closeSessionModal() {
    modalOpen = false
    document.body.classList.remove('modal-open')
  }

  function onModalKeydown(e) {
    if (e.key === 'Escape' && modalOpen) closeSessionModal()
  }

  function showLoading(show) {
    modalLoading = show
    if (show) {
      modalSessions = null
      modalError = null
      noSessionsVisible = false
    }
  }

  function displaySessions(list) {
    modalError = null
    modalSessions = list
    noSessionsVisible = list.length === 0
  }

  function loadInitialSessions() {
    showLoading(true)
    fetch(`/api/person/${personId}/available-sessions`)
      .then((response) => response.json())
      .then((data) => {
        showLoading(false)
        if (data.success) {
          displaySessions(data.sessions)
        } else {
          modalError = 'Failed to load sessions: ' + data.message
        }
      })
      .catch((error) => {
        showLoading(false)
        modalError = 'Error loading sessions: ' + error.message
      })
  }

  function searchSessions(searchTerm) {
    showLoading(true)
    fetch(`/api/person/${personId}/search-sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ search_term: searchTerm }),
    })
      .then((response) => response.json())
      .then((data) => {
        showLoading(false)
        if (data.success) {
          displaySessions(data.sessions)
        } else {
          modalError = 'Failed to search sessions: ' + data.message
        }
      })
      .catch((error) => {
        showLoading(false)
        modalError = 'Error searching sessions: ' + error.message
      })
  }

  function onSearchInput() {
    clearTimeout(searchTimeout)
    const term = searchValue.trim()
    searchTimeout = setTimeout(() => {
      searchSessions(term)
    }, 300)
  }

  const locationInfo = (session) =>
    session.location_name && session.location_name !== session.location_display
      ? `${session.location_name} - ${session.location_display}`
      : session.location_display

  function addPersonToSession(sessionId, sessionName) {
    if (!confirm(`Add ${person.name} to "${sessionName}" as a ${selectedRole}?`)) {
      return
    }

    fetch('/api/add-person-to-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        person_id: personId,
        session_id: parseInt(sessionId),
        role: selectedRole,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          closeSessionModal()
          // Store success message for display after reload
          sessionStorage.setItem('personSavedMessage', data.message)
          // Reload the page to show updated sessions list
          window.location.reload()
        } else {
          toast('Error: ' + data.message, 'error')
        }
      })
      .catch((error) => {
        toast('Error adding person to session: ' + error.message, 'error')
      })
  }
</script>

<svelte:window onkeydown={onModalKeydown} />

<div class="mt-3">
  {#if sessions.length}
    <div class="mb-3">
      <select id="session-filter" class="form-select" bind:value={sessionFilter}>
        <option value="all">All Sessions</option>
        <option value="regular">Regular Sessions Only</option>
      </select>
    </div>
    <div class="sessions-card-list">
      {#each sessions as session, i (session.session_path)}
        <div
          class="session-card card mb-2"
          data-session-path={session.session_path}
          data-is-regular={String(session.is_regular).toLowerCase()}
          style:display={isVisible(session) ? '' : 'none'}>
          <div class="card-body d-flex justify-content-between align-items-center py-2 px-3">
            <div class="session-info">
              <a href="/sessions/{session.session_path}" class="session-title h6 mb-0 d-block text-decoration-none">{session.session_name}</a>
              <small class="text-muted">{session.location}{#if session.role} &middot; <span class="session-role-badge" data-session-path={session.session_path}>{session.role}</span>{/if}</small>
            </div>
            {#if isUserProfile}
              <button
                type="button"
                class="btn btn-link text-danger p-0 leave-session-btn"
                data-session-path={session.session_path}
                data-session-name={session.session_name}
                title="Leave this session"
                onclick={(e) => {
                  e.preventDefault()
                  leaveSession(session)
                }}>
                <span class="leave-x">&times;</span>
              </button>
            {:else if isSystemAdmin}
              <div class="custom-control custom-switch">
                <input
                  type="checkbox"
                  class="custom-control-input admin-toggle"
                  id="admin-toggle-{i + 1}"
                  data-session-path={session.session_path}
                  checked={session.is_admin}
                  onchange={(e) => toggleAdmin(session, e)} />
                <label class="custom-control-label" for="admin-toggle-{i + 1}">Admin</label>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
    {#if isUserProfile}
      <div class="mt-3">
        <a
          href="#add"
          id="add-to-session-link"
          class="btn btn-outline-primary btn-sm"
          onclick={(e) => {
            e.preventDefault()
            openSessionModal()
          }}>Add another session I've been to</a>
      </div>
    {:else}
      <div class="mt-3">
        <a
          href="#add"
          id="add-to-session-link"
          class="btn btn-outline-primary btn-sm"
          onclick={(e) => {
            e.preventDefault()
            openSessionModal()
          }}>Add this person to a session</a>
      </div>
    {/if}
  {:else if isUserProfile}
    <div class="alert alert-info" role="alert">
      <a
        href="#add"
        id="add-to-session-link"
        class="btn btn-outline-primary btn-sm"
        onclick={(e) => {
          e.preventDefault()
          openSessionModal()
        }}>add your first session</a>
    </div>
  {:else}
    <div class="alert alert-info" role="alert">
      No sessions associated with this person.
    </div>
    <div class="mt-3">
      <a
        href="#add"
        id="add-to-session-link"
        class="btn btn-outline-primary btn-sm"
        onclick={(e) => {
          e.preventDefault()
          openSessionModal()
        }}>Add this person to a session</a>
    </div>
  {/if}
</div>

<!-- Add to Session Modal -->
<!-- "show" matters for parity: legacy ModalManager.showModal always added it. -->
<div
  id="addToSessionModal"
  class="modal{modalOpen ? ' show' : ''}"
  style:display={modalOpen ? 'flex' : 'none'}
  role="presentation"
  onclick={(e) => {
    if (e.target === e.currentTarget) closeSessionModal()
  }}>
  <div class="modal-content">
    <div class="modal-header">
      <h3>{isUserProfile ? 'Add me to a Session' : `Add ${person.name} to a Session`}</h3>
      <span
        class="modal-close"
        role="button"
        tabindex="0"
        onclick={closeSessionModal}
        onkeydown={(e) => {
          if (e.key === 'Enter') closeSessionModal()
        }}>&times;</span>
    </div>
    <div class="modal-body">
      <div class="search-section">
        <div class="mb-3">
          <label for="session-search" class="form-label">Search Sessions:</label>
          <input
            type="text"
            id="session-search"
            class="form-control"
            placeholder="Type to search sessions..."
            bind:value={searchValue}
            oninput={onSearchInput} />
        </div>
      </div>
      <div class="role-section mb-3">
        <span class="form-label">{isUserProfile ? 'Add me as:' : 'Add as:'}</span>
        <div class="form-check">
          <input class="form-check-input" type="radio" name="user-role" id="role-regular" value="regular" bind:group={selectedRole} />
          <label class="form-check-label" for="role-regular">Regular</label>
        </div>
        <div class="form-check">
          <input class="form-check-input" type="radio" name="user-role" id="role-attendee" value="attendee" bind:group={selectedRole} />
          <label class="form-check-label" for="role-attendee">Attendee</label>
        </div>
      </div>
      <div id="sessions-loading" class="text-center" style:display={modalLoading ? 'block' : 'none'}>
        <span class="loading-spinner"></span>
        <span style="margin-left: 8px;">Loading sessions...</span>
      </div>
      <div id="sessions-results">
        {#if modalError}
          <div class="alert alert-danger">{modalError}</div>
        {:else if modalSessions}
          {#if modalSessions.length === 0}
            <p class="text-muted">No sessions found.</p>
          {:else}
            <div class="sessions-list">
              {#each modalSessions as session (session.session_id)}
                <div class="session-item">
                  <div class="session-info">
                    <div class="session-name">{session.name}</div>
                    <div class="session-location">{locationInfo(session)}</div>
                  </div>
                  <button
                    class="btn btn-sm btn-primary add-session-btn"
                    data-session-id={session.session_id}
                    data-session-name={session.name}
                    onclick={() => addPersonToSession(session.session_id, session.name)}>
                    Add
                  </button>
                </div>
              {/each}
            </div>
            {#if modalSessions.length === 10}
              <p class="text-muted mt-2"><small>Showing top 10 results. Use search to narrow down.</small></p>
            {/if}
            <p class="mt-3">Don't see the session here? <a href="/add-session" target="_blank">Add it!</a></p>
          {/if}
        {/if}
      </div>
      <div id="no-sessions-message" style:display={noSessionsVisible ? 'block' : 'none'}>
        <p>Don't see the session here? <a href="/add-session" target="_blank">Add it!</a></p>
      </div>
    </div>
  </div>
</div>
