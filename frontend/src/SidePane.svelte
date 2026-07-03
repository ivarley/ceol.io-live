<script>
  import TuneSearch from './TuneSearch.svelte'

  // Desktop-only persistent right pane (spec 028): the "likely next tune" suggestion on
  // top, then the shared search body — always visible instead of modal-gated. Only mounted
  // when the viewport is wide (≥900px), so mobile never pays for it.
  let {
    config,
    suggestion = null, // App's nextSuggestion (null in View mode / mid-set)
    preferType = null,
    displayStatus = 'live',
    onAdd, // App gates this by mode (in read-only View it confirms the edit-mode switch)
    onAddSuggestion,
    onDismissSuggestion,
  } = $props()

  let searchEl // the TuneSearch instance
  // Clear the pane search — called by App after a deferred (confirmed) add, so it ends in
  // the same idle state a direct edit-mode add leaves behind.
  export function resetSearch() {
    searchEl?.reset()
  }
</script>

<aside class="sidepane">
  {#if suggestion}
    <div class="pane-suggest">
      <div class="ps-top">
        <span class="ps-label">→ Usually next</span>
        <button class="ps-dismiss" title="Don't suggest this next" aria-label="Dismiss suggestion" onclick={onDismissSuggestion}>×</button>
      </div>
      <div class="ps-name">{suggestion.name}</div>
      <div class="ps-row">
        <span class="ps-type">{suggestion.tune_type || ''}</span>
        <button class="ps-add" onclick={() => onAddSuggestion(suggestion)}>＋ Add</button>
      </div>
    </div>
  {/if}
  <TuneSearch bind:this={searchEl} variant="pane" initialQuery="" {config} {preferType} {displayStatus} {onAdd} />
</aside>
