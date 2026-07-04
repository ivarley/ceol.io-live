<script>
  import { onDestroy, untrack } from 'svelte'
  import { deepSearch, thesessionSearch } from './client.js'
  import Incipit from './Incipit.svelte'
  import { pluralType, parseThesessionId, historyStep } from './logstate.js'

  // The deep-search body (spec 028): one shared component behind BOTH the mobile
  // full-screen modal and the desktop side pane, so local catalog search, the
  // thesession.org remote extension (spec 026), and paste-URL import never fork.
  // Owns all search state; every terminal action collapses to onAdd(payload, name)
  // — the caller decides what "add" means (close the modal, clear, log at cursor).
  let {
    config,
    initialQuery = '', // seed: the composer text (modal) or '' (pane)
    preferType = null, // the cursor set's type — a soft ranking preference, not a filter
    displayStatus = 'live', // gates the remote search (online-only)
    variant = 'pane', // 'modal' shows the Done header + autofocuses the field
    history = [], // page-local recall history (MRU, shared across pane + modal via the parent)
    onRemember = () => {}, // record a used query into the shared history
    onAdd,
    onClose = () => {},
  } = $props()

  const DEEP_TYPES = ['Reel', 'Jig', 'Slip Jig', 'Hornpipe', 'Polka', 'Slide', 'Waltz', 'Barndance', 'Mazurka', 'March', 'Strathspey', 'Three-Two']
  let deepQuery = $state(untrack(() => initialQuery)) // seed once; the field owns it after
  let deepType = $state(null) // hard tune-type filter (the popout)
  let deepMode = $state('mixed') // 'mixed' (name + ABC) | 'name' | 'abc' search mode
  let deepFilterOpen = $state(false) // type-filter popout visible
  let deepResults = $state([])
  let deepLoading = $state(false)
  let deepTimer = null
  let deepSeq = 0
  let hl = $state(-1) // keyboard-highlighted index into deepResults (-1 = none)
  let histPos = $state(null) // recall cursor into `history` (null = live draft, not navigating)

  // "Search on thesession.org" (spec 026): remote results shown BELOW the local ones, fetched
  // ONLY on explicit tap. Deduped against the local list by tune_id (suppress-in-place).
  let tsResults = $state([]) // remote hits for the current query, already deduped
  let tsSearching = $state(false)
  let tsSearched = $state(false) // has the user run a remote search for this query yet?
  let tsPasteUrl = $state('') // the "paste a URL / tune ID" field inside the remote section
  let tsPasteError = $state('')

  function autofocusIf(node, yes) {
    if (yes) node.focus()
  }

  function runSearch() {
    if (deepTimer) clearTimeout(deepTimer)
    deepLoading = true
    hl = -1 // a new query invalidates the keyboard highlight
    // The remote (thesession.org) results were for the previous query — drop them; the user
    // must tap "Search on thesession.org" again for the new query.
    resetThesession()
    deepTimer = setTimeout(async () => {
      const seq = ++deepSeq
      const r = await deepSearch(config, deepQuery.trim(), deepType, preferType, deepMode)
      if (seq === deepSeq) { deepResults = r; deepLoading = false }
    }, 160)
  }
  // Keyboard nav of the local result cards (spec 028). The pane list is a normal top-to-bottom
  // column, so ArrowDown = next (index+1), ArrowUp = previous; Enter picks the highlighted card.
  $effect(() => { if (hl >= deepResults.length) hl = -1 })
  function moveHl(dir) {
    const n = deepResults.length
    if (!n) return false
    hl = hl < 0 ? (dir > 0 ? 0 : n - 1) : Math.max(0, Math.min(n - 1, hl + dir))
    queueMicrotask(() => document.querySelector('.deep-results .deep-card.hl')?.scrollIntoView({ block: 'nearest' }))
    return true
  }
  // Typing in the field: blended results (mixed) unless the user narrowed with a tab. Also
  // remember the query once it settles (800ms idle) so recall holds real searches, not every
  // keystroke — complements remembering on a pick (afterAdd).
  let rememberTimer = null
  function onDeepInput() {
    histPos = null // typing leaves history-recall mode
    if (rememberTimer) clearTimeout(rememberTimer)
    rememberTimer = setTimeout(() => onRemember(deepQuery), 800)
    runSearch()
  }
  // Recall a past search into the box AND run it, so the results show immediately (spec 028).
  // histPos stays set so the arrows keep cycling history; typing or a pick exits recall mode.
  function stepHistory(dir) {
    const step = historyStep(history, histPos, dir)
    if (!step) return false
    histPos = step.pos
    deepQuery = step.value
    if (step.value.trim()) runSearch() // fire the recalled search
    else { deepResults = []; deepLoading = false; deepSeq++ } // back to the empty draft
    return true
  }
  const rememberQuery = () => onRemember(deepQuery)
  // Tabs act as filters: click to narrow to that mode; click the active tab to clear
  // back to the blended (mixed) list.
  function setDeepMode(m) {
    const next = deepMode === m ? 'mixed' : m
    if (deepMode !== next) { deepMode = next; runSearch() }
  }
  const toggleDeepFilters = () => { deepFilterOpen = !deepFilterOpen }
  function setDeepType(t) {
    deepType = deepType === t ? null : t
    deepFilterOpen = false
    runSearch()
  }

  // Clear the search back to idle (query, results, remote state). Exported so the pane's
  // owner can also clear after a DEFERRED add completes — View mode's "switch to editing?"
  // confirm logs the tune from App, outside this component.
  export function reset() {
    if (deepTimer) { clearTimeout(deepTimer); deepTimer = null }
    deepSeq++
    deepQuery = ''
    deepResults = []
    deepLoading = false
    resetThesession()
  }
  // After an add from the persistent pane, reset for the next tune (the composer clears the
  // same way). The modal instead unmounts — its caller closes it in onAdd. Skipped when the
  // caller returns false (the add was deferred, e.g. the View-mode confirm), so a cancelled
  // confirm doesn't eat the search.
  function afterAdd(added) {
    rememberQuery() // a query that led to a log is worth recalling later (spec 028)
    histPos = null
    if (added === false || variant !== 'pane') return
    reset()
  }
  // Tap a result → log that catalog tune at the cursor.
  function pickDeep(r) {
    afterAdd(onAdd({ tune_id: r.tune_id, name: r.name, tune_type: r.tune_type }, r.name))
  }
  // Log the typed text as an unlinked tune (the "as-is" escape lives here).
  function deepLogAsIs() {
    const name = deepQuery.trim()
    if (!name) return
    afterAdd(onAdd({ name }, name))
  }
  // Keyboard: with results showing, arrows walk the cards; with none (empty box), ArrowUp
  // recalls past searches (then keeps cycling until you type or commit). Esc closes the modal
  // (pane defers to App's global blur). Enter commits a recalled query to a real search, else
  // logs the highlighted/top card, else as-is (like type-ahead).
  function deepKey(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const dir = e.key === 'ArrowDown' ? 1 : -1
      // ArrowUp on an empty box recalls past searches (even though an empty query browses
      // popular tunes); with a typed query, or ArrowDown, the arrows walk the result cards.
      if (histPos != null) { if (stepHistory(dir)) e.preventDefault() } // cycling history
      else if (dir < 0 && !deepQuery.trim()) { if (stepHistory(-1)) e.preventDefault() } // empty box: recall
      else if (deepResults.length) { if (moveHl(dir)) e.preventDefault() } // result nav
    } else if (e.key === 'Escape') {
      if (variant === 'modal') { e.preventDefault(); onClose() }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (hl >= 0 && deepResults[hl]) pickDeep(deepResults[hl])
      else if (deepResults.length) pickDeep(deepResults[0])
      // Don't log a RECALLED query as-is while its search is still loading — only a query the
      // user actually typed (histPos == null) falls through to the as-is escape.
      else if (histPos == null && deepQuery.trim()) deepLogAsIs()
    }
  }

  // --- thesession.org remote search & import (spec 026) -----------------------------
  function resetThesession() {
    tsResults = []; tsSearching = false; tsSearched = false; tsPasteUrl = ''; tsPasteError = ''
  }
  // Extend the search to thesession.org for the CURRENT query (explicit action only). Remote
  // hits already shown in the local list are suppressed (they stay up top).
  async function runThesessionSearch() {
    const q = deepQuery.trim()
    if (!q || tsSearching || displayStatus === 'offline') return
    tsSearching = true; tsSearched = true
    const localIds = new Set(deepResults.map((r) => r.tune_id))
    const r = await thesessionSearch(config, q, deepType)
    tsResults = r.filter((t) => !localIds.has(t.tune_id))
    tsSearching = false
  }
  // Tap a remote result -> import (server-side, folded into the add op) + log linked at cursor.
  // We know the title/type from the search, so the optimistic row shows linked immediately.
  function pickRemote(r) {
    afterAdd(onAdd({ thesession_id: r.tune_id, tune_id: r.tune_id, name: r.name, tune_type: r.tune_type }, r.name))
  }
  // "Paste a thesession.org URL or tune ID" -> same import-and-log path (title unknown yet).
  function pasteThesession() {
    const id = parseThesessionId(tsPasteUrl)
    if (id == null) { tsPasteError = 'Enter a thesession.org tune URL or numeric ID.'; return }
    afterAdd(onAdd({ thesession_id: id, name: `#${id}` }, `#${id}`))
  }

  // Initial search: the modal always ran one on open (an empty query browses by
  // popularity/type); the pane stays idle until the user types.
  if (untrack(() => variant === 'modal' || initialQuery.trim())) runSearch()

  onDestroy(() => {
    if (deepTimer) clearTimeout(deepTimer)
    if (rememberTimer) clearTimeout(rememberTimer)
    deepSeq++ // discard an in-flight search settling after unmount
  })
