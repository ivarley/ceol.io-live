import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Add-to-My-Tunes pane bundle, mounted standalone on /my-tunes. Built separately from
// the live app (vite.config.js) so my_tunes.html loads only this pane's CSS — the live
// app.css can't be shared (it locks body scroll and hardcodes the dark palette).
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/mytunes'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/mytunes/main.js'),
      formats: ['es'],
      fileName: () => 'add.js',
    },
    rollupOptions: {
      output: {
        assetFileNames: 'add.[ext]',
      },
    },
  },
})
