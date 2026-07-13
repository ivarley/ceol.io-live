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
import SessionAbout from './SessionAbout.svelte'
import SessionRole from './SessionRole.svelte'
import SessionJoin from './SessionJoin.svelte'

const pageData = window.__PAGE_DATA__
const ctx = window.__PAGE_CTX__ || {}

const target = document.getElementById('session-detail-root')
if (target && pageData) {
  mount(App, { target, props: { pageData, ctx } })
}

// Spec 034: the role badge and the join prompt live in the page header, above the tab
// interface, so they mount separately. They were the last two Jinja holdouts on this page
// (App.svelte used to reach into the shell DOM to wire the join link).
if (pageData) {
  const permissions = { ...pageData.permissions, person_id: ctx.currentUserPersonId }

  // The shell server-renders the description inside this root (no flash of missing text);
  // we drop that copy and let SessionAbout own it, clamped to two lines with a toggle.
  const aboutTarget = document.getElementById('session-about-root')
  if (aboutTarget && pageData.session.comments) {
    aboutTarget.textContent = ''
    mount(SessionAbout, { target: aboutTarget, props: { comments: pageData.session.comments } })
  }

  const roleTarget = document.getElementById('session-role-root')
  if (roleTarget && permissions.is_logged_in && permissions.is_session_member) {
    mount(SessionRole, {
      target: roleTarget,
      props: { sessionPath: pageData.session.path, permissions },
    })
  }

  const joinTarget = document.getElementById('session-join-root')
  if (joinTarget && permissions.is_logged_in && !permissions.is_session_member) {
    mount(SessionJoin, { target: joinTarget, props: { sessionPath: pageData.session.path } })
  }
}
