<script>
  // i18n-converted
  import { untrack } from 'svelte'
  import { Chevron, LoadError, Sheet, t } from '../lib/index.js'
  import { tunePreview, thesessionPreview, settingImage, renderRemoteAbc } from '../client.js'

  // The setting chooser: "which written version of this tune do we play?" Opened
  // from the tune drawer for one layer (mine, the session's, or one night's), it
  // pages through every setting of the tune — the ones we hold, then the rest from
  // thesession.org as they arrive — showing each one's FULL notation, and hands
  // the picked one back to the drawer to save.
  //
  // Paging has to feel instant, so the renders run ahead of you: while you look
  // at a setting, the next two are rendered (and, for a setting we hold, cached
  // server-side for good) one after another, before you get to them.
  let {
    open = $bindable(false),
    tuneId,
    tuneName = '',
    tuneType = '',
    currentSettingId = null, // the setting this layer uses now: where the pager opens
    heading = '',
    onChoose, // async (setting, image) -> true when saved (the chooser then closes)
  } = $props()

  const NO_SCOPE = {} // the preview endpoints' scope: none — the drawer knows its own

  let settings = $state([]) // [{setting_id, key, abc, incipit_abc, incipit_image, remote?}]
  let idx = $state(0)
  let loading = $state(true)
  let failed = $state(false)
  let backfilling = $state(false)
  let touched = $state(false) // has the user paged? (then a late backfill mustn't move them)
  let saving = $state(false)
  let images = $state({}) // setting_id -> base64, or false when it couldn't be drawn
  let loadSeq = 0
  let warmSeq = 0

  const setting = $derived(settings[idx] || null)
  const image = $derived(setting ? images[setting.setting_id] : undefined)
  const isCurrent = $derived(!!setting && currentSettingId != null && setting.setting_id === Number(currentSettingId))
  const tsUrl = $derived(
    setting
      ? `https://thesession.org/tunes/${tuneId}?setting=${setting.setting_id}#setting${setting.setting_id}`
      : `https://thesession.org/tunes/${tuneId}`
  )

  // Load on every open: the settings we hold first (instant), then thesession.org's
  // full list in the background, merged in setting order so "Setting 3 of 12" means
  // the same as it does there.
  $effect(() => {
    if (!open || tuneId == null) return
    untrack(load)
    // Closed (or gone): whatever is still in flight lands on nothing.
    return () => {
      loadSeq++
      warmSeq++
    }
  })

  function load() {
    const seq = ++loadSeq
    settings = []
    idx = 0
    touched = false
    saving = false
    failed = false
    loading = true
    backfilling = false
    tunePreview(NO_SCOPE, tuneId)
      .then((d) => {
        if (seq !== loadSeq) return
        settings = d.settings || []
        loading = false
        jumpToCurrent()
        backfill(seq)
      })
      .catch(() => {
        if (seq !== loadSeq) return
        failed = true
        loading = false
      })
  }

  async function backfill(seq) {
    backfilling = true
    let ts
    try {
      ts = await thesessionPreview(NO_SCOPE, tuneId, true)
    } catch {
      if (seq === loadSeq) backfilling = false
      return // offline or thesession.org down: the settings we hold stand
    }
    if (seq !== loadSeq) return
    backfilling = false
    const have = new Set(settings.map((s) => s.setting_id))
    const extra = (ts?.settings || []).filter((s) => !have.has(s.setting_id)).map((s) => ({ ...s, remote: true }))
    if (!extra.length) return
    const showing = setting?.setting_id
    settings = [...settings, ...extra].sort((a, b) => a.setting_id - b.setting_id)
    // The current setting may only just have arrived; otherwise stay on the one showing.
    if (!touched && jumpToCurrent()) return
    const i = settings.findIndex((s) => s.setting_id === showing)
    if (i >= 0) idx = i
  }

  function jumpToCurrent() {
    if (currentSettingId == null) return false
    const i = settings.findIndex((s) => s.setting_id === Number(currentSettingId))
    if (i < 0) return false
    idx = i
    return true
  }

  // One setting's full notation. A setting we hold renders through the setting-image
  // endpoint, which caches the PNG for everyone; one only thesession.org has renders
  // ephemerally (it isn't ours until somebody picks it). Both share client.js's image
  // registry with the search preview, so nothing is ever drawn twice in a page.
  function warm(s) {
    if (!s || s.setting_id in images) return Promise.resolve()
    const p = s.remote
      ? renderRemoteAbc(NO_SCOPE, `ts:${tuneId}:${s.setting_id}:full`, {
          abc: s.abc,
          key: s.key,
          tune_type: tuneType,
          kind: 'full',
        })
      : settingImage(NO_SCOPE, s.setting_id, 'full')
    return p.then((img) => {
      images[s.setting_id] = img || false
    })
  }

  // The one in view first, then the next two, one at a time so the renderer works on
  // what you'll see soonest. Paging on starts a fresh run from the new place.
  $effect(() => {
    const i = idx
    const list = settings
    if (!open || !list.length) return
    untrack(() => warmFrom(i, list))
  })
  async function warmFrom(i, list) {
    const seq = ++warmSeq
    await warm(list[i])
    for (const j of [i + 1, i + 2]) {
      if (seq !== warmSeq) return
      await warm(list[j])
    }
  }

  function step(d) {
    const n = idx + d
    if (n < 0 || n >= settings.length) return
    idx = n
    touched = true
  }

  async function choose() {
    if (!setting || isCurrent || saving) return
    saving = true
    const ok = await onChoose(setting, images[setting.setting_id] || null).catch(() => false)
    saving = false
    if (ok) open = false
  }

  function onKey(e) {
    if (!open || e.target.closest?.('input, textarea, select')) return
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      step(-1)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      step(1)
    }
  }
