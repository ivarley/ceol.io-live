import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 056: the festival picker (/sessions/<festival-slug> when no year is near),
// mounted by the thin Flask shell templates/festival.html.
// Same lib-mode/no-hash pattern as the other page bundles.
export default defineConfig({
  // Component styles (the kit Sheet, the copy form) are injected at runtime; the
  // page's own page.css is emitted beside page.js.
  plugins: [svelte({ compilerOptions: { css: 'injected' } })],
  build: {
    outDir: resolve(__dirname, '../static/festivalpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/festivalpage/main.js'),
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
