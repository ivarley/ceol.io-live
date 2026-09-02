<script>
  // Recording segmenter (spec 050): put start/end timestamps on the tunes already
  // logged against a night's audio, fast enough to do a three-hour session in one
  // sitting. The output is the training corpus for tune recognition.
  //
  // The interaction is one key. A cursor sits on the next tune in the log; find
  // where it starts in the audio, press M, cursor advances. Ends come free --
  // the next tune's start IS the previous tune's end -- so an explicit end is
  // only typed at the end of a set, where chatter follows.
  import { onMount, tick } from 'svelte'
  import Waveform from './Waveform.svelte'
  import TuneList from './TuneList.svelte'
  import {
    edgeLimits,
    formatTime,
    nextUnplacedIndex,
    resolveSegments,
    snapToOnset,
    SPEEDS,
    ZOOM_LEVELS,
  } from './logic.js'

  let { pageData = null } = $props()

  const recording = $derived(pageData?.recording ?? null)
  const instance = $derived(pageData?.session_instance ?? null)

  // A deliberate one-time snapshot, not a mirror: `tunes` is the working copy the
  // operator edits, and pageData is a server-embedded blob that never changes
  // after mount. Re-deriving it would throw away every unsaved mark.
  // svelte-ignore state_referenced_locally
  let tunes = $state((pageData?.tunes ?? []).map((t) => ({ ...t })))
  let cursorIndex = $state(0)
  let currentMs = $state(0)
  let playing = $state(false)
  let speed = $state(1)
  let zoomMs = $state(20000)
  let snapEnabled = $state(true)
  let peaks = $state(null)
  let status = $state('')
  let statusKind = $state('info')
  let saving = $state(0)
  // 'loading' until the browser can play, 'buffering' when it runs dry mid-play.
  // Starts pessimistic: a 350MB file over cellular is not ready for a while, and
  // the waveform paints instantly from the precomputed peaks -- so the page LOOKS
  // finished long before the audio is. That gap is what makes it read as broken.
  let mediaState = $state('loading')

  // Which encode is being streamed. Both go down with the payload (proxy first);
  // which one you want depends on the connection you happen to be on, so it is a
  // control rather than a decision made at import time.
  const SOURCE_PREF_KEY = 'ceol.segmenter.audioSource'
  // svelte-ignore state_referenced_locally
  let sourceId = $state(
    (() => {
      const available = (pageData?.recording?.audio_sources ?? []).map((s) => s.id)
      let saved = null
      try {
        saved = window.localStorage.getItem(SOURCE_PREF_KEY)
      } catch {
        // Private browsing and friends: fall through to the default.
      }
      return available.includes(saved) ? saved : available[0] ?? null
    })(),
  )

  // Phone layout. The left column is sticky, so anything it does not need is
  // height the tune list does not get -- and on a phone that was the difference
  // between two visible tunes and a usable list. Read synchronously at init
  // rather than in onMount, so the tape is never drawn tall and then re-drawn
  // short on the first frame.
  const COMPACT_QUERY = '(max-width: 900px)'
  let compact = $state(
    typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(COMPACT_QUERY).matches : false,
  )

  // How much chrome sits above the tool -- the site's fixed header plus the
  // page padding. The phone layout gives the tape and the controls the top of
  // the screen and lets ONLY the log scroll under them, which means knowing
  // exactly how tall "the rest of the screen" is. Measured rather than
  // hardcoded so a change to the surrounding template can't quietly leave the
  // mark button hanging off the bottom; the 60px fallback in the stylesheet is
  // what it measures to today.
  let rootEl = $state(null)
  let topOffset = $state(60)

  function measureTop() {
    if (!rootEl) return
    const top = Math.round(rootEl.getBoundingClientRect().top + (window.scrollY || 0))
    if (top > 0) topOffset = top
  }

  const durationMs = $derived(recording?.duration_ms ?? 0)
  const segments = $derived(resolveSegments(tunes, durationMs))
  const placedCount = $derived(tunes.filter((t) => t.segment).length)
  const cursorTune = $derived(tunes[cursorIndex] ?? null)
  const mediaBusy = $derived(mediaState === 'loading' || mediaState === 'buffering')
  const audioSources = $derived(recording?.audio_sources ?? [])
  const currentSource = $derived(audioSources.find((s) => s.id === sourceId) ?? audioSources[0] ?? null)

  // The tune whose resolved range covers the playhead -- what "this tune ends
  // here" refers to.
  const soundingId = $derived.by(() => {
    for (const [id, seg] of segments) {
      if (currentMs >= seg.startMs && currentMs < seg.endMs) return id
    }
    return null
  })

  let audio = $state(null)
  let scrubbing = false
  let resumeAfterScrub = false
  const undoStack = []

  // Where the playhead was when "Fix the log" left this page (below). The way
  // back is the log header's own Recordings row, which carries no timestamp, so
  // the spot is left here instead of in the URL. sessionStorage and read-once:
  // it means "resume this round trip", not "always reopen where I left off".
  //
  // The element has no metadata at mount, and setting currentTime before it does
  // wedges the load outright (see switchSource), so it is applied on
  // loadedmetadata rather than immediately.
  const RESUME_KEY = (id) => `ceol.segmenter.resume.${id}`
  let pendingSeekMs = null

  function applyPendingSeek() {
    if (pendingSeekMs == null || !audio) return
    audio.currentTime = pendingSeekMs / 1000
    pendingSeekMs = null
  }

  function dropResumeMarkOnRestore(event) {
    if (event.persisted) takeResumeMark()
  }

  function takeResumeMark() {
    if (!recording) return null
    try {
      const key = RESUME_KEY(recording.recording_id)
      const raw = window.sessionStorage.getItem(key)
      window.sessionStorage.removeItem(key)
      if (raw == null) return null
      return Math.min(durationMs, Math.max(0, Number(raw) || 0))
    } catch {
      return null // private browsing and friends: just open at the top
    }
  }

  onMount(() => {
    const resumeAt = takeResumeMark()
    if (resumeAt != null) {
      // Paint the waveform at the remembered spot immediately -- the peaks are
      // already here, so the tape is back in place long before the audio is.
      pendingSeekMs = resumeAt
      currentMs = resumeAt
      flash('Back where you left off')
    }
    cursorIndex = Math.max(0, nextUnplacedIndex(tunes, 0))
    // On a warm cache the element can already be playable before the handlers
    // above are bound, and then no event ever fires to clear the spinner --
    // and no loadedmetadata either, so a pending restore has to be applied here.
    if (audio && audio.readyState >= 1) applyPendingSeek()
    if (audio && audio.readyState >= 3) mediaState = 'ready'
    loadPeaks()
    const tick = () => {
      // A pending restore means the element's clock is not authoritative yet:
      // it still reads 0 (and reads 0 forever if the audio never loads), which
      // would wipe the remembered spot the waveform is already painted at.
      if (audio && !scrubbing && pendingSeekMs == null) currentMs = audio.currentTime * 1000
      raf = requestAnimationFrame(tick)
    }
    let raf = requestAnimationFrame(tick)
    window.addEventListener('keydown', onKeydown)
    const media = window.matchMedia ? window.matchMedia(COMPACT_QUERY) : null
    const onMedia = (event) => (compact = event.matches)
    media?.addEventListener('change', onMedia)
    measureTop()
    window.addEventListener('resize', measureTop)
    // Coming back with the browser's Back button restores this page from the
    // bfcache instead of mounting it again -- the playhead is already where it
    // was, and the mark left for the trip would otherwise sit there waiting to
    // yank a later, unrelated visit back to an old spot.
    window.addEventListener('pageshow', dropResumeMarkOnRestore)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('keydown', onKeydown)
      window.removeEventListener('pageshow', dropResumeMarkOnRestore)
      media?.removeEventListener('change', onMedia)
      window.removeEventListener('resize', measureTop)
    }
  })

  async function loadPeaks() {
    if (!recording?.has_peaks) return
    try {
      const res = await fetch(recording.peaks_url, { credentials: 'same-origin' })
      if (!res.ok) throw new Error(`peaks ${res.status}`)
      peaks = new Uint8Array(await res.arrayBuffer())
    } catch (err) {
      flash(`Could not load the waveform: ${err.message}`, 'error')
    }
  }

  function flash(message, kind = 'info') {
    status = message
    statusKind = kind
    if (kind !== 'error') {
      const mine = message
      setTimeout(() => {
        if (status === mine) status = ''
      }, 2600)
    }
  }

  // ---- transport -------------------------------------------------------------

  function seek(ms) {
    const clamped = Math.min(durationMs, Math.max(0, ms))
    // Going somewhere deliberately outranks the remembered spot -- otherwise a
    // restore still waiting on metadata would yank the playhead back out from
    // under a scrub that had already moved on.
    pendingSeekMs = null
    currentMs = clamped
    if (audio) audio.currentTime = clamped / 1000
  }

  function nudge(deltaMs) {
    seek(currentMs + deltaMs)
  }

  function togglePlay() {
    if (!audio) return
    if (audio.paused) {
      audio.play().catch((err) => flash(`Playback failed: ${err.message}`, 'error'))
    } else {
      audio.pause()
    }
  }

  /**
   * Switch encodes without losing your place.
   *
   * Changing an <audio> element's src resets it to zero and stops playback, so
   * the position and play state are captured first and restored once the new
   * source has metadata. Without that, switching quality mid-session throws away
   * exactly the spot you were working on.
   */
  async function switchSource(id) {
    if (!audio || id === sourceId || !audioSources.some((s) => s.id === id)) return
    const resumeAt = audio.currentTime
    const wasPlaying = !audio.paused
    mediaState = 'loading'
    sourceId = id
    try {
      window.localStorage.setItem(SOURCE_PREF_KEY, id)
    } catch {
      // Not being able to remember the choice is not worth failing the switch.
    }
    await tick() // the src attribute has now been rewritten

    // Wait for metadata unconditionally, and subscribe BEFORE calling load().
    // `load()` does not reset readyState synchronously, so checking it here
    // reports the OLD source's value -- and restoring the position on an
    // element that has no metadata yet wedges the load outright: networkState
    // stays LOADING, readyState stays HAVE_NOTHING, and nothing ever buffers.
    audio.addEventListener(
      'loadedmetadata',
      () => {
        audio.currentTime = resumeAt
        if (wasPlaying) audio.play().catch(() => {})
      },
      { once: true },
    )
    audio.load()
  }

  function setSpeed(value) {
    speed = value
    if (audio) audio.playbackRate = value
  }

  function cycleZoom(direction) {
    const i = ZOOM_LEVELS.indexOf(zoomMs)
    const next = Math.min(ZOOM_LEVELS.length - 1, Math.max(0, (i < 0 ? 2 : i) + direction))
    zoomMs = ZOOM_LEVELS[next]
  }

  // Pause while dragging so the playhead doesn't fight the finger, then pick up
  // where the drag left it.
  function onScrubStart() {
    scrubbing = true
    if (audio && !audio.paused) {
      resumeAfterScrub = true
      audio.pause()
    }
  }

  function onScrubEnd() {
    scrubbing = false
    if (audio) audio.currentTime = currentMs / 1000
    if (resumeAfterScrub) {
      resumeAfterScrub = false
      audio.play().catch(() => {})
    }
  }

  // ---- placement -------------------------------------------------------------

  async function save(tune, startMs, endMs) {
    saving += 1
    try {
      const res = await fetch(
        `/api/recordings/${recording.recording_id}/segments/${tune.session_instance_tune_id}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ start_ms: Math.round(startMs), end_ms: endMs == null ? null : Math.round(endMs) }),
        },
      )
      const body = await res.json()
      if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
      return body.segment
    } finally {
      saving -= 1
    }
  }

  async function place(index, startMs, endMs) {
    const tune = tunes[index]
    if (!tune) return
    const previous = tune.segment
    // Optimistic: the mark lands under the crosshair immediately, which is the
    // whole point of the tool. A failed write rolls it back and says so.
    tunes[index] = { ...tune, segment: { ...(previous ?? {}), start_ms: Math.round(startMs), end_ms: endMs == null ? null : Math.round(endMs) } }
    undoStack.push({ index, previous, cursor: cursorIndex })
    try {
      const saved = await save(tune, startMs, endMs)
      tunes[index] = { ...tunes[index], segment: saved }
    } catch (err) {
      tunes[index] = { ...tunes[index], segment: previous }
      undoStack.pop()
      flash(`Could not save "${tune.name}": ${err.message}`, 'error')
    }
  }

  /**
   * The tune waiting on an explicit end, or null.
   *
   * True exactly when the previous log entry closed a set, has been placed, and
   * hasn't been ended yet — i.e. the moment right after marking a set's last
   * tune, when the only sensible next act is to say where that set stopped.
   */
  const pendingSetEndIndex = $derived.by(() => {
    const prev = cursorIndex - 1
    const tune = prev >= 0 ? tunes[prev] : null
    if (!tune?.segment) return null
    if (!tune.is_set_end || tune.segment.end_ms != null) return null
    return prev
  })

  function markStart() {
    // Having marked a set's last tune, the next thing anyone does is mark where
    // that set ended -- so M means that here, rather than making the operator
    // remember a second key. E still works, and pressing M again once the end
    // is set moves on to the next tune as usual.
    if (pendingSetEndIndex != null) {
      markEndAt(pendingSetEndIndex)
      return
    }
    if (!cursorTune) {
      flash('Every tune in the log is placed.', 'info')
      return
    }
    const ms = snapEnabled ? snapToOnset(peaks, recording.peaks_hz, currentMs) : currentMs
    const name = cursorTune.name
    place(cursorIndex, ms, cursorTune.segment?.end_ms ?? null)
    cursorIndex = Math.min(tunes.length - 1, cursorIndex + 1)

    // Say when snap moved the mark. It used to move silently, which reads as
    // the tool ignoring where you put the playhead -- and leaves you with no
    // hint that S would turn it off.
    const shift = ms - currentMs
    if (Math.abs(shift) >= 60) {
      const dir = shift > 0 ? '+' : '−'
      flash(`${name} at ${formatTime(ms, { millis: true })} (snapped ${dir}${(Math.abs(shift) / 1000).toFixed(2)}s — S to turn off)`)
    }
  }

  function markEnd() {
    // Ends the tune under the playhead. Falls back to the last tune placed
    // before now, so it still works when the playhead has drifted past a set's
    // last tune into the chatter -- exactly when you reach for this key.
    let targetId = soundingId
    if (targetId == null) {
      let best = null
      for (const [id, seg] of segments) {
        if (seg.startMs <= currentMs && (!best || seg.startMs > best.startMs)) best = { id, startMs: seg.startMs }
      }
      targetId = best?.id ?? null
    }
    if (targetId == null) {
      flash('No placed tune before the playhead to end.', 'info')
      return
    }
    markEndAt(tunes.findIndex((t) => t.session_instance_tune_id === targetId))
  }

  function markEndAt(index) {
    const tune = tunes[index]
    if (!tune?.segment) return
    if (currentMs <= tune.segment.start_ms) {
      flash('The end has to come after the start.', 'error')
      return
    }
    place(index, tune.segment.start_ms, currentMs)
    flash(`Ended "${tune.name}" at ${formatTime(currentMs)}`)
  }

  // ---- dragging a boundary ---------------------------------------------------
  //
  // Marking is done at speed against a moving playhead, so some marks land a
  // little off -- and re-marking a tune only fixes its start. Dragging the edge
  // itself is the direct correction: grab the line, move it, let go.
  //
  // The drag is local until it is dropped. A PUT per animation frame would be
  // dozens of writes for one adjustment, and the intermediate positions are not
  // decisions -- only where the finger stops is.

  // The segment as it stood before this drag began. Kept so the save records the
  // right "previous" for undo, and so a failed write rolls back to where the
  // edge actually was rather than to the last previewed position.
  let edgeDrag = null

  function previewEdge(id, edge, ms) {
    const index = tunes.findIndex((t) => t.session_instance_tune_id === id)
    const tune = tunes[index]
    if (!tune?.segment) return
    if (!edgeDrag || edgeDrag.index !== index || edgeDrag.edge !== edge) {
      edgeDrag = { index, edge, original: tune.segment }
    }
    const limits = edgeLimits(segments, id, edge, durationMs)
    if (!limits) return
    const at = Math.round(Math.min(limits.hi, Math.max(limits.lo, ms)))
    tunes[index] = {
      ...tune,
      segment: edge === 'start' ? { ...tune.segment, start_ms: at } : { ...tune.segment, end_ms: at },
    }
    // Straight to `status`, not through flash(): this runs every frame of the
    // drag, and flash() would be scheduling and cancelling a timer each time.
    status = `${tune.name} ${edge === 'start' ? 'starts' : 'ends'} ${formatTime(at, { millis: true })}`
    statusKind = 'info'
  }

  async function commitEdge(id, edge, ms) {
    if (!edgeDrag) return
    // The drop position is a position like any other: run it through the same
    // clamping as every frame of the drag, so releasing outside the legal range
    // can't save what dragging there wouldn't have shown.
    previewEdge(id, edge, ms)
    const held = edgeDrag
    edgeDrag = null
    const index = held.index
    const moved = tunes[index]?.segment
    const original = held.original
    if (!moved) return
    if (moved.start_ms === original.start_ms && moved.end_ms === original.end_ms) {
      status = ''
      return
    }
    const tune = tunes[index]
    // Put the original back before saving: place() reads the current segment as
    // the undo point, and by now that is the previewed position.
    tunes[index] = { ...tune, segment: original }
    await place(index, moved.start_ms, moved.end_ms)
    flash(`Moved "${tune.name}" ${edge === 'start' ? 'start' : 'end'} to ${formatTime(edge === 'start' ? moved.start_ms : moved.end_ms, { millis: true })} — U to undo`)
  }

  /**
   * Unplace a tune.
   *
   * `moveCursor` puts the cursor back on the tune just cleared, which is what
   * clearing MEANS when you do it by hand: you got that one wrong and want
   * another go, so the next M belongs to it, not to whatever came after.
   * Off by default because undo() restores its own cursor position and must
   * not have it overwritten here.
   */
  async function clearAt(index, moveCursor = false) {
    const tune = tunes[index]
    if (!tune?.segment) return
    const previous = tune.segment
    const previousCursor = cursorIndex
    tunes[index] = { ...tune, segment: null }
    if (moveCursor) cursorIndex = index
    saving += 1
    try {
      const res = await fetch(
        `/api/recordings/${recording.recording_id}/segments/${tune.session_instance_tune_id}`,
        { method: 'DELETE', credentials: 'same-origin' },
      )
      const body = await res.json()
      if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
    } catch (err) {
      tunes[index] = { ...tunes[index], segment: previous }
      if (moveCursor) cursorIndex = previousCursor
      flash(`Could not clear "${tune.name}": ${err.message}`, 'error')
    } finally {
      saving -= 1
    }
  }

  async function undo() {
    const step = undoStack.pop()
    if (!step) {
      flash('Nothing to undo.', 'info')
      return
    }
    cursorIndex = step.cursor
    if (step.previous) {
      await place(step.index, step.previous.start_ms, step.previous.end_ms)
      undoStack.pop() // place() pushed its own entry; the undo itself isn't undoable
    } else {
      await clearAt(step.index)
    }
    flash(`Undid "${tunes[step.index]?.name ?? 'that mark'}"`)
  }

  function moveCursor(delta) {
    cursorIndex = Math.min(tunes.length - 1, Math.max(0, cursorIndex + delta))
  }

  function jumpToCursor() {
    const seg = cursorTune && segments.get(cursorTune.session_instance_tune_id)
    if (seg) seek(seg.startMs)
  }

  /**
   * Go fix the log, then come straight back here.
   *
   * Timestamping is where you find out the log is wrong -- a tune nobody wrote
   * down is a stretch of audio with no cursor to put on it -- and the fix is one
   * line in the logger. `edit=1` lands in edit mode rather than costing a tap to
   * get there, and the playhead is stashed first so the way back (the log
   * header's Recordings row) reopens on the same moment instead of the top of a
   * three-hour file.
   */
  function editLog() {
    if (!instance) return
    if (audio && !audio.paused) audio.pause()
    try {
      window.sessionStorage.setItem(RESUME_KEY(recording.recording_id), String(Math.round(currentMs)))
    } catch {
      // Not being able to remember the spot is not worth blocking the trip.
    }
    window.location.href = `/live/instances/${instance.session_instance_id}?edit=1`
  }

  // ---- keyboard --------------------------------------------------------------

  function onKeydown(event) {
    const el = event.target
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
    if (event.metaKey || event.ctrlKey) return

    const fine = event.altKey ? 200 : event.shiftKey ? 1000 : 5000
    let handled = true
    switch (event.key) {
      case ' ':
        togglePlay()
        break
      case 'm':
      case 'M':
      case 'Enter':
        markStart()
        break
      case 'e':
      case 'E':
        markEnd()
        break
      case 'u':
      case 'U':
      case 'Backspace':
        undo()
        break
      case 'ArrowLeft':
      case 'j':
        nudge(-fine)
        break
      case 'ArrowRight':
      case 'l':
        nudge(fine)
        break
      case 'ArrowUp':
        moveCursor(-1)
        break
      case 'ArrowDown':
        moveCursor(1)
        break
      case '-':
      case '_':
        cycleZoom(1)
        break
      case '=':
      case '+':
        cycleZoom(-1)
        break
      case 's':
      case 'S':
        snapEnabled = !snapEnabled
        flash(`Onset snap ${snapEnabled ? 'on' : 'off'}`)
        break
      case '[':
        setSpeed(SPEEDS[Math.max(0, SPEEDS.indexOf(speed) - 1)])
        break
      case ']':
        setSpeed(SPEEDS[Math.min(SPEEDS.length - 1, SPEEDS.indexOf(speed) + 1)])
        break
      case 'g':
      case 'G':
        jumpToCursor()
        break
      default:
        handled = false
    }
    if (handled) event.preventDefault()
  }
</script>

<!-- Which encode is streamed. One definition, rendered in the header on a phone
     and in the options row on a desktop -- the control is the same either way,
     only the room for it differs. -->
{#snippet audioPicker()}
  {#if audioSources.length > 1}
    <label class="sg-opt sg-opt-audio">
      audio
      <select value={sourceId} onchange={(e) => switchSource(e.currentTarget.value)}>
        {#each audioSources as src (src.id)}
          <option value={src.id}>
            {src.label}{src.size_bytes ? ` · ${Math.round(src.size_bytes / 1e6)} MB` : ''}
          </option>
        {/each}
      </select>
    </label>
  {/if}
{/snippet}

{#if !recording}
  <p class="sg-error">No recording payload. Reload the page.</p>
{:else}
  <div class="sg" bind:this={rootEl} style="--sg-top: {topOffset}px">
    <header class="sg-head">
      <div>
        <h1>{recording.label || 'Recording'}</h1>
        <p class="sg-sub">
          <a href="/sessions/{instance.session_path}">{instance.session_name}</a>
          · {instance.date}
          · {formatTime(durationMs)}
          {#if recording.clock_offset_ms}· offset {formatTime(recording.clock_offset_ms)}{/if}
        </p>
      </div>
      <div class="sg-progress">
        <strong>{placedCount}</strong> / {tunes.length}{#if !compact} placed{/if}
        {#if saving > 0}<span class="sg-saving">saving…</span>{/if}
        <!-- On a phone the encode switch rides up here with the other header
             controls: down in the options row it was one more line of the
             sticky column, and it is the one option you reach for when the
             connection changes rather than while marking. -->
        {#if compact}{@render audioPicker()}{/if}
        <button
          type="button"
          class="sg-editlog"
          onclick={editLog}
          title="Open this night's log in edit mode — you'll come back here, at this moment in the audio"
        >✎ {compact ? 'Fix' : 'Fix the log'}</button>
        <a class="sg-export" href="/api/recordings/{recording.recording_id}/export" target="_blank" rel="noopener">export</a>
      </div>
    </header>

    {#if recording.audio_error}
      <p class="sg-error">Audio unavailable: {recording.audio_error}</p>
    {/if}

    <div class="sg-body">
      <section class="sg-left">
        <Waveform
          {peaks}
          {compact}
          peaksHz={recording.peaks_hz ?? 20}
          {durationMs}
          {currentMs}
          {zoomMs}
          {segments}
          {tunes}
          cursorTuneId={cursorTune?.session_instance_tune_id ?? null}
          onseek={seek}
          onscrubstart={onScrubStart}
          onscrubend={onScrubEnd}
          onedgepreview={previewEdge}
          onedgecommit={commitEdge}
        />

        <div class="sg-clock">
          <span class="sg-time">{formatTime(currentMs, { millis: true })}</span>
          <span class="sg-of">of {formatTime(durationMs)}</span>
          {#if mediaBusy}
            <span class="sg-loading">
              {mediaState === 'loading' ? 'loading audio…' : 'buffering…'}
            </span>
          {/if}
        </div>

        <!-- Which tune the mark key will place, and in which of its two modes.
             Its own band on a desktop; on a phone it is folded into the mark
             button's own row (below), because a full-width banner is 46px of a
             sticky column that has none to spare. -->
        {#if !compact}
          {#if pendingSetEndIndex != null}
            {@const ending = tunes[pendingSetEndIndex]}
            <div class="sg-next is-ending">
              <span class="sg-next-label">end of set {ending.set_number}</span>
              <span class="sg-next-name">{ending.name}</span>
              <span class="sg-next-meta">M marks where it stopped</span>
            </div>
          {:else}
            <div class="sg-next">
              {#if cursorTune}
                <span class="sg-next-label">next up</span>
                <span class="sg-next-name">{cursorTune.name}</span>
                <span class="sg-next-meta">set {cursorTune.set_number}{cursorTune.is_set_end ? ' · last of set' : ''}</span>
              {:else}
                <span class="sg-next-label">log complete</span>
              {/if}
            </div>
          {/if}
        {/if}

        <div class="sg-controls">
          <button type="button" onclick={() => nudge(-15000)}>−15s</button>
          <button type="button" onclick={() => nudge(-5000)}>−5s</button>
          <button
            type="button"
            class="sg-play"
            onclick={togglePlay}
            aria-busy={mediaBusy}
            title={mediaBusy ? 'Audio still loading' : playing ? 'Pause' : 'Play'}
          >
            {#if mediaBusy}
              <span class="sg-spinner" aria-hidden="true"></span>
            {:else}
              {playing ? '❚❚' : '▶'}
            {/if}
          </button>
          <button type="button" onclick={() => nudge(5000)}>+5s</button>
          <button type="button" onclick={() => nudge(15000)}>+15s</button>
        </div>

        <div class="sg-controls sg-controls-main">
          <!-- Phone: the banner's job rides on the button's own row. Whose turn
               it is matters as much as the button does, and side by side they
               cost one row instead of two. No set number -- the list two
               inches below is already showing which set this is. -->
          {#if compact}
            {@const ending = pendingSetEndIndex != null ? tunes[pendingSetEndIndex] : null}
            <div class="sg-next-inline" class:is-ending={ending != null}>
              <span class="sg-next-label">{ending ? 'end of set' : cursorTune ? 'next up' : 'done'}</span>
              <span class="sg-next-name">{(ending ?? cursorTune)?.name ?? 'every tune placed'}</span>
            </div>
          {/if}
          <button
            type="button"
            class="sg-mark"
            class:is-ending={pendingSetEndIndex != null}
            onclick={markStart}
            disabled={!cursorTune && pendingSetEndIndex == null}
          >
            {pendingSetEndIndex != null ? 'End of set' : 'Mark start'}{#if !compact} <kbd>M</kbd>{/if}
          </button>
          <!-- The separate end key is for ending a set you have already scrolled
               past; the mark button covers the ordinary case on its own, by
               switching mode. On a phone that second button is a whole row for
               the rarer of the two, so the one that changes with you wins. -->
          {#if !compact}
            <button type="button" class="sg-end" onclick={markEnd}>End of set <kbd>E</kbd></button>
          {/if}
          <button type="button" class="sg-undo" onclick={undo} title="Undo the last mark" aria-label="Undo">
            {#if compact}↺{:else}Undo <kbd>U</kbd>{/if}
          </button>
        </div>

        <div class="sg-opts">
          <label class="sg-opt">
            speed
            <select value={speed} onchange={(e) => setSpeed(Number(e.currentTarget.value))}>
              {#each SPEEDS as s}<option value={s}>{s}×</option>{/each}
            </select>
          </label>
          <label class="sg-opt">
            zoom
            <select value={zoomMs} onchange={(e) => (zoomMs = Number(e.currentTarget.value))}>
              {#each ZOOM_LEVELS as z}<option value={z}>{z / 1000}s</option>{/each}
            </select>
          </label>
          <label class="sg-opt sg-opt-check">
            <input type="checkbox" bind:checked={snapEnabled} />
            snap to onset
          </label>
          {#if !compact}{@render audioPicker()}{/if}
        </div>

        <details class="sg-keys">
          <summary>Keyboard</summary>
          <dl>
            <div><dt>Space</dt><dd>play / pause</dd></div>
            <div><dt>M · Enter</dt><dd>mark start of the next tune</dd></div>
            <div><dt>E</dt><dd>explicit end (end of a set)</dd></div>
            <div><dt>U · ⌫</dt><dd>undo the last mark</dd></div>
            <div><dt>← →</dt><dd>seek 5s (⇧ 1s, ⌥ 0.2s)</dd></div>
            <div><dt>↑ ↓</dt><dd>move the cursor in the log</dd></div>
            <div><dt>G</dt><dd>go to the cursor tune's mark</dd></div>
            <div><dt>− =</dt><dd>zoom out / in</dd></div>
            <div><dt>[ ]</dt><dd>slower / faster</dd></div>
            <div><dt>S</dt><dd>toggle onset snap</dd></div>
            <div><dt>drag an edge</dt><dd>move a boundary in the tape (no snap — the drag is the correction)</dd></div>
          </dl>
        </details>
      </section>

      <section class="sg-right">
        <TuneList
          {tunes}
          {segments}
          {cursorIndex}
          onpick={(i) => (cursorIndex = i)}
          onseek={seek}
          onclear={(i) => clearAt(i, true)}
        />
      </section>
    </div>

    <audio
      bind:this={audio}
      src={currentSource ? currentSource.url : ''}
      preload="metadata"
      onplay={() => (playing = true)}
      onpause={() => (playing = false)}
      onratechange={() => audio && (speed = audio.playbackRate)}
      onloadstart={() => (mediaState = 'loading')}
      onloadedmetadata={applyPendingSeek}
      oncanplay={() => (mediaState = 'ready')}
      onplaying={() => (mediaState = 'ready')}
      onseeked={() => (mediaState = audio && audio.readyState >= 3 ? 'ready' : mediaState)}
      onwaiting={() => (mediaState = 'buffering')}
      onstalled={() => (mediaState = 'buffering')}
      onerror={() => {
        mediaState = 'error'
        flash('The audio file could not be loaded. The signed URL may have expired — reload the page.', 'error')
      }}
    ></audio>

    <!-- Floating, so a mark's confirmation never reflows the page under a
         finger already on its way to the next transport button. -->
    {#if status}
      <div class="sg-toast" class:is-error={statusKind === 'error'} role="status" aria-live="polite">
        <span>{status}</span>
        {#if statusKind === 'error'}
          <button type="button" class="sg-toast-x" onclick={() => (status = '')} aria-label="Dismiss">×</button>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .sg {
    max-width: 1500px;
    margin: 0 auto;
    padding: 0 4px 24px;
    /* No double-tap zoom anywhere in the tool. The transport buttons are tapped
       in quick succession -- three −5s in a row is an ordinary thing to do --
       and every other pair of them was being read as a double-tap and zooming
       the page instead. `manipulation` drops that gesture only: panning and
       PINCH zoom still work, which matters on a page whose whole content is a
       waveform you sometimes want a closer look at. (The canvases set their own
       `pan-y`, which already excludes double-tap zoom.) */
    touch-action: manipulation;
  }
  .sg-head {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 10px;
  }
  .sg-head h1 {
    font-size: 1.25rem;
    margin: 0;
  }
  .sg-sub {
    margin: 2px 0 0;
    font-size: 0.82rem;
    color: var(--disabled-text, #888);
  }
  .sg-progress {
    font-size: 0.85rem;
    color: var(--disabled-text, #888);
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
  .sg-progress strong {
    color: var(--text-color, #e0e0e0);
    font-size: 1.05rem;
  }
  .sg-saving {
    color: var(--warning, #f5c842);
  }
  /* Sits between the count and the export link, so it reads as part of the same
     header cluster rather than as a control on the tool itself. */
  .sg-editlog {
    background: var(--header-bg, #2d2d2d);
    color: var(--text-color, #e0e0e0);
    border: 1px solid var(--border-color, #444);
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 32px;
    font-size: 0.82rem;
    cursor: pointer;
  }
  .sg-editlog:hover {
    background: var(--hover-bg, #3d3d3d);
  }
  .sg-error {
    background: rgba(232, 90, 90, 0.15);
    border: 1px solid var(--danger, #e85a5a);
    border-radius: 5px;
    padding: 8px 10px;
    margin: 0 0 10px;
  }
  /* The running commentary -- which tune just landed where -- as a toast rather
     than a band in the flow. Inline, it added a line to the top of the page on
     every mark, which slid the transport buttons down exactly as a thumb was
     arriving at one: you would mark a tune, reach for +15s, and press Undo.
     Fixed and top-centre, matching the site's own flash messages. */
  .sg-toast {
    position: fixed;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: var(--z-toast, 9999);
    max-width: min(420px, calc(100vw - 24px));
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border: 1px solid var(--border-color, #444);
    border-radius: 8px;
    background: var(--header-bg, #2d2d2d);
    color: var(--info, #5b99ea);
    font-size: 0.85rem;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.45);
    /* Never eats a tap meant for what it is floating over. */
    pointer-events: none;
    animation: sg-toast-in 0.15s ease-out;
  }
  .sg-toast.is-error {
    color: var(--danger, #e85a5a);
    border-color: var(--danger, #e85a5a);
  }
  /* Errors stay put until they are replaced or dismissed, so they get the one
     piece of the toast you can actually hit. */
  .sg-toast-x {
    pointer-events: auto;
    background: none;
    border: 0;
    color: inherit;
    font-size: 1.1rem;
    line-height: 1;
    padding: 0 2px;
    cursor: pointer;
  }
  @keyframes sg-toast-in {
    from {
      opacity: 0;
      transform: translate(-50%, -8px);
    }
  }

  .sg-body {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 340px;
    gap: 16px;
    align-items: start;
  }
  .sg-right {
    /* The log scrolls inside its own column so the waveform and the marking
       buttons never leave the screen during a long night. */
    max-height: calc(100vh - 190px);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .sg-right :global(.tl) {
    flex: 1 1 auto;
    min-height: 0;
  }

  .sg-clock {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-top: 8px;
  }
  .sg-time {
    font-family: var(--font-family-monospace, monospace);
    font-size: 1.45rem;
    color: var(--warning, #f5c842);
  }
  .sg-of {
    font-size: 0.78rem;
    color: var(--disabled-text, #888);
  }

  .sg-next {
    display: flex;
    align-items: baseline;
    gap: 9px;
    flex-wrap: wrap;
    padding: 8px 10px;
    margin: 8px 0;
    border: 1px solid var(--warning, #f5c842);
    background: rgba(245, 200, 66, 0.08);
    border-radius: 6px;
  }
  .sg-next-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--warning, #f5c842);
  }
  .sg-next-name {
    font-size: 1.05rem;
    font-weight: 600;
  }
  .sg-next-meta {
    font-size: 0.75rem;
    color: var(--disabled-text, #888);
  }

  .sg-controls {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .sg-controls button {
    flex: 1 1 auto;
    min-height: 44px;
    background: var(--header-bg, #2d2d2d);
    color: var(--text-color, #e0e0e0);
    border: 1px solid var(--border-color, #444);
    border-radius: 6px;
    font-size: 0.9rem;
    cursor: pointer;
  }
  .sg-controls button:hover {
    background: var(--hover-bg, #3d3d3d);
  }
  .sg-controls button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .sg-play {
    max-width: 90px;
    font-size: 1.05rem !important;
  }
  .sg-spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-color, #444);
    border-top-color: var(--warning, #f5c842);
    border-radius: 50%;
    animation: sg-spin 0.7s linear infinite;
    vertical-align: middle;
  }
  @keyframes sg-spin {
    to { transform: rotate(360deg); }
  }
  /* Respect a reduced-motion preference: still show the state, just don't spin. */
  @media (prefers-reduced-motion: reduce) {
    .sg-spinner { animation: none; }
  }
  .sg-loading {
    font-size: 0.78rem;
    color: var(--warning, #f5c842);
  }
  .sg-controls-main button {
    min-height: 52px;
    font-size: 0.95rem;
  }
  /* When M means "end the set", the banner and the button both switch to the
     end colour -- the mode is never something you have to remember. */
  .sg-next.is-ending {
    border-color: var(--info, #5b99ea);
    background: rgba(91, 153, 234, 0.1);
  }
  .sg-next.is-ending .sg-next-label {
    color: var(--info, #5b99ea);
  }
  .sg-mark.is-ending {
    border-color: var(--info, #5b99ea) !important;
    background: rgba(91, 153, 234, 0.16) !important;
  }
  .sg-mark {
    flex-grow: 3 !important;
    border-color: var(--warning, #f5c842) !important;
    background: rgba(245, 200, 66, 0.16) !important;
  }
  .sg-end {
    border-color: var(--info, #5b99ea) !important;
  }
  kbd {
    font-family: var(--font-family-monospace, monospace);
    font-size: 0.7rem;
    border: 1px solid var(--border-color, #444);
    border-radius: 3px;
    padding: 0 4px;
    margin-left: 5px;
    color: var(--disabled-text, #888);
  }

  .sg-opts {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    align-items: center;
    font-size: 0.8rem;
    color: var(--disabled-text, #888);
  }
  .sg-opt select {
    background: var(--header-bg, #2d2d2d);
    color: var(--text-color, #e0e0e0);
    border: 1px solid var(--border-color, #444);
    border-radius: 4px;
    padding: 3px 5px;
    margin-left: 4px;
  }
  .sg-opt-check {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .sg-keys {
    margin-top: 12px;
    font-size: 0.8rem;
    color: var(--disabled-text, #888);
  }
  .sg-keys summary {
    cursor: pointer;
  }
  .sg-keys dl {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 2px 14px;
    margin: 8px 0 0;
  }
  .sg-keys div {
    display: flex;
    gap: 8px;
  }
  .sg-keys dt {
    font-family: var(--font-family-monospace, monospace);
    color: var(--text-color, #e0e0e0);
    min-width: 74px;
  }
  .sg-keys dd {
    margin: 0;
  }

  /* Whose turn it is, folded into the mark button's row on a phone. Shrinks
     before the button does: the name can ellipsize, but a mark button that has
     to be aimed at is the wrong thing to make smaller. */
  .sg-next-inline {
    flex: 1 1 40%;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 1px;
    padding: 4px 8px;
    border: 1px solid var(--border-color, #444);
    border-left: 3px solid var(--warning, #f5c842);
    border-radius: 6px;
    text-align: left;
  }
  .sg-next-inline.is-ending {
    border-left-color: var(--info, #5b99ea);
  }
  .sg-next-inline .sg-next-label {
    font-size: 0.6rem;
  }
  .sg-next-inline .sg-next-name {
    font-size: 0.85rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sg-next-inline.is-ending .sg-next-label {
    color: var(--info, #5b99ea);
  }

  @media (max-width: 900px) {
    .sg-body {
      grid-template-columns: minmax(0, 1fr);
    }
    .sg-left {
      position: sticky;
      top: 0;
      z-index: 2;
      background: var(--bg-color, #1a1a1a);
      padding-bottom: 6px;
    }
    .sg-right {
      max-height: none;
    }
    .sg-keys {
      display: none;
    }
    /* The header is one line on a phone: count, encode, Fix, export. */
    .sg-head {
      gap: 4px;
    }
    .sg-progress {
      gap: 8px;
      font-size: 0.8rem;
    }
    .sg-progress .sg-opt-audio select {
      margin-left: 3px;
      padding: 2px 3px;
      font-size: 0.75rem;
      max-width: 96px;
    }
    .sg-editlog {
      padding: 4px 8px;
      min-height: 28px;
    }
    /* Undo is an icon here: it is one of three things competing for a row that
       also has to hold the mark button and whose turn it is. */
    .sg-undo {
      flex: 0 0 auto !important;
      min-width: 48px;
      font-size: 1.15rem !important;
    }
  }

  /*
   * Phone: the tape and its controls hold the top of the screen, and only the
   * log scrolls under them.
   *
   * Sticky was not enough. A sticky block only stays put while the page has
   * somewhere to put it, and this one is most of a phone screen -- so scrolling
   * the log inevitably pushed the header and the top of the tape (where the
   * drag handles are) out of view, and getting them back meant scrolling the
   * log all the way home. Making the page itself unscrollable and giving the
   * log its own overflow is the only arrangement where "scroll the list" and
   * "keep the controls" are not the same gesture.
   *
   * Guarded on height: a phone in landscape cannot fit the tape, the transport
   * and the mark row in ~375px, and pinning a block taller than the viewport
   * would clip the mark button with no way to scroll to it. There the page goes
   * back to scrolling as a whole, which is worse but never unusable.
   */
  @media (max-width: 900px) and (min-height: 500px) {
    :global(html),
    :global(body) {
      overflow: hidden;
    }
    .sg {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      padding-bottom: 0;
      height: calc(100vh - var(--sg-top, 60px));
      /* dvh, so the phone's collapsing URL bar doesn't leave the mark button
         under the fold or a dead strip below the log. */
      height: calc(100dvh - var(--sg-top, 60px));
    }
    .sg-body {
      flex: 1 1 auto;
      min-height: 0;
      grid-template-rows: auto minmax(0, 1fr);
      align-items: stretch;
    }
    .sg-left {
      /* Nothing to stick to any more: it is simply the top of a fixed column. */
      position: static;
      padding-bottom: 4px;
    }
    .sg-right {
      min-height: 0;
    }
  }
</style>
