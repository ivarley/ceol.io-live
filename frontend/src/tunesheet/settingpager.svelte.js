// The settings pager: every written version of one tune, in thesession.org's order,
// with the notation of the one in view drawn ahead of you: the engine behind the
// tune drawer's staff (swipe / arrows page it in place).
//
// The list is the settings Ceol holds (the tune preview, one cheap local call) and
// then thesession.org's full list merged in (`backfill`). The backfill is a live call
// to thesession.org with no server-side cache, and the drawer opens on every tune tap
// across the site, so it is LAZY here: `ensureBackfill()` runs it once, when something
// asks for it (the first touch of the staff or the first step). A step past the end while the backfill is still in flight
// is kept and applied when the list grows.
//
// Paging has to feel instant, so the renders run ahead: the setting in view, then the
// next, then the one before (a swipe slides either neighbour on), then the one after
// next, one at a time, in the size (`kind`) being looked at. A setting we hold
// renders through the setting-image endpoint, which caches the PNG for everyone; one
// only thesession.org has renders ephemerally (it isn't ours until somebody picks it).
// Both share client.js's image registry, so nothing is drawn twice in a page.
//
// Runes in a .svelte.js module, as shared/abcfilter.svelte.js: each bundle compiles
// its own copy.
import { tunePreview, thesessionPreview, settingImage, renderRemoteAbc } from '../client.js'

const NO_SCOPE = {} // the preview endpoints' scope: none — the caller knows its own

