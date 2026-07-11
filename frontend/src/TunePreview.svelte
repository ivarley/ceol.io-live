<script>
  import { Chip } from './lib/index.js'
  import { untrack } from 'svelte'
  import { fly } from 'svelte/transition'
  import { tunePreview, thesessionPreview, settingImage, renderRemoteAbc } from './client.js'

  // The deep-search preview: tapping a result card lands here for a proper look
  // (notation, aliases, ABC, stats) BEFORE committing the add — the card's ＋ rail
  // keeps the old one-tap path. Occupies the same real estate as the search in
  // every host (TuneSearch swaps its content for this component). The ‹ › steppers
  // page through the whole result list (local, then remote) so candidates can be
  // compared without bouncing back to the list each time.
  //
  // Notation block mirrors the tune-detail modal's anatomy: content on top;
  // notes/abc mode tabs on the left below it, a thesession link on the right;
  // clicking the image or the ABC flips incipit ⇄ full. Pending renders live in
  // client.js's module-level registry, so a spinner survives stepping away and back.
  let {
    config,
    items, // combined nav list: [{r: <search result>, remote: bool}]
    index = 0, // start position
    initialSettingId = null, // a pasted URL's ?setting=/#setting deep link — land the pager there (counts as CHOSEN)
    actionLabel = '＋ Log This Tune',
    onAction, // (item, previewData) -> onAdd's return (false = deferred, stay open)
    onClose,
  } = $props()

  let idx = $state(untrack(() => index)) // seed once; stepping is internal
  let mode = $state('notes') // 'notes' | 'abc'
  let size = $state('incipit') // 'incipit' | 'full' (flips on content click)
  let setIdx = $state(0) // which setting the pager is on
  let pagerTouched = false // did the user WORK the settings pager? (gates "chosen setting")
  // A URL-requested setting jumps the pager when (or as soon as) it appears — including
  // after the backfill lands, since the deep-linked setting may not be imported yet.
  let pendingSetting = untrack(() => initialSettingId)
  let data = $state(null) // tune-preview / thesession-preview response
  let loading = $state(true)
  let failed = $state(false)
  let image = $state(null)
  let imgPending = $state(false)
  let backfilling = $state(false) // thesession settings backfill in flight (the › slot hints it)
  let aliasesExpanded = $state(false) // "Also known as" is clamped to 3 lines until expanded
  let aliasesClamped = $state(false) // does the collapsed block actually overflow?
  let aliasesEl = $state(null)
  let loadSeq = 0
  let imgSeq = 0

  // Show "More …" only when the clamped alias block truly overflows its 3 lines —
  // re-measured whenever the aliases change (the backfill can grow them).
  $effect(() => {
    void data?.aliases
    if (!aliasesEl || aliasesExpanded) return
    aliasesClamped = aliasesEl.scrollHeight > aliasesEl.clientHeight + 1
  })

  const item = $derived(items[idx])
  const settings = $derived(data?.settings || [])
  const setting = $derived(settings[setIdx] || null)
  // remote = shown from thesession.org and NOT in our library (an import-on-add);
  // a remote id that resolved to a local tune loads the local preview instead.
  const isRemote = $derived(data ? data.is_local === false : !!item?.remote && !item?.r?.is_local)
  // The thesession link deep-links the SETTING currently showing (same URL shape the
  // rest of the app builds: ?setting=NNN#settingNNN).
  const tsUrl = $derived.by(() => {
    const base = `https://thesession.org/tunes/${data?.tune_id ?? item?.r?.tune_id ?? ''}`
    const sid = setting?.setting_id
    return sid != null ? `${base}?setting=${sid}#setting${sid}` : base
  })

  function show(i) {
    idx = i
    mode = 'notes'
    size = 'incipit'
    setIdx = 0
    pagerTouched = false
    aliasesExpanded = false
    aliasesClamped = false
    data = null
    failed = false
    loading = true
    image = null
    imgPending = false
    const it = items[i]
    const seq = ++loadSeq
    const p = it.remote && !it.r.is_local
      ? thesessionPreview(config, it.r.tune_id).then((d) => (d.is_local ? tunePreview(config, d.tune_id) : d))
      : tunePreview(config, it.r.tune_id)
    p.then((d) => {
      if (seq !== loadSeq) return
      data = d
      // A pasted URL's setting wins (and COUNTS as chosen — the user pointed at it);
      // otherwise the pager OPENS on the session's preferred setting — the notation
      // you see first is the one this session plays. Landing there isn't a "choice"
      // (pagerTouched stays false), so logging changes nothing.
      let si = -1
      if (pendingSetting != null) {
        si = (d.settings || []).findIndex((s) => s.setting_id === pendingSetting)
        if (si >= 0) { pagerTouched = true; pendingSetting = null }
        // not found yet: keep pendingSetting — the backfill may bring it
      }
      if (si < 0 && d.session_setting_id != null) {
        si = (d.settings || []).findIndex((s) => s.setting_id === d.session_setting_id)
      }
      if (si > 0) setIdx = si
      loading = false
      loadImage()
      if (d.is_local !== false) backfillSettings(d, seq)
    }).catch(() => {
      if (seq !== loadSeq) return
      failed = true
      loading = false
    })
  }

  // The local catalog usually holds only the setting(s) an import brought over;
  // thesession.org has them all. Backfill the rest in the BACKGROUND — the local
  // setting shows instantly and the pager grows when the full list lands (the
  // response is cached per id, so stepping away and back is instant). Offline or
  // thesession down: the local settings simply stand.
  async function backfillSettings(d, seq) {
    backfilling = true
    let ts
    try {
      ts = await thesessionPreview(config, d.tune_id, true)
    } catch {
      if (seq === loadSeq) backfilling = false
      return
    }
    if (seq !== loadSeq) return // another tune took over; its own backfill owns the flag
    backfilling = false
    if (!ts?.settings?.length) return
    const have = new Set((d.settings || []).map((s) => s.setting_id))
    const extra = ts.settings.filter((s) => !have.has(s.setting_id)).map((s) => ({ ...s, remote: true }))
    const aliases = [...(d.aliases || [])]
    for (const a of ts.aliases || []) if (!aliases.includes(a)) aliases.push(a)
    if (!extra.length && aliases.length === (d.aliases || []).length) return
    const hadNone = !(d.settings || []).length
    data = { ...d, settings: [...(d.settings || []), ...extra], aliases }
    // The URL-requested setting arrived with the backfill: jump there now (unless the
    // user already started paging themselves).
    if (pendingSetting != null && !pagerTouched) {
      const si = data.settings.findIndex((s) => s.setting_id === pendingSetting)
      pendingSetting = null // one shot — found or not
      if (si >= 0) {
        setIdx = si
        pagerTouched = true
        size = 'incipit'
        if (mode === 'notes') loadImage()
        return
      }
    }
    pendingSetting = null
    if (hadNone && extra.length && mode === 'notes') loadImage() // was "no notation"; now renderable
  }

  // Fetch the notation image for the current tune/setting/size. Cached incipits
  // arrive inline with the preview; everything else goes through the shared
  // render-on-demand registry (server renders + caches per setting; remote ABC
  // renders ephemerally).
  function loadImage() {
    const d = data
    const s = d?.settings?.[setIdx]
    if (!d || !s || mode !== 'notes') return
    if (size === 'incipit' && s.incipit_image) {
      image = s.incipit_image
      imgPending = false
      return
    }
    const seq = ++imgSeq
    image = null
    imgPending = true
    // A backfilled setting (s.remote) has no tune_setting row even though the TUNE is
    // local — it renders ephemerally, same as a fully remote tune's settings.
    const p = s.remote || d.is_local === false
      ? renderRemoteAbc(config, `ts:${d.tune_id}:${s.setting_id ?? setIdx}:${size}`,
          { abc: s.abc, key: s.key, tune_type: d.tune_type, kind: size })
      : settingImage(config, s.setting_id, size)
    p.then((img) => {
      if (seq !== imgSeq) return
      image = img
      imgPending = false
    })
  }

  function setMode(m) {
    if (mode === m) return
    mode = m
    if (m === 'notes') loadImage()
  }
  function flipSize() {
    size = size === 'incipit' ? 'full' : 'incipit'
    if (mode === 'notes') loadImage()
  }
  function stepSetting(d) {
    const n = setIdx + d
    if (!settings.length || n < 0 || n >= settings.length) return
    setIdx = n
    pagerTouched = true
    size = 'incipit'
    if (mode === 'notes') loadImage()
  }
  function stepResult(d) {
    const n = idx + d
    if (n < 0 || n >= items.length) return
    pendingSetting = null // a URL's setting deep-link only applies to the tune it named
    show(n)
  }

  function doAction() {
    // A setting counts as CHOSEN only if the user worked the pager on this tune —
    // merely opening the preview (which lands on setting 1) expresses no preference.
    const chosen = pagerTouched && setting?.setting_id != null ? setting.setting_id : null
    onAction(items[idx], data, chosen)
  }

  // Keys: ← → compare candidates, Enter confirms, Esc backs out to the results.
  // Focused controls keep their own Enter (their click already handles it).
  function onKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      onClose()
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      stepResult(-1)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      stepResult(1)
    } else if (e.key === 'Enter') {
      if (e.target.closest('button, a, input, textarea, select')) return
      e.preventDefault()
      doAction()
    }
  }

  show(untrack(() => idx))
