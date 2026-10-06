// Entry for the Places admin page (spec 055), mounted by templates/admin_places.html.
// window.__PAGE_DATA__ is serializers.build_admin_places_payload.
import { mount } from 'svelte'
import './page.css'
import App from './App.svelte'

const target = document.getElementById('admin-places-root')
if (target && window.__PAGE_DATA__) {
  mount(App, { target, props: { pageData: window.__PAGE_DATA__ } })
}
