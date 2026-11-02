// Entry for Listen (spec 061 stage 3), mounted by templates/listen.html from
// window.__PAGE_DATA__ (serializers.build_listen_payload): the context the page was
// opened from, if any. Where to listen comes from /api/listen/connection at Start.
import { mount } from 'svelte'
import './page.css'
import App from './App.svelte'

const target = document.getElementById('listen-root')
if (target) mount(App, { target, props: { payload: window.__PAGE_DATA__ || {} } })
