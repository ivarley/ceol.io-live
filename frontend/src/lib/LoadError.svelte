<script>
  // LoadError: THE failed-load state. A fetch that fills content and fails must
  // never look like real data (an empty list, "no stats", a silently-reset
  // filter) — render this where the content would be instead: "Couldn't load
  // <what>." plus a Retry that re-runs the fetch.
  let {
    what = 'this', // noun phrase: "the logs", "your tunes"
    message = '', // full override of the sentence, when "Couldn't load X." doesn't fit
    onRetry = null, // re-runs the fetch; no button when omitted
    retrying = false, // host's in-flight flag → busy label, disabled button
    inline = false, // one compact line (filter notes, small panes) vs. a padded block
    ...rest // id, class, data-* pass through
  } = $props()
</script>

<div {...rest} class="kit-load-error {rest.class ?? ''}" class:inline role="alert">
  <span class="kit-load-error-msg">{message || `Couldn't load ${what}.`}</span>
  {#if onRetry}
    <button type="button" class="kit-load-retry" onclick={() => onRetry()} disabled={retrying}>
      {retrying ? 'Retrying…' : 'Retry'}
    </button>
  {/if}
</div>

<style>
  .kit-load-error {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: var(--sp-2, 8px) var(--sp-3, 12px);
    padding: var(--sp-5, 24px) var(--sp-4, 16px);
    color: var(--text-color, #252930);
    text-align: center;
  }
  .kit-load-error.inline {
    justify-content: flex-start;
    padding: var(--sp-1, 4px) 0;
    text-align: left;
    font-size: 0.9rem;
  }
  .kit-load-error-msg {
    color: var(--danger, #dc3545);
  }
  .kit-load-retry {
    padding: 0.25rem 0.8rem;
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r, 8px);
    background: transparent;
    color: var(--primary, #007bff);
    font: inherit;
    cursor: pointer;
  }
  .kit-load-error.inline .kit-load-retry {
    padding: 0.1rem 0.6rem;
  }
  .kit-load-retry:hover:not(:disabled) {
    border-color: var(--primary, #007bff);
  }
  .kit-load-retry:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
