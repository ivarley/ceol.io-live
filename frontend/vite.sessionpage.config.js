import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 035 Step 4b: the session-detail page view, mounted by the thin Flask
// shell templates/session_detail.html. Same lib-mode/no-hash pattern as the
// other page bundles.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/sessionpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/sessionpage/main.js'),
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
