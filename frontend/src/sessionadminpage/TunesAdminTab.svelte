<script>
  // i18n-converted
  // Tunes tab: grid of all tunes played at this session — search (free text or
  // tune id/URL) + sortable columns, fetched once when the tab is active.
  import { untrack } from 'svelte'
  import { LoadError, SearchField, t, tuneTypeName } from '../lib/index.js'
  import { createAbcMatcher } from '../shared/abcfilter.svelte.js'
  import { compareValues, filterTuneList, tuneSortValue } from './logic.js'

  let { sessionPath, load } = $props()

  let allTunes = $state(null) // null until loaded
  let loadError = $state(null)
  let search = $state('')
  let sortColumn = $state('tune_name')
  let sortDirection = $state('asc')
  let started = false

  let loading = $state(false)

  // A failure renders LoadError (with Retry) in place of the table.
  function loadTunes() {
    loading = true
    fetch(`/api/admin/sessions/${sessionPath}/tunes`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error || !data.tunes) throw new Error(data.error || 'tunes load failed')
        loadError = null
        allTunes = data.tunes
      })
      .catch((error) => {
        console.error('Error loading session tunes:', error)
        loadError = 'failed'
      })
      .finally(() => {
        loading = false
      })
  }

  $effect(() => {
    if (load && !started) {
      started = true
      loadTunes()
    }
  })

  function sortTunes(column) {
    if (sortColumn === column) {
      // Toggle direction if same column
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc'
    } else {
      // New column, default to ascending
      sortColumn = column
      sortDirection = 'asc'
    }
  }

  // Notation search: the box takes notes as well as names/aliases/keys, but the payload
  // carries no ABC, so the matching ids come from the server. A query that isn't
  // note-shaped never leaves the browser.
  const abcMatch = createAbcMatcher()
  $effect(() => {
    // Tracked: the query, and the SIZE of the list — allTunes is null until the tab's
    // fetch lands, so the first query has nothing to match against and must be retried.
    abcMatch.update(
      search,
      () => untrack(() => (allTunes || []).map((tune) => tune.tune_id)),
      (allTunes || []).length
    )
  })

  const filteredTunes = $derived.by(() => {
    if (!allTunes) return []
    const filtered = filterTuneList(allTunes, search, abcMatch.ids)
    return [...filtered].sort((a, b) => compareValues(tuneSortValue(a, sortColumn), tuneSortValue(b, sortColumn), sortDirection))
  })

  const indicator = (column) => (sortColumn !== column ? '' : sortDirection === 'asc' ? ' ↑' : ' ↓')
</script>

<section class="docs-section">
  <!-- Search Control -->
  <div class="mb-3">
    <div class="d-flex align-items-center gap-3">
      <div class="flex-grow-1">
        <SearchField
          bind:value={search}
          id="tunes-search"
          inputClass="form-control"
          styled={false}
          placeholder={t('Search tunes...')}
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false" />
      </div>
    </div>
  </div>

  <div id="tunes-content">
    {#if loadError}
      <LoadError id="tunes-load-error" message={t("Couldn't load this session's tunes.")} onRetry={loadTunes} retrying={loading} />
    {:else if !allTunes}
      <p class="text-muted">{t('Loading tunes...')}</p>
    {:else if allTunes.length === 0}
      <div class="alert alert-info">{t('No tunes have been played at this session yet.')}</div>
    {:else if filteredTunes.length === 0}
      <div class="alert alert-info">{t('No tunes match the search criteria.')}</div>
    {:else}
      <div class="table-responsive">
        <table class="table table-striped" id="tunes-table">
          <thead>
            <tr>
              <th style="cursor: pointer;" onclick={() => sortTunes('tune_name')}>{t('Tune Name')}{indicator('tune_name')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('session_alias')}>{t('Session Alias')}{indicator('session_alias')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('tune_type')}>{t('Type')}{indicator('tune_type')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('session_key')}>{t('Session Key')}{indicator('session_key')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('setting_key')}>{t('Setting Key')}{indicator('setting_key')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('play_count')}>{t('Plays')}{indicator('play_count')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('want_to_learn')}>{t('Want')}{indicator('want_to_learn')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('learning')}>{t('Learning')}{indicator('learning')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('learned')}>{t('Learned')}{indicator('learned')}</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredTunes as tune (tune.tune_id)}
              <tr>
                <td class="tune-name">
                  <a href="/sessions/{sessionPath}/tunes/{tune.tune_id}" class="tune-link">
                    {tune.tune_name}
                  </a>
                  <!-- Here because its NOTATION matched, not its name/alias/type/key. -->
                  {#if abcMatch.ids.has(tune.tune_id)}<span class="abc-only-badge" title={t('Matched the notation')}>♪</span>{/if}
                </td>
                <td class="tune-alias">
                  {#if tune.session_alias && tune.session_alias !== tune.tune_name}{tune.session_alias}{:else}<span class="text-muted">-</span>{/if}
                </td>
                <td class="tune-type">{#if tune.tune_type}{tuneTypeName(tune.tune_type)}{:else}<span class="text-muted">-</span>{/if}</td>
                <td class="tune-session-key">{#if tune.session_key}{tune.session_key}{:else}<span class="text-muted">-</span>{/if}</td>
                <td class="tune-setting-key">{#if tune.setting_key}{tune.setting_key}{:else}<span class="text-muted">-</span>{/if}</td>
                <td class="tune-play-count text-center">{tune.play_count}</td>
                <td class="tune-want-to-learn text-center">{#if tune.want_to_learn_count > 0}{tune.want_to_learn_count}{:else}<span class="text-muted">-</span>{/if}</td>
                <td class="tune-learning text-center">{#if tune.learning_count > 0}{tune.learning_count}{:else}<span class="text-muted">-</span>{/if}</td>
                <td class="tune-learned text-center">{#if tune.learned_count > 0}{tune.learned_count}{:else}<span class="text-muted">-</span>{/if}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>
