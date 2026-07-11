<script>
  // The Tunes tab: instant first paint from the embedded first 20 rows, async
  // /tunes/remaining merge (serializer dicts — the tuple reshaping hack is dead),
  // client-side search/type/my-status filtering with URL round-trip, selection
  // mode + the Copy To flow, and the add-tune pane hook (the bundled-in
  // SessionTuneAddApp, handed down from App via the addPane prop).
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import {
    filterAndSortTunes,
    resultsCountLabel,
    stateFromParams,
    applyStateToParams,
  } from './logic.js'

  let {
    active,
    session,
    permissions,
    tunes: initialTunes = [],
    totalTunesCount = 0,
    hasMoreTunes = false,
    deepLinkTuneId = null,
    addPane = () => null, // () => the bundled-in SessionTuneAddApp instance
  } = $props()

  const sessionPath = session.path
  const isLoggedIn = permissions.is_logged_in

  import { toast, SearchField, Chip } from '../lib/index.js'

  // ---- state ---------------------------------------------------------------
  let allTunes = $state([...initialTunes])
  let allTunesLoaded = $state(!hasMoreTunes)
  let loadingTunes = $state(false)
  let pendingTuneId = null // deep-linked tune to open once the full list arrives

  const initial = stateFromParams(new URLSearchParams(window.location.search), isLoggedIn)
  let filters = $state(initial.filters)
  let rawSearch = $state(initial.rawSearch)
  let sort = $state(initial.sort)
  let myStatusInstrument = $state(initial.myStatusInstrument)

  // Bumped when TunebookStatus finishes loading so derived filtering re-runs.
  let tunebookVersion = $state(0)
  let tunebookLoading = $state(false)
  let statusInstruments = $state([]) // shown only for 2+ instrument players

  let selectionMode = $state(false)
  const selectedTuneIds = new SvelteSet()

  let panelVisible = $state(false)
  let panelAnim = $state('') // '', 'opening', 'closing'

  // ---- derived ---------------------------------------------------------------
  const filteredTunes = $derived.by(() => {
    void tunebookVersion // re-filter/re-color once the tunebook loads
    return filterAndSortTunes(allTunes, filters, sort, myStatusInstrument)
  })
  const tuneTypes = $derived([...new Set(allTunes.map((t) => t.tune_type).filter(Boolean))].sort())
  const hasActiveFilters = $derived(!!(filters.type || filters.mystatus))
  const allVisibleSelected = $derived(
    filteredTunes.length > 0 && filteredTunes.every((t) => selectedTuneIds.has(t.tune_id))
  )
  const countText = $derived.by(() => {
    if (tunebookLoading) return 'Loading your tunebook…'
    if (loadingTunes) return `Loading all tunes... (${allTunes.length}/${totalTunesCount})`
    return resultsCountLabel(filteredTunes.length, allTunes.length)
  })
  const showInstScope = $derived(!!filters.mystatus && statusInstruments.length > 0)

  // My-tunebook row coloring (roll-up, same rules as the tune-detail modal).
  function rowStatus(tune) {
    void tunebookVersion
    const tb = window.TunebookStatus
    if (!filters.mystatus || !tb || !tb.isLoaded()) return null
    const st = tb.statusFor(tune.tune_id, myStatusInstrument)
    return { status: st, cls: tb.classFor(st) }
  }

  // ---- URL state (read once above; written on every filter/sort change) --------
  let urlInitialized = false
  $effect(() => {
    const params = applyStateToParams(
      new URLSearchParams(window.location.search),
      filters,
      sort,
      myStatusInstrument
    )
    if (!urlInitialized) {
      urlInitialized = true
      return
    }
    const q = params.toString()
    const newURL = window.location.pathname + (q ? '?' + q : '')
    window.history.replaceState({}, '', newURL)
  })

  // ---- data loading -------------------------------------------------------------
  function loadRemainingTunes() {
    if (allTunesLoaded || loadingTunes) return
    loadingTunes = true
    fetch(`/api/sessions/${sessionPath}/tunes/remaining`)
      .then((r) => r.json())
      .then((data) => {
        if (data.success && data.tunes) {
          // Serializer dicts, straight in — same shape as the embedded rows.
          allTunes = [...allTunes, ...data.tunes]
          allTunesLoaded = true
          if (pendingTuneId) {
            const tune = allTunes.find((t) => t.tune_id === pendingTuneId)
            if (tune) setTimeout(() => showTuneDetail(tune), 100)
            pendingTuneId = null
          }
        } else {
          throw new Error(data.message || 'Failed to load remaining tunes')
        }
      })
      .catch((error) => {
        console.error('Error loading remaining tunes:', error)
        // Mark as loaded to prevent infinite retry (legacy behavior).
        allTunesLoaded = true
        pendingTuneId = null
      })
      .finally(() => {
        loadingTunes = false
      })
  }

  $effect(() => {
    untrack(() => {
      if (!allTunesLoaded) setTimeout(loadRemainingTunes, 100)
      if (filters.mystatus) activateMyStatus() // ?mystatus= deep link
      checkForSuccessMessage()
      scrollToAndHighlightTune()
      if (deepLinkTuneId) {
        const tune = allTunes.find((t) => t.tune_id === deepLinkTuneId)
        if (tune) {
          setTimeout(() => showTuneDetail(tune), 100)
        } else if (!allTunesLoaded) {
          pendingTuneId = deepLinkTuneId
          loadRemainingTunes()
        }
      }
    })
  })

  // ---- search / filters -----------------------------------------------------------

  function toggleFilterPanel() {
    if (!panelVisible) {
      panelVisible = true
      panelAnim = 'opening'
      setTimeout(() => (panelAnim = ''), 300)
    } else {
      panelAnim = 'closing'
      setTimeout(() => {
        panelVisible = false
        panelAnim = ''
      }, 300)
    }
  }

  function setSortMode(sortType) {
    if (sort.type === sortType) {
      sort.dir = sort.dir === 'asc' ? 'desc' : 'asc'
      return
    }
    sort.type = sortType
    // Alpha defaults ascending; session/everywhere default descending.
    sort.dir = sortType === 'session' || sortType === 'everywhere' ? 'desc' : 'asc'
  }

  function clearFilters() {
    // Preserves the current search (legacy behavior).
    filters.type = ''
    filters.mystatus = ''
    myStatusInstrument = 'all'
  }

  // Engage the my-tunebook status view: lazy-load the list on first use, then
  // color/filter. A load failure resets the control rather than filtering on
  // an empty list.
  function activateMyStatus() {
    if (!filters.mystatus) return
    const tb = window.TunebookStatus
    if (tb && tb.isLoaded()) {
      populateMyStatusInstruments()
      tunebookVersion++
      return
    }
    if (!tb) return
    tunebookLoading = true
    tb.load()
      .then(() => {
        tunebookLoading = false
        populateMyStatusInstruments()
        tunebookVersion++
      })
      .catch(() => {
        tunebookLoading = false
        filters.mystatus = ''
      })
  }

  // Instrument scope droplist: only meaningful for 2+ instrument players.
  function populateMyStatusInstruments() {
    const instruments = window.TunebookStatus.getInstruments() || []
    if (instruments.length < 2) {
      statusInstruments = []
      return
    }
    statusInstruments = instruments.map((i) => i.instrument)
    if (!['all', ...statusInstruments].includes(myStatusInstrument)) {
      myStatusInstrument = 'all'
    }
  }

  // ---- tune detail / row clicks -----------------------------------------------------
  function showTuneDetail(tune) {
    window.TuneDetailModal.show({
      context: 'session',
      tuneId: tune.tune_id,
      apiEndpoint: `/api/sessions/${sessionPath}/tunes/${tune.tune_id}`,
      onSave: function () {
        // Reload to refresh the tune list
        window.location.reload()
      },
      additionalData: {
        sessionPath: sessionPath,
        tuneName: tune.tune_name,
        tuneType: tune.tune_type,
        isUserLoggedIn: isLoggedIn,
        isSessionAdmin: permissions.is_session_admin,
      },
    })
  }

  function handleTuneRowClick(tune) {
    if (selectionMode) {
      toggleTuneSelection(tune.tune_id)
      return
    }
    showTuneDetail(tune)
  }

  // ---- selection & copy -----------------------------------------------------------
  function toggleTuneSelection(tuneId) {
    if (selectedTuneIds.has(tuneId)) selectedTuneIds.delete(tuneId)
    else selectedTuneIds.add(tuneId)
  }

  function toggleSelectionMode() {
    selectionMode = !selectionMode
    if (!selectionMode) selectedTuneIds.clear()
  }

  function toggleSelectAll(event) {
    event.stopPropagation()
    if (allVisibleSelected) {
      filteredTunes.forEach((t) => selectedTuneIds.delete(t.tune_id))
    } else {
      filteredTunes.forEach((t) => selectedTuneIds.add(t.tune_id))
    }
  }

  function deselectAll() {
    selectedTuneIds.clear()
  }

  let copyOpen = $state(false)
  let copyStep = $state(1)
  let adminSessions = $state(null) // fetched once, cached
  let destLoading = $state(false)
  let destError = $state(false)
  let selectedDestination = $state(null)
  let selectedLearnStatus = $state('want to learn')
  let copying = $state(false)

  const learnStatuses = [
    ['want to learn', 'Want to Learn'],
    ['learning', 'Learning'],
    ['learned', 'Learned'],
  ]

  async function showCopyModal() {
    if (selectedTuneIds.size === 0) return
    copyStep = 1
    selectedDestination = null
    copyOpen = true
    if (adminSessions === null && !destLoading) {
      destLoading = true
      destError = false
      try {
        const response = await fetch('/api/user/admin-sessions')
        const data = await response.json()
        // Filter out the current session.
        adminSessions = data.success ? data.sessions.filter((s) => s.path !== sessionPath) : []
      } catch {
        destError = true
      }
      destLoading = false
    }
  }

  const copyConfirmMessage = $derived.by(() => {
    let destinationName
    if (selectedDestination === 'my_tunes') {
      destinationName = `My Tunes (as "${selectedLearnStatus}")`
    } else if (selectedDestination) {
      const destPath = selectedDestination.replace('session:', '')
      const dest = (adminSessions || []).find((s) => s.path === destPath)
      destinationName = dest ? dest.name : destPath
    } else {
      return ''
    }
    const n = selectedTuneIds.size
    return `${n} tune${n !== 1 ? 's' : ''} will be copied to ${destinationName}. Proceed?`
  })

  const copyWarning = $derived.by(() => {
    const visibleSelectedCount = filteredTunes.filter((t) => selectedTuneIds.has(t.tune_id)).length
    const totalSelectedCount = selectedTuneIds.size
    if (visibleSelectedCount !== totalSelectedCount && (filters.search || filters.type)) {
      return `Warning: This will copy all ${totalSelectedCount} selected tunes, not just the ${visibleSelectedCount} selected tunes visible right now with your filters and searches enabled!`
    }
    return ''
  })

  async function executeCopy() {
    if (!selectedDestination || selectedTuneIds.size === 0) return
    copying = true
    try {
      const payload = { tune_ids: Array.from(selectedTuneIds) }
      if (selectedDestination === 'my_tunes') {
        payload.destination_type = 'my_tunes'
        payload.learn_status = selectedLearnStatus
      } else {
        payload.destination_type = 'session'
        payload.destination_session_path = selectedDestination.replace('session:', '')
      }
      const response = await fetch('/api/tunes/copy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json()
      if (data.success) {
        // Message shows as a toast on the destination page.
        sessionStorage.setItem('copyTunesMessage', data.message)
        window.location.href = data.redirect_url
      } else {
        toast(data.error || 'Failed to copy tunes', 'error')
        copying = false
      }
    } catch {
      toast('An error occurred while copying tunes', 'error')
      copying = false
    }
  }

  // ---- add-tune pane (bundled-in SessionTuneAddApp, via the addPane prop) ----------
  function handleAddSessionTuneClick(event) {
    const pane = addPane()
    if (!pane) return // let the <a href> navigate to the legacy page
    event.preventDefault()
    pane.open({
      sessionPath: sessionPath,
      query: rawSearch.trim(),
      onAdded: function (tuneId, name) {
        // Land on the tunes tab with the existing toast + scroll/highlight flow.
        window.location.href =
          '/sessions/' + sessionPath + '/tunes?show=' + tuneId + '&added=' + encodeURIComponent(name || '')
      },
      onAlready: function (tuneId) {
        window.location.href = '/sessions/' + sessionPath + '/tunes?show=' + tuneId + '&already=1'
      },
    })
  }

  // ---- landing flows (?added / ?already / ?show) -----------------------------------
  function checkForSuccessMessage() {
    const params = new URLSearchParams(window.location.search)
    if (params.has('added')) {
      toast(`Successfully added "${params.get('added')}" to the session!`, 'success')
    } else if (params.has('already')) {
      toast('This tune is already on the session list', 'info')
    }
  }

  function stripLandingParams() {
    const params = new URLSearchParams(window.location.search)
    params.delete('show')
    params.delete('added')
    params.delete('already')
    const q = params.toString()
    const newURL = q ? `${window.location.pathname}?${q}` : window.location.pathname
    window.history.replaceState({}, '', newURL)
  }

  let hasScrolledToTune = false
  function scrollToAndHighlightTune() {
    if (hasScrolledToTune) return
    const params = new URLSearchParams(window.location.search)
    const hasShow = params.has('show')
    const hasAdded = params.has('added')
    const hasAlready = params.has('already')
    if (!(hasShow || hasAdded || hasAlready)) return
    hasScrolledToTune = true
    const tuneId = hasShow ? params.get('show') : null

    let attempts = 0
    const maxAttempts = 30 // 3 seconds max
    const pollForElement = () => {
      attempts++
      if (tuneId) {
        const tuneElement = document.querySelector(`[data-tune-id="${tuneId}"]`)
        if (tuneElement) {
          tuneElement.scrollIntoView({ behavior: 'instant', block: 'end' })
          const targetOffset = window.innerHeight * 0.33
          window.scrollBy({ top: targetOffset, behavior: 'instant' })
          setTimeout(() => {
            const startTime = Date.now()
            const duration = 3000
            const animate = () => {
              const progress = Math.min((Date.now() - startTime) / duration, 1)
              const alpha = 0.8 * (1 - progress)
              tuneElement.style.backgroundColor = `rgba(255, 243, 205, ${alpha})`
              if (progress < 1) requestAnimationFrame(animate)
              else tuneElement.style.backgroundColor = ''
            }
            requestAnimationFrame(animate)
          }, 100)
          stripLandingParams()
          return
        }
      }
      if (attempts < maxAttempts) setTimeout(pollForElement, 100)
      else stripLandingParams()
    }
    pollForElement()
  }

  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)
