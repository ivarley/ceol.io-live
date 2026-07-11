<script>
  // Chip (spec 035): small pill — tune pills, filter pills, instrument badges,
  // status badges. Clickable when onclick is passed; dismissible shows the one
  // sanctioned close glyph (U+00D7).
  let {
    label = '',
    active = false,
    dismissible = false,
    variant = 'default', // 'default' | 'primary' | 'success' | 'warning' | 'danger'
    onclick = null,
    onDismiss = () => {},
    children, // richer content than a plain label
  } = $props()
</script>

<span class="kit-chip kit-chip-{variant}" class:active class:clickable={!!onclick}>
  {#if onclick}
    <!-- the pill body is the button; × stays a sibling so we never nest buttons -->
    <button type="button" class="kit-chip-body" {onclick}>{label}{@render children?.()}</button>
  {:else}
    <span class="kit-chip-body">{label}{@render children?.()}</span>
  {/if}
  {#if dismissible}
    <button type="button" class="kit-x" aria-label="Remove {label}" onclick={onDismiss}>&#215;</button>
  {/if}
</span>

<style>
  .kit-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-1, 4px);
    padding: 2px var(--sp-2, 8px);
    font-size: 0.85rem;
    line-height: 1.4;
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-pill, 999px);
    background: var(--bg-color, #fff);
    color: var(--text-color, #252930);
    white-space: nowrap;
  }
  .kit-chip-body {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-1, 4px);
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    color: inherit;
  }
  .kit-chip.clickable {
    cursor: pointer;
  }
  .kit-chip.clickable :is(button.kit-chip-body) {
    cursor: pointer;
  }
  .kit-chip.clickable:hover {
    background: var(--hover-bg, #f8f9fa);
  }
  .kit-chip.active,
  .kit-chip-primary {
    background: var(--primary, #00a1e0);
    border-color: var(--primary, #00a1e0);
    color: #fff;
  }
  .kit-chip.active.clickable:hover,
  .kit-chip-primary.clickable:hover {
    background: var(--primary-dark, #0056b3);
  }
  .kit-chip-success {
    background: var(--success-bg, #d4edda);
    border-color: var(--success-border, #c3e6cb);
    color: var(--success-text, #155724);
  }
  .kit-chip-warning {
    background: var(--warning-bg, #fff3cd);
    border-color: var(--warning-border, #ffeaa7);
    color: var(--warning-text, #856404);
  }
  .kit-chip-danger {
    background: var(--error-bg, #f8d7da);
    border-color: var(--error-border, #f5c6cb);
    color: var(--error-text, #721c24);
  }
  .kit-x {
    background: none;
    border: none;
    padding: 0 2px;
    font: inherit;
    font-size: 1em;
    line-height: 1;
    color: inherit;
    opacity: 0.7;
    cursor: pointer;
  }
  .kit-x:hover {
    opacity: 1;
  }
</style>
