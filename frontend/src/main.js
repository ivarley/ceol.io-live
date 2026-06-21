import { mount } from 'svelte'
import App from './App.svelte'
import './app.css'

// Config inlined by the Flask shell (templates/live_logging.html).
const config = window.__LIVE_CONFIG__ || {}

mount(App, {
  target: document.getElementById('app'),
  props: { config },
})
