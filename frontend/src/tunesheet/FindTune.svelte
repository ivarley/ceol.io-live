<script>
  // The app-wide "Find a tune" overlay (hamburger menu), ported from the vanilla
  // implementation that lived in static/js/hamburger_menu.js (spec 035 Step 3c).
  // Same DOM contract — #find-tune-overlay, .ft-* classes (styled by
  // hamburger_menu.css, e2e-selected by offline.spec.ts) — and same behavior:
  // 200ms debounce, min 2 chars, server search with offline-bundle fallback,
  // stale-response guard, click a result -> the shared tune-detail sheet.
  import { SearchField } from '../lib/index.js'

  let open = $state(false)
  let query = $state('')
  let results = $state(null) // null = nothing to show; [] = "No tunes match"
  let searchField = $state(null)

  let seq = 0

  export function show() {
    query = ''
    results = null
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
  async function runSearch(raw) {
    const q = (raw || '').trim()
    if (q.length < 2) {
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
      const off = await offlineSearch(q)
      render(off !== null ? off : json.tunes || [])
    } catch (e) {
      const off = await offlineSearch(q)
      if (off !== null) render(off)
    }
  }

  function pick(tune) {
    close()
    // 'session_instance' context renders the session_tune shape the session-agnostic
    // /api/tunes/<id>/detail returns (no sessionPath/dateOrId — a global read view).
    window.TuneDetailModal.show({
      context: 'session_instance',
      tuneId: tune.tune_id,
      apiEndpoint: '/api/tunes/' + tune.tune_id + '/detail',
      // CEOL_UID (base.html) is null for logged-out viewers: hide the add-to-list
      // control instead of showing an Add that would 401.
      additionalData: {
        isUserLoggedIn: typeof CEOL_UID !== 'undefined' && CEOL_UID != null,
        tuneName: tune.name,
        global: true,
      },
    })
  }

  $effect(() => {
    if (!open) return
    const esc = (e) => {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  })
</script>

{#if open}
  <div id="find-tune-overlay">
    <div class="ft-scrim" onclick={close} role="presentation"></div>
    <div class="ft-panel" role="dialog" aria-modal="true">
      <div class="ft-head">
        <span>Find a tune</span>
        <button class="ft-close" aria-label="Close" onclick={close}>✕</button>
      </div>
      <SearchField
        bind:this={searchField}
        bind:value={query}
        inputClass="ft-input"
        wrapperClass="ft-search-wrap"
        styled={false}
        placeholder="Search tunes…"
        autocomplete="off"
        autocorrect="off"
        autocapitalize="off"
        spellcheck="false"
        debounce={200}
        onSearch={runSearch} />
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
                tabindex="0">{tune.name}<span class="ft-type">{tune.tune_type || ''}</span></li>
            {/each}
          {:else}
            <li class="ft-empty">No tunes match</li>
          {/if}
        {/if}
      </ul>
    </div>
  </div>
{/if}
