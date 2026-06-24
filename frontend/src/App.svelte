<script>
  import { onMount, onDestroy } from 'svelte'
  import { SvelteMap, SvelteSet } from 'svelte/reactivity'
  import { bootstrap, sendOp, sendTyping, searchTunes, tuneDetail, openStream } from './client.js'
  import { queuePut, queueAll, queueDelete, snapshotPut, snapshotGet } from './offline.js'
  import { generateAppend, generateBetween } from './fracindex.js'

  let { config } = $props()

  // Canonical records keyed by id (tunes + break rows), applied idempotently.
  // SvelteMap (not a plain Map) so .set/.delete are reactive in Svelte 5.
  const byId = new SvelteMap()
  // op_id -> {tempId, name, op_type, payload, status, ts}. status 'sending' = online
  // optimistic in-flight (§A2); 'queued' = offline, persisted to IndexedDB (§G).
  const pending = new SvelteMap()
  const flashing = new SvelteSet() // record ids briefly highlighted on settle (§39)
  let sseStatus = $state('connecting') // raw SSE state: connecting | live | reconnecting | error
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
  let activity = $state(null) // transient "X did Y" notice for others' changes (§E)
  let activitySeq = 0

  let es = null
  let inputEl // the composer input element (for stay-hot refocus)
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
  let lastTypingSent = 0 // throttle the "still typing" refresh
  let highWater = 0 // max event_id seen; persisted with the snapshot for offline resume
  let snapTimer = null
  let everConnected = false // distinguishes the first connect from a reconnect
  let syncMsg = $state(null) // transient "N synced · M added while away" on reconnect (§I36)
  let syncMsgSeq = 0
  let sessionId = null // for search ranking/flagging (set from bootstrap when online)
  let sessionName = $state('')
  let sessionDate = $state('')
  let notesText = $state('')
  let menuOpen = $state(false)
  let expanded = $state(false)
  let results = $state([]) // type-ahead search results shown above the composer (§D)
  let resultsQuery = '' // the query `results` correspond to (guards the debounce race)
  let searchTimer = null
  let searchSeq = 0

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
  const PALETTE = ['#4f9dff', '#46d27a', '#e0b341', '#e0594b', '#b07cff', '#3fd0c9', '#ff8fab', '#9ab0c0']
  const colorFor = (seq) => PALETTE[((seq % PALETTE.length) + PALETTE.length) % PALETTE.length]
  const initials = (name) => (name || '?').trim().slice(0, 2).toUpperCase()

  function put(record) {
    if (!record) return
    byId.set(record.session_instance_tune_id, record)
  }

  function drop(id) {
    byId.delete(id)
  }

  // Briefly highlight a record when it settles / changes (the §39 settle-flash).
  function flashId(id) {
    if (id == null) return
    flashing.add(id)
    setTimeout(() => flashing.delete(id), 700)
  }

  // Ordered, non-deleted records (tunes + breaks), then segment into sets on breaks.
  const ordered = $derived(
    [...byId.values()]
      .filter((r) => !r.deleted)
      .sort((a, b) => (a.order_position < b.order_position ? -1 : a.order_position > b.order_position ? 1 : 0))
  )
  const sets = $derived.by(() => {
    const out = []
    let cur = []
    for (const r of ordered) {
      if (r.record_type === 'break') {
        if (cur.length) out.push(cur)
        cur = []
      } else {
        cur.push(r)
      }
    }
    if (cur.length) out.push(cur)
    return out
  })
  const lastRecordId = $derived(ordered.length ? ordered[ordered.length - 1].session_instance_tune_id : null)

  // Insertion point (spec 021 §B): null = append at the end (the 95% case); a
  // record id = insert right after that record. The active seam shows the yellow line.
  let insertAfterId = $state(null)
  // Validated cursor for rendering (a removed target falls back to "end").
  const cursorId = $derived(
    insertAfterId != null && byId.has(insertAfterId) && !byId.get(insertAfterId).deleted ? insertAfterId : null
  )

  function maxPos() {
    let m = ''
    for (const r of byId.values()) if (r.order_position && r.order_position > m) m = r.order_position
    return m
  }
  // The server anchor + optimistic order_position for the current cursor.
  function cursorPos() {
    if (insertAfterId == null) return { afterId: null, position: generateAppend(maxPos()) }
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === insertAfterId)
    if (idx === -1) return { afterId: null, position: generateAppend(maxPos()) } // target gone -> append
    const before = ordered[idx].order_position
    const after = idx + 1 < ordered.length ? ordered[idx + 1].order_position : null
    return { afterId: insertAfterId, position: generateBetween(before, after) }
  }
  function setCursor(id) {
    insertAfterId = id
    queueMicrotask(() => inputEl?.focus())
  }

  // --- row selection + actions (spec 021 §E) ---
  let selectedId = $state(null) // the "opened" tune row (shows its action bar)
  let drawer = $state(null) // tune-detail drawer: null | {loading|unlinked|error|detail}

  function selectRow(id) {
    selectedId = selectedId === id ? null : id
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
    const pid = predecessorId(id) // "before X" = after X's predecessor
    if (pid != null) setCursor(pid)
    selectedId = null
  }
  function confirmRow(id) {
    op('set_confidence', { record_id: id, confidence: 100 }, 'Confirm')
    selectedId = null
  }
  function removeRow(id) {
    removeTune(id)
    selectedId = null
  }

  async function openDrawer(r) {
    selectedId = null
    if (!r.tune_id) {
      drawer = { unlinked: true, name: r.name }
      return
    }
    drawer = { loading: true, name: r.name }
    try {
      drawer = await tuneDetail(config, r.tune_id)
    } catch (e) {
      drawer = { error: e.message, name: r.name }
    }
  }
  const closeDrawer = () => (drawer = null)

  // Optimistic rows (add tunes AND breaks) live in byId as temp records with a
  // sortable position, so they segment into sets uniformly. Display = the sets.
  const displaySets = $derived(sets)

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
      case 'attribute_set_starter': return `set who started ${n}`
      case 'set_confidence': return `confirmed ${n}`
      default: return null
    }
  }

  // A change made by someone else — surface a brief, attributed activity notice (§E).
  function noteRemote(d) {
    if (!d.actor || d.actor.person_id == null || d.actor.person_id === person.person_id) return
    const label = remoteLabel(d)
    if (!label) return
    const seq = ++activitySeq
    activity = { text: `${d.actor.name || 'Someone'} ${label}`, color: colorForPerson(d.actor.person_id) }
    setTimeout(() => { if (seq === activitySeq) activity = null }, 4000)
  }

  // Apply one server-authoritative op (spec 024). Dispatch by op_type.
  function applyOp(d) {
    if (d.op_id && pending.has(d.op_id)) {
      const entry = pending.get(d.op_id) // settle our optimistic/queued op...
      if (entry.tempId) {
        if (insertAfterId === entry.tempId) insertAfterId = d.record?.session_instance_tune_id ?? null
        byId.delete(entry.tempId) // ...drop its optimistic temp record
      }
      pending.delete(d.op_id)
      queueDelete(d.op_id) // ...and drop it from the persisted queue (already applied)
    }
    if (d.event_id && d.event_id > highWater) highWater = d.event_id
    noteRemote(d)
    switch (d.op_type) {
      case 'add_tune':
      case 'change_tune':
      case 'set_confidence':
      case 'attribute_set_starter':
      case 'corroborate': // server collapsed a duplicate into this record (§H30)
        put(d.record)
        flashId(d.record?.session_instance_tune_id)
        break
      case 'set_break':
        if (d.removed) drop(d.record_id)
        else put(d.record)
        break
      case 'remove_tune':
        if (d.record) (d.record.deleted ? drop(d.record.session_instance_tune_id) : put(d.record))
        break
      case 'edit_notes':
      case 'mark_complete':
      case 'mark_incomplete':
        break // metadata; header-only (not shown in this minimal Phase 1 UI)
    }
    scheduleSnapshot() // keep the offline snapshot fresh
  }

  async function op(op_type, payload, label) {
    error = ''
    // Chunk 1 only queues add_tune offline; other ops need connectivity. Fail
    // gracefully with a notice rather than a raw error (full offline support later).
    if (!navigator.onLine) {
      notice = `You're offline — ${label || op_type} isn't available offline yet.`
      return
    }
    try {
      const res = await sendOp(config, op_type, payload)
      if (res.rejected) notice = res.message || `${label || op_type}: ${res.reason}`
    } catch (e) {
      if (e.networkError) notice = `You're offline — ${label || op_type} isn't available offline yet.`
      else error = e.message
    }
  }

  // Hold an op for reconnect replay (persisted to IndexedDB, §G).
  // Reflect an op's status on its optimistic temp record (sending vs queued).
  function markTempStatus(entry, st) {
    if (entry.tempId && byId.has(entry.tempId)) byId.set(entry.tempId, { ...byId.get(entry.tempId), _status: st })
  }

  async function markQueued(entry) {
    entry.status = 'queued'
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
  }

  function settleOp(entry, res) {
    pending.delete(entry.op_id)
    queueDelete(entry.op_id)
    if (res.rejected) {
      undoOp(entry)
      notice = res.message || `${entry.op_type}: ${res.reason}`
      return
    }
    if (entry.tempId) byId.delete(entry.tempId) // drop optimistic temp; the real record arrives below / via SSE
    if (res.record) {
      if (insertAfterId === entry.tempId) insertAfterId = res.record.session_instance_tune_id // cursor follows to the real id
      put(res.record) // settle now if the ack beat the SSE echo (idempotent)
      flashId(res.record.session_instance_tune_id)
    }
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
    try {
      const res = await sendOp(config, entry.op_type, entry.payload, entry.op_id)
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
  async function flush() {
    if (flushing) return
    flushing = true
    try {
      const queued = [...pending.values()].filter((e) => e.status === 'queued').sort((a, b) => a.ts - b.ts)
      for (const entry of queued) {
        await trySend(entry)
        if (entry.status === 'queued') break // still offline
      }
    } finally {
      flushing = false
    }
  }

  // Shared optimistic add: place a temp row at the cursor, send/queue the op, and
  // advance the cursor past it (so a burst logs a set in order). §B/§D13.
  function addOptimistic(payload, name) {
    const op_id = crypto.randomUUID()
    const tempId = `temp-${op_id}`
    const { afterId, position } = cursorPos()
    byId.set(tempId, {
      session_instance_tune_id: tempId, name, tune_id: payload.tune_id ?? null, record_type: 'tune',
      order_position: position, deleted: false, _temp: true, _status: 'sending',
    })
    trySend({ op_id, name, op_type: 'add_tune', payload: { ...payload, after_record_id: afterId }, status: 'sending', ts: Date.now(), tempId })
    if (insertAfterId != null) insertAfterId = tempId // mid-insert: cursor follows the new tune
  }

  // Cancel a pending debounced search AND invalidate any in-flight one, so a late
  // result can't repopulate the dropdown after we've committed/dismissed.
  function cancelSearch() {
    if (searchTimer) { clearTimeout(searchTimer); searchTimer = null }
    searchSeq++ // a search already awaiting will fail its seq check and be discarded
  }

  function clearEntry() {
    input = ''
    results = []
    resultsQuery = ''
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
  // (spec 021 §D13 burst entry).
  function pickResult(t) {
    clearEntry()
    addOptimistic({ tune_id: t.tune_id, name: t.name }, t.name)
    queueMicrotask(() => inputEl?.focus())
  }

  // Enter commits the top match: pick the top visible result (what the user sees
  // ranked first) — covers partials like "humours" -> "The Humours of …". Only when
  // there's truly no match does it fall back to adding the raw text (server still
  // tries an exact match on that). Fast-typing fallback: do a quick lookup if the
  // debounced results haven't landed yet.
  async function commit() {
    const q = input.trim()
    if (!q) return
    // Only trust the dropdown if it matches the CURRENT text (the debounced search
    // may still be showing results for an earlier prefix); otherwise look up fresh.
    if (resultsQuery === q && results.length) { pickResult(results[0]); return }
    const r = await searchTunes(config, q, sessionId)
    if (r.length) pickResult(r[0])
    else submit()
  }

  // Progressive type-ahead search (debounced), shown above the composer.
  function runSearch() {
    const q = input.trim()
    if (q.length < 2) {
      results = []
      resultsQuery = q
      return
    }
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(async () => {
      const seq = ++searchSeq
      const r = await searchTunes(config, q, sessionId)
      if (seq === searchSeq) {
        results = r
        resultsQuery = q
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
    if (lastTypingSent) {
      lastTypingSent = 0
      sendTyping(config, false)
    }
    // Result clicks use mousedown+preventDefault (no blur), so we can close
    // immediately on a real blur and cancel any pending search.
    cancelSearch()
    results = []
    resultsQuery = ''
  }

  const othersTyping = $derived(typers.filter((t) => t.person_id !== person.person_id))

  let connSeq = 0 // guards against overlapping connect() calls leaking a stream
  async function connect() {
    const myGen = ++connSeq
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
              session_name: cached.session_name, session_date: cached.session_date, notes: cached.notes }
          : { records: [], last_event_id: 0 }
        fromCache = true
      }
      if (myGen !== connSeq) return // a newer connect() superseded this one
      byId.clear()
      for (const r of snap.records || []) put(r)
      if (snap.current_person) person = snap.current_person
      if (snap.session_name) sessionName = snap.session_name
      if (snap.session_date) sessionDate = snap.session_date
      notesText = snap.notes || ''
      highWater = snap.last_event_id || 0
      if (!fromCache) await saveSnapshot() // refresh the cache from server truth, immediately
      await hydrateQueue() // re-apply still-queued ops' optimistic state onto these records

      if (fromCache) {
        // Offline: render from cache, don't open a doomed SSE that retries every ~3s.
        // Slow-poll a reconnect; the 'online' event also triggers one immediately.
        everConnected = true // this counts as having connected, so the next (online) reconnect summarizes
        scheduleReconnect()
        return
      }

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
      })
      if (myGen !== connSeq) { stream.close(); return } // superseded after we opened
      es = stream

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
      } else if (entry.op_type === 'set_break') {
        entry.tempId = `temp-${entry.op_id}`
        byId.set(entry.tempId, {
          session_instance_tune_id: entry.tempId, record_type: 'break',
          order_position: nextTempPos(), deleted: false, _temp: true,
        })
      } else if (entry.op_type === 'remove_tune') {
        const r = byId.get(entry.payload.record_id)
        if (r && !r._removing) byId.set(r.session_instance_tune_id, { ...r, _removing: entry.op_id })
      }
    }
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
    connect() // bootstraps records, then hydrateQueue() re-applies any queued ops
    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('pageshow', onPageShow)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
  })

  onDestroy(() => {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('pageshow', onPageShow)
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (reconnectPoll) clearTimeout(reconnectPoll)
    if (es) es.close()
  })
