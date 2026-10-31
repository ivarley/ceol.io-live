import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 061 stage 2: the listen test page (/listen/test),
// mounted by the thin Flask shell templates/listen_test.html.
// Same lib-mode/no-hash pattern as the other page bundles.
export default defineConfig({
  // Component styles are injected at runtime; the
  // page's own page.css is emitted beside page.js.
  plugins: [svelte({ compilerOptions: { css: 'injected' } })],
  build: {
    outDir: resolve(__dirname, '../static/listentest'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/listentest/main.js'),
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
