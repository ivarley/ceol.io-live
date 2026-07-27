<script>
  // The Add Session Instance sheet — kit Sheet chrome (spec 035: Cancel top-left,
  // scrim/Escape cancel, commit in the footer so a failed POST keeps it open).
  // Opening prefills from GET next_instance_suggestion; adding POSTs add_instance
  // and redirects to the new instance in edit mode.
  // isFestival re-frames one field: `location` is stored as session_instance.location_override,
  // which at a festival is the log's NAME, not an exception to the usual venue — several
  // sessions share the date, so it's the only thing telling them apart afterwards.
  let { sessionPath, locationName, isFestival = false } = $props()

  let visible = $state(false)
  let date = $state('')
  let startTime = $state('')
  let endTime = $state('')
  let location = $state('')
  let comments = $state('')

  import { Sheet, toast } from '../lib/index.js'

  export async function open() {
    // Defaults while we fetch the suggestion.
    date = new Date().toISOString().split('T')[0]
    startTime = ''
    endTime = ''
    location = ''
    comments = ''
    visible = true

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
</script>

<Sheet bind:open={visible} title="Add Session Instance">
  <!-- .modal-body keeps the page's label/input styling; the chrome is the Sheet's -->
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

    <label for="session-location-input" style="margin-top: 16px;">{isFestival ? 'Name:' : 'Location:'}</label>
    <input
      type="text"
      id="session-location-input"
      placeholder={isFestival ? 'e.g. Advanced Session @ Jim Bowie' : `The usual: ${locationName}`}
      bind:value={location} />
    {#if isFestival}
      <small class="add-instance-hint">
        Several sessions share a day at a festival, so the date alone won't tell them
        apart. This is what the log is called everywhere it's listed.
      </small>
    {/if}

    <label for="session-comments-input" style="margin-top: 16px;">Comments:</label>
    <textarea
      id="session-comments-input"
      placeholder="Notes about this session"
      rows="3"
      style="resize: vertical;"
      bind:value={comments}></textarea>
  </div>
  {#snippet footer()}
    <div style="text-align: right;">
      <button type="button" class="selection-btn primary" id="add-session-confirm-btn" onclick={addSessionInstance}>Add Session</button>
    </div>
  {/snippet}
</Sheet>

<style>
  /* Sits directly under the Name input, so it reads as that field's caption. */
  .add-instance-hint {
    display: block;
    margin-top: 6px;
    color: var(--text-muted, #9a9aa3);
    font-size: 12px;
    line-height: 1.4;
  }
</style>
