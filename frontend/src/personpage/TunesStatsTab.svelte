<script>
  // Tunes tab: lazy-loaded tune statistics. The type filter re-slices the loaded
  // stats client-side; the date filter re-fetches with start/end params (as the
  // legacy page did). Stat cards; on /me a "View tune list" link (it goes to the
  // viewer's own /my-tunes, which is only correct there); on the admin view the
  // actual tune grid renders below the stats instead.
  let { personId, load, isUserProfile = true } = $props()

  let loading = $state(true)
  let stats = $state(null) // the /tunes-stats stats object
  let noStats = $state(false)
  let tunes = $state(null) // admin view: the person's tune rows (null = loading)
  let selectedType = $state('')
  let startDate = $state('')
  let endDate = $state('')
  let panelStartDate = $state('')
  let panelEndDate = $state('')
  let datePanelVisible = $state(false)
  let started = false

  function loadTunesData() {
    let url = `/api/person/${personId}/tunes-stats`
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    if (params.toString()) url += '?' + params.toString()

    loading = true
    noStats = false
    stats = null
    datePanelVisible = false

    fetch(url)
      .then((response) => response.json())
      .then((data) => {
        loading = false
        if (data.success) {
          stats = data.stats
        } else {
          noStats = true
        }
      })
      .catch((err) => {
        loading = false
        noStats = true
        console.error('Error:', err)
      })
  }

  $effect(() => {
    if (load && !started) {
      started = true
      loadTunesData()
      if (!isUserProfile) loadTuneGrid()
    }
  })

  function loadTuneGrid() {
    fetch(`/api/person/${personId}/tunes`)
      .then((r) => r.json())
      .then((data) => {
        tunes = data.success ? data.tunes : []
      })
      .catch((err) => {
        tunes = []
        console.error('Error loading tunes:', err)
      })
  }

  // The grid obeys the same filters as the stat cards: the type droplist, and
  // the date range (which, like /tunes-stats, filters on when the tune was
  // added to the collection).
  const gridRows = $derived.by(() => {
    if (!tunes) return null
    return tunes.filter((t) => {
      if (selectedType && t.tune_type !== selectedType) return false
      const added = (t.created_date || '').slice(0, 10)
      if (startDate && (!added || added < startDate)) return false
      if (endDate && (!added || added > endDate)) return false
      return true
    })
  })

  const fmtDate = (iso) => (iso ? iso.slice(0, 10) : '')

  const displayStats = $derived.by(() => {
    if (!stats) return null
    if (selectedType && stats.by_type_detailed && stats.by_type_detailed[selectedType]) {
      return stats.by_type_detailed[selectedType]
    }
    return {
      total: stats.total_tunes,
      learned: stats.learned,
      learning: stats.learning,
      bookmarked: stats.bookmarked,
    }
  })

  const tuneListUrl = $derived.by(() => {
    const params = new URLSearchParams()
    if (selectedType && stats && stats.by_type_detailed && stats.by_type_detailed[selectedType]) {
      params.append('type', selectedType)
    }
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    return params.toString() ? `/my-tunes?${params.toString()}` : '/my-tunes'
  })

  const sortedTypes = $derived(stats && stats.by_type ? Object.keys(stats.by_type).sort() : [])
  const hasDateFilter = $derived(!!(startDate || endDate))
  const dateText = $derived.by(() => {
    if (startDate && endDate) return `${startDate} – ${endDate}`
    if (startDate) return `from ${startDate}`
    return `until ${endDate}`
  })

  function showDatePanel() {
    panelStartDate = startDate
    panelEndDate = endDate
    datePanelVisible = true
  }

  function applyDateFilter() {
    startDate = panelStartDate
    endDate = panelEndDate
    loadTunesData()
  }

  function clearDateFilter() {
    startDate = ''
    endDate = ''
    loadTunesData()
  }

  // Legacy date-input behavior: click opens the picker, keyboard input blocked.
  function dateInputClick(e) {
    if (e.currentTarget.showPicker) e.currentTarget.showPicker()
  }
  function dateInputKeydown(e) {
    e.preventDefault()
  }
</script>

