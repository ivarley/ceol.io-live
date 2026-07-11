<script module>
  // One body-scroll lock shared by every Sheet instance: with stacked sheets
  // (detail over add-pane) the body stays locked until the LAST one closes.
  // The kit owns this instead of bits-ui's preventScroll because bits restores
  // the body's full style attribute on a delay — two owners would clobber each
  // other when sheets nest (see the preventScroll={false} below).
  let lockCount = 0
  let savedOverflow = ''
  function lockBody() {
    if (lockCount++ === 0) {
      savedOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    }
  }
  function unlockBody() {
    if (lockCount > 0 && --lockCount === 0) document.body.style.overflow = savedOverflow
  }
</script>

<script>
  import { Dialog as BitsDialog } from 'bits-ui'

  // Sheet (spec 035): holds a task or scrollable detail — never a bare decision
  // (that's Dialog). Full-screen under 768px; on desktop a single prop picks
  // centered dialog vs docked right pane. Scrim tap / Escape = Cancel.
  let {
    open = $bindable(false),
    title = '',
    desktop = 'center', // 'center' | 'dock' — the ONE responsive knob
    back = null, // label for a back chevron ("‹ Label") replacing Cancel
    cancelLabel = 'Cancel',
    onCancel = () => {}, // abandon: Cancel button, back chevron, scrim tap, Escape
    onDone = null, // commit; the Done button only renders when this is passed
    doneLabel = 'Done',
    children,
    footer = null, // optional footer snippet (action bar)
  } = $props()

  // Lock body scroll only while open; cleanup covers close AND unmount-while-open.
  $effect(() => {
    if (!open) return
    suppressCancel = false
    lockBody()
    return () => unlockBody()
  })

  // Bits fires onOpenChange(false) for its own dismissals (scrim tap, Escape) —
  // those mean Cancel. Our buttons close by assigning `open` and must not
  // double-report, hence the suppress flag.
  let suppressCancel = false
  function cancel() {
    suppressCancel = true
    open = false
    onCancel()
  }
  function done() {
    suppressCancel = true
    open = false
    onDone?.()
  }
  function handleOpenChange(v) {
    if (!v && !suppressCancel) onCancel()
    suppressCancel = false
  }
</script>

<BitsDialog.Root bind:open onOpenChange={handleOpenChange}>
  <BitsDialog.Portal>
    <BitsDialog.Overlay class="kit-sheet-scrim" />
    <BitsDialog.Content class="kit-sheet kit-sheet-{desktop}" preventScroll={false} aria-describedby={undefined}>
      <header class="kit-sheet-head">
        {#if back != null}
          <button type="button" class="kit-sheet-back" onclick={cancel}>‹ {back}</button>
        {:else}
          <button type="button" class="kit-sheet-cancel" onclick={cancel}>{cancelLabel}</button>
        {/if}
        <BitsDialog.Title class="kit-sheet-title" level={2}>{title}</BitsDialog.Title>
        {#if onDone}
          <button type="button" class="kit-sheet-done" onclick={done}>{doneLabel}</button>
        {:else}
          <span class="kit-sheet-spacer" aria-hidden="true"></span>
        {/if}
      </header>
      <div class="kit-sheet-body">
        {@render children?.()}
      </div>
      {#if footer}
        <footer class="kit-sheet-foot">{@render footer()}</footer>
      {/if}
    </BitsDialog.Content>
  </BitsDialog.Portal>
</BitsDialog.Root>

<style>
  /* Bits renders the scrim/content/title elements, so they need :global; the
     header/body/footer are authored here and scope normally. */
  :global(.kit-sheet-scrim) {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal-overlay, 1900);
    background: var(--scrim, rgba(0, 0, 0, 0.5));
  }
  :global(.kit-sheet) {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal-content, 1910);
    display: flex;
    flex-direction: column;
    background: var(--bg-color, #fff);
    color: var(--text-color, #252930);
  }
  @media (min-width: 768px) {
    :global(.kit-sheet-center) {
      inset: auto;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: min(560px, calc(100vw - 32px));
      max-height: 85vh;
      border: 1px solid var(--border-color, #ddd);
      border-radius: var(--r-lg, 12px);
      box-shadow: var(--shadow-lg, 0 8px 30px rgba(0, 0, 0, 0.2));
    }
    :global(.kit-sheet-dock) {
      inset: 0 0 0 auto;
      width: min(420px, 100vw);
      border-left: 1px solid var(--border-color, #ddd);
      box-shadow: var(--shadow-lg, 0 8px 30px rgba(0, 0, 0, 0.2));
    }
  }
  .kit-sheet-head {
    display: flex;
    align-items: center;
    gap: var(--sp-2, 8px);
    padding: var(--sp-3, 12px) var(--sp-4, 16px);
    border-bottom: 1px solid var(--border-color, #ddd);
    flex: none;
  }
  :global(.kit-sheet-title) {
    flex: 1;
    margin: 0;
    text-align: center;
    font-size: 1.05rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kit-sheet-cancel,
  .kit-sheet-back,
  .kit-sheet-done {
    background: none;
    border: none;
    padding: 0;
    font-size: 1rem;
    color: var(--primary, #00a1e0);
    cursor: pointer;
    white-space: nowrap;
  }
  .kit-sheet-done {
    font-weight: 600;
  }
  /* keeps the title centered when there's no Done button */
  .kit-sheet-cancel,
  .kit-sheet-back,
  .kit-sheet-done,
  .kit-sheet-spacer {
    min-width: 3.5em;
  }
  .kit-sheet-cancel,
  .kit-sheet-back {
    text-align: left;
  }
  .kit-sheet-done {
    text-align: right;
  }
  .kit-sheet-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--sp-4, 16px);
  }
  .kit-sheet-foot {
    flex: none;
    padding: var(--sp-3, 12px) var(--sp-4, 16px);
    border-top: 1px solid var(--border-color, #ddd);
  }
</style>
