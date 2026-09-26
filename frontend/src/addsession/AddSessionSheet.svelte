<script>
  // Adding a session, stage 1 (spec 052 §B9): find it on thesession.org, or say
  // it isn't there.
  //
  // This was a page — a 36px heading, an intro paragraph and a bulleted lesson in
  // what you may type, after which the one text field started 538px down a 664px
  // screen and its button sat under the tab bar. It is a sheet presented from the
  // Sessions list now, because that is what adding a row to a list is: you come
  // back to the list when you are done, and Cancel leaves it exactly as it was.
  //
  // The lesson is gone. The field takes a name, an ID or a link because
  // parseSessionInput already sorts that out, and a placeholder says so in six
  // words.
  import { Chevron, Dialog, Row, SearchField, Sheet } from '../lib/index.js'
  import DetailsSheet from './DetailsSheet.svelte'
  import { parseSessionInput, parseTheSessionRecurrence, generatePath, guessTimezone } from './logic.js'

  let {
    open = $bindable(false),
    addMeDefault = true,
    navigate = (url) => window.location.assign(url),
    onCancel = () => {},
  } = $props()

  // Timezone options + the default, fetched the first time the sheet opens.
  let loadedPayload = $state(null)
  const timezoneOptions = $derived(loadedPayload?.timezone_options ?? [])
  const defaultTimezone = $derived(loadedPayload?.default_timezone ?? 'America/Chicago')

  // ---- search state -----------------------------------------------------------
  let query = $state('')
  let searching = $state(false)
  let results = $state(null) // null = nothing searched yet; [] = searched, no hits
  let error = $state(null) // { text, href?, linkText? } — stays until the next action
  let pendingId = $state(null) // bare digits: offered as a row rather than guessed at

  // ---- details stage ----------------------------------------------------------
  let detailsOpen = $state(false)
  let detailsSeed = $state(null)

  // ---- existing-session decision (kit Dialog: decisions are Dialogs) -----------
  let existingOpen = $state(false)
  let existingName = $state('')
  let existingPath = $state('')

  // The timezone list is the only thing this flow needs from the server up front,
  // and it is needed on the second stage at the earliest. Fetching it when the
  // sheet opens keeps it off the sessions-list payload, which is about sessions.
  let fetchedPayload = false
  $effect(() => {
    if (!open || fetchedPayload || loadedPayload) return
    fetchedPayload = true
    fetch('/api/add-session')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) loadedPayload = data
      })
      .catch(() => {
        // Not fatal: the details form falls back to its default timezone and the
        // select still carries the guessed value. Nothing to say to anybody here.
      })
  })

  function showError(text, href = null, linkText = null) {
    // No auto-dismiss. The old one cleared itself after five seconds, which is
    // long enough to start reading and not long enough to finish.
    error = { text, href, linkText }
  }

  // Typing is the fix for almost every error here, so it clears them.
  function onQuery(q) {
    error = null
    const parsed = parseSessionInput(q)
    if (parsed.kind === 'id') {
      // A pasted link is unambiguous — resolve it. Bare digits are not: a pause
      // while typing "1247" settles on "124", and silently opening session 124
      // would be worse than asking. So those become an offer.
      if (/^https?:/i.test(q.trim())) {
        pendingId = null
        results = null
        checkExistingSession(parsed.id)
      } else {
        pendingId = parsed.id
        results = null
      }
      return
    }
    pendingId = null
    if (parsed.query.length < 3) {
      results = null
      return
    }
    searchSessions(parsed.query)
  }

  function checkExistingSession(sessionId) {
    searching = true
    fetch('/api/check-existing-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((response) => response.json())
      .then((data) => {
        searching = false
        if (data.exists) {
          showError(
            `Session ${sessionId} is already on ceol.io.`,
            data.session_path,
            'Open it'
          )
        } else {
          fetchSessionData(sessionId)
        }
      })
      .catch((err) => {
        searching = false
        console.error('Error:', err)
        showError('Could not check that session. Please try again.')
      })
  }

  function searchSessions(q) {
    searching = true
    fetch('/api/search-sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q }),
    })
      .then((response) => response.json())
      .then((data) => {
        searching = false
        if (data.success) {
          results = data.results || []
        } else {
          results = null
          showError(data.message || 'Could not search thesession.org.')
        }
      })
      .catch((err) => {
        searching = false
        console.error('Error:', err)
        showError('Could not reach thesession.org. Please try again.')
      })
  }

  function pickSearchResult(result) {
    if (result.exists_in_db) {
      existingName = result.name
      existingPath = result.session_path
      existingOpen = true
    } else {
      checkExistingSession(String(result.id))
    }
  }

  function fetchSessionData(sessionId) {
    searching = true
    fetch('/api/fetch-session-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((response) => response.json())
      .then((data) => {
        searching = false
        if (data.success) {
          openDetails(seedFromSessionData(data.session_data))
        } else {
          showError(data.message || 'Could not fetch that session from thesession.org.')
        }
      })
      .catch((err) => {
        searching = false
        console.error('Error:', err)
        showError('Could not reach thesession.org. Please try again.')
      })
  }

  function seedFromSessionData(d) {
    const schedule =
      d.recurrence || d.comments ? parseTheSessionRecurrence(d.recurrence, d.comments) : null
    let unparsedText = null
    if (!schedule && d.recurrence) {
      const recurrenceText = Array.isArray(d.recurrence) ? d.recurrence.join(' ') : d.recurrence
      // (an empty schedule array is truthy — don't show the notice for "")
      if (recurrenceText) unparsedText = `Couldn't read a schedule from "${recurrenceText}" — set it here.`
    }
    return {
      thesession_id: d.id || '',
      name: d.name || '',
      path: generatePath(d.city || '', d.name || ''),
      location_name: d.location_name || '',
      location_phone: d.location_phone || '',
      location_website: d.location_website || '',
      city: d.city || '',
      state: d.state || '',
      country: d.country || '',
      inception_date: d.inception_date || '',
      timezone: guessTimezone(d.country, d.state, defaultTimezone),
      schedule,
      unparsedText,
    }
  }

  function openDetails(seed) {
    detailsSeed = seed
    detailsOpen = true
  }

  function addManually() {
    openDetails({ timezone: defaultTimezone, schedule: null, unparsedText: null })
  }

  function cancel() {
    // Leave the query behind: reopening the sheet should be a fresh start, not
    // yesterday's search.
    query = ''
    results = null
    pendingId = null
    error = null
    searching = false
    onCancel()
  }

  function placeOf(result) {
    // thesession.org's display_text repeats the name before the place more often
    // than not ("Celtic Crossing, Memphis, Tennessee, USA"), which reads as
    // stutter on a row that already shows the name.
    const text = result.display_text || ''
    const name = result.name || ''
    if (name && text.toLowerCase().startsWith(name.toLowerCase())) {
      return text.slice(name.length).replace(/^[,\s]+/, '')
    }
    return text
  }
</script>

<Sheet bind:open title="Add a Session" onCancel={cancel}>
  <div class="as-search">
    <SearchField
      bind:value={query}
      id="sessionUrl"
      debounce={450}
      onSearch={onQuery}
      placeholder="Session name, or a thesession.org link"
      aria-label="Search thesession.org for a session" />

    {#if error}
      <p class="as-error" id="errorAlert" role="alert">
        {error.text}
        {#if error.href}
          <a href={error.href} class="error-link">{error.linkText}</a>
        {/if}
      </p>
    {/if}

    {#if searching}
      <p class="as-status" id="loadingSpinner">Searching thesession.org…</p>
    {:else if pendingId}
      <!-- Bare digits: an offer rather than a guess. -->
      <div class="as-results" id="searchResultsList">
        <Row
          styled={false}
          rowClass="as-result"
          id="open-session-id"
          onclick={() => checkExistingSession(pendingId)}
          title="Open session {pendingId}"
          subtitle="thesession.org/sessions/{pendingId}">
          {#snippet trailing()}<Chevron class="kit-chev" />{/snippet}
        </Row>
      </div>
    {:else if results && results.length > 0}
      <div class="as-results" id="searchResultsList">
        {#each results as result (result.id)}
          <Row
            styled={false}
            rowClass="as-result search-result-item{result.exists_in_db ? ' existing' : ''}"
            onclick={() => pickSearchResult(result)}
            title={result.name}
            subtitle={placeOf(result)}>
            {#snippet trailing()}
              {#if result.exists_in_db}
                <span class="as-added existing-indicator">Already added</span>
              {/if}
              <Chevron class="kit-chev" />
            {/snippet}
          </Row>
        {/each}
      </div>
    {:else if results && results.length === 0}
      <p class="as-status" id="no-results">Nothing on thesession.org matches "{query.trim()}".</p>
    {:else if !query.trim()}
      <p class="as-status">
        Sessions come from thesession.org. Search for yours, or paste its link.
      </p>
    {/if}

    <!-- The way in for a session that isn't on thesession.org. It used to be a
         hyperlink inside a sentence, which made the only route for those sessions
         the least visible thing on the screen. -->
    <div class="as-results as-manual">
      <Row
        styled={false}
        rowClass="as-result"
        id="add-manually"
        onclick={addManually}
        title="Add a session manually"
        subtitle="For sessions that aren't on thesession.org">
        {#snippet trailing()}<Chevron class="kit-chev" />{/snippet}
      </Row>
    </div>
  </div>
</Sheet>

<!-- Stage 2, stacked over stage 1. Closing it uncovers the search, with the
     results still on screen — so picking the wrong pub costs one tap, not a
     retyped query. That is the whole reason the stages are two sheets rather
     than one screen that replaces itself. -->
<DetailsSheet
  bind:open={detailsOpen}
  seed={detailsSeed}
  {timezoneOptions}
  {addMeDefault}
  {navigate}
  back="Back" />

<!-- Picking a session that is already here is a decision, so it is a Dialog. -->
<Dialog
  bind:open={existingOpen}
  title="Already on ceol.io"
  description={`"${existingName}" is already here.`}
  confirmLabel="Open it"
  onConfirm={() => navigate(existingPath)} />

<style>
  .as-search {
    display: flex;
    flex-direction: column;
    gap: var(--sp-3, 12px);
  }

  /* The search box is the whole screen's purpose, so it is the first thing in it
     and it is full width. */
  .as-search :global(.kit-search-field) {
    width: 100%;
    padding: 10px var(--sp-6, 24px) 10px var(--sp-3, 12px);
    font: inherit;
    color: var(--text-color);
    background: var(--input-bg, #2d2d2d);
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r, 8px);
  }

  .as-search :global(.kit-search-field:focus) {
    outline: none;
    border-color: var(--primary, #65b464);
  }

  .as-status {
    margin: 0;
    padding: 0 var(--sp-1, 4px);
    font-size: 0.88rem;
    line-height: 1.45;
    color: var(--secondary-text, #888);
  }

  .as-error {
    margin: 0;
    padding: var(--sp-2, 8px) var(--sp-3, 12px);
    font-size: 0.88rem;
    color: var(--error-text, #ffb3b3);
    background: var(--error-bg, #5a2d2d);
    border-radius: var(--r-sm, 4px);
  }

  .as-error :global(.error-link) {
    color: inherit;
    text-decoration: underline;
    white-space: nowrap;
  }

  /* Rows in a card, the same shape the tune and session lists use. */
  .as-results {
    background: var(--input-bg, #2d2d2d);
    border-radius: var(--r-lg, 12px);
    overflow: hidden;
  }

  .as-manual {
    margin-top: var(--sp-2, 8px);
  }

  .as-results :global(.as-result) {
    min-height: 56px;
    padding: var(--sp-2, 8px) var(--sp-3, 12px);
    border-bottom: 1px solid var(--bg-color, #1a1a1a);
    cursor: pointer;
  }

  .as-results :global(.as-result:last-child) {
    border-bottom: none;
  }

  .as-results :global(.as-result:hover) {
    background: var(--hover-bg, #3d3d3d);
  }

  .as-results :global(.as-result .kit-row-sub) {
    font-size: 0.82rem;
    color: var(--secondary-text, #888);
  }

  /* A session already on ceol.io is still worth showing — it answers "is mine
     here?" — but it is not something you can add, so it recedes. */
  .as-results :global(.as-result.existing .kit-row-title) {
    color: var(--secondary-text, #888);
  }

  .as-added {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--secondary-text, #888);
  }

</style>
