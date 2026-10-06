<script>
  // i18n-converted
  /**
   * The People tab — this session's roster (spec 034).
   *
   * Gated on can_view_people (is_admin OR confirmed), NOT membership: joining a session must
   * not hand you its roster. The tab isn't even rendered for an unconfirmed member.
   *
   * What changed in 034:
   *  - The All/Regulars toggle is gone with is_regular. Ordering is computed from actual
   *    attendance (server-side), so who actually turns up is who you see first; nobody is
   *    hidden by a filter, and nobody is labelled with a rank.
   *  - The two stacked sheets (search-all-people → create-person) became ONE PersonPicker.
   *    Its search is local, because there is nothing to search but this roster: 034 removed
   *    global person search entirely, so you can't discover people from other sessions.
   *  - Visitors and archived people are behind filter chips rather than in your face.
   *  - The person sheet gained the admin controls: Confirm (which grants people-visibility,
   *    and says so at the point of click) and Archive (roster hygiene).
   */
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { Chip, LoadError, PersonPicker, Row, SearchField, Seg, Sheet, Toolbar, toast, ServerError, t, tn, instrumentName } from '../lib/index.js'
  import { toastFailed } from './failure.js'
  import { normalizeQuotes } from '../shared/parse.js'
  import { filterPeople } from './logic.js'

  let {
    active,
    sessionPath,
    sessionType,
    canonicalInstruments = [],
    currentUserId = null,
    initialPersonId = null,
    isSessionAdmin = false,
    // Spec 039: when the session isn't tracking attendance the roster still shows (this
    // is the members list, gated separately by show_people_list), but with no attendance
    // counts or attended-nights table — there's nothing to show.
    trackAttendance = true,
  } = $props()

  // ---- people list -----------------------------------------------------------
  let peopleData = $state([])
  let peopleLoaded = $state(false)
  let peopleError = $state('')
  let currentPeopleFilter = $state('members') // 'members' | 'visitors' | 'archived'
  let searchText = $state('')
  let filterOpen = $state(false) // the toolbar's filter panel

  const searchQuery = $derived(normalizeQuotes(searchText.toLowerCase().trim()))
  const filteredPeople = $derived(filterPeople(peopleData, currentPeopleFilter, searchQuery))

  const FILTERS = [
    { id: 'members', label: t('Members') },
    { id: 'visitors', label: t('Visitors') },
    { id: 'archived', label: t('Archived') },
  ]

  // People an admin has yet to vouch for. Until they're confirmed they can't see anyone here.
  const awaitingConfirmation = $derived(
    peopleData.filter((p) => !p.confirmed && !p.archived && p.has_user_account)
  )

  let fetchStarted = false
  $effect(() => {
    if (active && !fetchStarted) {
      fetchStarted = true
      fetchPeople()
    }
  })

  let peopleRetrying = $state(false)

  // A failure renders LoadError in place of the list (with Retry), never an empty roster.
  function fetchPeople() {
    peopleRetrying = !!peopleError
    return fetch(`/api/sessions/${sessionPath}/people`)
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) throw new Error(data.message || 'people load failed')
        peopleData = data.people
        peopleError = ''
      })
      .catch((error) => {
        console.error('Error loading people:', error)
        peopleError = 'failed'
      })
      .finally(() => {
        peopleLoaded = true
        peopleRetrying = false
      })
  }

  // ---- add person (ONE PersonPicker; no global search — see the header comment) ----
  let pickerOpen = $state(false)
  let saving = $state(false)

  function openAddPerson() {
    pickerOpen = true
  }

  async function createPerson({ first_name, last_name, email, instruments }) {
    saving = true
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/people/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name,
          last_name,
          email,
          instruments,
          relationship: 'member',
        }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new ServerError(data.message || data.error)
      // No success toast (spec 052 §B4): fetchPeople() puts them in the list you
      // are looking at, and a banner saying so says it twice.
      pickerOpen = false
      fetchPeople()
    } catch (e) {
      toastFailed(
        e,
        t("Couldn't add that person. Try again."),
        t("Couldn't add that person. Check your connection and try again.")
      )
    } finally {
      saving = false
    }
  }

  // ---- person detail sheet -----------------------------------------------------
  let detailOpen = $state(false)
  let detailLoading = $state(false)
  let detailFailed = $state(false)
  let detailPerson = $state(null)
  let detailBusy = $state(false)
  let detailBusyField = $state('') // which control is saving, so it can say "Saving…"
  let detailPersonId = $state(null)

  // The roster row for the person in the sheet — carries relationship/confirmed/archived,
  // which the /people/<id> detail endpoint doesn't return.
  const detailRow = $derived(
    detailPerson ? peopleData.find((p) => p.person_id === detailPerson.person_id) : null
  )

  export function showPersonDetail(personId) {
    let basePath = window.location.pathname
    basePath = basePath.replace(/\/people\/\d+$/, '').replace(/\/(tunes|logs|people)$/, '')
    window.history.pushState({}, '', `${basePath}/people/${personId}`)

    detailPerson = null
    detailOpen = true
    loadPersonDetail(personId)
  }

  function loadPersonDetail(personId) {
    detailPersonId = personId
    detailLoading = true
    detailFailed = false

    fetch(`/api/sessions/${sessionPath}/people/${personId}`)
      .then((response) => response.json())
      .then((data) => {
        if (personId !== detailPersonId) return
        detailLoading = false
        if (data.success) detailPerson = data.person
        else detailFailed = true
      })
      .catch((error) => {
        console.error('Error loading person details:', error)
        if (personId !== detailPersonId) return
        detailLoading = false
        detailFailed = true
      })
  }

  function onDetailClosed() {
    const newPath = window.location.pathname.replace(/\/people\/\d+$/, '/people')
    window.history.pushState({}, '', newPath)
  }

  const locationStringOf = (person) => {
    const parts = []
    if (person.city) parts.push(person.city)
    if (person.state) parts.push(person.state)
    if (person.country) parts.push(person.country)
    return parts
  }

  const nameOf = (p) => `${p.first_name} ${p.last_name}`.trim()

  // What a failed save says: [the server explained it, it never got there].
  const FIELD_FAILED = {
    confirmed: () => [
      t("Couldn't change whether they are confirmed. Try again."),
      t("Couldn't change whether they are confirmed. Check your connection and try again."),
    ],
    archived: () => [
      t("Couldn't change whether they are archived. Try again."),
      t("Couldn't change whether they are archived. Check your connection and try again."),
    ],
    relationship: () => [
      t("Couldn't change their relationship to this session. Try again."),
      t("Couldn't change their relationship to this session. Check your connection and try again."),
    ],
  }
  const fieldFailed = (field) =>
    FIELD_FAILED[field]
      ? FIELD_FAILED[field]()
      : [
          t("Couldn't save that change. Try again."),
          t("Couldn't save that change. Check your connection and try again."),
        ]

  async function setField(personId, field, value) {
    if (detailBusy) return false
    detailBusy = true
    detailBusyField = field
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/people/${personId}/${field}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new ServerError(data.message || data.error)
      // Patch the roster row in place so the list and the sheet agree without a refetch.
      peopleData = peopleData.map((p) =>
        p.person_id === personId ? { ...p, [field]: value } : p
      )
      return true
    } catch (e) {
      toastFailed(e, ...fieldFailed(field))
      return false
    } finally {
      detailBusy = false
      detailBusyField = ''
    }
  }

  async function toggleConfirmed() {
    if (!detailRow) return
    const next = !detailRow.confirmed
    if (await setField(detailRow.person_id, 'confirmed', next)) {
      toast(
        next
          ? t("{name} can now see this session's people and attendance.", { name: nameOf(detailRow) })
          : t("{name} can no longer see this session's people.", { name: nameOf(detailRow) }),
        'success'
      )
    }
  }

  async function toggleArchived() {
    if (!detailRow) return
    const next = !detailRow.archived
    // Silent (spec 052 §B4): the row leaves the filter you are on, or comes back to
    // it. Unlike the confirmed toggle above, which changes what somebody can SEE and
    // shows nothing here, this one's effect is the list in front of you.
    await setField(detailRow.person_id, 'archived', next)
  }

  async function setRelationship(value) {
    if (!detailRow || detailRow.relationship === value) return
    await setField(detailRow.person_id, 'relationship', value)
  }

  const RELATIONSHIPS = [
    { id: 'member', label: t('Member') },
    { id: 'visitor', label: t('Visitor') },
  ]

  // ---- deep link ---------------------------------------------------------------
  $effect(() => {
    untrack(() => {
      if (initialPersonId) {
        setTimeout(() => showPersonDetail(initialPersonId), 100)
      }
    })
  })
