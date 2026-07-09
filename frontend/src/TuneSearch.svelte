<script>
  import { onDestroy, untrack, tick } from 'svelte'
  import { deepSearch, thesessionSearch } from './client.js'
  import Incipit from './Incipit.svelte'
  import TunePreview from './TunePreview.svelte'
  import { pluralType, parseThesessionId, historyStep } from './logstate.js'

  // The deep-search body (spec 028): one shared component behind BOTH the mobile
  // full-screen modal and the desktop side pane, so local catalog search, the
  // thesession.org remote extension (spec 026), and paste-URL import never fork.
  // Owns all search state; every terminal action collapses to onAdd(payload, name)
  // — the caller decides what "add" means (close the modal, clear, log at cursor).
  let {
    config,
    initialQuery = '', // seed: the composer text (modal) or '' (pane)
    initialPreview = null, // {items, index}: open JUMPED into a preview (the composer's 🔍) — Back lands on the search
    preferType = null, // the cursor set's type — a soft ranking preference, not a filter
    displayStatus = 'live', // gates the remote search (online-only)
    variant = 'pane', // 'modal' shows the Done header + autofocuses the field
    title = 'Find a tune', // modal header text (the add pane says "Search for a tune")
    allowAsIs = true, // "log as-is (unlinked)" escape — off for My Tunes (needs a catalog tune)
    actionLabel = '＋ Log This Tune', // the preview's primary action (context-specific verb)
    dimOnList = false, // dim results already on the person's list (My Tunes add pane)
    dimInSession = false, // dim results already in the session's repertoire (session-tunes add pane)
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

  // --- preview (look before you log): tapping a card opens TunePreview in this same
  // real estate; the card's ＋ rail (or ⌘Enter) keeps the old one-tap add.
  let previewIdx = $state(null) // index into previewItems, or null (search showing)
  let pastePreview = $state(null) // pseudo remote result for a pasted URL/id, previewed before adding
  // Mounted straight into a preview (the composer's 🔍 on a quick result): the items are
  // the QUICK results (so ‹ › page the other matches and the header reads "2 of 4");
  // closing it falls back to the normal search, seeded from the composer text as usual.
  let externalPreview = $state(untrack(() => initialPreview))
  let resultsEl = $state(null) // the .deep-results scroller (to restore scroll on back)
  let resultsScroll = 0
  // gates the modal's input re-autofocus after a preview round-trip (a jumped-open
  // preview counts — Back should reveal the results, not pop the keyboard)
  let everPreviewed = $state(!!untrack(() => initialPreview))
  // The preview's ‹ › steppers page this combined list: local results, then remote.
  const previewItems = $derived([
    ...deepResults.map((r) => ({ r, remote: false })),
    ...tsResults.map((r) => ({ r, remote: true })),
    ...(pastePreview ? [{ r: pastePreview, remote: true }] : []),
  ])
  function openPreview(i) {
    everPreviewed = true
    resultsScroll = resultsEl?.scrollTop ?? 0
    previewIdx = i
  }
  async function closePreview() {
    previewIdx = null
    pastePreview = null
    await tick() // the search DOM remounts before the scroll restore
    if (resultsEl) resultsEl.scrollTop = resultsScroll
  }
  // The preview's primary action: same payloads the card tap used to send, plus the
  // explicitly chosen setting when the user worked the pager (spec 032 — the server
  // imports it and applies it as the session's preferred setting, or to this row only
  // if the session already prefers another). A pasted or remote id that turned out
  // local (or merged) logs the canonical LOCAL tune, with the fetched title standing
  // in for the placeholder "#id".
  function previewAction(item, data, chosenSetting = null) {
    const name = data?.name ?? item.r.name
    const tune_type = data?.tune_type ?? item.r.tune_type
    const setting = chosenSetting != null ? { setting_id: chosenSetting } : {}
    if (item.remote) {
      // data present without is_local:false means the id resolved to a local tune
      // (tunePreview response); no data (load failed) stays on the remote payload —
      // the import op handles already-local ids server-side anyway.
      return data && data.is_local !== false
        ? pickDeep({ ...item.r, tune_id: data.tune_id ?? item.r.tune_id, name, tune_type, ...setting })
        : pickRemote({ ...item.r, name, tune_type, ...setting })
    }
    return pickDeep({ ...item.r, name, tune_type, ...setting })
  }

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
    previewIdx = null
    pastePreview = null
    externalPreview = null
    resetThesession()
  }
  // After an add from the persistent pane, reset for the next tune (the composer clears the
  // same way). The modal instead unmounts — its caller closes it in onAdd. Skipped when the
  // caller returns false (the add was deferred, e.g. the View-mode confirm), so a cancelled
  // confirm doesn't eat the search.
  function afterAdd(added) {
    rememberQuery() // a query that led to a log is worth recalling later (spec 028)
    histPos = null
    if (added === false) return added
    previewIdx = null
    pastePreview = null
    externalPreview = null
    if (variant === 'pane') reset()
    return added
  }
  // The one-tap add (＋ rail / ⌘Enter / preview confirm): log that catalog tune at
  // the cursor. The full result card rides along as a third arg for callers that
  // want the rich fields (incipit, on_list — the add pane); the live composer
  // ignores it. Returns onAdd's result so the preview knows a deferred add.
  function pickDeep(r) {
    const payload = { tune_id: r.tune_id, name: r.name, tune_type: r.tune_type }
    if (r.setting_id != null) payload.setting_id = r.setting_id // preview's chosen setting only
    return afterAdd(onAdd(payload, r.name, r))
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
  // opens the PREVIEW of the highlighted/top card (Enter again there confirms — the fast path
  // is Enter-Enter); ⌘/Ctrl+Enter adds it immediately, skipping the preview (the ＋ rail's
  // keyboard twin). With no results, Enter falls through to as-is (like type-ahead).
  function deepKey(e) {
    if (previewIdx != null || externalPreview) return // the preview owns the keys while it's open
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
      const target = hl >= 0 && deepResults[hl] ? hl : deepResults.length ? 0 : -1
      if (target >= 0) {
        if (e.metaKey || e.ctrlKey) pickDeep(deepResults[target])
        else openPreview(target)
      }
      // Don't log a RECALLED query as-is while its search is still loading — only a query the
      // user actually typed (histPos == null) falls through to the as-is escape.
      else if (allowAsIs && histPos == null && deepQuery.trim()) deepLogAsIs()
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
  // Add a remote result -> import (server-side, folded into the add op) + log linked at
  // cursor. We know the title/type from the search, so the optimistic row shows linked
  // immediately. Returns onAdd's result so the preview knows a deferred add.
  function pickRemote(r) {
    const payload = { thesession_id: r.tune_id, tune_id: r.tune_id, name: r.name, tune_type: r.tune_type }
    if (r.setting_id != null) payload.setting_id = r.setting_id // preview's chosen setting only
    return afterAdd(onAdd(payload, r.name, r))
  }
  // "Paste a thesession.org URL or tune ID" -> preview it first (you pasted an id blind —
  // the preview fetches the title/notation so you confirm it's the right tune before the
  // import). The preview's action then follows the normal import-and-add path.
  function pasteThesession() {
    const id = parseThesessionId(tsPasteUrl)
    if (id == null) { tsPasteError = 'Enter a thesession.org tune URL or numeric ID.'; return }
    pastePreview = { tune_id: id, name: `#${id}`, tune_type: null }
    openPreview(deepResults.length + tsResults.length)
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

{#if externalPreview}
  <!-- Jumped open from a composer quick result's 🔍 — Back reveals the search. -->
  <TunePreview
    {config}
    items={externalPreview.items}
    index={externalPreview.index}
    {actionLabel}
    onAction={previewAction}
    onClose={() => { externalPreview = null }}
  />
{:else if previewIdx != null && previewItems[previewIdx]}
  <!-- Look before you log: the preview takes over the search's real estate (modal
       screen or side pane alike); Back/Esc returns with the search state intact. -->
  <TunePreview
    {config}
    items={previewItems}
    index={previewIdx}
    {actionLabel}
    onAction={previewAction}
    onClose={closePreview}
  />
{:else}
{#if variant === 'modal'}
  <div class="deep-head">
    <span class="deep-title">{title}</span>
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
  use:autofocusIf={variant === 'modal' && !everPreviewed}
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
{#if allowAsIs && deepMode !== 'abc' && deepQuery.trim()}
  <button class="deep-asis" onclick={deepLogAsIs}>＋ Log “{deepQuery.trim()}” as-is (unlinked)</button>
{/if}
<div class="deep-results" id="deep-results-list" role="listbox" bind:this={resultsEl}>
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
      <!-- Two targets: the body opens the preview (look before you log); the ＋ rail
           adds in one tap for a tune you already recognize from the incipit. -->
      <div id="dres-{di}" class="deep-card deep-card-split" class:hl={hl === di} class:onlist={(dimOnList && r.on_list) || (dimInSession && r.in_session)} role="option" aria-selected={hl === di}>
        <button class="deep-card-body" aria-label={`Preview ${r.name}`} onclick={() => openPreview(di)}>
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
        <button class="deep-quick" title="Add without previewing" aria-label={`Add ${r.name} without previewing`} onclick={() => pickDeep(r)}>＋</button>
      </div>
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
      {#each tsResults as r, ri (r.tune_id)}
        <div class="deep-card deep-card-split deep-remote-card" class:onlist={(dimOnList && r.on_list) || (dimInSession && r.in_session)}>
          <button class="deep-card-body" aria-label={`Preview ${r.name}`} onclick={() => openPreview(deepResults.length + ri)}>
            <div class="deep-card-head">
              <span class="deep-name">{r.name}</span>
              <span class="deep-type">{r.tune_type || ''}</span>
            </div>
            <div class="deep-meta">
              {#if r.alias}<span class="deep-alias">“{r.alias}”</span>{/if}
              {#if r.is_local}<span class="deep-badge">already in library</span>{/if}
              {#if r.in_session}<span class="deep-badge star">★ in this session</span>{/if}
              {#if r.on_list}<span class="deep-badge star">★ on your list</span>{/if}
            </div>
          </button>
          <button class="deep-quick" title="Add without previewing" aria-label={`Add ${r.name} without previewing`} onclick={() => pickRemote(r)}>＋</button>
        </div>
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
{/if}
