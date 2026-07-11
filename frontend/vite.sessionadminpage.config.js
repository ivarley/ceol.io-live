import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'path'

// Spec 035 Step 5b: the session-admin page view (/admin/sessions/<path> and its
// tab wrapper routes), mounted by the thin Flask shell templates/session_admin.html.
// Same lib-mode/no-hash pattern as the other page bundles.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, '../static/sessionadminpage'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/sessionadminpage/main.js'),
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
