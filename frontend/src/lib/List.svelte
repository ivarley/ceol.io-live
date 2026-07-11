<script>
  // List (spec 035): browse-mode results (deep-search cards, ul.results).
  // ArrowUp/ArrowDown move the active row, Enter selects — and deliberately NO
  // "N of M" label: counting positions is the Pager's job (inspect mode).
  let {
    items = [],
    active = $bindable(-1), // index of the keyboard-active row (-1 = none)
    onSelect = () => {},
    row, // snippet(item, isActive) — the row's content; wrapper li handles state
  } = $props()

  // A shrunk list invalidates a stale highlight.
  $effect(() => {
    if (active >= items.length) active = -1
  })

  let el = $state(null)
  function move(dir) {
    const n = items.length
    if (!n) return
    active = active < 0 ? (dir > 0 ? 0 : n - 1) : Math.max(0, Math.min(n - 1, active + dir))
    // optional chain: jsdom has no scrollIntoView
    el?.querySelector('.kit-list-row.active')?.scrollIntoView?.({ block: 'nearest' })
  }
  function onKey(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      move(e.key === 'ArrowDown' ? 1 : -1)
    } else if (e.key === 'Enter' && active >= 0 && items[active] !== undefined) {
      e.preventDefault()
      onSelect(items[active])
    }
  }
</script>

<ul
  class="kit-list"
  role="listbox"
  tabindex="0"
  aria-activedescendant={active >= 0 ? 'kit-list-row-' + active : undefined}
  bind:this={el}
  onkeydown={onKey}
>
  {#each items as item, i}
    <li
      id="kit-list-row-{i}"
      class="kit-list-row"
      class:active={i === active}
      role="option"
      aria-selected={i === active}
      onclick={() => {
        active = i
        onSelect(item)
      }}
    >
      {#if row}{@render row(item, i === active)}{:else}{String(item)}{/if}
    </li>
  {/each}
</ul>

<style>
  .kit-list {
    list-style: none;
    margin: 0;
    padding: 0;
    overflow-y: auto;
  }
  .kit-list:focus {
    outline: none;
  }
  .kit-list-row {
    padding: var(--sp-2, 8px) var(--sp-3, 12px);
    border-bottom: 1px solid var(--border-color, #ddd);
    cursor: pointer;
  }
  .kit-list-row:hover {
    background: var(--hover-bg, #f8f9fa);
  }
  .kit-list-row.active {
    background: var(--hover-bg, #f8f9fa);
    box-shadow: inset 2px 0 0 var(--primary, #00a1e0);
  }
</style>
