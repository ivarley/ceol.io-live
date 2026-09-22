<script>
  // SectionHeader (spec 052 §B8 Stage 1): a section's title, an optional icon,
  // and an optional "See all" link to the full list.
  //
  // The icon is a snippet rather than a name, so the kit carries no icon set and
  // each page passes the mark it already uses. The link is what makes a section
  // a SUMMARY: Home and the restructured person page show the first few rows and
  // hand off, instead of paging a long list in place (§B3).
  let {
    title = '',
    seeAllHref = null, // set => the link renders
    seeAllLabel = 'See all',
    level = 2, // heading level, so a page keeps one sane outline
    styled = true,
    headerClass = '',
    icon, // snippet: leading mark
    ...rest
  } = $props()
</script>

<div {...rest} class="kit-sechead{styled ? ' kit-sechead--styled' : ''} {headerClass}">
  <svelte:element this={`h${level}`} class="kit-sechead-title">
    {#if icon}<span class="kit-sechead-icon">{@render icon()}</span>{/if}
    {title}
  </svelte:element>
  {#if seeAllHref}
    <a class="kit-sechead-seeall" href={seeAllHref}>{seeAllLabel}</a>
  {/if}
</div>

<style>
  .kit-sechead {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--sp-3, 12px);
  }
  .kit-sechead-title {
    margin: 0;
    display: inline-flex;
    align-items: center;
    gap: var(--sp-2, 8px);
    min-width: 0;
  }
  .kit-sechead-icon {
    display: inline-flex;
    flex: 0 0 auto;
  }
  .kit-sechead-icon :global(svg) {
    width: 20px;
    height: 20px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .kit-sechead-seeall {
    flex: 0 0 auto;
  }

  .kit-sechead--styled .kit-sechead-title {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .kit-sechead--styled .kit-sechead-icon {
    color: var(--primary, #00a1e0);
  }
  .kit-sechead--styled .kit-sechead-seeall {
    font-size: 0.9rem;
    color: var(--link-color, #00a1e0);
  }
</style>
