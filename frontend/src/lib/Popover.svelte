<script>
  import { Popover as BitsPopover } from 'bits-ui'

  // Popover (spec 035): anchored floating panel (hamburger menu, in-session
  // popup, context menu). Click-outside + Escape dismiss come from bits-ui.
  let {
    open = $bindable(false),
    side = 'bottom', // 'top' | 'right' | 'bottom' | 'left'
    align = 'start', // 'start' | 'center' | 'end'
    triggerClass = '', // style the trigger button from the call site
    trigger, // snippet: the trigger button's content
    children, // snippet: the panel content
  } = $props()
</script>

<BitsPopover.Root bind:open>
  <BitsPopover.Trigger class="kit-popover-trigger {triggerClass}">
    {@render trigger?.()}
  </BitsPopover.Trigger>
  <BitsPopover.Portal>
    <BitsPopover.Content class="kit-popover" {side} {align} sideOffset={4}>
      {@render children?.()}
    </BitsPopover.Content>
  </BitsPopover.Portal>
</BitsPopover.Root>

<style>
  :global(.kit-popover-trigger) {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    color: inherit;
    cursor: pointer;
  }
  :global(.kit-popover) {
    z-index: var(--z-search-dropdown, 2100);
    min-width: 160px;
    padding: var(--sp-2, 8px);
    background: var(--dropdown-bg, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--dropdown-border, #ddd);
    border-radius: var(--r, 8px);
    box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.15));
  }
</style>
