<script>
  import { onDestroy } from 'svelte'

  // SearchField (spec 035): debounced text input with a clear-×. The generic
  // seed that later absorbs the tune-search UIs — no tune/thesession logic
  // here, just "settled text" → onSearch(query).
  let {
    value = $bindable(''),
    placeholder = 'Search…',
    debounce = 300, // ms of idle before onSearch fires
    onSearch = () => {},
    ...rest // aria-label etc. pass through to the input
  } = $props()

  let timer = null
  function schedule() {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      onSearch(value)
    }, debounce)
  }
  // Clearing (× or Escape) reports immediately — an empty box is already settled.
  function clear() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    if (value === '') return
    value = ''
    onSearch('')
  }
  function onKey(e) {
    if (e.key === 'Escape' && value !== '') {
      e.preventDefault()
      e.stopPropagation() // the clear consumed it; don't also close a Sheet
      clear()
    }
  }
  onDestroy(() => {
    if (timer) clearTimeout(timer)
  })
</script>

<div class="kit-search">
  <input
    {...rest}
    class="kit-search-field"
    type="text"
    {placeholder}
    bind:value
    oninput={schedule}
    onkeydown={onKey}
  />
  {#if value}
    <button type="button" class="kit-x" aria-label="Clear search" onclick={clear}>&#215;</button>
  {/if}
</div>

<style>
  .kit-search {
    position: relative;
    display: flex;
    align-items: center;
  }
  .kit-search-field {
    width: 100%;
    padding: var(--sp-2, 8px) var(--sp-6, 24px) var(--sp-2, 8px) var(--sp-3, 12px);
    font: inherit;
    background: var(--input-bg, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-sm, 4px);
  }
  .kit-search-field:focus {
    outline: none;
    border-color: var(--primary, #00a1e0);
  }
  .kit-x {
    position: absolute;
    right: var(--sp-2, 8px);
    background: none;
    border: none;
    padding: 0 2px;
    font-size: 1.1rem;
    line-height: 1;
    color: var(--text-muted, #6c757d);
    cursor: pointer;
  }
  .kit-x:hover {
    color: var(--text-color, #252930);
  }
</style>
