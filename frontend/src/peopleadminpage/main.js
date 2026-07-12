// Entry for the /admin/people table view (spec 035 final migration). Mounted by
// the thin Flask shell templates/admin_people.html onto #admin-people-root
// (below the Jinja admin breadcrumb/tab chrome), with the server-embedded
// payload (window.__PAGE_DATA__, the exact GET /api/admin/people shape) passed
// as a prop so first paint needs no fetch.
import { mount } from 'svelte'
// Page styles travel with the bundle (emitted as static/peopleadminpage/page.css,
// linked by the shell's extra_css block).
import './page.css'
import App from './App.svelte'

const target = document.getElementById('admin-people-root')
if (target) {
  mount(App, {
    target,
    props: { pageData: window.__PAGE_DATA__ ?? null },
  })
}
