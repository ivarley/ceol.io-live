// Entry for the recording segmenter (spec 050). Mounted by the thin Flask shell
// templates/recording_segmenter.html onto #segmenter-root, with the server-embedded
// payload (window.__PAGE_DATA__) passed as a prop so first paint needs no fetch.
import { mount } from 'svelte'
import App from './App.svelte'

const target = document.getElementById('segmenter-root')
if (target) {
  mount(App, {
    target,
    props: { pageData: window.__PAGE_DATA__ ?? null },
  })
}
