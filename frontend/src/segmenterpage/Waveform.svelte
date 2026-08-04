<script>
  // Two canvases over the same precomputed envelope (spec 050).
  //
  //   overview -- the whole recording at a glance, with every placed tune drawn
  //               as a coloured band. Click or drag anywhere to jump.
  //   detail   -- a zoomed tape that runs UNDER a fixed centre line. The mark
  //               point is therefore always in the same place on screen, which
  //               is what makes marking a whole night by feel possible; dragging
  //               the tape scrubs, so the finger never covers the mark point.
  import { envelopeForRange, formatTime, setColor } from './logic.js'

  let {
    peaks = null,
    peaksHz = 20,
    durationMs = 0,
    currentMs = 0,
    zoomMs = 20000,
    segments = new Map(),
    tunes = [],
    cursorTuneId = null,
    onseek = () => {},
    onscrubstart = () => {},
    onscrubend = () => {},
  } = $props()

  let overviewCanvas = $state(null)
  let detailCanvas = $state(null)
  let overviewWidth = $state(0)
  let detailWidth = $state(0)

  const OVERVIEW_H = 56
  const DETAIL_H = 168

  const tuneById = $derived(new Map(tunes.map((t) => [t.session_instance_tune_id, t])))

  // Redraw whenever anything visible changes. Reading the props here is what
  // registers the dependency -- Svelte 5 effects track what they touch.
  $effect(() => {
    drawOverview(overviewCanvas, overviewWidth, peaks, durationMs, currentMs, segments, zoomMs)
  })
  $effect(() => {
    drawDetail(detailCanvas, detailWidth, peaks, durationMs, currentMs, zoomMs, segments, cursorTuneId)
  })

  function prepare(canvas, cssWidth, cssHeight) {
    if (!canvas || !cssWidth) return null
    const dpr = window.devicePixelRatio || 1
    const w = Math.round(cssWidth * dpr)
    const h = Math.round(cssHeight * dpr)
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
    }
    const ctx = canvas.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, cssWidth, cssHeight)
    return ctx
  }

  function drawBars(ctx, env, width, height, colorAt) {
    const mid = height / 2
    for (let x = 0; x < width; x++) {
      const v = env[x]
      // A floor of one pixel keeps silence visible as a line rather than a
      // hole, so a gap still reads as part of the waveform.
      const half = Math.max(0.5, (v * height) / 2)
      ctx.fillStyle = colorAt(x)
      ctx.fillRect(x, mid - half, 1, half * 2)
    }
  }

  function drawOverview(canvas, width, peaks, durationMs, currentMs, segments, zoomMs) {
    const ctx = prepare(canvas, width, OVERVIEW_H)
    if (!ctx || !durationMs) return

    const env = envelopeForRange(peaks, peaksHz, 0, durationMs, width)

    // Placed tunes as coloured bands behind the waveform: the progress bar.
    for (const [id, seg] of segments) {
      const tune = tuneById.get(id)
      const x0 = (seg.startMs / durationMs) * width
      const x1 = (seg.endMs / durationMs) * width
      ctx.fillStyle = setColor(tune ? tune.set_number : 0, 0.34)
      ctx.fillRect(x0, 0, Math.max(1, x1 - x0), OVERVIEW_H)
    }

    drawBars(ctx, env, width, OVERVIEW_H, () => 'rgba(224,224,224,0.55)')

    // The slice the detail view is showing.
    const viewW = Math.max(2, (zoomMs / durationMs) * width)
    const viewX = (currentMs / durationMs) * width - viewW / 2
    ctx.strokeStyle = 'rgba(77,166,255,0.95)'
    ctx.lineWidth = 1
    ctx.strokeRect(Math.round(viewX) + 0.5, 0.5, Math.round(viewW), OVERVIEW_H - 1)
    ctx.fillStyle = 'rgba(77,166,255,0.15)'
    ctx.fillRect(viewX, 0, viewW, OVERVIEW_H)

    const px = (currentMs / durationMs) * width
    ctx.fillStyle = '#ffc107'
    ctx.fillRect(Math.round(px), 0, 1, OVERVIEW_H)
  }

  function drawDetail(canvas, width, peaks, durationMs, currentMs, zoomMs, segments, cursorTuneId) {
    const ctx = prepare(canvas, width, DETAIL_H)
    if (!ctx || !durationMs) return

    const startMs = currentMs - zoomMs / 2
    const endMs = currentMs + zoomMs / 2
    const msToX = (ms) => ((ms - startMs) / (endMs - startMs)) * width

    // Everything outside the file is drawn as a dead zone, so the ends of the
    // recording are unmistakable rather than just "no bars".
    if (startMs < 0) {
      ctx.fillStyle = 'rgba(255,255,255,0.04)'
      ctx.fillRect(0, 0, msToX(0), DETAIL_H)
    }
    if (endMs > durationMs) {
      const x = msToX(durationMs)
      ctx.fillStyle = 'rgba(255,255,255,0.04)'
      ctx.fillRect(x, 0, width - x, DETAIL_H)
    }

    // Segment bands + their boundaries.
    for (const [id, seg] of segments) {
      if (seg.endMs < startMs || seg.startMs > endMs) continue
      const tune = tuneById.get(id)
      const x0 = msToX(seg.startMs)
      const x1 = msToX(seg.endMs)
      const isCursor = id === cursorTuneId
      ctx.fillStyle = setColor(tune ? tune.set_number : 0, isCursor ? 0.4 : 0.22)
      ctx.fillRect(x0, 0, Math.max(1, x1 - x0), DETAIL_H)

      ctx.fillStyle = setColor(tune ? tune.set_number : 0, 1)
      ctx.fillRect(x0, 0, 2, DETAIL_H)
      // An explicit end gets its own hard edge; an implicit one deliberately
      // does not, because it is just wherever the next tune happens to start.
      if (seg.explicitEnd) {
        ctx.fillRect(x1 - 2, 0, 2, DETAIL_H)
      }

      if (tune && x1 - x0 > 46) {
        ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
        ctx.fillStyle = 'rgba(255,255,255,0.92)'
        ctx.save()
        ctx.beginPath()
        ctx.rect(x0 + 4, 0, x1 - x0 - 8, DETAIL_H)
        ctx.clip()
        ctx.fillText(tune.name, x0 + 6, 14)
        ctx.restore()
      }
    }

    const env = envelopeForRange(peaks, peaksHz, startMs, endMs, width)
    drawBars(ctx, env, width, DETAIL_H, () => 'rgba(224,224,224,0.7)')

    // Second ticks, thinning out as you zoom out so they never become noise.
    const stepMs = zoomMs <= 10000 ? 1000 : zoomMs <= 40000 ? 5000 : zoomMs <= 180000 ? 30000 : 120000
    ctx.font = '10px SFMono-Regular, Menlo, monospace'
    for (let t = Math.ceil(startMs / stepMs) * stepMs; t < endMs; t += stepMs) {
      const x = msToX(t)
      ctx.fillStyle = 'rgba(255,255,255,0.18)'
      ctx.fillRect(Math.round(x), DETAIL_H - 14, 1, 14)
      ctx.fillStyle = 'rgba(255,255,255,0.4)'
      ctx.fillText(formatTime(t), Math.round(x) + 3, DETAIL_H - 4)
    }

    // The centre line: the mark point, always here.
    const cx = Math.round(width / 2)
    ctx.fillStyle = '#ffc107'
    ctx.fillRect(cx, 0, 2, DETAIL_H)
    ctx.beginPath()
    ctx.moveTo(cx - 5, 0)
    ctx.lineTo(cx + 7, 0)
    ctx.lineTo(cx + 1, 8)
    ctx.closePath()
    ctx.fill()
  }

  // ---- pointer handling ------------------------------------------------------

  let drag = null

  function overviewPointer(event) {
    if (!durationMs || !overviewWidth) return
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
    onseek(ratio * durationMs)
  }

  function overviewDown(event) {
    event.currentTarget.setPointerCapture(event.pointerId)
    drag = { kind: 'overview' }
    onscrubstart()
    overviewPointer(event)
  }

  function detailDown(event) {
    event.currentTarget.setPointerCapture(event.pointerId)
    drag = { kind: 'detail', startX: event.clientX, startMs: currentMs, moved: false }
    onscrubstart()
  }

  function pointerMove(event) {
    if (!drag) return
    if (drag.kind === 'overview') {
      overviewPointer(event)
      return
    }
    const rect = event.currentTarget.getBoundingClientRect()
    const dx = event.clientX - drag.startX
    if (Math.abs(dx) > 3) drag.moved = true
    // Drag right = go back in time, like pulling tape past a playhead.
    const msPerPx = zoomMs / rect.width
    onseek(clamp(drag.startMs - dx * msPerPx))
  }

  function pointerUp(event) {
    if (!drag) return
    // A tap that never became a drag is a seek to that spot, which is what a
    // click means everywhere else.
    if (drag.kind === 'detail' && !drag.moved) {
      const rect = event.currentTarget.getBoundingClientRect()
      const offset = (event.clientX - rect.left - rect.width / 2) * (zoomMs / rect.width)
      onseek(clamp(drag.startMs + offset))
    }
    drag = null
    onscrubend()
  }

  function clamp(ms) {
    return Math.min(durationMs, Math.max(0, ms))
  }

  function detailWheel(event) {
    // Horizontal intent (trackpad swipe, shift+wheel) scrubs; the page keeps
    // vertical scroll, so the tool never traps the wheel.
    const dx = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.shiftKey ? event.deltaY : 0
    if (!dx) return
    event.preventDefault()
    onseek(clamp(currentMs + dx * (zoomMs / (detailWidth || 1))))
  }
