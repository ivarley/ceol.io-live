<script>
  // Local Cache tab (spec 024 fast-match vocabulary): N/M limits with a
  // debounced live preview of what each device would download, plus save.
  let { sessionPath, sessionLimit, globalLimit, load } = $props()

  const toast = (msg, type) => window.showMessage && window.showMessage(msg, type)

  let n = $state(String(sessionLimit))
  let m = $state(String(globalLimit))
  let summaryHtmlParts = $state(null) // {session_count, global_count, total, kb}
  let summaryText = $state('Loading preview…')
  let previewTunes = $state(null)
  let previewError = $state(null)
  let cachePreviewTimer = null
  let started = false

  function onEdit() {
    clearTimeout(cachePreviewTimer)
    cachePreviewTimer = setTimeout(loadCachePreview, 300) // debounce live preview
  }

  function loadCachePreview() {
    summaryText = 'Computing preview…'
    summaryHtmlParts = null

    fetch(`/api/admin/sessions/${sessionPath}/tune-cache?n=${encodeURIComponent(n)}&m=${encodeURIComponent(m)}`)
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) {
          summaryText = ''
          previewTunes = null
          previewError = data.error || 'Failed to load preview'
          return
        }
        renderCachePreview(data)
      })
      .catch((error) => {
        previewError = `Failed to load preview: ${error}`
      })
  }

  function renderCachePreview(data) {
    // Estimate the real download size from the LEAN fields the client actually receives
    // (the preview adds tier/plays/tunebook_count, which the vocabulary endpoint strips).
    const lean = data.tunes.map((t) => ({ tune_id: t.tune_id, name: t.name, alias: t.alias, tune_type: t.tune_type }))
    const kb = (new Blob([JSON.stringify(lean)]).size / 1024).toFixed(1)

    previewError = null
    summaryText = null
    summaryHtmlParts = {
      session_count: data.session_count,
      global_count: data.global_count,
      total: data.tunes.length,
      kb,
    }
    previewTunes = data.tunes
  }

  function saveCacheLimits() {
    const payload = {
      live_cache_session_limit: parseInt(n) || 0,
      live_cache_global_limit: parseInt(m) || 0,
    }
    fetch(`/api/sessions/${sessionPath}/admin-update`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          toast('Local cache settings saved', 'success')
          loadCachePreview() // reflect the now-saved values
        } else {
          toast(data.error || 'Failed to save cache settings', 'error')
        }
      })
      .catch((error) => {
        console.error('Error saving cache settings:', error)
        toast('An error occurred while saving cache settings', 'error')
      })
  }

  $effect(() => {
    if (load && !started) {
      started = true
      loadCachePreview()
    }
  })

  const popularityFor = (t) =>
    t.tier === 'session'
      ? `${t.plays} play${t.plays === 1 ? '' : 's'} here`
      : `${(t.tunebook_count || 0).toLocaleString()} tunebooks`
</script>

<section class="docs-section">
  <h2 class="section-heading">Local Tune Cache</h2>
  <p class="text-muted">
    The live-logging screen preloads a list of tunes onto each device so typed
    tune names match instantly &mdash; even offline. It holds the
    <strong>N</strong> most-played tunes from <em>this</em> session, plus the
    <strong>M</strong> most globally-popular tunes not already in that set.
    Bigger numbers match more tunes without a network call, but make each
    device download a little more.
  </p>

  <div class="d-flex flex-wrap align-items-end gap-3 mb-3">
    <div>
      <label for="cache-session-limit" class="form-label mb-1">N &mdash; this session's top tunes</label>
      <input
        type="number"
        class="form-control"
        id="cache-session-limit"
        bind:value={n}
        oninput={onEdit}
        min="0"
        max="2000"
        style="width: 120px;" />
    </div>
    <div>
      <label for="cache-global-limit" class="form-label mb-1">M &mdash; globally-popular extras</label>
      <input
        type="number"
        class="form-control"
        id="cache-global-limit"
        bind:value={m}
        oninput={onEdit}
        min="0"
        max="1000"
        style="width: 120px;" />
    </div>
    <button type="button" class="btn btn-primary" id="cache-save-btn" onclick={saveCacheLimits}>Save</button>
  </div>

  <div id="cache-summary" class="mb-3 text-muted">
    {#if summaryHtmlParts}
      Caching <strong>{summaryHtmlParts.session_count}</strong> session tune{summaryHtmlParts.session_count === 1 ? '' : 's'}
      + <strong>{summaryHtmlParts.global_count}</strong> globally-popular = <strong>{summaryHtmlParts.total}</strong> total
      (~{summaryHtmlParts.kb} KB per device).
    {:else if summaryText}{summaryText}{/if}
  </div>
  <div id="cache-content">
    {#if previewError}
      <div class="alert alert-danger">{previewError}</div>
    {:else if previewTunes && previewTunes.length === 0}
      <div class="alert alert-info">No tunes would be cached with these settings.</div>
    {:else if previewTunes}
      <table class="table table-sm" id="cache-table">
        <thead>
          <tr>
            <th style="width:3rem;">#</th><th>Tune</th><th>Type</th><th>Tier</th><th>Popularity</th>
          </tr>
        </thead>
        <tbody>
          {#each previewTunes as t, i (i)}
            <tr>
              <td class="text-muted">{i + 1}</td>
              <td><a href="/sessions/{sessionPath}/tunes/{t.tune_id}" class="tune-link">{t.name}</a></td>
              <td>{#if t.tune_type}{t.tune_type}{:else}<span class="text-muted">-</span>{/if}</td>
              <td>
                {#if t.tier === 'session'}<span class="badge badge-primary">session</span>{:else}<span class="badge badge-secondary">global</span>{/if}
              </td>
              <td class="text-muted">{popularityFor(t)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</section>