</script>

<main>
  <div class="topnav">
    <div class="appbar">
      <a class="brand" href="/" aria-label="ceol.io home"><img src="/static/images/logo3-1.png" alt="ceol" /></a>
      <div class="appbar-actions">
        <button class="hamburger-btn" aria-label="Menu" onclick={() => (menuOpen = !menuOpen)}>
          <span></span><span></span><span></span>
        </button>
        {#if menuOpen}
          <div class="hamburger-dropdown show">
            {#if person.first_name}<span class="hamburger-item who">{person.first_name} {person.last_name || ''}</span>{/if}
            <a class="hamburger-item" href="/my-tunes">My Tunes</a>
            <a class="hamburger-item" href="/me">My Sessions</a>
            <a class="hamburger-item" href="/add-session">Add A Session</a>
            <a class="hamburger-item" href="/share">Share</a>
            <a class="hamburger-item" href="/help">Help</a>
            <a class="hamburger-item" href="/logout">Log Out</a>
          </div>
        {/if}
      </div>
    </div>

    <header class="topbar">
      <div class="topbar-row" onclick={() => (expanded = !expanded)}>
        <div class="topbar-main">
          <div class="session-name">{sessionName || 'Session'}</div>
          <div class="session-date">{sessionDate}</div>
        </div>
        <span class="topbar-presence">
          {#each roster as p (p.person_id)}
            <span class="avatar" style="background:{colorFor(p.arrival_seq)}" title="{p.name}{p.devices > 1 ? ` (${p.devices} devices)` : ''}">
              {initials(p.name)}{#if p.devices > 1}<sup>{p.devices}</sup>{/if}
            </span>
          {/each}
        </span>
        <span class="status status-{displayStatus}" title="connection">{displayStatus}</span>
        <span class="header-chevron" class:up={expanded}>▾</span>
      </div>
      {#if expanded}
        <div class="header-expand">
          <div class="header-stat">{tunes.length} tune{tunes.length === 1 ? '' : 's'} in {sets.length} set{sets.length === 1 ? '' : 's'}</div>
          {#if notesText}<div class="header-stat header-notes">{notesText}</div>{/if}
          {#if roster.length}
            <div class="header-stat">Currently logging: {roster.map((p) => p.name).join(', ')}</div>
          {/if}
        </div>
      {/if}
    </header>
  </div>

  <div class="feed-msgs">
    {#if notice}<p class="notice" onclick={() => (notice = '')}>{notice}</p>{/if}
    {#if activity}
      <p class="activity"><span class="dot" style="background:{activity.color}"></span>{activity.text}</p>
    {/if}
    {#if syncMsg}
      <p class="sync-msg">↻ {syncMsg}</p>
    {/if}
    {#if queuedCount > 0}
      <p class="offline-banner">
        ⏳ {queuedCount} change{queuedCount === 1 ? '' : 's'} queued{displayStatus === 'offline' ? ' — offline' : ', syncing…'}
      </p>
    {/if}
  </div>

  <div class="sets" bind:this={setsEl} onscroll={onScroll}>
    {#each displaySets as set (set[0].session_instance_tune_id)}
      <div class="set">
        {#each set as r (r.session_instance_tune_id)}
          <div
            class="tune-row"
            class:low={!r._temp && r.confidence != null && r.confidence <= 70}
            class:pending={r._temp}
            class:queued={r._temp && r._status === 'queued'}
            class:removing={r._removing}
            class:selected={selectedId === r.session_instance_tune_id}
            class:flash={flashing.has(r.session_instance_tune_id)}
            onclick={() => !r._temp && !r._removing && selectRow(r.session_instance_tune_id)}
          >
            <span class="name">{r.name || (r.tune_id ? `#${r.tune_id}` : '(unnamed)')}</span>
            {#if r._temp}
              <span class="actions"><span class="hourglass" title={r._status === 'queued' ? 'Queued (offline)' : 'Sending…'}>⏳</span></span>
            {:else if r._removing}
              <span class="actions"><button class="restore" onclick={(e) => { e.stopPropagation(); restore(r.session_instance_tune_id) }}>Restore</button></span>
            {:else}
              <button class="info-btn" title="Tune details" onclick={(e) => { e.stopPropagation(); openDrawer(r) }}>ⓘ</button>
            {/if}
          </div>
          {#if selectedId === r.session_instance_tune_id}
            <div class="row-actions">
              {#if predecessorId(r.session_instance_tune_id) != null}
                <button onclick={() => insertBeforeRow(r.session_instance_tune_id)}>↑ Before</button>
              {/if}
              <button onclick={() => insertAfterRow(r.session_instance_tune_id)}>↓ After</button>
              {#if r.confidence != null && r.confidence <= 70}
                <button onclick={() => confirmRow(r.session_instance_tune_id)}>✓ Confirm</button>
              {/if}
              <button class="danger" onclick={() => removeRow(r.session_instance_tune_id)}>🗑 Remove</button>
            </div>
          {/if}
          {#if !r._temp}
            <div class="seam" class:active={cursorId === r.session_instance_tune_id} onclick={() => setCursor(r.session_instance_tune_id)}>
              {#if cursorId === r.session_instance_tune_id}<span class="seam-line"></span>{:else}<span class="seam-plus">＋</span>{/if}
            </div>
          {/if}
        {/each}
      </div>
    {:else}
      <p class="empty">No tunes yet — log one below.</p>
    {/each}
    {#if ordered.length}
      <div class="seam end-seam" class:active={cursorId === null} onclick={() => setCursor(null)}>
        {#if cursorId === null}<span class="seam-line"></span>{:else}<span class="seam-plus">＋ insert here</span>{/if}
      </div>
    {/if}
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  {#if othersTyping.length}
    <div class="typing">
      {#each othersTyping as t (t.person_id)}<span class="t-name" style="color:{colorFor(t.arrival_seq)}">{t.name}</span>{/each}
      <span class="t-verb">{othersTyping.length === 1 ? 'is' : 'are'} typing…</span>
    </div>
  {/if}

  <div class="dock">
    {#if !atEnd}
      <button class="goend-pill" onclick={goToEnd}>↓ Go to end</button>
    {/if}
    {#if results.length}
      <ul class="results">
        {#each results as t (t.tune_id)}
          <li onmousedown={(e) => e.preventDefault()} onclick={() => pickResult(t)}>
            <span class="r-name">{t.name}</span>
            <span class="r-meta">
              {t.tune_type || ''}{#if t.in_session_tune}<span class="r-insession"> · in session</span>{/if}
            </span>
          </li>
        {/each}
      </ul>
    {/if}

    <div class="composer">
      <input
        placeholder="Search or type a tune…"
        bind:value={input}
        bind:this={inputEl}
        oninput={onInput}
        onblur={stopTyping}
        onkeydown={(e) => e.key === 'Enter' && commit()}
      />
      <button onmousedown={(e) => e.preventDefault()} onclick={commit}>Log</button>
      <button
        class="endset"
        title="End the current set"
        disabled={!lastRecordId}
        onclick={endSet}
      >End set</button>
    </div>
  </div>

  {#if drawer}
    <div class="drawer-scrim" onclick={closeDrawer}></div>
    <aside class="drawer">
      <div class="drawer-head">
        <div class="drawer-title">{drawer.name}</div>
        <button class="drawer-done" onclick={closeDrawer}>Done</button>
      </div>
      <div class="drawer-body">
        {#if drawer.loading}
          <p class="d-note">Loading…</p>
        {:else if drawer.unlinked}
          <p class="d-note">Logged as text — not linked to a catalog tune yet, so there's no detail to show. (Linking it later pulls in stats, notation, and the thesession.org page.)</p>
        {:else if drawer.error}
          <p class="error">{drawer.error}</p>
        {:else}
          <div class="d-sub">{drawer.tune_type || ''}</div>
          <div class="d-links">
            <a href={`https://thesession.org/tunes/${drawer.tune_id}`} target="_blank" rel="noopener">thesession.org ↗</a>
          </div>
          <div class="d-section">
            <div class="d-statrow"><span>TheSession popularity</span><b>{drawer.tunebook_count ?? 0}</b></div>
            <div class="d-statrow"><span>Played at this session</span><b>{drawer.played_here}×</b></div>
            <div class="d-statrow"><span>Played globally</span><b>{drawer.played_global}×</b></div>
          </div>
          <div class="d-section">
            <div class="d-label">History at this session</div>
            <ul class="d-history">
              {#each drawer.dates as d}<li>{d}</li>{:else}<li>—</li>{/each}
            </ul>
          </div>
        {/if}
      </div>
    </aside>
  {/if}
</main>
