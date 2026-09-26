import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 052 §B8 Stage 4: the home page view, mounted by the thin Flask shell
// templates/home.html. Same lib-mode/no-hash pattern as the other page bundles.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/homepage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/homepage/main.js'),
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