</script>

{#if variant === 'modal'}
  <div class="deep-head">
    <span class="deep-title">Find a tune</span>
    <button class="deep-done" onclick={onClose}>Done</button>
  </div>
{/if}
<input
  class="deep-field"
  role="combobox"
  aria-expanded={deepResults.length > 0}
  aria-controls="deep-results-list"
  aria-activedescendant={hl >= 0 ? `dres-${hl}` : undefined}
  placeholder={deepMode === 'abc' ? 'Search by notes, e.g. GED or EBBA…' : deepMode === 'name' ? 'Search by name…' : 'Search by name or notes…'}
  bind:value={deepQuery}
  oninput={onDeepInput}
  onkeydown={deepKey}
  use:autofocusIf={variant === 'modal'}
/>
<div class="deep-tabs">
  <button class="deep-tab" class:active={deepMode === 'name'} onclick={() => setDeepMode('name')}>By name</button>
  <button class="deep-tab" class:active={deepMode === 'abc'} onclick={() => setDeepMode('abc')}>By ABC</button>
  <button class="deep-tab deep-filter-tab" class:active={deepType || deepFilterOpen} title="Filter by type" aria-label="Filter by type" onclick={toggleDeepFilters}>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>
      <line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>
      <line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>
      <line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>
    </svg>
  </button>
</div>
{#if deepFilterOpen}
  <div class="deep-filters">
    {#each DEEP_TYPES as t}
      <button class="deep-type-chip" class:active={deepType === t} onclick={() => setDeepType(t)}>{pluralType(t)}</button>
    {/each}
  </div>
{:else if deepType}
  <div class="deep-filters">
    <button class="filter-pill" onclick={() => setDeepType(deepType)}>{pluralType(deepType)} <span class="x">✕</span></button>
  </div>
{/if}
<!-- Extend the search to thesession.org (spec 026): explicit tap, online-only. Styled
     like "Log as-is" but blue; sits directly above it. -->
{#if deepQuery.trim() && displayStatus !== 'offline' && !tsSearched}
  <button class="deep-asis deep-asis-remote" onclick={runThesessionSearch}>🔎 Search on thesession.org for “{deepQuery.trim()}”</button>
{/if}
{#if deepMode !== 'abc' && deepQuery.trim()}
  <button class="deep-asis" onclick={deepLogAsIs}>＋ Log “{deepQuery.trim()}” as-is (unlinked)</button>
{/if}
<div class="deep-results" id="deep-results-list" role="listbox">
  {#if deepLoading && !deepResults.length}
    <p class="deep-empty">Searching…</p>
  {:else if !deepResults.length}
    {#if variant === 'pane' && !deepQuery.trim()}
      <p class="deep-empty">Search the tune catalog by name or ABC notes.</p>
    {:else}
      <p class="deep-empty">No{deepType ? ` ${deepType.toLowerCase()}` : ''} tunes match{deepQuery.trim() ? ` “${deepQuery.trim()}”` : ''}.</p>
    {/if}
  {:else}
    {#each deepResults as r, di (r.tune_id)}
      <button id="dres-{di}" class="deep-card" class:hl={hl === di} onclick={() => pickDeep(r)}>
        <div class="deep-card-head">
          <span class="deep-name">{r.name}</span>
          <span class="deep-type">{r.tune_type || ''}</span>
        </div>
        <div class="deep-staff">
          <Incipit {config} tuneId={r.tune_id} image={r.incipit_image} canRender={r.can_render} />
        </div>
        <div class="deep-meta">
          {#if r.abc_only}<span class="deep-badge">♪ notation</span>{/if}
          {#if r.on_list}<span class="deep-badge star">★ on your list</span>{/if}
          {#if r.in_session}<span class="deep-badge">in this session</span>{/if}
          {#if r.played_here}<span class="deep-badge">played here {r.played_here}×</span>{/if}
          <span class="deep-books">{r.tunebook_count ?? 0} tunebooks</span>
        </div>
      </button>
    {/each}
  {/if}
</div>

<!-- Remote results appear below the local ones once the search has been extended. -->
{#if tsSearched}
  <div class="deep-remote">
    <div class="deep-remote-head">From thesession.org</div>
    {#if tsSearching}
      <p class="deep-empty">Searching thesession.org…</p>
    {:else if !tsResults.length}
      <p class="deep-empty">No new tunes on thesession.org for “{deepQuery.trim()}”.</p>
    {:else}
      {#each tsResults as r (r.tune_id)}
        <button class="deep-card deep-remote-card" onclick={() => pickRemote(r)}>
          <div class="deep-card-head">
            <span class="deep-name">{r.name}</span>
            <span class="deep-type">{r.tune_type || ''}</span>
          </div>
          <div class="deep-meta">
            {#if r.alias}<span class="deep-alias">“{r.alias}”</span>{/if}
            {#if r.is_local}<span class="deep-badge">already in library</span>{/if}
            {#if r.in_session}<span class="deep-badge star">★ in this session</span>{/if}
          </div>
        </button>
      {/each}
    {/if}
    <!-- Direct link entry, revealed once you've extended to thesession.org. -->
    <div class="deep-paste">
      <input class="deep-paste-field" placeholder="Have a link? Paste a thesession.org URL or tune ID"
             bind:value={tsPasteUrl}
             oninput={() => (tsPasteError = '')}
             onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); pasteThesession() } }} />
      <button class="deep-paste-btn" disabled={!tsPasteUrl.trim()} onclick={pasteThesession}>Add</button>
    </div>
    {#if tsPasteError}<p class="deep-paste-error">{tsPasteError}</p>{/if}
  </div>
{/if}
