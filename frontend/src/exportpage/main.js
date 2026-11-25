// Entry for the export chooser (/export): Profile → Export my data. Mounted by the
// thin Flask shell templates/export.html; the server-embedded payload
// (window.__PAGE_DATA__: your sessions, and every session) gives first paint with no
// fetch. The chooser only picks WHAT to export; the page you land on does the rest.
import { mount } from 'svelte'
import './page.css'
import App from './App.svelte'

const target = document.getElementById('export-root')
if (target) {
  mount(App, {
    target,
    props: { pageData: window.__PAGE_DATA__ ?? null },
  })
}
