// Publish an element's height as a CSS custom property, so whatever sticks BELOW
// it can offset itself without a magic number (spec 052 §B8 Stage 3).
//
// The session page stacks three sticky layers under a fixed site header: the tab
// bar, then the active tab's toolbar, then (on Logs) the year headers. Each needs
// to know the height of everything above it. Hard-coding those numbers breaks the
// moment a toolbar wraps at a narrow width or grows — which the Tunes filter panel
// does every time it opens — so they are measured instead.
//
// Usage:  <div use:publishHeight={'--session-tabs-h'}>
export function publishHeight(node, varName) {
  const set = () =>
    document.documentElement.style.setProperty(
      varName,
      `${Math.round(node.getBoundingClientRect().height)}px`,
    )

  set()
  // ResizeObserver rather than a one-shot read: the panel opening, a font
  // loading, and the tab bar wrapping are all height changes nobody tells us about.
  const observer =
    typeof ResizeObserver === 'function' ? new ResizeObserver(set) : null
  observer?.observe(node)

  return {
    destroy() {
      observer?.disconnect()
      // Deliberately NOT removing the property. Switching tabs destroys the old
      // toolbar and creates the new one, and Svelte may run this teardown after
      // the new one has already published its height — clearing it here would
      // drop the offset to its fallback for a frame, and the year headers would
      // visibly jump. Every tab has a toolbar, so a stale value is always
      // replaced rather than left to rot.
    },
  }
}
