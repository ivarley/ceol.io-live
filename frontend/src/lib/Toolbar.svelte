<script>
  import SearchField from './SearchField.svelte'

  // Toolbar (spec 052 §B8 Stage 1): one line above a list — a SearchField plus
  // optional filter / sort / add buttons — and the filter panel that expands
  // DIRECTLY BENEATH IT.
  //
  // The panel's placement is the point. A filter refines the list immediately
  // below this line, so that is where it belongs, attached to the button that
  // opened it (a notch points back at it). The prototype briefly tried a bottom
  // sheet and it read as disconnected: you press at the top of the screen and
  // something appears at the bottom. A popover is not the escape hatch either —
  // on iPhone a popover anchored to a control adapts into a bottom sheet by
  // default, so the native port would land right back on the thing we rejected.
  // My Tunes already ships this pattern (filter-panel-toggle / filter-panel /
  // clear-filters-btn); this generalizes it rather than inventing it.
  //
  // Open/close is a CLASS TOGGLE on live nodes, never a re-render, so both
  // directions animate. The host owns `open` (bindable) and the filter state;
  // Toolbar owns only the chrome.
  let {
    // --- search ---
    // `search` replaces the built-in field entirely. Two of the three session
    // tabs need it: the Logs filter is a combobox whose dropdown is positioned
    // against its own wrapper, and the Tunes field carries a long tail of
    // autocomplete/spellcheck attributes. Toolbar's real job is the LINE and the
    // panel beneath it; which control does the searching is the page's business.
    search = null, // snippet
    query = $bindable(''),
    placeholder = 'Search…',
    debounce = 300,
    onSearch = () => {},

    // --- filter ---
    // `aside` renders BETWEEN the toolbar line and the filter panel: for a control
    // that is always visible and belongs with the search rather than inside the
    // drawer. My Tunes puts its learn-status segment here, so opening the drawer
    // pushes the drawer's own contents down and leaves the status where it was.
    aside = null, // snippet
    filter = null, // snippet: the panel's contents (the host's own controls)
    open = $bindable(false), // is the panel expanded?
    activeCount = 0, // how many filters are set (dots the button, shows Clear)
    onClear = null, // set => a "Clear filters" button appears in the panel

    // --- the other two controls ---
    onSort = null, // set => a sort button (host opens its own menu from it)
    sortActive = false, // mark it when sorting is not the default
    onAdd = null, // set => an add (+) button
    addHref = null, // render the add control as a real link (it navigates)
    addTitle = 'Add',

    // Legacy hooks. These pages already have ids and a button skin that CSS and
    // the e2e suite key on, and this component is meant to wear them rather than
    // rename everything at once (spec 035's DOM-contract discipline).
    filterId = null,
    panelId = null,
    addId = null,
    buttonClass = '',

    styled = true,
    toolbarClass = '',
    searchWrapperClass = '',
    searchInputClass = '',
    ...rest
  } = $props()

  let searchEl = $state(null)
  export function focus() {
    searchEl?.focus()
  }

  // The notch sits under the filter button, so it has to count the controls
  // that come AFTER it. Kept here rather than in CSS because only this
  // component knows which buttons were asked for.
  const notchRight = $derived(21 + ((onSort ? 1 : 0) + (onAdd ? 1 : 0)) * 50)
</script>

