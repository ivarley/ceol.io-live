<script>
  // Pager (spec 035): inspect-mode stepper — ‹ › plus "N of M" (TunePreview's
  // result/setting pagers). The "N of M" label lives HERE, never on a List.
  let {
    index = $bindable(0), // 0-based
    count = 0,
    onPrev = null, // omit to let the pager step bind:index itself
    onNext = null,
    label = 'result', // aria context, e.g. "setting"
  } = $props()

  function prev() {
    if (index <= 0) return
    if (onPrev) onPrev()
    else index -= 1
  }
  function next() {
    if (index >= count - 1) return
    if (onNext) onNext()
    else index += 1
  }
</script>

<div class="kit-pager">
  <button type="button" class="kit-pager-btn" aria-label="Previous {label}" disabled={index <= 0} onclick={prev}>&#8249;</button>
  <span class="kit-pager-label">{count ? index + 1 : 0} of {count}</span>
  <button type="button" class="kit-pager-btn" aria-label="Next {label}" disabled={index >= count - 1} onclick={next}>&#8250;</button>
</div>

<style>
  .kit-pager {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-2, 8px);
  }
  .kit-pager-btn {
    background: var(--bg-color, #fff);
    color: var(--primary, #00a1e0);
    border: 1px solid var(--border-color, #ddd);
    border-radius: var(--r-sm, 4px);
    min-width: 28px;
    padding: 2px var(--sp-2, 8px);
    font-size: 1.1rem;
    line-height: 1.2;
    cursor: pointer;
  }
  .kit-pager-btn:hover:not(:disabled) {
    background: var(--hover-bg, #f8f9fa);
  }
  .kit-pager-btn:disabled {
    color: var(--disabled-text, #adb4c0);
    cursor: default;
  }
  .kit-pager-label {
    font-size: 0.9rem;
    color: var(--text-muted, #6c757d);
    white-space: nowrap;
  }
</style>
