<script>
  import { Tabs as BitsTabs } from 'bits-ui'

  // Tabs (spec 035): THE tab engine — one horizontal strip of tabs at every width.
  //
  // It used to carry a second control: under 768px, pages with more than four tabs
  // collapsed the same sections behind a <select> (promoted from person_details.html
  // / admin_tabs.html). That is retired (spec 052 §B3). It had no iOS counterpart —
  // nothing in the platform turns a tab bar into a dropdown — so every page using it
  // was a page whose navigation could not be ported, only redesigned. Too many tabs
  // for a phone width now SCROLL, which is an idiom both platforms have.
  //
  // Two modes:
  //  * value mode (default): bits-ui Tabs — client-side switching, bind:value.
  //  * navigate mode: each tab is a real <a href> (middle-click works) — for
  //    pages whose tabs are routes.
  //
  // Panes: one children snippet receiving the active tab id. Callers either
  //  branch on it ({#if active === 'x'}) or keep every pane component mounted
  //  with an `active` flag when pane state must survive switching.
  //
  // Skinning: pages keep their existing look by passing their legacy classes
  //  (listClass/tabClass) and styled={false} to drop the kit's
  //  decorative skin; the structural responsive rule always applies. Triggers
  //  carry data-tab={id} and an `active` class so legacy CSS and e2e selectors
  //  keep working.
  let {
    // [{ id, label, count?, href?, domId? }] — href per tab in navigate mode; domId =
    // DOM id for the trigger (aria-labelledby targets). `count` renders muted after the
    // label (spec 052 §B8 Stage 2): how many are in there is worth knowing before you
    // open it, but it is not the name of the tab, so it must not compete with it.
    // Omit it (or pass null) where the number is unknown or the viewer may not see it —
    // 0 is a real count and renders as one.
    tabs = [],
    value = $bindable(), // active tab id; defaults to the first tab
    onValueChange = () => {},
    navigate = false,
    // navigate-mode seam: replace to intercept (tests) — default is a real navigation
    onNavigate = (href) => (window.location.href = href),
    styled = true, // false: structural behavior only, skin comes from the page
    listId = undefined,
    listClass = '',
    tabClass = '',
    paneClass = '',
    children, // snippet(activeId)
  } = $props()

  if (value === undefined) value = tabs[0]?.id

  function handleChange(v) {
    onValueChange(v)
  }

  const rootClass = $derived('kit-tabs' + (styled ? ' kit-tabs--styled' : ''))
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
          aria-current={value === t.id ? 'page' : undefined}
          >{t.label}{#if t.count != null}{' '}<span class="kit-tab-count">{t.count}</span>{/if}</a>
      {/each}
    </nav>
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
          data-tab={t.id}
          >{t.label}{#if t.count != null}{' '}<span class="kit-tab-count">{t.count}</span
            >{/if}</BitsTabs.Trigger>
      {/each}
    </BitsTabs.List>
    <div class="kit-tabs-pane {paneClass}">
      {@render children?.(value)}
    </div>
  </BitsTabs.Root>
{/if}

<style>
  /* A clicked tab shouldn't wear the browser's focus ring — that's for
     keyboard navigation (:focus-visible) only. Applies to every skin. */
  /* Muted and a size down: present, secondary to the tab's name. */
  :global(.kit-tab-count) {
    /* A real space already separates it (see the markup — the accessible name is
       the concatenated text), so this is the rest of the gap, not all of it. */
    margin-left: 0.15em;
    opacity: 0.55;
    font-weight: 400;
    font-size: 0.85em;
    font-variant-numeric: tabular-nums;
  }

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
  :global(.kit-tabs--styled .kit-tabs-pane) {
    padding-top: var(--sp-4, 16px);
  }

  /* Too many tabs for the width SCROLL — they do not collapse into a control of a
     different kind (spec 052 §B3). Six tabs on a phone is a strip you push sideways
     on both platforms; a <select> is a thing only the web has, and a page navigated
     by one cannot be ported, only redesigned.

     Structural, so it applies skinned or not. */
  @media (max-width: 767.98px) {
    :global(.kit-tabs .kit-tabs-list) {
      flex-wrap: nowrap;
      overflow-x: auto;
      overflow-y: hidden;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
      /* The active tab's underline sits on the bottom edge; without this the
         scroll container clips it. */
      padding-bottom: 1px;
    }
    :global(.kit-tabs .kit-tabs-list::-webkit-scrollbar) {
      display: none;
    }
    /* Only SHRINKING is disabled, not the whole flex shorthand. A tab that can
       shrink will squeeze to fit rather than overflow, and six squeezed tabs are
       six unreadable slivers — but writing `flex: 0 0 auto` here would also cancel
       any grow a page has set, and this selector outranks a page's own `.tab-button`.
       That is not hypothetical: it flattened the session page's three tabs, which
       divide the width evenly via `flex: 1 1 0`. Killing shrink alone leaves that
       working (1 0 0 still fills) and still lets six tabs overflow and scroll. */
    :global(.kit-tabs .kit-tab) {
      flex-shrink: 0;
      white-space: nowrap;
    }
  }

</style>
