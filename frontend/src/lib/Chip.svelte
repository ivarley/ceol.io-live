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
    styled = true, // false: structure only; skin comes from the page via chipClass
    chipClass = '', // legacy skin + e2e/CSS hook passthrough (wrapper)
    xClass = '', // legacy class for the dismiss ×
    children, // richer content than a plain label
    ...rest // title, style, data-* … pass through to the wrapper
  } = $props()
</script>

{#if onclick && !dismissible}
  <!-- whole chip is the button (padding included) — no × to conflict with -->
  <button
    {...rest}
    type="button"
    class="kit-chip{styled ? ` kit-chip--styled kit-chip-${variant}` : ''} {chipClass}"
    class:active
    class:clickable={true}
    {onclick}><span class="kit-chip-body">{label}{@render children?.()}</span></button>
{:else}
  <span
    {...rest}
    class="kit-chip{styled ? ` kit-chip--styled kit-chip-${variant}` : ''} {chipClass}"
    class:active
    class:clickable={!!onclick}
    >{#if onclick}<button type="button" class="kit-chip-body" {onclick}
        >{label}{@render children?.()}</button
      >{:else}<span class="kit-chip-body">{label}{@render children?.()}</span
      >{/if}{#if dismissible}<button
        type="button"
        class="kit-x {xClass}"
        aria-label="Remove {label}"
        onclick={onDismiss}>&#215;</button
      >{/if}</span
  >
{/if}

<style>
  .kit-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-1, 4px);
    white-space: nowrap;
  }
  /* Neutral button base at ZERO specificity (:where) so any legacy badge
     class (e.g. .status-badge) or the kit skin wins and paints it. */
  :global(:where(button.kit-chip)) {
    font: inherit;
    text-align: inherit;
    background: none;
    border: none;
    padding: 0;
  }
  /* Decorative skin — only under --styled so legacy badge classes aren't fought. */
  .kit-chip--styled {
    padding: 2px var(--sp-2, 8px);
    font-size: 0.85rem;
    line-height: 1.4;
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-pill, 999px);
    background: var(--bg-color, #fff);
    color: var(--text-color, #252930);
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
  .kit-chip--styled.clickable:hover {
    background: var(--hover-bg, #f8f9fa);
  }
  .kit-chip--styled.active,
  .kit-chip-primary {
    background: var(--primary, #00a1e0);
    border-color: var(--primary, #00a1e0);
    color: #fff;
  }
  .kit-chip--styled.active.clickable:hover,
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
