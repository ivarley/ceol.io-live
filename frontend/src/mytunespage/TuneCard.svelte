<script module>
  // Only one card across the list may stay revealed at once.
  const shared = { closeRevealed: null }
</script>

<script>
  // One tune card. Emits the SAME markup/classes as the legacy renderer
  // (my_tunes_mobile.css + e2e selectors depend on them): a bare .tune-card on
  // desktop; on mobile a .tune-card-swipe-container wrapping the swipe action
  // and a .tune-card-swipeable (swipe right to reveal/trigger the heard +).
  // `isMobile` is reactive (matchMedia in App), so rotating a tablet across the
  // 768px breakpoint re-renders the right variant — the legacy render-time
  // innerWidth check couldn't.
  import { Chip } from '../lib/index.js'

  let {
    tune,
    isMobile,
    displayStatus,
    cycleIsInstrument,
    typeLabel,
    typeTitle = '',
    onshow,
    oncycle,
    onincrement,
  } = $props()

  const BUTTON_WIDTH = 80 // matches .tune-card-swipe-action CSS

  let cardEl = $state(null)
  let containerEl = $state(null)
  let dragX = $state(0)
  let revealed = $state(false)
  let swiping = $state(false)
  let dragging = $state(false)
  let flashBtn = $state(false)

  const statusClass = $derived('status-' + displayStatus.replace(/ /g, '-'))
  const thesessionUrl = $derived(
    tune.tune_id
      ? tune.setting_id
        ? `https://thesession.org/tunes/${tune.tune_id}?setting=${tune.setting_id}#setting${tune.setting_id}`
        : `https://thesession.org/tunes/${tune.tune_id}`
      : ''
  )

  function close() {
    revealed = false
    dragX = 0
    if (shared.closeRevealed === close) shared.closeRevealed = null
  }

  function triggerIncrement() {
    flashBtn = true
    setTimeout(() => (flashBtn = false), 200)
    onincrement(tune)
  }

  // Swipe right = reveal / trigger the heard + (legacy swipe impl #2). Attached
  // manually because the move handler must be NON-passive (it preventDefaults to
  // stop the page scrolling during a horizontal drag).
  $effect(() => {
    const el = cardEl
    if (!el) return

    let startX = 0
    let startY = 0
    let active = false
    let direction = null

    const onStart = (e) => {
      startX = e.touches[0].clientX
      startY = e.touches[0].clientY
      active = true
      direction = null
      if (shared.closeRevealed && shared.closeRevealed !== close) shared.closeRevealed()
      shared.closeRevealed = close
      if (revealed) close()
    }
    const onMove = (e) => {
      if (!active) return
      const diffX = e.touches[0].clientX - startX
      const diffY = e.touches[0].clientY - startY
      if (direction === null && (Math.abs(diffX) > 5 || Math.abs(diffY) > 5)) {
        direction = Math.abs(diffX) > Math.abs(diffY) ? 'horizontal' : 'vertical'
        if (direction === 'horizontal') swiping = true
      }
      if (direction === 'horizontal' && diffX > 0) {
        dragging = true
        dragX = Math.min(diffX, BUTTON_WIDTH * 2)
        e.preventDefault()
      }
    }
    const onEnd = () => {
      if (!active) return
      active = false
      swiping = false
      dragging = false
      if (direction === 'horizontal') {
        if (dragX > BUTTON_WIDTH) {
          close()
          triggerIncrement()
        } else if (dragX > BUTTON_WIDTH * 0.25) {
          revealed = true
          dragX = BUTTON_WIDTH
        } else {
          close()
        }
      }
      direction = null
    }

    el.addEventListener('touchstart', onStart, { passive: true })
    el.addEventListener('touchmove', onMove, { passive: false })
    el.addEventListener('touchend', onEnd, { passive: true })
    return () => {
      el.removeEventListener('touchstart', onStart)
      el.removeEventListener('touchmove', onMove)
      el.removeEventListener('touchend', onEnd)
    }
  })

  // Tap elsewhere closes a revealed card.
  $effect(() => {
    if (!revealed) return
    const handler = (e) => {
      if (containerEl && !containerEl.contains(e.target)) close()
    }
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  })
</script>

