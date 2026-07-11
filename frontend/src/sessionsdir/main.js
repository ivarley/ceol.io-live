// Entry for the /sessions directory view (spec 035 Step 4a). Mounted by the thin
// Flask shell templates/sessions.html; the server-embedded payload
// (window.__PAGE_DATA__, the exact /api/sessions/with-today-status shape) gives
// first paint with no fetch.
import { mount } from 'svelte'
import App from './App.svelte'

const target = document.getElementById('sessions-root')
if (target) {
  mount(App, {
    target,
    props: {
      pageData: window.__PAGE_DATA__ ?? null,
      isLoggedIn: !!window.__IS_LOGGED_IN__,
    },
  })
}
