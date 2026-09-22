<script>
  // Row (spec 052 §B8 Stage 1): the list row — an optional leading slot, a
  // title with an optional subtitle, and an optional trailing slot hard against
  // the right margin. Every scrollable list on a phone is made of these: a tune
  // with its learn status, a logged night with its date block, a person with
  // their instruments.
  //
  // FLEX, NOT GRID — and this is the whole reason the component exists.
  // The prototype's first cut used `grid-template-columns: auto 1fr auto` with
  // `.lead:empty { display: none }`. Hiding a grid child removes it from the
  // grid entirely, so on a row with no lead the body auto-placed into column 1
  // and the trailing element into the STRETCHY middle column — putting the
  // status chip next to the text instead of at the right edge. Rows that had a
  // date block looked perfect, which is why it read as a styling whim rather
  // than a bug. Flex with `margin-left:auto` on the trailing slot has no such
  // failure mode, whatever the row happens to carry.
  //
  // Skinning follows the rest of the kit: pages keep their legacy look by
  // passing their own classes and styled={false}; ids/data-*/onclick pass
  // through via ...rest so existing CSS and e2e selectors keep working.
  let {
    title = '', // plain text; use the `titleContent` snippet for markup
    subtitle = '',
    onclick = null, // set => the row is a real <button>
    href = null, // set (and no onclick) => the row is a real <a>
    styled = true, // false: structure only; skin comes from the page
    rowClass = '',
    lead, // snippet: leading slot (date block, avatar, icon)
    body, // snippet: replaces title+subtitle entirely, for a body with its own
    //       layout (the session People row lays name/badges/instruments inline on
    //       desktop and stacked on a phone — a shape title+subtitle cannot express)
    titleContent, // snippet: replaces `title` when the heading needs markup
    trailing, // snippet: trailing slot (status chip, count, chevron)
    ...rest // id, data-*, aria-*, title… pass through to the row element
  } = $props()

  // A row that does something is a control, not a div: real button/anchor
  // semantics mean keyboard and screen readers get it for free.
  const tag = onclick ? 'button' : href ? 'a' : 'div'
</script>

<svelte:element
  this={tag}
  {...rest}
  type={tag === 'button' ? 'button' : undefined}
  href={tag === 'a' ? href : undefined}
  {onclick}
  class="kit-row{styled ? ' kit-row--styled' : ''} {rowClass}"
>
  {#if lead}<span class="kit-row-lead">{@render lead()}</span>{/if}
  <span class="kit-row-body">
    {#if body}
      {@render body()}
    {:else}
      <span class="kit-row-title">{#if titleContent}{@render titleContent()}{:else}{title}{/if}</span>
      {#if subtitle}<span class="kit-row-sub">{subtitle}</span>{/if}
    {/if}
  </span>
  {#if trailing}<span class="kit-row-trail">{@render trailing()}</span>{/if}
</svelte:element>

<style>
  .kit-row {
    display: flex;
    align-items: center;
    gap: var(--sp-3, 12px);
    width: 100%;
    text-align: left;
  }
  /* The leading slot keeps a fixed width so titles line up down the list, but
     disappears completely when a row has none — without disturbing the rest. */
  .kit-row-lead {
    flex: 0 0 auto;
    display: flex;
    justify-content: center;
  }
  /* min-width:0 is what lets a long title ellipsize instead of pushing the
     trailing slot off the right edge (and the page into sideways scroll). */
  .kit-row-body {
    flex: 1 1 auto;
    min-width: 0;
  }
  /* The default stack. A `body` snippet brings its own layout, so it must not
     inherit this — hence the :has() rather than styling .kit-row-body flatly. */
  .kit-row-body:has(> .kit-row-title) {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .kit-row-title,
  .kit-row-sub {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* margin-left:auto, not a grid column: the trailing slot sits at the right
     margin whatever else the row carries, including nothing. */
  .kit-row-trail {
    flex: 0 0 auto;
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--sp-2, 8px);
  }

  /* Neutral base at ZERO specificity so a page's legacy row classes still paint. */
  :global(:where(.kit-row)) {
    font: inherit;
    color: inherit;
    background: none;
    border: none;
    padding: 0;
    text-decoration: none;
  }
  :global(:where(button.kit-row, a.kit-row)) {
    cursor: pointer;
  }

  /* Decorative skin — only under --styled. */
  .kit-row--styled {
    min-height: 56px;
    padding: var(--sp-2, 8px) var(--sp-3, 12px);
    border-bottom: 1px solid var(--border-color, #ddd);
  }
  .kit-row--styled .kit-row-lead {
    width: 36px;
  }
  .kit-row--styled .kit-row-sub {
    font-size: 0.85em;
    color: var(--secondary-text, #888);
  }
  .kit-row--styled .kit-row-trail {
    color: var(--secondary-text, #888);
    font-size: 0.85em;
  }
  .kit-row--styled:hover {
    background: var(--hover-bg, #f8f9fa);
  }
</style>