</script>

<svelte:window onkeydown={onKey} />

<!-- in: only (no exit animation): a jump from one preview straight to another
     (pane 🔍 → paste) must swap instantly, not stack two flying previews -->
<div class="pv" in:fly={{ x: 32, duration: 180 }}>
  <div class="pv-head">
    <button class="pv-back" onclick={onClose}>‹ Results</button>
    <span class="pv-count">{idx + 1} of {items.length}</span>
    <button class="pv-step" disabled={idx === 0} aria-label="Previous result" onclick={() => stepResult(-1)}>‹</button>
    <button class="pv-step" disabled={idx >= items.length - 1} aria-label="Next result" onclick={() => stepResult(1)}>›</button>
  </div>

  <div class="pv-body">
    <div class="pv-name">{data?.name ?? item?.r?.name ?? ''}<span class="pv-type">{data?.tune_type ?? item?.r?.tune_type ?? ''}</span></div>

    {#if loading}
      <div class="pv-skel" style="width:60%"></div>
      <div class="pv-skel" style="height:96px"></div>
      <div class="pv-skel" style="width:40%"></div>
    {:else if failed}
      <p class="pv-fail">Couldn’t load tune details{item?.remote ? ' from thesession.org' : ''}. Check your connection and try again.</p>
    {:else}
      <!-- The two facts that decide "is this the right tune?": our history with it
           (gold — session identity) and how common it is (accent). "in this session"
           was redundant with the play count, so it's gone. -->
      <div class="pv-facts">
        {#if data.played_here}
          <span class="pv-fact-here">♪ Played here {data.played_here}×{data.dates?.length ? ` — last: ${data.dates.join(', ')}` : ''}</span>
        {:else}
          <span class="pv-fact-none">Not played here yet</span>
        {/if}
        <span class="pv-fact-pop"><b>{data.tunebook_count ?? 0}</b> tunebooks</span>
        {#if item?.r?.on_list}<Chip label="★ on your list" styled={false} chipClass="deep-badge star" />{/if}
      </div>

      <!-- The alias region is ALWAYS a fixed two-line box while collapsed — reserved
           even before/without aliases — so the backfill filling it in never shifts the
           pager/notation below. Only "More …" (an explicit act) may move the layout. -->
      <div class="pv-aliaswrap" class:fixed={!aliasesExpanded}>
        {#if data.aliases?.length}
          <div class="pv-aliases" class:clamped={!aliasesExpanded} bind:this={aliasesEl}>Also known as: {data.aliases.join(', ')}</div>
          {#if aliasesClamped && !aliasesExpanded}
            <button class="pv-more" onclick={() => (aliasesExpanded = true)}>More …</button>
          {/if}
        {/if}
      </div>

      {#if settings.length}
        <!-- ABOVE the notation, so paging settings never shifts this bar around
             (the notation below is the only thing that changes height) -->
        <div class="pv-setnav">
          <button class="pv-step" disabled={setIdx === 0} aria-label="Previous setting" onclick={() => stepSetting(-1)}>‹</button>
          <span class="pv-setlabel">Setting {setIdx + 1} of {settings.length}{setting?.setting_id != null ? ` · #${setting.setting_id}` : ''}{setting?.key ? ` · ${setting.key}` : ''}{#if setting?.setting_id != null && setting.setting_id === data.session_setting_id}<span class="pv-sesset"> · ★ this session’s</span>{/if}</span>
          <button class="pv-step" disabled={setIdx >= settings.length - 1} aria-label="Next setting" onclick={() => stepSetting(1)}>
            {#if backfilling && setIdx >= settings.length - 1}
              <!-- more settings may be on their way from thesession.org — the arrow
                   (maybe) appears when the backfill lands -->
              <span class="pv-spin" aria-hidden="true"></span>
            {:else}›{/if}
          </button>
        </div>
      {/if}

      <div class="nb">
        {#if mode === 'abc'}
          {#if setting}
            <button class="nb-abc" title="Click to show {size === 'full' ? 'the incipit' : 'the full tune'}" onclick={flipSize}>{size === 'full' ? setting.abc : setting.incipit_abc}</button>
          {:else}
            <div class="nb-pend"><span class="deep-noabc">♪ no notation</span></div>
          {/if}
        {:else if image}
          <button class="nb-imgbtn" title="Click to show {size === 'full' ? 'the incipit' : 'the full tune'}" onclick={flipSize}>
            <img src={`data:image/png;base64,${image}`} alt="notation ({size})" />
          </button>
        {:else if imgPending}
          <!-- still clickable mid-render: flip back to the cached incipit (or on to full)
               without waiting; the abandoned render finishes + caches in the background -->
          <button class="nb-pend" title="Click to show {size === 'full' ? 'the incipit' : 'the full tune'}" onclick={flipSize}><span class="spinner"></span> rendering notation…</button>
        {:else if setting}
          <button class="nb-pend" title="Click to show {size === 'full' ? 'the incipit' : 'the full tune'}" onclick={flipSize}><span class="deep-noabc">♪ no notation image</span></button>
        {:else}
          <div class="nb-pend"><span class="deep-noabc">♪ no notation</span></div>
        {/if}
        <div class="nb-foot">
          <button class="nb-tab" class:active={mode === 'notes'} onclick={() => setMode('notes')}>notes</button>
          <button class="nb-tab" class:active={mode === 'abc'} disabled={!setting} onclick={() => setMode('abc')}>abc</button>
          <a class="nb-ext" href={tsUrl} target="_blank" rel="noopener">thesession</a>
        </div>
      </div>

      {#if isRemote}
        <div class="pv-import-note">Not in the library yet — it will be imported from thesession.org when you add it.</div>
      {/if}
    {/if}
  </div>

  <div class="pv-foot">
    <button class="pv-action" onclick={doAction}>{actionLabel}</button>
  </div>
</div>
