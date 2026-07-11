// Entry for the session-admin page view (spec 035 Step 5b). Mounted by the thin
// Flask shell templates/session_admin.html; the server-embedded payload
// (window.__PAGE_DATA__, the exact /api/admin/sessions/<path>/admin-detail
// shape) gives first paint with no fetch, and window.__PAGE_CTX__ carries the
// routing state (active tab, session path, system-admin flag).
import { mount } from 'svelte'
// Page styles travel with the bundle (emitted as static/sessionadminpage/page.css,
// linked by the shell's extra_css block) so the components stay portable.
import './page.css'
import App from './App.svelte'

const target = document.getElementById('session-admin-root')
if (target && window.__PAGE_DATA__) {
  mount(App, {
    target,
    props: {
      pageData: window.__PAGE_DATA__,
      ctx: window.__PAGE_CTX__ || {},
    },
  })
}
