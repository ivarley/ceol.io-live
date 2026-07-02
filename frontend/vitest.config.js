import { defineConfig } from 'vitest/config'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { svelteTesting } from '@testing-library/svelte/vite'

// Test config for the live-logging bundle. Kept separate from vite.config.js (which
// is a lib build) so `vitest` never inherits the library rollup options. jsdom gives
// component tests (Layer 3) a DOM; pure-logic tests (Layer 2) ignore it. svelteTesting()
// sets the `browser` export condition (so Svelte's client mount is used, not the SSR
// build) and auto-cleans mounted components between tests.
export default defineConfig({
  plugins: [svelte({ hot: false }), svelteTesting()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    include: ['tests/**/*.test.js'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.js'],
      reporter: ['text', 'html'],
    },
  },
})
