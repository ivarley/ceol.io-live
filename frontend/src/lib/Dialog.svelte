<script>
  import { AlertDialog } from 'bits-ui'

  // Dialog (spec 035): ONE decision, never scrolls. Confirm label is an explicit
  // verb ("Delete session"), never "OK". Outside clicks are ignored (a decision
  // must be answered or cancelled); Escape = Cancel.
  let {
    open = $bindable(false),
    title = '',
    description = '', // plain-text body; use children for markup instead
    confirmLabel = 'Confirm', // callers should pass an explicit verb
    cancelLabel = 'Cancel',
    destructive = false, // red confirm for irreversible actions
    onConfirm = () => {},
    onCancel = () => {},
    children,
  } = $props()

  // bits-ui AlertDialog.Action does NOT auto-close (v2 behavior) — we close.
  let suppressCancel = false
  function confirm() {
    suppressCancel = true
    open = false
    onConfirm()
  }
  // AlertDialog.Cancel auto-closes on click; Escape closes via bits. Both land
  // in onOpenChange(false) — report Cancel there unless we just confirmed.
  function handleOpenChange(v) {
    if (!v && !suppressCancel) onCancel()
    suppressCancel = false
  }
</script>

<AlertDialog.Root bind:open onOpenChange={handleOpenChange}>
  <AlertDialog.Portal>
    <AlertDialog.Overlay class="kit-dialog-scrim" />
    <AlertDialog.Content class="kit-dialog" preventScroll={false} aria-describedby={undefined}>
      <AlertDialog.Title class="kit-dialog-title" level={2}>{title}</AlertDialog.Title>
      {#if description}
        <AlertDialog.Description class="kit-dialog-desc">{description}</AlertDialog.Description>
      {/if}
      {@render children?.()}
      <div class="kit-dialog-actions">
        <AlertDialog.Cancel class="kit-dialog-cancel">{cancelLabel}</AlertDialog.Cancel>
        <AlertDialog.Action class="kit-dialog-confirm{destructive ? ' destructive' : ''}" onclick={confirm}>
          {confirmLabel}
        </AlertDialog.Action>
      </div>
    </AlertDialog.Content>
  </AlertDialog.Portal>
</AlertDialog.Root>

<style>
  :global(.kit-dialog-scrim) {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal-overlay, 1900);
    background: var(--scrim, rgba(0, 0, 0, 0.5));
  }
  :global(.kit-dialog) {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: var(--z-modal-content, 1910);
    width: min(400px, calc(100vw - 32px));
    padding: var(--sp-5, 20px);
    background: var(--bg-color, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-lg, 12px);
    box-shadow: var(--shadow-lg, 0 8px 30px rgba(0, 0, 0, 0.2));
  }
  :global(.kit-dialog-title) {
    margin: 0 0 var(--sp-2, 8px);
    font-size: 1.1rem;
    font-weight: 600;
  }
  :global(.kit-dialog-desc) {
    margin: 0;
    color: var(--text-muted, #6c757d);
  }
  .kit-dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--sp-2, 8px);
    margin-top: var(--sp-5, 20px);
  }
  :global(.kit-dialog-cancel),
  :global(.kit-dialog-confirm) {
    padding: var(--sp-2, 8px) var(--sp-4, 16px);
    font-size: 0.95rem;
    border-radius: var(--r-sm, 4px);
    cursor: pointer;
  }
  :global(.kit-dialog-cancel) {
    background: var(--bg-color, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--border-color, #ddd);
  }
  :global(.kit-dialog-cancel:hover) {
    background: var(--hover-bg, #f8f9fa);
  }
  :global(.kit-dialog-confirm) {
    background: var(--primary, #00a1e0);
    color: #fff;
    border: 1px solid var(--primary, #00a1e0);
  }
  :global(.kit-dialog-confirm.destructive) {
    background: var(--danger, #dc3545);
    border-color: var(--danger, #dc3545);
  }
</style>
