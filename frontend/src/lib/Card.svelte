<script>
  // Card (spec 035): plain surface — replaces .home-card and Bootstrap .card.
  let {
    hover = false, // lift on hover (linky cards)
    children,
    ...rest // class, onclick, etc. pass through
  } = $props()
</script>

<div {...rest} class="kit-card {rest.class ?? ''}" class:hover>
  {@render children?.()}
</div>

<style>
  .kit-card {
    background: var(--bg-color, #fff);
    color: var(--text-color, #252930);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r, 8px);
    padding: var(--sp-4, 16px);
  }
  .kit-card.hover {
    transition: box-shadow var(--dur-quick, 0.15s) var(--ease, ease-out);
  }
  .kit-card.hover:hover {
    box-shadow: var(--shadow-md, 0 2px 10px rgba(0, 0, 0, 0.12));
  }
</style>
