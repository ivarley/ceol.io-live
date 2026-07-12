<script>
  // Seg (spec 035): segmented control — one row of mutually-exclusive option
  // buttons. THE seg — the status 3-ways (tune sheet + add pane), the sort/
  // status filter groups, and the history-scope toggles all run on it.
  //
  // CONTROLLED: the host owns `value`; Seg only paints the active option and
  // reports clicks. `onSelect` fires on EVERY option click — including the
  // active one — because some hosts toggle-off on that (per-instrument status).
  //
  // Skinning mirrors the rest of the kit: pages keep their look by passing
  // legacy classes (segClass/optClass) and styled={false}; options are stamped
  // with an id attribute (idAttr, e.g. "data-status") and an `active` class so
  // legacy CSS and e2e selectors keep working. `secondary` marks one option
  // with `active-secondary` (the my-tunes two-level sort).
  let {
    options = [], // [{ id, label }]
    value = undefined, // active option id (host-owned)
    onSelect = () => {},
    idAttr = 'data-seg', // attribute name the option id is stamped under
    secondary = null, // option id shown as the secondary selection
    styled = true, // false: structure only; skin comes from the page
    segClass = '',
    optClass = '',
    ...rest // role/aria-label/data-* … pass through to the container
  } = $props()

  // Svelte can't spread a dynamic attribute NAME, so build per-option attrs.
  const optAttrs = (id) => ({ [idAttr]: id })
</script>

<div {...rest} class="kit-seg{styled ? ' kit-seg--styled' : ''} {segClass}">
  {#each options as o (o.id)}
    <button
      type="button"
      {...optAttrs(o.id)}
      class="kit-seg-opt {optClass}"
      class:active={value === o.id}
      class:active-secondary={secondary === o.id && value !== o.id}
      onclick={() => onSelect(o.id)}>{o.label}</button>
  {/each}
</div>

<style>
  .kit-seg {
    display: flex;
  }
  /* Neutral button base at ZERO specificity so legacy option classes
     (.tunebook-status-opt, .filter-sort-btn…) or the kit skin paint it. */
  :global(:where(.kit-seg-opt)) {
    font: inherit;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
  }
  /* Decorative skin — only under --styled. */
  .kit-seg--styled {
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-sm, 4px);
    overflow: hidden;
  }
  .kit-seg--styled :global(.kit-seg-opt) {
    flex: 1;
    padding: var(--sp-2, 8px) var(--sp-3, 12px);
    background: var(--bg-color, #fff);
    color: var(--text-color, #252930);
    border-right: 1px solid var(--border-color, #ddd);
  }
  .kit-seg--styled :global(.kit-seg-opt:last-child) {
    border-right: none;
  }
  .kit-seg--styled :global(.kit-seg-opt:hover) {
    background: var(--hover-bg, #f8f9fa);
  }
  .kit-seg--styled :global(.kit-seg-opt.active) {
    background: var(--primary, #00a1e0);
    color: #fff;
  }
</style>
