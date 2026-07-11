import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 035 Step 3: the app-wide tune-detail sheet (the Svelte port of the legacy
// vanilla tune-detail modal, now deleted), loaded by base.html / live_logging.html /
// hamburger_menu.js as /static/tunesheet/sheet.js. Lib mode with fixed (no-hash)
// filenames, same pattern as the other page bundles. Styling stays in the shared
// static/css/tune_detail_modal.css (the component ships no CSS of its own).
export default defineConfig({
  // The kit Dialog ships scoped component CSS, but this bundle's page loads no
  // per-bundle stylesheet — inject component styles at runtime instead.
  plugins: [svelte({ compilerOptions: { css: 'injected' } })],
  build: {
    outDir: resolve(__dirname, '../static/tunesheet'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/tunesheet/main.js'),
      formats: ['es'],
      fileName: () => 'sheet.js',
    },
    rollupOptions: {
      output: {
        assetFileNames: 'sheet.[ext]',
      },
    },
  },
})
