// Entry for the session-detail page view (spec 035 Step 4b). Mounted by the thin
// Flask shell templates/session_detail.html; the server-embedded payload
// (window.__PAGE_DATA__, the exact /api/sessions/<path>/detail shape) gives
// first paint with no fetch, and window.__PAGE_CTX__ carries the routing state
// (active tab, deep-linked tune/person ids, current user, instrument list).
import { mount } from 'svelte'
// The add pane (SessionTuneAddApp, bundled in as a child of App) styles itself
// with the same stylesheet the My Tunes page bundle uses.
import '../mytunes/mytunes-add.css'
// Page styles (formerly the shell's <style> block) travel with the bundle;
// imported after mytunes-add.css to preserve the old document cascade order.
// Both are emitted into static/sessionpage/page.css.
import './page.css'
import App from './App.svelte'

const target = document.getElementById('session-detail-root')
if (target && window.__PAGE_DATA__) {
  mount(App, {
    target,
    props: {
      pageData: window.__PAGE_DATA__,
      ctx: window.__PAGE_CTX__ || {},
    },
  })
}