{#snippet cardBody()}
  <div class="tune-card-header">
    <h3 class="tune-name">{tune.tune_name || 'Unknown'}</h3>
    <!-- This tune is here because its NOTATION matched, not its name — without the mark
         a notes search reads as a list of unrelated tunes. -->
    {#if tune._abcOnly}<span class="abc-only-badge" title="Matched the notation, not the name">♪</span>{/if}
    {#if tune.pending_sync}
      <Chip
        label="pending"
        styled={false}
        chipClass="pending-sync-badge"
        title="Queued - will sync when you are back online"
        style="flex:0 0 auto;white-space:nowrap;font-size:11px;font-weight:600;color:#b58900;" />
    {/if}
    {#if typeLabel}<Chip label={typeLabel} styled={false} chipClass="tune-type" title={typeTitle || undefined} />{/if}
  </div>
  <div class="tune-meta">
    <div class="tune-meta-item">
      <Chip
        label={displayStatus}
        styled={false}
        chipClass="status-badge {statusClass}"
        style="cursor:pointer;"
        title="Tap to change status"
        onclick={(e) => {
          e.stopPropagation()
          oncycle(tune, displayStatus, cycleIsInstrument)
        }} />
    </div>
  </div>
  {#if displayStatus === 'want to learn'}
    <div class="heard-count-container">
      {#if tune.heard_count > 0}
        <span>Heard at sessions:</span>
        <span class="heard-count">{tune.heard_count}</span>
        <button
          class="increment-heard-btn"
          title="Increment heard count"
          onclick={(e) => {
            e.stopPropagation()
            onincrement(tune)
          }}>+</button>
      {:else}
        <button
          class="increment-heard-btn"
          title="Mark as heard"
          onclick={(e) => {
            e.stopPropagation()
            onincrement(tune)
          }}>+</button>
        <span style="font-size: 12px;">Mark as heard</span>
      {/if}
    </div>
  {/if}
  <div class="tune-actions">
    {#if thesessionUrl}
      <a
        href={thesessionUrl}
        target="_blank"
        class="tune-action-btn"
        onclick={(e) => e.stopPropagation()}>View on TheSession.org</a>
    {/if}
  </div>
{/snippet}

{#if isMobile}
  <div
    bind:this={containerEl}
    class="tune-card-swipe-container"
    data-person-tune-id={tune.person_tune_id}
    data-tune-id={tune.tune_id}>
    <div class="tune-card-swipe-action" style="width: {dragX}px;">
      <button
        class="swipe-action-btn"
        data-action="increment"
        data-person-tune-id={tune.person_tune_id}
        style={flashBtn ? 'background-color: #218838;' : ''}
        onclick={(e) => {
          e.stopPropagation()
          close()
          triggerIncrement()
        }}>
        <span class="swipe-action-icon">+</span>
      </button>
    </div>
    <div
      bind:this={cardEl}
      class="tune-card tune-card-swipeable"
      class:tune-card-dimmed={tune._instDimmed}
      class:swiping
      class:revealed
      style={dragging || revealed ? `transform: translateX(${dragX}px);` : ''}
      role="button"
      tabindex="0"
      onclick={() => onshow(tune)}
      onkeydown={(e) => e.key === 'Enter' && onshow(tune)}>
      {@render cardBody()}
    </div>
  </div>
{:else}
  <div
    class="tune-card"
    class:tune-card-dimmed={tune._instDimmed}
    data-person-tune-id={tune.person_tune_id}
    data-tune-id={tune.tune_id}
    role="button"
    tabindex="0"
    onclick={() => onshow(tune)}
    onkeydown={(e) => e.key === 'Enter' && onshow(tune)}>
    {@render cardBody()}
  </div>
{/if}
