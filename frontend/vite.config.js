import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 024 §H: a self-contained bundle Flask serves, isolated to this screen.
// Build to ../static/live with predictable filenames (no hash) so the thin Flask
// shell (templates/live_logging.html) can reference /static/live/app.js + app.css.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/live'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/main.js'),
      formats: ['es'],
      fileName: () => 'app.js',
    },
    rollupOptions: {
      output: {
        assetFileNames: 'app.[ext]',
      },
    },
  },
})
