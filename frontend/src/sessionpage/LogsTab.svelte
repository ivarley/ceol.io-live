<script>
  // The Logs tab ("Sessions" for festivals): lazy-loaded from
  // GET /api/sessions/<path>/logs on first view, rendered with the exact legacy
  // renderLogs markup (year/day sections, collapsible via the ▼/▶ toggle,
  // tune-count suffixes, empty-log dimming, active-now dots).
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { instanceTimeLabel, tuneCountOf, isEmptyLog, instanceUrlId, festivalDayLabel } from './logic.js'

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

<!-- Logs Tab Content -->
<div class="tab-content" class:active id="logs-tab" style="padding-left: 10px;">
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
  {:else if isFestival}
    {#if data.sorted_days && data.sorted_days.length > 0}
      <div class="past-instances">
        <table class="instances-table">
          {#each data.sorted_days as dayKey, index (dayKey)}
            <tbody class="year-section">
              <tr class="year-header-row">
                <td colspan="2" class="year-header-cell">
                  <div class="year-header" data-year={dayKey}>
                    <div class="year-header-left">
                      <span class="year-toggle" data-year={dayKey} onclick={() => toggleSection(String(dayKey))}>{collapsed.has(String(dayKey)) ? '▶' : '▼'}</span>
                      <h3 class="year-title">{festivalDayLabel(data.instances_by_day[dayKey][0].date)}</h3>
                      {#if index === 0 && isLoggedIn}<span class="year-add-link" id="add-session-btn" data-year={dayKey} onclick={addClick}>Add</span>{/if}
                    </div>
                  </div>
                </td>
              </tr>
              {#each data.instances_by_day[dayKey] as instance (instance.session_instance_id)}
                <tr class="year-content-row" data-year={dayKey} style:display={collapsed.has(String(dayKey)) ? 'none' : null}>
                  <td class="instance-location-cell">
                    {@render instanceLink(instance, instance.location_override || session.location_name)}
                  </td>
                  <td class="instance-time-cell">{instanceTimeLabel(instance)}</td>
                </tr>
              {/each}
            </tbody>
          {/each}
        </table>
      </div>
    {:else}
      <div class="past-instances">
        <p><a href="#add" id="add-first-session-btn" style="color: var(--primary); text-decoration: none;" onclick={addClick}>Add your first session</a></p>
      </div>
    {/if}
  {:else if data.sorted_years && data.sorted_years.length > 0}
    <div class="past-instances">
      {#if data.sorted_years.length > 1}
        <table class="instances-table">
          {#each data.sorted_years as year, index (year)}
            <tbody class="year-section">
              <tr class="year-header-row">
                <td class="year-header-cell">
                  <div class="year-header" data-year={year}>
                    <div class="year-header-left">
                      <span class="year-toggle" data-year={year} onclick={() => toggleSection(String(year))}>{collapsed.has(String(year)) ? '▶' : '▼'}</span>
                      <h3 class="year-title">{year}</h3>
                      {#if index === 0 && isLoggedIn}<span class="year-add-link" id="add-session-btn" data-year={year} onclick={addClick}>Add</span>{/if}
                      <a href="#view" class="year-view-link" data-year={year}>view {data.instances_by_year[year].length} log{data.instances_by_year[year].length !== 1 ? 's' : ''}</a>
                    </div>
                  </div>
                </td>
              </tr>
              {#each data.instances_by_year[year] as instance (instance.session_instance_id)}
                <tr class="year-content-row" data-year={year} style:display={collapsed.has(String(year)) ? 'none' : null}>
                  <td class="instance-date-cell">
                    {@render instanceLink(instance, instance.date)}{@render tuneCountSuffix(instance)}
                  </td>
                </tr>
              {/each}
            </tbody>
          {/each}
        </table>
      {:else}
        <!-- Single year view (compact) -->
        {#each data.sorted_years as year (year)}
          <div style="padding-left: 10px;">
            <h3>
              {year}{#if isLoggedIn}<span class="year-add-link" id="add-session-btn" data-year={year} style="margin-left: 15px; font-size: 0.6em;" onclick={addClick}>Add</span>{/if}
            </h3>
            <ul style="list-style: none; padding: 0;">
              {#each data.instances_by_year[year] as instance (instance.session_instance_id)}
                <li style="margin-bottom: 8px;">
                  {@render instanceLink(instance, instance.date)}{@render tuneCountSuffix(instance)}
                </li>
              {/each}
            </ul>
          </div>
        {/each}
      {/if}
    </div>
  {:else}
    <div class="past-instances">
      <p><a href="#add" id="add-session-btn" style="color: var(--primary); text-decoration: none;" onclick={addClick}>Add your first log</a></p>
    </div>
  {/if}
</div>
