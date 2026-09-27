<script>
  // Catalogue matches, below your own (spec 052 §B1).
  //
  // "Find a tune" used to be a hamburger item opening a full-screen overlay. The tab
  // bar has no menu, and search should not cost a tab, so the answer is that the Tunes
  // search reaches the whole catalogue: your matching tunes stay exactly where they
  // are, and anything else appears BELOW a divider that says so.
  //
  // Below, and clearly labelled, because the two lists mean different things. A result
  // here is not a tune you have — tapping it opens the add flow rather than the tune
  // you were expecting, and a mixed list would make that a surprise every time.
  import { Row } from '../lib/index.js'

  let {
    results = [],
    loading = false,
    failed = false, // the search itself failed: say so, rather than show no matches
    query = '',
    onPick = () => {},
    onRetry = () => {},
  } = $props()
</script>

{#if loading || failed || results.length}
  <div class="notlist" id="not-on-your-list">
    <div class="notlist-divider">
      <span class="notlist-label">Not on your list</span>
    </div>

    {#if loading && !results.length}
      <div class="notlist-empty">Searching the catalogue for “{query}”…</div>
    {:else if failed}
      <div class="notlist-empty notlist-failed">
        Couldn't search the catalogue. Check your connection, then
        <button type="button" class="notlist-retry" onclick={onRetry}>try again</button>.
      </div>
    {:else}
      <div class="notlist-rows">
        {#each results as tune (tune.tune_id)}
          <Row
            styled={false}
            rowClass="notlist-row"
            onclick={() => onPick(tune)}
            title={tune.name}>
            {#snippet trailing()}
              <span class="notlist-meta">
                {#if tune.tune_type}<span class="notlist-type">{tune.tune_type}</span>{/if}
                <span class="notlist-add" aria-hidden="true">+</span>
              </span>
            {/snippet}
          </Row>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .notlist {
    margin: 1.25rem 0 0;
  }

  .notlist-divider {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.25rem;
    /* Lines the label and the rows up with the tune cards above, which carry their
       own inner padding while running edge to edge. */
    padding-left: 10px;
  }

  .notlist-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border-color);
  }

  .notlist-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.55;
    white-space: nowrap;
  }

  .notlist-empty {
    padding: 0.75rem 10px;
    opacity: 0.55;
    font-size: 0.9rem;
  }

  .notlist-rows :global(.notlist-row) {
    width: 100%;
    padding: 0.7rem 10px;
    background: none;
    border: none;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
    text-align: left;
    cursor: pointer;
  }

  .notlist-rows :global(.notlist-row:hover) {
    color: var(--primary);
  }

  .notlist-meta {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
  }

  .notlist-type {
    font-size: 0.75rem;
    opacity: 0.55;
  }

  /* Says what the row does without spending a button on every one of them. */
  .notlist-add {
    color: var(--primary);
    font-size: 1.25rem;
    line-height: 1;
  }
  /* A failure is news, not an empty state: full-strength text, not the muted grey. */
  .notlist-failed {
    color: var(--text-color);
  }
  .notlist-retry {
    padding: 0;
    border: 0;
    background: none;
    color: var(--primary, #65b464);
    font: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
</style>
