<script>
  // i18n-converted
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
  import TunePicker from './TunePicker.svelte'
  import {
    edgeLimits,
    formatTime,
    isGuess,
    needsCheck,
    nextNeedingCheck,
    nextUnplacedIndex,
    resolveSegments,
    snapToOnset,
    SPEEDS,
    timeFromHash,
    ZOOM_LEVELS,
  } from './logic.js'
  import { t, tn } from '../lib/index.js'

  let { pageData = null } = $props()

  const recording = $derived(pageData?.recording ?? null)
  const instance = $derived(pageData?.session_instance ?? null)

  // Offline (spec 050 "Offline"): the app-wide store in static/js/segmenter_offline.js
  // -- a write queue for marks, a mirror of the working copy, and saved audio.
  // Without it (an older shell, or the component tests) the tool behaves exactly
  // as it always did: straight writes, streamed audio.
  const offline = typeof window !== 'undefined' ? (window.SegmenterOffline ?? null) : null
  let queued = $state(0)
  // Server timestamp of the payload the working copy was built from; the mirror
  // carries it so a later load can tell a stale page snapshot from local truth.
  // svelte-ignore state_referenced_locally
  let baseGeneratedAt = pageData?.generated_at ?? null
  // Saved encodes by source id: {url: blob:, size_bytes, saved_at}. A saved copy
  // is what plays with no signal, and it beats streaming on any signal.
  let local = $state({})
  // The <audio> gets no src until the saved copies have been looked up: pointing
  // it at a presigned URL first, offline, is an error toast for nothing.
  let localChecked = $state(!offline)
  let download = $state(null) // {source_id, loaded, total, abort} while saving audio

  // A deliberate one-time snapshot, not a mirror: `tunes` is the working copy the
  // operator edits, and pageData is a server-embedded blob that never changes
  // after mount. Re-deriving it would throw away every unsaved mark.
  // svelte-ignore state_referenced_locally
  let tunes = $state((pageData?.tunes ?? []).map((t) => ({ ...t })))
  // Which logged tune the mark key places next. -1 means NONE: every tune in
  // the log is placed (or there is no log), and a mark logs a new tune instead
  // (spec 050 "Logging while segmenting").
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
  const cursorTune = $derived(cursorIndex >= 0 ? tunes[cursorIndex] ?? null : null)
  // Logging from the audio: the mark key writes a new tune into the log.
  const appendMode = $derived(cursorTune == null && pendingSetEndIndex == null)
  const GAN_AINM = 'Gan Ainm'
  let picker = $state(null) // the TunePicker instance
  let revealId = $state(null) // the row the log should scroll to (a tune just logged)
  let pickerOpen = $state(false)
  const searchConfig = $derived({ sessionInstanceId: instance?.session_instance_id })
  const mediaBusy = $derived(mediaState === 'loading' || mediaState === 'buffering')
  const audioSources = $derived(recording?.audio_sources ?? [])
  const currentSource = $derived(audioSources.find((s) => s.id === sourceId) ?? audioSources[0] ?? null)
  const audioSrc = $derived(!localChecked ? '' : (local[sourceId]?.url ?? currentSource?.url ?? ''))
  const mb = (bytes) => Math.round((bytes ?? 0) / 1e6)

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

  // A link can name the moment to open at: #t=1:25:20 (logic.timeFromHash).
  // It outranks the remembered spot, which is about a round trip, not a link.
  function linkedTime() {
    const ms = timeFromHash(window.location.hash)
    return ms == null ? null : Math.min(durationMs, Math.max(0, ms))
  }

  function goToLinkedTime() {
    const ms = linkedTime()
    if (ms == null) return
    if (audio && audio.readyState >= 1) seek(ms)
    else {
      pendingSeekMs = ms
      currentMs = ms
    }
    flash(t('At {time}, from the link', { time: formatTime(ms) }))
  }

  onMount(() => {
    const linked = linkedTime()
    // Taken either way, so a link's visit also uses up the round trip's mark
    // rather than leaving it to yank some later visit back.
    const resumeAt = takeResumeMark()
    if (linked != null) {
      pendingSeekMs = linked
      currentMs = linked
      flash(t('At {time}, from the link', { time: formatTime(linked) }))
    } else if (resumeAt != null) {
      // Paint the waveform at the remembered spot immediately -- the peaks are
      // already here, so the tape is back in place long before the audio is.
      pendingSeekMs = resumeAt
      currentMs = resumeAt
      flash(t('Back where you left off'))
    }
    cursorIndex = nextUnplacedIndex(tunes, 0)
    // On a warm cache the element can already be playable before the handlers
    // above are bound, and then no event ever fires to clear the spinner --
    // and no loadedmetadata either, so a pending restore has to be applied here.
    if (audio && audio.readyState >= 1) applyPendingSeek()
    if (audio && audio.readyState >= 3) mediaState = 'ready'
    loadPeaks()
    initOffline()
    window.addEventListener('segmenter-synced', onSynced)
    // another #t= link to this recording, opened in the same tab
    window.addEventListener('hashchange', goToLinkedTime)
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
      window.removeEventListener('segmenter-synced', onSynced)
      window.removeEventListener('hashchange', goToLinkedTime)
      download?.abort?.abort()
      for (const copy of Object.values(local)) URL.revokeObjectURL(copy.url)
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
      flash(t('Could not load the waveform: {error}', { error: err.message }), 'error')
    }
  }

  // ---- offline ---------------------------------------------------------------
  //
  // The page the service worker hands back offline is a snapshot of the LAST
  // ONLINE LOAD, so its embedded marks can be an evening out of date. The mirror
  // is written after every change and carries the server timestamp of the
  // payload it grew from; whichever of the two is newer is the working copy, and
  // the queue is overlaid on it either way (idempotent: every op is the final
  // state of one tune).

  function applyOp(list, op) {
    const i = list.findIndex((t) => t.session_instance_tune_id === op.session_instance_tune_id)
    if (i < 0) return
    list[i] = {
      ...list[i],
      segment:
        op.kind === 'delete'
          ? null
          : {
              ...(list[i].segment ?? {}),
              session_instance_tune_id: op.session_instance_tune_id,
              start_ms: op.start_ms,
              end_ms: op.end_ms ?? null,
              pending: true,
            },
    }
  }

  async function initOffline() {
    if (!offline || !recording) return
    try {
      const [mirror, queue, saved] = await Promise.all([
        offline.mirrorGet(recording.recording_id),
        offline.pending(recording.recording_id),
        offline.audioList(recording.recording_id),
      ])
      const embedAt = pageData?.generated_at ?? null
      // Both stamps come from the server clock, so the comparison is safe; equal
      // means the same payload, and then the mirror has the edits made since.
      const mirrorWins = !!(mirror?.tunes && embedAt && mirror.generated_at && mirror.generated_at >= embedAt)
      const next = (mirrorWins ? mirror.tunes : tunes).map((t) => ({ ...t }))
      if (mirrorWins) baseGeneratedAt = mirror.generated_at
      for (const op of queue) applyOp(next, op)
      tunes = next
      cursorIndex = nextUnplacedIndex(tunes, 0)
      queued = queue.length
      await persistMirror()

      const copies = {}
      for (const entry of saved) {
        copies[entry.source_id] = {
          url: URL.createObjectURL(entry.blob),
          size_bytes: entry.size_bytes,
          saved_at: entry.saved_at,
        }
      }
      local = copies
      // A saved copy outranks the remembered encode: it is the one that works
      // with no signal, and it costs nothing on any signal.
      if (!copies[sourceId]) {
        const savedId = audioSources.map((s) => s.id).find((id) => copies[id])
        if (savedId) sourceId = savedId
      }
    } catch (err) {
      // No IndexedDB (private mode, quota): the tool still works online.
      console.warn('segmenter: offline store unavailable', err)
    } finally {
      localChecked = true
    }
  }

  async function persistMirror() {
    if (!offline || !recording) return
    try {
      await offline.mirrorPut(recording.recording_id, { generated_at: baseGeneratedAt, tunes: $state.snapshot(tunes) })
    } catch {
      // Best-effort: a mirror that fails to write costs offline reopening, not marks.
    }
  }

  async function refreshQueued() {
    if (!offline || !recording) return
    try {
      queued = (await offline.pending(recording.recording_id)).length
    } catch {
      // Keep the last count.
    }
  }

  // The queue drained -- from this page or any other. The server now holds every
  // mark it accepted, so adopt its picture rather than the optimistic one, and
  // say so if it refused any.
  async function onSynced(event) {
    if (!recording) return
    const detail = event?.detail ?? {}
    if (Array.isArray(detail.recording_ids) && !detail.recording_ids.includes(recording.recording_id)) return
    const refused = (detail.rejected ?? []).filter((r) => r.recording_id === recording.recording_id)
    try {
      const res = await fetch(`/api/recordings/${recording.recording_id}/segmenter`, {
        credentials: 'same-origin',
        cache: 'no-store',
      })
      const body = await res.json()
      if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
      const cursorId = cursorTune?.session_instance_tune_id ?? null
      tunes = (body.tunes ?? []).map((t) => ({ ...t }))
      baseGeneratedAt = body.generated_at ?? baseGeneratedAt
      const at = tunes.findIndex((t) => t.session_instance_tune_id === cursorId)
      cursorIndex = at >= 0 ? at : nextUnplacedIndex(tunes, 0)
      await refreshQueued()
      await persistMirror()
      if (refused.length) {
        flash(
          tn(refused.length, 'Synced, but {n} mark could not be saved: {error}', 'Synced, but {n} marks could not be saved: {error}', {
            error: refused[0].error,
          }),
          'error'
        )
      } else {
        const n = detail.recording_ids?.length === 1 ? detail.cleared : null
        flash(n ? tn(n, 'Synced {n} queued mark', 'Synced {n} queued marks') : t('Synced your queued marks'))
      }
    } catch (err) {
      flash(t('Synced, but could not refresh the log: {error}', { error: err.message }), 'error')
    }
  }

  // Keep this encode on the device. The presigned URL is fetched in full and the
  // bytes stored as a Blob; from then on the element plays a blob: URL, which
  // seeks natively and never expires.
  async function saveOffline() {
    if (!offline || !recording || !currentSource || download) return
    const source = currentSource
    const abort = typeof AbortController !== 'undefined' ? new AbortController() : null
    download = { source_id: source.id, loaded: 0, total: source.size_bytes ?? 0, abort }
    try {
      const entry = await offline.saveAudio(recording.recording_id, source, {
        signal: abort?.signal,
        onProgress: ({ loaded, total }) => {
          if (download) download = { ...download, loaded, total: total || download.total }
        },
      })
      local = {
        ...local,
        [source.id]: { url: URL.createObjectURL(entry.blob), size_bytes: entry.size_bytes, saved_at: entry.saved_at },
      }
      flash(t('Saved the {label} encode on this device ({n} MB) — the tool now works offline', { label: source.label, n: mb(entry.size_bytes) }))
      if (sourceId === source.id) await reloadAudioKeepingPlace()
    } catch (err) {
      if (err?.name === 'AbortError') flash(t('Download cancelled'))
      else flash(t('Could not save the audio: {error}', { error: err.message }), 'error')
    } finally {
      download = null
    }
  }

  async function forgetOffline(id = sourceId) {
    if (!offline || !recording || !local[id]) return
    const held = local[id]
    try {
      await offline.audioDelete(recording.recording_id, id)
      const rest = { ...local }
      delete rest[id]
      local = rest
      if (id === sourceId) await reloadAudioKeepingPlace()
      URL.revokeObjectURL(held.url)
      flash(t('Removed the offline copy'))
    } catch (err) {
      flash(t('Could not remove the offline copy: {error}', { error: err.message }), 'error')
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
      audio.play().catch((err) => flash(t('Playback failed: {error}', { error: err.message }), 'error'))
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
    sourceId = id
    try {
      window.localStorage.setItem(SOURCE_PREF_KEY, id)
    } catch {
      // Not being able to remember the choice is not worth failing the switch.
    }
    await reloadAudioKeepingPlace()
  }

  // Reload the element after its src has changed -- a different encode, or the
  // same one now coming from a saved copy -- without losing the spot.
  async function reloadAudioKeepingPlace() {
    if (!audio) return
    const resumeAt = audio.currentTime
    const wasPlaying = !audio.paused
    mediaState = 'loading'
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
    const start_ms = Math.round(startMs)
    const end_ms = endMs == null ? null : Math.round(endMs)
    try {
      if (offline) {
        // Through the queue: a network failure parks the op and resolves
        // {queued}, a server refusal throws (and rolls the mark back, below).
        const result = await offline.submit({
          recording_id: recording.recording_id,
          session_instance_tune_id: tune.session_instance_tune_id,
          kind: 'put',
          start_ms,
          end_ms,
        })
        if (result.queued) {
          await refreshQueued()
          return { session_instance_tune_id: tune.session_instance_tune_id, start_ms, end_ms, pending: true }
        }
        return result.data.segment
      }
      const res = await fetch(
        `/api/recordings/${recording.recording_id}/segments/${tune.session_instance_tune_id}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ start_ms, end_ms }),
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
      flash(t('Could not save "{name}": {error}', { name: tune.name, error: err.message }), 'error')
    }
    persistMirror()
  }

  /**
   * The tune waiting on an explicit end, or null.
   *
   * True exactly when the previous log entry closed a set, has been placed, and
   * hasn't been ended yet — i.e. the moment right after marking a set's last
   * tune, when the only sensible next act is to say where that set stopped.
   */
  const pendingSetEndIndex = $derived.by(() => {
    const prev = cursorIndex >= 0 ? cursorIndex - 1 : tunes.length - 1
    const tune = prev >= 0 ? tunes[prev] : null
    if (!tune?.segment) return null
    if (!tune.is_set_end || tune.segment.end_ms != null) return null
    // The last tune in the log is always "the end of its set" -- but when the
    // tool logged that tune itself, nothing is known about what follows it, and
    // the next mark is far more often the next tune of the SAME set than the
    // end. The End-set button (E) is the explicit way to close it.
    if (prev === tunes.length - 1 && tune.source === 'segmenter') return null
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
    const ms = snapEnabled ? snapToOnset(peaks, recording.peaks_hz, currentMs) : currentMs
    if (!cursorTune) {
      logNewTune(ms)
      return
    }
    const name = cursorTune.name
    place(cursorIndex, ms, cursorTune.segment?.end_ms ?? null)
    // Past the last tune the cursor goes to NONE rather than sticking on the
    // last row: from there a mark logs a new tune.
    cursorIndex = cursorIndex + 1 < tunes.length ? cursorIndex + 1 : -1

    // Say when snap moved the mark. It used to move silently, which reads as
    // the tool ignoring where you put the playhead -- and leaves you with no
    // hint that S would turn it off.
    const shift = ms - currentMs
    if (Math.abs(shift) >= 60) {
      const dir = shift > 0 ? '+' : '−'
      flash(
        t('{name} at {time} (snapped {shift}s — S to turn off)', {
          name,
          time: formatTime(ms, { millis: true }),
          shift: `${dir}${(Math.abs(shift) / 1000).toFixed(2)}`,
        })
      )
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
      flash(t('No placed tune before the playhead to end.'), 'info')
      return
    }
    markEndAt(tunes.findIndex((t) => t.session_instance_tune_id === targetId))
  }

  function markEndAt(index) {
    const tune = tunes[index]
    if (!tune?.segment) return
    if (currentMs <= tune.segment.start_ms) {
      flash(t('The end has to come after the start.'), 'error')
      return
    }
    place(index, tune.segment.start_ms, currentMs)
    flash(t('Ended "{name}" at {time}', { name: tune.name, time: formatTime(currentMs) }))
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
    status =
      edge === 'start'
        ? t('{name} starts {time}', { name: tune.name, time: formatTime(at, { millis: true }) })
        : t('{name} ends {time}', { name: tune.name, time: formatTime(at, { millis: true }) })
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
    flash(
      edge === 'start'
        ? t('Moved "{name}" start to {time} — U to undo', { name: tune.name, time: formatTime(moved.start_ms, { millis: true }) })
        : t('Moved "{name}" end to {time} — U to undo', { name: tune.name, time: formatTime(moved.end_ms, { millis: true }) })
    )
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
      if (offline) {
        const result = await offline.submit({
          recording_id: recording.recording_id,
          session_instance_tune_id: tune.session_instance_tune_id,
          kind: 'delete',
        })
        if (result.queued) await refreshQueued()
      } else {
        const res = await fetch(
          `/api/recordings/${recording.recording_id}/segments/${tune.session_instance_tune_id}`,
          { method: 'DELETE', credentials: 'same-origin' },
        )
        const body = await res.json()
        if (!res.ok || !body.success) {
          const err = new Error(body.error || `HTTP ${res.status}`)
          err.status = res.status
          throw err
        }
      }
    } catch (err) {
      // "No segment for that tune" is the state being asked for: the mark only
      // ever lived in the queue, and the server never saw it.
      if (err?.status !== 404) {
        tunes[index] = { ...tunes[index], segment: previous }
        if (moveCursor) cursorIndex = previousCursor
        flash(t('Could not clear "{name}": {error}', { name: tune.name, error: err.message }), 'error')
      }
    } finally {
      saving -= 1
    }
    persistMirror()
  }

  async function undo() {
    const step = undoStack.pop()
    if (!step) {
      flash(t('Nothing to undo.'), 'info')
      return
    }
    if (step.kind === 'log') {
      // The mark logged a tune: undoing it takes the tune back out of the log.
      const index = tunes.findIndex((t) => t.session_instance_tune_id === step.sitId)
      if (index >= 0) await unlogAt(index, false)
      cursorIndex = step.cursor
      flash(t('Undid that tune'))
      return
    }
    cursorIndex = step.cursor
    if (step.previous) {
      await place(step.index, step.previous.start_ms, step.previous.end_ms)
      undoStack.pop() // place() pushed its own entry; the undo itself isn't undoable
    } else {
      await clearAt(step.index)
    }
    flash(t('Undid "{name}"', { name: tunes[step.index]?.name ?? t('that mark') }))
  }

  // ---- logging while segmenting -------------------------------------------
  //
  // A night nobody wrote down still has audio worth timestamping. Once every
  // logged tune is placed -- or there was never a log -- the mark key logs a
  // NEW tune, unidentified ("Gan Ainm"), placed where the playhead is, in the
  // same call. The server decides its set from the audio: it joins the set of
  // the placed tune before it when that tune's end is implicit (they abut),
  // and opens a new set when that end was marked with End-set. Tapping the
  // tune's name in the log opens the live logger's own search to say which
  // tune it was. All three writes return the whole list, because inserting a
  // tune can renumber every set after it.

  function adoptTunes(list, keepCursorId = null) {
    tunes = (list ?? []).map((t) => ({ ...t }))
    if (keepCursorId != null) {
      const at = tunes.findIndex((t) => t.session_instance_tune_id === keepCursorId)
      cursorIndex = at >= 0 ? at : nextUnplacedIndex(tunes, 0)
    }
  }

  async function logNewTune(ms) {
    if (!recording) return
    const startMs = Math.round(ms)
    saving += 1
    try {
      const res = await fetch(`/api/recordings/${recording.recording_id}/segments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ start_ms: startMs, end_ms: null }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
      adoptTunes(body.tunes)
      cursorIndex = -1 // the next mark logs the next tune
      revealId = body.tune?.session_instance_tune_id ?? null
      undoStack.push({ kind: 'log', sitId: body.tune?.session_instance_tune_id, cursor: -1 })
      flash(t('{name} at {time} — tap it in the log to name it', { name: GAN_AINM, time: formatTime(startMs) }))
    } catch (err) {
      const offlineNow = err instanceof TypeError
      flash(offlineNow ? t('Logging a new tune needs a connection.') : t('Could not log a tune: {error}', { error: err.message }), 'error')
    } finally {
      saving -= 1
    }
    persistMirror()
  }

  // A machine's guesses (spec 053): the truly uncertain ones the listener logged
  // (shown at 80% or under) that nobody has confirmed or corrected yet, the
  // filter that shows only those, and the way from one to the next.
  let onlyChecks = $state(false)
  const checksLeft = $derived(tunes.filter(needsCheck).length)

  /** Put the cursor on the next (or previous) tune needing a check, and go to it. */
  function jumpToCheck(step = 1) {
    const i = nextNeedingCheck(tunes, cursorIndex >= 0 ? cursorIndex : step > 0 ? -1 : tunes.length, step)
    if (i < 0) {
      flash(t('Every tune here has been checked.'))
      return
    }
    cursorIndex = i
    jumpToCursor()
  }

  async function confirmAt(index) {
    const tune = tunes[index]
    if (!tune || !recording || !isGuess(tune)) return
    saving += 1
    try {
      const res = await fetch(
        `/api/recordings/${recording.recording_id}/segments/${tune.session_instance_tune_id}/confirm`,
        { method: 'POST', credentials: 'same-origin' },
      )
      const body = await res.json().catch(() => ({}))
      if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
      adoptTunes(body.tunes, cursorTune?.session_instance_tune_id ?? null)
      flash(t('Confirmed "{name}"', { name: tune.name }))
    } catch (err) {
      flash(t('Could not confirm "{name}": {error}', { name: tune.name, error: err.message }), 'error')
    } finally {
      saving -= 1
    }
    persistMirror()
  }

  async function unlogAt(index, moveCursor = true) {
    const tune = tunes[index]
    if (!tune || !recording) return
    saving += 1
    try {
      const res = await fetch(
        `/api/recordings/${recording.recording_id}/segments/${tune.session_instance_tune_id}/unlog`,
        { method: 'POST', credentials: 'same-origin' },
      )
      const body = await res.json().catch(() => ({}))
      if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
      const cursorId = cursorTune?.session_instance_tune_id ?? null
      adoptTunes(body.tunes, cursorId)
      if (moveCursor) flash(t('Removed "{name}" from the log', { name: tune.name }))
    } catch (err) {
      flash(t('Could not remove "{name}": {error}', { name: tune.name, error: err.message }), 'error')
    } finally {
      saving -= 1
    }
    persistMirror()
  }

  // The type the search should favour: what the rest of this tune's set is,
  // when the set agrees on one -- the same rule the live logger's composer
  // uses (cursorSetType), so a reel's neighbours come up reels first.
  function setTypeAround(index) {
    const tune = tunes[index]
    if (!tune) return null
    const types = new Set(
      tunes
        .filter((t) => t.set_number === tune.set_number && t.session_instance_tune_id !== tune.session_instance_tune_id)
        .map((t) => t.tune_type)
        .filter(Boolean),
    )
    return types.size === 1 ? [...types][0] : null
  }

  // Name (or rename) a tune: the picker over the log, seeded with the name the
  // row already has when that name is worth searching for -- a tune logged on
  // the night that matched nothing, or a linked tune being corrected. The
  // tool's own placeholder seeds nothing.
  function openPicker(index) {
    const tune = tunes[index]
    if (!tune || !picker) return
    pickerOpen = true
    picker.open(
      { kind: 'name', tune },
      {
        preferType: setTypeAround(index),
        initialQuery: tune.name && tune.name !== GAN_AINM ? tune.name : '',
      },
    )
  }

  // Add a tune next to a row (the row menu's "before" / "after"), or open a new
  // set after one (the + between sets; `newSet`). The picker asks which tune
  // first, so cancelling leaves no placeholder behind; the row it makes is
  // unplaced and becomes the cursor, so the next mark places it. With no anchor
  // (an empty log) the tune simply starts the log.
  function openInsertPicker(where) {
    if (!picker) return
    const anchor = where.index != null ? tunes[where.index] : null
    const preferType = where.index != null && !where.newSet ? setTypeAround(where.index) : null
    pickerOpen = true
    picker.open(
      { kind: 'insert', anchorId: anchor?.session_instance_tune_id ?? null, side: where.side, newSet: !!where.newSet },
      { preferType, title: where.newSet ? t('Start a new set with…') : t('Add a tune'), actionLabel: t('＋ Add This Tune') },
    )
  }

  function onPick(target, payload) {
    return target.kind === 'insert' ? insertTune(target, payload) : nameTune(target.tune, payload)
  }

  async function insertTune(target, payload) {
    const body = { ...payload, new_set: target.newSet }
    if (target.anchorId != null) {
      body[target.side === 'before' ? 'before_record_id' : 'after_record_id'] = target.anchorId
    }
    const res = await fetch(`/api/recordings/${recording.recording_id}/segments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    })
    const resBody = await res.json().catch(() => ({}))
    if (!res.ok || !resBody.success) throw new Error(resBody.error || `HTTP ${res.status}`)
    const previousCursor = cursorIndex
    const newId = resBody.tune?.session_instance_tune_id ?? null
    adoptTunes(resBody.tunes, newId)
    revealId = newId
    undoStack.push({ kind: 'log', sitId: newId, cursor: previousCursor })
    const name = resBody.tune?.name ?? t('that tune')
    flash(
      resBody.setting_failed
        ? t('Added "{name}" (setting not saved: {error}) — M places it', { name, error: resBody.setting_failed })
        : t('Added "{name}" — M places it at the playhead', { name }),
    )
    persistMirror()
    return true
  }

  // The picker's pick: TuneSearch's own payload (tune_id, or thesession_id for
  // an import, or just a typed name for "log as-is", plus a chosen setting),
  // written onto the tune being named. Resolves false to keep the pane open.
  async function nameTune(tune, payload) {
    const res = await fetch(
      `/api/recordings/${recording.recording_id}/segments/${tune.session_instance_tune_id}/tune`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      },
    )
    const body = await res.json().catch(() => ({}))
    if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
    const cursorId = cursorTune?.session_instance_tune_id ?? null
    adoptTunes(body.tunes, cursorId)
    flash(
      body.setting_failed
        ? t('Named it "{name}" (setting not saved: {error})', { name: body.tune?.name, error: body.setting_failed })
        : t('Named it "{name}"', { name: body.tune?.name })
    )
    persistMirror()
    return true
  }

  function moveCursor(delta) {
    if (!tunes.length) return
    // From NONE, up steps onto the last row; down stays at NONE.
    const from = cursorIndex >= 0 ? cursorIndex : tunes.length
    const next = from + delta
    cursorIndex = next >= tunes.length ? -1 : Math.max(0, next)
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
    // The picker owns the keyboard while it is up -- typing a tune name must
    // not scrub the audio -- except Escape, which closes it from anywhere.
    if (pickerOpen) {
      if (event.key === 'Escape') picker?.close()
      return
    }
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
        flash(snapEnabled ? t('Onset snap on') : t('Onset snap off'))
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
      case 'n':
        jumpToCheck(1)
        break
      case 'N':
        jumpToCheck(-1)
        break
      case 'c':
      case 'C':
        if (cursorIndex >= 0) confirmAt(cursorIndex)
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
      {#if !compact}{t('audio')}{/if}
      <select value={sourceId} onchange={(e) => switchSource(e.currentTarget.value)}>
        {#each audioSources as src (src.id)}
          <option value={src.id}>
            {src.label}{src.size_bytes && !compact ? ` · ${t('{n} MB', { n: mb(src.size_bytes) })}` : ''}{local[src.id] ? ' ✓' : ''}
          </option>
        {/each}
      </select>
    </label>
  {/if}
{/snippet}

<!-- Keep the current encode on the device (spec 050 "Offline"). Sits next to
     the picker wherever that is rendered; shown even with a single encode,
     since one source is still one worth keeping. -->
{#snippet offlineAudio()}
  {#if offline && currentSource}
    {#if download}
      <span class="sg-opt sg-offline is-busy" role="status">
        {t('saving {progress}', {
          progress: download.total
            ? `${Math.min(99, Math.round((download.loaded / download.total) * 100))}%`
            : t('{n} MB', { n: mb(download.loaded) }),
        })}
        <button type="button" class="sg-offline-x" onclick={() => download?.abort?.abort()} aria-label={t('Cancel the download')}>×</button>
      </span>
    {:else if local[sourceId]}
      <span class="sg-opt sg-offline is-saved" title={t('Saved on this device ({n} MB) — plays with no connection', { n: mb(local[sourceId].size_bytes) })}>
        {compact ? t('saved') : `${t('offline')} ✓`}
        <button type="button" class="sg-offline-x" onclick={() => forgetOffline()} aria-label={t('Remove the offline copy')} title={t('Remove the offline copy')}>×</button>
      </span>
    {:else}
      <button
        type="button"
        class="sg-opt sg-offline"
        onclick={saveOffline}
        title={t('Download this encode to the device so the tool works with no connection')}
      >⤓ {compact ? t('offline') : t('save offline')}{#if currentSource.size_bytes && !compact} · {t('{n} MB', { n: mb(currentSource.size_bytes) })}{/if}</button>
    {/if}
  {/if}
{/snippet}

{#if !recording}
  <p class="sg-error">{t('No recording payload. Reload the page.')}</p>
{:else}
  <div class="sg" bind:this={rootEl} style="--sg-top: {topOffset}px">
    <header class="sg-head">
      <div>
        <h1>{recording.label || t('Recording')}</h1>
        <p class="sg-sub">
          <a href="/sessions/{instance.session_path}">{instance.session_name}</a>
          · {instance.date}
          · {formatTime(durationMs)}
          {#if recording.clock_offset_ms}· {t('offset {time}', { time: formatTime(recording.clock_offset_ms) })}{/if}
        </p>
      </div>
      <div class="sg-progress">
        <span class="sg-count"><strong>{placedCount}</strong> / {tunes.length}{#if !compact}{' ' + t('placed')}{/if}</span>
        <!-- Always in the DOM, merely invisible when idle. Appearing and
             disappearing on every mark rewrapped the header, which moved the
             whole page under a thumb already on its way to +15s. A dot on a
             phone, where the word would cost the header a line of its own. -->
        <span
          class="sg-saving"
          class:is-on={saving > 0 || queued > 0}
          class:is-queued={queued > 0}
          title={queued > 0 ? tn(queued, '{n} mark waiting to sync', '{n} marks waiting to sync') : t('saving')}
        >{#if queued > 0}{compact ? `${queued}⇡` : t('{n} queued', { n: queued })}{:else}{compact ? '•' : t('saving…')}{/if}</span>
        <!-- On a phone the encode switch rides up here with the other header
             controls: down in the options row it was one more line of the
             sticky column, and it is the one option you reach for when the
             connection changes rather than while marking. -->
        {#if compact}{@render audioPicker()}{@render offlineAudio()}{/if}
        <!-- Fix and export travel together: when the phone header wraps, they
             move to the next row as a pair rather than stranding "export". -->
        <span class="sg-actions">
          <button
            type="button"
            class="sg-editlog"
            onclick={editLog}
            title={t("Open this night's log in edit mode — you'll come back here, at this moment in the audio")}
          >✎ {compact ? t('Fix') : t('Fix the log')}</button>
          <a class="sg-export" href="/api/recordings/{recording.recording_id}/export" target="_blank" rel="noopener">{t('export')}</a>
        </span>
      </div>
    </header>

    {#if recording.audio_error}
      <p class="sg-error">{t('Audio unavailable: {error}', { error: recording.audio_error })}</p>
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
          <span class="sg-of">{t('of {time}', { time: formatTime(durationMs) })}</span>
          {#if mediaBusy}
            <span class="sg-loading">
              {mediaState === 'loading' ? t('loading audio…') : t('buffering…')}
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
              <span class="sg-next-label">{t('end of set {n}', { n: ending.set_number })}</span>
              <span class="sg-next-name">{ending.name}</span>
              <span class="sg-next-meta">{t('M marks where it stopped')}</span>
            </div>
          {:else}
            <div class="sg-next" class:is-logging={!cursorTune}>
              {#if cursorTune}
                <span class="sg-next-label">{t('next up')}</span>
                <span class="sg-next-name">{cursorTune.name}</span>
                <span class="sg-next-meta">{t('set {n}', { n: cursorTune.set_number })}{cursorTune.is_set_end ? ` · ${t('last of set')}` : ''}</span>
              {:else}
                <span class="sg-next-label">{t('log a tune')}</span>
                <span class="sg-next-name">{GAN_AINM}</span>
                <span class="sg-next-meta">{t('M logs a new tune starting here · E ends the set')}</span>
              {/if}
            </div>
          {/if}
        {/if}

        <div class="sg-controls">
          <button type="button" onclick={() => nudge(-15000)}>{t('−15s')}</button>
          <button type="button" onclick={() => nudge(-5000)}>{t('−5s')}</button>
          <button
            type="button"
            class="sg-play"
            onclick={togglePlay}
            aria-busy={mediaBusy}
            title={mediaBusy ? t('Audio still loading') : playing ? t('Pause') : t('Play')}
          >
            {#if mediaBusy}
              <span class="sg-spinner" aria-hidden="true"></span>
            {:else}
              {playing ? '❚❚' : '▶'}
            {/if}
          </button>
          <button type="button" onclick={() => nudge(5000)}>{t('+5s')}</button>
          <button type="button" onclick={() => nudge(15000)}>{t('+15s')}</button>
        </div>

        <div class="sg-controls sg-controls-main">
          <!-- Phone: the banner's job rides on the button's own row. Whose turn
               it is matters as much as the button does, and side by side they
               cost one row instead of two. No set number -- the list two
               inches below is already showing which set this is. -->
          {#if compact}
            {@const ending = pendingSetEndIndex != null ? tunes[pendingSetEndIndex] : null}
            <div class="sg-next-inline" class:is-ending={ending != null}>
              <span class="sg-next-label">{ending ? t('end of set') : cursorTune ? t('next up') : t('new tune')}</span>
              <span class="sg-next-name">{(ending ?? cursorTune)?.name ?? GAN_AINM}</span>
            </div>
          {/if}
          <button
            type="button"
            class="sg-mark"
            class:is-ending={pendingSetEndIndex != null}
            class:is-logging={appendMode}
            onclick={markStart}
          >
            {pendingSetEndIndex != null ? t('End of set') : appendMode ? t('Log a tune') : t('Mark start')}{#if !compact} <kbd>{'M'}</kbd>{/if}
          </button>
          <!-- The separate end key is for ending a set you have already scrolled
               past; the mark button covers the ordinary case on its own, by
               switching mode. On a phone that second button is a whole row for
               the rarer of the two, so the one that changes with you wins --
               except while logging from the audio, where the mark button never
               flips (the tool can't know a set's last tune) and this IS the
               only way to close a set. -->
          {#if !compact || appendMode}
            <button type="button" class="sg-end" onclick={markEnd}>{compact ? t('End set') : t('End of set')}{#if !compact} <kbd>{'E'}</kbd>{/if}</button>
          {/if}
          <button type="button" class="sg-undo" onclick={undo} title={t('Undo the last mark')} aria-label={t('Undo')}>
            {#if compact}↺{:else}{t('Undo')} <kbd>{'U'}</kbd>{/if}
          </button>
        </div>

        <div class="sg-opts">
          <label class="sg-opt">
            {t('speed')}
            <select value={speed} onchange={(e) => setSpeed(Number(e.currentTarget.value))}>
              {#each SPEEDS as s}<option value={s}>{s}×</option>{/each}
            </select>
          </label>
          <label class="sg-opt">
            {t('zoom')}
            <select value={zoomMs} onchange={(e) => (zoomMs = Number(e.currentTarget.value))}>
              {#each ZOOM_LEVELS as z}<option value={z}>{t('{n}s', { n: z / 1000 })}</option>{/each}
            </select>
          </label>
          <label class="sg-opt sg-opt-check">
            <input type="checkbox" bind:checked={snapEnabled} />
            {t('snap to onset')}
          </label>
          {#if !compact}{@render audioPicker()}{@render offlineAudio()}{/if}
        </div>

        <details class="sg-keys">
          <summary>{t('Keyboard')}</summary>
          <dl>
            <div><dt>{t('Space')}</dt><dd>{t('play / pause')}</dd></div>
            <div><dt>{'M'} · {t('Enter')}</dt><dd>{t('mark start of the next tune')}</dd></div>
            <div><dt>{'E'}</dt><dd>{t('explicit end (end of a set)')}</dd></div>
            <div><dt>{'U'} · ⌫</dt><dd>{t('undo the last mark')}</dd></div>
            <div><dt>← →</dt><dd>{t('seek 5s (⇧ 1s, ⌥ 0.2s)')}</dd></div>
            <div><dt>↑ ↓</dt><dd>{t('move the cursor in the log')}</dd></div>
            <div><dt>{'G'}</dt><dd>{t("go to the cursor tune's mark")}</dd></div>
            <div><dt>{'N'} · ⇧{'N'}</dt><dd>{t('next / previous tune needing a check')}</dd></div>
            <div><dt>{'C'}</dt><dd>{t('confirm the cursor tune')}</dd></div>
            <div><dt>− =</dt><dd>{t('zoom out / in')}</dd></div>
            <div><dt>[ ]</dt><dd>{t('slower / faster')}</dd></div>
            <div><dt>{'S'}</dt><dd>{t('toggle onset snap')}</dd></div>
            <div><dt>{t('drag an edge')}</dt><dd>{t('move a boundary in the tape (no snap — the drag is the correction)')}</dd></div>
          </dl>
        </details>
      </section>

      <section class="sg-right">
        {#if checksLeft || onlyChecks}
          <!-- The listener's guesses still to check: show only those, and step
               through them (N / ⇧N), confirming (C) or correcting each. -->
          <div class="sg-checks">
            <label>
              <input type="checkbox" bind:checked={onlyChecks} />
              {tn(checksLeft, '{n} tune needs a check', '{n} tunes need a check')}
            </label>
            <button type="button" title={t('Previous tune needing a check')} onclick={() => jumpToCheck(-1)} disabled={!checksLeft}>‹</button>
            <button type="button" title={t('Next tune needing a check')} onclick={() => jumpToCheck(1)} disabled={!checksLeft}>›</button>
          </div>
        {/if}
        <TuneList
          {tunes}
          {segments}
          {cursorIndex}
          onpick={(i) => (cursorIndex = i)}
          onseek={seek}
          onclear={(i) => clearAt(i, true)}
          onname={openPicker}
          onunlog={(i) => unlogAt(i)}
          onconfirm={(i) => confirmAt(i)}
          {onlyChecks}
          oninsert={(i, side) => openInsertPicker({ index: i, side })}
          onnewset={(i) => openInsertPicker({ index: i, side: 'after', newSet: true })}
          {revealId}
        />
      </section>
    </div>

    <!-- "Which tune was this?" -- the live logger's search, over the tool. The
         audio element below is untouched by it, so playback carries on. -->
    <TunePicker
      bind:this={picker}
      config={searchConfig}
      onPick={onPick}
      onClosed={() => (pickerOpen = false)}
    />

    <audio
      bind:this={audio}
      src={audioSrc || undefined}
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
      onstalled={() => {
        // `stalled` means "no new bytes for a few seconds", not "playback
        // stopped" -- Chrome fires it once a download goes quiet, which for a
        // saved copy (a blob: URL that loads in full at once) is straight away,
        // while playback carries on. Only a real shortage of data is buffering.
        if (audio && audio.readyState < 3) mediaState = 'buffering'
      }}
      ontimeupdate={() => {
        // Advancing time is proof the audio isn't buffering, whatever event
        // said so; nothing else re-fires while playback never actually paused.
        if (mediaState === 'buffering' && audio && !audio.paused) mediaState = 'ready'
      }}
      onerror={() => {
        mediaState = 'error'
        flash(
          local[sourceId]
            ? t('The saved audio could not be played. Remove the offline copy and save it again.')
            : offline
              ? t('The audio could not be loaded. Offline, the tool needs a copy saved on this device ("save offline" while connected); online, the signed URL may have expired — reload the page.')
              : t('The audio file could not be loaded. The signed URL may have expired — reload the page.'),
          'error',
        )
      }}
    ></audio>

    <!-- Floating, so a mark's confirmation never reflows the page under a
         finger already on its way to the next transport button. -->
    {#if status}
      <div class="sg-toast" class:is-error={statusKind === 'error'} role="status" aria-live="polite">
        <span>{status}</span>
        {#if statusKind === 'error'}
          <button type="button" class="sg-toast-x" onclick={() => (status = '')} aria-label={t('Dismiss')}>×</button>
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
  /* The fraction is one word: "40 /" on one line and "82" on the next is
     exactly the wrap a squeezed phone header produced. */
  .sg-count,
  .sg-editlog,
  .sg-export {
    white-space: nowrap;
  }
  .sg-actions {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
  }
  .sg-saving {
    color: var(--warning, #f5c842);
    visibility: hidden;
  }
  /* Logging from the audio: the banner and the mark button read as "new tune". */
  .sg-next.is-logging .sg-next-name {
    font-style: italic;
  }
  .sg-mark.is-logging {
    border-style: dashed;
  }
  .sg-saving.is-on {
    visibility: visible;
  }
  /* Marks parked in the offline queue: the same orange as the connection dot. */
  .sg-saving.is-queued {
    color: #e0a23e;
    font-weight: 600;
  }
  .sg-offline {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: var(--header-bg, #2d2d2d);
    color: var(--text-color, #e0e0e0);
    border: 1px solid var(--border-color, #444);
    border-radius: 4px;
    padding: 3px 7px;
    font: inherit;
    font-size: 0.82rem;
    cursor: pointer;
    white-space: nowrap;
  }
  button.sg-offline:hover {
    background: var(--hover-bg, #3d3d3d);
  }
  .sg-offline.is-saved {
    color: var(--success, #4caf50);
    cursor: default;
  }
  .sg-offline.is-busy {
    color: #e0a23e;
    cursor: default;
  }
  .sg-offline-x {
    background: none;
    border: 0;
    color: var(--disabled-text, #888);
    font-size: 1rem;
    line-height: 1;
    padding: 0 2px;
    cursor: pointer;
  }
  .sg-offline-x:hover {
    color: var(--danger, #e85a5a);
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
  .sg-checks {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85rem;
    color: #e0b341;
    padding: 2px 2px 6px;
  }
  .sg-checks label {
    display: flex;
    align-items: center;
    gap: 5px;
    margin: 0;
    flex: 1;
    cursor: pointer;
  }
  .sg-checks button {
    background: none;
    border: 1px solid var(--border-color, #444);
    border-radius: 5px;
    color: var(--text-color, #e0e0e0);
    padding: 0 8px;
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
    /* On a phone the controls get a row of their own under the title rather
       than squeezing in beside it, and that row wraps between controls,
       never inside one: count and queue on the left, the encode switch and
       the offline copy in the middle, Fix and export pushed to the right. */
    .sg-head {
      gap: 4px;
    }
    .sg-progress {
      flex: 1 0 100%;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px 8px;
      font-size: 0.8rem;
    }
    .sg-progress .sg-opt-audio select {
      margin-left: 0;
      padding: 2px 3px;
      font-size: 0.75rem;
      max-width: 118px;
    }
    .sg-progress .sg-actions {
      margin-left: auto;
    }
    .sg-progress .sg-offline {
      padding: 2px 5px;
      font-size: 0.75rem;
      gap: 3px;
    }
    .sg-progress .sg-actions {
      gap: 8px;
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
    /* Logging from the audio adds End-set to that row (it is the only way to
       close a set then), so all four have to fit: the banner gives up some of
       its share and End-set takes only what its label needs. */
    .sg-controls-main .sg-next-inline {
      /* Zero basis: the row divides what is left rather than wrapping on the
         sum of everyone's natural width. */
      flex: 1 1 0;
      padding-left: 6px;
      padding-right: 6px;
    }
    .sg-controls-main .sg-mark {
      flex: 1.3 1 0 !important;
      padding-left: 6px;
      padding-right: 6px;
      white-space: nowrap;
    }
    .sg-controls-main .sg-end {
      flex: 0 0 auto !important;
      padding: 0 10px;
      white-space: nowrap;
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
