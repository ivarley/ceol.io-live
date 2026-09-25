<script>
  // Stage 2 of adding a session: review what came from thesession.org (or fill
  // in a session that isn't there), then commit via POST /api/add-session.
  //
  // This was one flat scroll of twenty label-above-input pairs, in source order,
  // where "Location Phone" carried the same weight as the session's name. It is
  // now grouped-table sections — label left, value right — with everything a
  // person creating their weekly session does not need folded behind Advanced.
  // The defaults back there are already correct; the 60-minute active window in
  // particular is a setting almost nobody changes and nobody new understands.
  //
  // The field ids are unchanged on purpose. The layout is a rewrite, the
  // behaviour is not, and keeping #sessionName, #sessionPathValue, #editPathBtn
  // and the rest means the tests that pinned the behaviour still pin it.
  //
  // Save is in the footer rather than a header Done: a failed save has to keep
  // the sheet open for another try, which is the kit's rule for server commits.
  import { tick } from 'svelte'
  import { Sheet, Seg } from '../lib/index.js'
  import '../lib/grouped.css'
  import { parseThesessionSessionId } from '../shared/parse.js'
  import { normalizeSessionPath } from '../shared/sessionpath.js'
  import { generatePath, summarizeRecurrence } from './logic.js'

  let {
    open = $bindable(false),
    seed = null, // a NEW object per open — fields reset from it
    timezoneOptions = [],
    addMeDefault = true, // false when ?acu=false said not to
    back = null, // label for the back chevron; null => a Cancel button
    onCancel = () => {},
    navigate = (url) => window.location.assign(url),
  } = $props()

  // ---- form fields (reset from each new seed) --------------------------------
  let thesessionId = $state('')
  let name = $state('')
  let locationName = $state('')
  let locationPhone = $state('')
  let locationWebsite = $state('')
  let city = $state('')
  let stateArea = $state('')
  let country = $state('')
  let inceptionDate = $state('')
  let timezone = $state('America/Chicago')
  // Editable here as well as on the admin page — the import seeds thesession_id, but a
  // hand-added session can be linked up now instead of needing SQL later.
  const thesessionRef = $derived(parseThesessionSessionId(thesessionId))
  let sessionType = $state('regular')
  let bufferBefore = $state('60')
  let bufferAfter = $state('60')
  let addMe = $state(true)
  let addMeRole = $state('admin')
  // People-tracking flags (spec 039): all on by default — this is opt-OUT. Set-starters
  // require attendance, so unchecking attendance disables and clears starters.
  let showPeopleList = $state(true)
  let trackAttendance = $state(true)
  let trackSetStarters = $state(true)
  $effect(() => {
    if (!trackAttendance) trackSetStarters = false
  })
  let unparsedText = $state('')

  // The timezone list arrives with the sheet's payload, which may still be in
  // flight. Without this the select would render empty and read as "no timezone",
  // when in fact one is chosen — so the current value is always an option.
  const tzOptions = $derived(
    timezoneOptions.some((t) => t.value === timezone)
      ? timezoneOptions
      : [{ value: timezone, label: timezone }, ...timezoneOptions]
  )

  // ---- path: generated from name + city, overridable --------------------------
  // The path is a URL, not a field anyone should have to invent. Presenting it as
  // a bare required input is how a production session ended up with a path of "."
  // — non-empty, so it validated, but it resolved to nothing and stranded the
  // session. So: derive it, show it, and make overriding it a deliberate act.
  let manualPath = $state('')
  let pathIsManual = $state(false)

  const generatedPath = $derived(generatePath(city, name))
  const effectivePath = $derived(pathIsManual ? manualPath.trim() : generatedPath)

  async function startEditingPath() {
    manualPath = effectivePath
    pathIsManual = true
    await tick()
    document.getElementById('sessionPath')?.focus()
  }

  function useGeneratedPath() {
    pathIsManual = false
    manualPath = ''
    markValid('sessionPath')
  }

  // ---- disclosure -------------------------------------------------------------
  let advancedOpen = $state(false)
  let recExpanded = $state(false)

  // ---- recurrence editor ------------------------------------------------------
  let recType = $state('')
  let weekday = $state(null)
  let frequency = $state(1)
  let which = $state([])
  let startTime = $state('19:00')
  let endTime = $state('22:00')

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

  // Everything that lives behind the Advanced disclosure. An error on one of these
  // has to open it, or the message points at a control that isn't on screen.
  const ADVANCED_FIELDS = [
    'sessionPath',
    'thesessionId',
    'activeBufferBefore',
    'activeBufferAfter',
  ]

  function applySeed(s) {
    thesessionId = s.thesession_id ?? ''
    name = s.name ?? ''
    locationName = s.location_name ?? ''
    locationPhone = s.location_phone ?? ''
    locationWebsite = s.location_website ?? ''
    city = s.city ?? ''
    stateArea = s.state ?? ''
    country = s.country ?? ''
    inceptionDate = s.inception_date ?? ''
    timezone = s.timezone ?? 'America/Chicago'
    sessionType = s.session_type ?? 'regular'
    bufferBefore = String(s.active_buffer_minutes_before ?? 60)
    bufferAfter = String(s.active_buffer_minutes_after ?? 60)
    addMe = addMeDefault
    addMeRole = 'admin'
    showPeopleList = true
    trackAttendance = true
    trackSetStarters = true
    unparsedText = s.unparsedText ?? ''
    // The import flow seeds exactly what generatePath would produce, so it stays
    // in generated mode; a seed that differs is a genuine override.
    const seededPath = (s.path ?? '').trim()
    pathIsManual = Boolean(seededPath) && seededPath !== generatePath(s.city ?? '', s.name ?? '')
    manualPath = seededPath
    invalidFields = []
    formError = ''
    saving = false
    advancedOpen = false
    // An import whose schedule text could not be parsed has something to say about
    // it, and it says it next to the schedule — so that section starts open.
    recExpanded = Boolean(s.unparsedText)
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

  async function focusField(id) {
    if (ADVANCED_FIELDS.includes(id)) advancedOpen = true
    await tick()
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
      el.focus()
    }
  }

  async function save() {
    const formData = {
      thesession_id: thesessionId,
      name: name.trim(),
      path: effectivePath,
      location_name: locationName.trim() || null,
      location_phone: locationPhone.trim() || null,
      location_website: locationWebsite.trim() || null,
      city: city.trim(),
      state: stateArea.trim(),
      country: country.trim(),
      inception_date: inceptionDate || null,
      timezone,
      session_type: sessionType,
      active_buffer_minutes_before: parseInt(bufferBefore, 10),
      active_buffer_minutes_after: parseInt(bufferAfter, 10),
      recurrence: recurrence.json || null,
      add_current_user: addMe,
      add_current_user_role: addMe ? addMeRole : null,
      show_people_list: showPeopleList,
      track_attendance: trackAttendance,
      track_set_starters: trackSetStarters && trackAttendance,
    }

    // Path isn't listed: it's generated from name + city, so those are what a
    // person actually has to supply.
    const requiredFields = [
      { id: 'sessionName', value: formData.name, label: 'Name' },
      { id: 'cityName', value: formData.city, label: 'City' },
      { id: 'stateName', value: formData.state, label: 'State' },
      { id: 'countryName', value: formData.country, label: 'Country' },
    ]
    const missing = requiredFields.filter((f) => !f.value)
    if (missing.length > 0) {
      invalidFields = missing.map((f) => f.id)
      formError = `Please fill in required fields: ${missing.map((f) => f.label).join(', ')}`
      await focusField(missing[0].id)
      return
    }

    // The path becomes the session's URL — a non-empty but unusable one (a bare
    // "/", a ".", a pasted zero-width space) would strand the session with no
    // reachable admin screen. Server enforces the same rule.
    const { error: pathError } = normalizeSessionPath(formData.path)
    if (pathError) {
      invalidFields = ['sessionPath']
      formError = pathError
      // A generated path can be unusable when the name and city are all
      // punctuation or non-Latin script — there's nothing to slugify. Retyping the
      // name won't help, so hand over the text box.
      advancedOpen = true
      if (!pathIsManual) await startEditingPath()
      await focusField('sessionPath')
      return
    }
    // A mistyped link (or a pasted TUNE url) is worth catching before the round trip.
    if (thesessionId.trim() && thesessionRef == null) {
      invalidFields = ['thesessionId']
      formError = 'Enter a thesession.org session URL (thesession.org/sessions/1234) or numeric ID'
      await focusField('thesessionId')
      return
    }
    for (const [id, minutes, label] of [
      ['activeBufferBefore', bufferBefore, 'Minutes before'],
      ['activeBufferAfter', bufferAfter, 'Minutes after'],
    ]) {
      if (!/^\d+$/.test(String(minutes).trim())) {
        invalidFields = [id]
        formError = `${label} must be a whole number of minutes`
        await focusField(id)
        return
      }
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

<Sheet bind:open title="Session Details" {back} {onCancel}>
  <form id="sessionDetailsForm" class="as-form" onsubmit={(e) => e.preventDefault()}>
    <!-- What the session is. Name is the only thing here anyone must supply. -->
    <div class="kit-group">
      <div class="kit-field">
        <label for="sessionName">Name</label>
        <input type="text" id="sessionName" required bind:value={name} placeholder="Required"
          class:is-invalid={invalidFields.includes('sessionName')}
          oninput={() => markValid('sessionName')} />
      </div>
      <div class="kit-field">
        <label for="locationName">Venue</label>
        <input type="text" id="locationName" bind:value={locationName} placeholder="Pub or hall" />
      </div>
    </div>

    <h3 class="kit-group-head">Where</h3>
    <div class="kit-group">
      <div class="kit-field">
        <label for="cityName">City</label>
        <input type="text" id="cityName" required bind:value={city} placeholder="Required"
          class:is-invalid={invalidFields.includes('cityName')}
          oninput={() => markValid('cityName')} />
      </div>
      <div class="kit-field">
        <label for="stateName">State / area</label>
        <input type="text" id="stateName" required bind:value={stateArea} placeholder="Required"
          class:is-invalid={invalidFields.includes('stateName')}
          oninput={() => markValid('stateName')} />
      </div>
      <div class="kit-field">
        <label for="countryName">Country</label>
        <input type="text" id="countryName" required bind:value={country} placeholder="Required"
          class:is-invalid={invalidFields.includes('countryName')}
          oninput={() => markValid('countryName')} />
      </div>
      <div class="kit-field">
        <label for="timezone">Time zone</label>
        <select id="timezone" bind:value={timezone}>
          {#each tzOptions as tz (tz.value)}
            <option value={tz.value}>{tz.label}</option>
          {/each}
        </select>
      </div>
    </div>

    <!-- When it meets. This is the point of the app, so it sits on the main path
         rather than in Advanced, and the summary reads as a sentence. -->
    <h3 class="kit-group-head">When</h3>
    <div class="kit-group">
      <div id="recurrence-section" class="recurrence-section" class:expanded={recExpanded}>
        <button
          type="button"
          id="recurrence-summary"
          class="kit-field kit-disclosure"
          aria-expanded={recExpanded}
          onclick={() => (recExpanded = !recExpanded)}>
          <span class="kit-field-label">Schedule</span>
          <span id="recurrence-summary-text" class="kit-field-value">{recurrence.summary}</span>
          <span class="kit-chev" class:open={recExpanded} aria-hidden="true">›</span>
        </button>

        {#if recExpanded}
          <div id="recurrence-edit" class="recurrence-edit">
            <div class="as-stack">
              <label class="as-sub-label" for="recurrence-type">Repeats</label>
              <select id="recurrence-type" class="as-wide" bind:value={recType}>
                <option value="">No schedule</option>
                <option value="weekly">Weekly</option>
                <option value="monthly_nth_weekday">Monthly (Nth weekday)</option>
              </select>
            </div>

            {#if recType}
              <div id="recurrence-options">
                <div class="as-stack">
                  <span class="as-sub-label">Day</span>
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
                  <div id="weekly-options" class="as-stack">
                    <label class="as-sub-label" for="recurrence-frequency">Frequency</label>
                    <select
                      id="recurrence-frequency"
                      class="as-wide"
                      value={String(frequency)}
                      onchange={(e) => (frequency = parseInt(e.target.value))}>
                      <option value="1">Every week</option>
                      <option value="2">Every 2 weeks</option>
                      <option value="3">Every 3 weeks</option>
                      <option value="4">Every 4 weeks</option>
                    </select>
                  </div>
                {:else if recType === 'monthly_nth_weekday'}
                  <div id="monthly-options" class="as-stack">
                    <span class="as-sub-label">Which occurrences</span>
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
                  <div class="as-stack">
                    <label class="as-sub-label" for="recurrence-start">Start</label>
                    <input type="time" id="recurrence-start" bind:value={startTime} />
                  </div>
                  <div class="as-stack">
                    <label class="as-sub-label" for="recurrence-end">End</label>
                    <input type="time" id="recurrence-end" bind:value={endTime} />
                  </div>
                </div>
              </div>
            {/if}
          </div>
        {/if}

        {#if unparsedText}
          <div id="recurrence-unparsed" class="recurrence-unparsed">{unparsedText}</div>
        {/if}
      </div>
    </div>

    <!-- Your own relationship to it. On by default, and the one thing here that
         decides whether you can administer the session you just created. -->
    <h3 class="kit-group-head">You</h3>
    <div class="kit-group">
      <div class="kit-field add-user-control">
        <label class="kit-check-label" for="addCurrentUser">
          <input type="checkbox" id="addCurrentUser" bind:checked={addMe} />
          Add me as
        </label>
        <select id="addCurrentUserRole" disabled={!addMe} bind:value={addMeRole}>
          <option value="member">a member</option>
          <option value="regular">a regular</option>
          <option value="admin">an admin</option>
        </select>
      </div>
    </div>

    <!-- Everything whose default is already right. Folded away so the main path is
         the nine fields above rather than twenty. -->
    <div class="kit-group as-advanced-group">
      <button
        type="button"
        id="advanced-toggle"
        class="kit-field kit-disclosure"
        aria-expanded={advancedOpen}
        aria-controls="advanced-section"
        onclick={() => (advancedOpen = !advancedOpen)}>
        <span class="kit-field-label">Advanced</span>
        <span class="kit-chev" class:open={advancedOpen} aria-hidden="true">›</span>
      </button>
    </div>

    {#if advancedOpen}
      <div id="advanced-section">
        <div class="kit-group">
          <!-- Sits after name + city because it's generated from them. -->
          <div class="kit-field as-field-path">
            <span class="kit-field-label" id="sessionPathLabel">Web address</span>
            {#if pathIsManual}
              <span class="as-path-edit">
                <input type="text" id="sessionPath" required bind:value={manualPath}
                  aria-labelledby="sessionPathLabel"
                  class:is-invalid={invalidFields.includes('sessionPath')}
                  oninput={() => markValid('sessionPath')} />
                {#if generatedPath && manualPath.trim() !== generatedPath}
                  <button type="button" class="as-path-action" id="useGeneratedPathBtn"
                    onclick={useGeneratedPath}>Use suggested</button>
                {/if}
              </span>
            {:else}
              <span class="as-path-display" class:is-invalid={invalidFields.includes('sessionPath')}>
                {#if generatedPath}
                  <code id="sessionPathValue">/sessions/{generatedPath}</code>
                {:else}
                  <span class="as-path-empty" id="sessionPathValue">Enter a name and city first</span>
                {/if}
                <button type="button" class="as-path-action" id="editPathBtn"
                  onclick={startEditingPath}>Edit</button>
              </span>
            {/if}
          </div>
          <div class="kit-field">
            <label for="locationPhone">Venue phone</label>
            <input type="text" id="locationPhone" bind:value={locationPhone} />
          </div>
          <div class="kit-field">
            <label for="locationWebsite">Venue website</label>
            <input type="url" id="locationWebsite" bind:value={locationWebsite} />
          </div>
          <div class="kit-field">
            <label for="inceptionDate">First met</label>
            <input type="date" id="inceptionDate" bind:value={inceptionDate} />
          </div>
        </div>

        <div class="kit-group">
          <!-- Seeded by the import; editable so a hand-added session can be linked too. -->
          <div class="kit-field">
            <label for="thesessionId">thesession.org</label>
            <input type="text" id="thesessionId" bind:value={thesessionId}
              placeholder="ID or link"
              class:is-invalid={invalidFields.includes('thesessionId')}
              oninput={() => markValid('thesessionId')} />
          </div>
          <p class="kit-field-help">Links this session to its listing on thesession.org.</p>
        </div>

        <div class="kit-group">
          <div class="kit-field">
            <label for="sessionType">Type</label>
            <select id="sessionType" bind:value={sessionType}>
              <option value="regular">Regular (recurring)</option>
              <option value="festival">Festival</option>
            </select>
          </div>
          <p class="kit-field-help">
            {#if sessionType === 'festival'}
              Runs between its first and last dates instead of recurring; its sessions are listed by day and may overlap.
            {:else}
              Recurs on the schedule above.
            {/if}
          </p>
        </div>

        <div class="kit-group">
          <div class="kit-field as-buffer-field">
            <span class="kit-field-label" id="activeWindowLabel">Active window</span>
            <span class="as-buffer-row" aria-labelledby="activeWindowLabel">
              <input type="number" id="activeBufferBefore" min="0" max="1440" bind:value={bufferBefore}
                aria-label="Minutes before the session starts"
                class:is-invalid={invalidFields.includes('activeBufferBefore')}
                oninput={() => markValid('activeBufferBefore')} />
              <span>before</span>
              <input type="number" id="activeBufferAfter" min="0" max="1440" bind:value={bufferAfter}
                aria-label="Minutes after the session ends"
                class:is-invalid={invalidFields.includes('activeBufferAfter')}
                oninput={() => markValid('activeBufferAfter')} />
              <span>after</span>
            </span>
          </div>
          <p class="kit-field-help">Minutes either side of the scheduled time that count as "happening now".</p>
        </div>

        <!-- People tracking (spec 039): all on by default; the creator can opt out. -->
        <h3 class="kit-group-head">People</h3>
        <div class="kit-group people-tracking-control">
          <div class="kit-check-field">
            <label class="kit-check-label" for="showPeopleList">
              <input type="checkbox" id="showPeopleList" bind:checked={showPeopleList} />
              Show a members list
            </label>
            <small class="people-tracking-help">Lets session members see who else plays here.</small>
          </div>
          <div class="kit-check-field">
            <label class="kit-check-label" for="trackAttendance">
              <input type="checkbox" id="trackAttendance" bind:checked={trackAttendance} />
              Record attendance
            </label>
            <small class="people-tracking-help">Record who attends each session. Visible only to members.</small>
          </div>
          <div class="kit-check-field">
            <label class="kit-check-label" for="trackSetStarters">
              <input type="checkbox" id="trackSetStarters" bind:checked={trackSetStarters} disabled={!trackAttendance} />
              Record set starters
            </label>
            <small class="people-tracking-help">
              Record who started each set. Visible only to members.{#if !trackAttendance} Requires attendance.{/if}
            </small>
          </div>
        </div>
      </div>
    {/if}
  </form>

  {#snippet footer()}
    <div class="session-sheet-actions">
      {#if formError}
        <div class="field-error" role="alert">{formError}</div>
      {/if}
      <button type="button" class="btn-save-session" id="saveSessionBtn" disabled={saving} onclick={save}>
        {saving ? 'Saving…' : 'Create session'}
      </button>
    </div>
  {/snippet}
</Sheet>

<style>
  /* Grouped-table form, the shape iOS uses for settings and for "review this
     before you commit": a section title, then an inset card whose rows are
     label-left / value-right. The point is that a row reads as a sentence at a
     glance — "City  Austin" — instead of as a label hovering over an empty box,
     which is what made a twenty-field scroll unreadable.


  .as-advanced-group .as-disclosure {
    border-bottom: none;
  }

  /* ---- the expanded editors --------------------------------------------------
     Inside a disclosure the label-left/value-right shape stops working: a weekday
     picker and a time range need the full width, so these rows stack instead. */

  .as-stack {
    display: flex;
    flex-direction: column;
    gap: var(--sp-1, 4px);
    padding: var(--sp-2, 8px) var(--sp-3, 12px);
  }

  .as-sub-label {
    font-size: 0.78rem;
    color: var(--secondary-text, #888);
  }

  .as-stack :global(select),
  .as-stack :global(input[type='time']) {
    width: 100%;
    padding: 7px 10px;
    font: inherit;
    color: var(--text-color);
    background: var(--bg-color, #1a1a1a);
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r-sm, 4px);
  }

  .recurrence-edit {
    padding-bottom: var(--sp-2, 8px);
    border-top: 1px solid var(--bg-color, #1a1a1a);
  }

  .rec-times {
    display: flex;
    gap: var(--sp-2, 8px);
  }

  .rec-times > :global(.as-stack) {
    flex: 1;
  }

  /* Seg renders these, so they are outside this component's scope. */
  :global(.weekday-buttons) {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  :global(.weekday-btn) {
    flex: 1 1 auto;
    min-width: 38px;
    padding: 7px 4px;
    font: inherit;
    font-size: 0.8rem;
    color: var(--text-color);
    background: var(--bg-color, #1a1a1a);
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r-sm, 4px);
    cursor: pointer;
  }

  :global(.weekday-btn:hover) {
    background: var(--hover-bg, #3d3d3d);
  }

  :global(.weekday-btn.active) {
    background: var(--primary-fill, #4a8049);
    border-color: var(--primary-fill, #4a8049);
    color: #fff;
  }

  .nth-checkboxes {
    display: flex;
    gap: var(--sp-3, 12px);
    flex-wrap: wrap;
  }

  .nth-checkboxes :global(label) {
    display: flex;
    align-items: center;
    gap: 4px;
    margin: 0;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .recurrence-unparsed {
    padding: var(--sp-2, 8px) var(--sp-3, 12px);
    font-size: 0.78rem;
    font-style: italic;
    color: var(--secondary-text, #888);
    border-top: 1px solid var(--bg-color, #1a1a1a);
  }

  /* ---- the generated web address ---------------------------------------------
     Still a result rather than a field: derived from name + city, shown read-only,
     with Edit to opt into typing one. A bare required input is what produced a
     production session whose path was "." — non-empty, so it validated, and
     unreachable as a URL. */

  .as-field-path {
    flex-wrap: wrap;
  }

  .as-path-display,
  .as-path-edit {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--sp-2, 8px);
  }

  .as-path-display code {
    font-size: 0.82rem;
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .as-path-display.is-invalid code {
    color: var(--danger, #dc3545);
  }

  .as-path-empty {
    font-size: 0.82rem;
    color: var(--disabled-text, #888);
  }

  .people-tracking-help {
    /* Lines up under the label text, past the checkbox. */
    padding-left: calc(17px + var(--sp-2, 8px));
    font-size: 0.78rem;
    color: var(--secondary-text, #888);
  }

  /* "Add me as [an admin]" is one sentence, so the select sits next to the
     checkbox label rather than in the value column. */
  .add-user-control .kit-check-label {
    flex: 0 0 auto;
    width: auto;
    max-width: none;
  }

  .add-user-control :global(select) {
    flex: 0 1 auto;
    text-align: left;
    text-align-last: left;
  }

  /* ---- footer ---------------------------------------------------------------- */

  .session-sheet-actions {
    display: flex;
    flex-direction: column;
    gap: var(--sp-2, 8px);
  }

  .session-sheet-actions .field-error {
    font-size: 0.82rem;
    color: var(--danger, #dc3545);
  }

  /* Full width: it is the only action down here, and the one the whole sheet is
     for. It also no longer says "Save", which said nothing about what happens —
     it creates a session and takes you to it. */
  .btn-save-session {
    width: 100%;
    padding: 12px 16px;
    font: inherit;
    font-weight: 600;
    color: #fff;
    background: var(--primary-fill, #4a8049);
    border: none;
    border-radius: var(--r, 8px);
    cursor: pointer;
  }

  .btn-save-session:hover {
    opacity: 0.92;
  }

  .btn-save-session:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
