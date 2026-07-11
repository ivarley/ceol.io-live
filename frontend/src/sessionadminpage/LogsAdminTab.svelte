<script>
  // Logs tab: session instance history table (row click opens the shared
  // SessionInstanceModal from static/js/session_instance_modal.js), ?instance=
  // deep link auto-open, and the Add Session Instance modal (suggestion-prefilled).
  let { sessionPath, locationName, load } = $props()

  const toast = (msg, type) => window.showMessage && window.showMessage(msg, type)

  // session_instance_modal.js declares `const SessionInstanceModal` — a global
  // LEXICAL binding, not a window property. The legacy inline onclick handlers
  // resolved it through the global scope chain; from module code we must do the
  // same (the typeof guard keeps tests/jsdom safe when the script isn't loaded).
  function instanceModal() {
    if (window.SessionInstanceModal) return window.SessionInstanceModal
    // eslint-disable-next-line no-undef
    return typeof SessionInstanceModal !== 'undefined' ? SessionInstanceModal : null
  }

  let logs = $state(null) // null until loaded
  let loadError = $state(null)
  let started = false

  function loadLogsContent() {
    fetch(`/api/admin/sessions/${sessionPath}/logs`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          loadError = data.error
          return
        }
        logs = data.logs

        // Check if we should auto-open a specific instance modal
        const urlParams = new URLSearchParams(window.location.search)
        const instanceId = urlParams.get('instance')
        if (instanceId) {
          // Find the log with this instance ID to get the date
          const log = data.logs.find((l) => l.session_instance_id == instanceId)
          const modal = instanceModal()
          if (log && modal) {
            modal.show(parseInt(instanceId), sessionPath, log.date)
          }
          // Clear the querystring so refreshing doesn't re-open
          window.history.replaceState({}, '', window.location.pathname)
        }
      })
      .catch((error) => {
        loadError = `Failed to load session logs: ${error}`
      })
  }

  $effect(() => {
    if (load && !started) {
      started = true
      loadLogsContent()
    }
  })

  const fmtDate = (dateStr) => {
    const date = new Date(dateStr)
    return {
      main: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
      weekday: date.toLocaleDateString('en-US', { weekday: 'long' }),
    }
  }

  function openInstance(log) {
    const modal = instanceModal()
    if (modal) {
      modal.show(log.session_instance_id, sessionPath, log.date)
    }
  }

  // --- Add Session Instance modal -----------------------------------------------
  let addModalOpen = $state(false)
  let dateValue = $state('')
  let startTimeValue = $state('')
  let endTimeValue = $state('')
  let locationValue = $state('')
  let commentsValue = $state('')

  async function showAddSessionModal() {
    // Set defaults while we fetch the suggestion
    dateValue = new Date().toISOString().split('T')[0]
    startTimeValue = ''
    endTimeValue = ''
    locationValue = ''
    commentsValue = ''

    addModalOpen = true
    document.body.classList.add('modal-open')

    // Fetch the next suggested session instance from the API
    try {
      const response = await fetch(`/api/sessions/${sessionPath}/next_instance_suggestion`)
      const data = await response.json()
      if (data.success) {
        // Update form with suggested values
        dateValue = data.date || dateValue
        startTimeValue = data.start_time || ''
        endTimeValue = data.end_time || ''
      }
    } catch (error) {
      console.error('Failed to get next session suggestion:', error)
      // Keep the default values if API call fails
    }
  }

  function hideAddSessionModal() {
    addModalOpen = false
    document.body.classList.remove('modal-open')
  }

  function onWindowKeydown(event) {
    // Legacy behavior: Escape always closes the add-instance modal.
    if (event.key === 'Escape') {
      hideAddSessionModal()
    }
  }

  function addSessionInstance() {
    const date = dateValue.trim()
    const startTime = startTimeValue.trim()
    const endTime = endTimeValue.trim()
    const location = locationValue.trim()
    const comments = commentsValue.trim()

    if (!date) {
      toast('Please enter a session date', 'error')
      return
    }

    // Prepare request data (optional fields only when provided)
    const requestData = { date: date }
    if (startTime) requestData.start_time = startTime
    if (endTime) requestData.end_time = endTime
    if (location) requestData.location = location
    if (comments) requestData.comments = comments

    fetch(`/api/sessions/${sessionPath}/add_instance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestData),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          toast(data.message)
          hideAddSessionModal()
          // Reload the logs content to show the new instance
          loadLogsContent()
        } else {
          toast(data.message, 'error')
        }
      })
      .catch((error) => {
        toast('Failed to add session instance', 'error')
        console.error('Error:', error)
      })
  }
</script>

<svelte:window onkeydown={onWindowKeydown} />

<section class="docs-section">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
    <h2 class="section-heading" style="margin-bottom: 0;">Session Instance History</h2>
    <button type="button" class="btn btn-primary" id="add-session-instance-btn" onclick={showAddSessionModal}>
      Add Session Instance
    </button>
  </div>
  <div id="logs-content">
    {#if loadError}
      <div class="alert alert-danger">{loadError}</div>
    {:else if !logs}
      <p class="text-muted">Loading session history...</p>
    {:else if logs.length === 0}
      <div class="alert alert-info">No session instances found.</div>
    {:else}
      <div class="table-responsive">
        <table class="table table-striped table-hover" id="logs-table">
          <thead>
            <tr>
              <th>Date</th>
              <th class="text-center">Tunes</th>
              <th class="text-center">Players</th>
              <th class="text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {#each logs as log (log.session_instance_id)}
              <tr
                class="log-row"
                style="cursor: pointer;"
                data-instance-id={log.session_instance_id}
                data-date={log.date}
                onclick={() => openInstance(log)}>
                <td class="log-date">
                  <strong>{fmtDate(log.date).main}</strong>
                  <br />
                  <small class="text-muted">{fmtDate(log.date).weekday}</small>
                </td>
                <td class="log-tunes text-center">{log.tune_count}</td>
                <td class="log-attendance text-center">{log.attendance_count}</td>
                <td class="log-status text-center">
                  {#if log.is_cancelled}<span class="badge bg-danger">Cancelled</span>{:else}<span class="badge bg-success">Held</span>{/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>

<!-- Add Session Instance Modal -->
{#if addModalOpen}
  <!-- "show" matters: .modal-overlay (tune_detail_modal.css) is opacity:0 without it,
       and legacy ModalManager.showModal always added it. -->
  <div id="add-session-instance-modal" class="modal-overlay show" style="display: flex;">
    <div class="modal-dialog">
      <div class="modal-dialog-content">
        <div class="modal-header">
          <h3 class="modal-title">Add Session Instance</h3>
        </div>
        <div class="modal-body">
          <div class="mb-3">
            <label for="session-date-input" class="form-label">Session Date:</label>
            <input type="date" id="session-date-input" class="form-control" bind:value={dateValue} required />
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div class="mb-3">
              <label for="session-start-time-input" class="form-label">Start Time:</label>
              <input type="time" id="session-start-time-input" class="form-control" bind:value={startTimeValue} />
            </div>
            <div class="mb-3">
              <label for="session-end-time-input" class="form-label">End Time:</label>
              <input type="time" id="session-end-time-input" class="form-control" bind:value={endTimeValue} />
            </div>
          </div>

          <div class="mb-3">
            <label for="session-location-input" class="form-label">Location:</label>
            <input type="text" id="session-location-input" class="form-control" placeholder="The usual: {locationName}" bind:value={locationValue} />
          </div>

          <div class="mb-3">
            <label for="session-comments-input" class="form-label">Comments:</label>
            <textarea id="session-comments-input" class="form-control" placeholder="Notes about this session" rows="3" style="resize: vertical;" bind:value={commentsValue}></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="add-session-cancel-btn" onclick={hideAddSessionModal}>Cancel</button>
          <button type="button" class="btn btn-primary" id="add-session-confirm-btn" onclick={addSessionInstance}>Add Session</button>
        </div>
      </div>
    </div>
  </div>
{/if}
