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
    LOG_VIEW_OPTIONS,
    filterInstanceGroups,
    matchLoggedTunes,
    tunePlayLinks,
  } from './logic.js'
  import { SearchField, Seg } from '../lib/index.js'

  let { active, session, isLoggedIn, onAddInstance } = $props()

  const sessionPath = session.path

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
  <div class="logs-filter-header" id="logs-filter-header">
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
<div class="tab-content" class:active id="logs-tab" style="padding-left: 10px;">
  <a href="/help/session-tracking/logs" class="help-icon" title="About session logs" style="float: right; margin: 4px 8px 0 0;">
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"></circle>
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
      <line x1="12" y1="17" x2="12.01" y2="17"></line>
    </svg>
  </a>
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
  {:else if isFestival}
    {@render filterHeader()}
    {#if view.sortedKeys.length > 0}
      <div class="past-instances">
        <table class="instances-table">
          {#each view.sortedKeys as dayKey, index (dayKey)}
            <tbody class="year-section">
              <tr class="year-header-row">
                <td colspan="2" class="year-header-cell">
                  <div class="year-header" data-year={dayKey}>
                    <div class="year-header-left">
                      <span class="year-toggle" data-year={dayKey} onclick={() => toggleSection(String(dayKey))}>{collapsed.has(String(dayKey)) ? '▶' : '▼'}</span>
                      <h3 class="year-title">{festivalDayLabel(view.byKey[dayKey][0].date)}</h3>
                      {#if index === 0 && isLoggedIn}<span class="year-add-link" id="add-session-btn" data-year={dayKey} onclick={addClick}>Add</span>{/if}
                    </div>
                  </div>
                </td>
              </tr>
              {#each view.byKey[dayKey] as instance (instance.session_instance_id)}
                <tr class="year-content-row" data-year={dayKey} style:display={collapsed.has(String(dayKey)) ? 'none' : null}>
                  <td class="instance-location-cell">
                    {@render instanceLink(instance, instance.location_override || session.location_name)}
                    {@render tuneHits(instance)}
                  </td>
                  <td class="instance-time-cell">{instanceTimeLabel(instance)}</td>
                </tr>
              {/each}
            </tbody>
          {/each}
        </table>
      </div>
    {:else}
      {@render emptyState()}
    {/if}
  {:else}
    {@render filterHeader()}
    {#if view.sortedKeys.length > 0}
      <div class="past-instances">
        <!-- Table vs. compact list keys off the session's OWN year count, not the
             filtered one: a filter must not flip the page's whole layout. -->
        {#if data.sorted_years.length > 1}
          <table class="instances-table">
            {#each view.sortedKeys as year, index (year)}
              <tbody class="year-section">
                <tr class="year-header-row">
                  <td class="year-header-cell">
                    <div class="year-header" data-year={year}>
                      <div class="year-header-left">
                        <span class="year-toggle" data-year={year} onclick={() => toggleSection(String(year))}>{collapsed.has(String(year)) ? '▶' : '▼'}</span>
                        <h3 class="year-title">{year}</h3>
                        {#if index === 0 && isLoggedIn}<span class="year-add-link" id="add-session-btn" data-year={year} onclick={addClick}>Add</span>{/if}
                        <a href="#view" class="year-view-link" data-year={year}>view {view.byKey[year].length} log{view.byKey[year].length !== 1 ? 's' : ''}</a>
                      </div>
                    </div>
                  </td>
                </tr>
                {#each view.byKey[year] as instance (instance.session_instance_id)}
                  <tr class="year-content-row" data-year={year} style:display={collapsed.has(String(year)) ? 'none' : null}>
                    <td class="instance-date-cell">
                      {@render instanceLink(instance, instance.date)}{@render tuneCountSuffix(instance)}
                      {@render tuneHits(instance)}
                    </td>
                  </tr>
                {/each}
              </tbody>
            {/each}
          </table>
        {:else}
          <!-- Single year view (compact) -->
          {#each view.sortedKeys as year (year)}
            <div style="padding-left: 10px;">
              <h3>
                {year}{#if isLoggedIn}<span class="year-add-link" id="add-session-btn" data-year={year} style="margin-left: 15px; font-size: 0.6em;" onclick={addClick}>Add</span>{/if}
              </h3>
              <ul style="list-style: none; padding: 0;">
                {#each view.byKey[year] as instance (instance.session_instance_id)}
                  <li style="margin-bottom: 8px;">
                    {@render instanceLink(instance, instance.date)}{@render tuneCountSuffix(instance)}
                    {@render tuneHits(instance)}
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        {/if}
      </div>
    {:else}
      {@render emptyState()}
    {/if}
  {/if}
</div>
