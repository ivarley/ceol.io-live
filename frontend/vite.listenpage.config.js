import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 061 stage 3: Listen (/listen), the meter,
// mounted by the thin Flask shell templates/listen.html.
// Same lib-mode/no-hash pattern as the other page bundles.
export default defineConfig({
  // Component styles are injected at runtime; the
  // page's own page.css is emitted beside page.js.
  plugins: [svelte({ compilerOptions: { css: 'injected' } })],
  build: {
    outDir: resolve(__dirname, '../static/listenpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/listenpage/main.js'),
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
