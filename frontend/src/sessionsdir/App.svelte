<script>
  // i18n-converted
  // The /sessions directory (spec 035 Step 4a) — ported behavior-for-behavior from
  // the legacy inline script in templates/sessions.html. Same DOM contract
  // (#search-bar, #sessions-table, #sessions-tbody, #no-results — the e2e suite and
  // this bundle's page.css select on these). First paint comes from the embedded
  // payload; a background refetch of the same API keeps it fresh.
  import { formatTime } from '../shared/format.js'
  import { untrack } from 'svelte'
  import { SearchField, Seg, Toolbar, LoadError, t, tn } from '../lib/index.js'
  import { parseLocalDate } from '../shared/parse.js'
  import { locationLabel } from './logic.js'
  import AddSessionSheet from '../addsession/AddSessionSheet.svelte'

  let { pageData = null, isLoggedIn = false } = $props()

  // A place page (spec 055): /sessions/<town-or-metro> is this list scoped to the
  // place, under a heading that names it.
  const scope = untrack(() => pageData?.place || null)

  // Filter states cycle on the toggle button; logged-out users have no "My
  // Sessions"/"Visited". 'my' is member-strict (spec 033); 'visited' shows the
  // sessions the viewer has a visitor relationship with (spec 034).
  const filterStates = isLoggedIn
    ? ['my', 'visited', 'active', 'all', 'inactive']
    : ['active', 'all', 'inactive']
  const filterButtonLabels = {
    my: t('My Sessions'),
    visited: t('Visited'),
    active: t('All Active'),
    all: t('All'),
    inactive: t('Inactive'),
  }
  // The words after the count. English says "sessions" whatever the number (the two
  // forms are the same); Irish needs the number to choose the noun's form.
  function countLabel(filter, n) {
    if (filter === 'my') return tn(n, 'sessions in your list', 'sessions in your list')
    if (filter === 'visited') return tn(n, "sessions you've visited", "sessions you've visited")
    if (filter === 'active') return tn(n, 'active sessions', 'active sessions')
    if (filter === 'inactive') return tn(n, 'inactive sessions', 'inactive sessions')
    return tn(n, 'sessions', 'sessions')
  }

  let allSessions = $state([])
  let loaded = $state(false)
  let loadError = $state(false)
  // A place page opens on "All Active": it is about the place, not your list.
  let filterIndex = $state(scope ? filterStates.indexOf('active') : 0)
  let rawSearch = $state('')
  // Instant client-side filter (legacy behavior): derive from the bound value.
  const searchTerm = $derived(normalizeQuotes(rawSearch.toLowerCase()))

  const currentFilter = $derived(filterStates[filterIndex])

  // Normalize smart quotes to straight quotes (iOS keyboard compatibility).
  const normalizeQuotes = (str) =>
    str.replace(/[‘’]/g, "'").replace(/[“”]/g, '"')

  function adopt(sessions) {
    allSessions = sessions || []
    // Logged in but not a member of anything: default to "All Active" instead
    // of an empty "My Sessions" view (legacy behavior).
    if (isLoggedIn && filterStates[filterIndex] === 'my' && !allSessions.some((s) => s.user_is_member)) {
      filterIndex = filterStates.indexOf('active')
    }
    loaded = true
  }

  if (pageData && pageData.success) adopt(pageData.sessions)

  let retrying = $state(false)

  // Mount-once background refresh; a failure never blanks an already-shown list
  // (it stays silent then — the embedded list is real data). With nothing shown
  // yet, a failure says so with a Retry.
  function refresh() {
    retrying = loadError
    const url = scope
      ? `/api/sessions/with-today-status?place=${encodeURIComponent(scope.slug)}`
      : '/api/sessions/with-today-status'
    return fetch(url, { credentials: 'same-origin' })
      .then((r) => r.json())
      .then((d) => {
        if (d.success) adopt(d.sessions)
        else throw new Error(d.error || d.message || 'sessions load failed')
      })
      .catch((e) => {
        console.error('Error loading sessions:', e)
        if (!loaded) loadError = true
      })
      .finally(() => {
        retrying = false
      })
  }

  $effect(() => {
    untrack(() => refresh())
  })

  const filtered = $derived.by(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return allSessions.filter((session) => {
      let passes = false
      if (currentFilter === 'my') {
        passes = session.user_is_member
      } else if (currentFilter === 'visited') {
        passes = session.user_relationship === 'visitor'
      } else if (currentFilter === 'active') {
        passes = !session.termination_date || parseLocalDate(session.termination_date) > today
      } else if (currentFilter === 'all') {
        passes = true
      } else if (currentFilter === 'inactive') {
        passes = !!session.termination_date && parseLocalDate(session.termination_date) <= today
      }
      if (!passes) return false
      if (searchTerm) {
        const location = [session.place?.name, session.place?.area, session.place?.country]
          .filter(Boolean)
          .join(', ')
          .toLowerCase()
        return session.name.toLowerCase().includes(searchTerm) || location.includes(searchTerm)
      }
      return true
    })
  })

  // formatTime (shared): "7:00pm" in English, the 24-hour clock in Irish.
  function formatTimeRange(startTime, endTime) {
    if (!startTime) return ''
    const start = formatTime(startTime)
    return endTime ? `${start}-${formatTime(endTime)}` : start + ' - ?'
  }

  // The rule itself is in ./logic.js, where both of its branches can be tested:
  // every seeded session is in the USA, so a browser test can only ever see the
  // "drop my own country" half.
  const viewerCountry = pageData?.viewer_country || ''
  const locationOf = (s) => locationLabel(s, viewerCountry)

  function instanceLabel(session, instance) {
    const timeStr = formatTimeRange(instance.start_time, instance.end_time)
    const locationStr = instance.location_override || session.location_name || ''
    return [timeStr, locationStr].filter(Boolean).join(' @ ')
  }

  const goto = (url) => (window.location.href = url)

  // Adding a session is a sheet over this list, not a page you navigate to
  // (spec 052 §B9). /add-session still exists and still works — it redirects
  // here with ?add=1, which is what opens this.
  let addOpen = $state(untrack(() => new URLSearchParams(window.location.search).get('add') === '1'))

  // ?acu=false pre-unchecks "Add me as" (the admin sessions list links this way).
  const addMeDefault = untrack(
    () => new URLSearchParams(window.location.search).get('acu') !== 'false'
  )

  function openAdd(e) {
    e?.preventDefault()
    addOpen = true
  }

  // Arriving with ?add=1 should not leave it in the URL: reloading after you
  // cancelled would reopen the sheet you just dismissed.
  function clearAddParam() {
    const url = new URL(window.location.href)
    if (!url.searchParams.has('add')) return
    url.searchParams.delete('add')
    url.searchParams.delete('acu')
    window.history.replaceState({}, '', url.pathname + url.search + url.hash)
  }

  let searchField = $state(null)
  let panelVisible = $state(false)

  // "My Sessions" only shows memberships, so a missing session usually just
  // needs a wider filter — jump to "All" and put the cursor in the search box.
  function searchAllSessions(e) {
    e.preventDefault()
    filterIndex = filterStates.indexOf('all')
    searchField?.focus()
  }
