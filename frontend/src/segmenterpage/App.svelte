<script>
  // Recording segmenter (spec 050): put start/end timestamps on the tunes already
  // logged against a night's audio, fast enough to do a three-hour session in one
  // sitting. The output is the training corpus for tune recognition.
  //
  // The interaction is one key. A cursor sits on the next tune in the log; find
  // where it starts in the audio, press M, cursor advances. Ends come free --
  // the next tune's start IS the previous tune's end -- so an explicit end is
  // only typed at the end of a set, where chatter follows.
  import { onMount } from 'svelte'
  import Waveform from './Waveform.svelte'
  import TuneList from './TuneList.svelte'
  import {
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

  const durationMs = $derived(recording?.duration_ms ?? 0)
  const segments = $derived(resolveSegments(tunes, durationMs))
  const placedCount = $derived(tunes.filter((t) => t.segment).length)
  const cursorTune = $derived(tunes[cursorIndex] ?? null)

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

  onMount(() => {
    cursorIndex = Math.max(0, nextUnplacedIndex(tunes, 0))
    loadPeaks()
    const tick = () => {
      if (audio && !scrubbing) currentMs = audio.currentTime * 1000
      raf = requestAnimationFrame(tick)
    }
    let raf = requestAnimationFrame(tick)
    window.addEventListener('keydown', onKeydown)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('keydown', onKeydown)
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

  function markStart() {
    if (!cursorTune) {
      flash('Every tune in the log is placed.', 'info')
      return
    }
    const ms = snapEnabled ? snapToOnset(peaks, recording.peaks_hz, currentMs) : currentMs
    place(cursorIndex, ms, cursorTune.segment?.end_ms ?? null)
    cursorIndex = Math.min(tunes.length - 1, cursorIndex + 1)
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
    const index = tunes.findIndex((t) => t.session_instance_tune_id === targetId)
    const tune = tunes[index]
    if (currentMs <= tune.segment.start_ms) {
      flash('The end has to come after the start.', 'error')
      return
    }
    place(index, tune.segment.start_ms, currentMs)
    flash(`Ended "${tune.name}" at ${formatTime(currentMs)}`)
  }

  async function clearAt(index) {
    const tune = tunes[index]
    if (!tune?.segment) return
    const previous = tune.segment
    tunes[index] = { ...tune, segment: null }
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

{#if !recording}
  <p class="sg-error">No recording payload. Reload the page.</p>
{:else}
  <div class="sg">
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
        <strong>{placedCount}</strong> / {tunes.length} placed
        {#if saving > 0}<span class="sg-saving">saving…</span>{/if}
        <a class="sg-export" href="/api/recordings/{recording.recording_id}/export" target="_blank" rel="noopener">export</a>
      </div>
    </header>

    {#if recording.audio_error}
      <p class="sg-error">Audio unavailable: {recording.audio_error}</p>
    {/if}
    {#if status}
      <p class="sg-status" class:is-error={statusKind === 'error'}>{status}</p>
    {/if}

    <div class="sg-body">
      <section class="sg-left">
        <Waveform
          {peaks}
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
        />

        <div class="sg-clock">
          <span class="sg-time">{formatTime(currentMs, { millis: true })}</span>
          <span class="sg-of">of {formatTime(durationMs)}</span>
        </div>

        <div class="sg-next">
          {#if cursorTune}
            <span class="sg-next-label">next up</span>
            <span class="sg-next-name">{cursorTune.name}</span>
            <span class="sg-next-meta">set {cursorTune.set_number}{cursorTune.is_set_end ? ' · last of set' : ''}</span>
          {:else}
            <span class="sg-next-label">log complete</span>
          {/if}
        </div>

        <div class="sg-controls">
          <button type="button" onclick={() => nudge(-15000)}>−15s</button>
          <button type="button" onclick={() => nudge(-5000)}>−5s</button>
          <button type="button" class="sg-play" onclick={togglePlay}>{playing ? '❚❚' : '▶'}</button>
          <button type="button" onclick={() => nudge(5000)}>+5s</button>
          <button type="button" onclick={() => nudge(15000)}>+15s</button>
        </div>

        <div class="sg-controls sg-controls-main">
          <button type="button" class="sg-mark" onclick={markStart} disabled={!cursorTune}>
            Mark start <kbd>M</kbd>
          </button>
          <button type="button" class="sg-end" onclick={markEnd}>End of set <kbd>E</kbd></button>
          <button type="button" onclick={undo}>Undo <kbd>U</kbd></button>
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
          onclear={clearAt}
        />
      </section>
    </div>

    <audio
      bind:this={audio}
      src={recording.audio_url}
      preload="metadata"
      onplay={() => (playing = true)}
      onpause={() => (playing = false)}
      onratechange={() => audio && (speed = audio.playbackRate)}
      onerror={() => flash('The audio file could not be loaded. The signed URL may have expired — reload the page.', 'error')}
    ></audio>
  </div>
{/if}

<style>
  .sg {
    max-width: 1500px;
    margin: 0 auto;
    padding: 0 4px 24px;
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
  .sg-error {
    background: rgba(232, 90, 90, 0.15);
    border: 1px solid var(--danger, #e85a5a);
    border-radius: 5px;
    padding: 8px 10px;
    margin: 0 0 10px;
  }
  .sg-status {
    margin: 0 0 8px;
    font-size: 0.85rem;
    color: var(--info, #5b99ea);
  }
  .sg-status.is-error {
    color: var(--danger, #e85a5a);
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
  .sg-controls-main button {
    min-height: 52px;
    font-size: 0.95rem;
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
  }
</style>
