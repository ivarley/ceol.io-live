<script>
  // Shows a tune's incipit notation as a server-rendered PNG (the abc-renderer
  // service is the only renderer — no client-side music rendering). If the image
  // isn't cached yet, lazily (when scrolled into view) asks the incipit endpoint to
  // render + cache it in the background, then displays it.
  import { fetchIncipit } from './client.js'

  let { config, tuneId, image = null, canRender = false } = $props()
  let src = $state(image)
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
    if (src || !visible || !canRender || !tuneId) return
    loading = true
    fetchIncipit(config, tuneId)
      .then((b64) => { if (b64) src = b64 })
      .finally(() => { loading = false })
  })
</script>

<div class="incipit" bind:this={el}>
  {#if src}
    <img class="incipit-img" src={`data:image/png;base64,${src}`} alt="notation" />
  {:else if loading}
    <span class="deep-noabc">♪ rendering…</span>
  {:else if canRender}
    <span class="deep-noabc">♪</span>
  {:else}
    <span class="deep-noabc">♪ no notation</span>
  {/if}
</div>
