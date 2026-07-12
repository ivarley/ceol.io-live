<script>
  // The session-instance detail sheet — the Svelte port of the vanilla
  // static/js/session_instance_modal.js (spec 035 Sheet unification). Kit Sheet
  // chrome replaces the slide-in overlay; the body (info rows, comments, the
  // View/Edit/Delete actions and the inline delete confirmation) is ported
  // behavior-for-behavior: details come from the same admin logs endpoint,
  // delete calls the same DELETE route and reports through the site toast.
  import { parseLocalDate } from '../shared/parse.js'
  import { Sheet, toast } from '../lib/index.js'

  let { onDeleted = () => {} } = $props()

  let open = $state(false)
  let loading = $state(false)
  let error = $state('')
  let instance = $state(null)
  let deleteConfirmShown = $state(false)
  let deleting = $state(false)

  let sessionPath = $state('')
  let currentDate = $state('')

  export function show(sessionInstanceId, path, date) {
    sessionPath = path
    currentDate = date
    instance = null
    error = ''
    deleteConfirmShown = false
    deleting = false
    loading = true
    open = true

    // Same source as the legacy modal: the admin logs list, filtered client-side.
    fetch(`/api/admin/sessions/${path}/logs`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to fetch session logs')
        return response.json()
      })
      .then((data) => {
        if (data.error) throw new Error(data.error)
        const found = data.logs.find((log) => log.session_instance_id === sessionInstanceId)
        if (!found) throw new Error('Session instance not found')
        instance = found
        loading = false
      })
      .catch((e) => {
        console.error('Error fetching instance details:', e)
        error = e.message
        loading = false
      })
  }

  // "Monday, June 2, 2026" — same formatting as the legacy header, now the sheet
  // title (computed from the passed date so it shows during the load too).
  const dateStr = $derived(
    currentDate
      ? parseLocalDate(currentDate).toLocaleDateString('en-US', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        })
      : ''
  )

  const timeRange = $derived.by(() => {
    if (!instance) return ''
    if (instance.start_time && instance.end_time) return `${instance.start_time} - ${instance.end_time}`
    if (instance.start_time) return `From ${instance.start_time}`
    return 'Time not specified'
  })

  function showDeleteConfirmation() {
    deleteConfirmShown = true
    // Bring the confirmation into view inside the scrolling sheet body (legacy behavior).
    setTimeout(() => {
      document.getElementById('delete-confirmation')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 0)
  }

  function executeDelete() {
    deleting = true
    fetch(`/api/sessions/${sessionPath}/${currentDate}/delete`, { method: 'DELETE' })
      .then((response) => {
        if (!response.ok) throw new Error('Failed to delete session instance')
        return response.json()
      })
      .then((data) => {
        if (!data.success) throw new Error(data.message || 'Failed to delete session instance')
        toast(data.message || 'Session instance deleted successfully', 'success')
        open = false
        onDeleted() // refresh the logs table
      })
      .catch((e) => {
        console.error('Error deleting instance:', e)
        deleting = false
        deleteConfirmShown = false
        error = e.message
      })
  }
</script>

<Sheet bind:open title={dateStr}>
  {#if loading || deleting}
    <div class="instance-modal-loading">
      <div class="instance-loading-spinner"></div>
      <p>{deleting ? 'Deleting instance...' : 'Loading instance details...'}</p>
    </div>
  {:else if error}
    <div class="modal-error">
      <h3>Error</h3>
      <p>{error}</p>
      <button class="instance-action-btn instance-action-btn-primary" onclick={() => (open = false)}>Close</button>
    </div>
  {:else if instance}
    <div class="instance-modal-subtitle">{sessionPath}</div>

    <div class="instance-info-section">
      <div class="instance-info-row">
        <span class="instance-info-label">Time:</span>
        <span class="instance-info-value">{timeRange}</span>
      </div>
      <div class="instance-info-row">
        <span class="instance-info-label">Status:</span>
        <span class="instance-status-badge {instance.is_cancelled ? 'instance-status-cancelled' : 'instance-status-held'}">
          {instance.is_cancelled ? 'Cancelled' : 'Held'}
        </span>
      </div>
      <div class="instance-info-row">
        <span class="instance-info-label">Tunes Played:</span>
        <span class="instance-info-value">
          <a href="/sessions/{sessionPath}/{instance.date}" target="_blank">
            {instance.tune_count} tune{instance.tune_count !== 1 ? 's' : ''}
          </a>
        </span>
      </div>
      <div class="instance-info-row">
        <span class="instance-info-label">Attendance:</span>
        <span class="instance-info-value">{instance.attendance_count} player{instance.attendance_count !== 1 ? 's' : ''}</span>
      </div>
    </div>

    {#if instance.comments && instance.comments.trim()}
      <div class="instance-comments-section">
        <div class="instance-comments-label">Comments:</div>
        <div class="instance-comments-value">{instance.comments}</div>
      </div>
    {/if}

    <div class="instance-modal-actions">
      <a href="/sessions/{sessionPath}/{instance.date}" class="instance-action-btn instance-action-btn-primary" target="_blank">
        View Full Log
      </a>
      <a href="/sessions/{sessionPath}/{instance.date}?mode=edit" class="instance-action-btn instance-action-btn-secondary">
        Edit Log
      </a>
      <button class="instance-action-btn instance-action-btn-danger" onclick={showDeleteConfirmation}>
        Delete This Instance
      </button>
    </div>

    {#if deleteConfirmShown}
      <div id="delete-confirmation">
        <div class="instance-delete-confirm">
          <div class="instance-delete-confirm-title">⚠️ Confirm Deletion</div>
          <div class="instance-delete-confirm-text">
            Are you sure you want to delete this session instance?<br />
            This will remove:<br />
            • {instance.tune_count} {instance.tune_count === 1 ? 'tune' : 'tunes'}<br />
            • {instance.attendance_count} {instance.attendance_count === 1 ? 'player' : 'players'}
            <br /><br />
            <strong>This action cannot be undone.</strong>
          </div>
          <div class="instance-delete-confirm-actions">
            <button class="instance-delete-confirm-btn instance-delete-cancel-btn" onclick={() => (deleteConfirmShown = false)}>
              Cancel
            </button>
            <button class="instance-delete-confirm-btn instance-delete-execute-btn" onclick={executeDelete}>
              Yes, Delete Instance
            </button>
          </div>
        </div>
      </div>
    {/if}
  {/if}
</Sheet>
