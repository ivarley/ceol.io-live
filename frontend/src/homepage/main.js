// Entry for the home page (spec 052 §B8 Stage 4). Mounted by the thin Flask shell
// templates/home.html, from window.__PAGE_DATA__ — the exact GET /api/home body,
// built by serializers.build_home_payload, so first paint needs no fetch and the
// page and the API cannot drift.
//
// Signed out there is no payload and no mount: the anonymous hero is Jinja in the
// shell, and a visitor with no account never downloads this bundle.
import { mount } from 'svelte'
import './page.css'
import App from './App.svelte'

const pageData = window.__PAGE_DATA__
const target = document.getElementById('home-root')

if (target && pageData) {
  mount(App, { target, props: { payload: pageData } })
}
