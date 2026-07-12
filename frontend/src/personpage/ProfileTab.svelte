<script>
  // Profile tab: person + account cards with a display/edit mode toggle, the live
  // per-instrument profile editor (saves immediately, decoupled from the profile
  // Save button), admin-only verify-email / beta-logging / danger-zone controls.
  let { person, user, isUserProfile, personId, timezoneOptions = [], canonicalInstruments = [] } = $props()

  import { Dialog, Sheet, toast } from '../lib/index.js'

  let editMode = $state(false)

  // --- Person / user form fields (edit mode) --------------------------------
  let firstName = $state(person.first_name || '')
  let lastName = $state(person.last_name || '')
  let email = $state(person.email || '')
  let smsNumber = $state(person.sms_number || '')
  let city = $state(person.city || '')
  let stateField = $state(person.state || '')
  let country = $state(person.country || '')
  let thesessionUserId = $state(person.thesession_user_id != null ? String(person.thesession_user_id) : '')

  let username = $state(user ? user.username || '' : '')
  let userEmail = $state(user ? user.user_email || '' : '')
  let timezone = $state(user ? user.timezone : null)
  let isActiveChecked = $state(user ? !!user.is_active : false)
  let receiveUpdateEmails = $state(user ? !!user.receive_update_emails : false)

  const originalUsername = user ? user.username || '' : ''
  let usernameWarning = $state('')

  // "YYYY-MM-DD HH:MM" from an ISO timestamp (legacy strftime('%Y-%m-%d %H:%M')).
  const fmtDateTime = (iso) => (iso ? iso.slice(0, 16).replace('T', ' ') : null)

  function toggleEditMode(isEdit) {
    editMode = isEdit
    if (isEdit) {
      loadProfileInstruments()
    } else {
      usernameWarning = ''
    }
  }

  function checkUsernameAvailability(value) {
    fetch('/api/check-username-availability', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: value, current_user_id: user ? user.user_id : null }),
    })
      .then((response) => response.json())
      .then((data) => {
        usernameWarning = data.available ? '' : data.message
      })
      .catch((error) => {
        console.error('Error checking username:', error)
      })
  }

  function onUsernameBlur() {
    const v = username
    if (v !== originalUsername && v.trim() !== '') {
      checkUsernameAvailability(v.trim())
    } else {
      usernameWarning = ''
    }
  }

  function saveChanges() {
    const currentUsername = user ? username.trim() : originalUsername
    if (usernameWarning && currentUsername !== originalUsername) {
      toast('Please fix the username issue before saving.', 'error')
      return
    }

    const formData = { person_id: personId, person: {}, user: {} }

    // Instruments are managed live (immediate save) by the instrument editor, so
    // they are NOT part of this form save.
    formData.person = {
      first_name: firstName.trim() || null,
      last_name: lastName.trim() || null,
      email: email.trim() || null,
      sms_number: smsNumber.trim() || null,
      city: city.trim() || null,
      state: stateField.trim() || null,
      country: country.trim() || null,
      thesession_user_id: String(thesessionUserId).trim() || null,
    }

    if (user) {
      formData.user = {
        username: username.trim() || null,
        user_email: userEmail.trim() || null,
        timezone: timezone || null,
        user_id: user.user_id,
      }
      if (!isUserProfile) {
        formData.user.is_active = isActiveChecked
      } else {
        formData.user.receive_update_emails = receiveUpdateEmails
      }
    }

    fetch(`/api/person/${personId}/update`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) {
          throw new Error(data.message || 'Failed to update person data')
        }
        // Instruments already saved live; just reload to show updated profile.
        sessionStorage.setItem('personSavedMessage', 'Profile updated successfully')
        window.location.reload()
      })
      .catch((error) => {
        console.error('Error saving changes:', error)
        toast('Error saving changes. Please try again.', 'error')
      })
  }

  // --- Verify email (admin flavor) -------------------------------------------
  let verifyingEmail = $state(false)
  let verifyBtnLabel = $state('Verify Email')

  // Verifying is a decision -> kit Dialog with an explicit verb (spec 035).
  let verifyConfirmOpen = $state(false)

  function verifyEmail() {
    verifyingEmail = true
    verifyBtnLabel = 'Verifying...'
    fetch(`/api/admin/user/${user.user_id}/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          toast(data.message, 'success')
          setTimeout(() => {
            window.location.reload()
          }, 1000)
        } else {
          toast('Error: ' + data.message, 'error')
          verifyingEmail = false
          verifyBtnLabel = 'Verify Email'
        }
      })
      .catch((error) => {
        toast('Error verifying email: ' + error.message, 'error')
        verifyingEmail = false
        verifyBtnLabel = 'Verify Email'
      })
  }

  // --- Beta live-editor toggle (system admin only) ----------------------------
  let betaBusy = $state(false)

  function toggleBetaLogging() {
    const enable = !user.beta_live_logging
    betaBusy = true
    fetch(`/api/admin/users/${user.user_id}/beta-logging`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: enable }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          toast('Live editor (beta) ' + (enable ? 'enabled' : 'disabled') + ' for this user.', 'success')
          setTimeout(() => window.location.reload(), 800)
        } else {
          toast('Error: ' + (data.error || 'failed'), 'error')
          betaBusy = false
        }
      })
      .catch((err) => {
        toast('Error: ' + err.message, 'error')
        betaBusy = false
      })
  }

  // --- Live instrument editor (changes save immediately) ----------------------
  let profileInstruments = $state([]) // [{instrument, is_auto, removal_loss_count}]
  let configOpen = $state(false) // the per-instrument config sheet
  let configInstrument = $state(null) // instrument name open in the config sheet
  let removeConfirmOpen = $state(false) // the data-loss removal Dialog
  let pendingRemoveInstrument = $state(null) // instrument awaiting the data-loss confirmation
  let removeWarnParts = $state(null) // {name, tunesText}
  let typeaheadValue = $state('')
  let typeaheadOpen = $state(false)
  let typeaheadWrap = $state(null)

  function loadProfileInstruments() {
    fetch(`/api/person/${personId}/instruments`)
      .then((r) => r.json())
      .then((d) => {
        profileInstruments = d && d.instruments ? d.instruments : []
      })
      .catch(() => {
        profileInstruments = []
      })
  }

  function saveInstrumentList() {
    // PUT the full name list; the server diffs (so is_auto on kept instruments is
    // preserved) and normalizes casing/aliases.
    return fetch(`/api/person/${personId}/instruments`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruments: profileInstruments.map((i) => i.instrument) }),
    }).then((r) => r.json())
  }

  function addInstrumentToProfile(name) {
    name = (name || '').trim()
    if (!name) return
    if (profileInstruments.some((i) => i.instrument.toLowerCase() === name.toLowerCase())) {
      typeaheadOpen = false
      return // already on the list
    }
    profileInstruments = [...profileInstruments, { instrument: name, is_auto: true }].sort((a, b) =>
      a.instrument.localeCompare(b.instrument)
    )
    typeaheadValue = ''
    typeaheadOpen = false
    saveInstrumentList().then(loadProfileInstruments) // reload to get canonical casing
  }

  // Type-ahead against the canonical list, with an "other" (free-text) escape hatch.
  const typeaheadOptions = $derived.by(() => {
    const q = typeaheadValue.trim().toLowerCase()
    const have = new Set(profileInstruments.map((i) => i.instrument.toLowerCase()))
    const matches = canonicalInstruments.filter((c) => c.toLowerCase().includes(q) && !have.has(c.toLowerCase()))
    const opts = matches.map((c) => ({ value: c, label: c }))
    // "Other" escape hatch: offer to add the typed text if it isn't an exact canonical match
    if (q && !canonicalInstruments.some((c) => c.toLowerCase() === q) && !have.has(q)) {
      opts.push({ value: typeaheadValue.trim(), label: `Add "${typeaheadValue.trim()}"` })
    }
    return opts
  })

  function updateTypeahead() {
    typeaheadOpen = typeaheadOptions.length > 0
  }

  function onTypeaheadKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (typeaheadValue.trim()) addInstrumentToProfile(typeaheadValue.trim())
    } else if (e.key === 'Escape') {
      typeaheadOpen = false
    }
  }

  function onDocumentClick(e) {
    if (typeaheadWrap && !typeaheadWrap.contains(e.target)) typeaheadOpen = false
  }

  // Config sheet (auto/manual + remove).
  function openInstrumentConfig(name) {
    configInstrument = name
    configOpen = true
  }
  function closeInstrumentConfig() {
    configOpen = false
  }
  const configInst = $derived(profileInstruments.find((i) => i.instrument === configInstrument) || null)

  function setInstrumentAutoFromModal(isAuto) {
    if (!configInstrument) return
    const inst = profileInstruments.find((i) => i.instrument === configInstrument)
    if (inst) inst.is_auto = isAuto
    profileInstruments = [...profileInstruments]
    fetch(`/api/person/${personId}/instrument-auto`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instrument: configInstrument, is_auto: isAuto }),
      // Reload either way: on failure to revert, on success to refresh each
      // instrument's removal_loss_count (auto vs manual changes what a removal loses).
    })
      .then((r) => r.json())
      .then(() => loadProfileInstruments())
  }

  function removeInstrumentFromProfile() {
    if (!configInstrument) return
    const inst = profileInstruments.find((i) => i.instrument === configInstrument)
    const loss = inst ? inst.removal_loss_count || 0 : 0
    if (loss > 0) {
      // Removing this instrument would delete per-tune status that re-adding it on
      // Auto wouldn't bring back — warn before losing it.
      pendingRemoveInstrument = configInstrument
      removeWarnParts = {
        name: configInstrument,
        tunesText: loss === 1 ? '1 tune' : loss + ' tunes',
      }
      removeConfirmOpen = true
      closeInstrumentConfig()
      return
    }
    doRemoveInstrument(configInstrument)
    closeInstrumentConfig()
  }

  function doRemoveInstrument(name) {
    profileInstruments = profileInstruments.filter((i) => i.instrument !== name)
    saveInstrumentList().then(loadProfileInstruments)
  }

  function confirmRemoveInstrument() {
    if (pendingRemoveInstrument) doRemoveInstrument(pendingRemoveInstrument)
    cancelRemoveInstrument()
  }

  function cancelRemoveInstrument() {
    pendingRemoveInstrument = null
    removeWarnParts = null
    removeConfirmOpen = false
  }

  // --- Deactivate/Reactivate person (admin only) ------------------------------
  let toggleActiveStatusHtml = $state(null) // null hidden; else {kind, text}

  // Deactivate/reactivate is a decision -> kit Dialog; deactivating is the
  // destructive flavor.
  let toggleActiveOpen = $state(false)
  let toggleActiveTarget = $state(null) // true = reactivate, false = deactivate

  function askTogglePersonActive(active) {
    toggleActiveTarget = active
    toggleActiveOpen = true
  }

  function togglePersonActive(active) {
    toggleActiveStatusHtml = { kind: 'info', text: 'Processing...' }

    fetch(`/api/admin/person/${personId}/active`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: active }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          toast(data.message, 'success')
          // Reload page to reflect new state
          setTimeout(() => {
            window.location.reload()
          }, 1000)
        } else {
          toggleActiveStatusHtml = { kind: 'danger', text: data.message }
        }
      })
      .catch((error) => {
        console.error('Error toggling person active status:', error)
        toggleActiveStatusHtml = { kind: 'danger', text: 'Error: ' + error.message }
      })
  }
</script>

<svelte:document onclick={onDocumentClick} />

<div class="mt-3">
  <div class="edit-controls mb-3">
    <button id="edit-btn" class="btn btn-primary" style:display={editMode ? 'none' : ''} onclick={() => toggleEditMode(true)}>Edit</button>
    <div id="edit-buttons" style:display={editMode ? 'block' : 'none'}>
      <button id="save-btn" class="btn btn-success" onclick={saveChanges}>Save</button>
      <button id="cancel-btn" class="btn btn-secondary" onclick={() => toggleEditMode(false)}>Cancel</button>
    </div>
  </div>

  <!-- Person Information -->
  <div class="card mb-3">
    <div class="card-header">
      <h5 class="mb-0">Personal Information</h5>
    </div>
    <div class="card-body">
      <!-- Display Mode -->
      <div id="person-display" class="row" style:display={editMode ? 'none' : ''}>
        <div class="col-md-6">
          <dl class="row mb-0">
            <dt class="col-sm-4">Name:</dt>
            <dd class="col-sm-8">{person.name}</dd>

            <dt class="col-sm-4">Email:</dt>
            <dd class="col-sm-8">{person.email || 'Not provided'}</dd>

            <dt class="col-sm-4">SMS Number:</dt>
            <dd class="col-sm-8">{person.sms_number || 'Not provided'}</dd>
          </dl>
        </div>
        <div class="col-md-6">
          <dl class="row mb-0">
            <dt class="col-sm-4">City:</dt>
            <dd class="col-sm-8">{person.city || 'Not provided'}</dd>

            <dt class="col-sm-4">State:</dt>
            <dd class="col-sm-8">{person.state || 'Not provided'}</dd>

            <dt class="col-sm-4">Country:</dt>
            <dd class="col-sm-8">{person.country || 'Not provided'}</dd>

            <dt class="col-sm-4">TheSession.org:</dt>
            <dd class="col-sm-8">
              {#if person.thesession_user_id}
                <a href="https://thesession.org/members/{person.thesession_user_id}" target="_blank" rel="noopener noreferrer">
                  {person.thesession_user_id}
                </a>
              {:else}
                <span class="text-muted">Not a member</span>
              {/if}
            </dd>
          </dl>
        </div>
        <div class="col-12 mt-2">
          <dl class="row mb-0">
            <dt class="col-sm-2">Instruments:</dt>
            <dd class="col-sm-10">
              {#if person.instruments && person.instruments.length}
                <span id="instruments-display">{person.instruments.join(', ')}</span>
              {:else}
                <span id="instruments-display" class="text-muted">No instruments listed</span>
              {/if}
            </dd>
          </dl>
        </div>
      </div>

      <!-- Edit Mode -->
      <div id="person-edit" class="row" style:display={editMode ? 'block' : 'none'}>
        <form id="person-form" onsubmit={(e) => e.preventDefault()}>
          <div class="row">
            <div class="col-md-6">
              <div class="mb-3">
                <label for="first_name" class="form-label">First Name</label>
                <input type="text" class="form-control" id="first_name" name="first_name" bind:value={firstName} required />
              </div>
              <div class="mb-3">
                <label for="last_name" class="form-label">Last Name</label>
                <input type="text" class="form-control" id="last_name" name="last_name" bind:value={lastName} required />
              </div>
              <div class="mb-3">
                <label for="email" class="form-label">Email</label>
                <input type="email" class="form-control" id="email" name="email" bind:value={email} />
              </div>
            </div>
            <div class="col-md-6">
              <div class="mb-3">
                <label for="sms_number" class="form-label">SMS Number</label>
                <input type="text" class="form-control" id="sms_number" name="sms_number" bind:value={smsNumber} />
              </div>
              <div class="mb-3">
                <label for="city" class="form-label">City</label>
                <input type="text" class="form-control" id="city" name="city" bind:value={city} />
              </div>
              <div class="mb-3">
                <label for="state" class="form-label">State</label>
                <input type="text" class="form-control" id="state" name="state" bind:value={stateField} />
              </div>
              <div class="mb-3">
                <label for="country" class="form-label">Country</label>
                <input type="text" class="form-control" id="country" name="country" bind:value={country} />
              </div>
              <div class="mb-3">
                <label for="thesession_user_id" class="form-label">TheSession User ID</label>
                <input type="number" class="form-control" id="thesession_user_id" name="thesession_user_id" bind:value={thesessionUserId} />
              </div>
            </div>
          </div>
          <div class="row">
            <div class="col-12">
              <div class="mb-3">
                <label class="form-label" for="instrument-typeahead">Instruments</label>
                <div class="text-muted small mb-2">Changes save immediately. Click an instrument to set it auto/manual or remove it.</div>
                <div class="instrument-typeahead-wrap" bind:this={typeaheadWrap}>
                  <input
                    type="text"
                    id="instrument-typeahead"
                    class="form-control"
                    placeholder="Add an instrument…"
                    autocomplete="off"
                    bind:value={typeaheadValue}
                    oninput={updateTypeahead}
                    onfocus={updateTypeahead}
                    onkeydown={onTypeaheadKeydown} />
                  <div id="instrument-typeahead-menu" class="typeahead-menu" style:display={typeaheadOpen && typeaheadOptions.length ? 'block' : 'none'}>
                    {#each typeaheadOptions as opt (opt.value)}
                      <button type="button" class="typeahead-option" onmousedown={(e) => e.preventDefault()} onclick={() => addInstrumentToProfile(opt.value)}>{opt.label}</button>
                    {/each}
                  </div>
                </div>
                <div id="instrument-rows" class="mt-2">
                  {#if !profileInstruments.length}
                    <div class="text-muted small">No instruments yet — add one above.</div>
                  {:else}
                    {#each profileInstruments as inst (inst.instrument)}
                      <div
                        class="instrument-row"
                        role="button"
                        tabindex="0"
                        onclick={() => openInstrumentConfig(inst.instrument)}
                        onkeydown={(e) => {
                          if (e.key === 'Enter') openInstrumentConfig(inst.instrument)
                        }}>
                        <span>{inst.instrument}</span>
                        <span class="instrument-row-badge{inst.is_auto ? ' auto' : ''}">{inst.is_auto ? 'Auto' : 'Manual'}</span>
                      </div>
                    {/each}
                  {/if}
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  </div>

  <!-- User Account Information -->
  <div class="card">
    <div class="card-header">
      <h5 class="mb-0">Account Information</h5>
    </div>
    <div class="card-body">
      {#if user}
        <!-- Display Mode -->
        <div id="user-display" class="row" style:display={editMode ? 'none' : ''}>
          <div class="col-md-6">
            <dl class="row mb-0">
              <dt class="col-sm-4">Username:</dt>
              <dd class="col-sm-8">
                <strong>{user.username}</strong>
                {#if user.is_system_admin}
                  <span class="admin-indicator">(admin)</span>
                {/if}
              </dd>

              <dt class="col-sm-4">User Email:</dt>
              <dd class="col-sm-8">{user.user_email || 'Not provided'}</dd>

              <dt class="col-sm-4">Email Verified:</dt>
              <dd class="col-sm-8">
                {#if user.email_verified}
                  <span class="text-success">✓ Verified</span>
                {:else}
                  <span class="text-warning">✗ Not verified</span>
                  {#if !isUserProfile}
                    <button id="verify-email-btn" class="btn btn-sm btn-success ms-2" disabled={verifyingEmail} onclick={(e) => { e.preventDefault(); verifyConfirmOpen = true }}>{verifyBtnLabel}</button>
                  {/if}
                {/if}
              </dd>

              <dt class="col-sm-4">Live editor (beta):</dt>
              <dd class="col-sm-8">
                <span id="beta-logging-status">
                  {#if user.beta_live_logging}<span class="text-success">✓ On</span>{:else}<span class="text-muted">Off</span>{/if}
                </span>
                {#if !isUserProfile}
                  <button id="beta-logging-btn" class="btn btn-sm btn-outline-primary ms-2" disabled={betaBusy} onclick={(e) => { e.preventDefault(); toggleBetaLogging() }}>
                    {user.beta_live_logging ? 'Turn off' : 'Turn on'}
                  </button>
                {/if}
              </dd>
            </dl>
          </div>
          <div class="col-md-6">
            <dl class="row mb-0">
              <dt class="col-sm-4">Active:</dt>
              <dd class="col-sm-8">
                {#if user.is_active}
                  <span class="text-success">✓ Active</span>
                {:else}
                  <span class="text-danger">✗ Inactive</span>
                {/if}
              </dd>

              <dt class="col-sm-4">Created:</dt>
              <dd class="col-sm-8">{fmtDateTime(user.created_at) || 'Unknown'}</dd>

              <dt class="col-sm-4">Last Login:</dt>
              <dd class="col-sm-8">{fmtDateTime(user.last_login) || 'Never'}</dd>

              <dt class="col-sm-4">Timezone:</dt>
              <dd class="col-sm-8">{user.timezone_display || 'UTC'}</dd>

              <dt class="col-sm-4">Update Emails:</dt>
              <dd class="col-sm-8">
                {#if user.receive_update_emails}<span class="text-success">✓ Subscribed</span>{:else}<span class="text-muted">Not subscribed</span>{/if}
              </dd>
            </dl>
          </div>
        </div>

        {#if isUserProfile}
          <!-- Change/Create Password Button for User Profile -->
          <div class="mt-3">
            <a href="/change-password" class="btn btn-outline-primary">{user.has_password ? 'Change My Password' : 'Create A Password'}</a>
          </div>
        {/if}

        <!-- Edit Mode -->
        <div id="user-edit" class="row" style:display={editMode ? 'block' : 'none'}>
          <form id="user-form" onsubmit={(e) => e.preventDefault()}>
            <div class="row">
              <div class="col-md-6">
                <div class="mb-3">
                  <label for="username" class="form-label">Username</label>
                  <input type="text" class="form-control" id="username" name="username" bind:value={username} onblur={onUsernameBlur} required />
                  <div id="username-warning" class="text-warning" style:display={usernameWarning ? 'block' : 'none'}>{usernameWarning}</div>
                </div>
                <div class="mb-3">
                  <label for="user_email" class="form-label">Email</label>
                  <input type="email" class="form-control" id="user_email" name="user_email" bind:value={userEmail} />
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
              <div class="col-md-6">
                {#if !isUserProfile}
                  <div class="mb-3">
                    <div class="form-check">
                      <input class="form-check-input" type="checkbox" id="is_active" name="is_active" bind:checked={isActiveChecked} />
                      <label class="form-check-label" for="is_active">
                        User Account Active
                      </label>
                    </div>
                  </div>
                {/if}
                {#if isUserProfile}
                  <div class="mb-3">
                    <div class="form-check">
                      <input class="form-check-input" type="checkbox" id="receive_update_emails" name="receive_update_emails" bind:checked={receiveUpdateEmails} />
                      <label class="form-check-label" for="receive_update_emails">
                        Get regular updates about this app via email
                      </label>
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          </form>
        </div>
      {:else}
        <div class="alert alert-info mb-0" role="alert">
          <p class="mb-0">This person is not connected with a user account.</p>
        </div>
      {/if}
    </div>
  </div>

  <!-- Bottom Edit Buttons -->
  <div id="bottom-edit-buttons" class="mt-3" style:display={editMode ? 'block' : 'none'}>
    <button id="bottom-save-btn" class="btn btn-success" onclick={saveChanges}>Save</button>
    <button id="bottom-cancel-btn" class="btn btn-secondary" onclick={() => toggleEditMode(false)}>Cancel</button>
  </div>

  <!-- Danger Zone - Admin Only -->
  {#if !isUserProfile}
    <div class="card mt-4 border-danger" id="danger-zone">
      <div class="card-header bg-danger text-white">
        <h5 class="mb-0">Danger Zone</h5>
      </div>
      <div class="card-body">
        {#if person.active}
          <h6 class="text-danger">Deactivate Person</h6>
          <p class="text-muted">
            Deactivating {person.name} will prevent them from being added to any sessions, session instances, or tune sets.
            Existing associations will not be affected.
          </p>
          <button type="button" class="btn btn-outline-danger" id="deactivate-person-btn" onclick={() => askTogglePersonActive(false)}>
            Deactivate {person.first_name}
          </button>
        {:else}
          <div class="alert alert-warning mb-3">
            <strong>This person is deactivated.</strong> They cannot be added to sessions, session instances, or tune sets.
          </div>
          <h6 class="text-success">Reactivate Person</h6>
          <p class="text-muted">
            Reactivating {person.name} will allow them to be added to sessions, session instances, and tune sets again.
          </p>
          <button type="button" class="btn btn-success" id="reactivate-person-btn" onclick={() => askTogglePersonActive(true)}>
            Reactivate {person.first_name}
          </button>
        {/if}
        <div id="toggle-active-status" class="mt-3" style:display={toggleActiveStatusHtml ? 'block' : 'none'}>
          {#if toggleActiveStatusHtml}
            <div class="alert alert-{toggleActiveStatusHtml.kind}">{toggleActiveStatusHtml.text}</div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<!-- Instrument config sheet (auto/manual + remove; changes save immediately,
     so there is no Done — Cancel/scrim/Escape just dismiss) -->
<Sheet bind:open={configOpen} title={configInstrument || ''}>
  <div class="inst-config-body">
    <div class="form-check">
      <input
        class="form-check-input"
        type="radio"
        name="instrument-auto"
        id="inst-auto-radio"
        value="auto"
        checked={!!(configInst && configInst.is_auto)}
        onchange={() => setInstrumentAutoFromModal(true)} />
      <label class="form-check-label" for="inst-auto-radio"><strong>Auto</strong> — follows the tune's main status. When you mark a tune learned, it's learned on this instrument.</label>
    </div>
    <div class="form-check">
      <input
        class="form-check-input"
        type="radio"
        name="instrument-auto"
        id="inst-manual-radio"
        value="manual"
        checked={!(configInst && configInst.is_auto)}
        onchange={() => setInstrumentAutoFromModal(false)} />
      <label class="form-check-label" for="inst-manual-radio"><strong>Manual</strong> — a curated list you set per tune. Starts empty; you add tunes to it one at a time.</label>
    </div>
  </div>
  {#snippet footer()}
    <a class="pd-modal-remove" href="#remove" onclick={(e) => { e.preventDefault(); removeInstrumentFromProfile() }}>Remove from profile</a>
  {/snippet}
</Sheet>

<!-- Instrument removal is a destructive decision -> kit Dialog (data-loss warning) -->
<Dialog
  bind:open={removeConfirmOpen}
  title="Remove instrument?"
  confirmLabel="Remove anyway"
  destructive={true}
  onConfirm={confirmRemoveInstrument}
  onCancel={cancelRemoveInstrument}>
  {#if removeWarnParts}
    <p id="instrument-remove-warn" class="pd-modal-warn">
      Removing <strong>{removeWarnParts.name}</strong> will delete its saved status for {removeWarnParts.tunesText} that you've customized away from your other instruments. Re-adding it later starts fresh on Auto. This can't be undone.
    </p>
  {/if}
</Dialog>

<Dialog
  bind:open={verifyConfirmOpen}
  title="Verify this email address?"
  description="This manually marks the email address as verified."
  confirmLabel="Verify email"
  onConfirm={verifyEmail} />

<Dialog
  bind:open={toggleActiveOpen}
  title={`${toggleActiveTarget ? 'Reactivate' : 'Deactivate'} ${person.name}?`}
  confirmLabel={toggleActiveTarget ? 'Reactivate person' : 'Deactivate person'}
  destructive={!toggleActiveTarget}
  onConfirm={() => togglePersonActive(toggleActiveTarget)} />
