// Entry for the listen test page (spec 061 stage 2), mounted by
// templates/listen_test.html. It embeds no payload: the page asks
// /api/listen/connection for where and how to connect when listening starts.
import { mount } from 'svelte'
import './page.css'
import App from './App.svelte'

const target = document.getElementById('listen-test-root')
if (target) mount(App, { target })
