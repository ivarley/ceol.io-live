<script>
  // i18n-converted
  // Local Cache tab (spec 024 fast-match vocabulary): N/M limits with a
  // debounced live preview of what each device would download, plus save.
  let { sessionPath, sessionLimit, globalLimit, load } = $props()

  import { LoadError, toast, t, tn, formatNumber, tuneTypeName } from '../lib/index.js'

  let n = $state(String(sessionLimit))
  let m = $state(String(globalLimit))
  let summaryHtmlParts = $state(null) // {session_count, global_count, total, kb}
  let summaryText = $state(t('Loading preview…'))
  let previewTunes = $state(null)
  let previewError = $state(null) // null | '' (connection) | the server's own message
  let previewLoading = $state(false)
  let saving = $state(false)
  let cachePreviewTimer = null
  let started = false

  function onEdit() {
    clearTimeout(cachePreviewTimer)
    cachePreviewTimer = setTimeout(loadCachePreview, 300) // debounce live preview
  }

  function loadCachePreview() {
    summaryText = t('Computing preview…')
    summaryHtmlParts = null
    previewLoading = true

    fetch(`/api/admin/sessions/${sessionPath}/tune-cache?n=${encodeURIComponent(n)}&m=${encodeURIComponent(m)}`)
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) {
          summaryText = ''
          previewTunes = null
          previewError = data.error || ''
          return
        }
        renderCachePreview(data)
      })
      .catch((error) => {
        // Never leave the previous preview standing in for these settings.
        console.error('Error loading cache preview:', error)
        summaryText = ''
        previewTunes = null
        previewError = ''
      })
      .finally(() => {
        previewLoading = false
      })
  }

  function renderCachePreview(data) {
    // Estimate the real download size from the LEAN fields the client actually receives
    // (the preview adds tier/plays/tunebook_count, which the vocabulary endpoint strips).
    const lean = data.tunes.map((tune) => ({ tune_id: tune.tune_id, name: tune.name, alias: tune.alias, tune_type: tune.tune_type }))
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
    if (saving) return
    saving = true
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
        saving = false
        if (data.success) {
          toast(t('Local cache settings saved'), 'success')
          loadCachePreview() // reflect the now-saved values
        } else {
          toast(data.error || t("Couldn't save the cache settings. Try again."), 'error')
        }
      })
      .catch((error) => {
        saving = false
        console.error('Error saving cache settings:', error)
        toast(t("Couldn't save the cache settings. Check your connection and try again."), 'error')
      })
  }

  $effect(() => {
    if (load && !started) {
      started = true
      loadCachePreview()
    }
  })

  const popularityFor = (tune) =>
    tune.tier === 'session'
      ? tn(tune.plays, '{n} play here', '{n} plays here')
      : tn(tune.tunebook_count || 0, '{n} tunebooks', '{n} tunebooks', { n: formatNumber(tune.tunebook_count || 0) })
</script>

<section class="docs-section">
  <h2 class="section-heading">{t('Local Tune Cache')}</h2>
  <p class="text-muted">
    {t('The live-logging screen preloads a list of tunes onto each device so typed tune names match instantly — even offline. It holds the')}
    <strong>{'N'}</strong> {t('most-played tunes from this session, plus the')}
    <strong>{'M'}</strong> {t('most globally-popular tunes not already in that set. Bigger numbers match more tunes without a network call, but make each device download a little more.')}
  </p>

  <div class="d-flex flex-wrap align-items-end gap-3 mb-3">
    <div>
      <label for="cache-session-limit" class="form-label mb-1">{'N'} — {t("this session's top tunes")}</label>
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
      <label for="cache-global-limit" class="form-label mb-1">{'M'} — {t('globally-popular extras')}</label>
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
    <button type="button" class="btn btn-primary" id="cache-save-btn" onclick={saveCacheLimits} disabled={saving}>{saving ? t('Saving…') : t('Save')}</button>
  </div>

  <div id="cache-summary" class="mb-3 text-muted">
    {#if summaryHtmlParts}
      {t('Caching')} <strong>{summaryHtmlParts.session_count}</strong> {tn(summaryHtmlParts.session_count, 'session tune', 'session tunes')}
      + <strong>{summaryHtmlParts.global_count}</strong> {t('globally-popular')} = <strong>{summaryHtmlParts.total}</strong> {t('total')}
      {t('(~{kb} KB per device).', { kb: summaryHtmlParts.kb })}
    {:else if summaryText}{summaryText}{/if}
  </div>
  <div id="cache-content">
    {#if previewError !== null}
      <LoadError
        id="cache-preview-error"
        message={previewError ? t("Couldn't load the cache preview: {error}", { error: previewError }) : t("Couldn't load the cache preview.")}
        onRetry={loadCachePreview}
        retrying={previewLoading} />
    {:else if previewTunes && previewTunes.length === 0}
      <div class="alert alert-info">{t('No tunes would be cached with these settings.')}</div>
    {:else if previewTunes}
      <table class="table table-sm" id="cache-table">
        <thead>
          <tr>
            <th style="width:3rem;">#</th><th>{t('Tune')}</th><th>{t('Type')}</th><th>{t('Tier')}</th><th>{t('Popularity')}</th>
          </tr>
        </thead>
        <tbody>
          {#each previewTunes as tune, i (i)}
            <tr>
              <td class="text-muted">{i + 1}</td>
              <td><a href="/sessions/{sessionPath}/tunes/{tune.tune_id}" class="tune-link">{tune.name}</a></td>
              <td>{#if tune.tune_type}{tuneTypeName(tune.tune_type)}{:else}<span class="text-muted">-</span>{/if}</td>
              <td>
                {#if tune.tier === 'session'}<span class="badge badge-primary">{t('session')}</span>{:else}<span class="badge badge-secondary">{t('global')}</span>{/if}
              </td>
              <td class="text-muted">{popularityFor(tune)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</section>
