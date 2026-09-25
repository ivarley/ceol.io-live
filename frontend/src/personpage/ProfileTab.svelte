<script>
  // The profile screen: grouped rows for the person and their account, with a
  // display/edit toggle that keeps the same rows either way, the live
  // per-instrument editor (saves immediately, decoupled from the profile Save
  // button), and the admin-only verify-email / danger-zone controls.
  let { person, user, isUserProfile, personId, timezoneOptions = [], canonicalInstruments = [] } = $props()

  import { Dialog, Sheet, toast } from '../lib/index.js'
  import '../lib/grouped.css'
  import MergeSection from './MergeSection.svelte'
  import IdentityHeader from './IdentityHeader.svelte'

  let editMode = $state(false)

  // Created / Last login / Active are evidence on somebody else's profile and
  // noise on your own — nobody checks when they signed up. So an admin gets them
  // outright and you get them behind a row.
  let detailsOpen = $state(!isUserProfile)

  // The line under the name: the account handle and where you play, which is the
  // context a profile is actually for.
  const placeLine = $derived(
    [person.city, person.state, person.country].filter(Boolean).join(', ')
  )
  const subtitle = $derived(
    [user && user.username ? '@' + user.username : null, placeLine].filter(Boolean).join('  ·  ')
  )

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
      // person.email is retired for connected people — the account's user_email
      // is the address. Never write it back for someone who has an account.
      email: user ? null : (email.trim() || null),
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
      // is_active is no longer editable here — it's governed by the person
      // deactivate/reactivate control, in lockstep with the account.
      if (isUserProfile) {
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
          // No toast (spec 052 §B4): the reload below is the confirmation, and it
          // destroys the toast a second after showing it.
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

<IdentityHeader
  name={person.name}
  {subtitle}
  isAdmin={!!(user && user.is_system_admin)}
  {editMode}
  onEdit={() => toggleEditMode(true)}
  onSave={saveChanges}
  onCancel={() => toggleEditMode(false)} />

<div class="pd-body">
  <!-- Who you are. Grouped rows, label left and value right, so each line reads
       as a sentence — "Location  Austin, TX" — instead of a bold grey caption
       stacked over a dimmer value, which had the hierarchy upside down. -->
  <div id="person-display" style:display={editMode ? 'none' : ''}>
    <div class="kit-group">
      <div class="kit-field kit-field-wrap">
        <span class="kit-field-label">Instruments</span>
        {#if person.instruments && person.instruments.length}
          <span class="kit-field-value" id="instruments-display">{person.instruments.join(', ')}</span>
        {:else}
          <span class="kit-field-value is-empty" id="instruments-display">None listed</span>
        {/if}
      </div>

      <!-- City, state and country were three rows saying one thing. -->
      <div class="kit-field">
        <span class="kit-field-label">Location</span>
        <span class="kit-field-value" class:is-empty={!placeLine}>{placeLine || 'Not provided'}</span>
      </div>

      <div class="kit-field">
        <span class="kit-field-label">SMS</span>
        <span class="kit-field-value" class:is-empty={!person.sms_number}>{person.sms_number || 'Not provided'}</span>
      </div>

      <!-- Person-level email only exists for people with no account; once
           connected, the account's email (below) is the address. -->
      {#if !user}
        <div class="kit-field">
          <span class="kit-field-label">Email</span>
          <span class="kit-field-value" class:is-empty={!person.email}>{person.email || 'Not provided'}</span>
        </div>
      {/if}

      <div class="kit-field">
        <span class="kit-field-label">thesession.org</span>
        {#if person.thesession_user_id}
          <a class="kit-field-value pd-link" href="https://thesession.org/members/{person.thesession_user_id}" target="_blank" rel="noopener noreferrer">
            {person.thesession_user_id}
          </a>
        {:else}
          <span class="kit-field-value is-empty">Not a member</span>
        {/if}
      </div>
    </div>
  </div>

  <!-- Same rows, same order, inputs instead of text: editing does not rearrange
       the screen you were just reading. -->
  <div id="person-edit" style:display={editMode ? 'block' : 'none'}>
    <form id="person-form" onsubmit={(e) => e.preventDefault()}>
      <div class="kit-group">
        <div class="kit-field">
          <label class="kit-field-label" for="first_name">First name</label>
          <input type="text" id="first_name" name="first_name" bind:value={firstName} required />
        </div>
        <div class="kit-field">
          <label class="kit-field-label" for="last_name">Last name</label>
          <input type="text" id="last_name" name="last_name" bind:value={lastName} required />
        </div>
        {#if !user}
          <div class="kit-field">
            <label class="kit-field-label" for="email">Email</label>
            <input type="email" id="email" name="email" bind:value={email} />
          </div>
        {/if}
        <div class="kit-field">
          <label class="kit-field-label" for="sms_number">SMS</label>
          <input type="text" id="sms_number" name="sms_number" bind:value={smsNumber} />
        </div>
      </div>

      <h3 class="kit-group-head">Where you play</h3>
      <div class="kit-group">
        <div class="kit-field">
          <label class="kit-field-label" for="city">City</label>
          <input type="text" id="city" name="city" bind:value={city} />
        </div>
        <div class="kit-field">
          <label class="kit-field-label" for="state">State / area</label>
          <input type="text" id="state" name="state" bind:value={stateField} />
        </div>
        <div class="kit-field">
          <label class="kit-field-label" for="country">Country</label>
          <input type="text" id="country" name="country" bind:value={country} />
        </div>
        <div class="kit-field">
          <label class="kit-field-label" for="thesession_user_id">thesession.org</label>
          <input type="number" id="thesession_user_id" name="thesession_user_id" bind:value={thesessionUserId} placeholder="Member ID" />
        </div>
      </div>

      <h3 class="kit-group-head">Instruments</h3>
      <div class="kit-group">
        <div class="kit-field">
          <label class="kit-field-label" for="instrument-typeahead">Add</label>
          <span class="instrument-typeahead-wrap" bind:this={typeaheadWrap}>
            <input
              type="text"
              id="instrument-typeahead"
              placeholder="Fiddle, whistle…"
              autocomplete="off"
              bind:value={typeaheadValue}
              oninput={updateTypeahead}
              onfocus={updateTypeahead}
              onkeydown={onTypeaheadKeydown} />
            <span id="instrument-typeahead-menu" class="typeahead-menu" style:display={typeaheadOpen && typeaheadOptions.length ? 'block' : 'none'}>
              {#each typeaheadOptions as opt (opt.value)}
                <button type="button" class="typeahead-option" onmousedown={(e) => e.preventDefault()} onclick={() => addInstrumentToProfile(opt.value)}>{opt.label}</button>
              {/each}
            </span>
          </span>
        </div>
        <div id="instrument-rows">
          {#if !profileInstruments.length}
            <p class="kit-field-help">No instruments yet — add one above.</p>
          {:else}
            {#each profileInstruments as inst (inst.instrument)}
              <button type="button" class="kit-field instrument-row" onclick={() => openInstrumentConfig(inst.instrument)}>
                <span class="kit-field-label">{inst.instrument}</span>
                <span class="instrument-row-badge{inst.is_auto ? ' auto' : ''}">{inst.is_auto ? 'Auto' : 'Manual'}</span>
                <span class="kit-chev" aria-hidden="true">›</span>
              </button>
            {/each}
          {/if}
        </div>
      </div>
      <p class="kit-field-help pd-inst-note">Instruments save as you change them. Tap one to set it auto or manual, or to remove it.</p>
    </form>
  </div>

  {#if user}
    <h3 class="kit-group-head">Account</h3>

    <div id="user-display" style:display={editMode ? 'none' : ''}>
      <div class="kit-group">
        <div class="kit-field">
          <span class="kit-field-label">Username</span>
          <span class="kit-field-value">{user.username}</span>
        </div>
        <div class="kit-field">
          <span class="kit-field-label">Email</span>
          <span class="kit-field-value">{user.user_email || 'Not provided'}</span>
        </div>
        {#if !user.email_verified}
          <!-- Only worth a row when it is a problem: "verified" is the state every
               working account is in, so saying so on every visit says nothing. -->
          <div class="kit-field">
            <span class="kit-field-label">Email status</span>
            <span class="kit-field-value pd-warn">Not verified</span>
            {#if !isUserProfile}
              <button type="button" id="verify-email-btn" class="pd-row-action" disabled={verifyingEmail} onclick={(e) => { e.preventDefault(); verifyConfirmOpen = true }}>{verifyBtnLabel}</button>
            {/if}
          </div>
        {/if}
        <div class="kit-field">
          <span class="kit-field-label">Time zone</span>
          <span class="kit-field-value">{user.timezone_display || 'UTC'}</span>
        </div>
        <div class="kit-field">
          <span class="kit-field-label">Update emails</span>
          <span class="kit-field-value" class:is-empty={!user.receive_update_emails}>
            {user.receive_update_emails ? 'Subscribed' : 'Not subscribed'}
          </span>
        </div>
      </div>

      <!-- The card, not just the row, is conditional: the tune-logger row used to
           keep it company, and without that an admin looking at somebody else
           would get an empty card. -->
      {#if isUserProfile}
        <div class="kit-group">
          <a class="kit-field" href="/change-password">
            <span class="kit-field-label">{user.has_password ? 'Change my password' : 'Create a password'}</span>
            <span class="kit-chev" aria-hidden="true">›</span>
          </a>
        </div>
      {/if}

      <!-- When you signed up and when you last logged in: evidence on somebody
           else's profile, noise on your own. -->
      <div class="kit-group">
        <button type="button" id="account-details-toggle" class="kit-field kit-disclosure" aria-expanded={detailsOpen} aria-controls="account-details" onclick={() => (detailsOpen = !detailsOpen)}>
          <span class="kit-field-label">Details</span>
          <span class="kit-chev" class:open={detailsOpen} aria-hidden="true">›</span>
        </button>
        {#if detailsOpen}
          <div id="account-details">
            <div class="kit-field">
              <span class="kit-field-label">Status</span>
              <span class="kit-field-value" class:pd-warn={!user.is_active}>{user.is_active ? 'Active' : 'Inactive'}</span>
            </div>
            <div class="kit-field">
              <span class="kit-field-label">Created</span>
              <span class="kit-field-value">{fmtDateTime(user.created_at) || 'Unknown'}</span>
            </div>
            <div class="kit-field">
              <span class="kit-field-label">Last login</span>
              <span class="kit-field-value" class:is-empty={!user.last_login}>{fmtDateTime(user.last_login) || 'Never'}</span>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <div id="user-edit" style:display={editMode ? 'block' : 'none'}>
      <form id="user-form" onsubmit={(e) => e.preventDefault()}>
        <div class="kit-group">
          <div class="kit-field">
            <label class="kit-field-label" for="username">Username</label>
            <input type="text" id="username" name="username" bind:value={username} onblur={onUsernameBlur} required />
          </div>
          {#if usernameWarning}
            <p id="username-warning" class="kit-field-help pd-warn">{usernameWarning}</p>
          {/if}
          <div class="kit-field">
            <label class="kit-field-label" for="user_email">Email</label>
            <input type="email" id="user_email" name="user_email" bind:value={userEmail} />
          </div>
          <div class="kit-field">
            <label class="kit-field-label" for="timezone">Time zone</label>
            <select id="timezone" name="timezone" bind:value={timezone}>
              {#each timezoneOptions as tz (tz.value)}
                <option value={tz.value}>{tz.label}</option>
              {/each}
            </select>
          </div>
        </div>

        {#if isUserProfile}
          <div class="kit-group">
            <div class="kit-check-field">
              <label class="kit-check-label" for="receive_update_emails">
                <input type="checkbox" id="receive_update_emails" name="receive_update_emails" bind:checked={receiveUpdateEmails} />
                Email me about updates to this app
              </label>
            </div>
          </div>
        {/if}
      </form>
    </div>
  {:else}
    <h3 class="kit-group-head">Account</h3>
    <div class="kit-group">
      <div class="kit-field">
        <span class="kit-field-value is-empty pd-no-account">Not connected to a user account.</span>
      </div>
    </div>
  {/if}

  <!-- Danger Zone - Admin Only -->
  {#if !isUserProfile}
    <h3 class="kit-group-head pd-danger-head" id="danger-zone-head">Danger zone</h3>
    <div class="kit-group pd-danger" id="danger-zone">
      {#if person.active}
        <p class="kit-field-help">
          Deactivating {person.name} will prevent them from being added to any sessions, session instances, or tune sets.
          Existing associations will not be affected.{#if user}{' '}This also disables their login and stops all emails to their account.{/if}
        </p>
        <button type="button" class="kit-field kit-field-danger" id="deactivate-person-btn" onclick={() => askTogglePersonActive(false)}>
          <span class="kit-field-label">Deactivate {person.first_name}</span>
        </button>
      {:else}
        <p class="kit-field-help">
          <strong>This person is deactivated.</strong> They cannot be added to sessions, session instances, or tune sets.{#if user}{' '}Their login is disabled.{/if}
          Reactivating allows all of that again.
        </p>
        <button type="button" class="kit-field" id="reactivate-person-btn" onclick={() => askTogglePersonActive(true)}>
          <span class="kit-field-label pd-reactivate">Reactivate {person.first_name}</span>
        </button>
      {/if}
      <div id="toggle-active-status" style:display={toggleActiveStatusHtml ? 'block' : 'none'}>
        {#if toggleActiveStatusHtml}
          <p class="kit-field-help" class:pd-warn={toggleActiveStatusHtml.kind === 'danger'}>{toggleActiveStatusHtml.text}</p>
        {/if}
      </div>
    </div>

    <MergeSection {person} {personId} />
  {/if}
</div>

<!-- Instrument config sheet (auto/manual + remove; changes save immediately,
     so the dismiss button is labeled Done — it, scrim, and Escape just dismiss) -->
<Sheet bind:open={configOpen} title={configInstrument || ''} cancelLabel="Done">
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
