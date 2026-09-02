<script>
  // The app-wide "Find a tune" sheet (hamburger menu), ported from the vanilla
  // implementation that lived in static/js/hamburger_menu.js (spec 035 Step 3c);
  // the bespoke overlay chrome (.ft-scrim/.ft-panel/.ft-head/.ft-close) became
  // the kit Sheet in the Sheet-unification round. The BODY keeps the .ft-*
  // contract (.ft-input / .ft-results .ft-item — styled by hamburger_menu.css,
  // e2e-selected by offline.spec.ts) and the same behavior: 200ms debounce,
  // min 2 chars, server search with offline-bundle fallback, stale-response
  // guard, click a result -> the shared tune-detail sheet.
  import { SearchField, Sheet } from '../lib/index.js'
  import { parseThesessionId, parseThesessionSettingId } from '../shared/parse.js'

  let open = $state(false)
  let query = $state('')
  let results = $state(null) // null = nothing to show; [] = "No tunes match"
  let searchField = $state(null)
  // A pasted thesession.org URL / tune id resolves to that one tune (the server does the
  // lookup, following merge redirects). When the catalog doesn't have it yet, the empty
  // state hands off to the My Tunes add pane, which CAN import it — carrying the raw
  // link so its ?setting=/#setting deep link survives as the person's setting.
  let linkRef = $state(null) // {id, settingId, raw} while the box holds a tune link
  const importHref = $derived(
    linkRef ? `/my-tunes?add=1&q=${encodeURIComponent(linkRef.raw)}` : '/my-tunes?add=1'
  )
  const loggedIn = typeof window !== 'undefined' && !!window.CEOL_AUTHED

  let seq = 0

  export function show() {
    query = ''
    results = null
    linkRef = null
    open = true
    setTimeout(() => searchField && searchField.focus(), 50)
  }

  function close() {
    open = false
    seq++ // invalidate any in-flight search
  }

  async function offlineSearch(q) {
    // Offline fallback: search the locally-cached bundle (your tunes + popular).
    if (window.CeolOffline) {
      try {
        return await window.CeolOffline.searchTunes(q, 10)
      } catch (e) {
        /* fall through */
      }
    }
    return null
  }

  // The kit SearchField owns the debounce (200ms) + Enter flush + Escape-clears;
  // this handler owns the min-2-chars rule, the stale-response guard, and the
  // server-with-offline-fallback search.
  //
  // Notation search needs no branch here: /api/tunes/search blends notation matches in
  // itself for note-shaped queries, and flags the ones that matched the notation rather
  // than the name as `abc_only` so the row can carry a musical note. Offline the bundle
  // answers the same shape, but only over incipits (`abc_scope: 'incipit'`).
  async function runSearch(raw) {
    const q = (raw || '').trim()
    const refId = parseThesessionId(q)
    linkRef = refId == null ? null : { id: refId, settingId: parseThesessionSettingId(q), raw: q }
    if (refId == null && q.length < 2) {
      results = null
      return
    }
    const mine = ++seq
    const render = (tunes) => {
      if (mine !== seq) return
      results = tunes || []
    }
    try {
      const res = await fetch('/api/tunes/search?q=' + encodeURIComponent(q) + '&limit=10', {
        credentials: 'same-origin',
      })
      const json = await res.json()
      if (mine !== seq) return
      if (json && json.success && (json.tunes || []).length) {
        render(json.tunes)
        return
      }
      // A link that found nothing is "not in the catalog yet", not "no name matches" —
      // the offline bundle (a name index) can't answer it either, so don't ask.
      if (refId != null) {
        render([])
        return
      }
      const off = await offlineSearch(q)
      render(off !== null ? off : json.tunes || [])
    } catch (e) {
      const off = await offlineSearch(q)
      if (off !== null) render(off)
    }
  }

  function pick(tune) {
    // A link that named a SETTING is a statement about which version you play, and the
    // drawer can't take one — it would be dropped on the floor here (the setting only
    // survived the "not in the library yet" branch below). Hand the raw link to the My
    // Tunes add pane, which lands the pager on that setting and, for a tune already on
    // your list, offers to update your setting.
    if (linkRef && linkRef.settingId != null && loggedIn) {
      close()
      window.location.href = importHref
      return
    }
    close()
    // The drawer derives everything from its payload (viewer flags, on-list
    // state) and defaults its scope from the URL — so a pick on a session page
    // opens session-scoped, and everywhere else opens the global view.
    window.TuneDetailModal.show({
      tuneId: tune.tune_id,
      tuneName: tune.name,
    })
  }

</script>

<!-- Escape/scrim dismissal is the Sheet's; closing (any path) invalidates
     in-flight searches through onCancel. -->
<Sheet bind:open title="Find a tune" onCancel={() => seq++}>
  <SearchField
    bind:this={searchField}
    bind:value={query}
    inputClass="ft-input"
    wrapperClass="ft-search-wrap"
    styled={false}
    placeholder="Search by name or notes, or paste a link…"
    autocomplete="off"
    autocorrect="off"
    autocapitalize="off"
    spellcheck="false"
    debounce={200}
    onSearch={runSearch} />
  {#if linkRef && results === null}
    <p class="ft-note">Looking up tune #{linkRef.id} from thesession.org…</p>
  {:else if linkRef && linkRef.settingId != null && loggedIn && results && results.length}
    <!-- Say where the tap goes: this sheet can't hold on to a setting, My Tunes can. -->
    <p class="ft-note">That link names setting #{linkRef.settingId} — opening it in My Tunes, where it can be saved.</p>
  {/if}
  <ul class="ft-results">
    {#if results !== null}
      {#if results.length}
        {#each results as tune (tune.tune_id)}
          <li
            class="ft-item"
            data-tune-id={tune.tune_id}
            onclick={() => pick(tune)}
            onkeydown={(e) => e.key === 'Enter' && pick(tune)}
            role="option"
            aria-selected="false"
            tabindex="0">{tune.name}{#if tune.abc_only}<span class="ft-abc" title={tune.abc_scope === 'incipit' ? 'Matched the opening bars (offline)' : 'Matched the notation, not the name'}>♪</span>{/if}<span class="ft-type">{tune.tune_type || ''}</span></li>
        {/each}
      {:else if linkRef}
        <!-- The link resolved, the catalog just doesn't have that tune yet. Importing is
             an add, so it happens where adds happen: the My Tunes add pane, seeded with
             the same link (setting deep link included). -->
        <li class="ft-empty">
          Tune #{linkRef.id} isn't in the library yet.
          {#if loggedIn}
            <a class="ft-import" href={importHref}>Add it from thesession.org</a>
          {:else}
            <a class="ft-import" href="https://thesession.org/tunes/{linkRef.id}" target="_blank" rel="noopener">View it on thesession.org</a>
          {/if}
        </li>
      {:else}
        <li class="ft-empty">No tunes match</li>
      {/if}
    {/if}
  </ul>
</Sheet>
