// App-wide connection / offline-sync indicator (a tappable dot + popup in the header),
// kept consistent with the live logger's offline/reconnecting model.
//
// Why a heartbeat: navigator.onLine and the 'online' event are unreliable (onLine can
// read true while actually offline, and 'online' may not fire), so we can't rely on
// them to know we're back. When there's unsynced work (or we believe we're offline) we
// POLL a tiny same-origin probe that the service worker does NOT cache, and act on the
// real result — flushing the My-Tunes op-queue as soon as we're truly reconnected.
//
// States (the whole control is hidden when 'online' and idle):
//   offline    - orange dot; disconnected (queued changes will sync later)
//   syncing    - orange pulsing dot; reconnected, replaying the queue
//   caught-up  - green dot for a few seconds after a successful sync, then hides
//
// Tapping the dot opens a popup: "You're offline", how long, and how many pending changes.
(function (window, document) {
  'use strict'
  if (window.CeolConnection) return

  var PROBE = '/sw.js' // network-passthrough (not SW-cached) -> reflects real connectivity
  var POLL_MS = 6000
  var CAUGHT_UP_MS = 3500

  var state = 'online'
  var offlineSince = null
  var pollTimer = null
  var caughtUpTimer = null
  var popupTimer = null
  var els = null

  function dom() {
    if (!els) {
      els = {
        wrap: document.getElementById('conn-status'),
        dot: document.getElementById('conn-status-dot'),
        btn: document.getElementById('conn-status-btn'),
        popup: document.getElementById('conn-status-popup'),
        title: document.getElementById('conn-status-title'),
        detail: document.getElementById('conn-status-detail'),
      }
    }
    return els
  }

  function fmtDuration(ms) {
    var s = Math.max(0, Math.round(ms / 1000))
    if (s < 60) return s + 's'
    var m = Math.round(s / 60)
    if (m < 60) return m + 'm'
    var h = Math.floor(m / 60)
    return h + 'h ' + (m % 60) + 'm'
  }

  function hasPending() {
    if (!window.MyTunesOffline || !window.MyTunesOffline.pending) return Promise.resolve(0)
    return window.MyTunesOffline.pending().then(function (o) { return (o || []).length }).catch(function () { return 0 })
  }

  function render() {
    var d = dom()
    if (!d.dot || !d.wrap) return
    d.dot.className = 'conn-dot conn-' + state
    d.wrap.style.display = state === 'online' ? 'none' : 'inline-flex'
    if (state === 'online' && d.popup) d.popup.classList.remove('show') // hide popup when control hides
    if (d.popup && d.popup.classList.contains('show')) updatePopup()
  }

  // Fill the popup for the current state (pending count is async).
  function updatePopup() {
    var d = dom()
    if (!d.title || !d.detail) return
    if (state === 'syncing') {
      d.title.textContent = 'Reconnected'
      d.detail.textContent = 'Syncing your changes...'
      return
    }
    if (state === 'caught-up') {
      d.title.textContent = 'All changes synced'
      d.detail.textContent = ''
      return
    }
    // offline
    d.title.textContent = "You're offline"
    var since = offlineSince ? 'Offline for ' + fmtDuration(Date.now() - offlineSince) : 'Offline'
    hasPending().then(function (n) {
      var pend = n > 0 ? n + ' change' + (n === 1 ? '' : 's') + ' waiting to sync' : 'No unsynced changes'
      d.detail.textContent = since + ' - ' + pend
    })
  }

  // offlineSince is persisted in localStorage so "Offline for Xm" accumulates across
  // page navigations (each page is a fresh script load), not just the current page.
  var STORE_KEY = 'ceol_offline_since'
  function readOfflineSince() {
    try { var v = window.localStorage.getItem(STORE_KEY); return v ? parseInt(v, 10) : null } catch (e) { return null }
  }
  function writeOfflineSince(v) {
    try { if (v == null) window.localStorage.removeItem(STORE_KEY); else window.localStorage.setItem(STORE_KEY, String(v)) } catch (e) {}
  }

  function setState(s) {
    if (s === 'offline') {
      if (!offlineSince) offlineSince = readOfflineSince() || Date.now()
      writeOfflineSince(offlineSince)
    } else {
      // Reconnected (syncing/caught-up/online): the offline period is over.
      offlineSince = null
      writeOfflineSince(null)
    }
    if (s === state) { render(); return }
    state = s
    render()
  }

  function probe() {
    return fetch(PROBE, { method: 'HEAD', cache: 'no-store' }).then(function () { return true }).catch(function () { return false })
  }

  function startPolling() { if (!pollTimer) pollTimer = setInterval(tick, POLL_MS) }
  function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

  function tick() {
    probe().then(function (online) {
      if (!online) {
        if (state !== 'offline' && state !== 'caught-up') setState('offline')
        else render() // refresh duration/pending
        startPolling()
        return
      }
      hasPending().then(function (n) {
        if (n > 0) {
          setState('syncing')
          startPolling()
          if (window.MyTunesOffline) window.MyTunesOffline.flush() // -> 'mytunes-synced' on drain
        } else {
          stopPolling()
          if (state === 'offline' || state === 'syncing') setState('online')
        }
      })
    })
  }

  function showCaughtUp() {
    stopPolling()
    setState('caught-up')
    if (caughtUpTimer) clearTimeout(caughtUpTimer)
    caughtUpTimer = setTimeout(function () { if (state === 'caught-up') setState('online') }, CAUGHT_UP_MS)
  }

  function togglePopup() {
    var d = dom()
    if (!d.popup) return
    var willShow = !d.popup.classList.contains('show')
    d.popup.classList.toggle('show', willShow)
    if (willShow) {
      updatePopup()
      // Keep the "offline for Xm" duration fresh while open.
      if (popupTimer) clearInterval(popupTimer)
      popupTimer = setInterval(updatePopup, 15000)
    } else if (popupTimer) {
      clearInterval(popupTimer); popupTimer = null
    }
  }

  function wire() {
    var d = dom()
    if (d.btn) {
      d.btn.addEventListener('click', function (e) { e.stopPropagation(); togglePopup() })
    }
    document.addEventListener('click', function (e) {
      if (d.popup && d.popup.classList.contains('show') && !e.target.closest('#conn-status')) {
        d.popup.classList.remove('show')
        if (popupTimer) { clearInterval(popupTimer); popupTimer = null }
      }
    })
  }

  // The op-queue tells us when it queued (went offline) and when it drained (synced).
  window.addEventListener('mytunes-queued', function () { setState('offline'); startPolling() })
  window.addEventListener('mytunes-synced', function () { showCaughtUp() })
  // Browser hints (treated as triggers to verify, never as ground truth).
  window.addEventListener('offline', function () { setState('offline'); startPolling() })
  window.addEventListener('online', function () { tick() })

  function init() {
    wire()
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      setState('offline')
      startPolling()
    }
    // Always verify real connectivity on load — navigator.onLine lies, so a probe is the
    // only reliable signal. Keeps the offline dot showing on every page while disconnected.
    tick()
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init)
  else init()

  window.CeolConnection = { refresh: tick }
})(window, document)