</script>

<!-- Tunes Tab Content -->
<div class="tab-content" class:active id="tunes-tab">
  <div class="tunes-container">
    <div class="filters-container">
      <div class="filter-top-row">
<SearchField
          bind:value={rawSearch}
          id="tune-search"
          inputClass="filter-search-input"
          wrapperClass="filter-search-wrap"
          styled={false}
          placeholder="Search"
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false"
          debounce={300}
          onSearch={(q) => (filters.search = q.toLowerCase().trim())} />
        {#if isLoggedIn}
          <a
            href="/sessions/{sessionPath}/tunes/add"
            class="filter-panel-toggle"
            id="add-session-tune-btn"
            title="Add tune"
            style="text-decoration: none; font-size: 24px; font-weight: 300; line-height: 1;"
            onclick={handleAddSessionTuneClick}>+</a>
        {/if}
        <button
          id="filter-panel-toggle"
          class="filter-panel-toggle"
          class:active={panelVisible || hasActiveFilters}
          title="Show filters"
          onclick={toggleFilterPanel}>
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="4" y1="21" x2="4" y2="14"></line>
            <line x1="4" y1="10" x2="4" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12" y2="3"></line>
            <line x1="20" y1="21" x2="20" y2="16"></line>
            <line x1="20" y1="12" x2="20" y2="3"></line>
            <line x1="1" y1="14" x2="7" y2="14"></line>
            <line x1="9" y1="8" x2="15" y2="8"></line>
            <line x1="17" y1="16" x2="23" y2="16"></line>
          </svg>
        </button>
      </div>

      {#if panelVisible}
        <div id="filter-panel" class="filter-panel {panelAnim}">
          <div class="filter-panel-row">
            <select id="type-filter" class="filter-panel-select" title="Tune type" bind:value={filters.type}>
              <option value="">All Tune Types</option>
              {#each tuneTypes as type (type)}
                <option value={type}>{cap(type)}</option>
              {/each}
            </select>
          </div>
          <div class="filter-panel-row">
            <div class="filter-button-group">
              <button class="filter-sort-btn" class:active={sort.type === 'alpha'} data-sort="alpha" onclick={() => setSortMode('alpha')}>a-z</button>
              <button class="filter-sort-btn" class:active={sort.type === 'session'} data-sort="session" onclick={() => setSortMode('session')}>session</button>
              <button class="filter-sort-btn" class:active={sort.type === 'everywhere'} data-sort="everywhere" onclick={() => setSortMode('everywhere')}>everywhere</button>
            </div>
            <button
              id="sort-direction-toggle"
              class="filter-sort-direction-btn"
              title="Toggle sort direction"
              onclick={() => (sort.dir = sort.dir === 'asc' ? 'desc' : 'asc')}>
              <span id="sort-direction-icon">{sort.dir === 'desc' ? '↓' : '↑'}</span>
            </button>
          </div>
          {#if isLoggedIn}
            <!-- My-tunebook status: colors every row by MY learn status (roll-up,
                 same rules as the tune-detail modal) and, past "all", filters to
                 one status. Instrument scope appears for 2+ instrument players. -->
            <div class="filter-panel-row">
              <select
                id="mystatus-filter"
                class="filter-panel-select"
                title="My tunebook status"
                bind:value={filters.mystatus}
                onchange={activateMyStatus}>
                <option value="">My Tunebook: off</option>
                <option value="all">Show My Status</option>
                <option value="not on list">Not On My List</option>
                <option value="want to learn">Want To Learn</option>
                <option value="learning">Learning</option>
                <option value="learned">Learned</option>
              </select>
              <select
                id="mystatus-inst"
                class="filter-panel-select"
                title="Instrument"
                style:display={showInstScope ? null : 'none'}
                bind:value={myStatusInstrument}>
                <option value="all">All Instruments</option>
                {#each statusInstruments as inst (inst)}
                  <option value={inst}>{inst}</option>
                {/each}
              </select>
            </div>
          {/if}
          <div class="filter-panel-actions">
            {#if hasActiveFilters}
              <button id="clear-filters-btn" class="filter-panel-clear-btn" onclick={clearFilters}>Clear Filters</button>
            {/if}
          </div>
          {#if isLoggedIn}
            <div class="selection-buttons">
              <button id="select-tunes-btn" class="selection-btn" onclick={toggleSelectionMode}>
                {selectionMode ? 'Cancel Selection' : 'Select Tunes...'}
              </button>
              <button id="copy-to-btn" class="selection-btn primary" disabled={selectedTuneIds.size === 0} onclick={showCopyModal}>And Copy To...</button>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <div class="results-count">
      <span id="results-count-text">{countText}</span>
      <div class="select-all-row" id="select-all-row" class:visible={selectionMode}>
        <input
          type="checkbox"
          id="select-all-checkbox"
          class="tune-select-checkbox"
          checked={allVisibleSelected}
          onclick={toggleSelectAll} />
        <label for="select-all-checkbox" id="select-all-label">Select all</label>
        <span
          id="deselect-link"
          class="deselect-link"
          style:display={selectedTuneIds.size > 0 ? 'inline' : 'none'}
          onclick={deselectAll}>(Clear)</span>
      </div>
    </div>

    <div class="tunes-list" id="tunes-list">
      {#if filteredTunes.length === 0 && filters.search}
        <div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);">
          <p style="margin-bottom: 20px;">No tunes found matching "{filters.search}"</p>
          {#if isLoggedIn}
            <a
              href="/sessions/{sessionPath}/tunes/add?q={encodeURIComponent(filters.search)}"
              class="btn btn-primary"
              style="padding: 12px 24px; background-color: var(--primary); color: white; text-decoration: none; border-radius: 4px; display: inline-block;"
              onclick={handleAddSessionTuneClick}>
              Add Tune
            </a>
          {/if}
        </div>
      {:else}
        {#each filteredTunes as tune (tune.tune_id)}
          {@const st = rowStatus(tune)}
          <div
            class="tune-row{selectionMode ? ' selection-mode' : ''}{st ? ' ' + st.cls : ''}"
            data-tune-id={tune.tune_id}
            onclick={() => handleTuneRowClick(tune)}>
            <div class="tune-row-header">
              <input
                type="checkbox"
                class="tune-select-checkbox"
                data-tune-id={tune.tune_id}
                checked={selectedTuneIds.has(tune.tune_id)}
                onclick={(e) => {
                  e.stopPropagation()
                  toggleTuneSelection(tune.tune_id)
                }} />
              <h3 class="tune-name">{tune.tune_name || 'Unknown'}</h3>
            </div>
            <div class="tune-meta">
              {#if st}<Chip label={st.status} styled={false} chipClass="ls-chip {st.cls}" />{/if}
              {#if tune.tune_type}<Chip label={tune.tune_type} styled={false} chipClass="tune-type" />{/if}
              {#if sort.type === 'session'}
                <Chip label={String(tune.play_count || 0)} styled={false} chipClass="tune-count-badge" />
              {:else if sort.type === 'everywhere'}
                <Chip label={String(tune.tunebook_count || 0)} styled={false} chipClass="tune-count-badge" />
              {/if}
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Tune Detail Modal container is provided app-wide by base.html -->

  <!-- Copy Tunes Modal -->
  {#if isLoggedIn}
    <div
      id="copy-modal-overlay"
      class="copy-modal-overlay"
      class:hidden={!copyOpen}
      onclick={(e) => {
        if (e.target === e.currentTarget) copyOpen = false
      }}>
      <div class="copy-modal">
        {#if copyStep === 1}
          <div id="copy-modal-step-1">
            <h3 id="copy-modal-title">Copy the {selectedTuneIds.size} selected tune{selectedTuneIds.size !== 1 ? 's' : ''} to:</h3>
            <div class="copy-modal-destinations" id="copy-destinations">
              {#if destLoading}
                <p style="color: var(--text-muted);">Loading destinations...</p>
              {:else if destError}
                <p style="color: #dc3545;">Failed to load destinations. Please try again.</p>
              {:else}
                <div
                  class="copy-destination-option"
                  class:selected={selectedDestination === 'my_tunes'}
                  onclick={() => (selectedDestination = 'my_tunes')}>
                  <input type="radio" name="destination" value="my_tunes" checked={selectedDestination === 'my_tunes'} />
                  <span>My Tunes</span>
                  <div
                    class="my-tunes-status-options"
                    id="my-tunes-status-options"
                    class:visible={selectedDestination === 'my_tunes'}>
                    {#each learnStatuses as [value, label] (value)}
                      <label><input
                          type="radio"
                          name="learn_status"
                          {value}
                          checked={selectedLearnStatus === value}
                          onclick={(e) => {
                            e.stopPropagation()
                            selectedLearnStatus = value
                          }} /> {label}</label>
                    {/each}
                  </div>
                </div>
                {#each adminSessions || [] as dest (dest.path)}
                  <div
                    class="copy-destination-option"
                    class:selected={selectedDestination === 'session:' + dest.path}
                    onclick={() => (selectedDestination = 'session:' + dest.path)}>
                    <input type="radio" name="destination" value={'session:' + dest.path} checked={selectedDestination === 'session:' + dest.path} />
                    <span>{dest.name}</span>
                  </div>
                {/each}
              {/if}
            </div>
            <div class="copy-modal-actions">
              <button class="selection-btn" onclick={() => (copyOpen = false)}>Cancel</button>
              <button id="copy-next-btn" class="selection-btn primary" disabled={!selectedDestination} onclick={() => (copyStep = 2)}>Next</button>
            </div>
          </div>
        {:else}
          <div id="copy-modal-step-2">
            <h3 id="copy-confirm-title">Confirm Copy</h3>
            <p id="copy-confirm-message">{copyConfirmMessage}</p>
            {#if copyWarning}
              <div id="copy-warning" class="copy-modal-warning">{copyWarning}</div>
            {/if}
            <div class="copy-modal-actions">
              <button class="selection-btn" onclick={() => (copyStep = 1)}>Back</button>
              <button id="copy-confirm-btn" class="selection-btn primary" disabled={copying} onclick={executeCopy}>
                {copying ? 'Copying...' : 'Copy Them!'}
              </button>
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
