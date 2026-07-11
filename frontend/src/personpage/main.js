// Entry for the person-details page view (spec 035 Step 5a). Mounted by the thin
// Flask shell templates/person_details.html; the server-embedded payload
// (window.__PAGE_DATA__, the exact /api/me/details shape) gives first paint with
// no fetch, and window.__PAGE_CTX__ carries the routing state (user-profile vs
// admin flavor, canonical instrument list).
import { mount } from 'svelte'
import App from './App.svelte'

const target = document.getElementById('person-details-root')
if (target && window.__PAGE_DATA__) {
  mount(App, {
    target,
    props: {
      pageData: window.__PAGE_DATA__,
      ctx: window.__PAGE_CTX__ || {},
    },
  })
}