<div class="mt-3">
  <div id="tunes-loading" class="text-center" style:display={loading ? 'block' : 'none'}>
    <span class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border-color); border-top: 2px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite;"></span>
    <span style="margin-left: 8px;">Loading tune statistics...</span>
  </div>
  <div id="tunes-content">
    {#if noStats}
      <div class="alert alert-info" role="alert">No tune statistics available.</div>
      {#if isUserProfile}
        <div class="mt-3">
          <a href="/my-tunes" class="tune-list-link">View tune list</a>
        </div>
      {/if}
    {:else if stats}
      <div class="tune-stats">
        <div class="tune-filter-row mb-3">
          {#if sortedTypes.length > 0}
            <div class="filter-group">
              <label for="tune-type-filter" class="filter-label">Type:</label>
              <select id="tune-type-filter" class="form-select tune-type-select" bind:value={selectedType}>
                <option value="">All Types</option>
                {#each sortedTypes as type (type)}
                  <option value={type}>{type} ({stats.by_type[type]})</option>
                {/each}
              </select>
            </div>
          {/if}

          {#if hasDateFilter}
            <span class="date-filter-summary">
              <span class="date-filter-text">{dateText}</span>
              <a
                href="#edit"
                id="edit-date-filter"
                class="date-filter-link"
                onclick={(e) => {
                  e.preventDefault()
                  showDatePanel()
                }}>edit</a>
              <a
                href="#clear"
                id="clear-date-filter"
                class="date-filter-link date-filter-clear"
                onclick={(e) => {
                  e.preventDefault()
                  clearDateFilter()
                }}>clear</a>
            </span>
          {:else}
            <a
              href="#filter"
              id="show-date-filter"
              class="date-filter-link"
              onclick={(e) => {
                e.preventDefault()
                showDatePanel()
              }}>Filter by date</a>
          {/if}

          {#if isUserProfile}
            <a href={tuneListUrl} class="tune-list-link">View tune list</a>
          {/if}
        </div>

        <div id="date-filter-panel" class="date-filter-panel" style:display={datePanelVisible ? 'block' : 'none'}>
          <div class="date-filter-row">
            <label for="tune-start-date" class="filter-label">From:</label>
            <input
              type="date"
              id="tune-start-date"
              class="form-control date-input"
              bind:value={panelStartDate}
              onclick={dateInputClick}
              onkeydown={dateInputKeydown} />
          </div>
          <div class="date-filter-row">
            <label for="tune-end-date" class="filter-label">To:</label>
            <input
              type="date"
              id="tune-end-date"
              class="form-control date-input"
              bind:value={panelEndDate}
              onclick={dateInputClick}
              onkeydown={dateInputKeydown} />
          </div>
          <div class="date-filter-row">
            <button id="apply-date-filter" class="btn btn-sm btn-primary" onclick={applyDateFilter}>Apply</button>
            <button id="cancel-date-filter" class="btn btn-sm btn-outline-secondary" onclick={() => (datePanelVisible = false)}>Cancel</button>
          </div>
        </div>

        <div class="row">
          <div class="col-md-6 col-lg-3 mb-3">
            <div class="stat-card">
              <div class="stat-value">{displayStats.total || 0}</div>
              <div class="stat-label">Total Tunes</div>
            </div>
          </div>
          <div class="col-md-6 col-lg-3 mb-3">
            <div class="stat-card">
              <div class="stat-value">{displayStats.learned || 0}</div>
              <div class="stat-label">Learned</div>
            </div>
          </div>
          <div class="col-md-6 col-lg-3 mb-3">
            <div class="stat-card">
              <div class="stat-value">{displayStats.learning || 0}</div>
              <div class="stat-label">Learning</div>
            </div>
          </div>
          <div class="col-md-6 col-lg-3 mb-3">
            <div class="stat-card">
              <div class="stat-value">{displayStats.bookmarked || 0}</div>
              <div class="stat-label">Bookmarked</div>
            </div>
          </div>
        </div>

        {#if !isUserProfile}
          {#if !gridRows}
            <p class="text-muted">Loading tunes…</p>
          {:else if gridRows.length === 0}
            <p class="text-muted">No tunes match the current filters.</p>
          {:else}
            <div class="table-responsive">
              <table class="table table-striped tune-grid" id="person-tunes-grid">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th class="tune-grid-num">Heard</th>
                    <th>Learned</th>
                    <th>Added</th>
                  </tr>
                </thead>
                <tbody>
                  {#each gridRows as tune (tune.person_tune_id)}
                    <tr>
                      <td class="tune-grid-name">
                        <a href="/admin/tunes/{tune.tune_id}">{tune.tune_name}</a>
                      </td>
                      <td>{tune.tune_type || ''}</td>
                      <td>{tune.learn_status}</td>
                      <td class="tune-grid-num">{tune.heard_count || 0}</td>
                      <td>{fmtDate(tune.learned_date)}</td>
                      <td>{fmtDate(tune.created_date)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .tune-grid-name a {
    color: var(--primary);
    text-decoration: none;
    font-weight: 500;
    white-space: nowrap;
  }
  .tune-grid-name a:hover {
    text-decoration: underline;
  }
  .tune-grid-num {
    text-align: right;
  }
  .tune-grid td,
  .tune-grid th {
    color: var(--text-color);
  }
</style>
