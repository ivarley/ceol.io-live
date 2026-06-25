import { mount } from 'svelte'
import App from './App.svelte'
import './app.css'

// Config inlined by the Flask shell (templates/live_logging.html).
const config = window.__LIVE_CONFIG__ || {}

// Register the live-screen service worker (scope /live/) so the shell loads
// offline (spec 024 §H). Best-effort: failure just means no offline reload.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/live/sw.js').catch(() => {})
    // Prime the cache with THIS page so an offline reload always has a shell to
    // serve (the navigation URL is dynamic, so it can't be precached at install).
    const primeShell = () => navigator.serviceWorker.controller?.postMessage({ type: 'cache-shell', url: location.href })
    navigator.serviceWorker.ready.then(primeShell)
    navigator.serviceWorker.addEventListener('controllerchange', primeShell)
  })
}

mount(App, {
  target: document.getElementById('app'),
  props: { config },
})
