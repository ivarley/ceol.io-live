// Shared open/close state machine for the add panes (My Tunes + session tunes).
// One body class drives the desktop split-pane squeeze on whichever page hosts the
// pane; close() unmounts on a delay (the slide-out transition) and open() cancels a
// pending unmount so a reopen inside the window can't be killed by the stale timer
// (which would leave the page squeezed with no pane).
export function createPaneState(bodyClass = 'mt-add-open') {
  let visible = $state(false) // pane in the DOM
  let shown = $state(false) // slide-in transform applied (one frame later, so it animates)
  let closeTimer = null

  return {
    get visible() {
      return visible
    },
    get shown() {
      return shown
    },
    open() {
      if (closeTimer) {
        clearTimeout(closeTimer)
        closeTimer = null
      }
      visible = true
      document.body.classList.add(bodyClass)
      requestAnimationFrame(() => requestAnimationFrame(() => (shown = true)))
    },
    close(onHidden = () => {}) {
      if (closeTimer) clearTimeout(closeTimer)
      shown = false
      document.body.classList.remove(bodyClass)
      closeTimer = setTimeout(() => {
        closeTimer = null
        visible = false
        onHidden()
      }, 300) // matches the pane's slide transition
    },
  }
}
