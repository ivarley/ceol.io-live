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
    onedgepreview = () => {},
    onedgecommit = () => {},
  } = $props()

  let overviewCanvas = $state(null)
  let detailCanvas = $state(null)
  let overviewWidth = $state(0)
  let detailWidth = $state(0)
  // The boundary under the pointer, or the one being dragged: `{id, edge}`.
  // Drawn thicker so it is obvious WHICH edge a drag has hold of before the
  // drag starts -- two marks a second apart are two pixels apart at 3-hour zoom.
  let hotEdge = $state(null)

  const OVERVIEW_H = 56
  const DETAIL_H = 168
  // Grab tolerance. Touch gets far more of it: a fingertip is nowhere near as
  // precise as a cursor, and a 2px line is not a touch target.
  const EDGE_GRAB_PX = 6
  const EDGE_GRAB_TOUCH_PX = 15

  /**
   * The draggable boundaries: every placed tune's start, plus explicit ends.
   *
   * An implicit end is deliberately absent -- it IS the next tune's start, and
   * that start is already here. One handle per edge on screen, so a drag can
   * never be ambiguous about which of two coincident things it moves.
   */
  const edgeHandles = $derived.by(() => {
    const out = []
    for (const [id, seg] of segments) {
      out.push({ id, edge: 'start', ms: seg.startMs })
      if (seg.explicitEnd) out.push({ id, edge: 'end', ms: seg.endMs })
    }
    return out
  })

  const tuneById = $derived(new Map(tunes.map((t) => [t.session_instance_tune_id, t])))

  // Redraw whenever anything visible changes. Reading the props here is what
  // registers the dependency -- Svelte 5 effects track what they touch.
  $effect(() => {
    drawOverview(overviewCanvas, overviewWidth, peaks, durationMs, currentMs, segments, zoomMs)
  })
  $effect(() => {
    drawDetail(detailCanvas, detailWidth, peaks, durationMs, currentMs, zoomMs, segments, cursorTuneId, hotEdge)
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

  /**
   * One boundary line, with a grip tab at the top.
   *
   * The tab is the affordance: a 2px coloured line reads as decoration, and
   * nothing else on the tape says "this can be moved". When the pointer is on
   * it (or dragging it) the whole edge thickens and goes white, so you can see
   * which of two nearby edges you have hold of before you commit to the drag.
   */
  function drawEdge(ctx, x, color, hot) {
    ctx.fillStyle = hot ? '#fff' : color
    ctx.fillRect(x - (hot ? 1 : 0), 0, hot ? 4 : 2, DETAIL_H)
    ctx.fillRect(x - (hot ? 3 : 2), 0, hot ? 8 : 6, hot ? 9 : 6)
  }

  function drawDetail(canvas, width, peaks, durationMs, currentMs, zoomMs, segments, cursorTuneId, hotEdge) {
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

      const color = setColor(tune ? tune.set_number : 0, 1)
      drawEdge(ctx, x0, color, hotEdge && hotEdge.id === id && hotEdge.edge === 'start')
      // An explicit end gets its own hard edge; an implicit one deliberately
      // does not, because it is just wherever the next tune happens to start --
      // and that start is the handle you drag to move the pair of them.
      if (seg.explicitEnd) {
        drawEdge(ctx, x1 - 2, color, hotEdge && hotEdge.id === id && hotEdge.edge === 'end')
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

  /** Absolute time under a client X coordinate on the detail tape. */
  function detailMsAt(clientX, rect) {
    const offset = (clientX - rect.left - rect.width / 2) * (zoomMs / rect.width)
    return clamp(currentMs + offset)
  }

  /** The boundary within grabbing distance of a client X, or null. */
  function edgeNear(clientX, rect, tolerancePx) {
    if (!durationMs || !rect.width) return null
    const msPerPx = zoomMs / rect.width
    let best = null
    for (const handle of edgeHandles) {
      const hx = rect.left + rect.width / 2 + (handle.ms - currentMs) / msPerPx
      const distance = Math.abs(hx - clientX)
      if (distance <= tolerancePx && (!best || distance < best.distance)) best = { ...handle, distance }
    }
    return best
  }

  function detailDown(event) {
    event.currentTarget.setPointerCapture?.(event.pointerId)
    const rect = event.currentTarget.getBoundingClientRect()
    // Grabbing an edge beats scrubbing the tape: a drag that starts ON a
    // boundary can only have meant that boundary. Everywhere else is still the
    // scrub it has always been, so the common gesture is unchanged.
    const grabbed = edgeNear(event.clientX, rect, event.pointerType === 'touch' ? EDGE_GRAB_TOUCH_PX : EDGE_GRAB_PX)
    if (grabbed) {
      drag = { kind: 'edge', id: grabbed.id, edge: grabbed.edge }
      hotEdge = { id: grabbed.id, edge: grabbed.edge }
      onscrubstart()
      onedgepreview(grabbed.id, grabbed.edge, detailMsAt(event.clientX, rect))
      return
    }
    drag = { kind: 'detail', startX: event.clientX, startMs: currentMs, moved: false }
    onscrubstart()
  }

  function pointerMove(event) {
    if (!drag) {
      // Idle hover: light up whatever edge a press would grab, so the tape says
      // where its handles are before anything is committed to.
      if (event.currentTarget === detailCanvas) {
        const near = edgeNear(event.clientX, event.currentTarget.getBoundingClientRect(), EDGE_GRAB_PX)
        hotEdge = near ? { id: near.id, edge: near.edge } : null
      }
      return
    }
    if (drag.kind === 'overview') {
      overviewPointer(event)
      return
    }
    const rect = event.currentTarget.getBoundingClientRect()
    if (drag.kind === 'edge') {
      // The tape deliberately does NOT follow: it is centred on the playhead,
      // so moving the playhead here would slide the view out from under the
      // edge being placed.
      onedgepreview(drag.id, drag.edge, detailMsAt(event.clientX, rect))
      return
    }
    const dx = event.clientX - drag.startX
    if (Math.abs(dx) > 3) drag.moved = true
    // Drag right = go back in time, like pulling tape past a playhead.
    const msPerPx = zoomMs / rect.width
    onseek(clamp(drag.startMs - dx * msPerPx))
  }

  function pointerUp(event) {
    if (!drag) return
    const rect = event.currentTarget.getBoundingClientRect()
    if (drag.kind === 'edge') {
      onedgecommit(drag.id, drag.edge, detailMsAt(event.clientX, rect))
      hotEdge = null
      drag = null
      onscrubend()
      return
    }
    // A tap that never became a drag is a seek to that spot, which is what a
    // click means everywhere else.
    if (drag.kind === 'detail' && !drag.moved) {
      onseek(detailMsAt(event.clientX, rect))
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
      class:on-edge={hotEdge != null}
      style="height:{DETAIL_H}px"
      onpointerdown={detailDown}
      onpointermove={pointerMove}
      onpointerup={pointerUp}
      onpointercancel={pointerUp}
      onpointerleave={() => { if (!drag) hotEdge = null }}
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
  /* Over a boundary the gesture means something different — moving that edge,
     not scrubbing the tape — so the cursor says so before the press. */
  canvas.on-edge {
    cursor: col-resize;
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
