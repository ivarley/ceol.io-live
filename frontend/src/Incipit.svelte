<script>
  // i18n-converted
  // Shows a tune's incipit notation as a server-rendered PNG (the abc-renderer
  // service is the only renderer — no client-side music rendering). If the image
  // isn't cached yet, lazily (when scrolled into view) asks the incipit endpoint to
  // render + cache it in the background, then displays it.
  import { untrack } from 'svelte'
  import { fetchIncipit, settingImage } from './client.js'
  import { t } from './lib/index.js'

  // settingId: a particular setting's opening bars (what a session of yours plays)
  // rather than the tune's default ones.
  let { config, tuneId, image = null, canRender = false, settingId = null } = $props()
  let src = $state(untrack(() => image)) // initial cached image; the lazy fetch fills it in if absent
  let loading = $state(false)
  let el

  // only fetch/render when the card actually scrolls into view (don't hammer the
  // renderer for 30 results at once)
  let visible = $state(false)
  $effect(() => {
    if (!el || visible) return
    const io = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) { visible = true; io.disconnect() } },
      { rootMargin: '150px' },
    )
    io.observe(el)
    return () => io.disconnect()
  })

  $effect(() => {
    if (src || !visible || !tuneId) return
    if (settingId == null && !canRender) return
    loading = true
    const p = settingId != null ? settingImage(config, settingId, 'incipit') : fetchIncipit(config, tuneId)
    p.then((b64) => { if (b64) src = b64 })
      .finally(() => { loading = false })
  })
</script>

<div class="incipit" bind:this={el}>
  {#if src}
    <img class="incipit-img" src={`data:image/png;base64,${src}`} alt={t('notation')} />
  {:else if loading}
    <span class="deep-noabc">♪ {t('rendering…')}</span>
  {:else if canRender || settingId != null}
    <span class="deep-noabc">♪</span>
  {:else}
    <span class="deep-noabc">♪ {t('no notation')}</span>
  {/if}
</div>