<div class="kit-toolbar-wrap">
  <div {...rest} class="kit-toolbar {toolbarClass}">
    {#if search}
      {@render search()}
    {:else}
      <SearchField
        bind:this={searchEl}
        bind:value={query}
        {placeholder}
        {debounce}
        {onSearch}
        {styled}
        wrapperClass="kit-toolbar-search {searchWrapperClass}"
        inputClass={searchInputClass}
      />
    {/if}

    {#if filter}
      <button
        type="button"
        id={filterId}
        class="kit-tool-btn kit-tool-filter {buttonClass}"
        class:on={activeCount > 0}
        class:open
        class:active={open || activeCount > 0}
        title="Show filters"
        aria-label="Filter"
        aria-expanded={open}
        onclick={() => (open = !open)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" />
          <line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" />
          <line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" />
          <line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" />
          <line x1="17" y1="16" x2="23" y2="16" />
        </svg>
        {#if activeCount > 0}<span class="kit-tool-badge"></span>{/if}
      </button>
    {/if}

    {#if onSort}
      <button
        type="button"
        class="kit-tool-btn kit-tool-sort"
        class:on={sortActive}
        aria-label="Sort"
        onclick={(e) => onSort(e)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"
          ><path d="M4 7h10M4 12h6M4 17h3" /><path d="M17.5 7.5v9M14.5 13.5l3 3 3-3" /></svg
        >
      </button>
    {/if}

    {#if onAdd || addHref}
      <!-- An anchor when it navigates, a button when it acts: the session-tunes
           add is a real URL you can open in a new tab, the others are not. -->
      {#if addHref}
        <a
          id={addId}
          href={addHref}
          class="kit-tool-btn kit-tool-add {buttonClass}"
          title={addTitle}
          aria-label={addTitle}
          onclick={onAdd}>+</a>
      {:else}
        <button
          type="button"
          id={addId}
          class="kit-tool-btn kit-tool-add {buttonClass}"
          title={addTitle}
          aria-label={addTitle}
          onclick={onAdd}>+</button>
      {/if}
    {/if}
  </div>

  {#if aside}
    {@render aside()}
  {/if}

  {#if filter}
    <div id={panelId} class="kit-filter-panel" class:open style="--kit-notch-right: {notchRight}px">
      <div class="kit-filter-inner">
        {@render filter()}
        {#if onClear && activeCount > 0}
          <button type="button" class="kit-filter-clear" onclick={onClear}>Clear filters</button>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .kit-toolbar-wrap {
    display: flex;
    flex-direction: column;
    /* Fill the host, whatever the host is. In a block parent this is already
       true; in a FLEX parent a lone child is `flex: 0 1 auto` and shrinks to its
       content, which is how two of the three session tabs ended up with a
       toolbar ~100px narrower than the tab it sat in. A toolbar is the full
       width of the list it filters, so the component guarantees that itself
       rather than asking every host to remember. */
    flex: 1 1 auto;
    min-width: 0;
  }
  .kit-toolbar {
    display: flex;
    gap: var(--sp-2, 8px);
    align-items: stretch;
  }
  .kit-toolbar :global(.kit-toolbar-search) {
    flex: 1;
    min-width: 0;
  }

  .kit-tool-btn {
    position: relative;
    flex: 0 0 auto;
    width: 42px;
    min-height: 42px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font: inherit;
    font-size: 24px;
    line-height: 1;
    cursor: pointer;
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-sm, 4px);
    background: var(--bg-color, #fff);
    color: var(--secondary-text, #888);
  }
  .kit-tool-btn svg {
    width: 20px;
    height: 20px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.9;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .kit-tool-btn.on,
  .kit-tool-btn.open,
  .kit-tool-add {
    color: var(--primary, #65b464);
  }
  /* A dot, not a number: "there are filters on" is the fact that matters, and a
     count would compete with the list's own numbers for attention. */
  .kit-tool-badge {
    position: absolute;
    top: 7px;
    right: 8px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--primary, #65b464);
    border: 2px solid var(--bg-color, #fff);
  }

  /* grid-template-rows 0fr -> 1fr animates a panel of UNKNOWN height, which
     max-height cannot do without a magic number that clips or lags. */
  .kit-filter-panel {
    display: grid;
    grid-template-rows: 0fr;
    opacity: 0;
    transition:
      grid-template-rows var(--dur, 0.24s) var(--ease, ease-out),
      opacity var(--dur-quick, 0.18s) var(--ease, ease-out);
  }
  .kit-filter-inner {
    overflow: hidden;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--sp-3, 12px);
  }
  .kit-filter-panel.open {
    grid-template-rows: 1fr;
    opacity: 1;
  }
  .kit-filter-panel.open .kit-filter-inner {
    margin-top: var(--sp-2, 8px);
    padding: var(--sp-3, 12px);
    background: var(--bg-color, #fff);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r, 8px);
    position: relative;
  }
  /* The notch: says which button opened this, so the panel reads as attached
     to the toolbar rather than as a slab that appeared under it. */
  .kit-filter-panel.open .kit-filter-inner::before {
    content: '';
    position: absolute;
    top: -6px;
    right: var(--kit-notch-right, 21px);
    width: 11px;
    height: 11px;
    margin-right: -5px;
    background: var(--bg-color, #fff);
    border-left: 1px solid var(--border-color, #ddd);
    border-top: 1px solid var(--border-color, #ddd);
    transform: rotate(45deg);
  }
  .kit-filter-clear {
    align-self: flex-start;
    font: inherit;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: var(--primary, #65b464);
  }

  @media (prefers-reduced-motion: reduce) {
    .kit-filter-panel {
      transition: none;
    }
  }
</style>
