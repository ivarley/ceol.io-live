<script>
  import { onMount, onDestroy, untrack } from 'svelte'
  import { fly } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { SvelteMap, SvelteSet } from 'svelte/reactivity'
  import { bootstrap, vocabulary, sendOp, sendTyping, liveMatch, livePeople, peopleSearch, deepSearch, fetchIncipit, openStream, tuneDetail } from './client.js'
  import TuneSearch from './TuneSearch.svelte'
  import SidePane from './SidePane.svelte'
  import { queuePut, queueAll, queueDelete, snapshotPut, snapshotGet, matchCachePut, matchCacheGet } from './offline.js'
  import { generateAppend, generateBetween } from './fracindex.js'
  import {
    computeOrdered, segmentByBreaks, setsOf, tunesOf, pluralType, setLabel,
    maxPos, cursorPos, remapAnchors, normName, normAbc, stripThe,
    openSetMergeTarget, mergeStable, parseThesessionId,
    computeCursorSlots, seamKeyFor, seamActionFor,
    rememberInHistory, historyStep,
  } from './logstate.js'
  import {
    dragBlock, dropTargets, optimisticMove,
    serializeClipboard, parseClipboard, rangeBetween, selectableIds,
  } from './selection.js'

  let { config } = $props()

  // Canonical records keyed by id (tunes + break rows), applied idempotently.
  // SvelteMap (not a plain Map) so .set/.delete are reactive in Svelte 5.
  const byId = new SvelteMap()
  // op_id -> {tempId, name, op_type, payload, status, ts}. status 'sending' = online
  // optimistic in-flight (§A2); 'queued' = offline, persisted to IndexedDB (§G).
  const pending = new SvelteMap()
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

  // "reconnecting" is short-lived: if the stream doesn't come back within a few
  // seconds, declare offline (covers reload-while-offline, where navigator.onLine
  // can read true and no `offline` event fires, and server-down with network up).
  let reconnectTimer = null
  function noteSse(s) {
    if (s === 'live') {
      reachable = true
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
    } else if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => { reconnectTimer = null; reachable = false }, 8000)
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
      connect()
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
    if (n > lastCount && atEnd && setsEl) {
      requestAnimationFrame(() => { if (setsEl) setsEl.scrollTop = setsEl.scrollHeight })
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
    if (!setsEl || searchMode || didInitialHide) return
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
    const seam = setsEl.querySelector('.seam.active')
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
  let sessionDate = $state('')
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
  let searchInputEl // the filter input element (focus/blur)
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
    const records = [...byId.values()]
      .filter((r) => !r._temp && typeof r.session_instance_tune_id === 'number')
      .map(({ _removing, _temp, pending, status, ...rest }) => rest)
    try {
      // JSON round-trip strips Svelte reactive proxies; IndexedDB can't
      // structured-clone a Proxy (DataCloneError), which would silently fail.
      const value = JSON.parse(JSON.stringify({
        records, last_event_id: highWater, person, ts: Date.now(),
        session_name: sessionName, session_date: sessionDate, notes: notesText,
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
    setTimeout(() => { const e = flashing.get(id); if (e && e.tok === tok) flashing.delete(id) }, kind === 'mine' ? 700 : 1400)
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

  // maxPos + cursorPos now live in logstate.js (pure, unit-tested). Call sites pass
  // the current insertion cursor, the ordered list, and all records (for append).
  function setCursor(id) {
    insertAfterId = id
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
    if (searchMode) return
    if (r._resolving) { if (!viewing) selectRow(r.session_instance_tune_id); return }
    if (r._temp || r._removing) return
    viewing ? openDrawer(r) : selectRow(r.session_instance_tune_id)
  }
  // Arm the between-sets seam: the next tune starts a NEW set in this gap, before
  // the set whose first tune is `nextFirstId` (spec 021 §C; prototype "new-set-after").
  function setNewSetCursor(nextFirstId) {
    insertAfterId = { newSet: nextFirstId }
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
    trySend({ op_id, op_type: 'set_break', payload: { action: 'insert', after_record_id: afterTuneId }, status: 'sending', ts: Date.now(), tempId })
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
    trySend({ op_id, op_type: 'set_break', payload: { action: 'remove', record_id: breakId }, status: 'sending', ts: Date.now(), restoreRecord: brk })
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
  function toggleTray(id) { openTrayId = openTrayId === id ? null : id; starterPickerSet = null }

  // "Started by" picker (§19): which set's picker is open, + cached attendee list.
  let starterPickerSet = $state(null) // first-tune id of the set being attributed
  let starterFilter = $state('')
  let attendees = $state([]) // [{person_id, display_name}] for this instance
  let attendeesLoaded = $state(false) // read reactively in the starter tray ("Loading…" vs "No one checked in")
  // the set's recorded starter name (first tune that carries one)
  function setStarterName(seg) {
    for (const t of seg.tunes) if (t.started_by_name) return t.started_by_name
    return null
  }
  const filteredAttendees = $derived.by(() => {
    const f = starterFilter.trim().toLowerCase()
    return f ? attendees.filter((p) => p.display_name.toLowerCase().includes(f)) : attendees
  })
  async function openStarterPicker(firstId) {
    starterPickerSet = starterPickerSet === firstId ? null : firstId
    starterFilter = ''
    if (starterPickerSet && !attendeesLoaded) {
      try { attendees = await livePeople(config); attendeesLoaded = true } catch { /* keep empty */ }
    }
  }
  // --- attendance editor (§F) ---
  let attendanceOpen = $state(false)
  let personQuery = $state('')
  let personResults = $state([])
  let personSearchTimer = null
  let showCreate = $state(false)
  let newFirst = $state('')
  let newLast = $state('')
  // Optional instrument picker for the create-person form (parity with the old logger).
  let showInstruments = $state(false)
  let newInstruments = $state([]) // selected instrument names (canonical + free-text "other")
  let newOther = $state('')
  const canonicalInstruments = $derived(config.canonicalInstruments || [])
  // The free-text picks, shown as removable chips (canonical picks live in their checkboxes).
  const otherPicks = $derived(newInstruments.filter(
    (i) => !canonicalInstruments.some((c) => c.toLowerCase() === i.toLowerCase())
  ))
  let pendingStarterFirstId = null // set we were attributing when the drawer was opened from the starter picker

  function toggleInstrument(name) {
    newInstruments = newInstruments.includes(name)
      ? newInstruments.filter((i) => i !== name)
      : [...newInstruments, name]
  }
  function addOtherInstrument() {
    const v = newOther.trim()
    if (v && !newInstruments.some((i) => i.toLowerCase() === v.toLowerCase())) {
      newInstruments = [...newInstruments, v]
    }
    newOther = ''
  }
  function removeInstrument(name) {
    newInstruments = newInstruments.filter((i) => i !== name)
  }
  function resetCreateForm() {
    newFirst = ''; newLast = ''; showCreate = false
    newInstruments = []; newOther = ''; showInstruments = false
  }

  async function refreshAttendees() {
    try { attendees = await livePeople(config); attendeesLoaded = true } catch { /* keep current */ }
  }
  function openAttendance() {
    starterPickerSet = null
    attendanceOpen = true
    personQuery = ''; personResults = []; resetCreateForm()
    if (!attendeesLoaded) refreshAttendees()
  }
  const closeAttendance = () => { attendanceOpen = false; pendingStarterFirstId = null }
  // "＋ Add a player" in the starter picker opens the attendance editor. Remember which
  // set's picker we came from (before openAttendance clears it) so the person we add
  // gets logged as that set's starter.
  function addPlayer() { pendingStarterFirstId = starterPickerSet; openAttendance() }
  // If the drawer was opened from a set's starter picker, log this person as that set's
  // starter and close everything. Returns true if it acted.
  function applyPendingStarter(person) {
    if (pendingStarterFirstId == null) return false
    const seg = displaySegments.find((s) => s.tunes[0].session_instance_tune_id === pendingStarterFirstId)
    if (seg) setStarter(seg, { person_id: person.person_id, display_name: person.display_name })
    closeAttendance() // also nulls pendingStarterFirstId
    return true
  }

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
  async function checkIn(p) {
    if (await attendanceOp('attendance_add', { person_id: p.person_id }, 'Check in')) {
      if (!applyPendingStarter(p)) searchPeople() // refresh "in" flags
    }
  }
  function checkOut(p) { attendanceOp('attendance_remove', { person_id: p.person_id }, 'Remove') }
  async function createPerson() {
    const first = newFirst.trim()
    if (!first) return
    // Include picked instruments plus any leftover typed-but-not-added "other" text.
    const instruments = [...newInstruments]
    if (newOther.trim()) instruments.push(newOther.trim())
    const res = await attendanceOp('attendance_create_person', { first_name: first, last_name: newLast.trim(), instruments }, 'Add person')
    if (res) {
      resetCreateForm(); personQuery = ''; personResults = []
      if (res.person) applyPendingStarter(res.person)
    }
  }
  function searchPeople() {
    const q = personQuery.trim()
    if (q.length < 2) { personResults = []; return }
    if (personSearchTimer) clearTimeout(personSearchTimer)
    personSearchTimer = setTimeout(async () => {
      try { personResults = await peopleSearch(config, q) } catch { personResults = [] }
    }, 180)
  }

  // --- session notes (header §F) ---
  function toggleExpand() {
    expanded = !expanded
    if (expanded) notesDraft = notesText // sync the editable buffer on open
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

  // Mark this session "completely logged" (§024): hides the editing affordances for
  // everyone (the SSE echo flips other clients via applyOp). Online-only metadata op,
  // like notes. Drops us to read-only view; the next reload takes the render-only path.
  async function markComplete() {
    error = ''
    if (!navigator.onLine) { notice = "You're offline — marking complete needs a connection."; return }
    if (!confirm('Mark this session log as completely logged? This hides the editing controls.')) return
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
  async function markIncomplete() {
    error = ''
    if (!navigator.onLine) { notice = "You're offline — this needs a connection."; return }
    if (!confirm('Re-open this session log for editing?')) return
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
        started_by_name: personOrNull?.display_name ?? null,
      })
    }
    const op_id = crypto.randomUUID()
    trySend({ op_id, op_type: 'attribute_set_starter', payload: { record_id: firstId, person_id: personOrNull?.person_id ?? null }, status: 'sending', ts: Date.now(), prevRecords })
    // Close the whole tray immediately; flash the new starter pill (top-right) as
    // confirmation (only when one was set, not on clear).
    starterPickerSet = null
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
    return f ? attendees.filter((p) => p.display_name.toLowerCase().includes(f)) : attendees
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

  function enterSelectMode() {
    // State hygiene (spec 029 §A): close transient edit UI; a half-open edit with no
    // composer is a trap. Selection always starts empty. The cursor seam carries over.
    selectedId = null
    openTrayId = null
    starterPickerSet = null
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
  async function pasteSets(sets) {
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
        await trySend({ op_id: bop, op_type: 'set_break', payload: { action: 'insert', after_record_id: prevTempId }, status: 'sending', ts: Date.now(), tempId: btmp })
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
        await trySend({ op_id, name: t.name, op_type: 'add_tune', payload, status: 'sending', ts: Date.now(), tempId })
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
      await trySend({ op_id: bop, op_type: 'set_break', payload: { action: 'insert', before_record_id: newSetTarget }, status: 'sending', ts: Date.now(), tempId: btmp })
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
    trySend({ op_id, op_type: 'remove_tunes', payload: { record_ids: ids }, status: 'sending', ts: Date.now(), bulkRemoveIds: ids })
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
      pending.delete(u.op_id)
      queueDelete(u.op_id)
      for (const id of u.ids) {
        const r = byId.get(id)
        if (r && r._removing) { const { _removing, ...rest } = r; byId.set(id, rest) }
      }
      return
    }
    // already sent/settled: optimistic re-add + the inverse op (streams to everyone)
    for (const r of u.records) if (r) byId.set(r.session_instance_tune_id, { ...r, deleted: false, _removing: undefined })
    trySend({ op_id: crypto.randomUUID(), op_type: 'restore_tunes', payload: { record_ids: u.ids }, status: 'sending', ts: Date.now(), restoredIds: u.ids })
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
      status: 'sending', ts: Date.now(), prevRecords, tempIds,
    })
    flashId(drag.block.tuneIds[0], 'mine')
    insertAfterId = drag.block.tuneIds[drag.block.tuneIds.length - 1] // cursor lands after the block
  }

  // Toggle View <-> Edit (spec 021 §A2–3). Leaving edit drops every transient editing
  // affordance; the SSE then reconnects so the server learns this connection's new
  // presence intent — a viewer asserts nothing (spec 024 §presence).
  function setMode(m) {
    if (mode === m) return
    mode = m
    if (m === 'view') {
      if (editingId != null) cancelEdit()
      else clearEntry()
      selectedId = null
      insertAfterId = null
      starterPickerSet = null
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
    setCursor(id) // cursor right after this tune; focuses composer
    selectedId = null
  }
  function insertBeforeRow(id) {
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === id)
    const pred = idx > 0 ? ordered[idx - 1] : null
    // mid-set: cursor after the previous tune. start-of-set (pred is a break) or
    // start-of-session (no pred): use the before-anchor so it lands at the set's front.
    if (pred && pred.record_type !== 'break') setCursor(pred.session_instance_tune_id)
    else setCursor({ before: id })
    selectedId = null
  }
  function confirmRow(id) {
    // Optimistic + offline-queued (like change/remove/set-starter): patch confidence,
    // reconcile by op_id, undo on reject. Works offline via trySend's queue (§G).
    const prev = byId.get(id)
    if (prev) byId.set(id, { ...prev, confidence: 100 })
    const op_id = crypto.randomUUID()
    flashId(id)
    trySend({ op_id, op_type: 'set_confidence', payload: { record_id: id, confidence: 100 }, status: 'sending', ts: Date.now(), prev })
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
    insertAfterId = null // editing isn't an insertion point
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
    trySend({ op_id, op_type: 'change_tune', payload: { record_id, ...payload }, status: 'sending', ts: Date.now(), prev })
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
      context: 'session_instance',
      tuneId: r.tune_id,
      apiEndpoint: `/api/sessions/${config.sessionPath}/${config.sessionInstanceId}/tunes/${r.tune_id}`,
      // the modal builds its save/heard/popularity endpoints from additionalData
      additionalData: {
        sessionPath: config.sessionPath,
        dateOrId: config.sessionInstanceId,
        isUserLoggedIn: true,
      },
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
      pending.delete(d.op_id)
      queueDelete(d.op_id) // ...and drop it from the persisted queue (already applied)
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
    pending.delete(entry.op_id)
    queueDelete(entry.op_id)
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
  async function trySend(entry) {
    entry.status = 'sending'
    pending.set(entry.op_id, entry)
    // Fast-path: if the browser knows it's offline, queue without a doomed fetch
    // (the first such fetch would otherwise hang on a dead keep-alive socket).
    if (!navigator.onLine) {
      await markQueued(entry)
      return
    }
    // Remap any temp anchor/target ids to their real server ids (an offline mid-set
    // insert / burst can reference a record that hadn't settled yet, #5b).
    const { payload, skip } = remapAnchors(entry.payload, tempToReal)
    if (skip) { // the target record never reached the server -> drop this orphaned op
      pending.delete(entry.op_id); await queueDelete(entry.op_id)
      if (entry.tempId) byId.delete(entry.tempId)
      return
    }
    try {
      const res = await sendOp(config, entry.op_type, payload, entry.op_id)
      settleOp(entry, res)
    } catch (e) {
      if (e.networkError) await markQueued(entry)
      else {
        undoOp(entry)
        pending.delete(entry.op_id)
        await queueDelete(entry.op_id)
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
      const queued = [...pending.values()].filter((e) => e.status === 'queued').sort((a, b) => a.ts - b.ts)
      for (const entry of queued) {
        await trySend(entry)
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
    trySend({ op_id: crypto.randomUUID(), name, op_type: 'add_tune', payload: { ...payload, after_record_id: null, before_record_id: null }, status: 'sending', ts: Date.now(), _localMerged: true })
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
    trySend({ op_id, name, op_type: 'add_tune', payload: { ...payload, after_record_id: afterId, before_record_id: beforeId }, status: 'sending', ts: Date.now(), tempId })
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
    trySend({ op_id, name: n.name, op_type: 'add_tune', payload: { ...n.payload, after_record_id: null, before_record_id: null, no_merge: true }, status: 'sending', ts: Date.now(), tempId })
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

    await trySend({ op_id, name, op_type: 'add_tune', payload: { ...payload, before_record_id: nextFirstId }, status: 'sending', ts: Date.now(), tempId })
    trySend({ op_id: bid, op_type: 'set_break', payload: { action: 'insert', before_record_id: nextFirstId }, status: 'sending', ts: Date.now() + 1, tempId: btmp })
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

  // Enter: add by typed text (server matches it to a tune, §C).
  function submit() {
    const name = input.trim()
    if (!name) return
    clearEntry()
    addOptimistic({ name }, name)
  }

  // Log a pasted thesession.org URL/id: the add op imports it server-side and resolves the
  // canonical name (spec 026). The optimistic row shows "#id" until the SSE echo settles it.
  function logThesessionInput() {
    const id = tsInputId
    if (id == null) return
    tsInputId = null
    clearEntry()
    addOptimistic({ thesession_id: id, name: `#${id}` }, `#${id}`)
    queueMicrotask(() => inputEl?.focus())
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
    // Enter on a pasted thesession.org URL/id: import + log (even if a title pre-fetch is still
    // pending — the intent is clear). Works offline too: the op just replays on reconnect.
    if (tsInputId != null) { logThesessionInput(); return }
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
    const addEntry = { op_id: crypto.randomUUID(), name, op_type: 'add_tune', payload: { ...payload, ...rs.addAnchors }, status: 'sending', ts: Date.now(), tempId: rs.tempId }
    if (rs.breakOp) {
      // new-set seam: send the break only AFTER the tune resolves, anchored before the same
      // next tune, so it always lands after our tune (mirrors addNewSetTune).
      await trySend(addEntry)
      trySend({ op_id: crypto.randomUUID(), op_type: rs.breakOp.op_type, payload: rs.breakOp.payload, status: 'sending', ts: Date.now() + 1, tempId: rs.breakTempId })
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

  const openDeep = () => { deepOpen = true } // TuneSearch seeds itself from the composer text
  const closeDeep = () => { deepOpen = false }

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
    trySend({ op_id, op_type: 'remove_tune', payload: { record_id }, status: 'sending', ts: Date.now() })
  }

  // Restore a not-yet-synced removal: cancel the queued op, clear the mark.
  function restore(record_id) {
    const r = byId.get(record_id)
    if (!r || !r._removing) return
    pending.delete(r._removing)
    queueDelete(r._removing)
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
    trySend({ op_id, op_type: 'set_break', payload: { action: 'insert', after_record_id: null }, status: 'sending', ts: Date.now(), tempId })
  }

  const queuedCount = $derived([...pending.values()].filter((e) => e.status === 'queued').length)

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
  const showConnDot = $derived(
    !renderOnly && (mode === 'edit' || (viewing && !logComplete && roster.some((p) => !p.away)))
  )
  async function connect() {
    const myGen = ++connSeq
    renderOnly = false
    if (reconnectPoll) { clearTimeout(reconnectPoll); reconnectPoll = null }
    // Snapshot pre-reconnect state for the §I36 "synced / added while away" summary.
    const prevIds = new Set([...byId.values()].filter((r) => typeof r.session_instance_tune_id === 'number').map((r) => r.session_instance_tune_id))
    const wasQueued = [...pending.values()].filter((e) => e.status === 'queued').length
    try {
      if (es) { es.close(); es = null }
      let snap
      let fromCache = false
      try {
        snap = await bootstrap(config) // server truth + fresh high-water
        reachable = true // we just reached the server
        if (snap.session_id) sessionId = snap.session_id
      } catch (e) {
        if (!e.networkError) throw e
        reachable = false // couldn't reach the server -> offline (not just "reconnecting")
        // Offline: fall back to the cached snapshot so the screen still renders (§G).
        const cached = await snapshotGet(config.sessionInstanceId).catch(() => null)
        snap = cached
          ? { records: cached.records, last_event_id: cached.last_event_id || 0, current_person: cached.person,
              session_name: cached.session_name, session_date: cached.session_date, notes: cached.notes,
              log_complete: cached.log_complete, user_timezone: cached.display_tz,
              known_tunes: cached.known_tunes || [], known_aliases: cached.known_aliases || [] }
          : { records: [], last_event_id: 0 }
        fromCache = true
      }
      if (myGen !== connSeq) return // a newer connect() superseded this one
      byId.clear()
      for (const r of snap.records || []) put(r)
      // Local fast-match vocabulary: rendering from the OFFLINE cache rebuilds the index
      // immediately from the cached copy; ONLINE it's fetched in the background after
      // render (loadVocabulary, below) so it never blocks bootstrap.
      if (fromCache) buildLocalIndex(snap.known_tunes, snap.known_aliases)
      if (snap.current_person) person = snap.current_person
      if (snap.session_name) sessionName = snap.session_name
      if (snap.session_date) sessionDate = snap.session_date
      displayTz = snap.user_timezone || snap.session_timezone || undefined
      notesText = snap.notes || ''
      logComplete = !!snap.log_complete
      highWater = snap.last_event_id || 0
      // Server truth is applied — the screen can render NOW. Flipping `loaded` here
      // (rather than when connect() fully resolves) matters only for an EMPTY log:
      // rows render as soon as byId fills, but the "No tunes yet" message is gated on
      // `loaded`, and the snapshot write + queue hydration below run on IndexedDB,
      // which can take seconds on a cold mobile browser — an empty session would sit
      // on the loading skeleton that whole time.
      loaded = true
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

      const stream = openStream(config, snap.last_event_id, {
        onOp: applyOp,
        onPresence: (r) => (roster = r),
        onTyping: (l) => (typers = l),
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
      if (everConnected) {
        const added = (snap.records || []).filter((r) => !prevIds.has(r.session_instance_tune_id)).length
        const parts = []
        if (wasQueued) parts.push(`${wasQueued} synced`)
        if (added) parts.push(`${added} added while away`)
        if (parts.length) showSync(parts.join(' · '))
      }
      everConnected = true
    } catch (e) {
      error = e.message
      sseStatus = 'error'
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
      if (!pending.has(e.op_id)) {
        pending.set(e.op_id, { op_id: e.op_id, op_type: e.op_type, payload: e.payload, name: e.name, status: 'queued', ts: e.ts })
      }
    }
    // Re-apply optimistic state for everything still queued, in offline (ts) order
    // so temp positions stack the same way they did originally.
    const queued = [...pending.values()].filter((e) => e.status === 'queued').sort((a, b) => a.ts - b.ts)
    for (const entry of queued) {
      if (entry.op_type === 'add_tune') {
        entry.tempId = `temp-${entry.op_id}`
        byId.set(entry.tempId, {
          session_instance_tune_id: entry.tempId, name: entry.name, tune_id: null, record_type: 'tune',
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
    const params = new URLSearchParams(window.location.search)
    const autoTuneId = params.get('tune')
    if (autoTuneId) {
      params.delete('tune')
      const qs = params.toString()
      window.history.replaceState({}, '', window.location.pathname + (qs ? '?' + qs : ''))
    }
    connect().then(() => { loaded = true; if (autoTuneId) autoLogTune(autoTuneId) }) // bootstraps records, then hydrateQueue() re-applies any queued ops
    // The shared app menu's 'Find a tune' calls this in the live context -> insert.
    window.__liveFindTune = () => openDeep()
    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('pageshow', onPageShow)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
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
      return
    }
    mainEl.style.height = vv.height + 'px'
    mainEl.style.transform = 'translateY(' + vv.offsetTop + 'px)'
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
    if (window.visualViewport) {
      window.visualViewport.removeEventListener('resize', onViewportChange)
      window.visualViewport.removeEventListener('scroll', onViewportChange)
    }
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (reconnectPoll) clearTimeout(reconnectPoll)
    if (es) es.close()
  })
</script>

<svelte:window bind:innerWidth={winW} onkeydown={onWinKey} />

<main bind:this={mainEl} class:view-mode={viewing} class:wide>
  <!-- Connection dot, floated top-right next to the shared hamburger (templates/live_logging.html)
       so it sits where the app-wide indicator sits on every other page. -->
  {#if showConnDot}
    <span class="conn-dot conn-fixed conn-{displayStatus}" title={displayStatus} aria-label="Connection: {displayStatus}"></span>
  {/if}
  <div class="topnav" bind:clientHeight={headerH}>
    <!-- Mirrors the app-wide header (base.html .header): full-viewport bar, 30px logo +
         site title (hidden on phones, like .logo-text). -->
    <div class="appbar">
      <a class="brand" href="/" aria-label="ceol.io home"><img src="/static/images/logo3-1.png" alt="ceol" /><span class="brand-text">Traditional Irish Session Logs</span></a>
      <!-- The hamburger menu is the SHARED app menu, rendered server-side in the live
           shell (templates/hamburger_menu.html) and floated top-right. 'Find a tune'
           routes to openDeep() here via window.__liveFindTune (set in onMount). -->
    </div>

    <header class="topbar">
      <div class="topbar-row" role="button" tabindex="0" onclick={toggleExpand} onkeydown={(e) => activate(e, toggleExpand)}>
        <div class="topbar-main">
          <div class="session-name">{sessionName || 'Session'}<a class="session-return" href="/sessions/{config.sessionPath}" title="Back to session" onclick={(e) => e.stopPropagation()}>⮐</a></div>
          <div class="session-date">{sessionDate}{#if !expanded && ordered.length}{sessionDate ? ' · ' : ''}{tuneSummary}{/if}</div>
          {#if notesText && !expanded && logComplete}
            <div class="session-notes">{notesText}</div>
          {/if}
        </div>
        <span class="topbar-presence">
          {#each roster as p (p.person_id)}
            <span class="avatar" class:away={p.away} style="background:{colorFor(p.arrival_seq)}" title="{p.name}{p.away ? ' (away)' : p.devices > 1 ? ` (${p.devices} devices)` : ''}">
              {initials(p.name)}{#if !p.away && p.devices > 1}<sup>{p.devices}</sup>{/if}
            </span>
          {/each}
        </span>
        <span class="header-chevron" class:up={expanded}>▾</span>
      </div>
      {#if expanded}
        <div class="header-expand">
          <div class="header-stat">{tuneSummary}</div>
          <div class="header-notes-edit">
            <span class="hn-label">Notes</span>
            <textarea
              class="hn-area"
              rows="2"
              placeholder="Add notes for this session…"
              bind:value={notesDraft}
              onclick={(e) => e.stopPropagation()}
            ></textarea>
            {#if notesDraft !== notesText}
              <div class="hn-actions">
                <button class="hn-save" onclick={(e) => { e.stopPropagation(); saveNotes() }}>Save</button>
                <button class="hn-cancel" onclick={(e) => { e.stopPropagation(); notesDraft = notesText }}>Cancel</button>
              </div>
            {/if}
          </div>
          <div class="header-stat header-attend">
            <span class="ha-text">
              <span class="ha-label">Attendance ({attendees.length}):</span>
              {attendees.length ? attendees.map((a) => a.display_name).join(', ') : 'no one checked in yet'}
            </span>
            <button class="ha-manage" onclick={(e) => { e.stopPropagation(); openAttendance() }}>Manage</button>
          </div>
          {#if roster.some((p) => !p.away)}
            <div class="header-stat">Currently logging: {roster.filter((p) => !p.away).map((p) => p.name).join(', ')}</div>
          {/if}
          {#if roster.some((p) => p.away)}
            <div class="header-stat header-away">Away: {roster.filter((p) => p.away).map((p) => p.name).join(', ')}</div>
          {/if}
          <div class="header-stat header-complete">
            {#if logComplete}
              <span class="hc-done">✓ This log is marked complete.</span>
              <button class="hc-link" onclick={(e) => { e.stopPropagation(); markIncomplete() }}>Mark as not complete</button>
            {:else}
              <button class="hc-mark" onclick={(e) => { e.stopPropagation(); markComplete() }}>Mark this log complete</button>
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
      <span class="searchbar-icon" aria-hidden="true">🔍</span>
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
    {/if}
    {#if drag?.started && dragKeys?.has('top-new')}
      <!-- drag-only drop zone: land as own set(s) at the very start (spec 029 §F) -->
      <div class="drop-extreme" data-seam="top-new" class:drop-active={drag.activeKey === 'top-new'}>new set</div>
    {/if}
    {#each displaySegments as seg, si (seg.tunes[0].session_instance_tune_id)}
      <div class="set">
        <button class="set-label" class:open={openTrayId === seg.tunes[0].session_instance_tune_id} onclick={(e) => { e.stopPropagation(); toggleTray(seg.tunes[0].session_instance_tune_id) }}>{setLabel(seg.tunes)}</button>
        {#if setStarterName(seg)}
          <button class="starter-pill" class:flash={starterFlashId === seg.tunes[0].session_instance_tune_id} title="Started by {setStarterName(seg)}" onclick={(e) => { e.stopPropagation(); openTrayId = seg.tunes[0].session_instance_tune_id; starterPickerSet = null }}>▸ {setStarterName(seg)}</button>
        {/if}
        {#if openTrayId === seg.tunes[0].session_instance_tune_id}
          <div class="set-tray">
            <div class="tray-row">
              <span class="tray-k">Started by</span>
              {#if viewing}
                <span class="starter-value" class:set={setStarterName(seg)}>{setStarterName(seg) || 'Not set'}</span>
              {:else}
                <button
                  class="starter-value"
                  class:set={setStarterName(seg)}
                  class:open={starterPickerSet === seg.tunes[0].session_instance_tune_id}
                  onclick={() => openStarterPicker(seg.tunes[0].session_instance_tune_id)}
                >{setStarterName(seg) || 'Not set'}</button>
              {/if}
            </div>
            {#if canEdit && starterPickerSet === seg.tunes[0].session_instance_tune_id}
              <div class="starter-picker">
                <input class="starter-filter" placeholder="Filter players…" bind:value={starterFilter} />
                <div class="starter-list">
                  {#if setStarterName(seg)}
                    <button class="starter-item clear" onclick={() => setStarter(seg, null)}>— Clear —</button>
                  {/if}
                  {#each filteredAttendees as p (p.person_id)}
                    <button class="starter-item" onclick={() => setStarter(seg, p)}>{p.display_name}</button>
                  {:else}
                    {#if attendeesLoaded}<p class="starter-empty">No one checked in yet.</p>{:else}<p class="starter-empty">Loading…</p>{/if}
                  {/each}
                  <button class="starter-item add-player" onclick={() => addPlayer()}>＋ Add a player</button>
                </div>
              </div>
            {/if}
            {#if loggedInfo(seg.tunes)}
              {@const li = loggedInfo(seg.tunes)}
              <div class="tray-row"><span class="tray-k">Logged by</span><span class="tray-v">{li.who || 'someone'}{li.when ? ` · ${li.when}` : ''}</span></div>
            {/if}
          </div>
        {/if}
        {#if canEdit}
          <div class="seam start-seam" role="button" tabindex="0" data-seam={`start:${seg.tunes[0].session_instance_tune_id}`} class:drop-eligible={dragKeys?.has(`start:${seg.tunes[0].session_instance_tune_id}`)} class:drop-active={drag?.started && drag.activeKey === `start:${seg.tunes[0].session_instance_tune_id}`} class:active={activeSeam === `start:${seg.tunes[0].session_instance_tune_id}`} onclick={() => setCursor({ before: seg.tunes[0].session_instance_tune_id })} onkeydown={(e) => activate(e, () => setCursor({ before: seg.tunes[0].session_instance_tune_id }))}>
            {#if activeSeam === `start:${seg.tunes[0].session_instance_tune_id}`}
              <span class="seam-line"></span>
            {:else}<span class="seam-plus">＋ start of set</span>{/if}
          </div>
        {/if}
        {#each seg.tunes as r, ti (r.session_instance_tune_id)}
          <div
            class="tune-row"
            role="button"
            tabindex="0"
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
            style={canEdit ? rowStyle(r) : ''}
            onclick={(e) => rowClick(r, e)}
            onkeydown={(e) => activate(e, () => rowClick(r))}
          >
            <span class="name">{#if searchMode && searchText.trim() && tuneNameMatches(r, searchText.trim().toLowerCase())}{@const p = suggestionParts(r.name, searchText.trim())}{p.pre}<span class="search-hit">{p.mid}</span>{p.post}{:else}{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}{/if}</span>
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
              {#if canEdit && !selectMode}<button class="info-btn" title="Tune details" onclick={(e) => { e.stopPropagation(); openDrawer(r) }}>ⓘ</button>{/if}
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
            {:else}
            <div class="row-actions">
              <button onclick={() => openDrawer(r)}>ⓘ Info</button>
              <button onclick={() => insertBeforeRow(r.session_instance_tune_id)}>↑ Before</button>
              <button onclick={() => insertAfterRow(r.session_instance_tune_id)}>↓ After</button>
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
              <div class="seam end-seam" role="button" tabindex="0" data-seam="end" class:drop-eligible={dragKeys?.has('end')} class:drop-active={drag?.started && drag.activeKey === 'end'} class:active={activeSeam === 'end'} onclick={() => setCursor(null)} onkeydown={(e) => activate(e, () => setCursor(null))}>
                {#if activeSeam === 'end'}<span class="seam-line"></span>{:else}<span class="seam-plus">＋</span>{/if}
              </div>
              {#if drag?.started && dragKeys?.has('end-new')}
                <!-- drag-only drop zone: land as own set(s) below the open end (spec 029 §F) -->
                <div class="drop-extreme" data-seam="end-new" class:drop-active={drag.activeKey === 'end-new'}>new set</div>
              {/if}
            {:else}
              <div class="seam" role="button" tabindex="0" data-seam={`after:${r.session_instance_tune_id}`} class:drop-eligible={dragKeys?.has(`after:${r.session_instance_tune_id}`)} class:drop-active={drag?.started && drag.activeKey === `after:${r.session_instance_tune_id}`} class:active={activeSeam === `after:${r.session_instance_tune_id}`} onclick={() => setCursor(r.session_instance_tune_id)} onkeydown={(e) => activate(e, () => setCursor(r.session_instance_tune_id))}>
                {#if activeSeam === `after:${r.session_instance_tune_id}`}
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
        <div class="seam inter-seam" role="button" tabindex="0" data-seam={`inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`} class:drop-eligible={dragKeys?.has(`inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`)} class:drop-active={drag?.started && drag.activeKey === `inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`} class:active={activeSeam === `inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`} onclick={() => setNewSetCursor(displaySegments[si + 1].tunes[0].session_instance_tune_id)} onkeydown={(e) => activate(e, () => setNewSetCursor(displaySegments[si + 1].tunes[0].session_instance_tune_id))}>
          {#if activeSeam === `inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`}
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
      <div class="seam end-seam new-set-end" role="button" tabindex="0" data-seam="end" class:drop-eligible={dragKeys?.has('end')} class:drop-active={drag?.started && drag.activeKey === 'end'} class:active={activeSeam === 'end'} onclick={() => setCursor(null)} onkeydown={(e) => activate(e, () => setCursor(null))}>
        {#if activeSeam === 'end'}
          <span class="seam-line"></span><span class="seam-hint">new set</span>
        {:else}<span class="seam-plus">＋ new set</span>{/if}
      </div>
    {/if}
    <!-- scroll room so the end-of-list seam can rise ABOVE the upward dropdown (§D) -->
    {#if dropdownOpen}<div class="drop-spacer" style="height:{resultsH}px" aria-hidden="true"></div>{/if}
    </div>
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  {#if canEdit && othersTyping.length}
    <div class="typing">
      {#each othersTyping as t (t.person_id)}<span class="t-name" style="color:{colorFor(t.arrival_seq)}">{t.name}</span>{/each}
      <span class="t-verb">{othersTyping.length === 1 ? 'is' : 'are'} typing…</span>
    </div>
  {/if}

  <div class="dock">
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
          <button class="sel-act" disabled={!selected.size} onclick={openAssign}>Assign</button>
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
        {#if logComplete}
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
          <li class="result-ts" role="option" aria-selected="false" onmousedown={(e) => e.preventDefault()} onclick={logThesessionInput}>
            <span class="r-name">＋ Add tune #{tsInputId} from thesession.org</span>
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
        {:else if editingId == null && (results.length || noMatch)}
          <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->
          <li class="result-deeper" role="option" aria-selected="false" onmousedown={(e) => e.preventDefault()} onclick={openDeep}>
            <span class="r-name">🔍 Search …</span>
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
          onfocus={() => { composerFocused = true; scheduleSeam() }}
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
        {#if searching}<span class="spinner input-spin"></span>{/if}
      </div>
      <button onmousedown={(e) => e.preventDefault()} onclick={commit} disabled={editingId == null && !composerLocked && !input.trim()}>{editingId != null ? 'Save' : 'Log'}</button>
      {#if editingId != null}
        <button class="endset" title="Cancel editing" onclick={cancelEdit}>Cancel</button>
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

  {#if drag?.started}
    <!-- floating drag ghost (spec 029 §F): name for one tune, a count card for a block -->
    <div class="drag-ghost" style="left:{drag.x}px; top:{drag.y}px">
      {#if drag.block.tuneIds.length === 1}{drag.name}{:else}{drag.block.tuneIds.length} tunes{drag.block.setCount > 1 ? ` · ${drag.block.setCount} sets` : ''}{/if}
    </div>
  {/if}

  {#if attendanceOpen}
    <div class="drawer-scrim" role="button" tabindex="-1" aria-label="Close" onclick={closeAttendance} onkeydown={(e) => activate(e, closeAttendance)}></div>
    <aside class="drawer">
      <div class="drawer-head">
        <div class="drawer-title">Attendance</div>
        <button class="drawer-done" onclick={closeAttendance}>Done</button>
      </div>
      <div class="drawer-body">
        <div class="d-label">Checked in ({attendees.length})</div>
        <ul class="att-list">
          {#each attendees as a (a.person_id)}
            <li><span class="att-name">{a.display_name}</span><button class="att-x" title="Check out" onclick={() => checkOut(a)}>✕</button></li>
          {:else}
            <li class="att-empty">No one checked in yet.</li>
          {/each}
        </ul>

        <div class="d-label">Add someone</div>
        <input class="att-search" placeholder="Search people…" bind:value={personQuery} oninput={searchPeople} />
        {#if personResults.length}
          <ul class="att-results">
            {#each personResults as r (r.person_id)}
              <li>
                <button class="att-result" class:attending={r.attending} disabled={r.attending} onclick={() => checkIn(r)} title={r.attending ? 'Already checked in' : 'Tap to check in'}>
                  <span class="att-name">{r.display_name}</span>
                  {#if r.attending}<span class="att-in">✓ in</span>{/if}
                </button>
              </li>
            {/each}
          </ul>
        {:else if personQuery.trim().length >= 2}
          <p class="att-empty">No matches — create them below.</p>
        {/if}

        <button class="att-create-toggle" onclick={() => (showCreate ? resetCreateForm() : (showCreate = true))}>{showCreate ? '× Cancel' : '＋ Create new person'}</button>
        {#if showCreate}
          <div class="att-create">
            <input placeholder="First name" bind:value={newFirst} />
            <input placeholder="Last name" bind:value={newLast} />
            <button class="att-add" disabled={!newFirst.trim()} onclick={createPerson}>Add</button>
          </div>
          <button class="att-inst-toggle" onclick={() => (showInstruments = !showInstruments)}>
            {showInstruments ? '× Instruments' : '＋ Add instruments (optional)'}
          </button>
          {#if showInstruments}
            <div class="att-inst">
              <div class="att-inst-grid">
                {#each canonicalInstruments as inst}
                  <label class="att-inst-item">
                    <input type="checkbox" checked={newInstruments.includes(inst)} onchange={() => toggleInstrument(inst)} />
                    <span>{inst}</span>
                  </label>
                {/each}
              </div>
              <div class="att-inst-other">
                <input placeholder="Other instrument…" bind:value={newOther}
                  onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addOtherInstrument() } }} />
                <button class="att-add" disabled={!newOther.trim()} onclick={addOtherInstrument}>Add</button>
              </div>
              {#if otherPicks.length}
                <div class="att-inst-chips">
                  {#each otherPicks as o}
                    <span class="att-chip">{o}<button aria-label={'Remove ' + o} onclick={() => removeInstrument(o)}>×</button></span>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        {/if}
      </div>
    </aside>
  {/if}

  {#if wide}
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
