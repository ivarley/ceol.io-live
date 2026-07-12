import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 035 final migration: the /admin/people table (search, sort, add-person
// wizard), mounted by the thin Flask shell templates/admin_people.html below
// the Jinja admin breadcrumb/tab chrome.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/peopleadminpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/peopleadminpage/main.js'),
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
