import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 035 final migration: the /add-session wizard (thesession.org search/import,
// session-details review sheet, empty-session flow), mounted by the thin Flask
// shell templates/add_session.html.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/addsessionpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/addsessionpage/main.js'),
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
