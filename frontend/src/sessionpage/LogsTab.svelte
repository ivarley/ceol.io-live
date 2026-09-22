<script>
  // The Logs tab ("Sessions" for festivals): lazy-loaded from
  // GET /api/sessions/<path>/logs on first view, rendered with the exact legacy
  // renderLogs markup (year/day sections, collapsible via the ▼/▶ toggle,
  // tune-count suffixes, empty-log dimming, active-now dots).
  //
  // Above the grid sits the filter header: the All/Logged toggle (Logged by
  // default — a night with nothing logged is a placeholder, and there are far
  // more of those than real logs) and a tune autocomplete that narrows the list
  // to the nights that tune was played. Both filter the already-loaded list; the
  // tune box lazy-loads its options on first focus.
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import {
    instanceTimeLabel,
    tuneCountOf,
    isEmptyLog,
    instanceUrlId,
    festivalDayLabel,
    dowOf,
    domOf,
    rowDateLabel,
    LOG_VIEW_OPTIONS,
    filterInstanceGroups,
    matchLoggedTunes,
    tunePlayLinks,
  } from './logic.js'
  import { publishHeight } from './sticky.js'
  import { Row, SearchField, Seg, Toolbar } from '../lib/index.js'

  let { active, session, isLoggedIn, onAddInstance } = $props()

  const sessionPath = session.path

  // A log's own name wins (spec 047 — a festival night needs one, an ordinary
  // Tuesday does not). Failing that: at a festival the room identifies it, and in
  // a year list the date does.
  const titleOf = (instance) =>
    instance.location_override ||
    (isFestival ? session.location_name || 'Session' : rowDateLabel(instance.date))

  let loaded = $state(false)
  let loading = $state(false)
  let loadError = $state(false)
  let data = $state(null)
  const collapsed = new SvelteSet() // year/day keys the user has collapsed

  // Instances currently "on now" (green dot). Fetched once, like the legacy
  // highlightActiveInstances, but applied whenever the logs render.
  let activeInstanceIds = $state([])

  $effect(() => {
    untrack(() => {
      fetch(`/api/session/${session.session_id}/active_instance`)
        .then((response) => response.json())
        .then((d) => {
          if (d.success && d.active_instance_ids && d.active_instance_ids.length > 0) {
            activeInstanceIds = d.active_instance_ids
          }
        })
        .catch((error) => {
          console.error('Error fetching active instances:', error)
        })
    })
  })

  // Lazy load on first view (or immediately when logs is the landing tab).
  $effect(() => {
    if (active && !loaded && !loading) loadLogs()
  })

  function loadLogs() {
    loading = true
    loadError = false
    fetch(`/api/sessions/${sessionPath}/logs`)
      .then((response) => response.json())
      .then((d) => {
        if (d.success) {
          data = d
          loaded = true
        } else {
          throw new Error(d.message || 'Failed to load logs')
        }
      })
      .catch((error) => {
        console.error('Error loading logs:', error)
        loadError = true
      })
      .finally(() => {
        loading = false
      })
  }

  function toggleSection(key) {
    if (collapsed.has(key)) collapsed.delete(key)
    else collapsed.add(key)
  }

  const isFestival = $derived(data && (data.session_type || 'regular') === 'festival')

  function addClick(e) {
    e.preventDefault()
    onAddInstance()
  }

  // ---- filters -------------------------------------------------------------

  // Regular sessions default to "logged" — an unlogged week is a placeholder.
  // A FESTIVAL's list is its schedule (rooms and times, spec 006), so hiding the
  // unlogged ones there would hide the festival itself; it defaults to "all".
  let viewMode = $state((session.session_type || 'regular') === 'festival' ? 'all' : 'logged')

  // Tune filter: the autocomplete options (every tune ever logged here), the
  // instance ids of the chosen one, and where in each night it came round.
  // `tuneInstanceIds` null = no tune filter.
  let loggedTunes = $state([])
  let tunesLoaded = $state(false)
  let tunesLoading = $state(false)
  let tunesError = $state(false)
  let tuneQuery = $state('')
  let selectedTune = $state(null)
  let tuneInstanceIds = $state(null)
  let tunePlays = $state(null) // Map<session_instance_id, positions[]>
  let instancesLoading = $state(false)
  let inputFocused = $state(false)
  let highlight = $state(0)
  let selectToken = 0 // drops stale instance-id responses when picks come fast
  let filterOpen = $state(false) // the toolbar's filter panel

  const totalInstances = $derived.by(() => {
    if (!data) return 0
    const groups = isFestival ? data.instances_by_day : data.instances_by_year
    return Object.values(groups || {}).reduce((n, list) => n + list.length, 0)
  })

  const view = $derived.by(() => {
    if (!data) return { sortedKeys: [], byKey: {}, total: 0 }
    const keys = isFestival ? data.sorted_days : data.sorted_years
    const groups = isFestival ? data.instances_by_day : data.instances_by_year
    return filterInstanceGroups(keys, groups, viewMode, tuneInstanceIds)
  })

  const options = $derived(selectedTune ? [] : matchLoggedTunes(loggedTunes, tuneQuery))
  const dropdownOpen = $derived(inputFocused && options.length > 0)
  const activeIndex = $derived(Math.min(highlight, Math.max(options.length - 1, 0)))
  // A typed query with nothing under it: say which it is, rather than leaving a
  // box that looks broken while the option list is still in flight.
  const dropdownStatus = $derived.by(() => {
    if (selectedTune || !inputFocused || options.length > 0) return null
    if (!tuneQuery.trim()) return null
    if (tunesLoading) return 'Loading tunes…'
    if (tunesError) return null // the note below the row says it
    return 'No tune logged here matches that'
  })

  // Editing the box (or the kit's clear ×) drops the selection — the filter must
  // never outlive the tune name that explains it.
  $effect(() => {
    if (selectedTune && tuneQuery !== selectedTune.name) clearTuneFilter()
  })

  // A fresh query starts at the top of the list again.
  $effect(() => {
    void tuneQuery
    highlight = 0
  })

  function ensureTunesLoaded() {
    if (tunesLoaded || tunesLoading) return
    tunesLoading = true
    tunesError = false
    fetch(`/api/sessions/${sessionPath}/logged-tunes`)
      .then((response) => response.json())
      .then((d) => {
        if (!d.success) throw new Error(d.message || 'Failed to load tunes')
        loggedTunes = d.tunes || []
        tunesLoaded = true
      })
      .catch((error) => {
        console.error('Error loading logged tunes:', error)
        tunesError = true
      })
      .finally(() => {
        tunesLoading = false
      })
  }

  function clearTuneFilter() {
    selectedTune = null
    tuneInstanceIds = null
    tunePlays = null
    instancesLoading = false
    selectToken += 1
  }

  function selectTune(tune) {
    const token = ++selectToken
    selectedTune = tune
    tuneQuery = tune.name
    instancesLoading = true
    // NOT inputFocused = false: the dropdown closes on its own (a selection empties
    // the options), and dropping focus would leave editing the box unable to reopen it.
    fetch(`/api/sessions/${sessionPath}/logged-tunes/${tune.tune_id}/instances`)
      .then((response) => response.json())
      .then((d) => {
        if (token !== selectToken) return
        if (!d.success) throw new Error(d.message || 'Failed to filter')
        tuneInstanceIds = new Set(d.session_instance_ids || [])
        tunePlays = new Map(
          (d.instances || []).map((i) => [i.session_instance_id, i.positions || []])
        )
      })
      .catch((error) => {
        if (token !== selectToken) return
        console.error('Error loading tune instances:', error)
        clearTuneFilter()
      })
      .finally(() => {
        if (token === selectToken) instancesLoading = false
      })
  }

  // Arrow/Enter for the autocomplete. Listened for on the wrapper: SearchField
  // owns the input's own onkeydown (Escape clears, Enter flushes), and both
  // still bubble here.
  function onFilterKey(e) {
    if (!dropdownOpen) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      highlight = Math.min(activeIndex + 1, options.length - 1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      highlight = Math.max(activeIndex - 1, 0)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      selectTune(options[activeIndex])
    }
  }
