<script>
  // Logged tab: tune records this person logged at sessions (rows they created,
  // by the loggers' created_by attribution). Lazy-loaded once like the other
  // tabs; server returns newest-first with a cap, so the footer notes when
  // there's more history than shown.
  let { personId, load } = $props()

  let view = $state('summary') // 'summary' | 'detail' — each fetched lazily, then cached
  let loading = $state(true)
  let records = $state(null) // detail rows
  let instances = $state(null) // summary rows
  let totalCount = $state(0)
  let error = $state(false)
  let started = false

  function loadView(which) {
    // already cached?
    if (which === 'detail' ? records : instances) {
      loading = false
      return
    }
    loading = true
    const params = which === 'summary' ? '?view=summary' : ''
    fetch(`/api/person/${personId}/logged-tunes${params}`)
      .then((response) => response.json())
      .then((data) => {
        loading = false
        if (data.success) {
          if (which === 'detail') {
            records = data.tunes
            totalCount = data.total_count
          } else {
            instances = data.instances
          }
        } else if (which === 'detail') {
          records = []
        } else {
          instances = []
        }
      })
      .catch((err) => {
        loading = false
        error = true
        console.error('Error:', err)
      })
  }

  $effect(() => {
    if (load && !started) {
      started = true
      loadView(view)
    }
  })

  function switchView() {
    loadView(view)
  }

  // "2026-07-18 21:15" from the ISO logged_at (same slice-don't-Date-parse rule
  // as the rest of the page: no timezone re-interpretation).
  const fmtLoggedAt = (iso) => (iso ? `${iso.slice(0, 10)} ${iso.slice(11, 16)}` : '')
</script>

<div class="mt-3">
  <div class="logged-toolbar">
    <label for="logged-view-select" class="logged-view-label">View:</label>
    <select
      id="logged-view-select"
      class="form-select logged-view-select"
      bind:value={view}
      onchange={switchView}>
      <option value="summary">Summary</option>
      <option value="detail">Detail</option>
    </select>
  </div>

  <div id="logged-loading" class="text-center" style:display={loading ? '' : 'none'}>
    <span class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border-color); border-top: 2px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite;"></span>
    <span style="margin-left: 8px;">Loading logged tunes...</span>
  </div>
  <div id="logged-content">
    {#if error}
      <div class="alert alert-danger" role="alert">Error loading logged tunes.</div>
    {:else if view === 'summary'}
      {#if instances && instances.length > 0}
        <div class="table-responsive">
          <table class="table table-striped" id="person-logged-summary-grid">
            <thead>
              <tr>
                <th>Session Name</th>
                <th>Date</th>
                <th class="logged-count-col">Tunes Logged</th>
                <th>Last Logged</th>
              </tr>
            </thead>
            <tbody>
              {#each instances as inst (inst.session_path + inst.date)}
                <tr>
                  <td class="logged-session"><a href="/sessions/{inst.session_path}">{inst.session_name}</a></td>
                  <td class="logged-date"><a href="/sessions/{inst.session_path}/{inst.date}">{inst.date}</a></td>
                  <td class="logged-count-col">{inst.tune_count}</td>
                  <td class="logged-at">{fmtLoggedAt(inst.last_logged_at)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else if instances}
        <div class="alert alert-info" role="alert">No logged tunes found.</div>
      {/if}
    {:else if records && records.length > 0}
      <div class="table-responsive">
        <table class="table table-striped" id="person-logged-grid">
          <thead>
            <tr>
              <th>Session Name</th>
              <th>Date</th>
              <th>Tune</th>
              <th>Logged</th>
            </tr>
          </thead>
          <tbody>
            {#each records as record (record.session_instance_tune_id)}
              <tr>
                <td class="logged-session"><a href="/sessions/{record.session_path}">{record.session_name}</a></td>
                <td class="logged-date"><a href="/sessions/{record.session_path}/{record.date}">{record.date}</a></td>
                <td class="logged-tune">{record.tune_name || '(unnamed)'}</td>
                <td class="logged-at">{fmtLoggedAt(record.logged_at)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if totalCount > records.length}
        <p class="text-muted">Showing the most recent {records.length} of {totalCount} logged tunes.</p>
      {/if}
    {:else if records}
      <div class="alert alert-info" role="alert">No logged tunes found.</div>
    {/if}
  </div>
</div>

<style>
  .logged-session a,
  .logged-date a {
    color: var(--primary);
    text-decoration: none;
  }
  .logged-session a:hover,
  .logged-date a:hover {
    text-decoration: underline;
  }
  .logged-session,
  .logged-date,
  .logged-at {
    white-space: nowrap;
  }
  .logged-toolbar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }
  .logged-view-label {
    margin: 0;
    font-size: 0.9rem;
    opacity: 0.75;
  }
  .logged-view-select {
    width: auto;
    padding: 0.3rem 1.8rem 0.3rem 0.6rem;
    background-color: var(--bg-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 0.25rem;
  }
  .logged-count-col {
    text-align: right;
  }
</style>
