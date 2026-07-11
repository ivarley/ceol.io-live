<script>
  // The Add Session Instance modal — the legacy #add-session-instance-modal,
  // with the ModalManager.showModal/hideModal calls replaced by component state.
  // Opening prefills from GET next_instance_suggestion; adding POSTs add_instance
  // and redirects to the new instance in edit mode.
  let { sessionPath, locationName } = $props()

  let visible = $state(false)
  let date = $state('')
  let startTime = $state('')
  let endTime = $state('')
  let location = $state('')
  let comments = $state('')

  import { toast } from '../lib/index.js'

  export async function open() {
    // Defaults while we fetch the suggestion.
    date = new Date().toISOString().split('T')[0]
    startTime = ''
    endTime = ''
    location = ''
    comments = ''
    visible = true
    document.body.classList.add('modal-open')

    try {
      const response = await fetch(`/api/sessions/${sessionPath}/next_instance_suggestion`)
      const data = await response.json()
      if (data.success) {
        date = data.date || date
        startTime = data.start_time || ''
        endTime = data.end_time || ''
      }
    } catch (error) {
      console.error('Failed to get next session suggestion:', error)
      // Keep the default values if the API call fails.
    }
  }

  export function close() {
    visible = false
    document.body.classList.remove('modal-open')
  }

  function addSessionInstance() {
    const dateVal = date.trim()
    if (!dateVal) {
      toast('Please enter a session date', 'error')
      return
    }

    const requestData = { date: dateVal }
    if (startTime.trim()) requestData.start_time = startTime.trim()
    if (endTime.trim()) requestData.end_time = endTime.trim()
    if (location.trim()) requestData.location = location.trim()
    if (comments.trim()) requestData.comments = comments.trim()

    fetch(`/api/sessions/${sessionPath}/add_instance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestData),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          toast(data.message, 'success')
          close()
          // Redirect to the new session instance in edit mode; the id-based URL
          // is unambiguous when several instances share a date.
          const instanceId = data.session_instance_id || dateVal
          window.location.href = `/sessions/${sessionPath}/${instanceId}?edit=true`
        } else {
          toast(data.message, 'error')
        }
      })
      .catch((error) => {
        toast('Failed to add session instance', 'error')
        console.error('Error:', error)
      })
  }

  function onKeydown(event) {
    if (event.key !== 'Escape') return
    // The shared tune-detail drawer closes itself on Escape; don't double-handle.
    const tuneModal = document.getElementById('tune-detail-modal')
    if (tuneModal && tuneModal.style.display === 'flex') return
    if (visible) close()
  }
</script>

<svelte:window onkeydown={onKeydown} />

<!-- Add Session Instance Modal -->
<div
  id="add-session-instance-modal"
  class="modal-overlay"
  class:show={visible}
  style:display={visible ? 'flex' : 'none'}
  onclick={(e) => {
    if (e.target === e.currentTarget) close()
  }}>
  <div class="modal-content">
    <div class="modal-header">
      <h3>Add Session Instance</h3>
    </div>
    <div class="modal-body">
      <label for="session-date-input">Session Date:</label>
      <input
        type="date"
        id="session-date-input"
        required
        bind:value={date}
        onkeydown={(e) => {
          if (e.key === 'Enter' && visible) addSessionInstance()
        }} />

      <div style="margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div>
          <label for="session-start-time-input">Start Time:</label>
          <input type="time" id="session-start-time-input" bind:value={startTime} />
        </div>
        <div>
          <label for="session-end-time-input">End Time:</label>
          <input type="time" id="session-end-time-input" bind:value={endTime} />
        </div>
      </div>

      <label for="session-location-input" style="margin-top: 16px;">Location:</label>
      <input type="text" id="session-location-input" placeholder="The usual: {locationName}" bind:value={location} />

      <label for="session-comments-input" style="margin-top: 16px;">Comments:</label>
      <textarea
        id="session-comments-input"
        placeholder="Notes about this session"
        rows="3"
        style="resize: vertical;"
        bind:value={comments}></textarea>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn-secondary" id="add-session-cancel-btn" onclick={close}>Cancel</button>
      <button type="button" class="btn-primary" id="add-session-confirm-btn" onclick={addSessionInstance}>Add Session</button>
    </div>
  </div>
</div>
