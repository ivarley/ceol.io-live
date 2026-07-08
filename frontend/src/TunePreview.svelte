<script>
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
    actionLabel = '＋ Log This Tune',
    onAction, // (item, previewData) -> onAdd's return (false = deferred, stay open)
    onClose,
  } = $props()

  let idx = $state(untrack(() => index)) // seed once; stepping is internal
  let mode = $state('notes') // 'notes' | 'abc'
  let size = $state('incipit') // 'incipit' | 'full' (flips on content click)
  let setIdx = $state(0) // which setting the pager is on
  let data = $state(null) // tune-preview / thesession-preview response
  let loading = $state(true)
  let failed = $state(false)
  let image = $state(null)
  let imgPending = $state(false)
  let loadSeq = 0
  let imgSeq = 0

  const item = $derived(items[idx])
  const settings = $derived(data?.settings || [])
  const setting = $derived(settings[setIdx] || null)
  // remote = shown from thesession.org and NOT in our library (an import-on-add);
  // a remote id that resolved to a local tune loads the local preview instead.
  const isRemote = $derived(data ? data.is_local === false : !!item?.remote && !item?.r?.is_local)
  const tsUrl = $derived(`https://thesession.org/tunes/${data?.tune_id ?? item?.r?.tune_id ?? ''}`)

  function show(i) {
    idx = i
    mode = 'notes'
    size = 'incipit'
    setIdx = 0
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
      loading = false
      loadImage()
    }).catch(() => {
      if (seq !== loadSeq) return
      failed = true
      loading = false
    })
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
    const p = d.is_local === false
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
    size = 'incipit'
    if (mode === 'notes') loadImage()
  }
  function stepResult(d) {
    const n = idx + d
    if (n < 0 || n >= items.length) return
    show(n)
  }

  function doAction() {
    onAction(items[idx], data)
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

<div class="pv" transition:fly={{ x: 32, duration: 180 }}>
  <div class="pv-head">
    <button class="pv-back" onclick={onClose}>‹ Results</button>
    <span class="pv-count">{idx + 1} of {items.length}</span>
    <button class="pv-step" disabled={idx === 0} aria-label="Previous result" onclick={() => stepResult(-1)}>‹</button>
    <button class="pv-step" disabled={idx >= items.length - 1} aria-label="Next result" onclick={() => stepResult(1)}>›</button>
  </div>

  <div class="pv-body">
    <div class="pv-name">{data?.name ?? item?.r?.name ?? ''}</div>
    <div class="pv-sub">
      {#if item?.r?.on_list}<span class="deep-badge star">★ on your list</span>{/if}
      {#if item?.r?.in_session}<span class="deep-badge">in this session</span>{/if}
      <span class="deep-type">{data?.tune_type ?? item?.r?.tune_type ?? ''}</span>
    </div>

    {#if loading}
      <div class="pv-skel" style="width:60%"></div>
      <div class="pv-skel" style="height:96px"></div>
      <div class="pv-skel" style="width:40%"></div>
    {:else if failed}
      <p class="pv-fail">Couldn’t load tune details{item?.remote ? ' from thesession.org' : ''}. Check your connection and try again.</p>
    {:else}
      {#if data.aliases?.length}
        <div class="pv-aliases">Also known as: {data.aliases.join(', ')}</div>
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
          <div class="nb-pend"><span class="spinner"></span> rendering notation…</div>
        {:else}
          <div class="nb-pend"><span class="deep-noabc">♪ {setting ? 'no notation image' : 'no notation'}</span></div>
        {/if}
        <div class="nb-foot">
          <button class="nb-tab" class:active={mode === 'notes'} onclick={() => setMode('notes')}>notes</button>
          <button class="nb-tab" class:active={mode === 'abc'} disabled={!setting} onclick={() => setMode('abc')}>abc</button>
          <a class="nb-ext" href={tsUrl} target="_blank" rel="noopener">thesession</a>
        </div>
      </div>

      {#if settings.length}
        <div class="pv-setnav">
          <button class="pv-step" disabled={setIdx === 0} aria-label="Previous setting" onclick={() => stepSetting(-1)}>‹</button>
          <span class="pv-setlabel">Setting {setIdx + 1} of {settings.length}{setting?.key ? ` · ${setting.key}` : ''}</span>
          <button class="pv-step" disabled={setIdx >= settings.length - 1} aria-label="Next setting" onclick={() => stepSetting(1)}>›</button>
        </div>
      {/if}

      {#if isRemote}
        <div class="pv-import-note">Not in the library yet — it will be imported from thesession.org when you add it.</div>
      {/if}

      <div class="pv-stats">
        <span><b>{data.tunebook_count ?? 0}</b> tunebooks{data.played_here
          ? ` · played here ${data.played_here}× — last: ${data.dates.join(', ')}`
          : ''}</span>
      </div>
    {/if}
  </div>

  <div class="pv-foot">
    <button class="pv-action" onclick={doAction}>{actionLabel}</button>
  </div>
</div>
