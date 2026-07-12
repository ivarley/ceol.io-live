<script>
  import { Tabs as BitsTabs } from 'bits-ui'

  // Tabs (spec 035): THE tab engine — horizontal tab buttons on desktop, and a
  // design-time knob (mobileSelect) deciding whether the SAME sections collapse
  // behind a <select> under 768px (promoted from person_details.html /
  // admin_tabs.html). Both controls always render; CSS media queries pick which
  // one shows. Few tabs fit a phone fine, so 'auto' (the default) only switches
  // to the select when the tab count genuinely overflows a phone width.
  //
  // Two modes:
  //  * value mode (default): bits-ui Tabs — client-side switching, bind:value.
  //  * navigate mode: each tab is a real <a href> (middle-click works) and the
  //    mobile select performs the navigation — for pages whose tabs are routes.
  //
  // Panes: one children snippet receiving the active tab id. Callers either
  //  branch on it ({#if active === 'x'}) or keep every pane component mounted
  //  with an `active` flag when pane state must survive switching.
  //
  // Skinning: pages keep their existing look by passing their legacy classes
  //  (listClass/tabClass/selectClass) and styled={false} to drop the kit's
  //  decorative skin; the structural responsive rule always applies. Triggers
  //  carry data-tab={id} and an `active` class so legacy CSS and e2e selectors
  //  keep working.
  let {
    tabs = [], // [{ id, label, href?, domId? }] — href per tab in navigate mode; domId = DOM id for the trigger (aria-labelledby targets)
    value = $bindable(), // active tab id; defaults to the first tab
    onValueChange = () => {},
    navigate = false,
    // navigate-mode seam: replace to intercept (tests) — default is a real navigation
    onNavigate = (href) => (window.location.href = href),
    // Mobile behavior under 768px: true = always the <select>, false = keep the
    // visual tabs, 'auto' = select only when there are more than 4 tabs.
    mobileSelect = 'auto',
    styled = true, // false: structural behavior only, skin comes from the page
    listId = undefined,
    listClass = '',
    tabClass = '',
    selectId = undefined,
    selectClass = '',
    paneClass = '',
    selectLabel = 'Section',
    children, // snippet(activeId)
  } = $props()

  if (value === undefined) value = tabs[0]?.id

  function handleChange(v) {
    onValueChange(v)
  }

  function onSelectChange(e) {
    const v = e.currentTarget.value
    if (navigate) {
      const t = tabs.find((x) => x.id === v)
      if (t?.href) onNavigate(t.href)
      return
    }
    value = v
    handleChange(v)
  }

  const useMobileSelect = $derived(mobileSelect === true || (mobileSelect === 'auto' && tabs.length > 4))
  const rootClass = $derived(
    'kit-tabs' + (styled ? ' kit-tabs--styled' : '') + (useMobileSelect ? ' kit-tabs--mselect' : '')
  )
</script>

{#if navigate}
  <div class={rootClass}>
    <nav id={listId} class="kit-tabs-list {listClass}">
      {#each tabs as t (t.id)}
        <a
          href={t.href}
          id={t.domId}
          class="kit-tab {tabClass}"
          class:active={value === t.id}
          data-tab={t.id}
          data-state={value === t.id ? 'active' : 'inactive'}
          aria-current={value === t.id ? 'page' : undefined}>{t.label}</a>
      {/each}
    </nav>
    <select id={selectId} class="kit-tabs-select {selectClass}" aria-label={selectLabel} {value} onchange={onSelectChange}>
      {#each tabs as t (t.id)}
        <option value={t.id}>{t.label}</option>
      {/each}
    </select>
    <div class="kit-tabs-pane {paneClass}">
      {@render children?.(value)}
    </div>
  </div>
{:else}
  <BitsTabs.Root bind:value onValueChange={handleChange} class={rootClass}>
    <BitsTabs.List id={listId} class="kit-tabs-list {listClass}">
      {#each tabs as t (t.id)}
        <BitsTabs.Trigger
          value={t.id}
          id={t.domId}
          class="kit-tab {tabClass}{value === t.id ? ' active' : ''}"
          data-tab={t.id}>{t.label}</BitsTabs.Trigger>
      {/each}
    </BitsTabs.List>
    <select id={selectId} class="kit-tabs-select {selectClass}" aria-label={selectLabel} {value} onchange={onSelectChange}>
      {#each tabs as t (t.id)}
        <option value={t.id}>{t.label}</option>
      {/each}
    </select>
    <div class="kit-tabs-pane {paneClass}">
      {@render children?.(value)}
    </div>
  </BitsTabs.Root>
{/if}

<style>
  /* A clicked tab shouldn't wear the browser's focus ring — that's for
     keyboard navigation (:focus-visible) only. Applies to every skin. */
  :global(.kit-tab:focus) {
    outline: none;
  }
  :global(.kit-tab:focus-visible) {
    outline: 2px solid var(--primary, #00a1e0);
    outline-offset: -2px;
  }

  /* Decorative skin — only under .kit-tabs--styled so pages with a legacy
     skin (tab-button / nav-link) aren't fought by kit rules. */
  :global(.kit-tabs--styled .kit-tabs-list) {
    display: flex;
    gap: var(--sp-1, 4px);
    border-bottom: 1px solid var(--border-color, #ddd);
  }
  :global(.kit-tabs--styled .kit-tab) {
    background: none;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: var(--r-sm, 4px) var(--r-sm, 4px) 0 0;
    padding: var(--sp-2, 8px) var(--sp-4, 16px);
    margin-bottom: -1px;
    font: inherit;
    color: var(--primary, #00a1e0);
    cursor: pointer;
    text-decoration: none;
  }
  :global(.kit-tabs--styled .kit-tab:hover) {
    background: var(--hover-bg, #f8f9fa);
  }
  /* bits-ui stamps data-state="active"; navigate mode mirrors it */
  :global(.kit-tabs--styled .kit-tab[data-state='active']) {
    border-color: var(--border-color, #ddd);
    border-bottom: 1px solid var(--bg-color, #fff);
    color: var(--text-color, #252930);
  }
  :global(.kit-tabs--styled .kit-tabs-select) {
    width: 100%;
    padding: var(--sp-2, 8px);
    font: inherit;
    background: var(--input-bg, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-sm, 4px);
  }
  :global(.kit-tabs--styled .kit-tabs-pane) {
    padding-top: var(--sp-4, 16px);
  }

  /* Structural responsive rule — applies skinned or not, but only for hosts
     whose mobileSelect knob resolved to the select (.kit-tabs--mselect). */
  :global(.kit-tabs .kit-tabs-select) {
    display: none;
  }
  @media (max-width: 767.98px) {
    :global(.kit-tabs--mselect .kit-tabs-list) {
      display: none;
    }
    :global(.kit-tabs--mselect .kit-tabs-select) {
      display: block;
      width: 100%;
    }
  }
</style>