</script>

<!-- No page heading (spec 052 §B1). The tab bar already says where you are, and the
     word "Sessions" over a list of sessions was a line of chrome between you and the
     list. The "What's a session?" link went with it; the help sidebar carries it. -->

{#if scope}
  <header class="place-heading" id="place-heading">
    <h1 class="place-name">{scope.name}</h1>
    <p class="place-where">
      {[scope.area, scope.country].filter(Boolean).join(', ')}
      {#if scope.parent}
        · {t('in')} <a href="/sessions/{scope.parent.slug}">{scope.parent.name}</a>
      {/if}
    </p>
    {#if scope.children?.length}
      <p class="place-children" id="place-children">
        {t('Includes')}
        {#each scope.children as child, i (child.slug)}
          <a href="/sessions/{child.slug}">{child.name}</a>{i < scope.children.length - 1 ? ', ' : ''}
        {/each}
      </p>
    {/if}
  </header>
{/if}

<!-- The same toolbar as My Tunes and the session tabs: search, a filter panel, and
     "+" — one control shape for "a list you can narrow", wherever you meet it. -->
<div class="filters-container">
  <Toolbar
    styled={false}
    toolbarClass="filter-top-row"
    buttonClass="filter-panel-toggle"
    filterId="filter-panel-toggle"
    panelId="filter-panel"
    bind:open={panelVisible}
    activeCount={currentFilter === filterStates[0] ? 0 : 1}
    addId={isLoggedIn ? 'add-session-link' : null}
    onAdd={isLoggedIn ? openAdd : null}
    addTitle={t('Add a session')}>
    {#snippet search()}
      <SearchField
        bind:this={searchField}
        bind:value={rawSearch}
        id="search-bar"
        inputClass="filter-search-input"
        wrapperClass="filter-search-wrap"
        styled={false}
        placeholder={t('Search by name or location...')} />
    {/snippet}

    {#snippet filter()}
      <Seg
        options={filterStates.map((id) => ({ id, label: filterButtonLabels[id] }))}
        value={currentFilter}
        onSelect={(id) => (filterIndex = filterStates.indexOf(id))}
        idAttr="data-session-filter"
        styled={false}
        segClass="filter-button-group"
        optClass="filter-sort-btn"
        aria-label={t('Which sessions to show')} />
    {/snippet}
  </Toolbar>
</div>

<!-- "3 sessions in your list", not "Showing 3 sessions in your list." — My Tunes
     says "10 tunes" in the same spot, and the extra words were the difference. -->
<!-- No count until the list has loaded: "0 sessions" over a failed or pending load
     would read as a real answer. -->
{#if loaded}
<div class="session-count" id="session-count">
  <span id="count-number">{filtered.length}</span>
  <span id="count-filter-type">{countLabel(currentFilter, filtered.length)}</span>
</div>
{/if}

{#if !loaded}
  <div id="loading-message" class="loading-message">
    {#if loadError}<LoadError message={t("Couldn't load sessions.")} onRetry={refresh} {retrying} />{:else}{t('Loading')}<span class="loading-dots">...</span>{/if}
  </div>
{:else if filtered.length === 0}
  <div id="no-results" class="no-sessions">{t('No sessions found.')}</div>
{:else}
  <!-- One line per session, like the tune lists: the name in full-strength text on
       the left, where the eye starts, and the place quiet and right-aligned. It was a
       three-column table with a header row, which is a lot of furniture for two
       fields. -->
  <div class="sessions-list" id="sessions-list">
    {#each filtered as session (session.session_id)}
      <a class="session-row" href="/sessions/{session.path}" data-session-path={session.path}>
        <span class="session-row-name">{session.name}</span>
        <span class="session-row-meta">
          {#if session.active_instances && session.active_instances.length === 1}
            <button
              class="today-action-btn btn-goto-today"
              onclick={(e) => {
                e.preventDefault()
                const night = session.active_instances[0]
                goto(`/sessions/${night.path || session.path}/${night.date}`)
              }}>{t('On Now')}</button>
          {:else if session.active_instances && session.active_instances.length > 1}
            <!-- A festival can have several rooms going at once; the select is the
                 only control here that has to stop the row's own navigation. -->
            <select
              class="today-action-btn btn-goto-today"
              id="dropdown-{session.session_id}"
              onclick={(e) => e.preventDefault()}
              onchange={(e) => e.target.value && goto(`/sessions/${e.target.value}`)}>
              <option value="">{t('On Now ...')}</option>
              {#each session.active_instances as instance (instance.session_instance_id)}
                <option value="{instance.path || session.path}/{instance.date}">{instanceLabel(session, instance)}</option>
              {/each}
            </select>
          {/if}
          {#if session.kind === 'festival'}
            <span class="session-row-kind">{t('Festival')}</span>
          {/if}
          {#if session.place && session.place.slug !== scope?.slug}
            <!-- The row is itself a link, so the place is a link by script: it takes
                 you to the place page (spec 055), which is how people find those. -->
            <span
              class="session-row-where session-row-place"
              role="link"
              tabindex="0"
              data-place={session.place.slug}
              onclick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                goto(`/sessions/${session.place.slug}`)
              }}
              onkeydown={(e) => {
                if (e.key !== 'Enter') return
                e.preventDefault()
                e.stopPropagation()
                goto(`/sessions/${session.place.slug}`)
              }}>{locationOf(session)}</span>
          {:else}
            <span class="session-row-where">{locationOf(session)}</span>
          {/if}
        </span>
      </a>
    {/each}
  </div>
{/if}

<!-- The one thing worth saying after the list, so it is centred under it rather
     than left-aligned like a caption. "Back to home" went with the page heading:
     the tab bar has a Home tab, and a link that repeats a tab is furniture. -->
<p class="sessions-footnote">
  {t("Don't see your session?")}<br />
  {#if currentFilter === 'my'}
    <a href="/sessions" onclick={searchAllSessions}>{t('Search all sessions')}</a> {t('or')}
    <a href="/add-session" onclick={openAdd}>{t('add it!')}</a>
  {:else}
    <a href="/add-session" onclick={openAdd}>{t('Add it!')}</a>
  {/if}
</p>

<AddSessionSheet bind:open={addOpen} {addMeDefault} onCancel={clearAddParam} />
