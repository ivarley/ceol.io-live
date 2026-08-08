<script>
  import { onMount, onDestroy, untrack, tick } from 'svelte'
  import { fly } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { SvelteMap, SvelteSet } from 'svelte/reactivity'
  import { bootstrap, vocabulary, sendOp, sendTyping, liveMatch, livePeople, deepSearch, fetchIncipit, openStream, probeServers, tuneDetail, myTunesList, myTunesOp, instanceAudio } from './client.js'
  import TuneSearch from './TuneSearch.svelte'
  import { Dialog, PersonPicker, Sheet } from './lib/index.js'
  import SidePane from './SidePane.svelte'
  import RecordingsModal from './RecordingsModal.svelte'
  import { queuePut, queueAll, queueDelete, snapshotPut, snapshotGet, matchCachePut, matchCacheGet } from './offline.js'
  import { generateAppend, generateBetween } from './fracindex.js'
  import {
    computeOrdered, segmentByBreaks, setsOf, tunesOf, pluralType, setLabel,
    maxPos, cursorPos, remapAnchors, normName, normAbc, stripThe,
    openSetMergeTarget, mergeStable, parseThesessionId, parseThesessionSettingId,
    computeCursorSlots, seamKeyFor, seamActionFor,
    rememberInHistory, historyStep, nextTs,
  } from './logstate.js'
  import {
    dragBlock, dropTargets, optimisticMove,
    serializeClipboard, parseClipboard, rangeBetween, selectableIds,
  } from './selection.js'
  import { listStatus, statusClass, planStatusOps, applyStatusLocally, NOT_ON_LIST } from './mylist.js'
  import { instanceTimeLabel } from './shared/format.js'
  import { resolveSegments, playbackStep, formatClock } from './shared/segments.js'

  let { config } = $props()

  // Canonical records keyed by id (tunes + break rows), applied idempotently.
  // SvelteMap (not a plain Map) so .set/.delete are reactive in Svelte 5.
  const byId = new SvelteMap()
  // op_id -> {tempId, name, op_type, payload, status, ts}. status 'sending' = online
  // optimistic in-flight (§A2); 'queued' = offline, persisted to IndexedDB (§G).
  const pending = new SvelteMap()
  // op_ids that fully resolved (settled, rejected, cancelled, or echoed via SSE).
  // The IndexedDB delete in dropPending is async, so a reconnect's hydrateQueue can
  // read the store before it commits — this set stops it resurrecting a finished op.
  const resolvedOps = new Set()
  function dropPending(op_id) {
    resolvedOps.add(op_id)
    pending.delete(op_id)
    return queueDelete(op_id)
  }
  // temp record id ("temp-<op_id>") -> real server id, learned as ops settle. Lets a
  // queued op whose anchor (after/before/record_id) points at a still-temp record be
  // remapped to the real id at send time, so offline mid-set inserts don't send
  // "temp-..." to the server (#5b).
  const tempToReal = new Map()
  const flashing = new SvelteMap() // record id -> {kind:'mine'|'remote'|'merge', color, tok} (§39/§E)
  let flashSeq = 0
  // "Likely next tune": anchor tune_id -> {tune_id, name, tune_type} of the successor that
  // follows it within a set >50% of the time at this session (precomputed server-side and
  // carried on each vocab entry's `next`). SvelteMap so the suggestion derived recomputes
  // when the background vocabulary load fills it in.
  const nextByTuneId = new SvelteMap()
  // Anchor->next associations the user has dismissed (the ✕ on the suggestion row) this
  // session. In-memory only, never persisted; keyed "<anchorTuneId>-><nextTuneId>" so a
  // dismissal only silences that one pairing. SvelteSet so nextSuggestion recomputes on add.
  const dismissedNext = new SvelteSet()
  const nextAssocKey = (anchorId, nextId) => `${anchorId}->${nextId}`
  let sseStatus = $state('connecting') // raw SSE state: connecting | live | reconnecting | error
  let loaded = $state(false) // first bootstrap has populated records — gates the loading skeleton vs "no tunes yet"
  let online = $state(typeof navigator === 'undefined' ? true : navigator.onLine)
  let reachable = $state(true) // have we reached the server recently? (navigator.onLine lies)
  // One source of truth for the pill + banner so they never disagree:
  //   live           - stream is up
  //   offline        - browser offline, OR bootstrap failed, OR reconnect timed out
  //   reconnecting   - a transient stream blip we're still hopeful about
  const displayStatus = $derived(
    !online || !reachable ? 'offline' : sseStatus === 'live' ? 'live' : 'reconnecting'
  )

  // --- Connection-dot popover (tap the dot for detail) -----------------------
  let connPopup = $state(false)
  let lastEventAt = $state(0) // last byte observed on the stream (op/presence/typing/ping/open)
  let offlineSince = $state(0) // when displayStatus first went offline (this page load)
  let connNow = $state(0) // ticks while the popover is open so durations render live
  // Active reachability probe (client.js probeServers), refreshed while the popover is
  // open and the stream isn't live. The app and the streaming sidecar fail
  // INDEPENDENTLY — locally a localhost vs 127.0.0.1 mismatch in streamingBaseUrl kills
  // only the stream — so the popover names which one is unreachable.
  let connProbe = $state(null) // {app: bool, stream: bool} | null while first probe runs
  const streamHost = (() => {
    try { return new URL(config.streamingBaseUrl, location.href).host } catch { return config.streamingBaseUrl }
  })()
  // The classic local-dev trap: page on localhost, stream on 127.0.0.1 (or vice versa).
  // The sidecar responds to the probe but authenticates via the Flask-Login cookie,
  // which is HOST-scoped — those are different hosts, so the SSE request 401s forever.
  // Only flagged when BOTH hosts are loopback so it can never misfire in production
  // (where the stream legitimately lives on a different host with domain-wide cookies).
  const streamHostMismatch = (() => {
    const loop = (h) => h === 'localhost' || h === '127.0.0.1'
    try {
      const sh = new URL(config.streamingBaseUrl, location.href).hostname
      return loop(location.hostname) && loop(sh) && sh !== location.hostname
    } catch { return false }
  })()
  // Clock starts when the stream stops being live (not when we finally declare
  // 'offline'): in the sidecar-down case displayStatus oscillates offline->reconnecting
  // every retry cycle, and anchoring on 'offline' would reset the duration each time.
  $effect(() => {
    if (displayStatus === 'live') offlineSince = 0
    else if (!offlineSince) offlineSince = Date.now()
  })
  $effect(() => {
    if (!connPopup) return
    connNow = Date.now()
    const tick = setInterval(() => (connNow = Date.now()), 1000)
    return () => clearInterval(tick)
  })
  $effect(() => {
    if (!connPopup || displayStatus === 'live') { connProbe = null; return }
    let stale = false
    const run = () => probeServers(config).then((r) => { if (!stale) connProbe = r })
    run()
    const timer = setInterval(run, 5000)
    return () => { stale = true; clearInterval(timer) }
  })
  function fmtDur(ms) {
    const s = Math.max(0, Math.round(ms / 1000))
    if (s < 60) return `${s}s`
    const m = Math.round(s / 60)
    if (m < 60) return `${m}m`
    return `${Math.floor(m / 60)}h ${m % 60}m`
  }
  const connTitle = $derived(
    displayStatus === 'live' ? 'Connected'
      // "offline" is the dot's catch-all for can't-connect, but if the probe proves the
      // app server IS reachable the honest headline is stream trouble, not "offline".
      : displayStatus === 'offline' ? (connProbe?.app ? 'Connection trouble' : "You're offline")
      : sseStatus === 'connecting' ? 'Connecting…' : 'Reconnecting…'
  )

  // "reconnecting" is short-lived: if the stream doesn't come back within a few
  // seconds, declare offline (covers reload-while-offline, where navigator.onLine
  // can read true and no `offline` event fires, and server-down with network up).
  let reconnectTimer = null
  function noteSse(s) {
    if (s === 'live') {
      reachable = true
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
    } else {
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => { reconnectTimer = null; reachable = false }, 8000)
      }
      // Safety net: any not-live stream state keeps a full-reconnect poll pending,
      // so no failure mode (EventSource permanently closed on a non-200, a stalled
      // reconnect, a wedged connect()) can strand us with nothing left to retry.
      scheduleReconnect()
    }
  }

  // When we can't reach the server, don't keep an EventSource hammering every ~3s;
  // slow-poll a full reconnect instead. navigator.onLine is unreliable, so we can't
  // rely solely on the 'online' event to know when we're back.
  let reconnectPoll = null
  function scheduleReconnect() {
    if (reconnectPoll) return
    reconnectPoll = setTimeout(() => {
      reconnectPoll = null
      if (sseStatus !== 'live') connect() // the stream recovered on its own — stand down
    }, 10000)
  }
  // Wide-screen two-pane layout (spec 028): ≥900px turns <main> into a grid with a
  // persistent right pane (suggestion + search). Below that, the mobile layout is untouched
  // and the pane never mounts.
  let winW = $state(typeof window === 'undefined' ? 0 : window.innerWidth)
  const wide = $derived(winW >= 900)
  let input = $state('')
  let error = $state('')
  let notice = $state('')
  let person = $state(untrack(() => config.currentPerson) || {}) // initial fallback; bootstrap overwrites it
  // Signed out: this screen is the PUBLIC session-instance page, rendered read-only.
  // No composer, no edit affordances, and no people anywhere — the server already
  // scrubs people from the bootstrap and the stream, so this is presentation only,
  // not the guard. `mode` can never leave 'view' (see setMode).
  const readOnly = untrack(() => config.canEdit) === false
  let roster = $state([]) // who's connected right now (ephemeral presence, §F)
  let typers = $state([]) // who's currently composing (ephemeral typing, §F)
  let activities = $state([]) // transient "X did Y" toasts for others' changes (§E); stack up to MAX
  let activityId = 0
  const MAX_TOASTS = 3 // cap concurrent toasts; oldest drops off
  let mergeNudge = $state(null) // {name, payload} when my append merged into a dup (§D16)
  let mergeNudgeSeq = 0
  let reconcile = $state(null) // {items:[{op_type,name,reason,message}]} reconnect review (§G)

  let es = null
  let headerH = $state(0) // measured header height, so floating toasts hover just below it
  let inputEl = $state(null) // the composer input element (for stay-hot refocus)
  let mainEl // the app container — visualViewport keyboard compensation (§41, mobile)
  let setsEl // the scrolling list element
  let atEnd = $state(true) // is the list scrolled to (near) the bottom?
  let lastCount = 0 // tracks record count to auto-scroll only on additions

  function onScroll() {
    if (setsEl) atEnd = setsEl.scrollHeight - setsEl.scrollTop - setsEl.clientHeight < 80
  }
  function goToEnd() {
    insertAfterId = null // move the insertion point to the end (append); server decides
    // whether that continues the open set or starts a new one (if a trailing break exists)
    if (setsEl) setsEl.scrollTo({ top: setsEl.scrollHeight, behavior: 'smooth' })
  }
  // Stick to the bottom on new tunes (mine or others') — but only if already at the
  // end, so a manual scroll-up isn't yanked away (the "Go to end" pill covers that).
  $effect(() => {
    const n = ordered.length
    if (n > lastCount && atEnd && setsEl && !pendingHighlight) {
      requestAnimationFrame(() => { if (setsEl && !pendingHighlight) setsEl.scrollTop = setsEl.scrollHeight })
    }
    lastCount = n
  })

  // The pull-down filter bar is the first child of the list, so it occupies the top
  // SEARCH_BAR_H of scroll content — hidden until you scroll all the way up. The inner
  // .sets-body has min-height:100%, so the list always overflows by ≥ SEARCH_BAR_H even for
  // short logs (which otherwise can't scroll, leaving the bar stuck visible). Nudge past the
  // bar once on first load so it isn't shown initially; long logs are already scrolled down.
  let didInitialHide = false
  function hideBarInitially(tries) {
    if (!setsEl || searchMode || didInitialHide || pendingHighlight) return
    const max = setsEl.scrollHeight - setsEl.clientHeight
    if (max > 0) {
      // scroll just past the bar (short logs may allow less — clamp to what's available)
      setsEl.scrollTop = Math.min(SEARCH_BAR_H, max)
      didInitialHide = true
    } else if (tries > 0) {
      requestAnimationFrame(() => hideBarInitially(tries - 1)) // overflow not laid out yet — retry
    }
  }
  $effect(() => {
    // Gate on content (not `loaded`): `loaded` only flips once streaming connects, which may
    // never happen offline — but the list renders from the bootstrap snapshot regardless.
    if (ordered.length > 0 && setsEl && !searchMode && !didInitialHide) requestAnimationFrame(() => hideBarInitially(30))
  })

  // Measured height of the type-ahead dropdown (it floats UP from the dock and covers the
  // lower part of the list). Drives both the bottom spacer (scroll room past the end) and
  // the visible-band calc below. (§D smart scroll)
  let resultsH = $state(0)
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

  // Keep the active insertion point (the yellow seam / a resolving placeholder) within the
  // VISIBLE BAND — below the header, above the dropdown's top edge — parked as high as the
  // content allows, but only scroll when it's actually occluded/off-screen (no gratuitous
  // jumps). The bottom spacer (rendered in .sets) gives the end-of-list seam room to rise
  // above the dropdown. (§D smart scroll)
  function ensureSeamVisible() {
    if (!setsEl) return
    // While editing, the edited row is the active spot (no seam is rendered) — keep IT
    // in the band so the dropdown floating up from the dock can't cover it.
    const seam = editingId != null ? setsEl.querySelector('.tune-row.editing') : setsEl.querySelector('.seam.active')
    if (!seam) return
    const sets = setsEl.getBoundingClientRect()
    const r = seam.getBoundingClientRect()
    const dropH = dropdownOpen && resultsH ? resultsH + 6 : 0 // dropdown height + its margin
    const bandTop = sets.top + 4
    const bandBottom = sets.bottom - dropH - 8
    if (r.top >= bandTop && r.bottom <= bandBottom) return // already comfortably visible
    const target = clamp(setsEl.scrollTop + (r.top - bandTop), 0, setsEl.scrollHeight - setsEl.clientHeight)
    animateScroll(setsEl, target)
  }

  // Custom eased scroll (slower / calmer than the browser's `behavior:'smooth'`, which
  // restarts and jumps when retriggered). A new target supersedes any in-flight animation.
  let seamScrollRAF = null
  function animateScroll(el, to, duration = 520) {
    if (seamScrollRAF) cancelAnimationFrame(seamScrollRAF)
    const from = el.scrollTop
    const dist = to - from
    if (Math.abs(dist) < 1) { el.scrollTop = to; return }
    const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2) // easeInOutCubic
    let start = null
    const step = (ts) => {
      if (start == null) start = ts
      const p = Math.min(1, (ts - start) / duration)
      el.scrollTop = from + dist * ease(p)
      seamScrollRAF = p < 1 ? requestAnimationFrame(step) : null
    }
    seamScrollRAF = requestAnimationFrame(step)
  }

  // Re-park whenever what's displayed changes: the dropdown appearing / growing / shrinking
  // (resultsH), the results set, the ambiguous gate, or a placeholder resolving — any of
  // which can newly cover the seam. Debounced so the instant result updates (local, then the
  // server merge, then height settling) coalesce into ONE calm move with a slight lag, rather
  // than a burst of competing scrolls. Results themselves still update instantly. (§D)
  let seamTimer = null
  function scheduleSeam() {
    if (seamTimer) clearTimeout(seamTimer)
    seamTimer = setTimeout(() => requestAnimationFrame(ensureSeamVisible), 140)
  }
  $effect(() => {
    resultsH; results.length; ambiguous; resolving // deps
    scheduleSeam()
  })
  let lastTypingSent = 0 // throttle the "still typing" refresh
  let highWater = 0 // max event_id seen; persisted with the snapshot for offline resume
  let snapTimer = null
  let everConnected = false // distinguishes the first connect from a reconnect
  let syncMsg = $state(null) // transient "N synced · M added while away" on reconnect (§I36)
  let syncMsgSeq = 0
  let sessionId = null // for search ranking/flagging (set from bootstrap when online)
  let sessionName = $state('')
  let sessionDate = $state('') // display form ("Mon · Jul 27, 2026")
  // Raw YYYY-MM-DD. Seeded by the shell, but re-datable while the screen is open
  // (spec 046), so it's state rather than a straight read of config.
  let instanceDate = $state(untrack(() => config.instanceDate) || '')
  // This log's own name — session_instance.location_override. Null for the ordinary
  // weekly night; at a festival it's the only thing telling two same-day instances
  // apart, so it's editable from the header alongside the date (spec 047).
  let instanceName = $state(untrack(() => config.instanceName) || '')
  // When it ran (spec 048). Raw "HH:MM[:SS]", '' when unset — and unset is a real
  // state for end_time: the after-hours session that runs until it stops.
  let instanceStart = $state(untrack(() => config.instanceStartTime) || '')
  let instanceEnd = $state(untrack(() => config.instanceEndTime) || '')
  // "8:00pm-11:00pm", or "11:00pm - ?" when it never got an end. The identical
  // string the session's Logs tab shows, from the one shared formatter.
  const timeLabel = $derived(instanceTimeLabel({ start_time: instanceStart, end_time: instanceEnd }))
  // 'regular' | 'festival' (spec 004). Used ONLY to word the naming help: at a festival a
  // name is the norm and the reason is specific ("several sessions share this day"),
  // anywhere else it's the exception ("a night somewhere other than the usual place").
  // Nothing is gated on it — the same fields are editable either way.
  let sessionType = $state(untrack(() => config.sessionType) || 'regular')
  const isFestival = $derived(sessionType === 'festival')
  let displayTz = $state(undefined) // viewer's tz (fallback session tz) for "logged at" times
  let notesText = $state('') // server-truth session notes
  let notesDraft = $state('') // editable buffer in the expanded header
  let logComplete = $state(false) // session marked "completely logged" — hides editing (§024)
  let expanded = $state(false)
  let results = $state([]) // type-ahead search results shown above the composer (§D)
  let resultsQuery = '' // the query `results` correspond to (guards the debounce race)
  let noMatch = $state(false) // a completed search returned nothing (show the empty + deeper prompt)
  let tsInputId = $state(null) // the composer holds a thesession.org URL/id -> offer a direct import (spec 026)
  let ambiguous = $state(false) // Enter hit a fragment matching several tunes, no unique exact (local "red" state)
  let lastMatchExact = false // whether `results` (for resultsQuery) was a unique exact match (gate decision)
  let searchTimer = null
  let searchSeq = 0
  let searching = $state(false) // a server search is in flight for the typed text (input spinner)
  let composerFocused = $state(false) // input has focus — gates the "likely next tune" suggestion row
  let composerHl = $state(-1) // keyboard-highlighted index into composerNavItems (-1 = none, mouse/Enter-default)
  // Pull-down filter (orthogonal to view/edit mode): a search box hidden just above the
  // list, revealed by scrolling to the top, that filters visible sets live and highlights
  // matches. Purely client-side over byId — no network, no stream/mode change (§024).
  let searchMode = $state(false) // the filter UI is active
  let searchText = $state('') // live filter string
  let searchInputEl = $state(null) // the filter input element (focus/blur); null while list mode swaps in the droplist
  const SEARCH_BAR_H = 56 // px; scroll offset that hides the bar (52px bar + ~4px top gap)
  // A placeholder tune row whose match is still resolving (Enter was hit faster than the
  // search returned). While set, the composer is locked; the row settles to linked/unlinked
  // or — if ambiguous — waits for the user to pick. null when nothing is resolving. (§D)
  let resolving = $state(null) // {tempId, breakTempId, text, addAnchors, breakOp, advance, seq}
  let resolvingSeq = 0
  const composerLocked = $derived(resolving != null)

  function showSync(text) {
    const seq = ++syncMsgSeq
    syncMsg = text
    setTimeout(() => { if (seq === syncMsgSeq) syncMsg = null }, 5000)
  }

  // Persist a clean (server-truth) snapshot of the records so the screen can render
  // offline (§G): strip client-only optimistic flags and temp rows.
  async function saveSnapshot() {
    if (readOnly) return // the offline cache serves loggers; a public viewer writes nothing
    const records = [...byId.values()]
      .filter((r) => !r._temp && typeof r.session_instance_tune_id === 'number')
      .map(({ _removing, _temp, pending, status, ...rest }) => rest)
    try {
      // JSON round-trip strips Svelte reactive proxies; IndexedDB can't
      // structured-clone a Proxy (DataCloneError), which would silently fail.
      const value = JSON.parse(JSON.stringify({
        records, last_event_id: highWater, person, ts: Date.now(),
        session_name: sessionName, session_date: sessionDate, instance_date: instanceDate,
        instance_name: instanceName, start_time: instanceStart, end_time: instanceEnd,
        session_type: sessionType, notes: notesText,
        log_complete: logComplete, display_tz: displayTz,
        // Persist the session vocabulary so the offline-render path keeps the local
        // exact-match fast path working without a fresh bootstrap (§024 / §G).
        known_tunes: vocabKnown, known_aliases: vocabAliases,
      }))
      await snapshotPut(config.sessionInstanceId, value)
    } catch {
      /* IndexedDB unavailable — skip */
    }
  }

  // Debounced save for incremental op updates (the full-set save after bootstrap is
  // immediate, so a quick reload can't lose it).
  function scheduleSnapshot() {
    if (snapTimer) return
    snapTimer = setTimeout(() => {
      snapTimer = null
      saveSnapshot()
    }, 800)
  }

  // The UI infers a presence color from the arrival ordinal (spec 024 §F).
  // Player colors. Avoid yellow/gold — that's reserved for the seam / insertion point
  // / End-set (var(--insert)); a player tinted the same would read as the cursor.
  const PALETTE = ['#4f9dff', '#46d27a', '#ef8b3d', '#e0594b', '#b07cff', '#3fd0c9', '#ff8fab', '#9ab0c0']
  const colorFor = (seq) => PALETTE[((seq % PALETTE.length) + PALETTE.length) % PALETTE.length]
  const initials = (name) => {
    const words = (name || '').trim().split(/\s+/).filter(Boolean)
    if (words.length === 0) return '?'
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
    return (words[0][0] + words[words.length - 1][0]).toUpperCase()
  }

  function put(record) {
    if (!record) return
    byId.set(record.session_instance_tune_id, record)
  }

  function drop(id) {
    byId.delete(id)
  }

  // Briefly highlight a record when it settles / changes (the §39 settle-flash),
  // personalized: 'mine' = a soft accent flare (my own settle), 'remote' = a ring
  // pulse in the actor's color (someone else changed it), 'merge' = a purple bounce
  // when an append collapsed into an existing tune (§E/§H30).
  function flashId(id, kind = 'mine', color = null) {
    if (id == null) return
    const tok = ++flashSeq
    flashing.set(id, { kind, color, tok })
    setTimeout(() => { const e = flashing.get(id); if (e && e.tok === tok) flashing.delete(id) }, kind === 'mine' ? 700 : kind === 'highlight' ? 2600 : 1400)
  }

  // Deep-link from a tune's play history (?highlight=<session_instance_tune_id>):
  // scroll the record's row into view and flash it. While pendingHighlight is set,
  // the first-load scroll behaviors (jump-to-end on arriving records, the search-bar
  // hide nudge) are suppressed — they'd clobber this scroll. Retries briefly because
  // the rows render a tick after the bootstrap resolves.
  let pendingHighlight = null
  function highlightFromUrl(id, tries = 60) {
    const el = setsEl?.querySelector(`[data-sit="${id}"]`)
    if (!el) {
      if (tries > 0) setTimeout(() => highlightFromUrl(id, tries - 1), 100)
      else {
        // Don't fail silently: a deep-link that lands on nothing should say so, not just
        // leave the user staring at a log wondering which row they were sent to.
        console.warn(`[live] ?highlight=${id}: record never appeared (waited 6s)`)
        pendingHighlight = null
      }
      return
    }
    didInitialHide = true
    el.scrollIntoView({ block: 'center' }) // instant — a smooth scroll can be interrupted
    flashId(id, 'highlight')
    pendingHighlight = null
  }

  // Resolve a row's logger color index: the persisted per-session color (joined at
  // insert), else the live roster keyed on the logger's person_id (a present logger
  // whose color row didn't join — e.g. just assigned, or a freshly-settled add) — so
  // a row colors as soon as its logger is known, not only after a reload.
  function loggerColorIdx(r) {
    // Only tint OTHER people's rows — never my own. Solo session => nothing tinted
    // (clean); multi-logger => color reads as "someone else logged this" (§F).
    if (r.logged_by_person_id != null && person && r.logged_by_person_id === person.person_id) return null
    if (r.logged_by_color != null) return r.logged_by_color
    if (r.logged_by_person_id != null) {
      const p = roster.find((x) => x.person_id === r.logged_by_person_id)
      if (p) return p.arrival_seq
    }
    return null
  }

  // Inline per-row style: the logger's persisted color drives a subtle attribution
  // tint (--by), and an active flash carries the actor's color (--flash).
  function rowStyle(r) {
    const parts = []
    const idx = loggerColorIdx(r)
    if (idx != null) parts.push(`--by:${colorFor(idx)}`)
    const f = flashing.get(r.session_instance_tune_id)
    if (f && f.color) parts.push(`--flash:${f.color}`)
    return parts.join(';')
  }

  // Ordering + set segmentation are pure logic in logstate.js (unit-tested); the
  // reactive SvelteMap stays here and these derive off its values.
  const ordered = $derived(computeOrdered(byId.values()))
  const segments = $derived(segmentByBreaks(ordered))
  const sets = $derived(setsOf(segments))
  const tunes = $derived(tunesOf(ordered))
  // "61 tunes in 26 sets" — shown in the header-expand and (collapsed) on the date line.
  const tuneSummary = $derived(`${tunes.length} tune${tunes.length === 1 ? '' : 's'} in ${sets.length} set${sets.length === 1 ? '' : 's'}`)

  // pluralType + setLabel now live in logstate.js (pure, unit-tested).

  // "Logged by X, Y · 8:42 PM" for a set — every distinct person who logged a tune in
  // it (in order of first appearance), with the latest log time. null if unknown.
  function loggedInfo(setTunes) {
    const seen = new Set()
    const names = []
    let latest = null
    for (const t of setTunes) {
      if (t.record_type !== 'tune') continue
      if (t.logged_by) {
        const key = t.logged_by_person_id ?? t.logged_by
        if (!seen.has(key)) { seen.add(key); names.push(t.logged_by) }
      }
      if (t.logged_at && (!latest || new Date(t.logged_at) > new Date(latest))) latest = t.logged_at
    }
    if (!names.length && !latest) return null
    const opts = { hour: 'numeric', minute: '2-digit' }
    if (displayTz) opts.timeZone = displayTz
    return {
      who: names.length ? names.join(', ') : null,
      when: latest ? new Date(latest).toLocaleTimeString('en-US', opts) : null,
    }
  }
  const lastRecordId = $derived(ordered.length ? ordered[ordered.length - 1].session_instance_tune_id : null)
  // Is there an OPEN set at the end? (last record is a tune, not a break) — i.e. a
  // set in progress that "End set" would close. A trailing break (or empty list)
  // means the end is closed and appending starts a NEW set (§B/§C).
  const endIsOpen = $derived(ordered.length > 0 && ordered[ordered.length - 1].record_type !== 'break')

  // Insertion point (spec 021 §B): null = append at the end (the 95% case); a record
  // id = insert after it; {before:id} = insert before it (enables insert-at-start).
  let insertAfterId = $state(null)
  // Which seam shows the yellow line: 'end' | `start:<firstTuneId>` (a set's start
  // seam) | `after:<recordId>` (a tune's trailing seam).
  const activeSeam = $derived.by(() => {
    const c = insertAfterId
    if (c == null) return 'end'
    if (typeof c === 'object' && c.newSet != null) {
      // a new set in the gap before this set (the between-sets seam)
      return byId.has(c.newSet) && !byId.get(c.newSet).deleted ? `inter:${c.newSet}` : 'end'
    }
    if (typeof c === 'object' && c.before != null) {
      return byId.has(c.before) && !byId.get(c.before).deleted ? `start:${c.before}` : 'end'
    }
    return byId.has(c) && !byId.get(c).deleted ? `after:${c}` : 'end'
  })
  // What the seams actually render: while a tune row is selected (or being edited) the
  // cursor hides — the selected row's ↑/↓ pills / the editing highlight are the active
  // spot, and showing both at once reads as two competing "active" spots. The underlying
  // position (insertAfterId) is kept, so it surfaces again when the row closes.
  const visibleSeam = $derived(selectedId != null || editingId != null ? null : activeSeam)

  // maxPos + cursorPos now live in logstate.js (pure, unit-tested). Call sites pass
  // the current insertion cursor, the ordered list, and all records (for append).
  function setCursor(id) {
    insertAfterId = id
    selectedId = null // cursor and row selection compete — placing the cursor deselects
    queueMicrotask(() => inputEl?.focus())
  }
  // Move the cursor to a seam and STAY in cursor mode (no composer focus) — used after a
  // split/join so the seam holds its place and the user can Enter/tap again to toggle it back.
  function holdCursor(id) {
    insertAfterId = id
    selectedId = null
    queueMicrotask(() => setsEl?.querySelector('.seam.active')?.scrollIntoView({ block: 'nearest' }))
  }
  // Every insertion-cursor position, top to bottom (computeCursorSlots + seamKeyFor are pure,
  // unit-tested in logstate.js). Arrow keys step the cursor through these when no field is focused.
  const cursorSlots = $derived(computeCursorSlots(displaySegments, endIsOpen, ordered.length > 0))
  // Move the insertion cursor one slot. Deliberately does NOT focus the composer — cursor-
  // stepping happens while nothing is focused, and refocusing would flip us back into dropdown
  // nav. Stepping off either end is a mode transition: past the bottom → the tune-entry box,
  // above the top → the filter box (spec 028 keyboard nav).
  function moveCursor(dir) {
    const slots = cursorSlots
    if (!slots.length) return
    const cur = activeSeam
    let idx = slots.findIndex((s) => seamKeyFor(s) === cur)
    if (idx === -1) idx = dir > 0 ? -1 : slots.length
    const target = idx + dir
    if (target >= slots.length) { inputEl?.focus(); return } // off the bottom → tune entry box
    if (target < 0) { focusFilterBox(); return } // off the top seam → filter box
    insertAfterId = slots[target]
    selectedId = null // stepping the cursor drops any row selection (they compete for the arrows)
    queueMicrotask(() => setsEl?.querySelector('.seam.active')?.scrollIntoView({ block: 'nearest' }))
  }
  // Reveal + focus the pull-down filter box (it lives above the fold); onfocus enters searchMode.
  function focusFilterBox() {
    const fb = mainEl?.querySelector('.searchbar-input')
    if (!fb) return
    setsEl?.scrollTo({ top: 0 })
    queueMicrotask(() => fb.focus())
  }
  // Page-local recall history for the filter box (MRU) and the pane/modal search box (shared,
  // passed down). Not persisted — lives only for this page's lifetime (spec 028).
  let filterHist = []
  let filterHistPos = null // navigation cursor into filterHist (null = live draft)
  let searchHist = $state([]) // shared with TuneSearch via a prop; MRU list of past deep-search queries
  // Filter box keys: ArrowUp cycles older filters, ArrowDown cycles newer (past newest → empty)
  // or, from an empty non-navigating box, drops back onto the top seam.
  function onFilterKey(e) {
    if (e.key === 'ArrowUp') {
      const step = historyStep(filterHist, filterHistPos, -1)
      if (step) { filterHistPos = step.pos; searchText = step.value; e.preventDefault() }
    } else if (e.key === 'ArrowDown') {
      if (filterHistPos != null) {
        const step = historyStep(filterHist, filterHistPos, 1)
        if (step) { filterHistPos = step.pos; searchText = step.value; e.preventDefault() }
      } else if (!searchText.trim()) {
        e.preventDefault()
        exitFilterToTopSeam()
      }
    }
  }
  // Remember a filter term once you've settled on it (800ms idle), so recall history holds the
  // terms you actually filtered by — not every intermediate keystroke. Deterministic, no blur.
  let filterRememberTimer = null
  function onFilterInput() {
    searchMode = true
    filterHistPos = null
    if (filterRememberTimer) clearTimeout(filterRememberTimer)
    filterRememberTimer = setTimeout(() => rememberInHistory(filterHist, searchText), 800)
  }
  const rememberFilter = () => { rememberInHistory(filterHist, searchText); filterHistPos = null }
  // ArrowDown on an empty filter: leave filter mode and land on the very top seam (cursor mode).
  function exitFilterToTopSeam() {
    searchText = ''
    searchMode = false
    searchInputEl?.blur()
    if (viewing || !segments.length) return
    insertAfterId = { before: segments[0].tunes[0].session_instance_tune_id }
    selectedId = null
    queueMicrotask(() => setsEl?.querySelector('.seam.active')?.scrollIntoView({ block: 'nearest' }))
  }
  // "/" focus target: the persistent pane search when it's mounted (wide), else the modal.
  function focusSearchBox() {
    const paneField = mainEl?.querySelector('.sidepane .deep-field')
    if (paneField) { paneField.focus(); return }
    openDeep()
  }
  // Global keys (spec 028): Escape blurs whatever's focused; "/" jumps to the search box; and
  // while nothing is focused (cursor mode), Up/Down step the cursor, Enter joins/splits at the
  // active seam, and Space drops back into the tune-entry box. A focused field owns its own
  // keys first — text-field focus is the signal that "a list may be active", so we never steal.
  function onWinKey(e) {
    const ae = document.activeElement
    const inField = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)
    if (e.key === 'Escape') {
      if (e.defaultPrevented) return // a modal/resolving handler already claimed it
      if (inField) { ae.blur(); return }
      if (drag) { cancelDrag(); return } // Esc mid-drag: settle the block back, no op
      if (listStatusOpen) { listStatusOpen = false; return }
      if (assignOpen) { assignOpen = false; return }
      if (selectMode) { exitSelectMode(); return }
      return
    }
    if (e.key === '/') {
      if (inField || e.defaultPrevented) return // a slash typed into a field is just text
      e.preventDefault()
      focusSearchBox()
      return
    }
    if (inField || e.defaultPrevented) return // everything below is cursor-mode only
    // Selection-mode shortcuts (spec 029 §C): work in view mode too (copy-only there).
    if (selectMode) {
      const mod = e.metaKey || e.ctrlKey
      const k = e.key.toLowerCase()
      if (mod && k === 'c') {
        // don't hijack a real text-selection copy
        if (!window.getSelection()?.toString()) { e.preventDefault(); copySelection() }
        return
      }
      if (mod && k === 'v') { e.preventDefault(); if (!viewing && !searchMode) pasteClipboard(); return }
      if (mod && k === 'a') { e.preventDefault(); selectAllVisible(); return }
      if ((e.key === 'Delete' || e.key === 'Backspace') && !viewing) { e.preventDefault(); bulkDelete(); return }
      if (e.key === ' ') { e.preventDefault(); return } // no composer to jump to
    }
    if (!canEdit) return // no cursor in view/filter modes
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      moveCursor(e.key === 'ArrowDown' ? 1 : -1)
      return
    }
    // Enter/Space: don't steal from a focused button/link/role=button (a focused seam already
    // claimed the key via its own handler + preventDefault, caught by the guard above).
    const interactive = ae && (ae.tagName === 'BUTTON' || ae.tagName === 'A' || ae.getAttribute?.('role') === 'button')
    if (interactive) return
    if (e.key === 'Enter') {
      if (selectedId != null) return // row selected -> the cursor is hidden; no seam to act on
      // The live yellow end seam of an open set: Enter closes the set (same as "End set").
      if (activeSeam === 'end' && endIsOpen) { e.preventDefault(); endSet(); return }
      const act = seamActionFor(insertAfterId, displaySegments)
      if (act?.type === 'join') { e.preventDefault(); joinAt(act.breakId) }
      else if (act?.type === 'split') { e.preventDefault(); splitAt(act.tuneId) }
    } else if (e.key === ' ') {
      e.preventDefault()
      inputEl?.focus() // Space → back to the tune entry box
    }
  }
  // Keyboard activation for click-only elements (a11y): Enter/Space runs the same action.
  function activate(e, fn) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn() }
  }
  // The tune-row click action, shared by onclick + onkeydown so the row is keyboard-operable.
  // Selection mode redefines the tap (toggle select) and — deliberately — works even while
  // the filter is active (spec 029 §B: filter + selection compose).
  function rowClick(r, e) {
    if (selectMode) { toggleSelect(r, e); return }
    if (r._resolving) { if (canEdit) selectRow(r.session_instance_tune_id); return }
    // A QUEUED offline add is selectable so it can be cancelled before it ever syncs;
    // a 'sending' temp settles within moments and stays inert until it's real.
    if (r._temp && r._status === 'queued') { if (canEdit) selectRow(r.session_instance_tune_id); return }
    if (r._temp || r._removing) return
    // While filtering, a tap opens details (same as view mode) — filtering is
    // exactly when you've hunted down a tune and want its info.
    if (viewing || searchMode) { openDrawer(r); return }
    selectRow(r.session_instance_tune_id)
  }
  // Arm the between-sets seam: the next tune starts a NEW set in this gap, before
  // the set whose first tune is `nextFirstId` (spec 021 §C; prototype "new-set-after").
  function setNewSetCursor(nextFirstId) {
    insertAfterId = { newSet: nextFirstId }
    selectedId = null
    queueMicrotask(() => inputEl?.focus())
  }

  // Split: drop a break after this tune (intra-set seam) -> two sets (§C).
  function splitAt(afterTuneId) {
    const op_id = crypto.randomUUID()
    const tempId = `temp-${op_id}`
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === afterTuneId)
    const before = idx >= 0 ? ordered[idx].order_position : maxPos(byId.values())
    const after = idx >= 0 && idx + 1 < ordered.length ? ordered[idx + 1].order_position : null
    // The tune right after the split becomes the first tune of the new set — the cursor holds
    // that spot as the new between-sets seam (Enter/tap there now Joins, undoing the split).
    const nextId = idx >= 0 ? ordered[idx + 1]?.session_instance_tune_id : null
    byId.set(tempId, {
      session_instance_tune_id: tempId, record_type: 'break',
      order_position: generateBetween(before, after), deleted: false, _temp: true,
    })
    trySend({ op_id, op_type: 'set_break', payload: { action: 'insert', after_record_id: afterTuneId }, status: 'sending', ts: nextTs(), tempId })
    holdCursor(nextId != null ? { newSet: nextId } : null)
  }

  // Join: remove the boundary break (between-sets seam) -> merge the two sets (§C).
  function joinAt(breakId) {
    const brk = byId.get(breakId)
    // The tune just before the removed break is no longer a set's last tune — the cursor holds
    // that spot, now an intra-set seam (Enter/tap there now Splits, undoing the join).
    const bidx = ordered.findIndex((r) => r.session_instance_tune_id === breakId)
    const prevId = bidx > 0 ? ordered[bidx - 1]?.session_instance_tune_id : null
    byId.delete(breakId) // optimistic merge
    const op_id = crypto.randomUUID()
    trySend({ op_id, op_type: 'set_break', payload: { action: 'remove', record_id: breakId }, status: 'sending', ts: nextTs(), restoreRecord: brk })
    holdCursor(prevId != null ? prevId : null)
  }

  // --- row selection + actions (spec 021 §E) ---
  // Read-only View (default) vs full Edit (logging), toggled on this same screen
  // (spec 021 §A2–3). View is the common case — most people read a logged session
  // rather than log one — so a logger taps "✎ Edit log" to start.
  let mode = $state('view')
  const viewing = $derived(mode === 'view')
  // Editing affordances (seams, row actions, composer) are allowed only when in edit mode
  // AND not filtering — search mode hides them regardless of the underlying view/edit mode.
  const canEdit = $derived(!viewing && !searchMode)

  let selectedId = $state(null) // the "opened" tune row (shows its action bar)
  let editingId = $state(null) // record being edited (composer pre-filled; §E "✎ Edit")
  let editingName = $state('') // its name, for the editing banner label
  let openTrayId = $state(null) // set whose info tray (started-by / logged-by) is open
  let starterFlashId = $state(null) // set whose starter pill is briefly flashing (confirm)
  function toggleTray(id) { openTrayId = openTrayId === id ? null : id }

  // --- People: ONE PersonPicker for both the starter picker and attendance (spec 034) ---
  //
  // These used to be two UIs. The starter picker could only see people already checked in,
  // so attributing a set to someone who'd just walked in meant leaving the picker, opening a
  // separate drawer, adding them, and coming back. Now it's one component and one gesture:
  // type "Sar", tap Sarah, she's checked in AND credited with the set.
  let pickerOpen = $state(false)
  let pickerMode = $state('attendance') // 'attendance' | 'starter'
  let pickerSet = $state(null)          // starter mode: the set (first-tune id) being attributed
  let attendees = $state([])            // the whole session roster + tonight's flags
  let attendeesLoaded = $state(false)
  const canonicalInstruments = $derived(config.canonicalInstruments || [])

  // Per-session people-tracking flags (spec 039). Default true when the config predates
  // the flags. These gate ONLY attendance + set-starters; presence, "logged by", and
  // typing are attribution of who's actively logging and are never gated. Starters
  // additionally require attendance (the DB CHECK), so trackStarters folds it in.
  // Audio for this night (spec 050, schema/053). Off unless this viewer holds the
  // session's recordings grant -- for everyone else the row simply isn't there,
  // and every endpoint behind it re-checks regardless.
  const canManageRecordings = $derived(config.canManageRecordings === true)
  let recordingsOpen = $state(false)
  let recordingCount = $state(null) // null until asked; the header shows a count once known

  async function loadRecordingCount() {
    if (!canManageRecordings) return
    try {
      const res = await fetch(`/api/session-instances/${config.sessionInstanceId}/recordings`)
      const data = await res.json()
      if (data.success) recordingCount = (data.recordings || []).length
    } catch { /* the header just shows no count; Manage still works */ }
  }

  // ---------- playback (spec 050 read side) ----------
  // A tune that was timestamped in the segmenter can be heard from its row here.
  // Everything below is inert until loadAudio() finds a segmented recording, which
  // most nights will not have — `resolved` stays empty and no button ever renders.
  let audioEl = $state(null)
  let audioRec = $state(null) // {recording_id, duration_ms, audio_url, mime_type, label}
  // session_instance_tune_id -> {startMs, endMs, ...}, from the SHARED resolver the
  // segmenter uses, so a tune's extent is identical in the tool and on this page.
  let resolved = $state(new SvelteMap())
  // The queue is ids in play order plus a cursor; null means nothing is playing.
  let playQ = $state(null) // {ids: [sit_id], idx}
  let playhead = $state(0) // ms into the CURRENT tune's segment
  let audioPaused = $state(true)
  let audioErr = $state(null)
  let rafId = null
  let urlRetried = false
  // Transport panel (the playbar expanded). All of this is session-only by
  // design -- these are "for this listen" choices, not settings, and persisting
  // them would mean a page opened tomorrow silently repeats one tune forever.
  let playerOpen = $state(false)
  let repeatOne = $state(false)
  let autoContinue = $state(true)
  // Dragging the scrubber: the rAF loop must not fight the thumb, so while a
  // drag is live the slider shows scrubMs and the playhead is left alone.
  let scrubbing = $state(false)
  let scrubMs = $state(0)

  // Which encode is playing. Session-only like the other panel toggles: a page
  // opened tomorrow starts on the cheap one again, which is the safe default to
  // land on when you don't yet know what connection you're on.
  let audioSourceId = $state('proxy')
  const audioSources = $derived(audioRec?.audio_sources || [])
  const currentSource = $derived(
    audioSources.find((s) => s.id === audioSourceId) || audioSources[0] || null,
  )
  // Only worth offering when there are genuinely two things to choose between --
  // with no proxy the master IS the only encode, and an "HD" button that just
  // reloads the same file would be a lie.
  const canSwitchHd = $derived(audioSources.length > 1)
  const hdOn = $derived(currentSource?.id === 'master')

  const playingId = $derived(playQ ? playQ.ids[playQ.idx] : null)
  const playingSeg = $derived(playingId != null ? resolved.get(playingId) : null)
  const tuneLenMs = $derived(playingSeg ? playingSeg.endMs - playingSeg.startMs : 0)
  const scrubValue = $derived(scrubbing ? scrubMs : playhead)
  // "Previous" restarts the current tune when you're already into it -- the
  // transport convention, and it keeps the button useful on the first tune.
  const RESTART_BEFORE_PREV_MS = 3000

  async function loadAudio() {
    if (!canManageRecordings) return
    try {
      const data = await instanceAudio(config)
      if (!data?.recording?.audio_sources?.length) return
      audioRec = data.recording
      resolved = new SvelteMap(
        resolveSegments(
          data.segments.map((s) => ({ session_instance_tune_id: s.session_instance_tune_id, segment: s })),
          data.recording.duration_ms,
        ),
      )
    } catch { /* no play buttons; the log is unaffected */ }
  }

  /** Ids of a set's timestamped tunes, in play order, from `fromId` onward. */
  function queueFor(setTunes, fromId = null) {
    const ids = setTunes
      .filter((t) => resolved.has(t.session_instance_tune_id))
      .map((t) => t.session_instance_tune_id)
    if (fromId == null) return ids
    const i = ids.indexOf(fromId)
    return i < 0 ? [] : ids.slice(i)
  }

  // A queue stops at the end of its SET rather than running on into the night. The
  // gap to the next set is the talking, the tuning and the pint — skipping it would
  // splice two unrelated sets together, and playing it is the one thing we said we
  // wouldn't do.
  /**
   * play(), distinguishing the two very different reasons it rejects.
   *
   * An AbortError means a load() or pause() landed on top of a play() that was
   * still pending — routine every time the HD switch reloads the element, and no
   * reason to tell anyone or to tear the player down. Anything else (the autoplay
   * policy refusing, a decode failure) is real and the listener needs it said.
   */
  function playAudio(onFail) {
    audioEl?.play().catch((e) => {
      if (e?.name === 'AbortError') return
      audioErr = String(e?.message || e)
      onFail?.()
    })
  }

  function startQueue(ids) {
    if (!audioEl || !ids.length) return
    audioErr = null
    playQ = { ids, idx: 0 }
    seekToCurrent()
    playAudio(() => (playQ = null))
  }

  function seekToCurrent() {
    const seg = resolved.get(playQ?.ids[playQ.idx])
    if (seg && audioEl) {
      audioEl.currentTime = seg.startMs / 1000
      playhead = 0
    }
  }

  function toggleTune(setTunes, id) {
    if (playingId === id) return audioEl?.paused ? audioEl.play() : audioEl?.pause()
    startQueue(queueFor(setTunes, id))
  }

  function stopPlayback() {
    audioEl?.pause()
    playQ = null
    playhead = 0
    playerOpen = false
    scrubbing = false
  }

  // ---- transport ----
  function jumpTo(idx) {
    if (!playQ || idx < 0 || idx >= playQ.ids.length) return
    playQ = { ...playQ, idx }
    seekToCurrent()
  }

  function nextTune() {
    if (!playQ) return
    if (playQ.idx + 1 >= playQ.ids.length) return stopPlayback()
    jumpTo(playQ.idx + 1)
  }

  function prevTune() {
    if (!playQ) return
    // Past the first few seconds, or already at the head of the queue: restart
    // this tune rather than doing nothing.
    if (playhead > RESTART_BEFORE_PREV_MS || playQ.idx === 0) return seekToCurrent()
    jumpTo(playQ.idx - 1)
  }

  function togglePlayPause() {
    if (!audioEl) return
    if (audioEl.paused) playAudio()
    else audioEl.pause()
  }

  /**
   * Switch encode without losing your place.
   *
   * Changing an <audio> element's src resets it to zero and stops playback, so
   * position and play state are captured first and restored once the NEW source
   * has metadata. The ordering below is load-bearing and matches the segmenter's
   * switchSource(): subscribe to loadedmetadata BEFORE calling load(), because
   * load() doesn't reset readyState synchronously — and writing currentTime on an
   * element that has no metadata yet wedges the load outright (networkState stuck
   * at LOADING, nothing ever buffers).
   */
  async function switchAudioSource(id) {
    if (!audioEl || id === audioSourceId || !audioSources.some((s) => s.id === id)) return
    const resumeAt = audioEl.currentTime
    const wasPlaying = !audioEl.paused
    audioSourceId = id
    audioErr = null
    await tick() // the src attribute has now been rewritten
    audioEl.addEventListener(
      'loadedmetadata',
      () => {
        audioEl.currentTime = resumeAt
        if (wasPlaying) playAudio()
      },
      { once: true },
    )
    audioEl.load()
  }

  // Tunes whose slice is being cut server-side right now, so the row can spin.
  const downloading = new SvelteSet()

  /** Pull the server's filename out of Content-Disposition, RFC 5987 form first. */
  function filenameFrom(disposition) {
    if (!disposition) return null
    const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
    if (star) { try { return decodeURIComponent(star[1]) } catch { /* fall through */ } }
    const plain = /filename="([^"]+)"/i.exec(disposition)
    return plain ? plain[1] : null
  }

  /**
   * Download one tune.
   *
   * Fetched rather than left to the browser's own download of the href, because
   * cutting the slice takes a couple of seconds server-side and the row needs to
   * say so. The cost is that the browser's native progress UI is out of the loop,
   * which is why the spinner exists — and why the element stays an <a href>, so
   * middle-click and "Save link as" still work the plain way.
   */
  async function downloadTune(r) {
    const id = r.session_instance_tune_id
    if (downloading.has(id) || !audioRec) return
    downloading.add(id)
    audioErr = null
    try {
      const res = await fetch(`/api/recordings/${audioRec.recording_id}/segments/${id}/download`, {
        credentials: 'same-origin',
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.error || `Download failed (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filenameFrom(res.headers.get('Content-Disposition')) || `${r.name || 'tune'}.mp3`
      document.body.appendChild(a)
      a.click()
      a.remove()
      // Firefox needs the object URL to outlive the click; revoking immediately
      // cancels the save it just started.
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (e) {
      audioErr = String(e?.message || e)
    } finally {
      downloading.delete(id)
    }
  }

  /** Bytes -> "43 MB" / "348 MB". The listener's only honest basis for judging HD. */
  function formatBytes(n) {
    if (!n) return null
    const mb = n / 1e6
    return mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${Math.round(mb)} MB`
  }

  // Drag: `input` fires continuously, `change` on release. Seeking only on
  // release keeps a drag across a 40-minute recording from firing a range
  // request per pixel; the label still tracks the thumb live.
  function onScrubInput(e) {
    scrubbing = true
    scrubMs = Number(e.currentTarget.value)
  }

  function onScrubCommit(e) {
    const ms = Number(e.currentTarget.value)
    scrubbing = false
    if (!audioEl || !playingSeg) return
    playhead = ms
    audioEl.currentTime = (playingSeg.startMs + ms) / 1000
  }

  // One frame of playback: advance the queue when the current tune ends, seeking
  // only across a real gap (playbackStep decides; it's pure and unit-tested).
  function playTick() {
    rafId = null
    if (!playQ || !audioEl) return
    // A seek in flight means currentTime is still the OLD position. Acting on it
    // would re-fire whichever branch issued the seek (repeat-one loops on itself
    // this way), so wait for it to land.
    if (audioEl.seeking) {
      rafId = requestAnimationFrame(playTick)
      return
    }
    const nowMs = audioEl.currentTime * 1000
    const step = playbackStep(playQ.ids, playQ.idx, nowMs, resolved, { repeatOne, autoContinue })
    if (step.done) return stopPlayback()
    if (step.idx !== playQ.idx) playQ = { ...playQ, idx: step.idx }
    if (step.seekMs != null) audioEl.currentTime = step.seekMs / 1000
    const seg = resolved.get(playQ.ids[playQ.idx])
    // Mid-drag the thumb owns the readout; writing playhead here would yank it back.
    if (!scrubbing) playhead = seg ? Math.max(0, nowMs - seg.startMs) : 0
    rafId = requestAnimationFrame(playTick)
  }

  function onAudioPlay() {
    audioPaused = false
    if (rafId == null) rafId = requestAnimationFrame(playTick)
  }

  function onAudioPause() {
    audioPaused = true
    if (rafId != null) { cancelAnimationFrame(rafId); rafId = null }
  }

  // The URL is a presigned S3 link with a finite life, so a page left open long
  // enough will fail to load one day. Re-ask for a fresh one, ONCE, and resume where
  // we were — a second failure is a real error and gets shown.
  async function onAudioError() {
    if (urlRetried || !audioRec) { audioErr = 'Audio unavailable'; return }
    urlRetried = true
    const wasPlaying = playQ
    await loadAudio()
    if (wasPlaying) startQueue(wasPlaying.ids.slice(wasPlaying.idx))
  }

  const trackAttendance = $derived(config.trackAttendance !== false)
  const trackStarters = $derived(config.trackSetStarters !== false && trackAttendance)

  // The roster's display_name is the FULL name (people lists show full names); the
  // starter pill uses the server's abbreviated form ("First L"). Abbreviate the
  // optimistic name the same way so it doesn't flicker when the server record echoes.
  function starterAbbrev(p) {
    if (!p.first_name) return p.display_name
    return p.last_name ? `${p.first_name} ${p.last_name[0]}` : p.first_name
  }

  // the set's recorded starter name (first tune that carries one)
  function setStarterName(seg) {
    for (const t of seg.tunes) if (t.started_by_name) return t.started_by_name
    return null
  }
  const pickerStarterName = $derived.by(() => {
    if (pickerMode !== 'starter' || pickerSet == null) return null
    const seg = displaySegments.find((s) => s.tunes[0].session_instance_tune_id === pickerSet)
    return seg ? setStarterName(seg) : null
  })
  // Who's actually here — for the header's attendance line.
  const checkedIn = $derived(attendees.filter((p) => p.attending))

  /**
   * Tense. A session happening tonight (or not yet) has people "Attending"; one already in
   * the past had people who "Attended". Both dates are plain YYYY-MM-DD, so a string compare
   * is the whole comparison — no Date parsing, no timezone arithmetic.
   *
   * "Today" is the logger's own local date, which is the right frame: whoever is running this
   * is standing in the room.
   */
  const attendanceLabel = $derived.by(() => {
    if (!instanceDate) return 'Attending'
    return instanceDate < localToday() ? 'Attended' : 'Attending'
  })

  /** Today, in the logger's own local calendar, as YYYY-MM-DD. */
  function localToday() {
    const t = new Date()
    return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
  }

  async function refreshAttendees() {
    // The roster feeds ONLY the attendance header and the starter picker. With both off
    // (spec 039) nothing consumes it, so we don't fetch it — and the endpoint would be
    // pointless work besides.
    if (!trackAttendance && !trackStarters) return
    try { attendees = await livePeople(config); attendeesLoaded = true } catch { /* keep current */ }
  }
  async function ensureAttendees() {
    if (!attendeesLoaded) await refreshAttendees()
  }

  async function openStarterPicker(firstId) {
    pickerMode = 'starter'
    pickerSet = firstId
    pickerOpen = true
    await ensureAttendees()
  }
  async function openAttendance() {
    pickerMode = 'attendance'
    pickerSet = null
    pickerOpen = true
    await ensureAttendees()
  }
  function closePicker() { pickerOpen = false; pickerSet = null }

  // Attendance ops need a connection (not in the offline op model); surface rejections.
  async function attendanceOp(op_type, payload, label) {
    error = ''
    if (!navigator.onLine) { notice = `You're offline — ${label} needs a connection.`; return false }
    try {
      const res = await sendOp(config, op_type, payload)
      if (res.rejected) { notice = res.message || `${label}: ${res.reason}`; return false }
      await refreshAttendees()
      return res
    } catch (e) {
      if (e.networkError) notice = `You're offline — ${label} needs a connection.`
      else error = e.message
      return false
    }
  }

  /**
   * Attribute a set to someone. Takes the set id EXPLICITLY rather than reading `pickerSet`:
   * in starter mode the picker calls onSelect() and then closes itself synchronously, which
   * nulls pickerSet -- so by the time an awaited check-in resolves, the state that says which
   * set we were attributing is already gone. (That race silently dropped the attribution
   * while still checking the person in: the exact half-done outcome this flow exists to
   * avoid.) Capture the target before the first await; never re-read it after.
   */
  function attributeTo(setId, person) {
    if (setId == null) return
    const seg = displaySegments.find((s) => s.tunes[0].session_instance_tune_id === setId)
    if (seg) setStarter(seg, person)
  }

  /**
   * Tapping a row. The single gesture that motivated this whole change: in starter mode, a
   * person who isn't checked in yet gets checked in FIRST, then credited with the set.
   */
  async function pickPerson(person) {
    if (pickerMode === 'starter') {
      const setId = pickerSet // capture: the picker closes out from under us
      if (!person.attending) {
        const ok = await attendanceOp('attendance_add', { person_id: person.person_id }, 'Check in')
        if (!ok) return
      }
      attributeTo(setId, person)
      return
    }
    // Attendance mode: the row toggles. (Check-out has its own ✕; tapping a checked-in row
    // is a no-op rather than a surprise removal.)
    if (!person.attending) {
      await attendanceOp('attendance_add', { person_id: person.person_id }, 'Check in')
    }
  }

  function checkOutPerson(person) {
    attendanceOp('attendance_remove', { person_id: person.person_id }, 'Remove')
  }

  function clearStarter() {
    if (pickerSet == null) return
    const seg = displaySegments.find((s) => s.tunes[0].session_instance_tune_id === pickerSet)
    if (seg) setStarter(seg, null)
  }

  async function createPerson({ first_name, last_name, email, instruments }) {
    // Capture before the await, for the same reason as pickPerson: closePicker() below (and
    // any close the user triggers meanwhile) nulls pickerSet.
    const setId = pickerSet
    const wasStarter = pickerMode === 'starter'
    const res = await attendanceOp(
      'attendance_create_person',
      { first_name, last_name, email, instruments },
      'Add person'
    )
    // The new person is checked in by the op. In starter mode, credit them with the set and
    // close -- that is the "a visitor shows up mid-tune" path, and it should cost one gesture.
    if (res && res.person && wasStarter) {
      attributeTo(setId, res.person)
      closePicker()
    }
  }

  // --- session notes (header §F) ---
  function toggleExpand() {
    expanded = !expanded
    if (expanded) notesDraft = notesText // sync the editable buffer on open
  }
  // Auto-collapse the expanded header as soon as the user starts doing anything else on
  // the page (tap/click or keyboard focus outside the header). An unsaved notes draft
  // keeps it open — collapsing would silently discard the typing (Save/Cancel stay up).
  function collapseHeaderOnOutside(e) {
    // Also dismiss the connection-dot popover on any interaction outside it.
    if (connPopup && e.target instanceof Element && !e.target.closest('.conn-btn, .conn-popup')) connPopup = false
    if (!expanded) return
    if (e.target instanceof Element && e.target.closest('.topbar')) return
    if (dateOpen) return // the date sheet portals outside .topbar; it IS header work
    if (notesDraft !== notesText) return
    expanded = false
  }
  // Save the edited notes (online-only op; optimistic, reconciled by SSE echo).
  async function saveNotes() {
    const text = notesDraft
    error = ''
    if (!navigator.onLine) { notice = "You're offline — notes need a connection."; return }
    notesText = text // optimistic; dirty clears
    try {
      const res = await sendOp(config, 'edit_notes', { notes: text })
      if (res.rejected) notice = res.message || res.reason
    } catch (e) {
      if (e.networkError) notice = "You're offline — notes need a connection."
      else error = e.message
    }
  }

  // --- session date (header §F, spec 046) ---
  // A log's date is set when the instance is created, which is wrong whenever you start
  // logging after midnight: the session was really the evening before. This sheet moves
  // it. Online-only, like notes — the SSE echo re-dates every other open screen.
  let dateOpen = $state(false)
  let dateDraft = $state('') // YYYY-MM-DD in the picker
  let dateErr = $state('') // rejection text shown inside the sheet
  let dateConfirm = $state(false) // a collision was reported; the next save says "yes, really"
  let dateSaving = $state(false)

  // The time drafts live alongside the date one: same sheet, same Save (spec 048).
  // '' is meaningful — clearing end_time is how you say "it ran until it stopped".
  let startDraft = $state('')
  let endDraft = $state('')
  // <input type="time"> wants HH:MM; the server sends HH:MM:SS.
  const toInputTime = (t) => (t ? String(t).slice(0, 5) : '')
  const dateDirty = $derived(
    dateDraft !== instanceDate ||
      startDraft !== toInputTime(instanceStart) ||
      endDraft !== toInputTime(instanceEnd)
  )
  // The sheet's one-line preview of what Save would write.
  const draftWhen = $derived.by(() => {
    const when = instanceTimeLabel({ start_time: startDraft, end_time: endDraft })
    return (longDate(dateDraft) || '—') + (when ? ` · ${when}` : '')
  })

  function openDateEditor() {
    dateDraft = instanceDate || localToday()
    startDraft = toInputTime(instanceStart)
    endDraft = toInputTime(instanceEnd)
    dateErr = ''
    dateConfirm = false
    dateSaving = false
    dateOpen = true
  }
  // Shift the draft by ±1 day. Parsed as local noon so a DST boundary can't land the
  // arithmetic on the wrong calendar day.
  function nudgeDate(days) {
    const base = dateDraft || instanceDate || localToday()
    const [y, m, d] = base.split('-').map(Number)
    const dt = new Date(y, m - 1, d, 12)
    dt.setDate(dt.getDate() + days)
    dateDraft = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
    dateErr = ''
    dateConfirm = false
  }
  // Long form of a YYYY-MM-DD, for the sheet's preview line.
  function longDate(iso) {
    if (!iso) return ''
    const [y, m, d] = iso.split('-').map(Number)
    if (!y || !m || !d) return iso
    return new Date(y, m - 1, d, 12).toLocaleDateString(undefined, {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
    })
  }

  async function saveDate() {
    if (!dateDraft || !dateDirty) { dateOpen = false; return }
    dateErr = ''
    if (!navigator.onLine) { dateErr = "You're offline — changing the date needs a connection."; return }
    dateSaving = true
    try {
      // Date and times go in ONE op: they're one edit behind one Save, so sending
      // them together means one history row and no half-applied "when".
      const res = await sendOp(config, 'set_date', {
        date: dateDraft, start_time: startDraft, end_time: endDraft, confirm: dateConfirm,
      })
      if (res.rejected) {
        dateErr = res.message || res.reason
        // A same-date collision is allowed, just rarely intended: offer to go ahead.
        dateConfirm = res.reason === 'date_conflict'
        return
      }
      applyDate(res)
      dateOpen = false
    } catch (e) {
      dateErr = e.networkError ? "You're offline — changing the date needs a connection." : e.message
    } finally {
      dateSaving = false
    }
  }

  // One place that lands a new date/time on the screen — used by both the local save
  // and the SSE echo (which is what re-dates everyone else's open logger). Times apply
  // on key PRESENCE, not truthiness: null means "no end time", which has to be able to
  // land, and an echo from a pre-048 client carries no time keys at all.
  function applyDate(d) {
    if (d.date) instanceDate = d.date
    if (d.session_date) sessionDate = d.session_date
    if ('start_time' in d) instanceStart = d.start_time || ''
    if ('end_time' in d) instanceEnd = d.end_time || ''
  }

  // The log's name (session_instance.location_override). A weekly session doesn't need
  // one — the date says it. A festival does: several sessions run in a day and the date
  // names all of them equally, so this is what tells them apart in every list that shows
  // instances. Same shape as the date editor: sheet, explicit save, SSE echo.
  let nameOpen = $state(false)
  let nameDraft = $state('')
  let nameErr = $state('')
  let nameSaving = $state(false)

  function openNameEditor() {
    nameDraft = instanceName || ''
    nameErr = ''
    nameSaving = false
    nameOpen = true
  }

  async function saveName() {
    const next = nameDraft.trim()
    if (next === (instanceName || '')) { nameOpen = false; return }
    nameErr = ''
    if (!navigator.onLine) { nameErr = "You're offline — naming this log needs a connection."; return }
    nameSaving = true
    try {
      const res = await sendOp(config, 'set_name', { name: next })
      if (res.rejected) {
        nameErr = res.message || res.reason
        return
      }
      applyName(res)
      nameOpen = false
    } catch (e) {
      nameErr = e.networkError ? "You're offline — naming this log needs a connection." : e.message
    } finally {
      nameSaving = false
    }
  }

  // One place a new name lands — the local save and the SSE echo both come through here.
  function applyName(d) {
    instanceName = d.instance_name || ''
  }

  // Mark this session "completely logged" (§024): hides the editing affordances for
  // everyone (the SSE echo flips other clients via applyOp). Online-only metadata op,
  // like notes. Drops us to read-only view; the next reload takes the render-only path.
  // Mark complete / re-open are decisions -> kit Dialogs (spec 035), not native
  // confirms. markComplete()/markIncomplete() raise the Dialog; do*() run on confirm.
  let markCompleteOpen = $state(false)
  let markIncompleteOpen = $state(false)

  function markComplete() {
    error = ''
    if (!navigator.onLine) { notice = "You're offline — marking complete needs a connection."; return }
    markCompleteOpen = true
  }

  async function doMarkComplete() {
    logComplete = true // optimistic footer/header feedback; the SSE echo reconciles
    try {
      const res = await sendOp(config, 'mark_complete', {})
      if (res.rejected) { logComplete = false; notice = res.message || res.reason; return }
      if (mode === 'edit') setMode('view') // leave editing; re-bootstrap now sees it complete
    } catch (e) {
      logComplete = false
      if (e.networkError) notice = "You're offline — marking complete needs a connection."
      else error = e.message
    }
  }
  // Re-open a completed log for editing. After it sticks, connect() rewires the full live
  // session (re-bootstrap returns log_complete=false -> normal path: SSE + vocabulary),
  // so a session opened via the render-only fast-path becomes editable without a reload.
  function markIncomplete() {
    error = ''
    if (!navigator.onLine) { notice = "You're offline — this needs a connection."; return }
    markIncompleteOpen = true
  }

  async function doMarkIncomplete() {
    try {
      const res = await sendOp(config, 'mark_incomplete', {})
      if (res.rejected) { notice = res.message || res.reason; return }
      logComplete = false
      connect() // rewire live editing (stream + vocabulary)
    } catch (e) {
      if (e.networkError) notice = "You're offline — this needs a connection."
      else error = e.message
    }
  }

  // Attribute (or clear) the set's starter: optimistic across all its tunes, one op.
  function setStarter(seg, personOrNull) {
    const firstId = seg.tunes[0].session_instance_tune_id
    const prevRecords = seg.tunes.map((t) => byId.get(t.session_instance_tune_id)).filter(Boolean)
    for (const r of prevRecords) {
      byId.set(r.session_instance_tune_id, {
        ...r,
        started_by_person_id: personOrNull?.person_id ?? null,
        started_by_name: personOrNull ? starterAbbrev(personOrNull) : null,
      })
    }
    const op_id = crypto.randomUUID()
    trySend({ op_id, op_type: 'attribute_set_starter', payload: { record_id: firstId, person_id: personOrNull?.person_id ?? null }, status: 'sending', ts: nextTs(), prevRecords })
    // Close the picker and the whole tray immediately; flash the new starter pill (top-right)
    // as confirmation (only when one was set, not on clear).
    closePicker()
    openTrayId = null
    if (personOrNull) {
      starterFlashId = firstId
      setTimeout(() => { if (starterFlashId === firstId) starterFlashId = null }, 800)
    }
  }

  function selectRow(id) {
    selectedId = selectedId === id ? null : id
  }

  // --- selection mode (spec 029): bulk select / copy / paste / delete / assign / move ---
  // Pure client UI state, never synced. Composes with the pull-down filter (selection
  // survives filter changes); positional actions (Paste, drag) need the filter clear.
  // In view mode it's copy-only: no grab bars, no Paste/Delete/Assign.
  let selectMode = $state(false)
  const selected = new SvelteSet() // selected tune record ids
  let shiftAnchor = null // last-tapped row: the shift-click range anchor
  let lastCopy = $state(null) // internal rich clipboard {text, rich}; survives exiting selection mode
  let undoDelete = $state(null) // {op_id, ids, records, count, seq} — the "Deleted N — Undo" toast
  let undoDeleteSeq = 0
  let assignOpen = $state(false)
  let assignFilter = $state('')
  const assignAttendees = $derived.by(() => {
    const f = assignFilter.trim().toLowerCase()
    // Only people actually checked in tonight -- `attendees` is now the whole roster.
    const here = attendees.filter((p) => p.attending)
    return f ? here.filter((p) => p.display_name.toLowerCase().includes(f)) : here
  })

  // Transient success feedback (copied/pasted/assigned): rides the same `notice` slot
  // but auto-dismisses. Sticky notices (offline warnings, rejections) still set
  // `notice` directly and stay until tapped; the seq guard means an older timer never
  // clobbers a newer message, transient or sticky.
  let noticeSeq = 0
  function flashNotice(text) {
    const seq = ++noticeSeq
    notice = text
    setTimeout(() => { if (noticeSeq === seq && notice === text) notice = '' }, 4000)
  }

  // --- my-list highlight mode: color/label every tune by MY learn status ---
  // Orthogonal to view/edit, the filter, and selection mode (it composes with
  // selection: select-by-status shortcuts + a bulk "My list" footer action). The
  // status shown is the SAME roll-up the tune-detail modal uses (mylist.js); the
  // scope droplist narrows it to one of my instruments. Pure personal state —
  // person_tune only, never the session log — so it works in view mode too.
  let listMode = $state(false)
  let listInstrument = $state('all') // 'all' or one of my instrument names
  let myInstruments = $state([]) // [{instrument, is_auto}] from /api/my-tunes
  const myList = new SvelteMap() // tune_id -> {learn_status, instrument_status}
  let listLoading = $state(false)
  let listLoaded = $state(false) // fetched once per page load; bulk updates keep it current locally
  let listStatusOpen = $state(false) // the bulk set-status modal
  let listBusy = $state(false) // a bulk status update is in flight

  function toggleListMode() {
    if (listMode) {
      listMode = false
      listStatusOpen = false
      return
    }
    if (searchMode) doneSearching() // the droplist replaces the filter box
    listMode = true
    if (!listLoaded) refreshMyList()
  }
  async function refreshMyList() {
    listLoading = true
    try {
      const d = await myTunesList()
      myList.clear()
      for (const t of d.tunes) {
        if (t.tune_id != null) myList.set(t.tune_id, { learn_status: t.learn_status, instrument_status: t.instrument_status || {} })
      }
      myInstruments = d.instruments || []
      if (listInstrument !== 'all' && !myInstruments.some((i) => i.instrument === listInstrument)) listInstrument = 'all'
      listLoaded = true
    } catch {
      listMode = false
      notice = "Couldn't load your tune list — this needs a connection."
    } finally {
      listLoading = false
    }
  }
  // Status for a log row under the current scope. null for breaks and unlinked
  // rows (no tune_id -> can't be on a list); those render without a chip. Also
  // null until the list has actually loaded — an empty map would paint every
  // tune "not on list" during the fetch.
  function rowListStatus(r) {
    if (!listLoaded || r.record_type !== 'tune' || r.tune_id == null) return null
    return listStatus(myList.get(r.tune_id), myInstruments, listInstrument)
  }
  // Select-by-status shortcut (additive, like "Select all"): every settled linked
  // tune currently SHOWING the given status chip.
  function selectByStatus(target) {
    for (const seg of displaySegments) {
      for (const t of seg.tunes) {
        if (t._temp || t._removing || t.tune_id == null) continue
        if (rowListStatus(t) === target) selected.add(t.session_instance_tune_id)
      }
    }
  }
  // Bulk add-to-list / set-status on the selection, scoped to the droplist's
  // instrument. Ops go one-per-tune through the modal's idempotent endpoint;
  // the cached list is updated locally as each tune lands (no refetch). The
  // selection is kept afterwards (cheap to layer another change on).
  async function applyListStatus(target) {
    listStatusOpen = false
    const tuneIds = [...new Set([...selected].map((id) => byId.get(id)?.tune_id).filter((t) => t != null))]
    const unlinked = [...selected].filter((id) => byId.get(id) && byId.get(id).tune_id == null).length
    const plans = planStatusOps(tuneIds, (tid) => myList.get(tid), myInstruments, listInstrument, target)
    if (!plans.length) {
      flashNotice(unlinked ? 'No change — unlinked tunes can’t be added to your list' : 'Already up to date')
      return
    }
    listBusy = true
    let done = 0
    let failed = 0
    for (const p of plans) {
      try {
        for (const op of p.ops) await myTunesOp({ ...op, tune_id: p.tune_id })
        myList.set(p.tune_id, applyStatusLocally(myList.get(p.tune_id), myInstruments, listInstrument, target))
        done++
      } catch {
        failed++
      }
    }
    listBusy = false
    const scope = listInstrument !== 'all' && myInstruments.length > 1 ? ` on ${listInstrument}` : ''
    const skipped = tuneIds.length - plans.length
    if (failed) notice = `Set ${done} of ${plans.length} tunes to “${target}”${scope} — ${failed} failed (offline?)`
    else flashNotice(`Set ${done} tune${done === 1 ? '' : 's'} to “${target}”${scope}${skipped ? ` · ${skipped} already there` : ''}`)
  }

  function enterSelectMode() {
    // State hygiene (spec 029 §A): close transient edit UI; a half-open edit with no
    // composer is a trap. Selection always starts empty. The cursor seam carries over.
    selectedId = null
    openTrayId = null
    closePicker()
    if (editingId != null) cancelEdit()
    selected.clear()
    shiftAnchor = null
    selectMode = true
  }
  function exitSelectMode() {
    selectMode = false
    selected.clear()
    shiftAnchor = null
    assignOpen = false
    cancelDrag()
  }
  const toggleSelectMode = () => (selectMode ? exitSelectMode() : enterSelectMode())

  // Tap = toggle; shift-tap = range from the anchor (desktop). Placeholder/temp/
  // removing rows aren't selectable (no settled id for a bulk op to address).
  function toggleSelect(r, e) {
    if (r._temp || r._removing || r._resolving) return
    const id = r.session_instance_tune_id
    if (e?.shiftKey && shiftAnchor != null) {
      for (const rid of rangeBetween(ordered, shiftAnchor, id)) selected.add(rid)
      shiftAnchor = id
      return
    }
    selected.has(id) ? selected.delete(id) : selected.add(id)
    shiftAnchor = id
  }
  // Remote deletions silently leave the selection (the activity toast explains the
  // count dropping); remote moves don't touch it (ids are stable).
  $effect(() => {
    if (!selected.size) return
    for (const id of [...selected]) {
      const r = byId.get(id)
      if (!r || r.deleted) selected.delete(id)
    }
  })
  // "Select all" respects the filter: only matching tunes when one is active (§B).
  function selectAllVisible() {
    for (const id of selectableIds(displaySegments, searchMode ? searchText : '')) selected.add(id)
  }
  function selectNone() { selected.clear(); shiftAnchor = null }

  // Copy (§D): rich internal clipboard + plain text (lines = sets, commas = tunes —
  // the old pill logger's system-clipboard format) so cross-app paste works.
  async function copySelection() {
    const clip = serializeClipboard(segments, selected)
    if (!clip) return
    lastCopy = clip
    try { await navigator.clipboard.writeText(clip.text) } catch { /* internal clipboard still set */ }
    const n = clip.rich.reduce((s, set) => s + set.length, 0)
    flashNotice(`Copied ${n} tune${n === 1 ? '' : 's'} in ${clip.rich.length} set${clip.rich.length === 1 ? '' : 's'}`)
  }

  // Paste (§D): three-case resolution — our own last copy pastes RICH (links survive);
  // old-logger JSON maps to adds; plain text re-matches server-side. A blocked
  // clipboard read falls back to the internal clipboard.
  async function pasteClipboard() {
    if (viewing || searchMode) return
    let text = ''
    try { text = await navigator.clipboard.readText() } catch { /* read blocked — internal fallback */ }
    const plan = parseClipboard(text, lastCopy) || (lastCopy ? { kind: 'internal', sets: lastCopy.rich } : null)
    if (!plan || !plan.sets.length) { flashNotice('Nothing to paste'); return }
    await pasteSets(plan.sets)
  }

  // Sequential add_tune/set_break ops anchored at the cursor seam — awaited one by
  // one so each op's temp anchor is settled (or queued for remap on flush) before the
  // next sends. To other clients this looks like fast logging. no_merge: a pasted
  // duplicate must never corroborate-collapse (the old logger's paste also always adds).
  // advanceCursor (the composer paste): a mid-insert cursor follows the pasted block,
  // exactly as typed-Enter entries would, so burst entry continues after it.
  async function pasteSets(sets, { advanceCursor = false } = {}) {
    const c = insertAfterId
    const newSetTarget = c && typeof c === 'object' && c.newSet != null ? c.newSet : null
    let afterAnchor = null
    let beforeAnchor = null
    let prevPos = null // optimistic key chain bounds
    let succPos = null
    if (newSetTarget != null) {
      beforeAnchor = newSetTarget
      const idx = ordered.findIndex((r) => r.session_instance_tune_id === newSetTarget)
      succPos = idx >= 0 ? ordered[idx].order_position : null
      prevPos = idx > 0 ? ordered[idx - 1].order_position : null
    } else {
      const p = cursorPos(insertAfterId, ordered, [...byId.values()])
      afterAnchor = p.afterId
      beforeAnchor = p.beforeId
      // p.position is the key for the FIRST pasted row; chain the rest behind it
      prevPos = null
      succPos = null
      if (beforeAnchor != null) {
        const idx = ordered.findIndex((r) => r.session_instance_tune_id === beforeAnchor)
        succPos = idx >= 0 ? ordered[idx].order_position : null
        prevPos = idx > 0 ? ordered[idx - 1].order_position : null
      } else if (afterAnchor != null) {
        const idx = ordered.findIndex((r) => r.session_instance_tune_id === afterAnchor)
        prevPos = idx >= 0 ? ordered[idx].order_position : null
        succPos = idx >= 0 && idx + 1 < ordered.length ? ordered[idx + 1].order_position : null
      } else {
        prevPos = maxPos(byId.values())
      }
    }
    let prevTempId = null
    let total = 0
    for (let si = 0; si < sets.length; si++) {
      if (si > 0) {
        // break between pasted sets, anchored after the previous set's last tune
        const bop = crypto.randomUUID()
        const btmp = `temp-${bop}`
        const bkey = generateBetween(prevPos, succPos)
        byId.set(btmp, { session_instance_tune_id: btmp, record_type: 'break', order_position: bkey, deleted: false, _temp: true })
        await trySend({ op_id: bop, op_type: 'set_break', payload: { action: 'insert', after_record_id: prevTempId }, status: 'sending', ts: nextTs(), tempId: btmp })
        prevPos = bkey
        prevTempId = btmp // next tune anchors after the BREAK, not before it
      }
      for (const t of sets[si]) {
        const op_id = crypto.randomUUID()
        const tempId = `temp-${op_id}`
        const key = generateBetween(prevPos, succPos)
        byId.set(tempId, {
          session_instance_tune_id: tempId, name: t.name, tune_id: t.tune_id ?? null, tune_type: t.tune_type ?? null,
          record_type: 'tune', order_position: key, deleted: false, _temp: true, _status: 'sending',
        })
        const payload = {
          tune_id: t.tune_id ?? null, name: t.name, no_merge: true,
          after_record_id: prevTempId ?? afterAnchor, before_record_id: prevTempId ? null : (afterAnchor ? null : beforeAnchor),
        }
        // Advance BEFORE the send: the ack's temp→real remap chases insertAfterId, so
        // setting it after the await could leave it on an already-retired temp id.
        if (advanceCursor && insertAfterId != null) insertAfterId = tempId
        await trySend({ op_id, name: t.name, op_type: 'add_tune', payload, status: 'sending', ts: nextTs(), tempId })
        prevTempId = tempId
        prevPos = key
        total++
      }
    }
    if (newSetTarget != null && prevTempId) {
      // close the pasted block off from the following set (mirrors addNewSetTune)
      const bop = crypto.randomUUID()
      const btmp = `temp-${bop}`
      const bkey = generateBetween(prevPos, succPos)
      byId.set(btmp, { session_instance_tune_id: btmp, record_type: 'break', order_position: bkey, deleted: false, _temp: true })
      await trySend({ op_id: bop, op_type: 'set_break', payload: { action: 'insert', before_record_id: newSetTarget }, status: 'sending', ts: nextTs(), tempId: btmp })
    }
    flashNotice(`Pasted ${total} tune${total === 1 ? '' : 's'} in ${sets.length} set${sets.length === 1 ? '' : 's'}`)
  }

  // Bulk delete (§E): ONE atomic remove_tunes op + an Undo toast wired to the
  // restore_tunes inverse op — undo over confirm for a destructive bulk action.
  function bulkDelete() {
    if (viewing || !selected.size) return
    const ids = [...selected].filter((id) => {
      const r = byId.get(id)
      return r && !r._temp && !r._removing && typeof id === 'number'
    })
    if (!ids.length) return
    const op_id = crypto.randomUUID()
    const records = ids.map((id) => byId.get(id))
    for (const id of ids) byId.set(id, { ...byId.get(id), _removing: op_id })
    trySend({ op_id, op_type: 'remove_tunes', payload: { record_ids: ids }, status: 'sending', ts: nextTs(), bulkRemoveIds: ids })
    selected.clear()
    shiftAnchor = null
    const seq = ++undoDeleteSeq
    undoDelete = { op_id, ids, records, count: ids.length, seq }
    setTimeout(() => { if (undoDelete && undoDelete.seq === seq) undoDelete = null }, 8000)
  }
  function undoBulkDelete() {
    const u = undoDelete
    undoDelete = null
    if (!u) return
    const entry = pending.get(u.op_id)
    if (entry && entry.status === 'queued') {
      // the delete never reached the server (offline) — cancel it locally, like restore()
      dropPending(u.op_id)
      for (const id of u.ids) {
        const r = byId.get(id)
        if (r && r._removing) { const { _removing, ...rest } = r; byId.set(id, rest) }
      }
      return
    }
    // already sent/settled: optimistic re-add + the inverse op (streams to everyone)
    for (const r of u.records) if (r) byId.set(r.session_instance_tune_id, { ...r, deleted: false, _removing: undefined })
    trySend({ op_id: crypto.randomUUID(), op_type: 'restore_tunes', payload: { record_ids: u.ids }, status: 'sending', ts: nextTs(), restoredIds: u.ids })
  }

  // Assign (§G): one attribute_set_starter per set containing a selected tune —
  // stamps the WHOLE set (started_by means the set). Selection is kept afterwards
  // so a mis-pick is cheap to correct.
  function openAssign() {
    if (!selected.size) return
    assignOpen = true
    assignFilter = ''
    if (!attendeesLoaded) refreshAttendees()
  }
  function assignTo(personOrNull) {
    const segs = segments.filter((seg) => seg.tunes.some((t) => selected.has(t.session_instance_tune_id)))
    for (const seg of segs) setStarter(seg, personOrNull)
    assignOpen = false
    const n = segs.length
    flashNotice(personOrNull
      ? `Assigned ${n} set${n === 1 ? '' : 's'} to ${personOrNull.display_name}`
      : `Cleared the starter on ${n} set${n === 1 ? '' : 's'}`)
  }

  // --- drag-to-move (§F): pointer events on the grab bar, seams as drop zones ---
  let drag = $state(null) // {block, targets, keys, activeKey, x, y, startX, startY, started, name}
  let dragRAF = null
  let dragPointerY = 0
  const dragKeys = $derived(drag?.started ? drag.keys : null)
  function startDrag(e, r) {
    if (viewing || searchMode || !selectMode) return
    const block = dragBlock(ordered, selected, r.session_instance_tune_id)
    if (!block) return
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    const targets = dropTargets(ordered, displaySegments, endIsOpen, block.recordIds)
    drag = {
      block, targets, keys: new Set(targets.map((t) => t.key)), activeKey: null,
      x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY, started: false,
      name: r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)'),
    }
  }
  function dragMove(e) {
    if (!drag) return
    dragPointerY = e.clientY
    if (!drag.started) {
      if (Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) < 6) return // slop
      drag = { ...drag, started: true }
      if (!dragRAF) dragRAF = requestAnimationFrame(autoScrollTick)
    }
    drag = { ...drag, x: e.clientX, y: e.clientY }
    hitTestDrop()
  }
  function dragEnd() {
    if (!drag) return
    const t = drag.started && drag.activeKey ? drag.targets.find((x) => x.key === drag.activeKey) : null
    if (t) performMove(t)
    cancelDrag()
  }
  function cancelDrag() {
    drag = null
    if (dragRAF) { cancelAnimationFrame(dragRAF); dragRAF = null }
  }
  // Nearest eligible seam to the pointer's y (fat fingers: interval distance, capped).
  function hitTestDrop() {
    if (!drag?.started || !setsEl) return
    let best = null
    let bestD = Infinity
    for (const el of setsEl.querySelectorAll('[data-seam]')) {
      const key = el.dataset.seam
      if (!drag.keys.has(key)) continue
      const rect = el.getBoundingClientRect()
      const d = Math.abs((rect.top + rect.bottom) / 2 - dragPointerY)
      if (d < bestD) { bestD = d; best = key }
    }
    const activeKey = bestD < 90 ? best : null
    if (activeKey !== drag.activeKey) drag = { ...drag, activeKey }
  }
  // Autoscroll near the list edges, speed proportional to proximity (§F).
  function autoScrollTick() {
    dragRAF = null
    if (!drag?.started || !setsEl) return
    const rect = setsEl.getBoundingClientRect()
    const M = 48
    let dy = 0
    if (dragPointerY < rect.top + M) dy = -Math.ceil((rect.top + M - dragPointerY) / 4)
    else if (dragPointerY > rect.bottom - M) dy = Math.ceil((dragPointerY - (rect.bottom - M)) / 4)
    if (dy) { setsEl.scrollTop += dy; hitTestDrop() }
    dragRAF = requestAnimationFrame(autoScrollTick)
  }
  // Drop: optimistic local reorder (same exclude-the-block key rule as the server,
  // so the settle doesn't jump) + ONE move_tunes op. new_set boundary breaks render
  // as temp rows that the settling event replaces.
  function performMove(t) {
    const { positions, tempBreakKeys } = optimisticMove(ordered, [...byId.values()], drag.block.recordIds, t)
    const prevRecords = drag.block.recordIds.map((id) => byId.get(id)).filter(Boolean).map((r) => ({ ...r }))
    for (const [id, key] of positions) {
      const r = byId.get(id)
      if (r) byId.set(id, { ...r, order_position: key })
    }
    const op_id = crypto.randomUUID()
    const tempIds = []
    for (const side of ['before', 'after']) {
      const k = tempBreakKeys[side]
      if (k) {
        const tid = `temp-${op_id}-${side}`
        byId.set(tid, { session_instance_tune_id: tid, record_type: 'break', order_position: k, deleted: false, _temp: true })
        tempIds.push(tid)
      }
    }
    trySend({
      op_id, op_type: 'move_tunes',
      payload: { record_ids: drag.block.tuneIds, after_record_id: t.after_record_id, before_record_id: t.before_record_id, new_set: t.new_set },
      status: 'sending', ts: nextTs(), prevRecords, tempIds,
    })
    flashId(drag.block.tuneIds[0], 'mine')
    insertAfterId = drag.block.tuneIds[drag.block.tuneIds.length - 1] // cursor lands after the block
  }

  // Toggle View <-> Edit (spec 021 §A2–3). Leaving edit drops every transient editing
  // affordance; the SSE then reconnects so the server learns this connection's new
  // presence intent — a viewer asserts nothing (spec 024 §presence).
  function setMode(m) {
    if (readOnly) return // signed-out viewers never leave view mode
    if (mode === m) return
    mode = m
    if (m === 'view') {
      if (editingId != null) cancelEdit()
      else clearEntry()
      selectedId = null
      insertAfterId = null
      closePicker()
      openTrayId = null
      expanded = false
    }
    if (m === 'edit') {
      // Drop you at the end of the log, ready to append the next tune. Wait two frames so
      // the composer dock has rendered (it grows scrollHeight) before we measure the bottom.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (setsEl) setsEl.scrollTo({ top: setsEl.scrollHeight, behavior: 'smooth' })
      }))
    }
    if (!fromCacheOnly()) connect() // re-open the stream with the new mode= flag
  }
  // Leave the pull-down filter: remember the term, clear the query, restore the underlying
  // view/edit controls, and scroll the bar out of view. Never touches `mode` or the stream.
  // Both the "Done Searching" button and the filter's clear "✕" route here, so clearing the
  // filter always drops search mode too (not just the text).
  function doneSearching() {
    rememberInHistory(filterHist, searchText)
    if (filterRememberTimer) { clearTimeout(filterRememberTimer); filterRememberTimer = null }
    filterHistPos = null
    searchText = ''
    searchMode = false
    if (searchInputEl) searchInputEl.blur()
    if (setsEl) setsEl.scrollTo({ top: SEARCH_BAR_H, behavior: 'smooth' })
  }
  // Reconnecting requires the server; while offline we just flip the UI (presence is
  // already dropped offline) and let the next reconnect carry the current mode.
  function fromCacheOnly() {
    return !online || !reachable
  }
  function predecessorId(id) {
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === id)
    return idx > 0 ? ordered[idx - 1].session_instance_tune_id : null
  }
  function insertAfterRow(id) {
    setCursor(id) // cursor right after this tune; focuses composer + deselects
  }
  function insertBeforeRow(id) {
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === id)
    const pred = idx > 0 ? ordered[idx - 1] : null
    // mid-set: cursor after the previous tune. start-of-set (pred is a break) or
    // start-of-session (no pred): use the before-anchor so it lands at the set's front.
    if (pred && pred.record_type !== 'break') setCursor(pred.session_instance_tune_id)
    else setCursor({ before: id })
  }
  function confirmRow(id) {
    // Optimistic + offline-queued (like change/remove/set-starter): patch confidence,
    // reconcile by op_id, undo on reject. Works offline via trySend's queue (§G).
    const prev = byId.get(id)
    if (prev) byId.set(id, { ...prev, confidence: 100 })
    const op_id = crypto.randomUUID()
    flashId(id)
    trySend({ op_id, op_type: 'set_confidence', payload: { record_id: id, confidence: 100 }, status: 'sending', ts: nextTs(), prev })
    selectedId = null
  }
  function removeRow(id) {
    removeTune(id)
    selectedId = null
  }

  // --- edit / relink (spec 021 §E; change_tune op) ---
  // Edit re-opens the composer pre-filled with the tune's name: pick a search
  // result to relink, Enter to rename/re-match, or Unlink to drop the catalog link.
  function startEdit(id) {
    const r = byId.get(id)
    if (!r || r._temp) return
    editingId = id
    editingName = r.name || ''
    selectedId = null
    // The edited tune IS the cursor location: no seam is shown or scrolled to while
    // editing (the row's yellow highlight marks the spot), and when the edit ends the
    // cursor surfaces right after this tune instead of jumping to the end of the list.
    insertAfterId = id
    input = r.name || ''
    runSearch()
    queueMicrotask(() => { inputEl?.focus(); inputEl?.select() })
  }
  function cancelEdit() {
    editingId = null
    editingName = ''
    clearEntry()
  }

  // Apply a change_tune optimistically (patch the record now; reconcile on ack/SSE),
  // stashing the prior record so a rejection can roll it back.
  function sendChange(record_id, payload, patch) {
    const prev = byId.get(record_id)
    if (prev) byId.set(record_id, { ...prev, ...patch })
    const op_id = crypto.randomUUID()
    flashId(record_id)
    trySend({ op_id, op_type: 'change_tune', payload: { record_id, ...payload }, status: 'sending', ts: nextTs(), prev })
  }

  // Relink the edited record to a catalog tune (from a tapped/Enter-picked result).
  function relinkTo(t) {
    const id = editingId
    cancelEdit()
    sendChange(id, { tune_id: t.tune_id, name: t.name }, { tune_id: t.tune_id, name: t.name, tune_type: t.tune_type ?? null, confidence: 100 })
  }
  // Unlink: keep the text, drop the catalog link (becomes a raw name).
  function unlinkEdit() {
    const id = editingId
    cancelEdit()
    sendChange(id, { unlink: true }, { tune_id: null, tune_type: null })
  }
  // Enter while editing: mirror add's commit — pick the top match if one fits the
  // current text (relink), else rename in place to the typed text (unlinked).
  async function commitEdit() {
    const id = editingId
    const q = input.trim()
    if (!q) { cancelEdit(); return }
    if (resultsQuery === q && results.length) { relinkTo(results[0]); return }
    const m = await matchFor(q)
    if (m.results.length) { relinkTo(m.results[0]); return }
    cancelEdit()
    sendChange(id, { name: q, unlink: true }, { name: q, tune_id: null, tune_type: null })
  }

  // Reuse the legacy tune-detail modal (window.TuneDetailModal) so it matches the
  // rest of the app exactly (same layout + cached incipit rendering, no custom code).
  function openDrawer(r) {
    selectedId = null
    if (!r.tune_id) {
      notice = 'Logged as text — link it to a catalog tune to see details, notation, and stats.'
      return
    }
    if (!window.TuneDetailModal) return
    window.TuneDetailModal.show({
      tuneId: r.tune_id,
      // the instance scope keeps the session_instance variant (wording, stats,
      // per-instance config); everything else the drawer derives from the payload
      scope: { session: config.sessionPath, instance: config.sessionInstanceId },
      tuneName: r.name,
      // Apply the sheet's edit (key override, name, setting) to the log immediately.
      // The save also broadcasts a change_tune event, but the editor's own screen must
      // not depend on the round trip: offline, or with the stream down, that never
      // arrives and the row would keep showing the old key until a reload. put() is
      // idempotent, so the echo that follows is a no-op.
      onSave: (data) => { for (const rec of data?.records || []) put(rec) },
    })
    // background-render+cache the notation (incipit + full) so the drawer shows dots
    // next time (the abc-renderer service does the rendering, never the client)
    fetchIncipit(config, r.tune_id, 'both')
  }

  // Optimistic rows (add tunes AND breaks) live in byId as temp records with a
  // sortable position, so they segment into sets uniformly. Display = the sets,
  // narrowed to sets with a name match while the pull-down filter is active.
  function tuneNameMatches(r, q) {
    return r.record_type === 'tune' && (r.name || '').toLowerCase().includes(q)
  }
  const displaySegments = $derived.by(() => {
    if (!searchMode) return segments
    const q = searchText.trim().toLowerCase()
    if (!q) return segments // empty query → show all, no highlight
    return segments.filter((seg) => seg.tunes.some((r) => tuneNameMatches(r, q)))
  })
  // "Likely next tune" (§ likely-next): when the composer sits at the END of a non-empty
  // set, the tune that follows that set's last tune >50% of the time at this session (from
  // nextByTuneId). At most one. Null mid-set, at a set start, while editing/resolving, in
  // view mode, or when the successor is already in the set (a redundant pick).
  const nextSuggestion = $derived.by(() => {
    if (viewing || logComplete || editingId != null || resolving) return null
    if (insertAfterId && typeof insertAfterId === 'object') return null // before/new-set: not end-of-set
    const seg = cursorSegment()
    if (!seg || !seg.tunes.length) return null
    const last = seg.tunes[seg.tunes.length - 1]
    // anchor = the tune just before the cursor, only when the cursor is at the set's end
    if (insertAfterId != null && last.session_instance_tune_id !== insertAfterId) return null
    if (last.record_type === 'break' || last.tune_id == null) return null
    const nx = nextByTuneId.get(last.tune_id)
    if (!nx) return null
    if (dismissedNext.has(nextAssocKey(last.tune_id, nx.tune_id))) return null // dismissed this session
    if (currentSetTuneIds().has(nx.tune_id)) return null // already in this set -> suppress
    return nx
  })
  // The suggestion stays pinned while the typed text is an (accent-insensitive) substring of
  // its name — you may simply not have noticed it was already there. Empty box -> always show.
  const nextMatches = $derived.by(() => {
    if (!nextSuggestion) return false
    const q = normName(input)
    return !q || normName(nextSuggestion.name).includes(q)
  })
  const showNext = $derived(!viewing && !composerLocked && composerFocused && nextMatches)
  // Silence the current anchor->suggestion pairing for the rest of this session (memory only).
  function dismissNext() {
    const nx = nextSuggestion
    if (!nx) return
    const seg = cursorSegment()
    const last = seg && seg.tunes.length ? seg.tunes[seg.tunes.length - 1] : null
    if (last && last.tune_id != null) dismissedNext.add(nextAssocKey(last.tune_id, nx.tune_id))
  }
  // Don't list the suggested tune twice (pinned row + a normal result below it).
  const visibleResults = $derived(
    showNext && nextSuggestion ? results.filter((r) => r.tune_id !== nextSuggestion.tune_id) : results
  )
  // Split the suggestion name around the typed substring so it can be bolded. Raw
  // case-insensitive match (not normName) so the slice indices line up with the display
  // string; an accent-only match just renders unbolded.
  function suggestionParts(name, q) {
    const raw = (q || '').trim()
    if (!raw) return { pre: name, mid: '', post: '' }
    const i = name.toLowerCase().indexOf(raw.toLowerCase())
    if (i < 0) return { pre: name, mid: '', post: '' }
    return { pre: name.slice(0, i), mid: name.slice(i, i + raw.length), post: name.slice(i + raw.length) }
  }

  // Is the type-ahead dropdown currently rendered? (gates the bottom spacer + band calc)
  const dropdownOpen = $derived(!viewing && (showNext || results.length > 0 || tsInputId != null || (noMatch && editingId == null)))

  // --- keyboard nav of the composer dropdown (spec 028 desktop) ---------------------
  // The arrow-navigable rows, in visual BOTTOM-TO-TOP order (the list is column-reverse,
  // so results[0] sits nearest the input and the suggestion just below it): index 0 is
  // the pinned suggestion (if shown), then the search results going up. ArrowUp walks up
  // the stack (index+1), ArrowDown back toward the input (index-1). Enter picks the
  // highlighted row; -1 means none is highlighted (Enter falls back to its default).
  const composerNavItems = $derived(
    showNext && nextSuggestion ? [nextSuggestion, ...visibleResults] : visibleResults
  )
  // Keep the highlight valid as results stream in/out; never auto-jump to a row.
  $effect(() => { if (composerHl >= composerNavItems.length) composerHl = -1 })
  function moveComposerHl(dir) {
    const n = composerNavItems.length
    if (!n) return false
    let i = composerHl
    i = i < 0 ? (dir > 0 ? 0 : n - 1) : Math.max(0, Math.min(n - 1, i + dir))
    composerHl = i
    queueMicrotask(() => document.querySelector('.results li.hl')?.scrollIntoView({ block: 'nearest' }))
    return true
  }

  // A position after everything currently present, so optimistic appends stay last
  // and stay ordered among themselves (base-62 order_position; 'z' is the max char).
  function nextTempPos() {
    let max = ''
    for (const r of byId.values()) if (r.order_position && r.order_position > max) max = r.order_position
    return max + 'z'
  }

  const colorForPerson = (pid) => {
    const p = roster.find((r) => r.person_id === pid)
    return p ? colorFor(p.arrival_seq) : 'var(--muted)'
  }

  function remoteLabel(d) {
    const n = d.record?.name || (d.record?.tune_id ? `#${d.record.tune_id}` : 'a tune')
    switch (d.op_type) {
      case 'add_tune': return `added ${n}`
      case 'corroborate': return `also logged ${n}`
      case 'change_tune': return `edited ${n}`
      case 'remove_tune': return `removed ${n}`
      case 'move_tunes': { const c = d.moved_ids?.length || 0; return `moved ${c} tune${c === 1 ? '' : 's'}` }
      case 'remove_tunes': { const c = d.records?.length || 0; return `removed ${c} tune${c === 1 ? '' : 's'}` }
      case 'restore_tunes': { const c = d.records?.length || 0; return `restored ${c} tune${c === 1 ? '' : 's'}` }
      case 'set_break': return d.removed ? 'removed a break' : 'ended a set'
      case 'attribute_set_starter': return d.person ? `set ${d.person.display_name} as starting a set` : 'cleared a set starter'
      case 'set_confidence': return `confirmed ${n}`
      case 'attendance_add': return d.person ? `checked in ${d.person.display_name}` : 'updated attendance'
      case 'attendance_create_person': return d.person ? `added ${d.person.display_name}` : 'added a player'
      case 'attendance_remove': return d.person ? `checked out ${d.person.display_name}` : 'updated attendance'
      case 'edit_notes': return 'edited the notes'
      // One op, up to two distinct edits — say which actually happened, or the
      // toast claims someone re-dated a log when they only fixed the end time.
      case 'set_date': {
        const movedDate = d.previous_date != null && d.date !== d.previous_date
        const movedTimes =
          ('start_time' in d && d.start_time !== d.previous_start_time) ||
          ('end_time' in d && d.end_time !== d.previous_end_time)
        const when = instanceTimeLabel({ start_time: d.start_time, end_time: d.end_time })
        if (movedDate && movedTimes && d.session_date) return `re-dated this log to ${d.session_date}${when ? `, ${when}` : ''}`
        if (movedDate) return d.session_date ? `re-dated this log to ${d.session_date}` : 're-dated this log'
        if (movedTimes) return when ? `set this log's time to ${when}` : "cleared this log's time"
        return 're-dated this log'
      }
      case 'set_name': return d.instance_name ? `named this log "${d.instance_name}"` : "cleared this log's name"
      default: return null
    }
  }

  // A change made by someone else — surface a brief, attributed activity notice (§E).
  // In edit mode we skip your own changes (you just made them). In view mode this
  // window authors nothing, so every incoming change is "remote" worth showing — even
  // one from your own account logging in another window.
  function noteRemote(d) {
    if (!d.actor || d.actor.person_id == null) return
    if (!viewing && d.actor.person_id === person.person_id) return
    const label = remoteLabel(d)
    if (!label) return
    const id = ++activityId
    // Append; keep only the most recent MAX_TOASTS so a burst from several people
    // stacks (newest at the bottom) instead of one clobbering the last.
    activities = [...activities, { id, text: `${d.actor.name || 'Someone'} ${label}`, color: colorForPerson(d.actor.person_id) }].slice(-MAX_TOASTS)
    setTimeout(() => { activities = activities.filter((a) => a.id !== id) }, 4000)
  }

  // Apply one server-authoritative op (spec 024). Dispatch by op_type.
  function applyOp(d) {
    if (d.op_id && pending.has(d.op_id)) {
      const entry = pending.get(d.op_id) // settle our optimistic/queued op...
      if (entry.tempId) {
        if (d.record) tempToReal.set(entry.tempId, d.record.session_instance_tune_id) // anchor remap (#5b)
        if (insertAfterId === entry.tempId) insertAfterId = d.record?.session_instance_tune_id ?? null
        byId.delete(entry.tempId) // ...drop its optimistic temp record
      }
      if (entry.tempIds) for (const t of entry.tempIds) byId.delete(t) // optimistic move boundary breaks
      dropPending(d.op_id) // ...and drop it from the persisted queue (already applied)
    }
    if (d.event_id && d.event_id > highWater) highWater = d.event_id
    noteRemote(d)
    const prevLastId = lastRecordId // before applying, to detect an append at the end
    switch (d.op_type) {
      case 'attribute_set_starter': // applies to the whole set -> many records
        for (const r of d.records || []) put(r)
        // no tune-row flash here — the starter pill flash is the confirmation
        break
      case 'add_tune':
      case 'change_tune':
      case 'set_confidence':
      case 'corroborate': // server collapsed a duplicate into this record (§H30)
        put(d.record)
        {
          const rid = d.record?.session_instance_tune_id
          if (d.op_type === 'corroborate') flashId(rid, 'merge')
          else if (d.actor && d.actor.person_id === person.person_id) flashId(rid, 'mine')
          else flashId(rid, 'remote', d.actor ? colorForPerson(d.actor.person_id) : null)
        }
        // Live-logging follow-the-end (§E): if my cursor was parked right after the
        // previously-last tune and someone's tune just landed at the very end, move
        // my cursor to the end so my next add goes AFTER theirs, not before.
        if (
          typeof insertAfterId === 'number' && insertAfterId === prevLastId &&
          d.record?.record_type === 'tune' &&
          lastRecordId === d.record.session_instance_tune_id
        ) {
          insertAfterId = null
        }
        break
      case 'set_break':
        if (d.removed) drop(d.record_id)
        else put(d.record)
        break
      case 'remove_tune':
        if (d.record) (d.record.deleted ? drop(d.record.session_instance_tune_id) : put(d.record))
        break
      case 'move_tunes': // one atomic block move (spec 029 §F)
        for (const r of d.records || []) put(r)
        for (const id of d.removed_break_ids || []) drop(id)
        if (d.actor && d.actor.person_id !== person.person_id) {
          for (const id of d.moved_ids || []) flashId(id, 'remote', colorForPerson(d.actor.person_id))
        }
        break
      case 'remove_tunes': // atomic bulk delete (spec 029 §E)
        for (const r of d.records || []) drop(r.session_instance_tune_id)
        break
      case 'restore_tunes': // the delete's inverse op (undo)
        for (const r of d.records || []) put(r)
        break
      case 'attendance_add':
      case 'attendance_remove':
      case 'attendance_create_person':
        refreshAttendees() // keep the roster/picker list current across clients
        break
      case 'edit_notes': {
        const wasClean = notesDraft === notesText
        notesText = d.notes || ''
        if (wasClean) notesDraft = notesText // don't clobber an in-progress local edit
        break
      }
      case 'set_date':
        applyDate(d)
        break
      case 'set_name':
        applyName(d)
        break
      case 'mark_complete':
        logComplete = true
        if (mode === 'edit') setMode('view') // completion locks editing for everyone
        break
      case 'mark_incomplete':
        logComplete = false
        break
    }
    scheduleSnapshot() // keep the offline snapshot fresh
  }

  // Hold an op for reconnect replay (persisted to IndexedDB, §G).
  // Reflect an op's status on its optimistic temp record (sending vs queued).
  function markTempStatus(entry, st) {
    if (entry.tempId && byId.has(entry.tempId)) byId.set(entry.tempId, { ...byId.get(entry.tempId), _status: st })
  }

  async function markQueued(entry) {
    entry.status = 'queued'
    entry._queued = true // so a later corroborate-on-flush doesn't pop the merge nudge
    pending.set(entry.op_id, entry)
    markTempStatus(entry, 'queued')
    await queuePut({
      op_id: entry.op_id, op_type: entry.op_type, payload: entry.payload,
      name: entry.name, ts: entry.ts, session_instance_id: config.sessionInstanceId,
    })
  }

  // Revert an op's optimistic effect when it fails/rejects.
  function undoOp(entry) {
    if (entry.op_type === 'remove_tune') {
      const r = byId.get(entry.payload.record_id)
      if (r && r._removing === entry.op_id) {
        const { _removing, ...rest } = r
        byId.set(r.session_instance_tune_id, rest)
      }
    }
    if (entry.tempId) byId.delete(entry.tempId)
    if (entry.tempIds) for (const t of entry.tempIds) byId.delete(t) // optimistic move boundary breaks
    if (entry.restoreRecord) byId.set(entry.restoreRecord.session_instance_tune_id, entry.restoreRecord) // un-join
    if ((entry.op_type === 'change_tune' || entry.op_type === 'set_confidence') && entry.prev) byId.set(entry.prev.session_instance_tune_id, entry.prev) // revert edit / confirm
    if (entry.prevRecords) for (const r of entry.prevRecords) byId.set(r.session_instance_tune_id, r) // revert set-starter / move
    if (entry.bulkRemoveIds) { // rejected bulk delete: clear the removing marks
      for (const id of entry.bulkRemoveIds) {
        const r = byId.get(id)
        if (r && r._removing) { const { _removing, ...rest } = r; byId.set(id, rest) }
      }
    }
    if (entry.restoredIds) for (const id of entry.restoredIds) drop(id) // rejected restore: rows stay gone
  }

  function settleOp(entry, res) {
    dropPending(entry.op_id)
    if (res.rejected) {
      undoOp(entry)
      // An offline-originated op that the server rejected on flush is collected for the
      // reconciliation review (§G) — losing offline work to a transient toast is too easy
      // to miss. Online rejections stay a quick inline notice.
      if (entry._queued && flushingNow) {
        flushRejects.push({ op_type: entry.op_type, name: entry.name || entry.payload?.name || null, reason: res.reason, message: res.message })
      } else {
        notice = res.message || `${entry.op_type}: ${res.reason}`
      }
      return
    }
    if (entry.tempId) byId.delete(entry.tempId) // drop optimistic temp; the real record arrives below / via SSE
    if (entry.tempIds) for (const t of entry.tempIds) byId.delete(t) // optimistic move boundary breaks
    if (entry.tempId && res.record) tempToReal.set(entry.tempId, res.record.session_instance_tune_id) // for anchor remap (#5b)
    if (res.records) for (const r of res.records) put(r) // multi-record ops (set-starter, bulk ops)
    if (res.removed_break_ids) for (const id of res.removed_break_ids) drop(id) // move_tunes source cleanup
    if (res.record) {
      if (insertAfterId === entry.tempId) insertAfterId = res.record.session_instance_tune_id // cursor follows to the real id
      put(res.record) // settle now if the ack beat the SSE echo (idempotent)
      flashId(res.record.session_instance_tune_id, res.op_type === 'corroborate' ? 'merge' : 'mine')
    }
    // An ack landing while a bootstrap is in flight may postdate that bootstrap's DB
    // read; remember it so the snapshot apply can re-put it instead of wiping the row
    // until SSE catch-up (see lateSettles at connect()).
    if (bootstrapInFlight && res.event_id && (res.record || res.records)) {
      lateSettles.push({ event_id: res.event_id, records: [...(res.records || []), ...(res.record ? [res.record] : [])] })
    }
    // My append collapsed into an existing tune (§H30/§D16). Surface a gentle nudge so
    // the merge is visible and reversible ("keep both"), rather than silent.
    if (entry.op_type === 'add_tune' && res.op_type === 'corroborate' && !entry._queued) {
      const seq = ++mergeNudgeSeq
      mergeNudge = { name: entry.name || res.record?.name || 'that tune', payload: entry.payload }
      setTimeout(() => { if (seq === mergeNudgeSeq) mergeNudge = null }, 7000)
    }
  }

  // Replace temp anchor/target ids in an op's payload with their real server ids
  // (#5b). Anchors (after/before_record_id) that are still unresolved fall back to
  // null (append) rather than erroring; an unresolved record_id target means the row
  // never persisted, so the op is skipped. Returns a COPY (entry.payload is kept for
  // local byId lookups, which are still keyed by the temp id until settle).
  // remapAnchors now lives in logstate.js (pure, unit-tested).

  // Send a pending op (any type). Success -> settle; network failure -> queue it
  // (persisted for replay); server error -> undo + surface. Idempotent by op_id.
  async function trySend(entry, fromFlush = false) {
    entry.status = 'sending'
    pending.set(entry.op_id, entry)
    // Fast-path: if the browser knows it's offline, queue without a doomed fetch
    // (the first such fetch would otherwise hang on a dead keep-alive socket).
    if (!navigator.onLine) {
      await markQueued(entry)
      return
    }
    // FIFO gate: while older ops sit queued, a new op must queue behind them, never
    // jump the line. On a flaky connection a fresh add can otherwise POST successfully
    // while an earlier one waits for replay — and since appends carry no anchor, the
    // server would bake that swapped order into order_position permanently. Queue it
    // and kick a flush: if the network is back, the whole backlog drains in order now.
    if (!fromFlush && [...pending.values()].some((e) => e.status === 'queued')) {
      await markQueued(entry)
      flush()
      return
    }
    // Remap any temp anchor/target ids to their real server ids (an offline mid-set
    // insert / burst can reference a record that hadn't settled yet, #5b).
    const { payload, skip } = remapAnchors(entry.payload, tempToReal)
    if (skip) { // the target record never reached the server -> drop this orphaned op
      await dropPending(entry.op_id)
      if (entry.tempId) byId.delete(entry.tempId)
      return
    }
    try {
      const res = await sendOp(config, entry.op_type, payload, entry.op_id)
      settleOp(entry, res)
      // This POST just proved the server is reachable. If the stream isn't live,
      // resync NOW instead of waiting for a poll — while the stream is down, ops
      // others logged (which only ever arrive via SSE or re-bootstrap) are missing,
      // even though our own writes are landing fine.
      if (sseStatus !== 'live' && !connecting) connect()
    } catch (e) {
      if (e.networkError) await markQueued(entry)
      else {
        undoOp(entry)
        await dropPending(entry.op_id)
        error = e.message
      }
    }
  }

  // Replay queued ops in offline order; stop if we go offline again mid-drain.
  let flushing = false
  let flushingNow = false // true only while draining the queue (gates reconcile collection)
  let flushRejects = []   // offline ops the server rejected this flush -> reconciliation review (§G)
  async function flush() {
    if (flushing) return
    flushing = true
    flushingNow = true
    flushRejects = []
    const hadQueued = [...pending.values()].some((e) => e.status === 'queued')
    try {
      // Re-pick the head each iteration (not a snapshot): the FIFO gate in trySend can
      // queue NEW ops behind the backlog while this drain is in flight, and its flush()
      // call no-ops on the `flushing` guard — so this loop must see them or they'd
      // strand until the next 'live' event. Each pass either settles/drops the head
      // (trySend removes it from pending) or leaves it queued (offline again -> stop).
      for (;;) {
        const queued = [...pending.values()].filter((e) => e.status === 'queued').sort((a, b) => a.ts - b.ts)
        if (!queued.length) break
        const entry = queued[0]
        await trySend(entry, true)
        if (entry.status === 'queued') break // still offline
      }
    } finally {
      flushing = false
      flushingNow = false
    }
    // Major-divergence review (§G): if offline work couldn't be applied (e.g. someone
    // removed a tune you edited), surface a review of exactly what was dropped rather
    // than a fleeting toast. The clean case (all flushed) stays the lightweight summary.
    if (hadQueued && flushRejects.length) {
      reconcile = { items: flushRejects.slice() }
      notice = '' // the modal supersedes the inline notice
    }
  }

  // The existing tune a PURE APPEND would collapse into, mirroring the server's merge rule
  // (_find_corroboration_target §H30): same tune already live in the OPEN set (after the last
  // break) — by tune_id when linked, else by identical normalized name when unlinked. Skips
  // optimistic/temp rows. Returns the target record or null. Used so one log action never
  // momentarily shows two copies of the same tune: we corroborate the existing row instead.
  // openSetMergeTarget now lives in logstate.js (pure, unit-tested).

  // Optimistic corroboration: an append of a tune already in the open set merges into the
  // existing row (flash + "keep both" nudge) instead of adding a second copy. The op is still
  // sent (no tempId, so no transient row) so the server records the corroboration. §H30/§D16.
  function corroborateLocally(target, payload, name) {
    flashId(target.session_instance_tune_id, 'merge')
    const seq = ++mergeNudgeSeq
    mergeNudge = { name: name || payload.name || 'that tune', payload }
    setTimeout(() => { if (seq === mergeNudgeSeq) mergeNudge = null }, 7000)
    trySend({ op_id: crypto.randomUUID(), name, op_type: 'add_tune', payload: { ...payload, after_record_id: null, before_record_id: null }, status: 'sending', ts: nextTs(), _localMerged: true })
  }

  // Shared optimistic add: place a temp row at the cursor, send/queue the op, and
  // advance the cursor past it (so a burst logs a set in order). §B/§D13.
  function addOptimistic(payload, name) {
    const c = insertAfterId
    if (c && typeof c === 'object' && c.newSet != null) {
      addNewSetTune(payload, name, c.newSet)
      return
    }
    const op_id = crypto.randomUUID()
    const tempId = `temp-${op_id}`
    const { afterId, beforeId, position } = cursorPos(insertAfterId, ordered, [...byId.values()])
    // Pure append of a duplicate -> corroborate the existing row, never a second copy.
    if (afterId == null && beforeId == null) {
      const target = openSetMergeTarget(payload, ordered)
      if (target) { corroborateLocally(target, payload, name); return }
    }
    byId.set(tempId, {
      session_instance_tune_id: tempId, name, tune_id: payload.tune_id ?? null, tune_type: payload.tune_type ?? null,
      record_type: 'tune', order_position: position, deleted: false, _temp: true, _status: 'sending',
    })
    trySend({ op_id, name, op_type: 'add_tune', payload: { ...payload, after_record_id: afterId, before_record_id: beforeId }, status: 'sending', ts: nextTs(), tempId })
    if (insertAfterId != null) insertAfterId = tempId // mid-insert: cursor follows the new tune
  }

  // Auto-log a tune arriving via ?tune=<id> ("Log to current session" from a tune-detail
  // page elsewhere in the app, §024). Append to the very end — which continues the trailing
  // open set if there is one, else starts a new set. We resolve the name/type for the
  // optimistic row; the server re-resolves canonically on the add_tune op.
  async function autoLogTune(rawId) {
    const tune_id = parseInt(rawId, 10)
    if (!Number.isFinite(tune_id)) return
    let name = '', tune_type = null
    try {
      const d = await tuneDetail(config, tune_id)
      if (d && d.success) { name = d.name || ''; tune_type = d.tune_type || null }
    } catch { /* offline / not found: fall through with a bare add */ }
    if (!name) name = '#' + tune_id
    setCursor(null) // append at the end of the session instance
    addOptimistic({ tune_id, name, tune_type }, name)
    requestAnimationFrame(() => {
      const sets = mainEl?.querySelector('.sets')
      if (sets) sets.scrollTop = sets.scrollHeight
    })
  }

  // "Keep both" (§D16): re-log the just-merged tune as a DISTINCT row at the end,
  // bypassing corroboration (no_merge). Dismisses the nudge.
  function keepBoth() {
    const n = mergeNudge
    mergeNudge = null
    if (!n) return
    const op_id = crypto.randomUUID()
    const tempId = `temp-${op_id}`
    byId.set(tempId, {
      session_instance_tune_id: tempId, name: n.name, tune_id: n.payload.tune_id ?? null, tune_type: n.payload.tune_type ?? null,
      record_type: 'tune', order_position: generateAppend(maxPos(byId.values())), deleted: false, _temp: true, _status: 'sending',
    })
    trySend({ op_id, name: n.name, op_type: 'add_tune', payload: { ...n.payload, after_record_id: null, before_record_id: null, no_merge: true }, status: 'sending', ts: nextTs(), tempId })
  }
  const dismissMerge = () => { mergeNudge = null }

  // --- reconnect reconciliation review (§G) ---
  const RECONCILE_VERB = {
    add_tune: 'Add', change_tune: 'Edit', remove_tune: 'Remove', set_break: 'Set break',
    set_confidence: 'Confirm', attribute_set_starter: 'Set starter', edit_notes: 'Edit notes',
    move_tunes: 'Move', remove_tunes: 'Bulk remove', restore_tunes: 'Restore',
  }
  const RECONCILE_REASON = {
    target_deleted: 'it had already been removed',
    not_found: 'it no longer exists',
    target_removed: 'it had already been removed',
  }
  function reconcileDesc(item) {
    const verb = RECONCILE_VERB[item.op_type] || item.op_type
    return item.name ? `${verb} “${item.name}”` : verb
  }
  function reconcileWhy(item) {
    return RECONCILE_REASON[item.reason] || item.message || item.reason || 'a conflict'
  }
  const dismissReconcile = () => { reconcile = null }

  // Start a NEW set in the gap before `nextFirstId` (the between-sets seam): drop a
  // tune there plus a trailing break that separates it from the next set. The break
  // is sent AFTER the tune resolves (awaited) and anchored before the same next tune,
  // so it always lands *after* our tune — both online (committed) and on offline
  // replay (flush awaits each op in turn). §C / prototype "new-set-after".
  async function addNewSetTune(payload, name, nextFirstId) {
    if (typeof nextFirstId !== 'number') { setCursor(null); addOptimistic(payload, name); return }
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === nextFirstId)
    if (idx === -1) { setCursor(null); addOptimistic(payload, name); return }
    const nextPos = ordered[idx].order_position
    const predPos = idx > 0 ? ordered[idx - 1].order_position : null
    const tunePos = generateBetween(predPos, nextPos)
    const breakPos = generateBetween(tunePos, nextPos)

    const op_id = crypto.randomUUID()
    const tempId = `temp-${op_id}`
    byId.set(tempId, {
      session_instance_tune_id: tempId, name, tune_id: payload.tune_id ?? null, record_type: 'tune',
      order_position: tunePos, deleted: false, _temp: true, _status: 'sending',
    })
    const bid = crypto.randomUUID()
    const btmp = `temp-${bid}`
    byId.set(btmp, {
      session_instance_tune_id: btmp, record_type: 'break',
      order_position: breakPos, deleted: false, _temp: true,
    })
    insertAfterId = tempId // burst continues inside the new set (before its trailing break)

    await trySend({ op_id, name, op_type: 'add_tune', payload: { ...payload, before_record_id: nextFirstId }, status: 'sending', ts: nextTs(), tempId })
    trySend({ op_id: bid, op_type: 'set_break', payload: { action: 'insert', before_record_id: nextFirstId }, status: 'sending', ts: nextTs(), tempId: btmp })
  }

  // Cancel a pending debounced search AND invalidate any in-flight one, so a late
  // result can't repopulate the dropdown after we've committed/dismissed.
  function cancelSearch() {
    if (searchTimer) { clearTimeout(searchTimer); searchTimer = null }
    searchSeq++ // a search already awaiting will fail its seq check and be discarded
  }

  function clearEntry() {
    if (resolving) cancelResolving(false)
    input = ''
    results = []
    resultsQuery = ''
    noMatch = false
    ambiguous = false
    searching = false
    composerHl = -1
    cancelSearch()
    lastTypingSent = 0
    sendTyping(config, false) // clear-on-commit (§F)
    error = ''
  }

  // Paste into the composer: text with separators — commas = tunes in a set, line
  // breaks = new sets — bulk-logs at the cursor through the selection-mode paste
  // pipeline (spec 029 §D three-case resolution, so our own copy pastes rich and the
  // old pill-logger JSON still works). The server matches each name with the same
  // rules as typed-Enter: linked when it resolves, unlinked otherwise (an ambiguous
  // name stays unlinked rather than blocking the batch on a dropdown). A single plain
  // name falls through to a normal paste so it can be edited before committing.
  function onComposerPaste(e) {
    if (composerLocked || editingId != null) return
    const plan = parseClipboard(e.clipboardData?.getData('text/plain') || '', lastCopy)
    if (!plan) return
    if (plan.kind === 'text' && plan.sets.length === 1 && plan.sets[0].length === 1) return
    e.preventDefault()
    // A half-typed fragment stays in the field (never silently discard user text);
    // the cursor advances past the pasted block, so Enter still logs it in order.
    pasteSets(plan.sets, { advanceCursor: true })
  }

  // Enter: add by typed text (server matches it to a tune, §C).
  function submit() {
    const name = input.trim()
    if (!name) return
    clearEntry()
    addOptimistic({ name }, name)
  }

  // A pasted thesession.org URL/id jumps into the deep-search PREVIEW of that tune
  // (spec 032, replacing the old log-immediately behavior): look at the notation —
  // landing on the URL's ?setting=/#setting when it has one — then "＋ Log This Tune".
  // The search underneath re-seeds with the tune's real name (session alias first,
  // via initialPreview.reseedId), so Back shows its results, not a URL search.
  function previewThesessionInput() {
    const id = tsInputId
    if (id == null) return
    const preview = {
      items: [{ r: { tune_id: id, name: `#${id}`, tune_type: null }, remote: true }],
      index: 0,
      settingId: parseThesessionSettingId(input),
      reseedId: id,
    }
    if (wide && sidePaneEl) { sidePaneEl.openPreview(preview); return }
    deepPreview = preview
    deepOpen = true
  }

  // Tap a search result: add the linked tune directly, then stay hot for the next
  // (spec 021 §D13 burst entry). If a placeholder is resolving, settle IT instead.
  function pickResult(t) {
    if (editingId != null) { relinkTo(t); return }
    if (resolving) { settleResolving({ tune_id: t.tune_id, name: t.name, tune_type: t.tune_type }, t.name); return }
    clearEntry()
    addOptimistic({ tune_id: t.tune_id, name: t.name, tune_type: t.tune_type }, t.name)
    queueMicrotask(() => inputEl?.focus())
  }

  // --- Enter / placeholder resolution (§D) -----------------------------------------
  // Hitting Enter asserts "this text is enough to find the tune." If the answer is known
  // synchronously (a unique exact local match, or the dropdown already resolved this exact
  // text), we log the real row instantly. Otherwise the text LEAVES the input and becomes a
  // placeholder "resolving" row at the seam with a spinner; the input locks. When the match
  // lands it settles to a linked or unlinked row — or, if several tunes match, the row waits
  // (input still locked) while the dropdown offers the choices. Failures (no match / offline /
  // error) settle as an unlinked "as-is" log: a committed entry is NEVER silently lost.
  async function commit() {
    if (editingId != null) { commitEdit(); return }
    if (resolving) {
      // Enter while a placeholder is pending: if ambiguous, pick the top match.
      if (ambiguous && results.length) {
        const t = results[0]
        settleResolving({ tune_id: t.tune_id, name: t.name, tune_type: t.tune_type }, t.name)
      }
      return
    }
    // Enter on a pasted thesession.org URL/id: open its preview (spec 032) — verify the
    // tune/setting, then log from there. (The op still queues offline from the preview.)
    if (tsInputId != null) { previewThesessionInput(); return }
    const q = input.trim()
    if (!q) return
    // Fast path: a UNIQUE exact match in the session's local vocabulary logs instantly.
    const local = resolveLocal(q)
    if (local) { pickResult(local); return }
    // A single candidate is already on screen for this exact text -> use it immediately, even
    // if the server search is still in flight. The user sees one option and Enter means "that
    // one"; no reason to drop their raw text into a placeholder first. (Covers the common case
    // the exact matchers miss — e.g. "kesh" -> the sole "Kesh, The" comma-form, found only by
    // substring.)
    if (resultsQuery === q && results.length === 1) { pickResult(results[0]); return }
    // If the server already answered for this exact text, decide synchronously (no placeholder).
    if (!searching && resultsQuery === q && (results.length || noMatch)) {
      const m = { exact_match: lastMatchExact, results }
      if (!m.results.length) { submit(); return }                          // no match -> unlinked
      if (m.exact_match) { pickResult(m.results[0]); return }              // unique exact among several
      startResolving(q); applyResolution(m); return                        // multiple -> placeholder + dropdown
    }
    // Out-typed the search: drop a resolving placeholder NOW, then settle when the match lands.
    startResolving(q)
    const seq = resolving.seq
    const m = await matchFor(q)
    if (!resolving || resolving.seq !== seq) return // settled / cancelled / edited meanwhile
    applyResolution(m)
  }

  // Apply a server verdict to the pending placeholder: settle it (linked / unlinked) or,
  // when several tunes match, keep it pending and surface the choices in the dropdown.
  function applyResolution(m) {
    if (!resolving) return
    if (!m.results.length) { settleResolving({ name: resolving.text }, resolving.text); return }
    if (m.exact_match || m.results.length === 1) {
      const t = m.results[0]
      settleResolving({ tune_id: t.tune_id, name: t.name, tune_type: t.tune_type }, t.name); return
    }
    results = m.results.slice(0, 8); resultsQuery = resolving.text; noMatch = false; ambiguous = true
  }

  // Drop a placeholder "resolving" row at the cursor and lock the composer. Captures the
  // op anchors now (cursor can't move while locked); the add_tune op fires only on settle.
  // Handles the between-sets ("new set") seam too — a tune plus a trailing break.
  function startResolving(q) {
    const tempId = `temp-${crypto.randomUUID()}`
    const c = insertAfterId
    const nextFirstId = c && typeof c === 'object' && c.newSet != null ? c.newSet : null
    const nsIdx = typeof nextFirstId === 'number' ? ordered.findIndex((r) => r.session_instance_tune_id === nextFirstId) : -1
    let position, addAnchors, breakTempId = null, breakOp = null, advance
    if (nsIdx !== -1) {
      const nextPos = ordered[nsIdx].order_position
      const predPos = nsIdx > 0 ? ordered[nsIdx - 1].order_position : null
      position = generateBetween(predPos, nextPos)
      const breakPos = generateBetween(position, nextPos)
      breakTempId = `temp-${crypto.randomUUID()}`
      byId.set(breakTempId, { session_instance_tune_id: breakTempId, record_type: 'break', order_position: breakPos, deleted: false, _temp: true })
      addAnchors = { before_record_id: nextFirstId }
      breakOp = { op_type: 'set_break', payload: { action: 'insert', before_record_id: nextFirstId } }
      advance = true
    } else {
      const cp = cursorPos(insertAfterId, ordered, [...byId.values()])
      position = cp.position
      addAnchors = { after_record_id: cp.afterId, before_record_id: cp.beforeId }
      advance = insertAfterId != null
    }
    byId.set(tempId, {
      session_instance_tune_id: tempId, name: q, tune_id: null, tune_type: null,
      record_type: 'tune', order_position: position, deleted: false, _temp: true, _resolving: true,
    })
    resolving = { tempId, breakTempId, text: q, addAnchors, breakOp, advance, seq: ++resolvingSeq }
    // clear & lock the composer (the text now lives in the placeholder row)
    input = ''
    results = []; resultsQuery = ''; noMatch = false; ambiguous = false; searching = false
    cancelSearch()
    lastTypingSent = 0; sendTyping(config, false)
    queueMicrotask(() => inputEl?.focus())
    scheduleSeam() // keep the new placeholder row in view
  }

  // Settle the placeholder into a real (linked or unlinked) row and fire the add_tune op
  // now — reusing the SAME temp id so the row never jumps. payload: {tune_id?, name, tune_type?}.
  async function settleResolving(payload, name) {
    const rs = resolving
    if (!rs) return
    // Pure append that resolved to a duplicate -> drop the placeholder and corroborate the
    // existing row, so the action never leaves a second copy behind. §H30
    if (!rs.breakOp && rs.addAnchors.after_record_id == null && rs.addAnchors.before_record_id == null) {
      const target = openSetMergeTarget(payload, ordered)
      if (target) {
        byId.delete(rs.tempId)
        resolving = null
        results = []; resultsQuery = ''; noMatch = false; ambiguous = false
        queueMicrotask(() => inputEl?.focus())
        corroborateLocally(target, payload, name)
        return
      }
    }
    const row = byId.get(rs.tempId)
    if (row) byId.set(rs.tempId, { ...row, name, tune_id: payload.tune_id ?? null, tune_type: payload.tune_type ?? null, _resolving: false, _status: 'sending' })
    if (rs.advance) insertAfterId = rs.tempId // burst continues after this tune
    resolving = null
    results = []; resultsQuery = ''; noMatch = false; ambiguous = false
    queueMicrotask(() => inputEl?.focus())
    const addEntry = { op_id: crypto.randomUUID(), name, op_type: 'add_tune', payload: { ...payload, ...rs.addAnchors }, status: 'sending', ts: nextTs(), tempId: rs.tempId }
    if (rs.breakOp) {
      // new-set seam: send the break only AFTER the tune resolves, anchored before the same
      // next tune, so it always lands after our tune (mirrors addNewSetTune).
      await trySend(addEntry)
      trySend({ op_id: crypto.randomUUID(), op_type: rs.breakOp.op_type, payload: rs.breakOp.payload, status: 'sending', ts: nextTs(), tempId: rs.breakTempId })
    } else {
      trySend(addEntry)
    }
  }

  // Abandon a pending placeholder. returnText=true ("Edit"/Escape) puts the text back in the
  // input to fix; false ("Remove") just discards it. Cancels any in-flight match (seq bump).
  function cancelResolving(returnText) {
    const rs = resolving
    if (!rs) return
    byId.delete(rs.tempId)
    if (rs.breakTempId) byId.delete(rs.breakTempId)
    resolving = null
    resolvingSeq++ // invalidate an in-flight commit() await
    results = []; resultsQuery = ''; noMatch = false; ambiguous = false
    if (returnText) {
      input = rs.text
      queueMicrotask(() => { inputEl?.focus(); runSearch() })
    } else {
      queueMicrotask(() => inputEl?.focus())
    }
  }

  // The droplist "Log "<text>" as-is" escape: settle the pending placeholder as unlinked text.
  function logAsIs() {
    if (resolving) settleResolving({ name: resolving.text }, resolving.text)
  }

  // --- deep catalog search (§D "search deeper") ---
  // The search body (state + logic + markup) lives in TuneSearch.svelte (spec 028), shared
  // between the mobile modal and the desktop side pane; only the modal gate remains here.
  let deepOpen = $state(false)

  // The single tune type of the set the cursor currently points into (preset filter).
  // The set (segment) the cursor is appending/inserting into, or null (new set / unknown).
  function cursorSegment() {
    const c = insertAfterId
    if (c == null) return endIsOpen && segments.length ? segments[segments.length - 1] : null
    if (typeof c === 'object') {
      if (c.newSet != null) return null
      return segments.find((s) => s.tunes.some((t) => t.session_instance_tune_id === c.before)) || null
    }
    return segments.find((s) => s.tunes.some((t) => t.session_instance_tune_id === c)) || null
  }

  function cursorSetType() {
    const seg = cursorSegment()
    if (!seg) return null
    const types = new Set(seg.tunes.map((t) => t.tune_type).filter(Boolean))
    return types.size === 1 ? [...types][0] : null
  }

  // tune_ids already logged into the set the cursor is building. They're DEMOTED in the
  // suggestion ranking — a tune you just added shouldn't be the top "log again" pick — but
  // kept in the list (a set can legitimately repeat a tune).
  function currentSetTuneIds() {
    const seg = cursorSegment()
    const ids = new Set()
    if (seg) for (const t of seg.tunes) if (t.tune_id != null) ids.add(t.tune_id)
    return ids
  }

  // ABC-ish input: legal ABC melody characters — note letters, accidentals (^ _ =),
  // octave/bar/repeat marks (' , | : [ ]), durations, etc. — with whitespace ignored
  // (it's meaningless in ABC). Such a query gets its notation matches blended in alongside
  // name matches, so e.g. "fdd cAA | B" finds "My Darling Asleep".
  const looksLikeAbc = (q) => {
    const s = (q || '').replace(/\s+/g, '')
    return s.length > 0 && /^[A-Ga-gxz0-9|^_=,'\/()\[\]:<>~-]+$/.test(s)
  }

  // Deep search entry: on DESKTOP the deep search IS the side pane (spec 032 — never a
  // centered modal there): seed it from the composer and focus it. Mobile opens the
  // full-screen modal, which seeds itself from the composer text.
  const openDeep = () => {
    if (wide && sidePaneEl) {
      const q = input.trim()
      if (q) sidePaneEl.seedSearch(q)
      queueMicrotask(() => mainEl?.querySelector('.sidepane .deep-field')?.focus())
      return
    }
    deepOpen = true
  }
  const closeDeep = () => { deepOpen = false; deepPreview = null }

  // 🔍 on a quick result (spec 032): jump straight into that tune's preview — the nav
  // list is the quick results themselves, so the header reads "2 of 4" and ‹ › page the
  // other matches; Back lands on the deep search. Desktop: in the side pane; mobile:
  // the full-screen modal (via initialPreview).
  let deepPreview = $state(null) // {items, index} passed to TuneSearch as initialPreview
  function openQuickPreview(vi) {
    const preview = {
      items: visibleResults.map((t) => ({
        r: { tune_id: t.tune_id, name: t.name, tune_type: t.tune_type, in_session: t.in_session_tune },
        remote: false,
      })),
      index: vi,
    }
    if (wide && sidePaneEl) { sidePaneEl.openPreview(preview); return }
    deepPreview = preview
    deepOpen = true
  }

  // The shared terminal path for every TuneSearch add (modal pick / pane pick / log-as-is /
  // remote import): log at the cursor and hand focus back to the composer.
  function logTune(payload, name) {
    clearEntry()
    addOptimistic(payload, name)
    queueMicrotask(() => inputEl?.focus())
  }

  // A pane add while in read-only View would silently mutate a log the user is just reading —
  // confirm the implicit switch to edit mode instead (spec 028). While the pull-down filter is
  // active, adding just exits the filter first (it's a transient state, not a deliberate mode).
  // Returns false when nothing was logged yet, so the pane keeps the user's search.
  let pendingViewAdd = $state(null) // {payload, name} picked in the pane while viewing
  let sidePaneEl = $state(null) // the SidePane instance (to clear its search after a confirmed add)
  function paneAdd(payload, name) {
    if (!viewing) {
      if (searchMode) doneSearching()
      logTune(payload, name)
      return true
    }
    if (logComplete) {
      notice = 'This log is marked complete — use "Mark as not complete" in the header to edit it.'
    } else {
      pendingViewAdd = { payload, name }
    }
    return false
  }
  const cancelViewAdd = () => { pendingViewAdd = null }
  function confirmViewAdd() {
    const p = pendingViewAdd
    pendingViewAdd = null
    if (!p) return
    setMode('edit')
    logTune(p.payload, p.name)
    sidePaneEl?.resetSearch() // the add went through — clear, like a direct edit-mode add
    requestAnimationFrame(() => inputEl?.focus()) // the composer mounts with the mode flip
  }

  // The shared matcher (same as the legacy pill editor: find_matching_tune + wildcard),
  // --- local exact-match fast path (§024) -----------------------------------
  // The session's repertoire (known_tunes/known_aliases from bootstrap) is indexed
  // locally so a typed name matching a known tune EXACTLY logs with no network in the
  // hot path. Normalization mirrors the server matcher (find_matching_tune): apostrophe
  // fold, unaccent, lower; "The" prefix flexibility on the tune-name tier only.
  let localIndex = null
  let vocabKnown = [], vocabAliases = [] // raw bootstrap vocabulary, kept for offline persistence
  // stripThe / normName / normAbc now live in logstate.js (pure, unit-tested).
  function buildLocalIndex(known, aliases) {
    nextByTuneId.clear()
    if (!known && !aliases) { localIndex = null; vocabKnown = []; vocabAliases = []; return }
    vocabKnown = known || []
    vocabAliases = aliases || []
    for (const t of known || []) if (t.tune_id && t.next) nextByTuneId.set(t.tune_id, t.next)
    const aliasMap = new Map(), nameMap = new Map(), byId = new Map()
    const add = (map, key, id) => { if (!key) return; let s = map.get(key); if (!s) map.set(key, (s = new Set())); s.add(id) }
    // `list` is the flat, vocab-ordered set of entries scanned for SUBSTRING matches (the
    // type-ahead dropdown). Vocabulary order already encodes ranking — this session's
    // top-N by plays first, then globally-popular tunes — so an entry's index is a good
    // relevance proxy. Deduped by tune_id; first occurrence keeps the better (earlier) rank.
    const list = [], listById = new Map()
    const ensure = (id, name, tune_type) => {
      let e = listById.get(id)
      if (!e) { e = { tune_id: id, name, tune_type: tune_type ?? null, nn: normName(name), aliases: [], abc: '' }; listById.set(id, e); list.push(e) }
      return e
    }
    for (const t of known || []) {
      if (!t.tune_id) continue
      byId.set(t.tune_id, { tune_id: t.tune_id, name: t.name, tune_type: t.tune_type ?? null })
      const n = normName(t.name)
      add(nameMap, n, t.tune_id)
      add(nameMap, stripThe(n), t.tune_id) // "The X" <-> "X" flexibility (both directions)
      const e = ensure(t.tune_id, t.name, t.tune_type)
      if (t.abc) e.abc = normAbc(t.abc) // searchable notation for instant ABC substring match
      if (t.alias) { add(aliasMap, normName(t.alias), t.tune_id); e.aliases.push(normName(t.alias)) }
    }
    for (const a of aliases || []) {
      if (!a.tune_id || !a.alias) continue
      add(aliasMap, normName(a.alias), a.tune_id)
      if (!byId.has(a.tune_id)) byId.set(a.tune_id, { tune_id: a.tune_id, name: a.name || a.alias, tune_type: a.tune_type ?? null })
      ensure(a.tune_id, a.name || a.alias, a.tune_type).aliases.push(normName(a.alias))
    }
    list.forEach((e, i) => { e.idx = i })
    localIndex = { aliasMap, nameMap, byId, list }
  }
  // Resolve a typed string to a UNIQUE exact known tune, or null (no match OR ambiguous
  // -> defer to the server path, which never guesses). Alias tier wins, exactly as the
  // server does, and only returns when there's a single candidate.
  function resolveLocal(q) {
    if (!localIndex) return null
    const qn = normName(q)
    if (!qn) return null
    const aIds = localIndex.aliasMap.get(qn)
    if (aIds && aIds.size === 1) return localIndex.byId.get([...aIds][0]) || null
    if (aIds && aIds.size > 1) return null // ambiguous alias -> let the gate handle it
    const ids = new Set()
    for (const key of new Set([qn, stripThe(qn)])) {
      const s = localIndex.nameMap.get(key)
      if (s) for (const id of s) ids.add(id)
    }
    if (ids.size === 1) return localIndex.byId.get([...ids][0]) || null
    return null
  }

  // Substring matches from the local vocabulary — the INSTANT type-ahead list (zero network).
  // Mirrors the server wildcard: plain substring over name+alias, ranked by the set's type
  // preference, then vocabulary order (session plays -> global popularity), then name. A
  // note-only query ALSO substring-matches cached notation (marked abc:true, appended after
  // name hits), so typing an incipit finds tunes instantly — even offline (§024 fast path).
  function resolveLocalMany(q, limit = 8) {
    if (!localIndex) return []
    const qn = normName(q)
    const prefer = cursorSetType() // the set's tune type (soft sort preference), or null
    const inSet = currentSetTuneIds() // already in this set -> demote below fresh suggestions
    const cmp = (a, b) => {
      const ia = inSet.has(a.tune_id) ? 1 : 0
      const ib = inSet.has(b.tune_id) ? 1 : 0
      if (ia !== ib) return ia - ib // a tune already in this set sinks beneath everything else
      const pa = prefer && a.tune_type === prefer ? 0 : 1
      const pb = prefer && b.tune_type === prefer ? 0 : 1
      if (pa !== pb) return pa - pb
      if (a.idx !== b.idx) return a.idx - b.idx
      return a.nn < b.nn ? -1 : a.nn > b.nn ? 1 : 0
    }
    const nameHits = []
    if (qn.length >= 2) {
      for (const e of localIndex.list) {
        if (e.nn.includes(qn) || e.aliases.some((a) => a.includes(qn))) nameHits.push(e)
      }
      nameHits.sort(cmp)
    }
    // Notation hits: only for note-only input with a selective needle (3+ chars, so a
    // one- or two-note fragment doesn't match half the catalog). Deduped against name hits.
    const abcHits = []
    const an = looksLikeAbc(q) ? normAbc(q) : ''
    if (an.length >= 3) {
      const seen = new Set(nameHits.map((e) => e.tune_id))
      for (const e of localIndex.list) {
        if (e.abc && !seen.has(e.tune_id) && e.abc.includes(an)) abcHits.push(e)
      }
      abcHits.sort(cmp)
    }
    return [
      ...nameHits.map((e) => ({ tune_id: e.tune_id, name: e.name, tune_type: e.tune_type })),
      ...abcHits.map((e) => ({ tune_id: e.tune_id, name: e.name, tune_type: e.tune_type, abc: true })),
    ].slice(0, limit)
  }

  // mergeStable now lives in logstate.js (pure, unit-tested).

  // Background vocabulary load (online): fetch the session vocabulary AFTER first render,
  // build the local fast-match index, and persist it into the offline snapshot. Deferred
  // so it never blocks bootstrap. Until it lands, resolveLocal() returns null and typing
  // simply falls through to the server matcher — the fast path just "warms up" a moment
  // later. A network failure is swallowed (the cached/previous index stands); the next
  // connect() retries.
  async function loadVocabulary(gen) {
    try {
      const v = await vocabulary(config)
      if (gen !== connSeq) return // a newer connect() superseded this one
      buildLocalIndex(v.known_tunes, v.known_aliases)
      await saveSnapshot() // persist the vocabulary into the offline snapshot
    } catch {
      // leave the existing index as-is; server match still works, retried next connect()
    }
  }

  // returning {exact_match, results}. ABC blend: for a note-only query (looksLikeAbc, any
  // length) we ALSO search the notation and append those matches (marked abc:true) after
  // the name matches, so typing "gabaged" surfaces tunes by name AND by notation at once.
  async function matchFor(q) {
    // Fire the notation search concurrently with the name match (server returns [] offline).
    const abcPromise = looksLikeAbc(q) ? deepSearch(config, q, null, cursorSetType(), 'abc') : null
    const m = await liveMatch(config, q, cursorSetType())
    if (m.results.length) {
      matchCachePut(config.sessionInstanceId, q, m) // remember for offline linking (#5c)
    } else if (!navigator.onLine || !reachable) {
      // Offline (server unreachable): fall back to the match cache so typing can still
      // LINK a previously-seen tune instead of always logging unlinked. Only when offline
      // — an online empty result is the authoritative "no match".
      const cached = await matchCacheGet(config.sessionInstanceId, q).catch(() => null)
      if (cached && cached.results.length) return cached
    }
    if (abcPromise) {
      const abc = await abcPromise
      const seen = new Set(m.results.map((r) => r.tune_id))
      const extra = abc
        .filter((t) => t.tune_id != null && !seen.has(t.tune_id))
        .map((t) => ({ tune_id: t.tune_id, name: t.name, tune_type: t.tune_type, in_session_tune: t.in_session, abc: true }))
      if (extra.length) {
        // Name matches first, then notation-only; exact_match stays the name match's verdict.
        return { exact_match: m.exact_match, results: [...m.results, ...extra].slice(0, 8) }
      }
    }
    return m
  }

  // Progressive type-ahead search, shown above the composer. The local vocabulary is
  // matched INSTANTLY (zero network) so common/known tunes appear with no delay; the
  // server search fires in parallel (debounced) and its long-tail results stable-append
  // below. The spinner stays lit until the server answers. (§D)
  function runSearch() {
    if (resolving) return // composer is locked while a placeholder resolves
    const q = input.trim()
    // A pasted thesession.org URL / tune id short-circuits the name search: offer a single
    // "add from thesession.org" row instead. The add op imports server-side (spec 026).
    const pastedId = parseThesessionId(q)
    tsInputId = pastedId
    if (pastedId != null) {
      results = []
      resultsQuery = q
      noMatch = false
      searching = false
      cancelSearch()
      return
    }
    if (q.length < 2) {
      results = []
      resultsQuery = q
      noMatch = false
      searching = false
      cancelSearch()
      return
    }
    const local = resolveLocalMany(q, 8) // instant
    results = local
    resultsQuery = q
    noMatch = false
    searching = true
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(async () => {
      const seq = ++searchSeq
      const m = await matchFor(q)
      if (seq === searchSeq) {
        results = mergeStable(local, m.results)
        resultsQuery = q
        lastMatchExact = m.exact_match
        noMatch = results.length === 0 // nothing at all -> show "no tunes match" + deeper search
        searching = false
      }
    }, 180)
  }

  // Remove (soft) — works offline: optimistically marks the row "⏳ removing"
  // (struck-through, restorable), queues the op, settles on the server's delete (§G).
  function removeTune(record_id) {
    const r = byId.get(record_id)
    if (!r || r.deleted || r._removing) return
    error = ''
    const op_id = crypto.randomUUID()
    byId.set(record_id, { ...r, _removing: op_id })
    trySend({ op_id, op_type: 'remove_tune', payload: { record_id }, status: 'sending', ts: nextTs() })
  }

  // Remove a QUEUED offline add before it syncs: the op never reached the server, so
  // this is a local cancel (like restore()/undoBulkDelete) — drop the op from the
  // queue and its optimistic row from the log. Only 'queued' entries: an in-flight
  // 'sending' op settles momentarily and can be removed normally once real.
  function cancelQueuedRow(tempId) {
    const entry = [...pending.values()].find((e) => e.tempId === tempId && e.status === 'queued')
    if (!entry) return
    dropPending(entry.op_id)
    byId.delete(tempId)
    if (insertAfterId === tempId) insertAfterId = null
    if (selectedId === tempId) selectedId = null
  }

  // Restore a not-yet-synced removal: cancel the queued op, clear the mark.
  function restore(record_id) {
    const r = byId.get(record_id)
    if (!r || !r._removing) return
    dropPending(r._removing)
    const { _removing, ...rest } = r
    byId.set(record_id, rest)
  }

  // End the current set — works offline: optimistically appends a break (which the
  // set segmentation renders as a divider), queues, settles on the real break.
  function endSet() {
    if (!ordered.length) return
    error = ''
    // "End set" = append a break at the very end. after_record_id: null so the
    // server appends at replay time (correctly landing after any offline tunes that
    // replay first by ts); avoids ever sending a temp id as the anchor.
    const op_id = crypto.randomUUID()
    const tempId = `temp-${op_id}`
    byId.set(tempId, {
      session_instance_tune_id: tempId, record_type: 'break',
      order_position: nextTempPos(), deleted: false, _temp: true,
    })
    trySend({ op_id, op_type: 'set_break', payload: { action: 'insert', after_record_id: null }, status: 'sending', ts: nextTs(), tempId })
  }

  const queuedCount = $derived([...pending.values()].filter((e) => e.status === 'queued').length)
  const sendingCount = $derived([...pending.values()].filter((e) => e.status === 'sending').length)

  // Refresh a typing reservation while composing (throttled), run search, clear when empty.
  function onInput() {
    if (viewing) return // no composer in view mode; never broadcast typing as a viewer
    if (resolving) return // composer is locked while a placeholder resolves
    ambiguous = false // editing the text re-opens the question; next Enter re-evaluates
    composerHl = -1 // typing invalidates any keyboard highlight
    runSearch()
    if (input.trim()) {
      const now = Date.now()
      if (now - lastTypingSent > 3000) {
        lastTypingSent = now
        sendTyping(config, true, lastRecordId)
      }
    } else if (lastTypingSent) {
      lastTypingSent = 0
      sendTyping(config, false)
    }
  }

  function stopTyping() {
    composerFocused = false // closes the "likely next tune" pinned row
    if (resolving) return // keep the resolution dropdown open while a placeholder is pending
    if (lastTypingSent) {
      lastTypingSent = 0
      sendTyping(config, false)
    }
    // Result clicks use mousedown+preventDefault (no blur), so we can close
    // immediately on a real blur and cancel any pending search.
    cancelSearch()
    results = []
    resultsQuery = ''
    noMatch = false
    ambiguous = false
    searching = false
    composerHl = -1
  }

  const othersTyping = $derived(typers.filter((t) => t.person_id !== person.person_id))

  let connSeq = 0 // guards against overlapping connect() calls leaking a stream
  let renderOnly = $state(false) // completed-log fast-path: rendered, no stream (hide status pill)
  // When to surface the connection dot (floated by the hamburger). Only when a live
  // stream is actually in play: always in edit mode (it reflects *my* connection), and
  // in view mode only while the log is still open AND someone else is connected and
  // editing live — a non-away roster entry (viewers are excluded from the roster
  // server-side, spec 024 §presence). A completed render-only log has no stream, so hide.
  // Signed out, the dot would only ever mean "this page is streaming" — the roster it
  // keys off is deliberately empty and there are no queued edits to report — so a
  // read-only viewer gets a live page with no connection chrome at all.
  const showConnDot = $derived(
    !renderOnly && !readOnly && (mode === 'edit' || (viewing && !logComplete && roster.some((p) => !p.away)))
  )
  let connecting = false // a connect() is in flight — gates the opportunistic reconnect triggers
  // Map a cached snapshot row (snapshotGet) to the bootstrap shape, so the offline
  // fallback and the slow-network fast paint apply through the same code.
  const snapFromCache = (cached) => ({
    records: cached.records, last_event_id: cached.last_event_id || 0, current_person: cached.person,
    session_name: cached.session_name, session_date: cached.session_date,
    instance_date: cached.instance_date, instance_name: cached.instance_name,
    start_time: cached.start_time, end_time: cached.end_time,
    session_type: cached.session_type, notes: cached.notes,
    log_complete: cached.log_complete, user_timezone: cached.display_tz,
    known_tunes: cached.known_tunes || [], known_aliases: cached.known_aliases || [],
  })
  // Apply a bootstrap-shaped snapshot (server truth or cached copy) to the screen.
  function applySnap(snap, fromCache) {
    byId.clear()
    for (const r of snap.records || []) put(r)
    // Local fast-match vocabulary: rendering from the OFFLINE cache rebuilds the index
    // immediately from the cached copy; ONLINE it's fetched in the background after
    // render (loadVocabulary, below) so it never blocks bootstrap.
    if (fromCache) buildLocalIndex(snap.known_tunes, snap.known_aliases)
    if (snap.current_person) person = snap.current_person
    if (snap.session_name) sessionName = snap.session_name
    if (snap.session_date) sessionDate = snap.session_date
    if (snap.instance_date) instanceDate = snap.instance_date
    // Presence of the key, not truthiness: null is a real value here (an unnamed log),
    // but a snapshot cached before spec 047 has no key at all and must not blank the
    // name the shell already painted.
    if ('instance_name' in snap) instanceName = snap.instance_name || ''
    if ('start_time' in snap) instanceStart = snap.start_time || ''
    if ('end_time' in snap) instanceEnd = snap.end_time || ''
    if (snap.session_type) sessionType = snap.session_type
    displayTz = snap.user_timezone || snap.session_timezone || undefined
    notesText = snap.notes || ''
    logComplete = !!snap.log_complete
    highWater = snap.last_event_id || 0
    // Truth (or cache) is applied — the screen can render NOW. Flipping `loaded` here
    // (rather than when connect() fully resolves) matters only for an EMPTY log:
    // rows render as soon as byId fills, but the "No tunes yet" message is gated on
    // `loaded`, and the snapshot write + queue hydration below run on IndexedDB,
    // which can take seconds on a cold mobile browser — an empty session would sit
    // on the loading skeleton that whole time.
    loaded = true
  }
  // How long the first bootstrap may keep the skeleton up before we paint the cached
  // snapshot provisionally. Fast connections resolve well under this and never see it.
  const STALE_PAINT_MS = 800
  // Records settled by op-POST acks while a bootstrap was in flight. The bootstrap's DB
  // read can predate those ops, so applying it verbatim would wipe a row the user just
  // watched land, and it would only blink back via SSE catch-up. After the snapshot
  // applies, re-put the ones newer than it — the same convergence the catch-up cursor
  // performs (idempotent by record id), just without the visible gap.
  let bootstrapInFlight = false
  let lateSettles = []
  async function connect() {
    const myGen = ++connSeq
    connecting = true
    renderOnly = false
    if (reconnectPoll) { clearTimeout(reconnectPoll); reconnectPoll = null }
    // Snapshot pre-reconnect state for the §I36 "synced / added while away" summary.
    const prevIds = new Set([...byId.values()].filter((r) => typeof r.session_instance_tune_id === 'number').map((r) => r.session_instance_tune_id))
    const wasQueued = [...pending.values()].filter((e) => e.status === 'queued').length
    // Slow-network fast paint (stale-first): if the FIRST bootstrap hasn't answered
    // within STALE_PAINT_MS and a cached snapshot exists, paint it provisionally so a
    // slow connection sees the log in under a second instead of a skeleton. Correctness
    // is unchanged by construction: this is the OFFLINE render path (cached records +
    // queued-op overlay) triggered by a timer instead of a network error, and the
    // bootstrap that eventually lands re-applies exactly like a reconnect does — byId
    // reset to server truth, with lateSettles + the stream's idempotent catch-up cursor
    // converging anything that raced in meanwhile. Never fires on reconnects (`loaded`),
    // where the screen already shows state newer than the cache.
    let snapApplied = false // the real bootstrap (or offline fallback) has painted — a late stale paint must not clobber it
    const stalePaint = loaded ? null : setTimeout(async () => {
      const cached = await snapshotGet(config.sessionInstanceId).catch(() => null)
      if (!cached || snapApplied || myGen !== connSeq) return
      applySnap(snapFromCache(cached), true)
      hydrateQueue() // overlay still-queued offline ops, same as the offline path
    }, STALE_PAINT_MS)
    try {
      if (es) { es.close(); es = null }
      let snap
      let fromCache = false
      lateSettles = []
      bootstrapInFlight = true
      try {
        snap = await bootstrap(config) // server truth + fresh high-water
        reachable = true // we just reached the server
        if (snap.session_id) sessionId = snap.session_id
      } catch (e) {
        if (!e.networkError) throw e
        reachable = false // couldn't reach the server -> offline (not just "reconnecting")
        // Offline: fall back to the cached snapshot so the screen still renders (§G).
        const cached = await snapshotGet(config.sessionInstanceId).catch(() => null)
        snap = cached ? snapFromCache(cached) : { records: [], last_event_id: 0 }
        fromCache = true
      } finally {
        bootstrapInFlight = false
        if (stalePaint) clearTimeout(stalePaint)
      }
      if (myGen !== connSeq) return // a newer connect() superseded this one
      snapApplied = true // from here on, a late-firing stale paint must stand down
      applySnap(snap, fromCache)
      // Converge ops acked while the bootstrap was in flight (see lateSettles above).
      for (const s of lateSettles) {
        if (s.event_id > (snap.last_event_id || 0)) for (const r of s.records) put(r)
      }
      lateSettles = []

      // Signed-out viewer: the snapshot IS the page. Nothing below this applies —
      // there's no offline queue to flush or hydrate, no attendance to load, no
      // vocabulary index and no local snapshot to write (all of that serves editing,
      // on the editor's own device). Stream only while the session is actually
      // happening: someone reading last month's log has nothing to watch, so they get
      // a static snapshot (the server refuses an anonymous stream on an inactive
      // instance regardless, so this is the polite half of the same rule).
      if (readOnly) {
        everConnected = true
        // Prefer the bootstrap's fresh value over the page-load config, so a viewer
        // whose session ends mid-watch drops to static on the next reconnect instead
        // of retrying a stream the server now refuses.
        const active = snap.instance_active ?? config.instanceActive
        if (fromCache || !active) {
          renderOnly = true
          if (fromCache) scheduleReconnect() // offline: retry so the page fills in when the network returns
          return
        }
        const viewStream = openStream(config, snap.last_event_id, {
          onOp: applyOp,
          onAlive: () => (lastEventAt = Date.now()),
          onStatus: (s) => { sseStatus = s; noteSse(s) },
          onDead: () => { if (myGen === connSeq) connect() },
        }, 'view')
        if (myGen !== connSeq) { viewStream.close(); return }
        es = viewStream
        return
      }

      if (!fromCache) await saveSnapshot() // refresh the cache from server truth, immediately

      // Completed log = read-only. Render the records and stop — skip the offline-queue
      // replay, attendance prefetch, SSE stream (presence/typing/live), and vocabulary
      // index; none are needed to *read* a finished log. A remote un-complete won't reflect
      // without a reload (rare; accepted, §024). Exception: if we still hold queued offline
      // ops for this instance, take the full path so they can flush.
      if (logComplete && !fromCache) {
        const queued = await queueAll(config.sessionInstanceId).catch(() => [])
        if (!queued.length) { everConnected = true; renderOnly = true; return }
      }

      await hydrateQueue() // re-apply still-queued ops' optimistic state onto these records

      if (fromCache) {
        // Offline: render from cache, don't open a doomed SSE that retries every ~3s.
        // Slow-poll a reconnect; the 'online' event also triggers one immediately.
        everConnected = true // this counts as having connected, so the next (online) reconnect summarizes
        scheduleReconnect()
        return
      }
      refreshAttendees() // load the attendance list (header + starter picker) — online only

      // The server is provably reachable (bootstrap just succeeded) — replay queued ops
      // NOW. Waiting for the stream to reach 'live' (the only other flush trigger) strands
      // the queue indefinitely when SSE can't connect (e.g. the streaming sidecar is down)
      // even though every op would land fine. Awaited so the §I36 summary below reports
      // what actually synced. The ops' own events replay via the stream's catch-up cursor
      // (idempotent by record id), so flushing before opening the stream loses nothing.
      await flush()
      if (myGen !== connSeq) return // a newer connect() superseded this one while flushing

      const stream = openStream(config, snap.last_event_id, {
        onOp: applyOp,
        onPresence: (r) => (roster = r),
        onTyping: (l) => (typers = l),
        onAlive: () => (lastEventAt = Date.now()),
        onStatus: (s) => {
          sseStatus = s
          noteSse(s)
          // Not live = no trustworthy presence; clear the stale roster/typers
          // (others have already seen us drop).
          if (s === 'live') flush() // back online -> replay anything queued (§G)
          else {
            roster = []
            typers = []
          }
        },
        // Silent half-open stream detected by the watchdog -> full reconnect (re-bootstrap
        // closes any gap of events missed while the socket was dead).
        onDead: () => { if (myGen === connSeq) connect() },
      }, mode)
      if (myGen !== connSeq) { stream.close(); return } // superseded after we opened
      es = stream
      loadVocabulary(myGen) // background: warm the local fast-match index, then persist it

      // On a reconnect (not the first connect), summarize what changed while away.
      // "synced" counts ops that actually LEFT the queue in the flush above — claiming
      // wasQueued outright showed a green "N synced" on every reconnect even when the
      // flush couldn't run and the ops were still stuck queued.
      if (everConnected) {
        const added = (snap.records || []).filter((r) => !prevIds.has(r.session_instance_tune_id)).length
        const stillQueued = [...pending.values()].filter((e) => e.status === 'queued').length
        const synced = Math.max(0, wasQueued - stillQueued)
        const parts = []
        if (synced) parts.push(`${synced} synced`)
        if (added) parts.push(`${added} added while away`)
        if (parts.length) showSync(parts.join(' · '))
      }
      everConnected = true
    } catch (e) {
      error = e.message
      sseStatus = 'error'
      scheduleReconnect() // never leave a failed connect with no retry pending
    } finally {
      if (myGen === connSeq) connecting = false // a superseding connect() owns the flag
    }
  }

  // Close the stream when the page is hidden/navigated/bfcached so the server sees
  // us leave (an SSE socket kept alive in bfcache would otherwise leave a ghost
  // present); reconnect when the page is restored from bfcache.
  function onPageHide() {
    if (es) { es.close(); es = null }
    sseStatus = 'reconnecting'
    saveSnapshot() // best-effort flush so the latest records are cached for offline
  }
  function onPageShow(e) {
    // Only reconnect on a bfcache restore; the initial load is handled by onMount
    // (pageshow also fires then, which previously caused a duplicate connection).
    if (e.persisted) connect()
  }

  // Load persisted queued ops (if any) and re-apply their optimistic effect onto
  // the current records. Runs after each (re)bootstrap, which resets byId to truth.
  async function hydrateQueue() {
    let saved = []
    try {
      saved = await queueAll(config.sessionInstanceId)
    } catch (err) {
      return // IndexedDB unavailable (private mode etc.) — degrade to online-only
    }
    for (const e of saved) {
      // Skip ops already tracked AND ops that resolved this session — queueAll can read
      // the store before a just-resolved op's IndexedDB delete commits, and re-queueing
      // it would replay (and optimistically re-render) an op that's already done.
      if (!pending.has(e.op_id) && !resolvedOps.has(e.op_id)) {
        pending.set(e.op_id, { op_id: e.op_id, op_type: e.op_type, payload: e.payload, name: e.name, status: 'queued', ts: e.ts })
      }
    }
    // Re-apply optimistic state for everything still queued, in offline (ts) order
    // so temp positions stack the same way they did originally.
    const queued = [...pending.values()].filter((e) => e.status === 'queued').sort((a, b) => a.ts - b.ts)
    for (const entry of queued) {
      if (entry.op_type === 'add_tune') {
        entry.tempId = `temp-${entry.op_id}`
        // Carry the link through from the op payload: an offline add matched via the
        // cache/local vocabulary IS linked, and dropping tune_id/tune_type here made
        // every queued tune render "unlinked" in an "Unknown" set after a reload.
        byId.set(entry.tempId, {
          session_instance_tune_id: entry.tempId, name: entry.name,
          tune_id: entry.payload?.tune_id ?? null, tune_type: entry.payload?.tune_type ?? null,
          record_type: 'tune',
          order_position: nextTempPos(), deleted: false, _temp: true, _status: 'queued',
        })
      } else if (entry.op_type === 'set_break' && entry.payload?.action === 'remove') {
        byId.delete(entry.payload.record_id) // re-apply an offline join
      } else if (entry.op_type === 'set_break') {
        entry.tempId = `temp-${entry.op_id}`
        byId.set(entry.tempId, {
          session_instance_tune_id: entry.tempId, record_type: 'break',
          order_position: nextTempPos(), deleted: false, _temp: true,
        })
      } else if (entry.op_type === 'remove_tune') {
        const r = byId.get(entry.payload.record_id)
        if (r && !r._removing) byId.set(r.session_instance_tune_id, { ...r, _removing: entry.op_id })
      } else if (entry.op_type === 'change_tune') {
        const r = byId.get(entry.payload.record_id)
        if (r) {
          const patch = {}
          if (entry.payload.unlink) patch.tune_id = null
          else if ('tune_id' in entry.payload) patch.tune_id = entry.payload.tune_id
          if ('name' in entry.payload) patch.name = entry.payload.name
          byId.set(r.session_instance_tune_id, { ...r, ...patch })
        }
      } else if (entry.op_type === 'set_confidence') {
        const r = byId.get(entry.payload.record_id)
        if (r) byId.set(r.session_instance_tune_id, { ...r, confidence: entry.payload.confidence })
      } else if (entry.op_type === 'attribute_set_starter') {
        // Re-apply across the set containing the anchor tune (server applies to the whole
        // set; offline we approximate from the current ordering). started_by_name will
        // refresh from the SSE echo once the op flushes on reconnect.
        for (const tid of setTuneIdsContaining(entry.payload.record_id)) {
          const r = byId.get(tid)
          if (r) byId.set(tid, { ...r, started_by_person_id: entry.payload.person_id ?? null })
        }
      }
    }
  }

  // Tune ids in the same set as a record (run of tunes between surrounding breaks),
  // from the current ordering — mirrors the server's set bounds for offline re-apply.
  function setTuneIdsContaining(recordId) {
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === recordId)
    if (idx < 0) return []
    let lo = idx, hi = idx
    while (lo > 0 && ordered[lo - 1].record_type !== 'break') lo--
    while (hi < ordered.length - 1 && ordered[hi + 1].record_type !== 'break') hi++
    return ordered.slice(lo, hi + 1).filter((r) => r.record_type === 'tune').map((r) => r.session_instance_tune_id)
  }

  const onOnline = () => {
    online = true
    reachable = true // give the stream a fresh chance; noteSse re-arms the timeout
    connect() // re-bootstrap + reopen the stream (which flushes the queue on 'live')
  }
  // Returning to the tab is the moment mobile stream death shows: iOS kills the SSE
  // socket (and freezes our timers) while the page is backgrounded/locked, and no
  // 'online'/'pageshow' event fires on the way back. If the stream isn't live when we
  // become visible, reconnect immediately — don't wait for a suspended poll/watchdog.
  // (A stale-'live' status is the watchdog's job: its timer fires right after resume.)
  const onVisible = () => {
    if (document.visibilityState === 'visible' && !renderOnly && sseStatus !== 'live' && !connecting) connect()
  }
  // Reflect offline immediately (the SSE onerror can lag): drop the stale presence and
  // close the stream so EventSource stops its ~3s reconnect spam while we're offline.
  const onOffline = () => {
    online = false
    roster = []
    typers = []
    if (es) { es.close(); es = null }
  }

  onMount(() => {
    // "Log to current session" from a tune-detail page elsewhere in the app lands here
    // with ?tune=<id>. Capture it and strip it from the URL up front so a reload/back
    // can't re-add the tune; append it once the first bootstrap has loaded truth (§024).
    // ?highlight=<session_instance_tune_id> is the other deep-link: a play-history click
    // that should scroll to + flash an EXISTING record — never append. It wins over
    // ?tune when both arrive (history links carry both for the legacy page's sake).
    const params = new URLSearchParams(window.location.search)
    const autoTuneId = params.get('tune')
    const highlightId = Number(params.get('highlight')) || null
    pendingHighlight = highlightId
    if (autoTuneId || highlightId) {
      params.delete('tune')
      params.delete('highlight')
      const qs = params.toString()
      window.history.replaceState({}, '', window.location.pathname + (qs ? '?' + qs : ''))
    }
    // The highlight does NOT wait on connect(). It only needs the row on screen, and it
    // polls until it is — so a bootstrap that is slow, or that rejects outright (offline,
    // a dead SSE) while the records still hydrate from cache, can't silently eat the
    // flash. autoLogTune DOES wait: appending a tune needs the loaded truth first.
    if (highlightId) highlightFromUrl(highlightId)
    // Independent of connect(): the header's Recordings count is its own small
    // fetch, and a slow or failed bootstrap shouldn't decide whether it appears.
    loadRecordingCount()
    // Same deal for the audio: background, nothing waits on it, and the play
    // buttons appear on the rows that have marks whenever it lands.
    loadAudio()
    connect().then(() => {
      loaded = true
      if (autoTuneId && !highlightId) autoLogTune(autoTuneId)
    }) // bootstraps records, then hydrateQueue() re-applies any queued ops
    // Load the roster up front. The header's "Attendance (n)" reads it, so leaving it lazy
    // (fetched only when the picker opens) made the header claim "no one checked in yet"
    // while the picker itself listed four people under "Checked in".
    // Signed out there is no attendance UI at all, and the endpoint is gated — skip it.
    if (!readOnly) {
      refreshAttendees()
      // The shared app menu's 'Find a tune' calls this in the live context -> insert.
      // Deep search is login-gated, so a signed-out viewer keeps the menu's default
      // (site-wide) behavior instead.
      window.__liveFindTune = () => openDeep()
    }
    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('pageshow', onPageShow)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    document.addEventListener('visibilitychange', onVisible)
    // iOS keyboard / address-bar compensation (§41, exactly like the prototype): on a
    // narrow screen, pin the app container to the VISUAL viewport (height + translateY)
    // so the on-screen keyboard or URL-bar shift can't push the fixed header off-screen.
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', onViewportChange)
      window.visualViewport.addEventListener('scroll', onViewportChange)
      fitToViewport()
    }
  })

  // Match the app container to the visual viewport (mobile). On desktop / no
  // visualViewport, clear the overrides so the CSS 100dvh layout governs.
  function fitToViewport() {
    const vv = window.visualViewport
    if (!mainEl) return
    if (!vv || window.innerWidth >= 480) {
      mainEl.style.height = ''
      mainEl.style.transform = ''
      mainEl.style.removeProperty('--results-max')
      return
    }
    mainEl.style.height = vv.height + 'px'
    mainEl.style.transform = 'translateY(' + vv.offsetTop + 'px)'
    // Cap the composer dropdown to the space actually visible above the composer.
    // Its CSS fallback (45vh) is measured against the LAYOUT viewport, which iOS
    // does NOT shrink for the keyboard — an uncapped dropdown can "fit" its own
    // max-height yet have its top rows (the "Log as-is" escape) clipped by main's
    // overflow:hidden with no scrollbar to reach them.
    const composer = mainEl.querySelector('.composer')
    const topnav = mainEl.querySelector('.topnav')
    if (composer && topnav) {
      const avail = composer.getBoundingClientRect().top - topnav.getBoundingClientRect().bottom - 12
      mainEl.style.setProperty('--results-max', Math.max(120, Math.round(avail)) + 'px')
    }
  }
  function onViewportChange() {
    fitToViewport()
    // keep the insertion point / end of the list visible as it resizes under the keyboard
    requestAnimationFrame(() => {
      const sets = mainEl?.querySelector('.sets')
      if (sets && insertAfterId == null) sets.scrollTop = sets.scrollHeight
      ensureSeamVisible()
    })
  }

  onDestroy(() => {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('pageshow', onPageShow)
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    document.removeEventListener('visibilitychange', onVisible)
    if (window.visualViewport) {
      window.visualViewport.removeEventListener('resize', onViewportChange)
      window.visualViewport.removeEventListener('scroll', onViewportChange)
    }
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (reconnectPoll) clearTimeout(reconnectPoll)
    if (rafId != null) cancelAnimationFrame(rafId)
    if (es) es.close()
  })
