import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 055: the Places admin page (/admin/places),
// mounted by the thin Flask shell templates/admin_places.html.
// Same lib-mode/no-hash pattern as the other page bundles.
export default defineConfig({
  // Component styles (the kit Sheet, the copy form) are injected at runtime; the
  // page's own page.css is emitted beside page.js.
  plugins: [svelte({ compilerOptions: { css: 'injected' } })],
  build: {
    outDir: resolve(__dirname, '../static/placesadminpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/placesadminpage/main.js'),
      formats: ['es'],
      fileName: () => 'page.js',
    },
    rollupOptions: {
      output: {
        assetFileNames: 'page.[ext]',
      },
    },
  },
})