</script>

<!-- People Tab Content -->
<div class="tab-content" class:active id="people-tab">
  <div class="people-container">
    <!-- One toolbar, same as Tunes and Logs (spec 052 §B8 Stage 3). -->
    <div class="people-controls">
      <Toolbar
        styled={false}
        toolbarClass="filter-top-row"
        buttonClass="filter-panel-toggle"
        bind:open={filterOpen}
        activeCount={currentPeopleFilter === FILTERS[0].id ? 0 : 1}
        addId="add-person-btn"
        addTitle={t('Add someone to this session')}
        onAdd={openAddPerson}>
        {#snippet search()}
          <SearchField
            bind:value={searchText}
            id="people-search-box"
            inputClass="filter-search-input"
            wrapperClass="people-search-wrap filter-search-wrap"
            styled={false}
            placeholder={t('Search people...')} />
        {/snippet}
        {#snippet filter()}
          <Seg
            options={FILTERS}
            value={currentPeopleFilter}
            onSelect={(id) => (currentPeopleFilter = id)}
            idAttr="data-people-filter"
            styled={false}
            segClass="filter-button-group"
            optClass="filter-sort-btn"
            aria-label={t('Filter people')} />
        {/snippet}
      </Toolbar>
    </div>

    {#if isSessionAdmin && awaitingConfirmation.length > 0}
      <!-- Confirming is the ONLY way people-visibility is granted, so an admin needs to know
           someone is waiting on it. -->
      <p class="people-nudge">
        {tn(
          awaitingConfirmation.length,
          "{n} person has joined and can't see who plays here yet. Open them to confirm.",
          "{n} people have joined and can't see who plays here yet. Open them to confirm."
        )}
      </p>
    {/if}

    <div class="people-list" id="people-list">
      {#if !peopleLoaded}
        <div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);">
          <i class="loading-dots">{t('Loading people...')}</i>
        </div>
      {:else if peopleError}
        <LoadError id="people-load-error" message={t("Couldn't load this session's people.")} onRetry={fetchPeople} retrying={peopleRetrying} />
      {:else if filteredPeople.length === 0}
        <div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);">
          <p>
            {#if searchQuery}
              {t('No people found matching your search')}
            {:else if currentPeopleFilter === 'visitors'}
              {t('No visitors to this session yet')}
            {:else if currentPeopleFilter === 'archived'}
              {t('Nobody archived')}
            {:else}
              {t('No people in this session yet')}
            {/if}
          </p>
          {#if searchQuery}
            <button class="people-empty-add" onclick={openAddPerson}>
              {t('Add Someone To This Session')}
            </button>
          {/if}
        </div>
      {:else}
        {#each filteredPeople as person (person.person_id)}
          <!-- The kit Row owns the three-slot layout (spec 052 §B8 Stage 2); this
               file keeps every legacy class, so page.css and the e2e selectors are
               untouched. `body` carries .person-info unchanged, because it lays name/
               badges/instruments out INLINE on desktop and stacked on a phone — a
               shape Row's title+subtitle cannot express. -->
          <Row
            styled={false}
            rowClass="person-row{person.archived ? ' archived' : ''}"
            onclick={() => showPersonDetail(person.person_id)}>
            {#snippet lead()}
              <div class="person-icon {person.has_user_account ? 'has-account' : 'no-account'}">
                <i class="fa fa-user-circle"></i>
              </div>
            {/snippet}
            {#snippet body()}
              <div class="person-info">
                <!-- Badges are SIBLINGS of .person-name, not children: the name element's text
                     content should be the name, nothing else. -->
                <div class="person-name">{person.first_name} {person.last_name}</div>
                {#if person.relationship === 'visitor' || person.archived || (!person.confirmed && person.has_user_account)}
                  <div class="person-badges">
                    {#if person.relationship === 'visitor'}
                      <Chip label={t('Visitor')} variant="warning" />
                    {/if}
                    {#if person.archived}
                      <Chip label={t('Archived')} />
                    {/if}
                    {#if !person.confirmed && person.has_user_account}
                      <Chip label={t('Unconfirmed')} variant="warning" title={t("Can't see this session's people yet")} />
                    {/if}
                  </div>
                {/if}
                <div class="person-instruments">
                  {person.instruments && person.instruments.length > 0 ? person.instruments.map(instrumentName).join(', ') : t('No instruments listed')}
                </div>
              </div>
            {/snippet}
            {#snippet trailing()}
              {#if trackAttendance}
                <div class="person-meta">
                  <Chip label={String(person.attendance_count || 0)} styled={false} chipClass="person-attendance-badge" title={t('Nights attended')} />
                </div>
              {/if}
            {/snippet}
          </Row>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Person Detail Sheet -->
  <Sheet bind:open={detailOpen} title={detailPerson ? nameOf(detailPerson) : ''} onCancel={onDetailClosed}>
    <div id="person-detail-content">
      {#if detailLoading}
        <div style="padding: 40px 20px; text-align: center;">
          <i class="loading-dots">{t('Loading...')}</i>
        </div>
      {:else if detailFailed || !detailPerson}
        <LoadError
          id="person-detail-load-error"
          message={t("Couldn't load this person's details.")}
          onRetry={detailPersonId ? () => loadPersonDetail(detailPersonId) : null}
          retrying={detailLoading} />
      {:else}
        {#if detailPerson.person_id === currentUserId}
          <div style="margin-bottom: 16px;"><a href="/me" class="person-detail-link">{t('View my profile')}</a></div>
        {/if}
        {#if detailPerson.has_user_account && detailPerson.person_id !== currentUserId}
          <div style="margin-bottom: 16px;"><a href="/me/and/{detailPerson.person_id}?from={sessionPath}" class="person-detail-link">{t('Common Tunes?')}</a></div>
        {/if}

        {#if detailRow && (isSessionAdmin || detailPerson.person_id === currentUserId)}
          <div class="person-detail-section">
            <h3>{t('Relationship to this session')}</h3>
            <Seg
              options={RELATIONSHIPS}
              value={detailRow.relationship}
              onSelect={setRelationship}
              idAttr="data-relationship" />
            <p class="pd-hint">
              {#if detailBusyField === 'relationship'}
                {t('Saving…')}
              {:else if detailRow.relationship === 'visitor'}
                {t("Came here, but this isn't one of their sessions.")}
              {:else}
                {t('This is one of their sessions — its tunes count towards their stats.')}
              {/if}
            </p>
          </div>
        {/if}

        {#if detailRow && isSessionAdmin}
          <div class="person-detail-section">
            <h3>{t('Session admin')}</h3>
            <!-- The copy has to say what confirming DOES, at the point of click. A bare
                 "Confirmed" toggle would be an admin handing over the roster without
                 realising it. -->
            <button class="pd-action" disabled={detailBusy} onclick={toggleConfirmed}>
              {#if detailBusyField === 'confirmed'}
                {t('Saving…')}
              {:else if detailRow.confirmed}
                {t("Un-confirm {name} — they'll no longer see this session's people list and attendance records", { name: nameOf(detailPerson) })}
              {:else}
                {t("Confirm {name} — they'll be able to see this session's people list and attendance records", { name: nameOf(detailPerson) })}
              {/if}
            </button>
            <button class="pd-action" disabled={detailBusy} onclick={toggleArchived}>
              {#if detailBusyField === 'archived'}
                {t('Saving…')}
              {:else if detailRow.archived}
                {t('Restore {name} to the roster', { name: nameOf(detailPerson) })}
              {:else}
                {t('Archive {name} — hide them from lists (still findable by name)', { name: nameOf(detailPerson) })}
              {/if}
            </button>
          </div>
        {/if}

        <div class="person-detail-location">
          {locationStringOf(detailPerson).length > 0 ? locationStringOf(detailPerson).join(', ') : t('No location specified')}
        </div>
        <div class="person-detail-section">
          <h3>{'TheSession.org' /* a name, not translated */}</h3>
          {#if detailPerson.thesession_user_id}
            <a href="https://thesession.org/members/{detailPerson.thesession_user_id}" target="_blank" class="person-detail-link">{t('View on TheSession.org')}</a>
          {:else}
            <span style="color: var(--text-muted);">{t('Not linked')}</span>
          {/if}
        </div>
        <div class="person-detail-section">
          <h3>{t('Instruments')}</h3>
          {#if detailPerson.instruments && detailPerson.instruments.length > 0}
            <div class="person-instruments-list">
              {#each detailPerson.instruments as inst (inst)}
                <Chip label={instrumentName(inst)} styled={false} chipClass="person-instrument-badge" />
              {/each}
            </div>
          {:else}
            <span style="color: var(--text-muted);">{t('No instruments listed')}</span>
          {/if}
        </div>
        {#if trackAttendance}
        <div class="person-detail-section">
          <h3>{t('Sessions Attended')}</h3>
          {#if detailPerson.attended_instances && detailPerson.attended_instances.length > 0}
            <table class="attendance-table">
              <thead>
                <tr><th>{t('Date')}</th></tr>
              </thead>
              <tbody>
                <!-- Keyed by instance id, not date: a session may legitimately run
                     twice in one day (a festival, spec 047), so a date is not a
                     unique key — and a duplicate key is a hard render error, not a
                     cosmetic one. The link goes to the id for the same reason: a
                     date URL resolves to whichever instance is first (spec 046). -->
                {#each detailPerson.attended_instances as instance (instance.session_instance_id)}
                  <tr>
                    <td>
                      <a href="/sessions/{sessionPath}/{instance.session_instance_id}" class="person-detail-link">{instance.date}</a>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <p style="color: var(--text-muted); margin-top: 12px;">{t('No sessions attended yet')}</p>
          {/if}
        </div>
        {/if}
      {/if}
    </div>
  </Sheet>

  <!--
    ONE add flow. Filtering is over this session's roster only; anyone else is typed in fresh
    and deduped on email server-side. (Before 034 this was two stacked sheets, the first of
    which searched every person in the database.)
  -->
  <PersonPicker
    bind:open={pickerOpen}
    scope="session"
    mode="attendance"
    title={t('Add someone to this session')}
    people={peopleData}
    {canonicalInstruments}
    busy={saving}
    onSelect={(p) => showPersonDetail(p.person_id)}
    onCreate={createPerson}
    onClose={() => (pickerOpen = false)} />
</div>

<style>
  .people-nudge {
    margin: 8px 0;
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--warning-bg);
    color: var(--text-color);
    font-size: 0.86rem;
  }
  .person-row.archived { opacity: 0.55; }
  .person-badges { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 2px; }
  .pd-hint { font-size: 0.82rem; color: var(--text-muted, #6c757d); margin: 8px 0 0; }
  .pd-action {
    display: block;
    width: 100%;
    text-align: left;
    margin-top: 8px;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--hover-bg);
    color: inherit;
    font: inherit;
    font-size: 0.86rem;
    cursor: pointer;
  }
  .pd-action:hover { border-color: var(--primary); }
  .pd-action:disabled { opacity: 0.5; cursor: default; }
  .people-empty-add {
    margin-top: 16px;
    padding: 10px 20px;
    background-color: var(--primary-fill);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  }
</style>