</script>

{#snippet instanceLink(instance, label)}
  <a
    href="/sessions/{sessionPath}/{instanceUrlId(instance)}"
    data-instance-id={instance.session_instance_id}
    class={isEmptyLog(instance) ? 'empty-log' : ''}>
    {#if activeInstanceIds.includes(instance.session_instance_id)}
      <span class="session-instance-link"><span>{label}</span><span class="active-now-badge"></span></span>
    {:else}{label}{/if}
  </a>
{/snippet}

{#snippet tuneCountSuffix(instance)}
  {#if tuneCountOf(instance) > 0}
    <span class="log-tune-count">({tuneCountOf(instance)} tune{tuneCountOf(instance) !== 1 ? 's' : ''} logged)</span>
  {/if}
{/snippet}

<!-- Under a filtered date: every time the tune came round that night, each link
     landing on that exact record in the log rather than the top of the night. -->
{#snippet tuneHits(instance)}
  {@const hits = selectedTune ? tunePlayLinks(tunePlays, instance, sessionPath, selectedTune.tune_id) : []}
  {#if hits.length > 0}
    <ul class="logs-tune-hits">
      {#each hits as hit (hit.key)}
        <li>
          <a href={hit.href} data-sit-id={hit.key}
            >{hit.name}<span class="logs-tune-hit-where">{hit.where}</span></a>
        </li>
      {/each}
    </ul>
  {/if}
{/snippet}

{#snippet filterHeader()}
  <!-- One toolbar, same as the Tunes and People tabs (spec 052 §B8 Stage 3):
       search, a + to add, and a filter button whose panel expands beneath the
       line. Logged/All lives in that panel now — it is a filter, and it was
       taking a third of a phone's toolbar to say so. -->
  <div class="logs-filter-header" id="logs-filter-header" use:publishHeight={'--logs-toolbar-h'}>
    <Toolbar
      styled={false}
      toolbarClass="filter-top-row"
      buttonClass="filter-panel-toggle"
      bind:open={filterOpen}
      activeCount={viewMode === 'all' ? 1 : 0}
      addId={isLoggedIn ? 'add-session-btn' : null}
      addTitle="Add a log"
      onAdd={isLoggedIn ? addClick : null}>
      {#snippet search()}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="logs-tune-filter" onkeydown={onFilterKey}>
      <SearchField
        bind:value={tuneQuery}
        id="logs-tune-filter-input"
        inputClass="filter-search-input"
        wrapperClass="filter-search-wrap"
        styled={false}
        placeholder="Search for a tune"
        autocomplete="off"
        autocorrect="off"
        autocapitalize="off"
        spellcheck="false"
        debounce={0}
        role="combobox"
        aria-expanded={dropdownOpen}
        aria-controls="logs-tune-options"
        aria-autocomplete="list"
        aria-activedescendant={dropdownOpen ? `logs-tune-option-${activeIndex}` : undefined}
        onfocus={() => {
          inputFocused = true
          ensureTunesLoaded()
        }}
        onblur={() => (inputFocused = false)} />
      {#if dropdownOpen}
        <ul class="logs-tune-options" id="logs-tune-options" role="listbox" aria-label="Tunes logged here">
          {#each options as option, i (option.tune_id)}
            <li id="logs-tune-option-{i}" role="option" aria-selected={i === activeIndex}>
              <button
                type="button"
                class="logs-tune-option"
                class:active={i === activeIndex}
                onmousedown={(e) => e.preventDefault()}
                onclick={() => selectTune(option)}>
                <span class="logs-tune-option-name">{option.name}</span>
                <span class="logs-tune-option-count">{option.log_count}</span>
              </button>
            </li>
          {/each}
        </ul>
          {:else if dropdownStatus}
            <div class="logs-tune-options logs-tune-status" id="logs-tune-status">{dropdownStatus}</div>
          {/if}
        </div>
      {/snippet}

      {#snippet filter()}
        <Seg
          options={LOG_VIEW_OPTIONS}
          value={viewMode}
          onSelect={(id) => (viewMode = id)}
          idAttr="data-log-view"
          styled={false}
          segClass="filter-button-group logs-view-toggle"
          optClass="filter-sort-btn"
          role="group"
          aria-label="Show all logs or only logged ones" />
      {/snippet}
    </Toolbar>
  </div>
  {#if selectedTune || tunesError}
    <div class="logs-filter-note" id="logs-filter-note">
      {#if tunesError}
        Couldn't load the tune list.
      {:else if instancesLoading}
        Filtering to {selectedTune.name}…
      {:else}
        {view.total} log{view.total !== 1 ? 's' : ''} with {selectedTune.name}
        <button type="button" class="logs-filter-clear" onclick={() => (tuneQuery = '')}>clear</button>
      {/if}
    </div>
  {/if}
{/snippet}

{#snippet emptyState()}
  <div class="logs-empty-state">
    {#if selectedTune}
      <p>No logs with {selectedTune.name}.</p>
    {:else}
      <p>
        No logs yet.{#if isLoggedIn}
          <span class="year-add-link" id="add-session-btn" onclick={addClick}>Add</span>
        {/if}
      </p>
      {#if totalInstances > 0}
        <p class="logs-empty-hint">
          <button type="button" class="logs-filter-clear" onclick={() => (viewMode = 'all')}>
            Show all {totalInstances} session{totalInstances !== 1 ? 's' : ''}
          </button>
        </p>
      {/if}
    {/if}
  </div>
{/snippet}

<!-- Logs Tab Content -->
<div class="tab-content" class:active id="logs-tab">
  {#if loadError}
    <div style="text-align: center; padding: 40px;">
      <p style="color: var(--danger, #dc3545);">
        Error loading logs. Please <a
          href="#reload"
          style="color: var(--primary);"
          onclick={(e) => {
            e.preventDefault()
            window.location.reload()
          }}>refresh the page</a>.
      </p>
    </div>
  {:else if !loaded}
    <div style="text-align: center; padding: 40px; color: var(--disabled-text);"><p>Loading logs...</p></div>
  {:else if totalInstances === 0}
    <div class="past-instances">
      {#if isFestival}
        <p><a href="#add" id="add-first-session-btn" style="color: var(--primary); text-decoration: none;" onclick={addClick}>Add your first session</a></p>
      {:else}
        <p><a href="#add" id="add-session-btn" style="color: var(--primary); text-decoration: none;" onclick={addClick}>Add your first log</a></p>
      {/if}
    </div>
  {:else}
    <!-- ONE list, whatever the grouping (spec 052 §B8 Stage 3). This replaced three
         near-identical render paths: a multi-year <table>, a compact single-year <ul>,
         and a day-grouped <table> for festivals. They differed only in what labels a
         group and what leads a row, both of which are now one ternary — `view` already
         handed us sortedKeys/byKey regardless of which grouping was in play.

         The group header stays TAPPABLE to collapse. On a weekly session five years
         deep (~260 logs) a flat list is a long flick with no way to reach 2019, so
         sticky headers tell you where you are and collapsing is what gets you
         somewhere. It is still in-memory only, exactly as before: collapse a year,
         come back tomorrow, and it is open again. -->
    {@render filterHeader()}
    {#if view.sortedKeys.length > 0}
      <div class="past-instances">
        <div class="logs-list" id="logs-list">
          {#each view.sortedKeys as groupKey, index (groupKey)}
            {@const instances = view.byKey[groupKey]}
            {@const isCollapsed = collapsed.has(String(groupKey))}
            <div class="logs-group year-section" data-year={groupKey}>
              <div class="logs-group-header year-header" data-year={groupKey}>
                <button
                  type="button"
                  class="year-toggle logs-group-toggle"
                  data-year={groupKey}
                  aria-expanded={!isCollapsed}
                  onclick={() => toggleSection(String(groupKey))}>{isCollapsed ? '▶' : '▼'}</button>
                <h3 class="year-title logs-group-title">
                  {isFestival ? festivalDayLabel(instances[0].date) : groupKey}
                </h3>
                <span class="logs-group-count">{instances.length} log{instances.length !== 1 ? 's' : ''}</span>
              </div>

              {#if !isCollapsed}
                {#each instances as instance (instance.session_instance_id)}
                  {@const live = activeInstanceIds.includes(instance.session_instance_id)}
                  {@const when = instanceTimeLabel(instance)}
                  {@const count = tuneCountOf(instance)}
                  <Row
                    as="div"
                    styled={false}
                    rowClass="logs-row year-content-row{isEmptyLog(instance) ? ' empty-log' : ''}"
                    data-year={groupKey}
                    data-instance-id={instance.session_instance_id}>
                    {#snippet lead()}
                      <!-- A festival day is named by its header, so repeating the date on
                           every row would say nothing; the time is what tells them apart. -->
                      {#if !isFestival}
                        <span class="logs-date-block">
                          <span class="logs-date-dow">{dowOf(instance.date)}</span>
                          <span class="logs-date-dom">{domOf(instance.date)}</span>
                        </span>
                      {/if}
                    {/snippet}
                    {#snippet body()}
                      <span class="logs-row-body">
                        <a
                          href="/sessions/{sessionPath}/{instanceUrlId(instance)}"
                          data-instance-id={instance.session_instance_id}
                          class="logs-row-title{isEmptyLog(instance) ? ' empty-log' : ''}">
                          {#if live}
                            <span class="session-instance-link"><span>{titleOf(instance)}</span><span class="active-now-badge"></span></span>
                          {:else}{titleOf(instance)}{/if}
                        </a>
                        <span class="logs-row-sub">
                          <!-- The separator is an expression, not literal whitespace:
                               Svelte trims text at a block boundary, so " · " written
                               inline collapses and the two facts run together. -->
                          {#if when}{when}{/if}{#if when && count}{' · '}{/if}{#if count}<span class="log-tune-count">{count} tune{count !== 1 ? 's' : ''} logged</span>{/if}
                        </span>
                      </span>
                      {@render tuneHits(instance)}
                    {/snippet}
                  </Row>
                {/each}
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {:else}
      {@render emptyState()}
    {/if}
  {/if}
</div>
