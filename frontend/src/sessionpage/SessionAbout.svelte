<script>
  /**
   * The session's free-text description, clamped to two lines with a "more" toggle.
   *
   * Some sessions paste a whole year's worth of dates in here, which on a phone pushed
   * the tunes/logs/people tabs off the bottom of the screen. Whether it actually needs
   * clamping depends on how the text wraps at the current width, so the toggle only
   * appears once we've measured that it overflows.
   *
   * The shell server-renders the same paragraph inside this component's mount target so
   * the text is there before the bundle loads; main.js clears it right before mounting.
   */
  let { comments } = $props()

  let el = $state()
  let expanded = $state(false)
  let overflowing = $state(false)

  $effect(() => {
    if (!el) return
    // Reading `expanded` here is deliberate: collapsing re-runs the effect so we
    // re-measure at the new width (an expanded box never overflows).
    const measure = () => {
      if (expanded) return
      overflowing = el.scrollHeight > el.clientHeight + 1
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  })
</script>

<div class="sa-wrap" class:sa-expanded={expanded}>
  <p class="sa-text" bind:this={el}>
    <strong>About this session:</strong>
    {comments}{#if expanded}<button class="sa-toggle sa-less" onclick={() => (expanded = false)}
        >less</button
      >{/if}
  </p>

  {#if overflowing && !expanded}
    <button class="sa-toggle sa-more" onclick={() => (expanded = true)}>more …</button>
  {/if}
</div>

<style>
  /* The margin lives on the wrapper (matching .session-details p) so the absolutely
     positioned "more" can sit flush against the last visible line. */
  .sa-wrap {
    position: relative;
    margin-bottom: 6px;
  }

  .sa-text {
    margin: 0;
  }

  .sa-wrap:not(.sa-expanded) .sa-text {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .sa-toggle {
    border: 0;
    padding: 0;
    background: none;
    color: var(--primary, #007bff);
    font: inherit;
    cursor: pointer;
  }

  .sa-more {
    position: absolute;
    right: 0;
    bottom: 0;
    /* Fade the clamped text out underneath, rather than butting up against it. */
    padding-left: 2.5em;
    background: linear-gradient(to right, rgba(42, 42, 42, 0), #2a2a2a 1.6em);
  }

  .sa-less {
    margin-left: 0.4em;
  }
</style>
