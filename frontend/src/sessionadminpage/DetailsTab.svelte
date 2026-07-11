<script>
  // Details tab: the session-details edit form (save via PUT
  // /api/sessions/<path>/admin-update), termination / reactivation flows, and
  // the recurrence schedule editor with live preview.
  import { formatTime } from './logic.js'

  let { session, sessionPath, timezoneOptions = [] } = $props()

  const toast = (msg, type) => window.showMessage && window.showMessage(msg, type)

  // --- Form fields ------------------------------------------------------------
  let name = $state(session.name || '')
  let path = $state(session.path || '')
  let locationName = $state(session.location_name || '')
  let locationStreet = $state(session.location_street || '')
  let city = $state(session.city || '')
  let stateField = $state(session.state || '')
  let country = $state(session.country || '')
  let timezone = $state(session.timezone)
  let locationPhone = $state(session.location_phone || '')
  let locationWebsite = $state(session.location_website || '')
  let initiationDate = $state(session.initiation_date || '')
  let terminationDate = $state(session.termination_date || '')
  let unlistedAddress = $state(!!session.unlisted_address)
  let comments = $state(session.comments || '')
  let autoCreateInstances = $state(!!session.auto_create_instances)
  let autoCreateHours = $state(String(session.auto_create_hours_ahead))

  function saveSessionDetails() {
    // Collect form data
    const formData = {
      name: name.trim(),
      path: path.trim(),
      location_name: locationName.trim(),
      location_street: locationStreet.trim(),
      city: city.trim(),
      state: stateField.trim(),
      country: country.trim(),
      timezone: timezone,
      location_website: locationWebsite.trim(),
      location_phone: locationPhone.trim(),
      initiation_date: initiationDate,
      unlisted_address: unlistedAddress,
      comments: comments.trim(),
      auto_create_instances: autoCreateInstances,
      auto_create_hours_ahead: parseInt(autoCreateHours) || 24,
    }

    // Include termination date if it exists
    if (session.termination_date) {
      formData.termination_date = terminationDate
    }

    // Basic validation
    if (!formData.name) {
      toast('Session name is required', 'error')
      return
    }
    if (!formData.path) {
      toast('URL path is required', 'error')
      return
    }

    fetch(`/api/sessions/${sessionPath}/admin-update`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          toast(data.message || 'Session details saved successfully', 'success')
        } else {
          toast(data.error || 'Failed to save session details', 'error')
        }
      })
      .catch((error) => {
        console.error('Error saving session details:', error)
        toast('An error occurred while saving session details', 'error')
      })
  }

  // --- Termination / reactivation ----------------------------------------------
  let terminationModalOpen = $state(false)
  let modalTerminationDate = $state('')
  let modalError = $state('')

  function openTerminationModal() {
    modalError = ''
    modalTerminationDate = ''
    terminationModalOpen = true
    document.body.classList.add('modal-open')
  }

  function hideModal() {
    terminationModalOpen = false
    document.body.classList.remove('modal-open')
  }

  function onWindowKeydown(e) {
    if (e.key === 'Escape' && terminationModalOpen) hideModal()
  }

  function saveTerminationDate() {
    if (!modalTerminationDate) {
      modalError = 'Please select a date.'
      return
    }
    setTerminationDate(modalTerminationDate)
  }

  function setTerminationDate(value) {
    fetch(`/api/admin/sessions/${sessionPath}/terminate`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ termination_date: value }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          hideModal()
          // Reload page to show updated state
          window.location.reload()
        } else {
          modalError = data.error || 'Failed to set termination date'
        }
      })
      .catch((error) => {
        console.error('Error setting termination date:', error)
        modalError = 'An error occurred while setting the termination date'
      })
  }

  function reactivateSession() {
    fetch(`/api/admin/sessions/${sessionPath}/reactivate`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          // Reload page to show updated state
          window.location.reload()
        } else {
          alert('Error: ' + (data.error || 'Failed to reactivate session'))
        }
      })
      .catch((error) => {
        console.error('Error reactivating session:', error)
        alert('An error occurred while reactivating the session')
      })
  }

  // --- Recurrence editor --------------------------------------------------------
  const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
  const NTH_OPTIONS = [
    { value: 1, label: '1st' },
    { value: 2, label: '2nd' },
    { value: 3, label: '3rd' },
    { value: 4, label: '4th' },
    { value: -1, label: 'Last' },
  ]

  let recurrenceEditMode = $state(false)
  let schedules = $state([]) // [{id, type, weekday, start_time, end_time, every_n_weeks, which:Set-like array}]
  let scheduleIdCounter = 0

  function newSchedule(data = null) {
    return {
      id: scheduleIdCounter++,
      type: data?.type || 'weekly',
      weekday: data?.weekday || 'monday',
      start_time: data?.start_time || '19:00',
      end_time: data?.end_time || '22:00',
      every_n_weeks: data?.every_n_weeks || 1,
      which: data?.which ? [...data.which] : [1],
    }
  }

  function showRecurrenceEditMode() {
    recurrenceEditMode = true
    schedules = []
    scheduleIdCounter = 0
    // Load existing recurrence data if it exists
    const existingRecurrence = session.recurrence || ''
    if (existingRecurrence) {
      try {
        const recurrenceData =
          typeof existingRecurrence === 'string' ? JSON.parse(existingRecurrence) : existingRecurrence
        if (recurrenceData.schedules && Array.isArray(recurrenceData.schedules)) {
          schedules = recurrenceData.schedules.map((s) => newSchedule(s))
        }
      } catch (e) {
        console.error('Error parsing recurrence JSON:', e)
      }
    }
    // If no schedules were added, show one empty form
    if (schedules.length === 0) {
      schedules = [newSchedule()]
    }
  }

  function hideRecurrenceEditMode() {
    recurrenceEditMode = false
    schedules = []
    scheduleIdCounter = 0
  }

  function addScheduleForm() {
    schedules = [...schedules, newSchedule()]
  }

  function removeSchedule(id) {
    schedules = schedules.filter((s) => s.id !== id)
  }

  function selectWeekday(schedule, weekday) {
    schedule.weekday = weekday
    schedules = [...schedules]
  }

  function toggleNth(schedule, value, checked) {
    if (checked) {
      if (!schedule.which.includes(value)) schedule.which = [...schedule.which, value]
    } else {
      schedule.which = schedule.which.filter((v) => v !== value)
    }
    schedules = [...schedules]
  }

  function collectSchedulesFromForm() {
    return schedules.map((s) => {
      const schedule = {
        type: s.type,
        weekday: s.weekday,
        start_time: s.start_time,
        end_time: s.end_time,
      }
      if (s.type === 'weekly') {
        schedule.every_n_weeks = parseInt(s.every_n_weeks)
      } else if (s.type === 'monthly_nth_weekday') {
        schedule.which = s.which.map((v) => parseInt(v))
      }
      return schedule
    })
  }

  // Preview text (legacy updateRecurrencePreview, recomputed reactively).
  const previewItems = $derived(
    collectSchedulesFromForm().map((schedule, idx) => {
      let desc = `Schedule ${idx + 1}: ${schedule.weekday}s`
      if (schedule.type === 'weekly') {
        desc += schedule.every_n_weeks > 1 ? ` (every ${schedule.every_n_weeks} weeks)` : ''
      } else {
        const nthLabels = (schedule.which || []).map((n) => (n === -1 ? 'last' : ['1st', '2nd', '3rd', '4th'][n - 1]))
        desc += ` (${nthLabels.join(', ')} of month)`
      }
      desc += ` from ${formatTime(schedule.start_time)} to ${formatTime(schedule.end_time)}`
      return desc
    })
  )

  function saveRecurrenceFromForm() {
    const collected = collectSchedulesFromForm()

    if (collected.length === 0) {
      // Save empty recurrence
      saveRecurrenceJSON('')
      return
    }

    // Validate all schedules have required fields
    for (let schedule of collected) {
      if (!schedule.weekday || !schedule.start_time || !schedule.end_time) {
        toast('All schedules must have a weekday, start time, and end time', 'error')
        return
      }
      if (schedule.type === 'monthly_nth_weekday' && (!schedule.which || schedule.which.length === 0)) {
        toast('Monthly patterns must have at least one occurrence selected', 'error')
        return
      }
    }

    const recurrenceJSON = JSON.stringify({ schedules: collected }, null, 2)
    saveRecurrenceJSON(recurrenceJSON)
  }

  function saveRecurrenceJSON(recurrenceValue) {
    // Validate JSON if not empty
    if (recurrenceValue) {
      try {
        JSON.parse(recurrenceValue)
      } catch (e) {
        toast('Invalid JSON format. Please check your recurrence pattern.', 'error')
        return
      }
    }

    // Make API call to save just the recurrence field
    fetch(`/api/sessions/${sessionPath}/admin-update`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recurrence: recurrenceValue }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          toast('Recurrence schedule updated successfully', 'success')
          // Reload page to show updated human-readable format
          setTimeout(() => window.location.reload(), 1000)
        } else {
          toast(data.error || 'Failed to update recurrence schedule', 'error')
        }
      })
      .catch((error) => {
        console.error('Error saving recurrence:', error)
        toast('An error occurred while saving the recurrence schedule', 'error')
      })
  }

  const capitalize3 = (day) => day.charAt(0).toUpperCase() + day.slice(1, 3)
