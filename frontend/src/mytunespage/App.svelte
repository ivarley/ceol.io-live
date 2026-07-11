<script>
  // The My Tunes page view (spec 035 Step 2). First paint comes from the
  // server-embedded payload (window.__PAGE_DATA__ — the exact /api/my-tunes
  // shape); everything after is client-side over the same API. All the page's
  // globals (MyTunesOffline, TuneDetailModal, TunebookStatus, AccentUtils,
  // showMessage, CeolOffline) come from base.html, exactly as before.
  import { untrack } from 'svelte'
  import AddTuneApp from '../mytunes/AddTuneApp.svelte'
  import TuneCard from './TuneCard.svelte'
  import { extractTuneId } from '../shared/parse.js'
  import {
    resolveTuneInstrumentStatus,
    filterAndSort,
    noResultsMessage,
    resultsCountText,
    typeBadgeLabel,
    stateFromParams,
    paramsFromState,
    overlayPendingOps,
    submitOp,
    nextStatus,
    cycleInstrumentOverride,
    fetchAllTunes,
  } from './logic.js'

  let { pageData = null } = $props()

  import { toast, SearchField } from '../lib/index.js'

  // ---- state -----------------------------------------------------------------
  const initial = stateFromParams(new URLSearchParams(window.location.search))
  let filters = $state(initial.filters)
  let sort = $state(initial.sort)
  let rawSearch = $state(initial.filters.search)

  let allTunes = $state([])
  let instruments = $state([])
  let fullTunesLoaded = $state(false) // suppresses no-results/count until the list is complete
  let fetchingMore = $state(false)
  let loadFailed = $state(false)

  // Reactive breakpoint — fixes the legacy render-time innerWidth bug (rotating
  // a tablet across 768px left the wrong card markup).
  const mq = window.matchMedia('(max-width: 768px)')
  let isMobile = $state(mq.matches)
  mq.addEventListener('change', (e) => (isMobile = e.matches))

  // ---- derived ----------------------------------------------------------------
  const visible = $derived(filterAndSort(allTunes, filters, sort, instruments))
  const tuneTypes = $derived([...new Set(allTunes.map((t) => t.tune_type).filter(Boolean))].sort())
  const hasActiveFilters = $derived(!!(filters.type || filters.status || filters.instrument))
  const matches = $derived(visible.filter((t) => !t._instDimmed))
  const dimmedTunes = $derived(visible.filter((t) => t._instDimmed))

  // ---- data loading -------------------------------------------------------------
  const sortParam = () => `${sort.type}-${sort.dir === 'desc' ? 'desc' : 'asc'}`

  function adopt(serverTunes, serverInstruments, complete) {
    return overlayPendingOps(serverTunes).then((merged) => {
      allTunes = merged
      if (serverInstruments) instruments = serverInstruments
      if (complete) fullTunesLoaded = true
    })
  }

  // Full refetch (all pages — follows pagination past the 2000-row cap, fixing
  // the legacy silent truncation). A failure never blanks an already-shown list.
  function loadTunes() {
    fetchingMore = true
    return fetchAllTunes(sortParam())
      .then((d) => {
        loadFailed = false
        return adopt(d.tunes, d.instruments, true)
      })
      .catch(() => {
        if (allTunes.length === 0) {
          loadFailed = true
          toast('Server error. Please try again.', 'error')
        }
      })
      .finally(() => {
        fetchingMore = false
      })
  }

  // First paint from the embed (no loading flash), then refresh from the API in
  // the background (also picks up pages the embed didn't include).
  if (pageData && pageData.tunes) {
    adopt(pageData.tunes, pageData.instruments, !(pageData.pagination || {}).has_next)
  }

  $effect(() => {
    // untrack: this is a mount-once effect — a sort change must NOT refetch
    // (sorting is client-side; the server sort param only orders the fetch).
    untrack(() => loadTunes())
    if (window.CeolOffline) window.CeolOffline.sync()

    // When queued offline ops finish syncing (on reconnect), re-fetch so the
    // newly-synced tunes lose their "pending" marker without a manual reload.
    const onSynced = () => loadTunes()
    window.addEventListener('mytunes-synced', onSynced)
    return () => window.removeEventListener('mytunes-synced', onSynced)
  })

  // ---- URL <-> state ------------------------------------------------------------
  $effect(() => {
    const params = paramsFromState(filters, sort)
    const q = params.toString()
    const newURL = q ? `${window.location.pathname}?${q}` : window.location.pathname
    // Never clobber one-shot landing params (?show/?added/?already/?ptid) before
    // their handlers strip them.
    const current = new URLSearchParams(window.location.search)
    if (current.has('show') || current.has('added') || current.has('already') || current.has('ptid')) return
    window.history.replaceState({}, '', newURL)
  })


  // ---- filter panel / dropdowns ---------------------------------------------------
  let panelOpen = $state(false)
  let panelAnim = $state('') // '', 'opening', 'closing'
  let panelVisible = $state(false)
  function toggleFilterPanel() {
    if (!panelVisible) {
      panelVisible = true
      panelOpen = true
      panelAnim = 'opening'
      setTimeout(() => (panelAnim = ''), 300)
    } else {
      panelAnim = 'closing'
      panelOpen = false
      setTimeout(() => {
        panelVisible = false
        panelAnim = ''
      }, 300)
    }
  }

  let typeMenuOpen = $state(false)
  let instMenuOpen = $state(false)
  $effect(() => {
    if (!typeMenuOpen && !instMenuOpen) return
    const handler = (e) => {
      if (!e.target.closest('.inst-select')) {
        typeMenuOpen = false
        instMenuOpen = false
      }
    }
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  })

  const cap = (s) => s.replace(/\b\w/g, (c) => c.toUpperCase())
  const typeLabelText = $derived(
    filters.type ? cap(filters.type) : 'All Tune Types'
  )
  const instLabelText = $derived.by(() => {
    if (filters.instrument) return filters.instrument
    // On desktop there's room to spell out what "all" means.
    if (!isMobile && instruments.length >= 2) {
      const names = instruments.map((i) => i.instrument)
      const listing =
        names.length === 2
          ? names.join(' and ')
          : names.slice(0, -1).join(', ') + ', and ' + names[names.length - 1]
      return 'All My Instruments (' + listing + ')'
    }
    return 'All My Instruments'
  })

  // Active-filter pills, shown only while the panel is collapsed.
  const pills = $derived.by(() => {
    if (panelVisible) return []
    const out = []
    if (filters.status) out.push({ key: 'status', label: cap(filters.status) })
    if (filters.type) out.push({ key: 'type', label: cap(filters.type) })
    if (filters.instrument) out.push({ key: 'instrument', label: filters.instrument })
    return out
  })
  function removeFilterPill(key) {
    if (key === 'status') filters.status = ''
    else if (key === 'type') filters.type = ''
    else if (key === 'instrument') filters.instrument = ''
  }

  function clearFilters() {
    // Keeps the search; resets the secondary sort (legacy behavior).
    filters.type = ''
    filters.status = ''
    filters.instrument = ''
    sort.type2 = null
    sort.dir2 = null
  }

  // ---- sorting -----------------------------------------------------------------
  function setSortMode(type) {
    if (sort.type === type) {
      sort.dir = sort.dir === 'asc' ? 'desc' : 'asc'
      return
    }
    // Demote the current primary to secondary, keeping its direction.
    sort.type2 = sort.type
    sort.dir2 = sort.dir
    sort.type = type
    sort.dir = type === 'popularity' || type === 'heard' || type === 'plays' ? 'desc' : 'asc'
  }

  // ---- writes -------------------------------------------------------------------
  function replaceTune(tuneId, patch) {
    allTunes = allTunes.map((t) => (t.tune_id === tuneId ? { ...t, ...patch } : t))
  }

  // Tap the status badge: cycle want to learn -> learning -> learned. Optimistic,
  // offline-queued, reverted only on a server rejection.
  function cycleStatus(tune, displayStatus, isInstrument) {
    if (isInstrument) {
      const inst = instruments.find(
        (i) => i.instrument.toLowerCase() === filters.instrument.toLowerCase()
      )
      if (!inst) return
      const next = nextStatus(displayStatus)
      const prev = { ...(tune.instrument_status || {}) }
      replaceTune(tune.tune_id, {
        instrument_status: cycleInstrumentOverride(tune, inst, next),
      })
      submitOp({
        type: 'set_instrument_status',
        tune_id: tune.tune_id,
        instrument: inst.instrument,
        status: next,
      })
        .then((res) => {
          if (res && res.queued) replaceTune(tune.tune_id, { pending_sync: true })
        })
        .catch(() => {
          replaceTune(tune.tune_id, { instrument_status: prev })
          toast('Could not change status. Please try again.', 'error')
        })
    } else {
      const next = nextStatus(tune.learn_status)
      const prev = tune.learn_status
      replaceTune(tune.tune_id, { learn_status: next })
      submitOp({ type: 'set_status', tune_id: tune.tune_id, learn_status: next })
        .then((res) => {
          if (res && res.queued) replaceTune(tune.tune_id, { pending_sync: true })
        })
        .catch(() => {
          replaceTune(tune.tune_id, { learn_status: prev })
          toast('Could not change status. Please try again.', 'error')
        })
    }
  }

  // Heard +: optimistic with a "N -> N+1" toast; sent as an ABSOLUTE set_heard so
  // a queued replay can't double-count. Reverts only on a server rejection.
  function incrementHeard(tune) {
    const oldCount = tune.heard_count || 0
    const newCount = oldCount + 1
    toast(`Heard count: ${oldCount} → ${newCount}`, 'success')
    replaceTune(tune.tune_id, { heard_count: newCount })
    submitOp({ type: 'set_heard', tune_id: tune.tune_id, heard_count: newCount })
      .then((res) => {
        // Online: sync the authoritative count. Offline (queued): keep optimistic UI.
        if (res && res.data && typeof res.data.heard_count === 'number' && res.data.heard_count !== newCount) {
          replaceTune(tune.tune_id, { heard_count: res.data.heard_count })
        }
      })
      .catch(() => {
        replaceTune(tune.tune_id, { heard_count: oldCount })
        toast('An error occurred. Please try again.', 'error')
      })
  }

  // ---- detail modal (Step 3 converts this; for now the shared legacy drawer) ----
  function showTuneDetail(personTuneId) {
    // Loose compare: pending offline-added tunes have a string 'pending-<id>'
    // person_tune_id, real ones a number.
    const tune = allTunes.find((t) => String(t.person_tune_id) === String(personTuneId))
    window.TuneDetailModal.show({
      context: 'my_tunes',
      tuneId: tune ? tune.tune_id : null,
      apiEndpoint: `/api/my-tunes/${personTuneId}`,
      onSave: () => loadTunes(),
      // Filtering by an instrument means you care about per-instrument statuses,
      // so open the modal with those rows already revealed.
      expandInstrumentStatus: filters.instrument ? true : undefined,
      onStatusChange: (change) => {
        // Statuses auto-save in the modal — mirror into our data so the list
        // behind the modal updates immediately.
        const t = allTunes.find((x) => x.tune_id === change.tune_id)
        if (!t) return
        replaceTune(change.tune_id, {
          learn_status: change.learn_status,
          instrument_status: change.instrument_status,
        })
      },
      additionalData: {
        personTuneId: personTuneId,
        tuneName: tune ? tune.tune_name : 'Loading...',
        tuneType: tune ? tune.tune_type : '',
        isUserLoggedIn: true,
      },
    })
  }

  // ---- add pane (bundled-in AddTuneApp; formerly window.MyTunesAddPane) ---------
  let addPane = $state(null)
  function handleAddTuneClick(event) {
    event.preventDefault()
    addPane.open({
      query: rawSearch.trim(),
      instruments,
      onAdded: (tuneId, name) => afterPaneAdd(tuneId, name, false),
      onAlready: (tuneId, name) => afterPaneAdd(tuneId, name, true),
    })
  }
  const addTuneHref = $derived(
    rawSearch.trim() ? `/my-tunes/add?q=${encodeURIComponent(rawSearch.trim())}` : '/my-tunes/add'
  )

  // After the pane adds (or finds we already have) a tune: reuse the existing
  // ?show/?added/?already landing flow — same toast, scroll + highlight, cleanup.
  function afterPaneAdd(tuneId, name, already) {
    const params = new URLSearchParams(window.location.search)
    params.delete('show')
    params.delete('added')
    params.delete('already')
    params.set('show', tuneId)
    if (already) params.set('already', '1')
    else params.set('added', name || '')
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
    loadTunes()
    checkForSuccessMessage()
    scrollToAndHighlightTune()
  }

  // ---- landing flows (?added / ?already / ?show / ?ptid / sessionStorage) -------
  function checkForSuccessMessage() {
    const params = new URLSearchParams(window.location.search)
    if (params.has('added')) toast(`Successfully added "${params.get('added')}" to your collection!`, 'success')
    else if (params.has('already')) toast('This tune is already on your list', 'info')
  }

  function stripLandingParams() {
    const params = new URLSearchParams(window.location.search)
    params.delete('show')
    params.delete('added')
    params.delete('already')
    const q = params.toString()
    window.history.replaceState({}, '', q ? `${window.location.pathname}?${q}` : window.location.pathname)
  }

  // Scroll the landed-on tune ~1/3 down the viewport and fade a yellow highlight,
  // then strip the one-shot params (legacy flow, ported).
  function scrollToAndHighlightTune() {
    const params = new URLSearchParams(window.location.search)
    if (!(params.has('show') || params.has('added') || params.has('already'))) return
    const tuneId = params.get('show')
    let attempts = 0
    const poll = () => {
      attempts++
      if (tuneId) {
        const el = document.querySelector(`[data-tune-id="${tuneId}"]`)
        if (el) {
          el.scrollIntoView({ behavior: 'instant', block: 'start' })
          const targetOffset = Math.max(120, window.innerHeight * 0.33)
          window.scrollBy({ top: -targetOffset, behavior: 'instant' })
          const card = el.querySelector('.tune-card') || el
          setTimeout(() => {
            const startTime = Date.now()
            const animate = () => {
              const progress = Math.min((Date.now() - startTime) / 3000, 1)
              card.style.backgroundColor = `rgba(255, 243, 205, ${0.8 * (1 - progress)})`
              if (progress < 1) requestAnimationFrame(animate)
              else card.style.backgroundColor = ''
            }
            requestAnimationFrame(animate)
          }, 100)
          stripLandingParams()
          return
        }
      }
      if (attempts < 30) setTimeout(poll, 100)
      else stripLandingParams()
    }
    setTimeout(poll, 100)
  }

  // Deep link ?ptid=<person_tune_id>: open the detail drawer once the tune shows
  // up (poll <=5s), else open anyway — the drawer fetches its own data.
  function waitForTuneAndOpen(personTuneId, attempts = 0) {
    const tune = allTunes.find((t) => String(t.person_tune_id) === String(personTuneId))
    if (tune) showTuneDetail(personTuneId)
    else if (attempts < 20) setTimeout(() => waitForTuneAndOpen(personTuneId, attempts + 1), 250)
    else showTuneDetail(personTuneId)
  }

  $effect(() => {
    checkForSuccessMessage()
    // sessionStorage handoffs: /me/and/<id> copy flow, offline add in the drawer.
    const copyMsg = sessionStorage.getItem('copyTunesMessage')
    if (copyMsg) {
      sessionStorage.removeItem('copyTunesMessage')
      toast(copyMsg, 'success')
    }
    const offlineToast = sessionStorage.getItem('myTunesToast')
    if (offlineToast) {
      sessionStorage.removeItem('myTunesToast')
      toast(offlineToast, 'success')
    }
    scrollToAndHighlightTune()
    const ptid = window.TuneDetailModal && window.TuneDetailModal.getTuneIdFromUrl
      ? window.TuneDetailModal.getTuneIdFromUrl()
      : null
    if (ptid) waitForTuneAndOpen(ptid)
  })

  // Swipe right on the shared drawer closes it (mobile) — ported from the legacy
  // page, which owned this enhancement of the app-wide modal.
  $effect(() => {
    const dialog = document.querySelector('#tune-detail-modal .modal-dialog') ||
      document.querySelector('.modal-dialog')
    if (!dialog) return
    let startX = 0
    let startY = 0
    let isSwiping = false
    const isControl = (t) => ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(t.tagName)
    const onStart = (e) => {
      if (isControl(e.target)) return
      startX = e.touches[0].clientX
      startY = e.touches[0].clientY
      isSwiping = false
    }
    const onMove = (e) => {
      if (!startX || isControl(e.target)) return
      const dx = e.touches[0].clientX - startX
      const dy = e.touches[0].clientY - startY
      if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) isSwiping = true
    }
    const onEnd = (e) => {
      if (!startX || !isSwiping || isControl(e.target)) {
        startX = 0
        isSwiping = false
        return
      }
      const dx = e.changedTouches[0].clientX - startX
      const dy = e.changedTouches[0].clientY - startY
      if (dx > 50 && Math.abs(dx) > Math.abs(dy) * 2 && window.TuneDetailModal) {
        window.TuneDetailModal.close()
      }
      startX = 0
      isSwiping = false
    }
    dialog.addEventListener('touchstart', onStart, { passive: true })
    dialog.addEventListener('touchmove', onMove, { passive: true })
    dialog.addEventListener('touchend', onEnd, { passive: true })
    return () => {
      dialog.removeEventListener('touchstart', onStart)
      dialog.removeEventListener('touchmove', onMove)
      dialog.removeEventListener('touchend', onEnd)
    }
  })

  // Per-card display values under the current filters/sort.
  function displayStatusFor(tune) {
    const instStatus =
      filters.instrument && !tune._instDimmed
        ? resolveTuneInstrumentStatus(tune, instruments, filters.instrument)
        : null
    return { status: instStatus || tune.learn_status, isInstrument: !!instStatus }
  }
