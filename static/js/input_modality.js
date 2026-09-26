/* How did focus get here? (spec 052 §B11)
 *
 * `:focus-visible` answers that for most controls, and the CSS leans on it: no
 * ring for a click, a green ring for the keyboard. But browsers deliberately
 * match :focus-visible on a CLICKED <select> (and on text fields), because you
 * can carry on with arrow keys and type-ahead once it is open. Correct in
 * general — and it is still a ring appearing because you tapped something.
 *
 * CSS cannot tell those apart on its own, so this records the modality and the
 * stylesheet suppresses the ring while the last input was a pointer.
 *
 * If this file never loads the attribute is simply absent, and every control
 * falls back to plain :focus-visible behaviour. Nothing breaks; selects go back
 * to ringing on click.
 */
;(function () {
  'use strict'
  var root = document.documentElement

  function set(mode) {
    if (root.getAttribute('data-input-modality') !== mode) {
      root.setAttribute('data-input-modality', mode)
    }
  }

  // Pointer first: mousedown/touchstart land before focus, so the attribute is
  // already right by the time the ring would paint.
  window.addEventListener('pointerdown', function () { set('pointer') }, true)

  window.addEventListener(
    'keydown',
    function (e) {
      // A real KeyboardEvent always carries a string `key`. This one may not: form
      // autofill and password managers announce themselves with a bare
      // `new Event('keydown')`, which has no `key` property at all, and reading
      // .indexOf off undefined threw on every filled-in login field. Nothing was
      // typed, so there is nothing to classify either way.
      if (typeof e.key !== 'string') return
      // Only keys that MOVE focus or act on it count. Typing into a field you
      // clicked should not turn the ring on underneath your cursor.
      if (e.metaKey || e.altKey || e.ctrlKey) return
      if (e.key === 'Tab' || e.key === 'Escape' || e.key === 'Enter' || e.key === ' ' ||
          e.key.indexOf('Arrow') === 0 || e.key === 'Home' || e.key === 'End' ||
          e.key === 'PageUp' || e.key === 'PageDown') {
        set('keyboard')
      }
    },
    true
  )
})()