</script>

<svelte:window onkeydown={onKey} />

<Sheet bind:open title={heading} onCancel={() => (open = false)}>
  <div class="sc">
    <div class="sc-name">{tuneName}</div>
    {#if loading}
      <div class="sc-skel" style="height:28px"></div>
      <div class="sc-skel" style="height:160px"></div>
    {:else if failed}
      <LoadError what={t('the settings of this tune')} onRetry={load} />
    {:else if !settings.length}
      <div class="sc-empty">{backfilling ? t('Looking for settings on thesession.org…') : t('No settings found for this tune')}</div>
    {:else}
      <div class="sc-nav">
        <button class="sc-step" disabled={idx === 0} aria-label={t('Previous setting')} onclick={() => step(-1)}
          ><Chevron dir="left" size={18} /></button
        >
        <span class="sc-label">
          {t('Setting {n} of {total}', { n: idx + 1, total: settings.length })}
          <span class="sc-meta">#{setting.setting_id}{setting.key ? ` · ${setting.key}` : ''}</span>
          {#if isCurrent}<span class="sc-current">★ {t('in use')}</span>{/if}
        </span>
        <button
          class="sc-step"
          disabled={idx >= settings.length - 1}
          aria-label={t('Next setting')}
          onclick={() => step(1)}
        >
          {#if backfilling && idx >= settings.length - 1}
            <!-- more settings may still be on their way from thesession.org -->
            <span class="sc-spin" aria-hidden="true"></span>
          {:else}<Chevron size={18} />{/if}
        </button>
      </div>

      <div class="sc-notation">
        {#if image}
          <img src={`data:image/png;base64,${image}`} alt={t('notation (full)')} />
        {:else if image === false}
          <!-- the renderer couldn't draw it: the abc still says what the setting is -->
          <pre class="sc-abc">{setting.abc}</pre>
        {:else}
          <div class="sc-pend"><span class="sc-spin" aria-hidden="true"></span> {t('rendering notation…')}</div>
        {/if}
      </div>
      <div class="sc-links">
        <a href={tsUrl} target="_blank" rel="noopener">{t('View on TheSession.org')}</a>
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <div class="sc-foot">
      <button class="sc-cancel" onclick={() => (open = false)}>{t('Cancel')}</button>
      <button class="sc-use" disabled={!setting || isCurrent || saving} onclick={choose}>
        {saving ? t('Saving…') : isCurrent ? t('This is the one in use') : t('Use this setting')}
      </button>
    </div>
  {/snippet}
</Sheet>

<style>
  .sc-name {
    font-weight: 600;
    font-size: 1.05rem;
    margin-bottom: 10px;
  }
  .sc-nav {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }
  .sc-label {
    flex: 1;
    text-align: center;
    font-size: 0.95rem;
  }
  .sc-meta {
    color: var(--text-muted, #6c757d);
    margin-left: 4px;
  }
  .sc-current {
    color: var(--warning-text, #b8860b);
    margin-left: 6px;
    white-space: nowrap;
  }
  .sc-step {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border: 1px solid var(--border-color, #ddd);
    border-radius: 8px;
    background: transparent;
    color: var(--text-color, inherit);
    cursor: pointer;
  }
  .sc-step:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .sc-notation {
    min-height: 160px;
    border: 1px solid var(--border-color, #ddd);
    border-radius: 8px;
    background: #fff; /* the rendered staff is black on white, in either theme */
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  .sc-notation img {
    display: block;
    width: 100%;
    height: auto;
  }
  .sc-abc {
    margin: 0;
    padding: 10px;
    width: 100%;
    white-space: pre-wrap;
    font-size: 0.8rem;
    color: #222;
  }
  .sc-pend {
    color: #666;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .sc-links {
    text-align: right;
    margin-top: 6px;
    font-size: 0.85rem;
  }
  .sc-empty {
    color: var(--text-muted, #6c757d);
    padding: 24px 0;
    text-align: center;
  }
  .sc-skel {
    border-radius: 8px;
    background: var(--hover-bg, rgba(127, 127, 127, 0.15));
    margin-bottom: 10px;
  }
  .sc-spin {
    width: 14px;
    height: 14px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    display: inline-block;
    animation: sc-spin 0.8s linear infinite;
  }
  @keyframes sc-spin {
    to {
      transform: rotate(360deg);
    }
  }
  .sc-foot {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .sc-foot button {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #ddd);
    background: transparent;
    color: var(--text-color, inherit);
    cursor: pointer;
  }
  .sc-foot .sc-use {
    background: var(--primary-fill, #0d6efd);
    border-color: var(--primary-fill, #0d6efd);
    color: #fff;
  }
  .sc-foot button:disabled {
    opacity: 0.55;
    cursor: default;
  }
</style>
