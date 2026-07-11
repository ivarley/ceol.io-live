<script>
  // The app-wide "Find a tune" overlay (hamburger menu), ported from the vanilla
  // implementation that lived in static/js/hamburger_menu.js (spec 035 Step 3c).
  // Same DOM contract — #find-tune-overlay, .ft-* classes (styled by
  // hamburger_menu.css, e2e-selected by offline.spec.ts) — and same behavior:
  // 200ms debounce, min 2 chars, server search with offline-bundle fallback,
  // stale-response guard, click a result -> the shared tune-detail sheet.
  let open = $state(false)
  let query = $state('')
  let results = $state(null) // null = nothing to show; [] = "No tunes match"
  let inputEl = $state(null)

  let timer = null
  let seq = 0

  export function show() {
    query = ''
    results = null
    open = true
    setTimeout(() => inputEl && inputEl.focus(), 50)
  }

  function close() {
    open = false
    if (timer) clearTimeout(timer)
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

  function onInput() {
    const q = query.trim()
    if (timer) clearTimeout(timer)
    if (q.length < 2) {
      results = null
      return
    }
    timer = setTimeout(async () => {
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
    }, 200)
  }

  function pick(tune) {
    close()
    // 'session_instance' context renders the session_tune shape the session-agnostic
    // /api/tunes/<id>/detail returns (no sessionPath/dateOrId — a global read view).
    window.TuneDetailModal.show({
      context: 'session_instance',
      tuneId: tune.tune_id,
      apiEndpoint: '/api/tunes/' + tune.tune_id + '/detail',
      additionalData: { isUserLoggedIn: true, tuneName: tune.name, global: true },
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
      <input
        bind:this={inputEl}
        bind:value={query}
        oninput={onInput}
        class="ft-input"
        type="text"
        placeholder="Search tunes…"
        autocomplete="off"
        autocorrect="off"
        autocapitalize="off"
        spellcheck="false" />
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