</script>

<svelte:window onkeydown={onWindowKeydown} />

<section class="docs-section">
  <h2 class="section-heading">Session Details</h2>

  <form
    id="session-details-form"
    onsubmit={(e) => {
      e.preventDefault()
      saveSessionDetails()
    }}>
    <input type="hidden" id="session-id" value={session.session_id} />

    <div class="row">
      <div class="col-md-6">
        <div class="mb-3">
          <label for="session-name" class="form-label">Session Name</label>
          <input type="text" class="form-control" id="session-name" bind:value={name} />
        </div>

        <div class="mb-3">
          <label for="session-path" class="form-label">URL Path</label>
          <input type="text" class="form-control" id="session-path" bind:value={path} />
        </div>

        <div class="mb-3">
          <label for="location-name" class="form-label">Location Name</label>
          <input type="text" class="form-control" id="location-name" bind:value={locationName} />
        </div>

        <div class="mb-3">
          <label for="location-street" class="form-label">Street Address</label>
          <input type="text" class="form-control" id="location-street" bind:value={locationStreet} />
        </div>
      </div>

      <div class="col-md-6">
        <div class="mb-3">
          <label for="city" class="form-label">City</label>
          <input type="text" class="form-control" id="city" bind:value={city} />
        </div>

        <div class="mb-3">
          <label for="state" class="form-label">State</label>
          <input type="text" class="form-control" id="state" bind:value={stateField} />
        </div>

        <div class="mb-3">
          <label for="country" class="form-label">Country</label>
          <input type="text" class="form-control" id="country" bind:value={country} />
        </div>

        <div class="mb-3">
          <label for="timezone" class="form-label">Timezone</label>
          <select class="form-select" id="timezone" name="timezone" bind:value={timezone}>
            {#each timezoneOptions as tz (tz.value)}
              <option value={tz.value}>{tz.label}</option>
            {/each}
          </select>
        </div>
      </div>
    </div>

    <div class="row">
      <div class="col-md-6">
        <div class="mb-3">
          <label for="location-phone" class="form-label">Location Phone</label>
          <input type="tel" class="form-control" id="location-phone" bind:value={locationPhone} />
        </div>

        <div class="mb-3">
          <label for="location-website" class="form-label">Location Website</label>
          <input type="url" class="form-control" id="location-website" bind:value={locationWebsite} />
        </div>

        <div class="mb-3">
          <label for="initiation-date" class="form-label">First Session Date</label>
          <input type="date" class="form-control" id="initiation-date" bind:value={initiationDate} />
        </div>
      </div>

      <div class="col-md-6">
        {#if session.termination_date}
          <div class="mb-3">
            <label for="termination-date" class="form-label">Last Session Date</label>
            <input type="date" class="form-control" id="termination-date" bind:value={terminationDate} />
            <div class="mt-2">
              <a
                href="#reactivate"
                id="reactivate-session-link"
                class="text-success"
                onclick={(e) => {
                  e.preventDefault()
                  if (confirm('Are you sure you want to reactivate this session? This will remove the termination date.')) {
                    reactivateSession()
                  }
                }}>
                <i class="fas fa-play-circle"></i> Reactivate session
              </a>
            </div>
          </div>
        {:else}
          <div class="mb-3">
            <div class="alert alert-warning">
              <strong>Session Status:</strong> This session is currently active
            </div>
            <a
              href="#deactivate"
              id="deactivate-session-link"
              class="text-danger"
              onclick={(e) => {
                e.preventDefault()
                openTerminationModal()
              }}>
              <i class="fas fa-stop-circle"></i> Mark this session as inactive
            </a>
          </div>
        {/if}

        <div class="mb-3">
          <div class="form-check">
            <input class="form-check-input" type="checkbox" id="unlisted-address" bind:checked={unlistedAddress} />
            <label class="form-check-label" for="unlisted-address">
              Hide address from public
            </label>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-3">
      <span class="form-label">Recurrence Schedule</span>

      <!-- Read-only view -->
      <div id="recurrence-readonly-view" style:display={recurrenceEditMode ? 'none' : ''}>
        {#if session.recurrence_readable}
          <div class="recurrence-display p-3 border rounded bg-light">
            <div class="d-flex justify-content-between align-items-start">
              <div class="recurrence-text">{session.recurrence_readable}</div>
              <button type="button" class="btn btn-sm btn-outline-primary" onclick={showRecurrenceEditMode}>
                <i class="fas fa-edit"></i> Edit
              </button>
            </div>
          </div>
        {:else}
          <div class="recurrence-display p-3 border rounded bg-light text-muted">
            <div class="d-flex justify-content-between align-items-center">
              <div>No recurrence pattern set</div>
              <button type="button" class="btn btn-sm btn-primary" onclick={showRecurrenceEditMode}>
                <i class="fas fa-plus"></i> Add Schedule
              </button>
            </div>
          </div>
        {/if}
      </div>

      <!-- Edit mode (hidden by default) -->
      <div id="recurrence-edit-view" style:display={recurrenceEditMode ? '' : 'none'}>
        <div id="recurrence-schedules-container">
          {#each schedules as schedule, idx (schedule.id)}
            <div class="schedule-form" id="schedule-{schedule.id}">
              <div class="schedule-form-header">
                <span class="schedule-form-title">Schedule {schedule.id + 1}</span>
                <button type="button" class="btn btn-sm btn-outline-danger" onclick={() => removeSchedule(schedule.id)}>
                  <i class="fas fa-trash"></i> Remove
                </button>
              </div>

              <div class="mb-3">
                <span class="form-label">Pattern Type</span>
                <select
                  class="form-select schedule-type"
                  data-schedule-id={schedule.id}
                  bind:value={schedule.type}>
                  <option value="weekly">Weekly</option>
                  <option value="monthly_nth_weekday">Monthly (Nth Weekday)</option>
                </select>
              </div>

              <div class="mb-3">
                <span class="form-label">Weekday</span>
                <div class="weekday-buttons">
                  {#each WEEKDAYS as day (day)}
                    <button
                      type="button"
                      class="weekday-btn {day === schedule.weekday ? 'active' : ''}"
                      data-schedule-id={schedule.id}
                      data-weekday={day}
                      onclick={() => selectWeekday(schedule, day)}>
                      {capitalize3(day)}
                    </button>
                  {/each}
                </div>
              </div>

              <div class="weekly-options" id="weekly-options-{schedule.id}" style:display={schedule.type === 'weekly' ? '' : 'none'}>
                <div class="mb-3">
                  <span class="form-label">Frequency</span>
                  <select class="form-select schedule-frequency" data-schedule-id={schedule.id} bind:value={schedule.every_n_weeks}>
                    <option value={1}>Every week</option>
                    <option value={2}>Every 2 weeks</option>
                    <option value={3}>Every 3 weeks</option>
                    <option value={4}>Every 4 weeks</option>
                  </select>
                </div>
              </div>

              <div
                class="monthly-options"
                id="monthly-options-{schedule.id}"
                style:display={schedule.type === 'monthly_nth_weekday' ? '' : 'none'}>
                <div class="mb-3">
                  <span class="form-label">Which occurrences?</span>
                  <div class="nth-occurrence-checkboxes">
                    {#each NTH_OPTIONS as opt (opt.value)}
                      <label class="nth-checkbox-label">
                        <input
                          type="checkbox"
                          class="nth-occurrence"
                          data-schedule-id={schedule.id}
                          value={opt.value}
                          checked={schedule.which.includes(opt.value)}
                          onchange={(e) => toggleNth(schedule, opt.value, e.currentTarget.checked)} />
                        <span>{opt.label}</span>
                      </label>
                    {/each}
                  </div>
                </div>
              </div>

              <div class="row">
                <div class="col-md-6 mb-3">
                  <label class="form-label" for="schedule-start-{schedule.id}">Start Time</label>
                  <input
                    type="time"
                    class="form-control schedule-start-time"
                    id="schedule-start-{schedule.id}"
                    data-schedule-id={schedule.id}
                    bind:value={schedule.start_time} />
                </div>
                <div class="col-md-6 mb-3">
                  <label class="form-label" for="schedule-end-{schedule.id}">End Time</label>
                  <input
                    type="time"
                    class="form-control schedule-end-time"
                    id="schedule-end-{schedule.id}"
                    data-schedule-id={schedule.id}
                    bind:value={schedule.end_time} />
                </div>
              </div>
            </div>
          {/each}
        </div>

        <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick={addScheduleForm}>
          <i class="fas fa-plus"></i> Add Schedule
        </button>

        <!-- Preview section -->
        <div id="recurrence-preview" class="mt-3 p-3 border rounded bg-light" style:display={previewItems.length ? 'block' : 'none'}>
          <h6 class="mb-2">Next 5 Occurrences:</h6>
          <ul id="recurrence-preview-list" class="mb-0">
            {#each previewItems as item, i (i)}
              <li>{item}</li>
            {/each}
          </ul>
        </div>

        <div class="mt-3">
          <button type="button" class="btn btn-sm btn-secondary" onclick={hideRecurrenceEditMode}>Cancel</button>
          <button type="button" class="btn btn-sm btn-primary" onclick={saveRecurrenceFromForm}>Save</button>
        </div>
      </div>
    </div>

    <!-- Auto-create instances settings -->
    <div class="mb-3">
      <span class="form-label">Auto-Create Instances</span>
      <div class="p-3 border rounded bg-light">
        <div class="form-check mb-2">
          <input class="form-check-input" type="checkbox" id="auto-create-instances" bind:checked={autoCreateInstances} />
          <label class="form-check-label" for="auto-create-instances">
            Automatically create session instances ahead of time
          </label>
        </div>
        <div class="d-flex align-items-center gap-2" id="auto-create-hours-container">
          <label for="auto-create-hours" class="form-label mb-0">Create instances</label>
          <input type="number" class="form-control" id="auto-create-hours" bind:value={autoCreateHours} min="1" max="168" style="width: 80px;" />
          <span>hours ahead</span>
        </div>
        <small class="text-muted d-block mt-2">
          When enabled, the system will automatically create upcoming session instances based on the recurrence pattern.
          This runs every 15 minutes.
        </small>
      </div>
    </div>

    <div class="mb-3">
      <label for="comments" class="form-label">Comments</label>
      <textarea class="form-control" id="comments" rows="4" bind:value={comments}></textarea>
    </div>

    <button type="submit" class="btn btn-primary">Save Changes</button>
  </form>
</section>

<!-- Termination Date Modal -->
{#if terminationModalOpen}
  <div
    class="modal show"
    id="terminationDateModal"
    aria-labelledby="terminationDateModalLabel"
    style="display: flex;"
    role="presentation"
    onclick={(e) => {
      if (e.target === e.currentTarget) hideModal()
    }}>
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="terminationDateModalLabel">Set Session End Date</h5>
          <button type="button" class="btn-close" onclick={hideModal} aria-label="Close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="mb-3">What was the last date of the session?</p>
          <div class="mb-3">
            <label for="modal-termination-date" class="form-label">Last Session Date</label>
            <input type="date" class="form-control" id="modal-termination-date" bind:value={modalTerminationDate} required />
          </div>
          <div id="modal-error-message" class="alert alert-danger" style:display={modalError ? 'block' : 'none'}>{modalError}</div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" onclick={hideModal}>Cancel</button>
          <button type="button" class="btn btn-danger" id="save-termination-date" onclick={saveTerminationDate}>Save</button>
        </div>
      </div>
    </div>
  </div>
{/if}
