<script>
  // The session-details review/edit sheet: seeded from thesession.org data (or
  // empty for the "just add it here" flow), holds the recurrence editor and the
  // "Add me as" control, and commits via POST /api/add-session. The commit
  // lives in the footer (not header Done) so a failed save keeps the sheet open
  // for retry — the kit convention for server-side commits.
  import { Sheet, Seg } from '../lib/index.js'
  import { summarizeRecurrence } from './logic.js'

  let {
    open = $bindable(false),
    seed = null, // a NEW object per open — fields reset from it
    timezoneOptions = [],
    addMeDefault = true, // false when the page was opened with ?acu=false
    navigate = (url) => window.location.assign(url),
  } = $props()

  // ---- form fields (reset from each new seed) --------------------------------
  let thesessionId = $state('')
  let name = $state('')
  let path = $state('')
  let locationName = $state('')
  let locationPhone = $state('')
  let locationWebsite = $state('')
  let city = $state('')
  let stateArea = $state('')
  let country = $state('')
  let inceptionDate = $state('')
  let timezone = $state('America/Chicago')
  let addMe = $state(true)
  let addMeRole = $state('admin')
  let unparsedText = $state('')

  // ---- recurrence editor ------------------------------------------------------
  let recType = $state('')
  let weekday = $state(null)
  let frequency = $state(1)
  let which = $state([])
  let startTime = $state('19:00')
  let endTime = $state('22:00')
  let recExpanded = $state(false)

  const WEEKDAYS = [
    { id: 'monday', label: 'Mon' },
    { id: 'tuesday', label: 'Tue' },
    { id: 'wednesday', label: 'Wed' },
    { id: 'thursday', label: 'Thu' },
    { id: 'friday', label: 'Fri' },
    { id: 'saturday', label: 'Sat' },
    { id: 'sunday', label: 'Sun' },
  ]
  const NTH_OPTIONS = [
    { value: 1, label: '1st' },
    { value: 2, label: '2nd' },
    { value: 3, label: '3rd' },
    { value: 4, label: '4th' },
    { value: -1, label: 'Last' },
  ]

  const recurrence = $derived(
    summarizeRecurrence({ type: recType, weekday, frequency, which, startTime, endTime })
  )

  // ---- validation + save --------------------------------------------------------
  let invalidFields = $state([])
  let formError = $state('')
  let saving = $state(false)

  function applySeed(s) {
    thesessionId = s.thesession_id ?? ''
    name = s.name ?? ''
    path = s.path ?? ''
    locationName = s.location_name ?? ''
    locationPhone = s.location_phone ?? ''
    locationWebsite = s.location_website ?? ''
    city = s.city ?? ''
    stateArea = s.state ?? ''
    country = s.country ?? ''
    inceptionDate = s.inception_date ?? ''
    timezone = s.timezone ?? 'America/Chicago'
    addMe = addMeDefault
    addMeRole = 'admin'
    unparsedText = s.unparsedText ?? ''
    invalidFields = []
    formError = ''
    saving = false
    // recurrence: seed with the parsed schedule, or reset
    recExpanded = false
    if (s.schedule) {
      recType = s.schedule.type
      weekday = s.schedule.weekday ?? null
      frequency = s.schedule.every_n_weeks ?? 1
      which = s.schedule.which ?? []
      startTime = s.schedule.start_time ?? '19:00'
      endTime = s.schedule.end_time ?? '22:00'
    } else {
      recType = ''
      weekday = null
      frequency = 1
      which = []
      startTime = '19:00'
      endTime = '22:00'
    }
  }

  // Every open passes a fresh seed object, so this refires per open.
  $effect(() => {
    if (seed) applySeed(seed)
  })

  function toggleNth(value, checked) {
    which = checked ? [...which, value] : which.filter((n) => n !== value)
  }

  function markValid(fieldId) {
    invalidFields = invalidFields.filter((f) => f !== fieldId)
  }

  function save() {
    const formData = {
      thesession_id: thesessionId,
      name: name.trim(),
      path: path.trim(),
      location_name: locationName.trim() || null,
      location_phone: locationPhone.trim() || null,
      location_website: locationWebsite.trim() || null,
      city: city.trim(),
      state: stateArea.trim(),
      country: country.trim(),
      inception_date: inceptionDate || null,
      timezone,
      recurrence: recurrence.json || null,
      add_current_user: addMe,
      add_current_user_role: addMe ? addMeRole : null,
    }

    const requiredFields = [
      { id: 'sessionName', value: formData.name, label: 'Name' },
      { id: 'sessionPath', value: formData.path, label: 'Path' },
      { id: 'cityName', value: formData.city, label: 'City' },
      { id: 'stateName', value: formData.state, label: 'State' },
      { id: 'countryName', value: formData.country, label: 'Country' },
    ]
    const missing = requiredFields.filter((f) => !f.value)
    if (missing.length > 0) {
      invalidFields = missing.map((f) => f.id)
      formError = `Please fill in required fields: ${missing.map((f) => f.label).join(', ')}`
      const firstInvalid = document.getElementById(missing[0].id)
      if (firstInvalid) {
        firstInvalid.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
        firstInvalid.focus()
      }
      return
    }
    formError = ''

    saving = true
    fetch('/api/add-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          open = false
          navigate(`/sessions/${formData.path}`)
        } else {
          saving = false
          formError = data.message || data.error || 'Failed to save session'
        }
      })
      .catch((error) => {
        console.error('Error:', error)
        saving = false
        formError = 'Error saving session. Please try again.'
      })
  }
