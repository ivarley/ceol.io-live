<script>
  /**
   * Sessions tab (spec 034, Change 3): the person's sessions, filterable by relationship;
   * leave-session (own profile) / admin-toggle (system admin); and the add-to-session sheet.
   *
   * Filter chips replaced the All/Regular <select>. `relationship` and `is_admin` are
   * ORTHOGONAL axes -- you can be an admin of a session you only visit -- so they filter
   * independently. The old select got this wrong: it matched the rendered role STRING against
   * "Regular", so an Admin row (whose badge said "Admin") vanished under the Regular filter
   * even when the person was a regular.
   */
  let { initialSessions, person, personId, isUserProfile, isSystemAdmin } = $props()

  import { Dialog, Sheet, SearchField, Seg, toast, Chip } from '../lib/index.js'

  let sessions = $state([...initialSessions])
  let sessionFilter = $state(null) // null = unfiltered; click the active chip to clear

  const FILTERS = [
    { id: 'member', label: 'Member' },
    { id: 'visitor', label: 'Visitor' },
    { id: 'admin', label: 'Admin' },
  ]

  // Chips are single-select and toggle OFF -- clicking the active one goes back to everything.
  function pickFilter(id) {
    sessionFilter = sessionFilter === id ? null : id
  }

  const isVisible = (s) => {
    if (!sessionFilter) return true
    if (sessionFilter === 'admin') return !!s.is_admin
    return s.relationship === sessionFilter
  }

  // Leaving is a decision -> kit Dialog with an explicit verb (spec 035).
  let leaveOpen = $state(false)
  let leaveTarget = $state(null)

  function askLeaveSession(s) {
    leaveTarget = s
    leaveOpen = true
  }

  function leaveSession(s) {
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
          // Re-derive the badge. Admin outranks the relationship in the LABEL, but the
          // relationship underneath is untouched -- separate axes.
          s.role = isAdmin ? 'Admin' : s.relationship === 'visitor' ? 'Visitor' : 'Member'
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
  let selectedRelationship = $state('member')

  const RELATIONSHIPS = [
    { id: 'member', label: isUserProfile ? 'I attend it' : 'Member' },
    { id: 'visitor', label: isUserProfile ? "I've visited" : 'Visitor' },
  ]

  // Search-FIRST (spec 034): no prefetched list. Twenty location-ranked sessions shown before
  // you typed anything was a filter pretending to be a search -- it buried the one you wanted.
  function openSessionModal() {
    searchValue = ''
    modalSessions = null
    modalError = null
    noSessionsVisible = false
    modalOpen = true
  }

  function closeSessionModal() {
    modalOpen = false
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

  // SearchField owns the debounce; an empty box goes back to the blank slate.
  function onSearch(term) {
    const q = (term || '').trim()
    if (!q) {
      modalSessions = null
      modalError = null
      noSessionsVisible = false
      return
    }
    searchSessions(q)
  }

  const locationInfo = (session) =>
    session.location_name && session.location_name !== session.location_display
      ? `${session.location_name} - ${session.location_display}`
      : session.location_display

  // Adding to a session is a decision -> kit Dialog (spec 035).
  let addConfirmOpen = $state(false)
  let addTarget = $state(null) // { sessionId, sessionName }

  function askAddPersonToSession(sessionId, sessionName) {
    addTarget = { sessionId, sessionName }
    addConfirmOpen = true
  }

  function addPersonToSession(sessionId) {
    fetch('/api/add-person-to-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        person_id: personId,
        session_id: parseInt(sessionId),
        relationship: selectedRelationship,
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

<div class="mt-3">
  {#if sessions.length}
    <div class="sessions-toolbar mb-3">
      <div class="sessions-filters" role="group" aria-label="Filter sessions">
        {#each FILTERS as f (f.id)}
          <Chip
            label={f.label}
            active={sessionFilter === f.id}
            variant={sessionFilter === f.id ? 'primary' : 'default'}
            onclick={() => pickFilter(f.id)}
            data-session-filter={f.id} />
        {/each}
      </div>
      <button
        type="button"
        class="sessions-add-btn"
        id="add-to-session-link"
        title={isUserProfile ? 'Add a session' : `Add ${person.name} to a session`}
        aria-label={isUserProfile ? 'Add a session' : `Add ${person.name} to a session`}
        onclick={openSessionModal}>+</button>
    </div>
    <div class="sessions-card-list">
      {#each sessions as session, i (session.session_path)}
        <div
          class="session-card card mb-2"
          data-session-path={session.session_path}
          data-relationship={session.relationship}
          style:display={isVisible(session) ? '' : 'none'}>
          <div class="card-body d-flex justify-content-between align-items-center py-2 px-3">
            <div class="session-info">
              <a href="/sessions/{session.session_path}" class="session-title h6 mb-0 d-block text-decoration-none">{session.session_name}</a>
              <small class="text-muted">{session.location}{#if session.role} &middot; <Chip label={session.role} styled={false} chipClass="session-role-badge" data-session-path={session.session_path} />{/if}</small>
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
                  askLeaveSession(session)
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

<!-- Add to Session Sheet (rows act via the Add button -> confirm Dialog on top) -->
<Sheet bind:open={modalOpen} title={isUserProfile ? 'Add me to a Session' : `Add ${person.name} to a Session`}>
  <div class="search-section mb-3">
    <SearchField
      bind:value={searchValue}
      id="session-search"
      placeholder="Type to search sessions..."
      onSearch={onSearch} />
  </div>
  <div class="role-section mb-3">
    <span class="form-label">{isUserProfile ? 'Add me as:' : 'Add as:'}</span>
    <Seg
      options={RELATIONSHIPS}
      value={selectedRelationship}
      onSelect={(id) => (selectedRelationship = id)}
      idAttr="data-relationship" />
    <p class="role-hint">
      {#if selectedRelationship === 'member'}
        {isUserProfile ? 'Its' : "The session's"} tunes count as
        {isUserProfile ? 'yours' : `${person.name}'s`}.
      {:else}
        Records the visit without making the session
        {isUserProfile ? 'yours' : `${person.name}'s`}.
      {/if}
    </p>
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
                onclick={() => askAddPersonToSession(session.session_id, session.name)}>
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
</Sheet>

<Dialog
  bind:open={leaveOpen}
  title={`Leave "${leaveTarget ? leaveTarget.session_name : ''}"?`}
  description="This will remove you from the session's member list. Your attendance history will be preserved."
  confirmLabel="Leave session"
  destructive={true}
  onConfirm={() => leaveSession(leaveTarget)}
  onCancel={() => (leaveTarget = null)} />

<Dialog
  bind:open={addConfirmOpen}
  title={`Add ${person.name} to "${addTarget ? addTarget.sessionName : ''}"?`}
  description={`${person.name} will be added as a ${selectedRelationship}.`}
  confirmLabel="Add to session"
  onConfirm={() => addPersonToSession(addTarget.sessionId)}
  onCancel={() => (addTarget = null)} />

<style>
  .sessions-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .sessions-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  /* The standard "+" affordance, top-right of the results (spec 034 Change 3). */
  .sessions-add-btn {
    flex: none;
    width: 2rem;
    height: 2rem;
    line-height: 1;
    font-size: 1.15rem;
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: 50%;
    background: var(--bg-secondary, transparent);
    color: inherit;
    cursor: pointer;
  }
  .sessions-add-btn:hover {
    border-color: var(--primary, #007bff);
    color: var(--primary, #007bff);
  }
  .role-hint {
    font-size: 0.82rem;
    color: var(--text-muted, #6c757d);
    margin: 0.5rem 0 0;
  }
</style>
