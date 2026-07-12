// Entry for the /add-session wizard (spec 035 final migration). Mounted by the
// thin Flask shell templates/add_session.html onto #add-session-root, with the
// server-embedded payload (window.__PAGE_DATA__, the exact GET /api/add-session
// shape) passed as a prop so first paint needs no fetch.
import { mount } from 'svelte'
// Page styles travel with the bundle (emitted as static/addsessionpage/page.css,
// linked by the shell's extra_css block).
import './page.css'
import App from './App.svelte'

const target = document.getElementById('add-session-root')
if (target) {
  mount(App, {
    target,
    props: { pageData: window.__PAGE_DATA__ ?? null },
  })
}
