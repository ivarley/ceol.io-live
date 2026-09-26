// Global test setup for the live-logging frontend suite.
//   - fake-indexeddb/auto polyfills the global `indexedDB` so offline.js runs in jsdom.
//   - @testing-library/jest-dom adds DOM matchers (toBeInTheDocument, etc.) for
//     the Layer-3 component tests.
import 'fake-indexeddb/auto'
import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement ResizeObserver (App.svelte observes the header height).
// A no-op stub is enough for component tests that don't assert on layout.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

// jsdom doesn't implement Element.scrollTo (App.svelte scrolls the log to the bottom
// on entering edit mode, in a double-rAF that can fire after a test finishes and
// surface as an unhandled error). A no-op is enough — nothing asserts scroll state.
if (typeof Element !== 'undefined' && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = () => {}
}

// jsdom doesn't implement the Web Animations API. Svelte's transitions call
// element.animate(), which throws from inside a rAF callback after the test that
// mounted the component has finished — so it lands as an unhandled error rather
// than a failure, and turns a green suite red with no failing test to point at.
//
// The stub returns just enough of an Animation for a caller to cancel or await it.
// Nothing asserts on animation, only that mounting and unmounting do not throw.
if (typeof Element !== 'undefined' && !Element.prototype.animate) {
  Element.prototype.animate = function () {
    const done = Promise.resolve()
    return {
      cancel() {},
      finish() {},
      pause() {},
      play() {},
      reverse() {},
      currentTime: 0,
      playState: 'finished',
      finished: done,
      onfinish: null,
      oncancel: null,
      addEventListener() {},
      removeEventListener() {},
    }
  }
}