</script>

<svelte:window bind:innerWidth={winW} onkeydown={onWinKey} />
<!-- Capture phase so inner stopPropagation (composer, trays, modals) can't keep the
     expanded header from auto-closing when the user interacts elsewhere. -->
<svelte:document onpointerdowncapture={collapseHeaderOnOutside} onfocusincapture={collapseHeaderOnOutside} />

<!-- `wide` on <main> means "the two-pane grid is IN EFFECT", which needs the pane to
     actually be there: it only mounts for editors ({#if wide && !readOnly} below), so a
     signed-out viewer got the grid's 440px pane column reserved and empty, with the log
     stranded in the left half. The `wide` state itself stays viewport-only — the preview
     routing and "/" focus target both guard on sidePaneEl. -->
<main bind:this={mainEl} class:view-mode={viewing} class:wide={wide && !readOnly}>
  <!-- Connection dot, floated top-right next to the shared hamburger (templates/live_logging.html)
       so it sits where the app-wide indicator sits on every other page. Tapping it opens
       a popover with the full picture: status, queued edits, and (when the stream is
       down) which server — app vs streaming sidecar — is actually unreachable. -->
  {#if showConnDot}
    <button
      class="conn-btn"
      title={displayStatus}
      aria-label="Connection: {displayStatus}"
      aria-expanded={connPopup}
      onclick={(e) => { e.stopPropagation(); connPopup = !connPopup }}
    ><span class="conn-dot conn-{displayStatus}"></span></button>
    {#if connPopup}
      <div class="conn-popup" role="status">
        <div class="conn-popup-title"><span class="conn-dot conn-{displayStatus}"></span>{connTitle}</div>
        {#if displayStatus === 'live'}
          <div class="conn-popup-line">{mode === 'edit' ? 'Live — changes save and stream instantly.' : 'Watching live — updates appear as others log.'}</div>
          {#if lastEventAt}
            <div class="conn-popup-line">Last server activity {fmtDur(connNow - lastEventAt)} ago.</div>
          {/if}
        {:else if displayStatus === 'offline' && offlineSince}
          <div class="conn-popup-line">{connProbe?.app ? 'Stream down' : 'Offline'} for {fmtDur(connNow - offlineSince)}.</div>
        {/if}
        {#if queuedCount > 0}
          <div class="conn-popup-line conn-popup-queued">
            {queuedCount} change{queuedCount === 1 ? '' : 's'} saved on this device — {displayStatus === 'offline' ? 'will sync when you reconnect.' : 'syncing…'}
          </div>
        {:else if sendingCount > 0}
          <div class="conn-popup-line">{sendingCount} change{sendingCount === 1 ? '' : 's'} saving…</div>
        {:else if mode === 'edit'}
          <div class="conn-popup-line">All changes saved.</div>
        {/if}
        {#if displayStatus !== 'live'}
          <div class="conn-popup-probe">
            <div class="conn-popup-line">App server: {connProbe ? (connProbe.app ? '✓ reachable' : '✕ unreachable') : 'checking…'}</div>
            <div class="conn-popup-line">Live-updates server ({streamHost}): {connProbe ? (connProbe.stream ? '✓ reachable' : '✕ unreachable') : 'checking…'}</div>
            {#if connProbe && connProbe.app && !connProbe.stream}
              <div class="conn-popup-line conn-popup-hint">Only the live-updates server is unreachable — changes still save, but updates from others won't appear until it's back.</div>
            {:else if connProbe && connProbe.app && connProbe.stream}
              {#if streamHostMismatch}
                <div class="conn-popup-line conn-popup-hint">Host mismatch: the page is on {location.host} but the stream is on {streamHost} — login cookies don't cross those hosts, so the stream can't authenticate. Open the app via the other host or set STREAMING_BASE_URL to match.</div>
              {:else}
                <div class="conn-popup-line conn-popup-hint">Both servers respond but the stream isn't connecting — if this persists, the stream may be failing to authenticate.</div>
              {/if}
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  {/if}
  <!-- --header-h feeds the full-bleed band behind this bar (app.css .topnav::before);
       it is the same measurement the toasts already offset by. -->
  <div class="topnav" bind:clientHeight={headerH} style="--header-h:{headerH}px">
    <!-- Mirrors the app-wide header (base.html .header): full-viewport bar, 30px logo +
         site title (hidden on phones, like .logo-text). -->
    <div class="appbar">
      <a class="brand" href="/" aria-label="ceol.io home"><img src="/static/images/logo3-1.png" alt="ceol" /><span class="brand-text">Traditional Irish Session Logs</span></a>
      <!-- The hamburger menu is the SHARED app menu, rendered server-side in the live
           shell (templates/hamburger_menu.html) and floated top-right. 'Find a tune'
           routes to openDeep() here via window.__liveFindTune (set in onMount). -->
    </div>

    <!--
      The session band. Two layers: the always-visible summary row (who/when/how much,
      plus the presence avatars) and, on tap, a labelled detail panel. The panel used to
      be a stack of loose sentences; it's a label/value grid now so each fact has one
      obvious home — and so the date has somewhere to hang its editor (spec 046). The
      whole band sits on its own lighter surface so it never reads as part of the list.
    -->
    <header class="topbar">
      <div class="topbar-row" role="button" tabindex="0" onclick={toggleExpand} onkeydown={(e) => activate(e, toggleExpand)}>
        <div class="topbar-main">
          <div class="session-name">{sessionName || 'Session'}<a class="session-return" href="/sessions/{config.sessionPath}" title="Back to session" onclick={(e) => e.stopPropagation()}>⮐</a></div>
          <!-- This log's own name, when it has one. A weekly session doesn't: the date
               says which night. A festival does, and there the date says nothing on its
               own — so it sits above the date, on its own line, rather than being packed
               into it. Absent when unset, so the ordinary case is unchanged. -->
          {#if instanceName}
            <div class="session-instance-name">{instanceName}</div>
          {/if}
          <div class="session-date">{sessionDate}{#if !expanded && ordered.length}{sessionDate ? ' · ' : ''}{tuneSummary}{/if}</div>
          {#if notesText && !expanded && logComplete}
            <div class="session-notes">{notesText}</div>
          {/if}
        </div>
        <!-- Right-hand controls, in one cluster: who's here, help, expand. -->
        <span class="topbar-tools">
          <span class="topbar-presence">
            {#each readOnly ? [] : roster as p (p.person_id)}
              <span class="avatar" class:away={p.away} style="background:{colorFor(p.arrival_seq)}" title="{p.name}{p.away ? ' (away)' : p.devices > 1 ? ` (${p.devices} devices)` : ''}">
                {initials(p.name)}{#if !p.away && p.devices > 1}<sup>{p.devices}</sup>{/if}
              </span>
            {/each}
          </span>
          <a class="header-help" href="/help/session-tracking/live-logger" title="How to use the live logger" onclick={(e) => e.stopPropagation()}>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </a>
          <span class="header-chevron" class:up={expanded}>▾</span>
        </span>
      </div>
      {#if expanded}
        <div class="header-expand">
          <!-- Date carries the time range too (spec 048). The session's Logs tab has
               always shown when an instance ran; the logger showed only the day, so
               the one screen that can edit it couldn't see it. Same formatter, so the
               two never disagree. -->
          <div class="hx-row">
            <span class="hx-label">Date</span>
            <span class="hx-val">
              <!-- Separator inside the expression: Svelte trims whitespace at the
                   start of an element, so a literal " · " here loses its space. -->
              {sessionDate || '—'}{#if timeLabel}<span class="hx-time">{` · ${timeLabel}`}</span>{/if}
            </span>
            {#if !readOnly}
              <button class="hx-act" onclick={(e) => { e.stopPropagation(); openDateEditor() }}>Change</button>
            {/if}
          </div>
          <!-- Name sits under Date because it answers the same question — which log is
               this? — and because at a festival the date can't answer it alone. Shown
               even when unset, since an unnamed log that COULD be named is exactly the
               case the row exists to fix. Unnamed reads differently by session type:
               "The usual" is a true statement about a weekly session's venue, but says
               nothing at a festival where there is no usual. -->
          {#if instanceName || !readOnly}
            <div class="hx-row">
              <span class="hx-label">Name</span>
              <span class="hx-val">{instanceName || (isFestival ? 'Unnamed' : 'The usual')}</span>
              {#if !readOnly}
                <button class="hx-act" onclick={(e) => { e.stopPropagation(); openNameEditor() }}>
                  {instanceName ? 'Rename' : 'Name it'}
                </button>
              {/if}
            </div>
          {/if}
          <div class="hx-row">
            <span class="hx-label">Tunes</span>
            <span class="hx-val">{tuneSummary}</span>
          </div>
          {#if trackAttendance && !readOnly}
            <div class="hx-row">
              <span class="hx-label">{attendanceLabel}</span>
              <span class="hx-val">
                <b class="hx-strong">{checkedIn.length}</b>
                {checkedIn.length ? `— ${checkedIn.map((a) => a.display_name).join(', ')}` : '— no one checked in yet'}
              </span>
              <button class="hx-act" onclick={(e) => { e.stopPropagation(); openAttendance() }}>Manage</button>
            </div>
          {/if}
          {#if canManageRecordings}
            <div class="hx-row">
              <span class="hx-label">Recordings</span>
              <span class="hx-val">
                {#if recordingCount === null}
                  —
                {:else if recordingCount === 0}
                  none uploaded yet
                {:else}
                  <b class="hx-strong">{recordingCount}</b>
                  {recordingCount === 1 ? 'recording' : 'recordings'}
                {/if}
              </span>
              <button class="hx-act" onclick={(e) => { e.stopPropagation(); recordingsOpen = true }}>Manage</button>
            </div>
          {/if}
          {#if !readOnly && roster.length}
            <div class="hx-row">
              <span class="hx-label">Logging</span>
              <span class="hx-val">
                {roster.filter((p) => !p.away).map((p) => p.name).join(', ') || 'no one right now'}
                {#if roster.some((p) => p.away)}
                  <span class="hx-away">· away: {roster.filter((p) => p.away).map((p) => p.name).join(', ')}</span>
                {/if}
              </span>
            </div>
          {/if}
          {#if readOnly}
            <!-- Signed out: notes are part of the public log, but read-only. -->
            {#if notesText}
              <div class="hx-row">
                <span class="hx-label">Notes</span>
                <span class="hx-val header-notes-ro">{notesText}</span>
              </div>
            {/if}
          {:else}
            <div class="hx-row hx-notes">
              <span class="hx-label">Notes</span>
              <span class="hx-val header-notes-edit">
                <textarea
                  class="hn-area"
                  rows="2"
                  placeholder="Add notes for this session…"
                  bind:value={notesDraft}
                  onclick={(e) => e.stopPropagation()}
                ></textarea>
                {#if notesDraft !== notesText}
                  <span class="hn-actions">
                    <button class="hn-save" onclick={(e) => { e.stopPropagation(); saveNotes() }}>Save</button>
                    <button class="hn-cancel" onclick={(e) => { e.stopPropagation(); notesDraft = notesText }}>Cancel</button>
                  </span>
                {/if}
              </span>
            </div>
          {/if}
          <div class="hx-row header-complete">
            <span class="hx-label">Status</span>
            {#if logComplete}
              <span class="hx-val hc-done">✓ Marked complete</span>
              {#if !readOnly}
                <button class="hx-act" onclick={(e) => { e.stopPropagation(); markIncomplete() }}>Re-open</button>
              {/if}
            {:else}
              <span class="hx-val">Still logging</span>
              {#if !readOnly}
                <button class="hx-act" onclick={(e) => { e.stopPropagation(); markComplete() }}>Mark complete</button>
              {/if}
            {/if}
          </div>
        </div>
      {/if}
    </header>
  </div>

  <!-- Transient toasts (other users' activity, reconnect summary) hover just below
       the fixed header, sliding in from / out to the top, under the header. -->
  <div class="toasts" style="top:{headerH}px">
    {#each activities as a (a.id)}
      <p class="toast activity" style="background:{a.color}" transition:fly={{ y: -24, duration: 240 }} animate:flip={{ duration: 180 }}>
        {a.text}
      </p>
    {/each}
    {#if syncMsg}
      <p class="toast sync-msg" transition:fly={{ y: -24, duration: 240 }}>↻ {syncMsg}</p>
    {/if}
  </div>

  <!-- Reconnect reconciliation review (§G): offline changes the server couldn't apply. -->
  {#if reconcile}
    <div class="reconcile-scrim" role="button" tabindex="-1" aria-label="Dismiss" onclick={dismissReconcile} onkeydown={(e) => activate(e, dismissReconcile)}></div>
    <div class="reconcile" role="dialog" aria-modal="true">
      <div class="reconcile-head">Some offline changes didn’t stick</div>
      <p class="reconcile-sub">
        {reconcile.items.length} change{reconcile.items.length === 1 ? '' : 's'} you made offline couldn’t be applied when you reconnected — usually because someone else changed the same tune first.
      </p>
      <ul class="reconcile-list">
        {#each reconcile.items as it, i (i)}
          <li><span class="rc-what">{reconcileDesc(it)}</span><span class="rc-why">— {reconcileWhy(it)}</span></li>
        {/each}
      </ul>
      <div class="reconcile-actions">
        <button class="rc-ok" onclick={dismissReconcile}>Got it</button>
      </div>
    </div>
  {/if}

  <div class="feed-msgs">
    {#if notice}<div class="notice" role="button" tabindex="0" onclick={() => (notice = '')} onkeydown={(e) => activate(e, () => (notice = ''))}>{notice}</div>{/if}
    {#if queuedCount > 0}
      <p class="offline-banner">
        ⏳ {queuedCount} change{queuedCount === 1 ? '' : 's'} queued{displayStatus === 'offline' ? ' — offline' : ', syncing…'}
      </p>
    {/if}
  </div>

  <div class="sets" bind:this={setsEl} onscroll={onScroll}>
    <!-- Pull-down filter: hidden above the fold, revealed by scrolling to the very top.
         Focusing/typing enters search mode; filters displaySegments live. (§024) -->
    <div class="searchbar" class:on={searchMode}>
      <span class="searchbar-icon" aria-hidden="true">{listMode ? '★' : '🔍'}</span>
      {#if listMode}
        <!-- highlight mode: the instrument scope replaces the filter box -->
        {#if myInstruments.length > 1}
          <select class="searchbar-inst" aria-label="Instrument" bind:value={listInstrument}>
            <option value="all">All instruments</option>
            {#each myInstruments as i (i.instrument)}
              <option value={i.instrument}>{i.instrument}</option>
            {/each}
          </select>
        {:else}
          <span class="searchbar-instlabel">{myInstruments[0]?.instrument || 'My tune list'}</span>
        {/if}
        {#if listLoading}<span class="spinner" aria-label="Loading your list"></span>{/if}
      {:else}
        <input
          class="searchbar-input"
          placeholder="Filter tunes…"
          bind:value={searchText}
          bind:this={searchInputEl}
          onfocus={() => (searchMode = true)}
          oninput={onFilterInput}
          onblur={rememberFilter}
          onkeydown={onFilterKey}
          autocorrect="off"
          autocapitalize="off"
          autocomplete="off"
          spellcheck="false"
        />
        {#if searchMode && searchText}<button class="searchbar-clear" title="Clear filter" onclick={doneSearching}>✕</button>{/if}
      {/if}
      <!-- my-list highlight toggle: color every tune by MY learn status (needs a list,
           so it's absent when signed out) -->
      {#if !readOnly}
        <button class="listmode-btn" class:on={listMode} title={listMode ? 'Hide my list status' : 'Show my list status'} aria-pressed={listMode} onclick={toggleListMode}>★</button>
      {/if}
      <!-- selection-mode toggle (spec 029 §A): available in edit AND view (copy-only) -->
      <button class="selmode-btn" class:on={selectMode} title={selectMode ? 'Leave selection mode' : 'Select tunes'} aria-pressed={selectMode} onclick={toggleSelectMode}>☑</button>
    </div>
    <!-- min-height:100% (in CSS) guarantees ≥ SEARCH_BAR_H of overflow so the bar can always
         tuck out of sight, even when the log is too short to fill the viewport -->
    <div class="sets-body">
    {#if selectMode}
      <div class="selrow">
        <button onclick={selectAllVisible}>Select all</button>
        <span aria-hidden="true">·</span>
        <button onclick={selectNone}>None</button>
      </div>
      {#if listMode}
        <!-- select-by-status shortcuts (additive, like Select all) -->
        <div class="selrow selrow-status">
          <span class="selrow-k">Select:</span>
          <button class="ls-not-on-list" onclick={() => selectByStatus(NOT_ON_LIST)}>not on list</button>
          <span aria-hidden="true">·</span>
          <button class="ls-want-to-learn" onclick={() => selectByStatus('want to learn')}>want to learn</button>
          <span aria-hidden="true">·</span>
          <button class="ls-learning" onclick={() => selectByStatus('learning')}>learning</button>
          <span aria-hidden="true">·</span>
          <button class="ls-learned" onclick={() => selectByStatus('learned')}>learned</button>
        </div>
      {/if}
    {/if}
    {#if drag?.started && dragKeys?.has('top-new')}
      <!-- drag-only drop zone: land as own set(s) at the very start (spec 029 §F) -->
      <div class="drop-extreme" data-seam="top-new" class:drop-active={drag.activeKey === 'top-new'}>new set</div>
    {/if}
    {#each displaySegments as seg, si (seg.tunes[0].session_instance_tune_id)}
      <div class="set">
        <button class="set-label" class:open={openTrayId === seg.tunes[0].session_instance_tune_id} onclick={(e) => { e.stopPropagation(); toggleTray(seg.tunes[0].session_instance_tune_id) }}>{setLabel(seg.tunes)}</button>
        <!-- Both of these ride the card's top-right corner, so they share ONE
             positioned row rather than each claiming the same coordinates. The ▶ is
             last, keeping it in the very corner whether or not a starter is named. -->
        <div class="set-topright">
          {#if trackStarters && !readOnly && setStarterName(seg)}
            <button class="starter-pill" class:flash={starterFlashId === seg.tunes[0].session_instance_tune_id} title="Started by {setStarterName(seg)}" onclick={(e) => { e.stopPropagation(); openTrayId = seg.tunes[0].session_instance_tune_id }}>▸ {setStarterName(seg)}</button>
          {/if}
          <!-- Play the whole set, from its first timestamped tune. Shown as soon as ANY
               tune in the set has a mark, since a part-marked set still plays what's there. -->
          {#if !selectMode && queueFor(seg.tunes).length}
            {@const setPlaying = playQ && queueFor(seg.tunes).includes(playingId)}
            <button
              class="setplay-btn"
              class:on={setPlaying}
              title={setPlaying ? 'Stop' : 'Play this set'}
              aria-label={setPlaying ? 'Stop' : 'Play this set'}
              onclick={(e) => { e.stopPropagation(); setPlaying ? stopPlayback() : startQueue(queueFor(seg.tunes)) }}
            >{setPlaying ? '■' : '▶'}</button>
          {/if}
        </div>
        <!-- The tray holds only people facts (starter, logger), so signed out it has
             nothing to show and never opens. -->
        {#if !readOnly && openTrayId === seg.tunes[0].session_instance_tune_id}
          <div class="set-tray">
            {#if trackStarters && !readOnly}
            <div class="tray-row">
              <span class="tray-k">Started by</span>
              {#if viewing}
                <span class="starter-value" class:set={setStarterName(seg)}>{setStarterName(seg) || 'Not set'}</span>
              {:else}
                <button
                  class="starter-value"
                  class:set={setStarterName(seg)}
                  onclick={() => openStarterPicker(seg.tunes[0].session_instance_tune_id)}
                >{setStarterName(seg) || 'Not set'}</button>
              {/if}
            </div>
            {/if}
            {#if !readOnly && loggedInfo(seg.tunes)}
              {@const li = loggedInfo(seg.tunes)}
              <div class="tray-row"><span class="tray-k">Logged by</span><span class="tray-v">{li.who || 'someone'}{li.when ? ` · ${li.when}` : ''}</span></div>
            {/if}
          </div>
        {/if}
        {#if canEdit}
          <div class="seam start-seam" role="button" tabindex="0" data-seam={`start:${seg.tunes[0].session_instance_tune_id}`} class:drop-eligible={dragKeys?.has(`start:${seg.tunes[0].session_instance_tune_id}`)} class:drop-active={drag?.started && drag.activeKey === `start:${seg.tunes[0].session_instance_tune_id}`} class:active={visibleSeam === `start:${seg.tunes[0].session_instance_tune_id}`} onclick={() => setCursor({ before: seg.tunes[0].session_instance_tune_id })} onkeydown={(e) => activate(e, () => setCursor({ before: seg.tunes[0].session_instance_tune_id }))}>
            {#if visibleSeam === `start:${seg.tunes[0].session_instance_tune_id}`}
              <span class="seam-line"></span>
            {:else}<span class="seam-plus">＋ start of set</span>{/if}
          </div>
        {/if}
        {#each seg.tunes as r, ti (r.session_instance_tune_id)}
          {@const lst = listMode ? rowListStatus(r) : null}
          <div
            class="tune-row"
            role="button"
            tabindex="0"
            data-sit={r.session_instance_tune_id}
            class:ls-want-to-learn={lst === 'want to learn'}
            class:ls-learning={lst === 'learning'}
            class:ls-learned={lst === 'learned'}
            class:ls-not-on-list={lst === NOT_ON_LIST}
            class:low={!r._temp && r.confidence != null && r.confidence <= 70}
            class:unlinked={!r._resolving && !r.tune_id && r.record_type === 'tune'}
            class:has-by={!viewing && !r._temp && r.tune_id && loggerColorIdx(r) != null}
            class:pending={r._resolving}
            class:queued={r._temp && r._status === 'queued'}
            class:removing={r._removing}
            class:selected={canEdit && !selectMode && selectedId === r.session_instance_tune_id}
            class:editing={editingId === r.session_instance_tune_id}
            class:bulk-selected={selectMode && selected.has(r.session_instance_tune_id)}
            class:drag-source={drag?.started && drag.block.recordIds.includes(r.session_instance_tune_id)}
            class:flash-mine={flashing.get(r.session_instance_tune_id)?.kind === 'mine'}
            class:flash-remote={flashing.get(r.session_instance_tune_id)?.kind === 'remote'}
            class:flash-merge={flashing.get(r.session_instance_tune_id)?.kind === 'merge'}
            class:flash-highlight={flashing.get(r.session_instance_tune_id)?.kind === 'highlight'}
            class:audio-playing={playingId === r.session_instance_tune_id}
            style={canEdit ? rowStyle(r) : ''}
            onclick={(e) => rowClick(r, e)}
            onkeydown={(e) => activate(e, () => rowClick(r))}
          >
            <span class="name">{#if searchMode && searchText.trim() && tuneNameMatches(r, searchText.trim().toLowerCase())}{@const p = suggestionParts(r.name, searchText.trim())}{p.pre}<span class="search-hit">{p.mid}</span>{p.post}{:else}{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}{/if}{#if r.key_override}<span class="key-override">(in {r.key_override})</span>{/if}</span>
            {#if lst}<span class="ls-chip {statusClass(lst)}">{lst}</span>{/if}
            {#if r._temp}
              {#if r._resolving}
                <!-- match still resolving: the one case worth a spinner (what got logged is unknown) -->
                <span class="actions"><span class="spinner"></span><span class="pend-label">resolving…</span></span>
              {:else}
                <!-- confident add: reads as fully logged; the op syncs transparently in the
                     background. Only an offline-queued op gets a marker (§D). -->
                {#if !r.tune_id && r.record_type === 'tune'}<span class="row-warn" title="Not linked to a catalog tune">⚠ unlinked</span>{/if}
                {#if r._status === 'queued'}<span class="pend-label offline" title="Saved offline — syncs when you reconnect">offline</span>{/if}
              {/if}
            {:else if r._removing}
              <span class="actions"><span class="spinner"></span><span class="pend-label">removing</span><button class="restore" onclick={(e) => { e.stopPropagation(); restore(r.session_instance_tune_id) }}>Restore</button></span>
            {:else}
              {#if !r.tune_id && r.record_type === 'tune'}<span class="row-warn" title="Not linked to a catalog tune">⚠ unlinked</span>{/if}
              <!-- Hear this tune. Deliberately NOT gated on canEdit (unlike ⓘ): playing
                   back is reading, so it survives view and search mode. Only the marks
                   gate it — a tune nobody timestamped has no button at all. -->
              {#if !selectMode && resolved.has(r.session_instance_tune_id)}
                <button
                  class="play-btn"
                  class:on={playingId === r.session_instance_tune_id}
                  title={playingId === r.session_instance_tune_id && !audioPaused ? 'Pause' : 'Play this tune'}
                  aria-label={playingId === r.session_instance_tune_id && !audioPaused ? 'Pause' : 'Play this tune'}
                  onclick={(e) => { e.stopPropagation(); toggleTune(seg.tunes, r.session_instance_tune_id) }}
                >{playingId === r.session_instance_tune_id && !audioPaused ? '❚❚' : '▶'}</button>
                <!-- Circular, because the glyph it replaced (⤓) carries its mass in the
                     bar at the bottom and read as sitting lower than the ▶ beside it. A
                     ring is symmetric about its own centre, so the two line up whatever
                     the arrow inside is doing. The ring doubles as the spinner.
                     Still an <a href>: the click is intercepted for the spinner, but
                     middle-click and "Save link as" keep working the plain way. -->
                {@const busy = downloading.has(r.session_instance_tune_id)}
                <a
                  class="dl-btn"
                  class:busy
                  href={`/api/recordings/${audioRec.recording_id}/segments/${r.session_instance_tune_id}/download`}
                  title={busy ? 'Preparing the file…' : 'Download this tune'}
                  aria-label={busy ? 'Preparing the file' : 'Download this tune'}
                  aria-busy={busy}
                  download
                  onclick={(e) => { e.stopPropagation(); e.preventDefault(); downloadTune(r) }}
                >
                  <svg class="dl-icon" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
                    {#if busy}
                      <!-- same ring, opened into an arc and spun; dasharray is a quarter
                           of the r=9 circumference (~56.5) -->
                      <circle class="dl-arc" cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-dasharray="14 43" />
                    {:else}
                      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.5" />
                      <path d="M12 7.4 V14.8 M8.9 11.7 L12 14.8 L15.1 11.7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                    {/if}
                  </svg>
                </a>
              {/if}
              {#if canEdit && !selectMode && r.tune_id}<button class="info-btn" title="Tune details" onclick={(e) => { e.stopPropagation(); openDrawer(r) }}>ⓘ</button>{/if}
              {#if canEdit && !selectMode && selectedId === r.session_instance_tune_id}
                <!-- selected-row insert points: pills riding the row's edges (like the
                     seam Split/Join pills) that place the cursor before/after this tune -->
                <button class="insert-pill top" title="Insert above" aria-label="Insert above" onclick={(e) => { e.stopPropagation(); insertBeforeRow(r.session_instance_tune_id) }}>↑</button>
                <button class="insert-pill bottom" title="Insert below" aria-label="Insert below" onclick={(e) => { e.stopPropagation(); insertAfterRow(r.session_instance_tune_id) }}>↓</button>
              {/if}
            {/if}
            {#if selectMode}
              {#if selected.has(r.session_instance_tune_id)}<span class="sel-badge" aria-hidden="true">✓</span>{/if}
              {#if canEdit && !r._temp && !r._removing}
                <!-- grab bar (spec 029 §F): touch-action:none here ONLY, so the handle
                     drags immediately while the rest of the row still scrolls the list -->
                <span
                  class="grab"
                  role="button"
                  tabindex="-1"
                  aria-label="Drag to move"
                  onpointerdown={(e) => startDrag(e, r)}
                  onpointermove={dragMove}
                  onpointerup={dragEnd}
                  onpointercancel={cancelDrag}
                  onclick={(e) => e.stopPropagation()}
                >⠿</span>
              {/if}
            {/if}
          </div>
          {#if canEdit && selectedId === r.session_instance_tune_id}
            {#if r._resolving}
              <!-- pending placeholder: bail out of the in-flight match -->
              <div class="row-actions">
                <button onclick={() => { selectedId = null; cancelResolving(true) }}>✎ Edit</button>
                <button class="danger" onclick={() => { selectedId = null; cancelResolving(false) }}>🗑 Remove</button>
              </div>
            {:else if r._temp}
              <!-- queued offline add: cancel it locally — the op hasn't reached the server -->
              <div class="row-actions">
                <button class="danger" onclick={() => cancelQueuedRow(r.session_instance_tune_id)}>🗑 Remove</button>
              </div>
            {:else}
            <div class="row-actions">
              {#if r.tune_id}<button onclick={() => openDrawer(r)}>ⓘ Info</button>{/if}
              {#if r.confidence != null && r.confidence <= 70}
                <button onclick={() => confirmRow(r.session_instance_tune_id)}>✓ Confirm</button>
              {/if}
              <button onclick={() => startEdit(r.session_instance_tune_id)}>✎ Edit</button>
              <button class="danger" onclick={() => removeRow(r.session_instance_tune_id)}>🗑 Remove</button>
            </div>
            {/if}
          {/if}
          {#if !r._temp && canEdit}
            {#if endIsOpen && si === displaySegments.length - 1 && ti === seg.tunes.length - 1}
              <!-- last tune of the open set: this seam IS the end (append) point -->
              <div class="seam end-seam" role="button" tabindex="0" data-seam="end" class:drop-eligible={dragKeys?.has('end')} class:drop-active={drag?.started && drag.activeKey === 'end'} class:active={visibleSeam === 'end'} onclick={() => setCursor(null)} onkeydown={(e) => activate(e, () => setCursor(null))}>
                {#if visibleSeam === 'end'}<span class="seam-line"></span>{:else}<span class="seam-plus">＋</span>{/if}
              </div>
              {#if drag?.started && dragKeys?.has('end-new')}
                <!-- drag-only drop zone: land as own set(s) below the open end (spec 029 §F) -->
                <div class="drop-extreme" data-seam="end-new" class:drop-active={drag.activeKey === 'end-new'}>new set</div>
              {/if}
            {:else}
              <div class="seam" role="button" tabindex="0" data-seam={`after:${r.session_instance_tune_id}`} class:drop-eligible={dragKeys?.has(`after:${r.session_instance_tune_id}`)} class:drop-active={drag?.started && drag.activeKey === `after:${r.session_instance_tune_id}`} class:active={visibleSeam === `after:${r.session_instance_tune_id}`} onclick={() => setCursor(r.session_instance_tune_id)} onkeydown={(e) => activate(e, () => setCursor(r.session_instance_tune_id))}>
                {#if visibleSeam === `after:${r.session_instance_tune_id}`}
                  <span class="seam-line"></span>
                  {#if ti < seg.tunes.length - 1}
                    <button class="seam-pill split" onclick={(e) => { e.stopPropagation(); splitAt(r.session_instance_tune_id) }}>Split</button>
                  {/if}
                {:else}<span class="seam-plus">＋</span>{/if}
              </div>
            {/if}
          {/if}
        {/each}
      </div>
      {#if canEdit && si < displaySegments.length - 1 && seg.breakAfter != null}
        <div class="seam inter-seam" role="button" tabindex="0" data-seam={`inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`} class:drop-eligible={dragKeys?.has(`inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`)} class:drop-active={drag?.started && drag.activeKey === `inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`} class:active={visibleSeam === `inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`} onclick={() => setNewSetCursor(displaySegments[si + 1].tunes[0].session_instance_tune_id)} onkeydown={(e) => activate(e, () => setNewSetCursor(displaySegments[si + 1].tunes[0].session_instance_tune_id))}>
          {#if visibleSeam === `inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`}
            <span class="seam-line"></span>
            <button class="seam-pill join" onclick={(e) => { e.stopPropagation(); joinAt(seg.breakAfter) }}>Join</button>
          {:else}<span class="seam-plus">＋ new set</span>{/if}
        </div>
      {/if}
    {:else}
      {#if loaded}
        <p class="empty">No tunes yet — log one below.</p>
      {:else}
        <!-- first-load skeleton: tune-sized rows with a shimmer sweeping across them -->
        <div class="skeleton" aria-hidden="true">
          <div class="sk-row" style="width: 62%"></div>
          <div class="sk-row" style="width: 78%"></div>
          <div class="sk-row" style="width: 45%"></div>
        </div>
      {/if}
    {/each}
    {#if ordered.length && !endIsOpen && canEdit}
      <!-- closed end (trailing break): the end cursor starts a NEW set here -->
      <div class="seam end-seam new-set-end" role="button" tabindex="0" data-seam="end" class:drop-eligible={dragKeys?.has('end')} class:drop-active={drag?.started && drag.activeKey === 'end'} class:active={visibleSeam === 'end'} onclick={() => setCursor(null)} onkeydown={(e) => activate(e, () => setCursor(null))}>
        {#if visibleSeam === 'end'}
          <span class="seam-line"></span><span class="seam-hint">new set</span>
        {:else}<span class="seam-plus">＋ new set</span>{/if}
      </div>
    {/if}
    <!-- scroll room so the end-of-list seam can rise ABOVE the upward dropdown (§D) -->
    {#if dropdownOpen}<div class="drop-spacer" style="height:{resultsH}px" aria-hidden="true"></div>{/if}
    </div>
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  {#if canEdit && !readOnly && othersTyping.length}
    <div class="typing">
      {#each othersTyping as t (t.person_id)}<span class="t-name" style="color:{colorFor(t.arrival_seq)}">{t.name}</span>{/each}
      <span class="t-verb">{othersTyping.length === 1 ? 'is' : 'are'} typing…</span>
    </div>
  {/if}

  <!-- One element for the whole page. preload="none" so opening a night with audio
       costs nothing until someone actually presses play; from then on S3 range
       requests make a mid-recording seek cheap. -->
  {#if currentSource}
    <audio
      bind:this={audioEl}
      src={currentSource.url}
      preload="none"
      onplay={onAudioPlay}
      onpause={onAudioPause}
      onended={stopPlayback}
      onerror={onAudioError}
    ></audio>
  {/if}

  <div class="dock">
    {#if playQ}
      <!-- in:, NOT transition:. stopPlayback() collapses the panel and drops the
           player in the same tick, so an OUTRO would be animating a container whose
           height is changing underneath it — it never completes, and the dock is left
           holding a dead `inert` panel. Nothing is lost: the entrance is the part with
           anything to say, and dismissal is already an explicit tap. -->
      <div class="player" class:open={playerOpen} in:fly={{ y: 8, duration: 160 }}>
        {#if playerOpen}
          <div class="pp-body">
            <!-- The scrubber is scoped to THIS TUNE, not the whole recording: the
                 recording is three hours long and the thing being listened to is
                 ninety seconds of it, so a full-length bar would make the tune an
                 unclickable sliver. -->
            <input
              class="pp-scrub"
              type="range"
              min="0"
              max={Math.max(1, tuneLenMs)}
              step="100"
              value={scrubValue}
              aria-label="Position within this tune"
              oninput={onScrubInput}
              onchange={onScrubCommit}
            />
            <div class="pp-times">
              <span>{formatClock(scrubValue)}</span>
              <span class="pp-pos">{playQ.idx + 1} of {playQ.ids.length}</span>
              <span>−{formatClock(Math.max(0, tuneLenMs - scrubValue))}</span>
            </div>
            <div class="pp-transport">
              <button class="pp-btn" title="Previous tune" aria-label="Previous tune" onclick={prevTune}>⏮</button>
              <button class="pp-btn big" title={audioPaused ? 'Play' : 'Pause'} aria-label={audioPaused ? 'Play' : 'Pause'} onclick={togglePlayPause}>{audioPaused ? '▶' : '❚❚'}</button>
              <button class="pp-btn" title="Next tune" aria-label="Next tune" disabled={playQ.idx + 1 >= playQ.ids.length} onclick={nextTune}>⏭</button>
              <button class="pp-btn" title="Stop" aria-label="Stop" onclick={stopPlayback}>■</button>
            </div>
            <div class="pp-modes">
              <button class="pp-mode" class:on={repeatOne} aria-pressed={repeatOne} onclick={() => (repeatOne = !repeatOne)}>Repeat 1</button>
              <button class="pp-mode" class:on={autoContinue} aria-pressed={autoContinue} onclick={() => (autoContinue = !autoContinue)}>Auto-continue</button>
              {#if canSwitchHd}
                {@const hdSize = formatBytes(audioSources.find((s) => s.id === 'master')?.size_bytes)}
                <button
                  class="pp-mode"
                  class:on={hdOn}
                  aria-pressed={hdOn}
                  title={hdOn ? 'Back to the smaller stream' : `Play the full-quality file${hdSize ? ` (${hdSize})` : ''} — best on a fast connection`}
                  onclick={() => switchAudioSource(hdOn ? 'proxy' : 'master')}
                >HD{#if hdSize && !hdOn}<span class="pp-mode-sub">{hdSize}</span>{/if}</button>
              {/if}
            </div>
          </div>
        {/if}
        <div class="playbar">
          <button class="pb-toggle" title={audioPaused ? 'Play' : 'Pause'} aria-label={audioPaused ? 'Play' : 'Pause'} onclick={togglePlayPause}>{audioPaused ? '▶' : '❚❚'}</button>
          <button class="pb-open" aria-expanded={playerOpen} title={playerOpen ? 'Hide controls' : 'Show controls'} onclick={() => (playerOpen = !playerOpen)}>
            <span class="pb-name">{byId.get(playingId)?.name || 'Playing'}</span>
            <span class="pb-time">{formatClock(playhead)} / {formatClock(tuneLenMs)}</span>
            <span class="pb-chev" aria-hidden="true">{playerOpen ? '⌄' : '⌃'}</span>
          </button>
          <button class="pb-stop" title="Stop" aria-label="Stop" onclick={stopPlayback}>×</button>
        </div>
      </div>
    {/if}
    {#if audioErr}<div class="playbar err">{audioErr}</div>{/if}
    {#if undoDelete}
      <div class="undo-toast" transition:fly={{ y: 8, duration: 160 }}>
        <span>Deleted {undoDelete.count} tune{undoDelete.count === 1 ? '' : 's'}</span>
        <button class="undo-btn" onclick={undoBulkDelete}>Undo</button>
      </div>
    {/if}
    {#if selectMode}
      <!-- selection bottom bar (spec 029 §C); view mode is copy-only -->
      <footer class="selbar">
        <span class="selcount">{selected.size} selected</span>
        <button class="sel-act" disabled={!selected.size} onclick={copySelection}>Copy</button>
        {#if !viewing}
          <button class="sel-act" class:dim={!lastCopy} disabled={searchMode} title="Paste tunes from clipboard" onclick={pasteClipboard}>Paste</button>
          <button class="sel-act sel-danger" disabled={!selected.size} onclick={bulkDelete}>Delete</button>
          {#if trackStarters}
            <button class="sel-act" disabled={!selected.size} onclick={openAssign}>Assign</button>
          {/if}
        {/if}
        {#if listMode}
          <!-- bulk add-to-list / set-status (my personal list — safe in view mode too) -->
          <button class="sel-act" disabled={!selected.size || listBusy} title="Add the selected tunes to my list / change their status" onclick={() => (listStatusOpen = true)}>My list</button>
        {/if}
        <button class="sel-done" onclick={exitSelectMode}>Done</button>
      </footer>
    {:else if searchMode}
      <footer class="viewbar searchbar-dock">
        <button class="editbtn done-search" onclick={doneSearching}>Done Searching</button>
      </footer>
    {:else}
    {#if !atEnd}
      <button class="goend-pill" onclick={goToEnd}>↓ Go to end</button>
    {/if}
    {#if viewing}
      <footer class="viewbar">
        {#if readOnly}
          <!-- Signed out: no edit affordance at all, just the way in. -->
          <span class="logdone">
            {#if logComplete}✓ This session has been fully logged{:else}Viewing this session log{/if}
            · <a class="viewbar-login" href="/login?next={encodeURIComponent(location.pathname + location.search)}">Log in to edit</a>
          </span>
        {:else if logComplete}
          <span class="logdone">✓ This session has been fully logged</span>
        {:else}
          <button class="editbtn" onclick={() => setMode('edit')}>✎ Edit log</button>
        {/if}
      </footer>
    {:else}
    {#if showNext || results.length || tsInputId != null || (noMatch && editingId == null)}
      <ul class="results" role="listbox" id="composer-results" bind:clientHeight={resultsH}>
        {#if tsInputId != null}
          <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->
          <li class="result-ts" role="option" aria-selected="false" onmousedown={(e) => e.preventDefault()} onclick={previewThesessionInput}>
            <span class="r-name">🔍 Tune #{tsInputId} from thesession.org…</span>
          </li>
        {/if}
        {#if showNext && nextSuggestion}
          {@const parts = suggestionParts(nextSuggestion.name, input)}
          <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->
          <li id="cres-0" class="result-next" class:hl={composerHl === 0} role="option" aria-selected={composerHl === 0} onmousedown={(e) => e.preventDefault()} onclick={() => pickResult(nextSuggestion)}>
            <span class="r-arrow" aria-hidden="true">→</span>
            <span class="r-name">{parts.pre}<strong>{parts.mid}</strong>{parts.post}</span>
            <span class="r-meta">{nextSuggestion.tune_type || ''}<span class="r-next-label"> · usually next</span></span>
            <button class="r-dismiss" type="button" title="Don't suggest this next" aria-label="Dismiss suggestion" onmousedown={(e) => e.preventDefault()} onclick={(e) => { e.stopPropagation(); dismissNext() }}>×</button>
          </li>
        {/if}
        {#each visibleResults as t, vi (t.tune_id)}
          {@const ci = (showNext && nextSuggestion ? 1 : 0) + vi}
          <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->
          <li id="cres-{ci}" class:hl={composerHl === ci} role="option" aria-selected={composerHl === ci} onmousedown={(e) => e.preventDefault()} onclick={() => pickResult(t)}>
            <span class="r-name">{t.name}</span>
            <span class="r-meta">
              {t.tune_type || ''}{#if t.in_session_tune}<span class="r-insession"> · in session</span>{/if}{#if t.abc}<span class="r-abc"> · ♪ notation</span>{/if}
            </span>
            <button class="r-peek" title="Look closer before logging" aria-label={`Preview ${t.name} before logging`} onmousedown={(e) => e.preventDefault()} onclick={(e) => { e.stopPropagation(); openQuickPreview(vi) }}>🔍</button>
          </li>
        {/each}
        {#if noMatch && !results.length}
          <li class="result-empty">No tunes match your search</li>
        {/if}
        {#if resolving}
          <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->
          <li class="result-asis" role="option" aria-selected="false" onmousedown={(e) => e.preventDefault()} onclick={logAsIs}>
            <span class="r-name">Log “{resolving.text}” as-is</span>
          </li>
        {/if}
      </ul>
    {/if}

    {#if ambiguous}
      <div class="ambig-hint" transition:fly={{ y: 8, duration: 160 }}>
        <span><b>“{resolving ? resolving.text : input.trim()}”</b> matches several tunes — tap one, press Enter for the top match, or “Log as-is”.</span>
      </div>
    {/if}

    {#if mergeNudge}
      <div class="merge-nudge" transition:fly={{ y: 8, duration: 160 }}>
        <span class="mn-text"><b>{mergeNudge.name}</b> is already in this set — merged.</span>
        <button class="mn-keep" onclick={keepBoth}>Keep both</button>
        <button class="mn-ok" onclick={dismissMerge} aria-label="Dismiss">✕</button>
      </div>
    {/if}

    {#if editingId != null}
      <div class="edit-banner">
        <span class="edit-label">Editing <b>{editingName}</b> — pick a match, or type a new name</span>
        <button class="edit-unlink" onclick={unlinkEdit} title="Drop the catalog link, keep the text">Unlink</button>
      </div>
    {/if}

    <div class="composer">
      <div class="composer-field">
        <input
          size="1"
          class:ambiguous={ambiguous}
          class:locked={composerLocked}
          readonly={composerLocked}
          autocorrect="off"
          autocapitalize="off"
          autocomplete="off"
          spellcheck="false"
          role="combobox"
          aria-expanded={composerNavItems.length > 0}
          aria-controls="composer-results"
          aria-activedescendant={composerHl >= 0 ? `cres-${composerHl}` : undefined}
          placeholder={composerLocked ? 'Resolving…' : (editingId != null ? 'Re-pick or rename this tune…' : 'Search or type a tune…')}
          bind:value={input}
          bind:this={inputEl}
          oninput={onInput}
          onpaste={onComposerPaste}
          onfocus={() => { composerFocused = true; selectedId = null; scheduleSeam() }}
          onblur={stopTyping}
          onkeydown={(e) => {
            // "/" as the very first character jumps to the search box (spec 028), matching the
            // global shortcut — you can still type "/" once there's text in the field.
            if (e.key === '/' && !input) { e.preventDefault(); focusSearchBox(); return }
            // ArrowRight from an EMPTY field hops to the "End set" button (when it's showing).
            if (e.key === 'ArrowRight' && !input) {
              const btn = mainEl?.querySelector('.dock .endset.hot')
              if (btn) { e.preventDefault(); btn.focus() }
              return
            }
            if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
              if (moveComposerHl(e.key === 'ArrowUp' ? 1 : -1)) { e.preventDefault(); return }
              // empty box + ArrowUp: leave the tune entry box and step back onto the cursor line
              if (e.key === 'ArrowUp' && !input.trim()) { e.preventDefault(); inputEl?.blur() }
            } else if (e.key === 'Enter') {
              e.preventDefault()
              if (composerHl >= 0 && composerNavItems[composerHl]) pickResult(composerNavItems[composerHl])
              else if (!input.trim() && nextSuggestion) pickResult(nextSuggestion)
              else commit()
            } else if (e.key === 'Escape' && resolving) { e.preventDefault(); cancelResolving(true) }
          }}
        />
        {#if searching}<span class="spinner input-spin"></span>{:else if input && !composerLocked}
          <!-- clear-× shares the spinner's slot (only one shows at a time) -->
          <button class="input-clear" type="button" title="Clear" aria-label="Clear entry" onmousedown={(e) => e.preventDefault()} onclick={clearEntry}>×</button>
        {/if}
      </div>
      <button onmousedown={(e) => e.preventDefault()} onclick={commit} disabled={editingId == null && !composerLocked && !input.trim()}>{editingId != null ? 'Save' : 'Log'}</button>
      {#if editingId != null}
        <button class="endset" title="Cancel editing" onclick={cancelEdit}>Cancel</button>
      {:else if input.trim() && !resolving}
        <!-- Mid-search, End set / Done are useless (End set is a post-pick action; Done
             leaves edit mode), so the slot becomes the deep-search escape instead of a
             row pinned to the dropdown's top edge that could clip off-screen. -->
        <button class="search-btn" title="Search deeper for this tune" onmousedown={(e) => e.preventDefault()} onclick={openDeep}>Search 🔍</button>
      {:else if activeSeam === 'end'}
        <!-- At the live end: open set -> close it (yellow "End set"); closed end with
             nothing selected -> the subtle grey "Done" leaves edit mode for read-only
             View (spec 021 §A3). Hidden while seam-editing or with a row selected. -->
        {#if endIsOpen}
          <button class="endset hot" title="End the current set" onclick={endSet}>End set</button>
        {:else if selectedId == null}
          <button class="done-btn" title="Done logging — switch to read-only view" onclick={() => setMode('view')}>Done</button>
        {/if}
      {/if}
    </div>
    {/if}
    {/if}
  </div>

  {#if recordingsOpen}
    <!-- This night's audio (spec 050): upload, and open the timestamping tool.
         Session and instance are fixed by the log this was opened from. -->
    <RecordingsModal
      sessionInstanceId={config.sessionInstanceId}
      onclose={() => { recordingsOpen = false; loadRecordingCount() }}
    />
  {/if}

  {#if assignOpen}
    <!-- bulk Assign (spec 029 §G): the set-tray starter picker as a modal -->
    <div class="drawer-scrim" role="button" tabindex="-1" aria-label="Close" onclick={() => (assignOpen = false)} onkeydown={(e) => activate(e, () => (assignOpen = false))}></div>
    <div class="assign-modal" role="dialog" aria-modal="true">
      <div class="assign-head">Sets started by…</div>
      <input class="starter-filter" placeholder="Filter players…" bind:value={assignFilter} />
      <div class="starter-list">
        <button class="starter-item clear" onclick={() => assignTo(null)}>— Clear —</button>
        {#each assignAttendees as p (p.person_id)}
          <button class="starter-item" onclick={() => assignTo(p)}>{p.display_name}</button>
        {:else}
          {#if attendeesLoaded}<p class="starter-empty">No one checked in yet.</p>{:else}<p class="starter-empty">Loading…</p>{/if}
        {/each}
        <button class="starter-item add-player" onclick={() => { assignOpen = false; openAttendance() }}>＋ Add a player</button>
      </div>
    </div>
  {/if}

  {#if listStatusOpen}
    <!-- bulk my-list status: reuses the assign-modal shell -->
    <div class="drawer-scrim" role="button" tabindex="-1" aria-label="Close" onclick={() => (listStatusOpen = false)} onkeydown={(e) => activate(e, () => (listStatusOpen = false))}></div>
    <div class="assign-modal mylist-modal" role="dialog" aria-modal="true">
      <div class="assign-head">Put on my list as…</div>
      <p class="mylist-scope">
        {selected.size} tune{selected.size === 1 ? '' : 's'}
        {listInstrument !== 'all' && myInstruments.length > 1 ? ` · for ${listInstrument}` : ' · all instruments'}
      </p>
      <div class="starter-list">
        <button class="starter-item ls-opt ls-want-to-learn" onclick={() => applyListStatus('want to learn')}>Want to learn</button>
        <button class="starter-item ls-opt ls-learning" onclick={() => applyListStatus('learning')}>Learning</button>
        <button class="starter-item ls-opt ls-learned" onclick={() => applyListStatus('learned')}>Learned</button>
      </div>
    </div>
  {/if}

  {#if drag?.started}
    <!-- floating drag ghost (spec 029 §F): name for one tune, a count card for a block -->
    <div class="drag-ghost" style="left:{drag.x}px; top:{drag.y}px">
      {#if drag.block.tuneIds.length === 1}{drag.name}{:else}{drag.block.tuneIds.length} tunes{drag.block.setCount > 1 ? ` · ${drag.block.setCount} sets` : ''}{/if}
    </div>
  {/if}

  <!--
    ONE picker, two entry points (spec 034). This replaced the bespoke .drawer AND the inline
    starter list. Sheet desktop="dock" gives full-screen under 768px / a right-docked pane
    above, which is exactly the presentation the spec asks for -- and it comes from the kit,
    so it behaves like every other sheet in the app.
  -->
  <PersonPicker
    bind:open={pickerOpen}
    scope="instance"
    mode={pickerMode}
    people={attendees}
    canonicalInstruments={canonicalInstruments}
    currentStarterName={pickerStarterName}
    onSelect={pickPerson}
    onCheckOut={checkOutPerson}
    onClear={clearStarter}
    onCreate={createPerson}
    onClose={closePicker}
  />

  <!-- The side pane is a search-and-add surface (its APIs are all login-gated), so it
       never mounts for a signed-out viewer. -->
  {#if wide && !readOnly}
    <SidePane
      bind:this={sidePaneEl}
      {config}
      suggestion={nextSuggestion}
      preferType={cursorSetType()}
      {displayStatus}
      history={searchHist}
      onRemember={(q) => rememberInHistory(searchHist, q)}
      onAdd={paneAdd}
      onAddSuggestion={(s) => logTune({ tune_id: s.tune_id, name: s.name, tune_type: s.tune_type }, s.name)}
      onDismissSuggestion={dismissNext}
    />
  {/if}

  <!-- Pane pick while in read-only View: confirm the implicit edit-mode switch (spec 028). -->
  {#if pendingViewAdd}
    <div class="reconcile-scrim" role="button" tabindex="-1" aria-label="Cancel" onclick={cancelViewAdd} onkeydown={(e) => activate(e, cancelViewAdd)}></div>
    <div class="reconcile viewadd" role="dialog" aria-modal="true">
      <div class="reconcile-head">Switch to editing?</div>
      <p class="reconcile-sub">You're viewing this log. Add <b>“{pendingViewAdd.name}”</b> and switch to edit mode?</p>
      <div class="reconcile-actions">
        <button class="va-cancel" onclick={cancelViewAdd}>Cancel</button>
        <button class="rc-ok" onclick={confirmViewAdd}>Add &amp; edit</button>
      </div>
    </div>
  {/if}

  {#if deepOpen}
    <div class="deep-modal" transition:fly={{ y: 24, duration: 200 }}>
      <TuneSearch
        variant="modal"
        initialQuery={input.trim()}
        initialPreview={deepPreview}
        preferType={cursorSetType()}
        {displayStatus}
        {config}
        history={searchHist}
        onRemember={(q) => rememberInHistory(searchHist, q)}
        onAdd={(p, n) => { closeDeep(); logTune(p, n) }}
        onClose={closeDeep}
      />
    </div>
  {/if}
</main>

<Dialog
  bind:open={markCompleteOpen}
  title="Mark this session log as completely logged?"
  description="This hides the editing controls."
  confirmLabel="Mark complete"
  onConfirm={doMarkComplete} />

<Dialog
  bind:open={markIncompleteOpen}
  title="Re-open this session log for editing?"
  confirmLabel="Re-open log"
  onConfirm={doMarkIncomplete} />

<!--
  Re-date this log (spec 046). The motivating case is a session logged past midnight,
  so "Previous day" is the first thing under your thumb; the picker is there for
  everything else. Save is explicit — a nudge or a picker change alone writes nothing.
-->
<Sheet
  bind:open={dateOpen}
  title="Date &amp; time"
  onCancel={() => { dateOpen = false }}>
  <div class="dt-body">
    <p class="dt-note">
      If you started logging after midnight, the log may be dated a day later than the
      session actually happened. Set it to the right night here.
    </p>
    <div class="dt-nudge">
      <button class="dt-step" onclick={() => nudgeDate(-1)}>‹ Previous day</button>
      <button class="dt-step" onclick={() => nudgeDate(1)}>Next day ›</button>
    </div>
    <label class="dt-field">
      <span class="dt-label">Date</span>
      <input
        class="dt-input"
        type="date"
        bind:value={dateDraft}
        oninput={() => { dateErr = ''; dateConfirm = false }} />
    </label>
    <!-- Start/end are NOT checked against each other: a session that starts at 11pm
         and ends at 2am is ordinary. Leaving End blank is a real answer — "it ran
         until it stopped" — which is why the hint says so instead of nagging. -->
    <div class="dt-times">
      <label class="dt-field">
        <span class="dt-label">Start</span>
        <input class="dt-input" type="time" bind:value={startDraft} oninput={() => { dateErr = '' }} />
      </label>
      <label class="dt-field">
        <span class="dt-label">End</span>
        <input class="dt-input" type="time" bind:value={endDraft} oninput={() => { dateErr = '' }} />
      </label>
    </div>
    <p class="dt-hint">Leave End blank if it ran on past when anyone was counting.</p>
    <p class="dt-preview" class:dt-changed={dateDirty}>
      {draftWhen}
      {#if !dateDirty}<span class="dt-same">(unchanged)</span>{/if}
    </p>
    {#if dateErr}
      <p class="dt-err">{dateErr}</p>
    {/if}
  </div>
  {#snippet footer()}
    <!-- Cancel lives in the Sheet's own header row; the footer carries only the commit. -->
    <div class="dt-actions">
      <button class="dt-save" disabled={dateSaving || !dateDraft || !dateDirty} onclick={saveDate}>
        {dateSaving ? 'Saving…' : dateConfirm ? 'Save anyway' : 'Save'}
      </button>
    </div>
  {/snippet}
</Sheet>

<!--
  Name this log (spec 047). Reuses the date sheet's shape and its .dt-* styles — same
  kind of decision, same chrome, one visual language for header edits. Empty clears the
  name, which is a real edit (back to the session's usual venue), so Save stays enabled
  when you blank a name that was set.
-->
<Sheet
  bind:open={nameOpen}
  title="Log name"
  onCancel={() => { nameOpen = false }}>
  <div class="dt-body">
    <!-- The help knows which kind of session this is (spec 004). At a festival naming is
         the norm and the reason is concrete — the day holds several sessions, so the date
         identifies none of them. Anywhere else it's the exception, and saying "a festival
         day with several sessions" to someone at a weekly pub session is noise about a
         case they'll never be in. The FIELDS are identical either way; only the words
         differ. -->
    <p class="dt-note">
      {#if isFestival}
        Several sessions share a day here, so the date on its own won't tell them apart.
        This name is what the log is called everywhere it's listed.
      {:else}
        Most nights don't need one — the date says which session it was. Name this log when
        the date isn't enough: a night somewhere other than the usual place, or a second
        session on the same day.
      {/if}
    </p>
    <label class="dt-field">
      <span class="dt-label">Name</span>
      <input
        class="dt-input"
        type="text"
        maxlength="255"
        placeholder={isFestival ? 'e.g. Advanced Session @ Jim Bowie' : "e.g. At Sarah's house"}
        bind:value={nameDraft}
        oninput={() => { nameErr = '' }}
        onkeydown={(e) => { if (e.key === 'Enter') saveName() }} />
    </label>
    <p class="dt-preview" class:dt-changed={nameDraft.trim() !== (instanceName || '')}>
      {nameDraft.trim() || (isFestival ? 'Unnamed — shown by date alone' : 'No name — shown by date alone')}
      {#if nameDraft.trim() === (instanceName || '')}<span class="dt-same">(unchanged)</span>{/if}
    </p>
    {#if nameErr}
      <p class="dt-err">{nameErr}</p>
    {/if}
  </div>
  {#snippet footer()}
    <div class="dt-actions">
      <!-- "Clear name" only when there is a name to clear. On an already-unnamed log
           an empty box is the status quo, not a deletion. -->
      <button class="dt-save" disabled={nameSaving || nameDraft.trim() === (instanceName || '')} onclick={saveName}>
        {nameSaving ? 'Saving…' : !nameDraft.trim() && instanceName ? 'Clear name' : 'Save name'}
      </button>
    </div>
  {/snippet}
</Sheet>
