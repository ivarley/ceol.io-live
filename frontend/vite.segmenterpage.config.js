import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 050: the recording segmenter, mounted by the thin Flask shell
// templates/recording_segmenter.html. Self-contained (canvas waveform + the
// night's tune log); shares nothing with the other page bundles.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/segmenterpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/segmenterpage/main.js'),
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
