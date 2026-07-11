// Entry for the My Tunes page view (spec 035 Step 2). Mounted by the thin Flask
// shell templates/my_tunes.html onto #my-tunes-root, with the server-embedded
// payload (window.__PAGE_DATA__) passed as a prop so first paint needs no fetch.
import { mount } from 'svelte'
// The add pane (AddTuneApp, bundled in as a child of App) styles itself with the
// same stylesheet the standalone /static/mytunes bundle uses.
import '../mytunes/mytunes-add.css'
import App from './App.svelte'

const target = document.getElementById('my-tunes-root')
if (target) {
  mount(App, {
    target,
    props: { pageData: window.__PAGE_DATA__ ?? null },
  })
}