</script>

<Sheet bind:open title="Session Details">
  <form id="sessionDetailsForm" class="as-form" onsubmit={(e) => e.preventDefault()}>
    <div class="mb-3">
      <label for="sessionName">Session Name:</label>
      <input type="text" id="sessionName" required bind:value={name}
        class:is-invalid={invalidFields.includes('sessionName')}
        oninput={() => markValid('sessionName')} />
    </div>
    <div class="mb-3">
      <label for="sessionPath">Path (URL slug):</label>
      <input type="text" id="sessionPath" required bind:value={path}
        class:is-invalid={invalidFields.includes('sessionPath')}
        oninput={() => markValid('sessionPath')} />
    </div>
    <div class="mb-3">
      <label for="locationName">Location Name:</label>
      <input type="text" id="locationName" bind:value={locationName} />
    </div>
    <div class="mb-3">
      <label for="locationPhone">Location Phone:</label>
      <input type="text" id="locationPhone" bind:value={locationPhone} />
    </div>
    <div class="mb-3">
      <label for="locationWebsite">Location Website:</label>
      <input type="url" id="locationWebsite" bind:value={locationWebsite} />
    </div>
    <div class="mb-3">
      <label for="cityName">City:</label>
      <input type="text" id="cityName" required bind:value={city}
        class:is-invalid={invalidFields.includes('cityName')}
        oninput={() => markValid('cityName')} />
    </div>
    <div class="mb-3">
      <label for="stateName">State/Area:</label>
      <input type="text" id="stateName" required bind:value={stateArea}
        class:is-invalid={invalidFields.includes('stateName')}
        oninput={() => markValid('stateName')} />
    </div>
    <div class="mb-3">
      <label for="countryName">Country:</label>
      <input type="text" id="countryName" required bind:value={country}
        class:is-invalid={invalidFields.includes('countryName')}
        oninput={() => markValid('countryName')} />
    </div>
    <div class="mb-3">
      <label for="inceptionDate">Inception Date:</label>
      <input type="date" id="inceptionDate" bind:value={inceptionDate} />
    </div>
    <div class="mb-3">
      <label for="timezone">Timezone:</label>
      <select id="timezone" class="form-control" bind:value={timezone}>
        {#each timezoneOptions as tz (tz.value)}
          <option value={tz.value}>{tz.label}</option>
        {/each}
      </select>
    </div>

    <!-- Recurrence editor (collapsible summary/edit) -->
    <div class="mb-3">
      <label>Schedule:</label>
      <div id="recurrence-section" class="recurrence-section" class:expanded={recExpanded}>
        <div
          id="recurrence-summary"
          class="recurrence-summary"
          role="button"
          tabindex="0"
          onclick={() => (recExpanded = !recExpanded)}
          onkeydown={(e) => e.key === 'Enter' && (recExpanded = !recExpanded)}>
          <span id="recurrence-summary-text">{recurrence.summary}</span>
          <span class="recurrence-toggle-icon">&#9662;</span>
        </div>

        {#if recExpanded}
          <div id="recurrence-edit" class="recurrence-edit">
            <div class="mb-2">
              <label class="form-label small" for="recurrence-type">Pattern Type:</label>
              <select id="recurrence-type" class="form-control" bind:value={recType}>
                <option value="">No schedule</option>
                <option value="weekly">Weekly</option>
                <option value="monthly_nth_weekday">Monthly (Nth Weekday)</option>
              </select>
            </div>

            {#if recType}
              <div id="recurrence-options">
                <div class="mb-2">
                  <span class="form-label small">Day:</span>
                  <Seg
                    options={WEEKDAYS}
                    value={weekday}
                    onSelect={(id) => (weekday = id)}
                    idAttr="data-weekday"
                    styled={false}
                    segClass="weekday-buttons"
                    optClass="weekday-btn"
                    role="group"
                    aria-label="Day of week" />
                </div>

                {#if recType === 'weekly'}
                  <div id="weekly-options" class="mb-2">
                    <label class="form-label small" for="recurrence-frequency">Frequency:</label>
                    <select
                      id="recurrence-frequency"
                      class="form-control"
                      value={String(frequency)}
                      onchange={(e) => (frequency = parseInt(e.target.value))}>
                      <option value="1">Every week</option>
                      <option value="2">Every 2 weeks</option>
                      <option value="3">Every 3 weeks</option>
                      <option value="4">Every 4 weeks</option>
                    </select>
                  </div>
                {:else if recType === 'monthly_nth_weekday'}
                  <div id="monthly-options" class="mb-2">
                    <span class="form-label small">Which occurrences:</span>
                    <div class="nth-checkboxes">
                      {#each NTH_OPTIONS as nth (nth.value)}
                        <label>
                          <input
                            type="checkbox"
                            class="nth-checkbox"
                            value={nth.value}
                            checked={which.includes(nth.value)}
                            onchange={(e) => toggleNth(nth.value, e.target.checked)} />
                          {nth.label}
                        </label>
                      {/each}
                    </div>
                  </div>
                {/if}

                <div class="rec-times">
                  <div>
                    <label class="form-label small" for="recurrence-start">Start:</label>
                    <input type="time" id="recurrence-start" class="form-control" bind:value={startTime} />
                  </div>
                  <div>
                    <label class="form-label small" for="recurrence-end">End:</label>
                    <input type="time" id="recurrence-end" class="form-control" bind:value={endTime} />
                  </div>
                </div>
              </div>
            {/if}

            <button type="button" class="rec-done-btn" onclick={() => (recExpanded = false)}>Done</button>
          </div>
        {/if}

        {#if unparsedText}
          <div id="recurrence-unparsed" class="recurrence-unparsed">{unparsedText}</div>
        {/if}
      </div>
    </div>

    <!-- Add current user -->
    <div class="mb-3">
      <div class="add-user-control">
        <label class="checkbox-label">
          <input type="checkbox" id="addCurrentUser" bind:checked={addMe} />
          Add me as
        </label>
        <select id="addCurrentUserRole" class="form-control form-control-inline" disabled={!addMe} bind:value={addMeRole}>
          <option value="member">a member</option>
          <option value="regular">a regular</option>
          <option value="admin">an admin</option>
        </select>
      </div>
    </div>
  </form>

  {#snippet footer()}
    <div class="session-sheet-actions">
      {#if formError}
        <div class="field-error" role="alert">{formError}</div>
      {/if}
      <button type="button" class="btn-save-session" id="saveSessionBtn" disabled={saving} onclick={save}>
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  {/snippet}
</Sheet>