</script>

<div class="wf">
  <div class="wf-detail" bind:clientWidth={detailWidth}>
    <canvas
      bind:this={detailCanvas}
      style="height:{DETAIL_H}px"
      onpointerdown={detailDown}
      onpointermove={pointerMove}
      onpointerup={pointerUp}
      onpointercancel={pointerUp}
      onwheel={detailWheel}
    ></canvas>
    {#if !peaks}
      <div class="wf-empty">no waveform for this recording</div>
    {/if}
  </div>

  <div class="wf-overview" bind:clientWidth={overviewWidth}>
    <canvas
      bind:this={overviewCanvas}
      style="height:{OVERVIEW_H}px"
      onpointerdown={overviewDown}
      onpointermove={pointerMove}
      onpointerup={pointerUp}
      onpointercancel={pointerUp}
    ></canvas>
  </div>
</div>

<style>
  .wf {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .wf-detail,
  .wf-overview {
    position: relative;
    background: #141414;
    border: 1px solid var(--border-color, #444);
    border-radius: 6px;
    overflow: hidden;
  }
  canvas {
    display: block;
    width: 100%;
    /* The tape is dragged horizontally; without this the browser claims the
       gesture for page scroll on touch and scrubbing simply never fires. */
    touch-action: pan-y;
    cursor: ew-resize;
  }
  .wf-empty {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--disabled-text, #888);
    font-size: 0.85rem;
    pointer-events: none;
  }
</style>
