<script>
  // Tunes tab: grid of all tunes played at this session — search (free text or
  // tune id/URL) + sortable columns, fetched once when the tab is active.
  import { compareValues, filterTuneList, tuneSortValue } from './logic.js'

  let { sessionPath, load } = $props()

  let allTunes = $state(null) // null until loaded
  let loadError = $state(null)
  let search = $state('')
  let sortColumn = $state('tune_name')
  let sortDirection = $state('asc')
  let started = false

  $effect(() => {
    if (load && !started) {
      started = true
      fetch(`/api/admin/sessions/${sessionPath}/tunes`)
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            loadError = data.error
            return
          }
          allTunes = data.tunes
        })
        .catch((error) => {
          loadError = `Failed to load tunes: ${error}`
        })
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

  const filteredTunes = $derived.by(() => {
    if (!allTunes) return []
    const filtered = filterTuneList(allTunes, search)
    return [...filtered].sort((a, b) => compareValues(tuneSortValue(a, sortColumn), tuneSortValue(b, sortColumn), sortDirection))
  })

  const indicator = (column) => (sortColumn !== column ? '' : sortDirection === 'asc' ? ' ↑' : ' ↓')
</script>

<section class="docs-section">
  <!-- Search Control -->
  <div class="mb-3">
    <div class="d-flex align-items-center gap-3">
      <div class="flex-grow-1">
        <input
          type="text"
          class="form-control"
          id="tunes-search"
          placeholder="Search tunes..."
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false"
          bind:value={search} />
      </div>
    </div>
  </div>

  <div id="tunes-content">
    {#if loadError}
      <div class="alert alert-danger">{loadError}</div>
    {:else if !allTunes}
      <p class="text-muted">Loading tunes...</p>
    {:else if allTunes.length === 0}
      <div class="alert alert-info">No tunes have been played at this session yet.</div>
    {:else if filteredTunes.length === 0}
      <div class="alert alert-info">No tunes match the search criteria.</div>
    {:else}
      <div class="table-responsive">
        <table class="table table-striped" id="tunes-table">
          <thead>
            <tr>
              <th style="cursor: pointer;" onclick={() => sortTunes('tune_name')}>Tune Name{indicator('tune_name')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('session_alias')}>Session Alias{indicator('session_alias')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('tune_type')}>Type{indicator('tune_type')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('session_key')}>Session Key{indicator('session_key')}</th>
              <th style="cursor: pointer;" onclick={() => sortTunes('setting_key')}>Setting Key{indicator('setting_key')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('play_count')}>Plays{indicator('play_count')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('want_to_learn')}>Want{indicator('want_to_learn')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('learning')}>Learning{indicator('learning')}</th>
              <th style="cursor: pointer; text-align: center;" onclick={() => sortTunes('learned')}>Learned{indicator('learned')}</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredTunes as tune (tune.tune_id)}
              <tr>
                <td class="tune-name">
                  <a href="/sessions/{sessionPath}/tunes/{tune.tune_id}" class="tune-link">
                    {tune.tune_name}
                  </a>
                </td>
                <td class="tune-alias">
                  {#if tune.session_alias && tune.session_alias !== tune.tune_name}{tune.session_alias}{:else}<span class="text-muted">-</span>{/if}
                </td>
                <td class="tune-type">{#if tune.tune_type}{tune.tune_type}{:else}<span class="text-muted">-</span>{/if}</td>
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
