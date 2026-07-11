<script>
  import { Tabs as BitsTabs } from 'bits-ui'

  // Tabs (spec 035): THE responsive tab rule — horizontal tab buttons on
  // desktop, the SAME panes behind a <select> under 768px (promoted from
  // person_details.html / admin_tabs.html). Both controls always render; CSS
  // media queries pick which one shows.
  //
  // Panes: one children snippet receiving the active tab id — the caller
  // branches on it ({#if active === 'x'}), so panes need no registration and
  // both controls drive the same markup.
  let {
    tabs = [], // [{ id, label }]
    value = $bindable(), // active tab id; defaults to the first tab
    onValueChange = () => {},
    children, // snippet(activeId)
  } = $props()

  if (value === undefined) value = tabs[0]?.id

  function handleChange(v) {
    onValueChange(v)
  }
</script>

<BitsTabs.Root bind:value onValueChange={handleChange} class="kit-tabs">
  <BitsTabs.List class="kit-tabs-list">
    {#each tabs as t (t.id)}
      <BitsTabs.Trigger value={t.id} class="kit-tab">{t.label}</BitsTabs.Trigger>
    {/each}
  </BitsTabs.List>
  <select
    class="kit-tabs-select"
    aria-label="Section"
    {value}
    onchange={(e) => {
      value = e.currentTarget.value
      handleChange(value)
    }}
  >
    {#each tabs as t (t.id)}
      <option value={t.id}>{t.label}</option>
    {/each}
  </select>
  <div class="kit-tabs-pane">
    {@render children?.(value)}
  </div>
</BitsTabs.Root>

<style>
  :global(.kit-tabs-list) {
    display: flex;
    gap: var(--sp-1, 4px);
    border-bottom: 1px solid var(--border-color, #ddd);
  }
  :global(.kit-tab) {
    background: none;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: var(--r-sm, 4px) var(--r-sm, 4px) 0 0;
    padding: var(--sp-2, 8px) var(--sp-4, 16px);
    margin-bottom: -1px;
    font: inherit;
    color: var(--primary, #00a1e0);
    cursor: pointer;
  }
  :global(.kit-tab:hover) {
    background: var(--hover-bg, #f8f9fa);
  }
  /* bits-ui stamps the active trigger with data-state="active" */
  :global(.kit-tab[data-state='active']) {
    border-color: var(--border-color, #ddd);
    border-bottom: 1px solid var(--bg-color, #fff);
    color: var(--text-color, #252930);
  }
  .kit-tabs-select {
    display: none;
    width: 100%;
    padding: var(--sp-2, 8px);
    font: inherit;
    background: var(--input-bg, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-sm, 4px);
  }
  .kit-tabs-pane {
    padding-top: var(--sp-4, 16px);
  }
  @media (max-width: 767.98px) {
    :global(.kit-tabs-list) {
      display: none;
    }
    .kit-tabs-select {
      display: block;
    }
  }
</style>
