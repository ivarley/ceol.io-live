<script>
  import { onMount, onDestroy } from 'svelte'
  import { fly } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { SvelteMap, SvelteSet } from 'svelte/reactivity'
  import { bootstrap, vocabulary, sendOp, sendTyping, liveMatch, livePeople, peopleSearch, deepSearch, fetchIncipit, openStream, tuneDetail } from './client.js'
  import Incipit from './Incipit.svelte'
  import { queuePut, queueAll, queueDelete, snapshotPut, snapshotGet, matchCachePut, matchCacheGet } from './offline.js'
  import { generateAppend, generateBetween } from './fracindex.js'

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
  let input = $state('')
  let error = $state('')
  let notice = $state('')
  let person = $state(config.currentPerson || {})
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
  let inputEl // the composer input element (for stay-hot refocus)
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
  let ambiguous = $state(false) // Enter hit a fragment matching several tunes, no unique exact (local "red" state)
  let lastMatchExact = false // whether `results` (for resultsQuery) was a unique exact match (gate decision)
  let searchTimer = null
  let searchSeq = 0
  let searching = $state(false) // a server search is in flight for the typed text (input spinner)
  let composerFocused = $state(false) // input has focus — gates the "likely next tune" suggestion row
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
  const initials = (name) => (name || '?').trim().slice(0, 2).toUpperCase()

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

  // Ordered, non-deleted records (tunes + breaks), then segment into sets on breaks.
  const ordered = $derived(
    [...byId.values()]
      .filter((r) => !r.deleted)
      .sort((a, b) => (a.order_position < b.order_position ? -1 : a.order_position > b.order_position ? 1 : 0))
  )
  // Segment into sets, remembering the break record that *ends* each set (its
  // boundary with the next). The between-sets ("inter") seam renders in that gap
  // and carries Join, which removes exactly that break (spec 021 §C; prototype).
  const segments = $derived.by(() => {
    const out = []
    let cur = []
    for (const r of ordered) {
      if (r.record_type === 'break') {
        if (cur.length) { out.push({ tunes: cur, breakAfter: r.session_instance_tune_id }); cur = [] }
        // a leading/empty-set break carries no set to attach to — ignore it
      } else {
        cur.push(r)
      }
    }
    if (cur.length) out.push({ tunes: cur, breakAfter: null })
    return out
  })
  const sets = $derived(segments.map((s) => s.tunes))
  const tunes = $derived(ordered.filter((r) => r.record_type !== 'break'))
  // "61 tunes in 26 sets" — shown in the header-expand and (collapsed) on the date line.
  const tuneSummary = $derived(`${tunes.length} tune${tunes.length === 1 ? '' : 's'} in ${sets.length} set${sets.length === 1 ? '' : 's'}`)

  // Pluralize a tune type for display ("Reel"→"Reels", "Waltz"→"Waltzes", "March"→"Marches").
  function pluralType(ty) {
    if (!ty) return ty
    if (/(s|z|ch|sh|x)$/i.test(ty)) return ty + 'es'
    return ty + 's'
  }

  // Per-set type label (prototype setLabel): the shared tune type pluralized
  // ("Reels"), "Mixed" if the set spans types, "Unknown" when no tune is matched.
  // Every set gets a pill.
  function setLabel(setTunes) {
    const types = new Set(setTunes.map((t) => t.tune_type).filter(Boolean))
    if (types.size === 0) return 'Unknown'
    if (types.size > 1) return 'Mixed'
    return pluralType([...types][0])
  }

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

  function maxPos() {
    let m = ''
    for (const r of byId.values()) if (r.order_position && r.order_position > m) m = r.order_position
    return m
  }
  // The server anchors + optimistic order_position for the current cursor.
  function cursorPos() {
    const append = () => ({ afterId: null, beforeId: null, position: generateAppend(maxPos()) })
    const c = insertAfterId
    if (c == null) return append()
    if (typeof c === 'object' && c.before != null) {
      const idx = ordered.findIndex((r) => r.session_instance_tune_id === c.before)
      if (idx === -1) return append()
      const x = ordered[idx].order_position
      const prev = idx > 0 ? ordered[idx - 1].order_position : null
      return { afterId: null, beforeId: c.before, position: generateBetween(prev, x) }
    }
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === c)
    if (idx === -1) return append()
    const before = ordered[idx].order_position
    const after = idx + 1 < ordered.length ? ordered[idx + 1].order_position : null
    return { afterId: c, beforeId: null, position: generateBetween(before, after) }
  }
  function setCursor(id) {
    insertAfterId = id
    queueMicrotask(() => inputEl?.focus())
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
    const before = idx >= 0 ? ordered[idx].order_position : maxPos()
    const after = idx >= 0 && idx + 1 < ordered.length ? ordered[idx + 1].order_position : null
    byId.set(tempId, {
      session_instance_tune_id: tempId, record_type: 'break',
      order_position: generateBetween(before, after), deleted: false, _temp: true,
    })
    trySend({ op_id, op_type: 'set_break', payload: { action: 'insert', after_record_id: afterTuneId }, status: 'sending', ts: Date.now(), tempId })
    setCursor(null) // split leaves edit mode (§C10)
  }

  // Join: remove the boundary break (between-sets seam) -> merge the two sets (§C).
  function joinAt(breakId) {
    const brk = byId.get(breakId)
    byId.delete(breakId) // optimistic merge
    const op_id = crypto.randomUUID()
    trySend({ op_id, op_type: 'set_break', payload: { action: 'remove', record_id: breakId }, status: 'sending', ts: Date.now(), restoreRecord: brk })
    setCursor(null)
  }

  // --- row selection + actions (spec 021 §E) ---
  // Read-only View (default) vs full Edit (logging), toggled on this same screen
  // (spec 021 §A2–3). View is the common case — most people read a logged session
  // rather than log one — so a logger taps "✎ Edit log" to start.
  let mode = $state('view')
  const viewing = $derived(mode === 'view')

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
  let attendeesLoaded = false
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
  let pendingStarterFirstId = null // set we were attributing when the drawer was opened from the starter picker

  async function refreshAttendees() {
    try { attendees = await livePeople(config); attendeesLoaded = true } catch { /* keep current */ }
  }
  function openAttendance() {
    starterPickerSet = null
    attendanceOpen = true
    personQuery = ''; personResults = []; showCreate = false; newFirst = ''; newLast = ''
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
    const res = await attendanceOp('attendance_create_person', { first_name: first, last_name: newLast.trim() }, 'Add person')
    if (res) {
      newFirst = ''; newLast = ''; showCreate = false; personQuery = ''; personResults = []
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
    if (!fromCacheOnly()) connect() // re-open the stream with the new mode= flag
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
  // sortable position, so they segment into sets uniformly. Display = the sets.
  const displaySegments = $derived(segments)
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
  const dropdownOpen = $derived(!viewing && (showNext || results.length > 0 || (noMatch && editingId == null)))

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
    if (entry.restoreRecord) byId.set(entry.restoreRecord.session_instance_tune_id, entry.restoreRecord) // un-join
    if ((entry.op_type === 'change_tune' || entry.op_type === 'set_confidence') && entry.prev) byId.set(entry.prev.session_instance_tune_id, entry.prev) // revert edit / confirm
    if (entry.prevRecords) for (const r of entry.prevRecords) byId.set(r.session_instance_tune_id, r) // revert set-starter
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
    if (entry.tempId && res.record) tempToReal.set(entry.tempId, res.record.session_instance_tune_id) // for anchor remap (#5b)
    if (res.records) for (const r of res.records) put(r) // multi-record ops (set-starter)
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
  function remapAnchors(entry) {
    const p = { ...entry.payload }
    const isTemp = (v) => typeof v === 'string' && v.startsWith('temp-')
    const fixAnchor = (v) => (isTemp(v) ? (tempToReal.get(v) ?? null) : v)
    if ('after_record_id' in p) p.after_record_id = fixAnchor(p.after_record_id)
    if ('before_record_id' in p) p.before_record_id = fixAnchor(p.before_record_id)
    if (isTemp(p.record_id)) {
      const real = tempToReal.get(p.record_id)
      if (real == null) return { payload: p, skip: true } // target never reached the server
      p.record_id = real
    }
    return { payload: p, skip: false }
  }

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
    const { payload, skip } = remapAnchors(entry)
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
  function openSetMergeTarget(payload) {
    let start = 0
    for (let i = ordered.length - 1; i >= 0; i--) {
      if (ordered[i].record_type === 'break') { start = i + 1; break }
    }
    const wantId = payload.tune_id ?? null
    const wantName = wantId == null ? normName(payload.name || '') : null
    for (let i = start; i < ordered.length; i++) {
      const r = ordered[i]
      if (r.record_type !== 'tune' || r.deleted || r._temp) continue
      if (wantId != null) { if (r.tune_id === wantId) return r }
      else if (wantName && !r.tune_id && normName(r.name || '') === wantName) return r
    }
    return null
  }

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
    const { afterId, beforeId, position } = cursorPos()
    // Pure append of a duplicate -> corroborate the existing row, never a second copy.
    if (afterId == null && beforeId == null) {
      const target = openSetMergeTarget(payload)
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
      record_type: 'tune', order_position: generateAppend(maxPos()), deleted: false, _temp: true, _status: 'sending',
    })
    trySend({ op_id, name: n.name, op_type: 'add_tune', payload: { ...n.payload, after_record_id: null, before_record_id: null, no_merge: true }, status: 'sending', ts: Date.now(), tempId })
  }
  const dismissMerge = () => { mergeNudge = null }

  // --- reconnect reconciliation review (§G) ---
  const RECONCILE_VERB = {
    add_tune: 'Add', change_tune: 'Edit', remove_tune: 'Remove', set_break: 'Set break',
    set_confidence: 'Confirm', attribute_set_starter: 'Set starter', edit_notes: 'Edit notes',
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
      const cp = cursorPos()
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
      const target = openSetMergeTarget(payload)
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
  const DEEP_TYPES = ['Reel', 'Jig', 'Slip Jig', 'Hornpipe', 'Polka', 'Slide', 'Waltz', 'Barndance', 'Mazurka', 'March', 'Strathspey', 'Three-Two']
  let deepOpen = $state(false)
  let deepQuery = $state('')
  let deepType = $state(null) // hard tune-type filter (the popout)
  let deepMode = $state('mixed') // 'mixed' (name + ABC) | 'name' | 'abc' search mode
  let deepFilterOpen = $state(false) // type-filter popout visible
  let deepResults = $state([])
  let deepLoading = $state(false)
  let deepTimer = null
  let deepSeq = 0
  let deepPrefer = null // the set's type, passed as a sort preference (not a filter)

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

  function openDeep() {
    deepQuery = input.trim()
    deepType = null // no hard filter; the set's type is a soft preference instead
    deepMode = 'mixed' // blended by default; the tabs narrow to name-only / ABC-only
    deepFilterOpen = false
    deepPrefer = cursorSetType()
    deepOpen = true
    runDeep()
  }
  const closeDeep = () => { deepOpen = false }
  // Typing in the field: blended results (mixed) unless the user narrowed with a tab.
  function onDeepInput() {
    runDeep()
  }
  // Tabs act as filters: click to narrow to that mode; click the active tab to clear
  // back to the blended (mixed) list.
  function setDeepMode(m) {
    const next = deepMode === m ? 'mixed' : m
    if (deepMode !== next) { deepMode = next; runDeep() }
  }
  const toggleDeepFilters = () => { deepFilterOpen = !deepFilterOpen }
  function setDeepType(t) {
    deepType = deepType === t ? null : t
    deepFilterOpen = false
    runDeep()
  }
  function runDeep() {
    if (deepTimer) clearTimeout(deepTimer)
    deepLoading = true
    deepTimer = setTimeout(async () => {
      const seq = ++deepSeq
      const r = await deepSearch(config, deepQuery.trim(), deepType, deepPrefer, deepMode)
      if (seq === deepSeq) { deepResults = r; deepLoading = false }
    }, 160)
  }
  // Tap a deep result → log that catalog tune at the cursor, then close.
  function pickDeep(r) {
    closeDeep()
    clearEntry()
    addOptimistic({ tune_id: r.tune_id, name: r.name, tune_type: r.tune_type }, r.name)
    queueMicrotask(() => inputEl?.focus())
  }
  // Log the typed text as an unlinked tune (the "as-is" escape lives here).
  function deepLogAsIs() {
    const name = deepQuery.trim()
    if (!name) return
    closeDeep()
    clearEntry()
    addOptimistic({ name }, name)
    queueMicrotask(() => inputEl?.focus())
  }
  // Keyboard: Esc closes; Enter logs the top result (or as-is if none, like type-ahead).
  function deepKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeDeep() }
    else if (e.key === 'Enter') {
      e.preventDefault()
      if (deepResults.length) pickDeep(deepResults[0])
      else if (deepQuery.trim()) deepLogAsIs()
    }
  }

  // The shared matcher (same as the legacy pill editor: find_matching_tune + wildcard),
  // --- local exact-match fast path (§024) -----------------------------------
  // The session's repertoire (known_tunes/known_aliases from bootstrap) is indexed
  // locally so a typed name matching a known tune EXACTLY logs with no network in the
  // hot path. Normalization mirrors the server matcher (find_matching_tune): apostrophe
  // fold, unaccent, lower; "The" prefix flexibility on the tune-name tier only.
  let localIndex = null
  let vocabKnown = [], vocabAliases = [] // raw bootstrap vocabulary, kept for offline persistence
  const stripThe = (s) => s.replace(/^the\s+/, '')
  // Mirror the server matcher (database.normalize_quotes + unaccent + lower). Smart-quote
  // code points are \u-escaped, never written literally — editors silently auto-correct
  // literal smart quotes back to ASCII, which would turn the fold into a no-op.
  function normName(s) {
    return (s || '')
      .replace(/[\u2018\u2019\u201b\u02bc\u2032\u0060\u00b4]/g, "'") // smart singles -> '
      .replace(/[\u201c\u201d\u201e\u2033\u00ab\u00bb]/g, '"')        // smart doubles -> "
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')              // unaccent (strip diacritics)
      .trim().toLowerCase()
  }
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
      if (!e) { e = { tune_id: id, name, tune_type: tune_type ?? null, nn: normName(name), aliases: [] }; listById.set(id, e); list.push(e) }
      return e
    }
    for (const t of known || []) {
      if (!t.tune_id) continue
      byId.set(t.tune_id, { tune_id: t.tune_id, name: t.name, tune_type: t.tune_type ?? null })
      const n = normName(t.name)
      add(nameMap, n, t.tune_id)
      add(nameMap, stripThe(n), t.tune_id) // "The X" <-> "X" flexibility (both directions)
      const e = ensure(t.tune_id, t.name, t.tune_type)
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
  // preference, then vocabulary order (session plays -> global popularity), then name.
  function resolveLocalMany(q, limit = 8) {
    if (!localIndex) return []
    const qn = normName(q)
    if (qn.length < 2) return []
    const prefer = cursorSetType() // the set's tune type (soft sort preference), or null
    const inSet = currentSetTuneIds() // already in this set -> demote below fresh suggestions
    const hits = []
    for (const e of localIndex.list) {
      if (e.nn.includes(qn) || e.aliases.some((a) => a.includes(qn))) hits.push(e)
    }
    hits.sort((a, b) => {
      const ia = inSet.has(a.tune_id) ? 1 : 0
      const ib = inSet.has(b.tune_id) ? 1 : 0
      if (ia !== ib) return ia - ib // a tune already in this set sinks beneath everything else
      const pa = prefer && a.tune_type === prefer ? 0 : 1
      const pb = prefer && b.tune_type === prefer ? 0 : 1
      if (pa !== pb) return pa - pb
      if (a.idx !== b.idx) return a.idx - b.idx
      return a.nn < b.nn ? -1 : a.nn > b.nn ? 1 : 0
    })
    return hits.slice(0, limit).map((e) => ({ tune_id: e.tune_id, name: e.name, tune_type: e.tune_type }))
  }

  // Stable-append merge (§D): keep every already-shown LOCAL result pinned in place (so
  // nothing the user is about to tap moves), enrich it with the server's richer fields
  // (in-session badge / notation), and append only the server-ONLY tunes below.
  function mergeStable(localList, serverList) {
    const sById = new Map(serverList.filter((r) => r.tune_id != null).map((r) => [r.tune_id, r]))
    const seen = new Set(localList.map((r) => r.tune_id))
    const merged = localList.map((r) => {
      const s = sById.get(r.tune_id)
      return s ? { ...r, in_session_tune: s.in_session_tune, abc: s.abc ?? r.abc } : r
    })
    const extra = serverList.filter((r) => r.tune_id != null && !seen.has(r.tune_id))
    return [...merged, ...extra].slice(0, 8)
  }

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
  }

  const othersTyping = $derived(typers.filter((t) => t.person_id !== person.person_id))

  let connSeq = 0 // guards against overlapping connect() calls leaking a stream
  let renderOnly = $state(false) // completed-log fast-path: rendered, no stream (hide status pill)
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

