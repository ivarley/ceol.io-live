import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 035 Step 2: the full My Tunes page view (list, filters, cards), mounted by the
// thin Flask shell templates/my_tunes.html. Separate from vite.mytunes.config.js (the
// add-pane bundle shared with the session-tunes page) and from the live app bundle,
// whose app.css can't be shared (locks body scroll, hardcodes the dark palette).
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/mytunespage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/mytunespage/main.js'),
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
