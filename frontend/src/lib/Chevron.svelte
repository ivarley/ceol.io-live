<script>
  // The app's one chevron (spec 052 §B16).
  //
  // Everything that pointed somewhere used to be a typographic character — `›` and
  // `‹` (single angle QUOTATION marks), `▸ ▾` (triangles), `←`. Punctuation makes a
  // poor icon: it inherits the font's metrics, so its stroke weight never matches the
  // UI around it, it sits on a text baseline instead of being optically centred, and
  // it renders differently per font and platform. The tune drawer's caret was a 9px
  // `▸`, which is where that ends up.
  //
  // Drawn instead: one path, one stroke weight, square box, centred. It matches the
  // tab-bar icons, which are stroked SVG at the same weight.
  //
  // Direction is a CLASS, not an inline transform, so a caller can still rotate it
  // with its own CSS — the disclosure rows flip theirs by adding `.open`.
  let {
    dir = 'right', // right | down | left | up
    size = 16,
    strokeWidth = 2,
    class: cls = '',
    ...rest
  } = $props()
</script>

<svg
  {...rest}
  class="kit-chevron kit-chevron--{dir} {cls}"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width={strokeWidth}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
  focusable="false"
><polyline points="9 5 16 12 9 19" /></svg>

<style>
  .kit-chevron {
    flex: 0 0 auto;
    display: block;
    /* Rotation is the whole mechanism, so it has to animate here rather than at
       each call site. */
    transition: transform 0.18s ease;
  }
  .kit-chevron--down {
    transform: rotate(90deg);
  }
  .kit-chevron--left {
    transform: rotate(180deg);
  }
  .kit-chevron--up {
    transform: rotate(-90deg);
  }
</style>
