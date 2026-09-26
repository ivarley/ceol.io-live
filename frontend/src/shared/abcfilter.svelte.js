// Notation matching for the three screens that filter a list they have ALREADY loaded:
// My Tunes, a session's Tunes tab, the admin session-tunes tab.
//
// Those filters run in the browser against data the page already holds, which works for
// names and cannot work for notation — the full ABC is far too large to ship with a page
// (a 300-tune list would gain 150-250KB). So the client posts the ids it is showing and
// gets back the subset whose notation matches, then unions that into the same filter
// pass. One mechanism, three call sites.
//
// Runes in a .svelte.js module, same as mytunes/pane.svelte.js: each bundle compiles its
// own copy, which is the established pattern here (see lib/index.js).
import { abcNeedle } from './abcquery.js'

export function createAbcMatcher(endpoint = '/api/tunes/abc-filter') {
  let ids = $state(new Set())
  let seq = 0
  let lastKey = null
  let timer = null

  const clear = () => {
    if (ids.size) ids = new Set()
  }

  const cancel = () => {
    seq++
    lastKey = null
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return {
    get ids() {
      return ids
    },

    // `getTuneIds` is a THUNK so the visible-id list is read only when a request actually
    // fires — otherwise every unrelated list mutation (a heard-count bump, a status
    // cycle) would re-trigger the effect that calls this. `listSize` is the caller's
    // tracked signal that the list ITSELF changed: these pages load their tunes after
    // mount, so a deep-linked ?search= runs before there is anything to match against,
    // and without it that first query would never be retried.
    update(rawQuery, getTuneIds, listSize = 0) {
      const needle = abcNeedle(rawQuery)
      // Ordinary name typing costs nothing: no request, and the sync filter is left to
      // behave exactly as it did before notation search existed.
      if (!needle) {
        cancel()
        clear()
        return
      }
      const key = `${needle}#${listSize}`
      if (key === lastKey) return
      // Offline, and on any failure below, we leave `ids` empty: the surface silently
      // degrades to name-only rather than showing an error for a filter keystroke. Note
      // lastKey stays unset, so coming back online and touching the box retries.
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        cancel()
        clear()
        return
      }
      lastKey = key
      const mine = ++seq
      if (timer) clearTimeout(timer)
      timer = setTimeout(async () => {
        timer = null
        const tuneIds = getTuneIds()
        if (!tuneIds.length) {
          lastKey = null // nothing to match yet; retry when the list arrives
          clear()
          return
        }
        try {
          const res = await fetch(endpoint, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q: rawQuery, tune_ids: tuneIds }),
          })
          const json = await res.json()
          if (mine !== seq) return // a newer query has since been issued
          ids = new Set(res.ok && json && json.success ? json.tune_ids : [])
        } catch (e) {
          if (mine !== seq) return
          lastKey = null // a failed lookup shouldn't stick; let the next keystroke retry
          clear()
        }
      }, 150) // a small stagger on top of the SearchField's own 300ms debounce
    },

    reset() {
      cancel()
      clear()
    },
  }
}
