import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// The export chooser (/export): Profile → Export my data → pick what to export,
// mounted by the thin Flask shell templates/export.html. Same
// lib-mode/no-hash pattern as the other page bundles.
export default defineConfig({
  // The kit Dialog ships scoped component CSS, but this bundle's page loads no
  // per-bundle stylesheet — inject component styles at runtime instead.
  plugins: [svelte({ compilerOptions: { css: 'injected' } })],
  build: {
    outDir: resolve(__dirname, '../static/exportpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/exportpage/main.js'),
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