export function createSettingPager({
  tuneId,
  tuneType = '',
  currentSettingId = null,
  kind = 'incipit',
  canBackfill = true, // thesession.org's list and the ephemeral render are sign-in gated
} = {}) {
  let settings = $state([]) // [{setting_id, key, abc, incipit_abc, incipit_image?, remote?}]
  let idx = $state(0)
  let loading = $state(true)
  let failed = $state(false)
  let backfilling = $state(false)
  let touched = $state(false) // has the user paged? (then a late backfill mustn't move them)
  let images = $state({}) // `${setting_id}:${kind}` -> base64, or false when it couldn't be drawn
  let current = $state(currentSettingId) // the layer's setting now: where the pager opens, the one marked
  let size = $state(kind) // 'incipit' | 'full' — the size being looked at, and warmed
  let backfillStarted = false
  let pendingStep = 0 // a step asked for past the end while more settings may be coming
  let loadSeq = 0
  let warmSeq = 0

  const key = (settingId, k) => `${settingId}:${k}`

  function jumpToCurrent() {
    if (current == null) return false
    const i = settings.findIndex((s) => s.setting_id === Number(current))
    if (i < 0) return false
    idx = i
    return true
  }

  // The settings we hold, at once. Resolves when they're in (or the load failed).
  async function load() {
    const seq = ++loadSeq
    settings = []
    idx = 0
    touched = false
    failed = false
    loading = true
    backfilling = false
    backfillStarted = false
    pendingStep = 0
    try {
      const d = await tunePreview(NO_SCOPE, tuneId)
      if (seq !== loadSeq) return
      // Seed the registry with any incipit the preview carried, so it needn't render.
      for (const s of d.settings || []) {
        if (s.incipit_image && !(key(s.setting_id, 'incipit') in images)) images[key(s.setting_id, 'incipit')] = s.incipit_image
      }
      settings = d.settings || []
      loading = false
      jumpToCurrent()
      warmAhead()
    } catch {
      if (seq !== loadSeq) return
      failed = true
      loading = false
    }
  }

  // thesession.org's full list, merged in setting order so "Setting 3 of 12" means the
  // same as it does there. Once per load; offline or thesession.org down, the settings
  // we hold simply stand.
  function ensureBackfill() {
    if (!canBackfill || backfillStarted || loading || failed) return
    backfillStarted = true
    backfill(loadSeq)
  }

  async function backfill(seq) {
    backfilling = true
    let ts
    try {
      ts = await thesessionPreview(NO_SCOPE, tuneId, true)
    } catch {
      if (seq === loadSeq) {
        backfilling = false
        pendingStep = 0
      }
      return
    }
    if (seq !== loadSeq) return
    backfilling = false
    const have = new Set(settings.map((s) => s.setting_id))
    const extra = (ts?.settings || []).filter((s) => !have.has(s.setting_id)).map((s) => ({ ...s, remote: true }))
    if (!extra.length) {
      pendingStep = 0
      return
    }
    const showing = settings[idx]?.setting_id
    settings = [...settings, ...extra].sort((a, b) => a.setting_id - b.setting_id)
    // The current setting may only just have arrived; otherwise stay on the one showing,
    // then honour a step asked for while the list was still growing.
    if (!(!touched && jumpToCurrent())) {
      const i = settings.findIndex((s) => s.setting_id === showing)
      if (i >= 0) idx = i
    }
    if (pendingStep) {
      const n = idx + pendingStep
      pendingStep = 0
      if (n >= 0 && n < settings.length) {
        idx = n
        touched = true // the user did page; the list was just late
      }
    }
    warmAhead()
  }

  // One step on, or back. Past the end while more may be coming, the step waits for
  // them; a step also starts the backfill, since paging is the ask for the whole list.
  function step(d) {
    if (loading || failed) return
    ensureBackfill()
    const n = idx + d
    if (n < 0 || n >= settings.length) {
      if (d > 0 && backfilling) pendingStep = d
      return
    }
    idx = n
    touched = true
    pendingStep = 0
    warmAhead()
  }

  function jumpTo(settingId) {
    const i = settings.findIndex((s) => s.setting_id === Number(settingId))
    if (i < 0) return false
    idx = i
    touched = true
    warmAhead()
    return true
  }

  function setSize(k) {
    if (size === k) return
    size = k
    warmAhead()
  }

  // The layer's setting changed (a save): the mark moves; the pager stays where it is.
  function setCurrent(settingId) {
    current = settingId
  }

  // One setting's notation in one size, through the shared registry.
  function warm(s, k) {
    if (!s || key(s.setting_id, k) in images) return Promise.resolve()
    const p = s.remote
      ? renderRemoteAbc(NO_SCOPE, `ts:${tuneId}:${s.setting_id}:${k}`, {
          abc: s.abc,
          key: s.key,
          tune_type: tuneType,
          kind: k,
        })
      : settingImage(NO_SCOPE, s.setting_id, k)
    return p.then((img) => {
      images[key(s.setting_id, k)] = img || false
    })
  }

  // The one in view first, then its neighbours (next, then before: both slide on under a
  // swipe), then the one after next, one at a time so the renderer works on what you'll
  // see soonest. Paging on starts a fresh run from the new place.
  function warmAhead() {
    const seq = ++warmSeq
    const i = idx
    const list = settings
    const k = size
    if (!list.length) return
    ;(async () => {
      await warm(list[i], k)
      for (const j of [i + 1, i - 1, i + 2]) {
        if (seq !== warmSeq) return
        await warm(list[j], k)
      }
    })()
  }

  // Whatever is still in flight lands on nothing.
  function dispose() {
    loadSeq++
    warmSeq++
  }

  return {
    get tuneId() {
      return tuneId
    },
    get settings() {
      return settings
    },
    get idx() {
      return idx
    },
    get setting() {
      return settings[idx] || null
    },
    get count() {
      return settings.length
    },
    get loading() {
      return loading
    },
    get failed() {
      return failed
    },
    get backfilling() {
      return backfilling
    },
    get touched() {
      return touched
    },
    get current() {
      return current
    },
    get size() {
      return size
    },
    // Is the setting in view the layer's?
    get isCurrent() {
      const s = settings[idx]
      return !!s && current != null && s.setting_id === Number(current)
    },
    // The image of a setting in a size: base64, false (undrawable), or undefined (not yet).
    image(settingId, k = size) {
      return images[key(settingId, k)]
    },
    load,
    ensureBackfill,
    step,
    jumpTo,
    setSize,
    setCurrent,
    dispose,
  }
}
