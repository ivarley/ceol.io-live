// Entry for the festival picker (spec 056), mounted by templates/festival.html on
// /sessions/<festival-slug> when no year is near. window.__PAGE_DATA__ is
// serializers.build_festival_payload.
import { mount } from 'svelte'
import './page.css'
import App from './App.svelte'

const target = document.getElementById('festival-root')
if (target && window.__PAGE_DATA__) {
  target.textContent = ''
  mount(App, { target, props: { pageData: window.__PAGE_DATA__ } })
}
