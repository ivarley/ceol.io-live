/* Push/pop slide between pages on a phone (spec 052 §B8 Stage 6).
 *
 * /sessions -> /sessions/<path> slides in from the right; going back up slides it
 * out again. Built on cross-document View Transitions (css/page_transitions.css
 * turns them on), not a client-side router: every page is still a full server round
 * trip, and a browser without the feature just navigates as it always did.
 *
 * The direction comes from the URL hierarchy rather than from history, so it is the
 * same whichever way you got there: going to a path UNDER the one you are on is a
 * push, going to one ABOVE it is a pop, and anything else — above all a tab-bar
 * switch — gets no transition at all, which is how iOS treats a tab change.
 *
 * This must run before the new page's first frame, which is when `pagereveal` fires,
 * so it is loaded in <head> and not deferred. Browsers without the Navigation API
 * (`navigation.activation`) cannot say where the navigation came from; they skip
 * the transition rather than guess.
 */
(function () {
  'use strict'

  // The path of the SCREEN a URL shows. A session page's tab rides in its URL
  // (/sessions/x/logs) but is the same screen, so a log opened from the Logs tab
  // (/sessions/x/2026-09-20) is still under it.
  function screenPath(pathname) {
    var p = pathname.replace(/\/+$/, '')
    if (p.indexOf('/sessions/') === 0) p = p.replace(/\/(tunes|people|logs)$/, '')
    return p
  }

  function isUnder(child, parent) {
    return child.indexOf(parent + '/') === 0
  }

  // 'push' | 'pop' | null. Home ('/') is a tab, not the parent of every page, so it
  // never slides.
  function slideDirection(fromUrl, toUrl) {
    if (!fromUrl || !toUrl) return null
    var from = new URL(fromUrl)
    var to = new URL(toUrl)
    if (from.origin !== to.origin) return null
    var a = screenPath(from.pathname)
    var b = screenPath(to.pathname)
    if (a === '' || b === '') return null
    if (isUnder(b, a)) return 'push'
    if (isUnder(a, b)) return 'pop'
    return null
  }

  window.CeolPageTransitions = { slideDirection: slideDirection }

  window.addEventListener('pagereveal', function (e) {
    // Null unless css/page_transitions.css opted this navigation in (phone width,
    // motion allowed, same-origin).
    if (!e.viewTransition) return
    var act = window.navigation && window.navigation.activation
    var dir = act && act.from && act.entry ? slideDirection(act.from.url, act.entry.url) : null
    if (!dir) {
      e.viewTransition.skipTransition()
      return
    }
    var root = document.documentElement
    root.setAttribute('data-slide', dir)
    e.viewTransition.finished.finally(function () {
      root.removeAttribute('data-slide')
    })
  })
})()
