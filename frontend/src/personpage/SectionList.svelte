<script>
  // The profile's sections, as a list of places to go (spec 052 §B3).
  //
  // These were tabs. They are rows because the page already had a vertical list of
  // account actions underneath them, and one screen offering two kinds of menu is
  // the thing this replaces. Rows also give each section room for a line saying what
  // is in it, which a tab strip never had space for — and on a phone six tabs were a
  // strip you had to push sideways to discover the last two.
  //
  // Same Row component and the same shape as the Account list below, on purpose:
  // "go and look at this" should look identical wherever it appears on the page.
  import { Row } from '../lib/index.js'

  let { sections = [], heading = 'More', onOpen = () => {} } = $props()
</script>

{#if sections.length}
  <section class="sections" id="profile-sections">
    <h2 class="sections-heading">{heading}</h2>
    <div class="sections-list">
      {#each sections as s (s.id)}
        <Row
          styled={false}
          rowClass="section-row"
          id={s.domId}
          data-tab={s.id}
          title={s.label}
          subtitle={s.hint || ''}
          onclick={() => onOpen(s.id)}>
          {#snippet trailing()}<span class="section-chev" aria-hidden="true">›</span>{/snippet}
        </Row>
      {/each}
    </div>
  </section>
{/if}

<style>
  .sections {
    margin: 2rem 0 0;
  }

  .sections-heading {
    font-family: 'Poppins', sans-serif;
    font-weight: 600;
    font-size: 1.05rem;
    margin: 0 0 0.5rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .sections-list :global(.section-row) {
    width: 100%;
    padding: 0.85rem 0.25rem;
    background: none;
    border: none;
    color: var(--text-color);
    text-align: left;
    cursor: pointer;
  }

  .sections-list :global(.section-row + .section-row) {
    border-top: 1px solid var(--border-color);
  }

  .sections-list :global(.section-row:hover) {
    color: var(--primary);
  }

  .sections-list :global(.kit-row-sub) {
    font-size: 0.82rem;
    opacity: 0.6;
  }

  .section-chev {
    opacity: 0.4;
    font-size: 1.2rem;
    line-height: 1;
  }
</style>
