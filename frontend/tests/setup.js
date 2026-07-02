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
