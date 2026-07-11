<script>
  import { onDestroy } from 'svelte'

  // SearchField (spec 035): debounced text input with a clear-×. THE search
  // input — every page filter box runs on it. No tune/thesession logic here,
  // just "settled text" → onSearch(query).
  //
  //  * Enter flushes immediately (search now, don't wait for the debounce).
  //  * Escape clears when there's text (and stops there); an empty box lets
  //    Escape propagate so a host Sheet/overlay can close.
  //  * Skinning mirrors Tabs: pages keep their legacy input classes via
  //    inputClass/wrapperClass and styled={false}; id/title/autocomplete etc.
  //    pass through to the <input> via ...rest.
  let {
    value = $bindable(''),
    placeholder = 'Search…',
    debounce = 300, // ms of idle before onSearch fires
    onSearch = () => {},
    styled = true, // false: behavior only, skin comes from the page
    wrapperClass = '',
    inputClass = '',
    ...rest // id, aria-label, autocomplete… pass through to the input
  } = $props()

  let inputEl = $state(null)
  export function focus() {
    inputEl && inputEl.focus()
  }

  let timer = null
  function fire() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    onSearch(value)
  }
  function schedule() {
    if (timer) clearTimeout(timer)
    timer = setTimeout(fire, debounce)
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
    } else if (e.key === 'Enter') {
      e.preventDefault()
      fire()
    }
  }
  onDestroy(() => {
    if (timer) clearTimeout(timer)
  })
</script>

<div class="kit-search{styled ? ' kit-search--styled' : ''} {wrapperClass}">
  <input
    {...rest}
    bind:this={inputEl}
    class="kit-search-field {inputClass}"
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
  }
  /* Decorative skin — only under --styled so legacy input classes aren't fought. */
  .kit-search--styled .kit-search-field {
    padding: var(--sp-2, 8px) var(--sp-6, 24px) var(--sp-2, 8px) var(--sp-3, 12px);
    font: inherit;
    background: var(--input-bg, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-sm, 4px);
  }
  .kit-search--styled .kit-search-field:focus {
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
