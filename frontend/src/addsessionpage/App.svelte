<script>
  // The /add-session wizard (spec 035 final migration) — ported behavior-for-
  // behavior from the legacy inline script in templates/add_session.html. Same
  // DOM contract (#sessionUrlForm, #sessionUrl, the "Add A New Session" h1 —
  // the e2e suite selects on these). Public page: anyone can search/review;
  // only the final POST /api/add-session is login-gated.
  import { untrack } from 'svelte'
  import { Dialog } from '../lib/index.js'
  import SessionSheet from './SessionSheet.svelte'
  import { parseSessionInput, parseTheSessionRecurrence, generatePath, guessTimezone } from './logic.js'

  let { pageData = null, navigate = (url) => window.location.assign(url) } = $props()

  const timezoneOptions = pageData?.timezone_options ?? []
  const defaultTimezone = pageData?.default_timezone ?? 'America/Chicago'

  // ?acu=false pre-unchecks "Add me as" (the admin sessions list links this way).
  const addMeDefault = untrack(
    () => new URLSearchParams(window.location.search).get('acu') !== 'false'
  )

  // ---- wizard state -----------------------------------------------------------
  let urlInput = $state('')
  let loading = $state(false)
  let error = $state(null) // { text, href?, linkText? }
  let errorTimeout = null
  let results = $state([])
  let resultsVisible = $state(false)
  let urlInputEl = $state(null)

  // ---- existing-session decision (kit Dialog: decisions are Dialogs) -----------
  let existingOpen = $state(false)
  let existingName = $state('')
  let existingPath = $state('')

  // ---- details sheet ------------------------------------------------------------
  let sheetOpen = $state(false)
  let sheetSeed = $state(null)

  function showError(text, href = null, linkText = null) {
    error = { text, href, linkText }
    clearTimeout(errorTimeout)
    errorTimeout = setTimeout(() => (error = null), 5000)
  }

  function submitUrlForm(e) {
    e.preventDefault()
    const parsed = parseSessionInput(urlInput)
    if (parsed.kind === 'id') checkExistingSession(parsed.id)
    else searchSessions(parsed.query)
  }

  function checkExistingSession(sessionId) {
    loading = true
    fetch('/api/check-existing-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((response) => response.json())
      .then((data) => {
        loading = false
        if (data.exists) {
          showError(`Session ${sessionId} is already in the database at:`, data.session_path, data.session_path)
        } else {
          fetchSessionData(sessionId)
        }
      })
      .catch((err) => {
        loading = false
        console.error('Error:', err)
        showError('Error checking existing session. Please try again.')
      })
  }

  function searchSessions(query) {
    loading = true
    resultsVisible = false
    fetch('/api/search-sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })
      .then((response) => response.json())
      .then((data) => {
        loading = false
        if (data.success) {
          if (data.results.length === 0) {
            showError(`No sessions found for "${query}". Try a different search term.`)
          } else {
            results = data.results
            resultsVisible = true
          }
        } else {
          showError(data.message || 'Failed to search sessions')
        }
      })
      .catch((err) => {
        loading = false
        console.error('Error:', err)
        showError('Error searching sessions. Please try again.')
      })
  }

  function pickSearchResult(result) {
    if (result.exists_in_db) {
      existingName = result.name
      existingPath = result.session_path
      existingOpen = true
    } else {
      resultsVisible = false
      checkExistingSession(String(result.id))
    }
  }

  function fetchSessionData(sessionId) {
    loading = true
    fetch('/api/fetch-session-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((response) => response.json())
      .then((data) => {
        loading = false
        if (data.success) {
          openSheetFromSessionData(data.session_data)
        } else {
          showError(data.message || 'Failed to fetch session data')
        }
      })
      .catch((err) => {
        loading = false
        console.error('Error:', err)
        showError('Error fetching session data. Please try again.')
      })
  }

  function openSheetFromSessionData(d) {
    const schedule =
      d.recurrence || d.comments ? parseTheSessionRecurrence(d.recurrence, d.comments) : null
    let unparsedText = null
    if (!schedule && d.recurrence) {
      const recurrenceText = Array.isArray(d.recurrence) ? d.recurrence.join(' ') : d.recurrence
      // (an empty schedule array is truthy — don't show the notice for "")
      if (recurrenceText) unparsedText = `Couldn't parse schedule from: "${recurrenceText}"`
    }
    sheetSeed = {
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
    sheetOpen = true
  }

  function openEmptySession(e) {
    e.preventDefault()
    sheetSeed = { timezone: defaultTimezone, schedule: null, unparsedText: null }
    sheetOpen = true
  }

  function newSearch() {
    resultsVisible = false
    urlInputEl?.focus()
  }
</script>

<article class="docs-article">
  <header class="docs-header">
    <h1 class="docs-heading">Add A New Session</h1>
    <section class="docs-intro">
      <p>To add your session to the site, you can:</p>
      <ul>
        <li>Search by name or location: <code>memphis</code> or <code>murphy's pub</code></li>
        <li>Paste the session ID (<code>6247</code>) or URL: <code>https://thesession.org/sessions/6247</code></li>
      </ul>
      <p>
        We'll pull all the details from TheSession.org. If you don't have your session on that
        site, you can <a href="https://thesession.org/sessions/add#step1" target="_blank">put it there first</a>,
        or <a href="/add-session#here" onclick={openEmptySession}>just add it here</a>.
      </p>
    </section>
  </header>
  <div class="docs-body">
    <section>
      {#if loading}
        <div class="alert alert-info" id="loadingSpinner">
          <i class="fas fa-spinner fa-spin"></i> Fetching session data from TheSession.org...
        </div>
      {/if}

      {#if error}
        <div class="alert alert-danger" id="errorAlert" role="alert">
          {error.text}
          {#if error.href}
            <a href={error.href} class="error-link">{error.linkText}</a>
          {/if}
        </div>
      {/if}

      <form id="sessionUrlForm" onsubmit={submitUrlForm}>
        <div class="mb-3">
          <label for="sessionUrl" class="form-label">Session URL, ID, or search term:</label>
          <input
            type="text"
            class="form-control"
            id="sessionUrl"
            placeholder="e.g. 'memphis' or a URL"
            required
            bind:value={urlInput}
            bind:this={urlInputEl} />
        </div>
        <button type="submit" class="btn btn-primary">Next</button>
      </form>

      {#if resultsVisible}
        <div id="searchResults">
          <h4>Search Results:</h4>
          <div class="search-results-container">
            <div id="searchResultsList">
              {#each results as result (result.id)}
                <div
                  class="search-result-item"
                  class:existing={result.exists_in_db}
                  role="button"
                  tabindex="0"
                  onclick={() => pickSearchResult(result)}
                  onkeydown={(e) => e.key === 'Enter' && pickSearchResult(result)}>
                  <strong>{result.name}</strong><br />{result.display_text}
                  {#if result.exists_in_db}
                    <div class="existing-indicator">Already in ceol.io</div>
                  {/if}
                </div>
              {/each}
            </div>
            <button type="button" class="btn btn-secondary" id="newSearchBtn" onclick={newSearch}>
              Search again
            </button>
          </div>
        </div>
      {/if}
    </section>
  </div>
</article>

<!-- Existing-session decision: go view it, or stay on the search results -->
<Dialog
  bind:open={existingOpen}
  title="Session Already Exists"
  description={`"${existingName}" is already in ceol.io; click "Go" to view it.`}
  confirmLabel="Go"
  onConfirm={() => navigate(existingPath)} />

<SessionSheet bind:open={sheetOpen} seed={sheetSeed} {timezoneOptions} {addMeDefault} {navigate} />