</script>

<div class="my-tunes-container">
  <div class="my-tunes-header-section">
    <div class="page-header">
      <h1>
        My Tunes
        <a href="/help/my-tunes" class="help-icon" title="How to use My Tunes">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </a>
      </h1>
      <div class="page-actions">
        <a href="/my-tunes/sync" class="btn btn-secondary sync-btn">Sync With TheSession.org</a>
      </div>
    </div>

    <div class="filters-container">
      <div class="filter-top-row">
        <SearchField
          bind:value={rawSearch}
          id="search-input"
          inputClass="filter-search-input"
          wrapperClass="filter-search-wrap"
          styled={false}
          placeholder="Search"
          title="Search tunes"
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false"
          debounce={300}
          onSearch={(q) => (filters.search = q.toLowerCase().trim())} />
        <a
          href={addTuneHref}
          class="filter-panel-toggle"
          id="add-tune-btn"
          title="Add tune"
          style="text-decoration: none; font-size: 24px; font-weight: 300; line-height: 1;"
          onclick={handleAddTuneClick}>+</a>
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
            <div class="filter-button-group">
              {#each [['', 'All'], ['learned', 'Learned'], ['learning', 'Learning'], ['want to learn', 'Want To Learn']] as [value, label] (value)}
                <button
                  class="filter-status-btn"
                  class:active={filters.status === value}
                  data-status={value}
                  onclick={() => (filters.status = value)}>{label}</button>
              {/each}
            </div>
          </div>
          <div class="filter-panel-row">
            <button
              id="sort-direction-toggle"
              class="filter-sort-direction-btn"
              title="Toggle sort direction"
              onclick={() => (sort.dir = sort.dir === 'asc' ? 'desc' : 'asc')}>
              <span id="sort-direction-icon">{sort.dir === 'desc' ? '↓' : '↑'}</span>
            </button>
            <div class="filter-button-group">
              {#each [['alpha', 'a-z'], ['popularity', 'popularity'], ['plays', 'plays'], ['heard', 'heard']] as [value, label] (value)}
                <button
                  class="filter-sort-btn"
                  class:active={sort.type === value}
                  class:active-secondary={sort.type2 === value && sort.type !== value}
                  data-sort={value}
                  onclick={() => setSortMode(value)}>{label}</button>
              {/each}
            </div>
          </div>
          <div class="filter-panel-row">
            <div class="inst-select" class:open={typeMenuOpen} id="type-filter">
              <button
                type="button"
                class="inst-select-trigger"
                onclick={(e) => {
                  e.stopPropagation()
                  instMenuOpen = false
                  typeMenuOpen = !typeMenuOpen
                }}>
                <span id="type-filter-label">{typeLabelText}</span>
                <span class="inst-select-caret">▾</span>
              </button>
              <div class="inst-select-menu" id="type-filter-menu">
                {#each [{ value: '', label: 'All Tune Types' }, ...tuneTypes.map((t) => ({ value: t, label: cap(t) }))] as opt (opt.value)}
                  <button
                    type="button"
                    class="inst-select-option"
                    class:active={opt.value === filters.type}
                    onclick={() => {
                      typeMenuOpen = false
                      filters.type = opt.value
                    }}>{opt.label}</button>
                {/each}
              </div>
            </div>
          </div>
          {#if instruments.length >= 2}
            <div class="filter-panel-row" id="instrument-filter-row">
              <div class="inst-select" class:open={instMenuOpen} id="instrument-filter">
                <button
                  type="button"
                  class="inst-select-trigger"
                  onclick={(e) => {
                    e.stopPropagation()
                    typeMenuOpen = false
                    instMenuOpen = !instMenuOpen
                  }}>
                  <span id="instrument-filter-label">{instLabelText}</span>
                  <span class="inst-select-caret">▾</span>
                </button>
                <div class="inst-select-menu" id="instrument-filter-menu">
                  {#each [{ value: '', label: 'All My Instruments' }, ...instruments.map((i) => ({ value: i.instrument, label: i.instrument }))] as opt (opt.value)}
                    <button
                      type="button"
                      class="inst-select-option"
                      class:active={opt.value === filters.instrument}
                      onclick={() => {
                        instMenuOpen = false
                        filters.instrument = opt.value
                      }}>{opt.label}</button>
                  {/each}
                </div>
              </div>
            </div>
          {/if}
          <div class="filter-panel-actions">
            {#if hasActiveFilters}
              <button id="clear-filters-btn" class="filter-panel-clear-btn" onclick={clearFilters}>Clear Filters</button>
            {/if}
          </div>
        </div>
      {/if}
    </div>

    {#if pills.length > 0}
      <div id="active-filter-pills" class="active-filter-pills" style="display: flex;">
        {#each pills as pill (pill.key)}
          <span class="filter-pill">{pill.label}<button
              type="button"
              class="filter-pill-x"
              title="Remove this filter"
              onclick={() => removeFilterPill(pill.key)}>×</button></span>
        {/each}
      </div>
    {/if}

    <div class="results-count">
      <span id="results-count-text">
        {#if fullTunesLoaded && visible.length > 0}
          {resultsCountText(visible, allTunes.length, filters)}
        {/if}
      </span>
    </div>
  </div>

  {#if loadFailed && allTunes.length === 0}
    <div class="tunes-grid" id="tunes-grid" style="display: grid;">
      <div class="error-state">
        <div class="error-state-icon">⚠️</div>
        <div class="error-state-title">Failed to Load Tunes</div>
        <div class="error-state-message">There was a problem loading your tune collection.</div>
        <div class="error-state-action">
          <button class="retry-btn" onclick={() => loadTunes()}>
            <span class="retry-icon">↻</span>
            Retry
          </button>
        </div>
      </div>
    </div>
  {:else if visible.length === 0}
    {#if fullTunesLoaded}
      <div id="no-results" class="no-results">
        <h3>No tunes found</h3>
        <p id="no-results-message">
          {allTunes.length === 0 && !filters.search && !hasActiveFilters
            ? 'Try adjusting your filters or add your first tune to get started!'
            : noResultsMessage(filters)}
        </p>
        <div id="no-results-action" style="margin-top: 15px;">
          {#if hasActiveFilters}
            <a
              href="#clear"
              class="btn"
              onclick={(e) => {
                e.preventDefault()
                clearFilters()
              }}>Clear Filters</a>
          {:else}
            <a href={addTuneHref} class="btn" onclick={handleAddTuneClick}>Add Tune</a>
          {/if}
        </div>
      </div>
    {:else if !loadFailed && allTunes.length === 0}
      <div id="loading" class="loading"><p>Loading your tunes...</p></div>
    {/if}
  {:else}
    <div class="tunes-grid" id="tunes-grid" style="display: grid;">
      {#if filters.instrument && dimmedTunes.length > 0}
        {#each matches as tune (tune.person_tune_id)}
          {@const d = displayStatusFor(tune)}
          <TuneCard
            {tune}
            {isMobile}
            displayStatus={d.status}
            cycleIsInstrument={d.isInstrument}
            typeLabel={typeBadgeLabel(tune, sort.type)}
            onshow={(t) => showTuneDetail(t.person_tune_id)}
            oncycle={cycleStatus}
            onincrement={incrementHeard} />
        {/each}
        <div class="tune-group-heading">Tunes on other instruments</div>
        {#each dimmedTunes as tune (tune.person_tune_id)}
          {@const d = displayStatusFor(tune)}
          <TuneCard
            {tune}
            {isMobile}
            displayStatus={d.status}
            cycleIsInstrument={d.isInstrument}
            typeLabel={typeBadgeLabel(tune, sort.type)}
            onshow={(t) => showTuneDetail(t.person_tune_id)}
            oncycle={cycleStatus}
            onincrement={incrementHeard} />
        {/each}
      {:else}
        {#each visible as tune (tune.person_tune_id)}
          {@const d = displayStatusFor(tune)}
          <TuneCard
            {tune}
            {isMobile}
            displayStatus={d.status}
            cycleIsInstrument={d.isInstrument}
            typeLabel={typeBadgeLabel(tune, sort.type)}
            onshow={(t) => showTuneDetail(t.person_tune_id)}
            oncycle={cycleStatus}
            onincrement={incrementHeard} />
        {/each}
      {/if}
    </div>
  {/if}

  <div id="loading-more" class="loading-more" class:visible={fetchingMore && !fullTunesLoaded}>
    <span class="loading-spinner"></span>
    <span>Loading more tunes...</span>
  </div>
</div>

<!-- Add-to-My-Tunes pane: same component as before, now a bundled-in child with
     callback props instead of the window.MyTunesAddPane global. -->
<AddTuneApp bind:this={addPane} />

<style>
  /* Desktop split pane: the add pane slides in from the right and the page
     content yields to it (mobile instead overlays full-width, backdrop included). */
  .my-tunes-container {
    transition: margin-right 0.3s ease-out;
  }
  @media (min-width: 769px) {
    :global(body.mt-add-open) .my-tunes-container {
      margin-right: 440px;
    }
  }
</style>