<main bind:this={mainEl} class:view-mode={viewing}>
  <div class="topnav" bind:clientHeight={headerH}>
    <div class="appbar">
      <a class="brand" href="/" aria-label="ceol.io home"><img src="/static/images/logo3-1.png" alt="ceol" /></a>
      <!-- The hamburger menu is the SHARED app menu, rendered server-side in the live
           shell (templates/hamburger_menu.html) and floated top-right. 'Find a tune'
           routes to openDeep() here via window.__liveFindTune (set in onMount). -->
    </div>

    <header class="topbar">
      <div class="topbar-row" onclick={toggleExpand}>
        <div class="topbar-main">
          <div class="session-name">{sessionName || 'Session'}</div>
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
        {#if !renderOnly}
          <span class="status status-{displayStatus}" title="connection">{displayStatus}</span>
        {/if}
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
    <div class="reconcile-scrim" onclick={dismissReconcile}></div>
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
    {#if notice}<p class="notice" onclick={() => (notice = '')}>{notice}</p>{/if}
    {#if queuedCount > 0}
      <p class="offline-banner">
        ⏳ {queuedCount} change{queuedCount === 1 ? '' : 's'} queued{displayStatus === 'offline' ? ' — offline' : ', syncing…'}
      </p>
    {/if}
  </div>

  <div class="sets" bind:this={setsEl} onscroll={onScroll}>
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
            {#if !viewing && starterPickerSet === seg.tunes[0].session_instance_tune_id}
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
        {#if !viewing}
          <div class="seam start-seam" class:active={activeSeam === `start:${seg.tunes[0].session_instance_tune_id}`} onclick={() => setCursor({ before: seg.tunes[0].session_instance_tune_id })}>
            {#if activeSeam === `start:${seg.tunes[0].session_instance_tune_id}`}
              <span class="seam-line"></span>
            {:else}<span class="seam-plus">＋ start of set</span>{/if}
          </div>
        {/if}
        {#each seg.tunes as r, ti (r.session_instance_tune_id)}
          <div
            class="tune-row"
            class:low={!r._temp && r.confidence != null && r.confidence <= 70}
            class:unlinked={!r._resolving && !r.tune_id && r.record_type === 'tune'}
            class:has-by={!viewing && !r._temp && r.tune_id && loggerColorIdx(r) != null}
            class:pending={r._resolving}
            class:queued={r._temp && r._status === 'queued'}
            class:removing={r._removing}
            class:selected={!viewing && selectedId === r.session_instance_tune_id}
            class:editing={editingId === r.session_instance_tune_id}
            class:flash-mine={flashing.get(r.session_instance_tune_id)?.kind === 'mine'}
            class:flash-remote={flashing.get(r.session_instance_tune_id)?.kind === 'remote'}
            class:flash-merge={flashing.get(r.session_instance_tune_id)?.kind === 'merge'}
            style={viewing ? '' : rowStyle(r)}
            onclick={() => r._resolving ? (!viewing && selectRow(r.session_instance_tune_id)) : (r._temp || r._removing ? null : viewing ? openDrawer(r) : selectRow(r.session_instance_tune_id))}
          >
            <span class="name">{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}</span>
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
              {#if !viewing}<button class="info-btn" title="Tune details" onclick={(e) => { e.stopPropagation(); openDrawer(r) }}>ⓘ</button>{/if}
            {/if}
          </div>
          {#if !viewing && selectedId === r.session_instance_tune_id}
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
          {#if !r._temp && !viewing}
            {#if endIsOpen && si === displaySegments.length - 1 && ti === seg.tunes.length - 1}
              <!-- last tune of the open set: this seam IS the end (append) point -->
              <div class="seam end-seam" class:active={activeSeam === 'end'} onclick={() => setCursor(null)}>
                {#if activeSeam === 'end'}<span class="seam-line"></span>{:else}<span class="seam-plus">＋</span>{/if}
              </div>
            {:else}
              <div class="seam" class:active={activeSeam === `after:${r.session_instance_tune_id}`} onclick={() => setCursor(r.session_instance_tune_id)}>
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
      {#if !viewing && si < displaySegments.length - 1 && seg.breakAfter != null}
        <div class="seam inter-seam" class:active={activeSeam === `inter:${displaySegments[si + 1].tunes[0].session_instance_tune_id}`} onclick={() => setNewSetCursor(displaySegments[si + 1].tunes[0].session_instance_tune_id)}>
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
    {#if ordered.length && !endIsOpen && !viewing}
      <!-- closed end (trailing break): the end cursor starts a NEW set here -->
      <div class="seam end-seam new-set-end" class:active={activeSeam === 'end'} onclick={() => setCursor(null)}>
        {#if activeSeam === 'end'}
          <span class="seam-line"></span><span class="seam-hint">new set</span>
        {:else}<span class="seam-plus">＋ new set</span>{/if}
      </div>
    {/if}
    <!-- scroll room so the end-of-list seam can rise ABOVE the upward dropdown (§D) -->
    {#if dropdownOpen}<div class="drop-spacer" style="height:{resultsH}px" aria-hidden="true"></div>{/if}
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  {#if !viewing && othersTyping.length}
    <div class="typing">
      {#each othersTyping as t (t.person_id)}<span class="t-name" style="color:{colorFor(t.arrival_seq)}">{t.name}</span>{/each}
      <span class="t-verb">{othersTyping.length === 1 ? 'is' : 'are'} typing…</span>
    </div>
  {/if}

  <div class="dock">
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
    {#if showNext || results.length || (noMatch && editingId == null)}
      <ul class="results" bind:clientHeight={resultsH}>
        {#if showNext && nextSuggestion}
          {@const parts = suggestionParts(nextSuggestion.name, input)}
          <li class="result-next" onmousedown={(e) => e.preventDefault()} onclick={() => pickResult(nextSuggestion)}>
            <span class="r-arrow" aria-hidden="true">→</span>
            <span class="r-name">{parts.pre}<strong>{parts.mid}</strong>{parts.post}</span>
            <span class="r-meta">{nextSuggestion.tune_type || ''}<span class="r-next-label"> · usually next</span></span>
          </li>
        {/if}
        {#each visibleResults as t (t.tune_id)}
          <li onmousedown={(e) => e.preventDefault()} onclick={() => pickResult(t)}>
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
          <li class="result-asis" onmousedown={(e) => e.preventDefault()} onclick={logAsIs}>
            <span class="r-name">Log “{resolving.text}” as-is</span>
          </li>
        {:else if editingId == null && (results.length || noMatch)}
          <li class="result-deeper" onmousedown={(e) => e.preventDefault()} onclick={openDeep}>
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
          placeholder={composerLocked ? 'Resolving…' : (editingId != null ? 'Re-pick or rename this tune…' : 'Search or type a tune…')}
          bind:value={input}
          bind:this={inputEl}
          oninput={onInput}
          onfocus={() => { composerFocused = true; scheduleSeam() }}
          onblur={stopTyping}
          onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (!input.trim() && nextSuggestion) pickResult(nextSuggestion); else commit() } else if (e.key === 'Escape' && resolving) { e.preventDefault(); cancelResolving(true) } }}
        />
        {#if searching}<span class="spinner input-spin"></span>{/if}
      </div>
      <button onmousedown={(e) => e.preventDefault()} onclick={commit}>{editingId != null ? 'Save' : 'Log'}</button>
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
  </div>

  {#if attendanceOpen}
    <div class="drawer-scrim" onclick={closeAttendance}></div>
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

        <button class="att-create-toggle" onclick={() => (showCreate = !showCreate)}>{showCreate ? '× Cancel' : '＋ Create new person'}</button>
        {#if showCreate}
          <div class="att-create">
            <input placeholder="First name" bind:value={newFirst} />
            <input placeholder="Last name" bind:value={newLast} />
            <button class="att-add" disabled={!newFirst.trim()} onclick={createPerson}>Add</button>
          </div>
        {/if}
      </div>
    </aside>
  {/if}

  {#if deepOpen}
    <div class="deep-modal" transition:fly={{ y: 24, duration: 200 }}>
      <div class="deep-head">
        <span class="deep-title">Find a tune</span>
        <button class="deep-done" onclick={closeDeep}>Done</button>
      </div>
      <input
        class="deep-field"
        placeholder={deepMode === 'abc' ? 'Search by notes, e.g. GED or EBBA…' : deepMode === 'name' ? 'Search by name…' : 'Search by name or notes…'}
        bind:value={deepQuery}
        oninput={onDeepInput}
        onkeydown={deepKey}
        autofocus
      />
      <div class="deep-tabs">
        <button class="deep-tab" class:active={deepMode === 'name'} onclick={() => setDeepMode('name')}>By name</button>
        <button class="deep-tab" class:active={deepMode === 'abc'} onclick={() => setDeepMode('abc')}>By ABC</button>
        <button class="deep-tab deep-filter-tab" class:active={deepType || deepFilterOpen} title="Filter by type" aria-label="Filter by type" onclick={toggleDeepFilters}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>
            <line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>
            <line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>
            <line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>
          </svg>
        </button>
      </div>
      {#if deepFilterOpen}
        <div class="deep-filters">
          {#each DEEP_TYPES as t}
            <button class="deep-type-chip" class:active={deepType === t} onclick={() => setDeepType(t)}>{pluralType(t)}</button>
          {/each}
        </div>
      {:else if deepType}
        <div class="deep-filters">
          <button class="filter-pill" onclick={() => setDeepType(deepType)}>{pluralType(deepType)} <span class="x">✕</span></button>
        </div>
      {/if}
      {#if deepMode !== 'abc' && deepQuery.trim()}
        <button class="deep-asis" onclick={deepLogAsIs}>＋ Log “{deepQuery.trim()}” as-is (unlinked)</button>
      {/if}
      <div class="deep-results">
        {#if deepLoading && !deepResults.length}
          <p class="deep-empty">Searching…</p>
        {:else if !deepResults.length}
          <p class="deep-empty">No{deepType ? ` ${deepType.toLowerCase()}` : ''} tunes match{deepQuery.trim() ? ` “${deepQuery.trim()}”` : ''}.</p>
        {:else}
          {#each deepResults as r (r.tune_id)}
            <button class="deep-card" onclick={() => pickDeep(r)}>
              <div class="deep-card-head">
                <span class="deep-name">{r.name}</span>
                <span class="deep-type">{r.tune_type || ''}</span>
              </div>
              <div class="deep-staff">
                <Incipit {config} tuneId={r.tune_id} image={r.incipit_image} canRender={r.can_render} />
              </div>
              <div class="deep-meta">
                {#if r.abc_only}<span class="deep-badge">♪ notation</span>{/if}
                {#if r.on_list}<span class="deep-badge star">★ on your list</span>{/if}
                {#if r.in_session}<span class="deep-badge">in this session</span>{/if}
                {#if r.played_here}<span class="deep-badge">played here {r.played_here}×</span>{/if}
                <span class="deep-books">{r.tunebook_count ?? 0} tunebooks</span>
              </div>
            </button>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</main>
