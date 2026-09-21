// Component tests for the segmenter (spec 050): first paint comes from the
// embedded payload with no fetch, and the one-key marking loop advances the
// cursor and persists through the API.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor, fireEvent } from '@testing-library/svelte'
import App from '../src/segmenterpage/App.svelte'

const payload = () => ({
  success: true,
  recording: {
    recording_id: 7,
    session_instance_id: 42,
    label: 'Test night',
    mime_type: 'audio/mp4',
    duration_ms: 600000,
    is_clock_anchor: true,
    clock_offset_ms: 0,
    started_at: null,
    peaks_hz: 20,
    has_peaks: false, // keeps the test off the binary peaks fetch
    peaks_url: '/api/recordings/7/peaks',
    audio_sources: [
      { id: 'proxy', label: 'low', url: 'blob:proxy', mime_type: 'audio/mp4', size_bytes: 44716235 },
      { id: 'master', label: 'full', url: 'blob:master', mime_type: 'audio/mpeg', size_bytes: 348303266 },
    ],
    has_proxy: true,
    audio_error: null,
    notes: null,
  },
  session_instance: {
    session_instance_id: 42,
    date: '2026-03-05',
    session_id: 3,
    session_name: 'Test Session',
    session_path: 'town/venue',
  },
  tunes: [
    { session_instance_tune_id: 1, tune_id: 101, name: 'Alpha Reel', tune_type: 'Reel', set_number: 1, position_in_set: 1, is_set_end: false, segment: null },
    { session_instance_tune_id: 2, tune_id: 102, name: 'Bravo Jig', tune_type: 'Jig', set_number: 1, position_in_set: 2, is_set_end: true, segment: null },
    { session_instance_tune_id: 3, tune_id: 103, name: 'Charlie Polka', tune_type: 'Polka', set_number: 2, position_in_set: 1, is_set_end: true, segment: null },
  ],
  other_recordings: [],
})

beforeEach(() => {
  // jsdom implements neither of these; the cursor row scrolls itself into view.
  Element.prototype.scrollIntoView = vi.fn()
  // jsdom has no media pipeline; play/pause just need to not throw.
  window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
  window.HTMLMediaElement.prototype.pause = vi.fn()
  window.HTMLMediaElement.prototype.load = vi.fn()
  // This jsdom exposes no localStorage at all; the app reads and writes the
  // remembered encode through it, and one test asserts on what it remembered.
  if (!window.localStorage) {
    const store = new Map()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (k) => (store.has(k) ? store.get(k) : null),
        setItem: (k, v) => store.set(k, String(v)),
        removeItem: (k) => store.delete(k),
      },
    })
  }
  // ...and its currentTime is read-only, so the playhead can never leave 0.
  // Make it a plain writable property: the app both writes it (seek) and reads
  // it back (the rAF tick), so a test can put the playhead somewhere real.
  Object.defineProperty(window.HTMLMediaElement.prototype, 'currentTime', {
    configurable: true, writable: true, value: 0,
  })
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ success: true, segment: { recording_tune_segment_id: 1, session_instance_tune_id: 1, start_ms: 0, end_ms: null } }),
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('first paint', () => {
  it('renders the embedded log without fetching', () => {
    const { container, getByText } = render(App, { props: { pageData: payload() } })
    // Scoped to the list: the cursor tune's name also appears in the "next up"
    // banner, so an unscoped query would be ambiguous.
    const listed = [...container.querySelectorAll('.tl .tl-name')].map((el) => el.textContent)
    expect(listed).toEqual(['Alpha Reel', 'Bravo Jig', 'Charlie Polka'])
    expect(getByText('Test night')).toBeTruthy()
    // has_peaks is false, so nothing should have been requested at all.
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('groups the log into its sets', () => {
    const { getByText } = render(App, { props: { pageData: payload() } })
    expect(getByText('Set 1')).toBeTruthy()
    expect(getByText('Set 2')).toBeTruthy()
  })

  it('shows the first tune as the cursor and the placed count as zero', () => {
    const { container } = render(App, { props: { pageData: payload() } })
    expect(container.querySelector('.sg-progress strong').textContent).toBe('0')
    expect(container.querySelector('.sg-next-name').textContent).toBe('Alpha Reel')
  })

  it('says so when there is no payload at all', () => {
    const { getByText } = render(App, { props: { pageData: null } })
    expect(getByText(/No recording payload/)).toBeTruthy()
  })
})

describe('marking', () => {
  it('places the cursor tune, advances, and PUTs the segment', async () => {
    const { container } = render(App, { props: { pageData: payload() } })

    await fireEvent.keyDown(window, { key: 'm' })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/recordings/7/segments/1',
        expect.objectContaining({ method: 'PUT' }),
      )
    })
    // Cursor moved on to the next tune in the log — the whole point of the key.
    await waitFor(() => {
      expect(container.querySelector('.sg-next-name').textContent).toBe('Bravo Jig')
    })
  })

  it('sends a null end_ms, because the next tune implies it', async () => {
    render(App, { props: { pageData: payload() } })
    await fireEvent.keyDown(window, { key: 'm' })
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    const body = JSON.parse(global.fetch.mock.calls[0][1].body)
    expect(body.end_ms).toBeNull()
    expect(body.start_ms).toBe(0)
  })

  it('rolls the mark back and reports when the save fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ success: false, error: 'boom' }),
    })
    const { container, getByText } = render(App, { props: { pageData: payload() } })

    await fireEvent.keyDown(window, { key: 'm' })

    await waitFor(() => expect(getByText(/Could not save "Alpha Reel"/)).toBeTruthy())
    // The optimistic placement is gone again: still 0 placed.
    expect(container.querySelector('.sg-progress strong').textContent).toBe('0')
  })

  it('ignores keystrokes typed into a field', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    const input = document.createElement('input')
    container.appendChild(input)
    await fireEvent.keyDown(input, { key: 'm' })
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

describe('explicit ends', () => {
  it('does nothing when no tune has been placed before the playhead', async () => {
    const { getByText } = render(App, { props: { pageData: payload() } })
    await fireEvent.keyDown(window, { key: 'e' })
    await waitFor(() => expect(getByText(/No placed tune before the playhead/)).toBeTruthy())
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

describe('cursor movement', () => {
  it('steps down and up the log without placing anything', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    await fireEvent.keyDown(window, { key: 'ArrowDown' })
    await waitFor(() => expect(container.querySelector('.sg-next-name').textContent).toBe('Bravo Jig'))
    await fireEvent.keyDown(window, { key: 'ArrowUp' })
    await waitFor(() => expect(container.querySelector('.sg-next-name').textContent).toBe('Alpha Reel'))
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

describe('clearing a mark', () => {
  const placed = () => {
    const p = payload()
    p.tunes[0].segment = { recording_tune_segment_id: 5, session_instance_tune_id: 1, start_ms: 1000, end_ms: null }
    // Bravo closes set 1, so give it an explicit end: otherwise the app is in
    // its "M means end the set" mode and these cursor assertions are testing
    // that instead of what they mean to.
    p.tunes[1].segment = { recording_tune_segment_id: 6, session_instance_tune_id: 2, start_ms: 9000, end_ms: 20000 }
    return p
  }

  it('puts the cursor back on the tune it cleared', async () => {
    // Clearing by hand means "I got that one wrong" — the next M belongs to it,
    // not to whatever the cursor had already moved on to.
    const { container } = render(App, { props: { pageData: placed() } })
    expect(container.querySelector('.sg-next-name').textContent).toBe('Charlie Polka')

    const clear = container.querySelectorAll('.tl-clear')[0]
    await fireEvent.click(clear)

    await waitFor(() => {
      expect(container.querySelector('.sg-next-name').textContent).toBe('Alpha Reel')
    })
  })

  it('restores both the mark and the cursor when the delete fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 500, json: async () => ({ success: false, error: 'nope' }),
    })
    const { container, getByText } = render(App, { props: { pageData: placed() } })

    await fireEvent.click(container.querySelectorAll('.tl-clear')[0])

    await waitFor(() => expect(getByText(/Could not clear "Alpha Reel"/)).toBeTruthy())
    // Cursor back where it was, and the mark is still there.
    expect(container.querySelector('.sg-next-name').textContent).toBe('Charlie Polka')
    expect(container.querySelector('.sg-progress strong').textContent).toBe('2')
  })

  it('does not let clearing hijack the cursor that undo restores', async () => {
    // undo() clears too, but it has already put the cursor back where the mark
    // was made; clearing must not overwrite that.
    const { container } = render(App, { props: { pageData: payload() } })
    await fireEvent.keyDown(window, { key: 'm' })          // places Alpha, cursor -> Bravo
    await waitFor(() => expect(container.querySelector('.sg-next-name').textContent).toBe('Bravo Jig'))

    await fireEvent.keyDown(window, { key: 'u' })          // undo -> cursor back to Alpha
    await waitFor(() => expect(container.querySelector('.sg-next-name').textContent).toBe('Alpha Reel'))
  })
})

// The app reads the playhead off the audio element on every animation frame,
// so moving it means writing there and letting a frame go by.
async function movePlayheadTo(container, seconds) {
  container.querySelector('audio').currentTime = seconds
  await new Promise((r) => setTimeout(r, 60))
}

describe('M as end-of-set', () => {
  // Marking a set's last tune leaves that set open. The next thing anyone does
  // is say where it stopped, so M means that rather than requiring a second key.
  const afterMarkingLastOfSet = () => {
    const p = payload()
    p.tunes[0].segment = { recording_tune_segment_id: 5, session_instance_tune_id: 1, start_ms: 1000, end_ms: null }
    p.tunes[1].segment = { recording_tune_segment_id: 6, session_instance_tune_id: 2, start_ms: 9000, end_ms: null }
    return p
  }

  it('announces the mode instead of leaving M ambiguous', () => {
    const { container } = render(App, { props: { pageData: afterMarkingLastOfSet() } })
    expect(container.querySelector('.sg-next.is-ending')).toBeTruthy()
    expect(container.querySelector('.sg-next-name').textContent).toBe('Bravo Jig')
    expect(container.querySelector('.sg-mark').textContent).toContain('End of set')
  })

  it('M sets the end on the set\'s last tune, not a start on the next one', async () => {
    const { container } = render(App, { props: { pageData: afterMarkingLastOfSet() } })
    await movePlayheadTo(container, 30)   // past Bravo's 9s start
    await fireEvent.keyDown(window, { key: 'm' })

    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/recordings/7/segments/2')   // Bravo, not Charlie
    expect(JSON.parse(opts.body).end_ms).not.toBeNull()
  })

  it('does not advance the cursor when it ends a set', async () => {
    const { container } = render(App, { props: { pageData: afterMarkingLastOfSet() } })
    await movePlayheadTo(container, 30)
    await fireEvent.keyDown(window, { key: 'm' })
    // Still pointed at the first tune of the next set, ready for the next M.
    await waitFor(() => {
      expect(container.querySelector('.sg-next-name').textContent).toBe('Charlie Polka')
    })
  })

  it('goes back to marking starts once the set is closed', async () => {
    const p = afterMarkingLastOfSet()
    p.tunes[1].segment.end_ms = 20000        // set already ended
    const { container } = render(App, { props: { pageData: p } })
    expect(container.querySelector('.sg-next.is-ending')).toBeNull()
    expect(container.querySelector('.sg-mark').textContent).toContain('Mark start')

    await fireEvent.keyDown(window, { key: 'm' })
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(global.fetch.mock.calls[0][0]).toBe('/api/recordings/7/segments/3')  // Charlie
  })

  it('stays in start mode mid-set, where the end is implied anyway', () => {
    const p = payload()
    // Alpha is placed but is NOT the last of its set, so nothing is pending.
    p.tunes[0].segment = { recording_tune_segment_id: 5, session_instance_tune_id: 1, start_ms: 1000, end_ms: null }
    const { container } = render(App, { props: { pageData: p } })
    expect(container.querySelector('.sg-next.is-ending')).toBeNull()
    expect(container.querySelector('.sg-next-name').textContent).toBe('Bravo Jig')
  })
})

describe('audio loading state', () => {
  // The waveform paints instantly from precomputed peaks, so the page looks
  // finished while a 350MB file is still loading. Without a spinner that reads
  // as "the tool is broken" -- which is exactly how it was reported.
  const spinner = (c) => c.querySelector('.sg-play .sg-spinner')

  it('shows a spinner in the play button until the audio can play', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    expect(spinner(container)).toBeTruthy()
    expect(container.querySelector('.sg-loading').textContent.trim()).toBe('loading audio…')

    await fireEvent(container.querySelector('audio'), new Event('canplay'))

    await waitFor(() => expect(spinner(container)).toBeNull())
    expect(container.querySelector('.sg-loading')).toBeNull()
    expect(container.querySelector('.sg-play').textContent).toContain('▶')
  })

  it('goes back to a spinner if playback runs dry mid-tune', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await fireEvent(el, new Event('canplay'))
    await waitFor(() => expect(spinner(container)).toBeNull())

    await fireEvent(el, new Event('waiting'))
    await waitFor(() => expect(spinner(container)).toBeTruthy())
    expect(container.querySelector('.sg-loading').textContent.trim()).toBe('buffering…')

    await fireEvent(el, new Event('playing'))
    await waitFor(() => expect(spinner(container)).toBeNull())
  })

  it('never disables play while loading — tapping it is what starts the fetch', () => {
    // preload="metadata" means the browser fetches nothing until asked, so a
    // disabled button during "loading" would deadlock: no play, so no load, so
    // no canplay, so no play.
    const { container } = render(App, { props: { pageData: payload() } })
    expect(spinner(container)).toBeTruthy()
    expect(container.querySelector('.sg-play').disabled).toBe(false)
  })

  it('clears the spinner on error rather than spinning forever', async () => {
    const { container, getByText } = render(App, { props: { pageData: payload() } })
    await fireEvent(container.querySelector('audio'), new Event('error'))
    await waitFor(() => expect(getByText(/could not be loaded/)).toBeTruthy())
    expect(spinner(container)).toBeNull()
  })
})

describe('audio quality switch', () => {
  const sel = (c) => [...c.querySelectorAll('.sg-opt select')].find((s) => s.value === 'proxy' || s.value === 'master')

  beforeEach(() => {
    try { window.localStorage.removeItem('ceol.segmenter.audioSource') } catch { /* ignore */ }
  })

  it('opens on the first source — the small one — and offers both with sizes', () => {
    const { container } = render(App, { props: { pageData: payload() } })
    const select = sel(container)
    expect(select.value).toBe('proxy')
    const labels = [...select.options].map((o) => o.textContent.trim())
    expect(labels[0]).toContain('low')
    expect(labels[0]).toContain('45 MB')
    expect(labels[1]).toContain('full')
    expect(labels[1]).toContain('348 MB')
  })

  it('keeps your place when you switch encodes', async () => {
    // The whole risk of this feature: changing src resets an <audio> to zero,
    // so switching quality mid-session would otherwise throw away the exact
    // spot being worked on.
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await fireEvent(el, new Event('canplay'))
    el.currentTime = 742

    await fireEvent.change(sel(container), { target: { value: 'master' } })
    await fireEvent(el, new Event('loadedmetadata'))

    await waitFor(() => expect(el.getAttribute('src')).toBe('blob:master'))
    expect(el.currentTime).toBe(742)
  })

  it('resumes playing if it was playing before the switch', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await fireEvent(el, new Event('canplay'))
    el.currentTime = 100
    Object.defineProperty(el, 'paused', { configurable: true, value: false })

    await fireEvent.change(sel(container), { target: { value: 'master' } })
    await fireEvent(el, new Event('loadedmetadata'))

    await waitFor(() => expect(el.play).toHaveBeenCalled())
  })

  it('shows the spinner while the new source loads', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    await fireEvent(container.querySelector('audio'), new Event('canplay'))
    await waitFor(() => expect(container.querySelector('.sg-play .sg-spinner')).toBeNull())

    await fireEvent.change(sel(container), { target: { value: 'master' } })
    await waitFor(() => expect(container.querySelector('.sg-play .sg-spinner')).toBeTruthy())
  })

  it('remembers the choice for next time', async () => {
    const { container, unmount } = render(App, { props: { pageData: payload() } })
    await fireEvent.change(sel(container), { target: { value: 'master' } })
    await waitFor(() => expect(window.localStorage.getItem('ceol.segmenter.audioSource')).toBe('master'))
    unmount()

    const again = render(App, { props: { pageData: payload() } })
    expect(sel(again.container).value).toBe('master')
  })

  it('hides the control when there is only one encode', () => {
    const p = payload()
    p.recording.audio_sources = [p.recording.audio_sources[1]]  // master only
    p.recording.has_proxy = false
    const { container } = render(App, { props: { pageData: p } })
    expect(sel(container)).toBeUndefined()
    expect(container.querySelector('audio').getAttribute('src')).toBe('blob:master')
  })
})

describe('the round trip to the log', () => {
  // Timestamping is where a missing tune shows up -- a stretch of audio with no
  // cursor to put on it -- and the fix is one line in the logger. The trip out
  // lands in edit mode; the way back is the log's own Recordings row, which
  // carries no timestamp, so the playhead is stashed here instead.
  const RESUME_KEY = 'ceol.segmenter.resume.7'

  let realLocation
  beforeEach(() => {
    window.sessionStorage.removeItem(RESUME_KEY)
    realLocation = window.location
    // jsdom refuses a real navigation; capture the href instead of following it.
    Object.defineProperty(window, 'location', {
      configurable: true, writable: true, value: { href: '', pathname: '/admin/recordings/7/segment', search: '' },
    })
  })
  afterEach(() => {
    Object.defineProperty(window, 'location', { configurable: true, writable: true, value: realLocation })
  })

  it('goes to the log in edit mode', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    await fireEvent.click(container.querySelector('.sg-editlog'))
    expect(window.location.href).toBe('/live/instances/42?edit=1')
  })

  it('stashes the playhead on the way out', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await fireEvent(el, new Event('canplay'))
    el.currentTime = 342
    // The rAF tick is what copies the element's clock into the app's playhead.
    await waitFor(() => expect(container.querySelector('.sg-time').textContent).toContain('5:42'))

    await fireEvent.click(container.querySelector('.sg-editlog'))
    expect(window.sessionStorage.getItem(RESUME_KEY)).toBe('342000')
  })

  it('reopens where it left off, once', async () => {
    window.sessionStorage.setItem(RESUME_KEY, '342000')

    const first = render(App, { props: { pageData: payload() } })
    const el = first.container.querySelector('audio')
    await fireEvent(el, new Event('loadedmetadata'))
    expect(el.currentTime).toBe(342)
    // Read once: the mark means "resume this round trip", not "always reopen
    // three hours in" -- so the next visit starts at the top.
    expect(window.sessionStorage.getItem(RESUME_KEY)).toBeNull()
    first.unmount()

    const again = render(App, { props: { pageData: payload() } })
    const el2 = again.container.querySelector('audio')
    el2.currentTime = 0
    await fireEvent(el2, new Event('loadedmetadata'))
    expect(el2.currentTime).toBe(0)
  })

  it('holds the remembered spot until the audio catches up', async () => {
    // The rAF tick copies the element's clock into the playhead, and that clock
    // reads 0 until metadata lands -- forever, if the audio never loads at all.
    // Without holding it, the tape snaps back to the top a frame after painting.
    window.sessionStorage.setItem(RESUME_KEY, '342000')
    const { container } = render(App, { props: { pageData: payload() } })
    await waitFor(() => expect(container.querySelector('.sg-time').textContent).toContain('5:42'))
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    expect(container.querySelector('.sg-time').textContent).toContain('5:42')
  })

  it('lets a deliberate seek win over a restore still in flight', async () => {
    window.sessionStorage.setItem(RESUME_KEY, '342000')
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await fireEvent.click(container.querySelector('.sg-controls button')) // −15s
    await fireEvent(el, new Event('loadedmetadata'))
    // The mark is spent, not queued: the scrub already moved on from it.
    expect(el.currentTime).not.toBe(342)
  })

  it('clamps a stale mark to the length of the recording', async () => {
    // The log can be edited between leaving and coming back, but the audio
    // cannot -- still, a mark past the end would seek nowhere useful.
    window.sessionStorage.setItem(RESUME_KEY, '99999999')
    const { container } = render(App, { props: { pageData: payload() } })
    await fireEvent(container.querySelector('audio'), new Event('loadedmetadata'))
    expect(container.querySelector('audio').currentTime).toBe(600)
  })
})

describe('dragging a boundary', () => {
  // Marking happens at speed against a moving playhead, so some marks land a
  // little off. Re-marking only fixes a START; dragging the edge itself is the
  // direct correction, and it is the only way to move an explicit end by hand.
  //
  // Placed here, all inside the tape's opening window (playhead 0, ±10s):
  //   Alpha  2s -> 4s implicit -- its end IS Bravo's start
  //   Bravo  4s -> 6s explicit -- closes set 1, then a gap
  //   Charlie 8s -> end of file
  const marked = () => {
    const p = payload()
    p.tunes[0].segment = { recording_tune_segment_id: 5, session_instance_tune_id: 1, start_ms: 2000, end_ms: null }
    p.tunes[1].segment = { recording_tune_segment_id: 6, session_instance_tune_id: 2, start_ms: 4000, end_ms: 6000 }
    p.tunes[2].segment = { recording_tune_segment_id: 7, session_instance_tune_id: 3, start_ms: 8000, end_ms: null }
    return p
  }

  const WIDTH = 600 // px of tape
  const ZOOM = 20000 // ms visible, the default zoom

  /** Where a time sits on screen: the tape is centred on the playhead, at 0 here. */
  const xFor = (ms) => WIDTH / 2 + (ms / ZOOM) * WIDTH

  /**
   * Render with the tape given a real size. jsdom lays nothing out, so without
   * this every coordinate collapses to zero and no edge is ever within reach.
   */
  function renderTape(pageData = marked()) {
    const view = render(App, { props: { pageData } })
    const canvas = view.container.querySelector('.wf-detail canvas')
    canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: WIDTH, height: 168, right: WIDTH, bottom: 168 })
    canvas.setPointerCapture = vi.fn()
    canvas.releasePointerCapture = vi.fn()
    return { ...view, canvas }
  }

  /**
   * jsdom has no PointerEvent, and fireEvent.pointerDown's fallback drops
   * clientX entirely -- which is the only thing these handlers read. A
   * MouseEvent carries it, so the pointer events are built by hand.
   */
  async function pointer(canvas, type, clientX, pointerType) {
    const event = new MouseEvent(type, { clientX, bubbles: true })
    if (pointerType) Object.defineProperty(event, 'pointerType', { value: pointerType })
    await fireEvent(canvas, event)
  }

  async function dragEdge(canvas, fromMs, toMs, pointerType) {
    await pointer(canvas, 'pointerdown', xFor(fromMs), pointerType)
    await pointer(canvas, 'pointermove', xFor(toMs), pointerType)
    await pointer(canvas, 'pointerup', xFor(toMs), pointerType)
  }

  const duration = (container, id) => container.querySelector(`[data-tune-id="${id}"] .tl-dur`).textContent.trim()

  beforeEach(() => {
    // Echo the upsert back the way the API does. The shared mock answers every
    // call with the SAME canned segment, which lands every dragged tune on top
    // of tune 1 at 0ms and makes the resolved ends nonsense.
    global.fetch = vi.fn(async (url, init) => ({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        segment: {
          recording_tune_segment_id: 9,
          session_instance_tune_id: Number(url.split('/').pop()),
          ...JSON.parse(init.body),
        },
      }),
    }))
  })

  it('moves an explicit end and saves it once', async () => {
    const { canvas } = renderTape()
    await dragEdge(canvas, 6000, 5500)

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))
    const [url, init] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/recordings/7/segments/2')
    expect(init.method).toBe('PUT')
    const body = JSON.parse(init.body)
    expect(body.start_ms).toBe(4000)
    expect(body.end_ms).toBe(5500)
  })

  it('moves a start, and with it the implicit end of the tune before it', async () => {
    const { container, canvas } = renderTape()
    // Bravo's start IS Alpha's end: one handle for the edge they share.
    await dragEdge(canvas, 4000, 5000)

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))
    // Only Bravo is written. Alpha's end was never a stored value -- it is
    // resolved from whatever starts next -- so there is nothing to save on it.
    expect(global.fetch.mock.calls[0][0]).toBe('/api/recordings/7/segments/2')
    const body = JSON.parse(global.fetch.mock.calls[0][1].body)
    expect(body.start_ms).toBe(5000)
    expect(body.end_ms).toBe(6000)
    expect(duration(container, 1)).toBe('3s~')
  })

  it('will not let an edge swallow its neighbour', async () => {
    const { canvas } = renderTape()
    // Yank Bravo's end back past its own start; it stops half a second short.
    await dragEdge(canvas, 6000, 1000)

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).end_ms).toBe(4500)
  })

  it('writes nothing when the edge is put back where it was', async () => {
    const { canvas } = renderTape()
    await dragEdge(canvas, 6000, 6000)
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('leaves the playhead alone — the tape must not slide under the drag', async () => {
    const { container, canvas } = renderTape()
    const before = container.querySelector('.sg-time').textContent
    await dragEdge(canvas, 6000, 5000)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(container.querySelector('.sg-time').textContent).toBe(before)
  })

  it('rolls back to where the edge actually was when the save fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 500, json: async () => ({ success: false, error: 'boom' }),
    })
    const { container, canvas, getByText } = renderTape()

    await dragEdge(canvas, 6000, 5000)

    await waitFor(() => expect(getByText(/Could not save "Bravo Jig"/)).toBeTruthy())
    // 4s -> 6s again, not the 5s the drag previewed.
    expect(duration(container, 2)).toBe('2s')
  })

  it('undoes back to the original position', async () => {
    const { container, canvas } = renderTape()
    await dragEdge(canvas, 6000, 5000)
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))

    await fireEvent.keyDown(window, { key: 'u' })

    await waitFor(() => expect(duration(container, 2)).toBe('2s'))
    expect(JSON.parse(global.fetch.mock.calls.at(-1)[1].body).end_ms).toBe(6000)
  })

  it('gives a fingertip more room to grab than a cursor', async () => {
    // ~12px off the edge: a mouse at that distance meant to scrub, a finger
    // almost certainly meant the boundary it was aiming at.
    const nearMissMs = 6000 - 12 * (ZOOM / WIDTH)

    const mouse = renderTape()
    await dragEdge(mouse.canvas, nearMissMs, 5000)
    expect(global.fetch).not.toHaveBeenCalled()
    mouse.unmount()

    const touch = renderTape()
    await dragEdge(touch.canvas, nearMissMs, 5000, 'touch')
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).end_ms).toBe(5000)
  })

  it('still scrubs when the drag starts away from any edge', async () => {
    const { container, canvas } = renderTape()
    const before = container.querySelector('.sg-time').textContent
    // 3s is mid-Alpha, a second from either boundary.
    await dragEdge(canvas, 3000, 2000)
    expect(global.fetch).not.toHaveBeenCalled()
    expect(container.querySelector('.sg-time').textContent).not.toBe(before)
  })
})

describe('the end badge', () => {
  const marked = () => {
    const p = payload()
    p.tunes[0].segment = { recording_tune_segment_id: 5, session_instance_tune_id: 1, start_ms: 10000, end_ms: null }
    p.tunes[1].segment = { recording_tune_segment_id: 6, session_instance_tune_id: 2, start_ms: 20000, end_ms: 30000 }
    return p
  }

  it('jumps to the end of the set — the one time the list could not reach', async () => {
    const { container } = render(App, { props: { pageData: marked() } })
    const badge = container.querySelector('[data-tune-id="2"] .tl-endmark')
    await fireEvent.click(badge)
    await waitFor(() => expect(container.querySelector('.sg-time').textContent).toBe('0:30.0'))
  })

  it('jumps to an implied end too, which is where you go to type a real one', async () => {
    const p = marked()
    p.tunes[1].segment.end_ms = null // Bravo now runs until Charlie starts...
    p.tunes[2].segment = { recording_tune_segment_id: 7, session_instance_tune_id: 3, start_ms: 45000, end_ms: null }
    const { container } = render(App, { props: { pageData: p } })

    await fireEvent.click(container.querySelector('[data-tune-id="2"] .tl-endmark'))

    await waitFor(() => expect(container.querySelector('.sg-time').textContent).toBe('0:45.0'))
  })

  it('is inert while the tune has no mark to end', async () => {
    const { container } = render(App, { props: { pageData: payload() } })
    const badge = container.querySelector('[data-tune-id="2"] .tl-endmark')
    expect(badge.tagName).toBe('SPAN')
  })
})

describe('phone layout', () => {
  // The left column is sticky above the tune list, so its height is the list's
  // height. At full size it filled a phone screen on its own: the header and the
  // top of the tape — where the drag handles are — could only be seen by
  // scrolling the list back to the very top, which then left room for two tunes.
  // Everything here is that column getting shorter.
  let mediaListeners = []
  function viewport(matches) {
    mediaListeners = []
    window.matchMedia = vi.fn().mockImplementation((media) => ({
      matches,
      media,
      addEventListener: (_type, fn) => mediaListeners.push(fn),
      removeEventListener: vi.fn(),
    }))
  }

  afterEach(() => {
    delete window.matchMedia
  })

  const phone = (pageData = payload()) => {
    viewport(true)
    return render(App, { props: { pageData } })
  }
  const desktop = (pageData = payload()) => {
    viewport(false)
    return render(App, { props: { pageData } })
  }

  it('shrinks both canvases by a quarter', () => {
    const { container } = phone()
    expect(container.querySelector('.wf-detail canvas').style.height).toBe('126px')
    expect(container.querySelector('.wf-overview canvas').style.height).toBe('42px')
  })

  it('keeps them full size on a desktop', () => {
    const { container } = desktop()
    expect(container.querySelector('.wf-detail canvas').style.height).toBe('168px')
    expect(container.querySelector('.wf-overview canvas').style.height).toBe('56px')
  })

  it('drops the separate end button — the mark button already switches modes', () => {
    const { container } = phone()
    expect(container.querySelector('.sg-end')).toBeNull()
    expect(container.querySelector('.sg-mark')).toBeTruthy()
  })

  it('still switches that one button to "End of set" when a set needs one', async () => {
    // The mode is the whole reason one button can do the work of two, so losing
    // the second must not cost the first its two states.
    const p = payload()
    p.tunes[1].is_set_end = true
    const { container } = phone(p)

    await fireEvent.keyDown(window, { key: 'm' }) // place Alpha
    await fireEvent.keyDown(window, { key: 'm' }) // place Bravo, which closes the set

    await waitFor(() => expect(container.querySelector('.sg-mark').textContent.trim()).toBe('End of set'))
    expect(container.querySelector('.sg-next-inline').textContent).toContain('end of set')
  })

  it('makes undo an icon', () => {
    const { container } = phone()
    const undo = container.querySelector('.sg-undo')
    expect(undo.textContent.trim()).toBe('↺')
    // Still announced properly — the label went, not the meaning.
    expect(undo.getAttribute('aria-label')).toBe('Undo')
  })

  it('folds "next up" into the mark button row, without the set number', () => {
    const { container } = phone()
    expect(container.querySelector('.sg-next')).toBeNull() // the full-width banner
    const inline = container.querySelector('.sg-controls-main .sg-next-inline')
    expect(inline.textContent).toContain('next up')
    expect(inline.textContent).toContain('Alpha Reel')
    expect(inline.textContent).not.toContain('set 1')
  })

  it('moves the encode switch into the header and shortens what shares the line', () => {
    const { container } = phone()
    expect(container.querySelector('.sg-progress .sg-opt-audio')).toBeTruthy()
    expect(container.querySelector('.sg-opts .sg-opt-audio')).toBeNull()
    expect(container.querySelector('.sg-progress').textContent).not.toContain('placed')
    expect(container.querySelector('.sg-editlog').textContent.trim()).toBe('✎ Fix')
  })

  it('follows a rotation or a resize without a reload', async () => {
    // Phone landscape crosses the breakpoint, and so does an iPad picked up
    // mid-session. The initial read is synchronous so the tape is never drawn
    // tall and re-drawn short; this is the other half of that — the listener.
    const { container } = phone()
    expect(container.querySelector('.sg-end')).toBeNull()

    expect(mediaListeners.length).toBe(1)
    mediaListeners.forEach((fn) => fn({ matches: false }))

    await waitFor(() => expect(container.querySelector('.sg-end')).toBeTruthy())
    expect(container.querySelector('.wf-detail canvas').style.height).toBe('168px')
    expect(container.querySelector('.sg-next')).toBeTruthy()
    expect(container.querySelector('.sg-next-inline')).toBeNull()
  })

  it('measures the chrome above it, so the pinned column ends at the screen edge', async () => {
    // The phone layout is `height: calc(100dvh - var(--sg-top))`: the tape and
    // the controls hold the top of the screen and only the log scrolls. Get the
    // offset wrong and either the mark button hangs below the fold or there is
    // a dead strip under the log.
    const realRect = Element.prototype.getBoundingClientRect
    Element.prototype.getBoundingClientRect = function () {
      return { ...realRect.call(this), top: this.classList?.contains('sg') ? 50 : 0 }
    }
    try {
      const { container } = phone()
      await waitFor(() => expect(container.querySelector('.sg').style.cssText).toContain('--sg-top: 50px'))
    } finally {
      Element.prototype.getBoundingClientRect = realRect
    }
  })

  it('leaves the desktop header and options row alone', () => {
    const { container } = desktop()
    expect(container.querySelector('.sg-opts .sg-opt-audio')).toBeTruthy()
    expect(container.querySelector('.sg-progress .sg-opt-audio')).toBeNull()
    expect(container.querySelector('.sg-progress').textContent).toContain('placed')
    expect(container.querySelector('.sg-editlog').textContent.trim()).toBe('✎ Fix the log')
    expect(container.querySelector('.sg-end')).toBeTruthy()
  })
})

// ---- offline (spec 050 "Offline") -------------------------------------------
//
// The store itself (static/js/segmenter_offline.js) has its own tests; here it
// is a hand-rolled fake, so these pin what the TOOL does with it: which copy of
// the log it opens on, how a queued mark looks, and what happens on sync.

function fakeOffline({ mirror = null, queue = [], audio = [], submit = null } = {}) {
  return {
    mirrorGet: vi.fn().mockResolvedValue(mirror),
    mirrorPut: vi.fn().mockResolvedValue(undefined),
    pending: vi.fn().mockResolvedValue(queue),
    audioList: vi.fn().mockResolvedValue(audio),
    audioGet: vi.fn().mockResolvedValue(undefined),
    audioDelete: vi.fn().mockResolvedValue(undefined),
    saveAudio: vi.fn(),
    submit: submit ?? vi.fn().mockResolvedValue({
      online: true, queued: false,
      data: { segment: { recording_tune_segment_id: 9, session_instance_tune_id: 1, start_ms: 0, end_ms: null } },
    }),
    flush: vi.fn().mockResolvedValue(undefined),
  }
}

const stamped = (generated_at) => ({ ...payload(), generated_at })

describe('offline', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:local')
    URL.revokeObjectURL = vi.fn()
  })
  afterEach(() => {
    delete window.SegmenterOffline
  })

  it('writes marks through the queue and keeps a queued one on screen, counted', async () => {
    const offline = fakeOffline({ submit: vi.fn().mockResolvedValue({ online: false, queued: true }) })
    window.SegmenterOffline = offline
    const { container } = render(App, { props: { pageData: stamped('2026-09-20T10:00:00+00:00') } })
    await waitFor(() => expect(offline.mirrorGet).toHaveBeenCalled())

    offline.pending.mockResolvedValue([{ key: '7:1', recording_id: 7, session_instance_tune_id: 1, kind: 'put', start_ms: 0, end_ms: null, ts: 1 }])
    await fireEvent.keyDown(window, { key: 'm' })

    await waitFor(() => {
      expect(offline.submit).toHaveBeenCalledWith(
        expect.objectContaining({ recording_id: 7, session_instance_tune_id: 1, kind: 'put', start_ms: 0, end_ms: null }),
      )
    })
    // Nothing went to fetch directly.
    expect(global.fetch).not.toHaveBeenCalled()
    // The mark stays, flagged, and the header counts it.
    await waitFor(() => expect(container.querySelector('.sg-saving').textContent).toBe('1 queued'))
    expect(container.querySelector('.tl-row[data-tune-id="1"]').classList.contains('is-pending')).toBe(true)
    expect(container.querySelector('.tl-row[data-tune-id="1"]').classList.contains('is-placed')).toBe(true)
    // ...and the working copy was mirrored with the pending mark in it.
    const last = offline.mirrorPut.mock.calls.at(-1)[1]
    expect(last.generated_at).toBe('2026-09-20T10:00:00+00:00')
    expect(last.tunes[0].segment).toMatchObject({ start_ms: 0, pending: true })
  })

  it('opens on the mirror when the page is a snapshot no newer than it', async () => {
    // Offline, the service worker hands back the page as it was last loaded
    // online. Everything marked since lives only in the mirror.
    window.SegmenterOffline = fakeOffline({
      mirror: {
        generated_at: '2026-09-20T12:00:00+00:00',
        tunes: payload().tunes.map((t, i) => (i === 0 ? { ...t, segment: { start_ms: 4000, end_ms: null } } : t)),
      },
    })
    const { container } = render(App, { props: { pageData: stamped('2026-09-20T10:00:00+00:00') } })
    await waitFor(() => {
      expect(container.querySelector('.tl-row[data-tune-id="1"]').classList.contains('is-placed')).toBe(true)
    })
    expect(container.querySelector('.sg-progress strong').textContent).toBe('1')
    // The cursor moved past the placed tune.
    expect(container.querySelector('.sg-next-name').textContent).toBe('Bravo Jig')
  })

  it('trusts a fresher payload over the mirror, with queued ops laid on top', async () => {
    // Online again: the server's picture is newer than the mirror, but the
    // queue holds a mark the server has not seen — that one still shows.
    window.SegmenterOffline = fakeOffline({
      mirror: {
        generated_at: '2026-09-20T10:00:00+00:00',
        tunes: payload().tunes.map((t, i) => (i === 1 ? { ...t, segment: { start_ms: 4000, end_ms: null } } : t)),
      },
      queue: [{ key: '7:3', recording_id: 7, session_instance_tune_id: 3, kind: 'put', start_ms: 9000, end_ms: null, ts: 1 }],
    })
    const { container } = render(App, { props: { pageData: stamped('2026-09-20T12:00:00+00:00') } })
    await waitFor(() => {
      expect(container.querySelector('.tl-row[data-tune-id="3"]').classList.contains('is-pending')).toBe(true)
    })
    // The mirror's mark on tune 2 was stale (the fresh payload has none).
    expect(container.querySelector('.tl-row[data-tune-id="2"]').classList.contains('is-placed')).toBe(false)
    expect(container.querySelector('.sg-saving').textContent).toBe('1 queued')
  })

  it('refetches the log from the server once the queue drains', async () => {
    window.SegmenterOffline = fakeOffline({
      queue: [{ key: '7:1', recording_id: 7, session_instance_tune_id: 1, kind: 'put', start_ms: 0, end_ms: null, ts: 1 }],
    })
    const { container } = render(App, { props: { pageData: stamped('2026-09-20T10:00:00+00:00') } })
    await waitFor(() => expect(container.querySelector('.sg-saving').textContent).toBe('1 queued'))

    const fresh = stamped('2026-09-20T13:00:00+00:00')
    fresh.tunes[0].segment = { recording_tune_segment_id: 1, session_instance_tune_id: 1, start_ms: 0, end_ms: null }
    global.fetch.mockResolvedValue({ ok: true, status: 200, json: async () => fresh })
    window.SegmenterOffline.pending.mockResolvedValue([])

    window.dispatchEvent(new CustomEvent('segmenter-synced', { detail: { cleared: 1, rejected: [], recording_ids: [7] } }))

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/recordings/7/segmenter', expect.anything()))
    await waitFor(() => expect(container.querySelector('.sg-saving').classList.contains('is-queued')).toBe(false))
    const row = container.querySelector('.tl-row[data-tune-id="1"]')
    expect(row.classList.contains('is-placed')).toBe(true)
    expect(row.classList.contains('is-pending')).toBe(false)
  })

  it('ignores a drain for some other recording', async () => {
    window.SegmenterOffline = fakeOffline()
    render(App, { props: { pageData: stamped('2026-09-20T10:00:00+00:00') } })
    await waitFor(() => expect(window.SegmenterOffline.mirrorGet).toHaveBeenCalled())
    window.dispatchEvent(new CustomEvent('segmenter-synced', { detail: { cleared: 1, rejected: [], recording_ids: [99] } }))
    await new Promise((r) => setTimeout(r, 20))
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('plays a saved copy from a blob URL and prefers it over the remembered encode', async () => {
    try { window.localStorage.setItem('ceol.segmenter.audioSource', 'master') } catch { /* ignore */ }
    window.SegmenterOffline = fakeOffline({
      audio: [{ recording_id: 7, source_id: 'proxy', blob: new Blob(['x']), size_bytes: 44716235, saved_at: 1 }],
    })
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    // No src until the lookup is done: a presigned URL offline is an error for nothing.
    expect(el.hasAttribute('src')).toBe(false)
    await waitFor(() => expect(el.getAttribute('src')).toBe('blob:local'))
    expect(container.querySelector('.sg-offline.is-saved')).toBeTruthy()
    const select = [...container.querySelectorAll('.sg-opt select')].find((s) => s.value === 'proxy' || s.value === 'master')
    expect(select.value).toBe('proxy')
    expect([...select.options].find((o) => o.value === 'proxy').textContent).toContain('✓')
    try { window.localStorage.removeItem('ceol.segmenter.audioSource') } catch { /* ignore */ }
  })

  it('streams the presigned URL when nothing is saved, and offers to save it', async () => {
    window.SegmenterOffline = fakeOffline()
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await waitFor(() => expect(el.getAttribute('src')).toBe('blob:proxy'))
    const btn = container.querySelector('button.sg-offline')
    expect(btn.textContent).toContain('save offline')
    expect(btn.textContent).toContain('45 MB')
  })

  it('saving downloads the current encode and switches playback to the copy in place', async () => {
    const offline = fakeOffline()
    offline.saveAudio.mockResolvedValue({ blob: new Blob(['x']), size_bytes: 44716235, saved_at: 2 })
    window.SegmenterOffline = offline
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await waitFor(() => expect(el.getAttribute('src')).toBe('blob:proxy'))
    await fireEvent(el, new Event('canplay'))
    el.currentTime = 321

    await fireEvent.click(container.querySelector('button.sg-offline'))
    expect(offline.saveAudio).toHaveBeenCalledWith(7, expect.objectContaining({ id: 'proxy' }), expect.anything())
    await waitFor(() => expect(el.getAttribute('src')).toBe('blob:local'))
    await fireEvent(el, new Event('loadedmetadata'))
    expect(el.currentTime).toBe(321)
    expect(container.querySelector('.sg-offline.is-saved')).toBeTruthy()
  })

  it('removing the copy goes back to streaming', async () => {
    window.SegmenterOffline = fakeOffline({
      audio: [{ recording_id: 7, source_id: 'proxy', blob: new Blob(['x']), size_bytes: 1, saved_at: 1 }],
    })
    const { container } = render(App, { props: { pageData: payload() } })
    const el = container.querySelector('audio')
    await waitFor(() => expect(el.getAttribute('src')).toBe('blob:local'))
    await fireEvent.click(container.querySelector('.sg-offline.is-saved .sg-offline-x'))
    await waitFor(() => expect(el.getAttribute('src')).toBe('blob:proxy'))
    expect(window.SegmenterOffline.audioDelete).toHaveBeenCalledWith(7, 'proxy')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:local')
  })

  it('a clear the server has no row for is still a clear', async () => {
    // The mark only ever lived in the queue; the server answering 404 to the
    // delete is the state being asked for, not a failure to roll back.
    const err = Object.assign(new Error('No segment for that tune'), { status: 404 })
    const offline = fakeOffline({
      mirror: {
        generated_at: '2026-09-20T12:00:00+00:00',
        tunes: payload().tunes.map((t, i) => (i === 0 ? { ...t, segment: { start_ms: 4000, end_ms: null, pending: true } } : t)),
      },
      submit: vi.fn().mockRejectedValue(err),
    })
    window.SegmenterOffline = offline
    const { container } = render(App, { props: { pageData: stamped('2026-09-20T10:00:00+00:00') } })
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="1"]').classList.contains('is-placed')).toBe(true))
    await fireEvent.click(container.querySelector('.tl-row[data-tune-id="1"] .tl-clear'))
    await waitFor(() => expect(offline.submit).toHaveBeenCalledWith(expect.objectContaining({ kind: 'delete', session_instance_tune_id: 1 })))
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="1"]').classList.contains('is-placed')).toBe(false))
    expect(container.querySelector('.sg-toast.is-error')).toBeNull()
  })
})

// ---- logging while segmenting (spec 050) -------------------------------------

// A written log with every tune placed and its last set CLOSED (an explicit end
// on the last tune) -- otherwise the tool's written-log rule applies first and
// the next M means "end of set", not "log a tune".
const allPlaced = () => {
  const p = payload()
  p.tunes = p.tunes.map((t, i) => ({
    ...t,
    segment: { session_instance_tune_id: t.session_instance_tune_id, start_ms: (i + 1) * 10000, end_ms: i === 2 ? 40000 : null },
  }))
  return p
}
const ganAinm = (id, start_ms, extra = {}) => ({
  session_instance_tune_id: id, tune_id: null, name: 'Gan Ainm', tune_type: null, set_number: 2, position_in_set: 2,
  is_set_end: true, source: 'segmenter', segment: { session_instance_tune_id: id, start_ms, end_ms: null }, ...extra,
})
const jsonResponse = (body, status = 200) => ({ ok: status < 400, status, json: async () => body })

describe('logging while segmenting', () => {
  beforeEach(() => {
    // jsdom has neither: the search's incipits lazy-load on intersection, and the
    // pane shell animates.
    globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
    Element.prototype.animate = vi.fn(() => ({ finished: Promise.resolve(), cancel() {}, finish() {}, onfinish: null }))
  })

  it('with every tune placed, the mark key logs a new tune at the playhead', async () => {
    const p = allPlaced()
    const logged = { ...p, tunes: [...p.tunes, ganAinm(4, 45000)] }
    global.fetch = vi.fn().mockResolvedValue(jsonResponse({ success: true, tunes: logged.tunes, tune: logged.tunes[3] }, 201))
    const { container } = render(App, { props: { pageData: p } })
    // No cursor: the banner and the button both say a mark logs a tune.
    expect(container.querySelector('.sg-next-label').textContent).toBe('log a tune')
    expect(container.querySelector('.sg-mark').textContent).toContain('Log a tune')
    expect(container.querySelector('.tl-row.is-cursor')).toBeNull()

    await movePlayheadTo(container, 45)
    await fireEvent.keyDown(window, { key: 'm' })
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/recordings/7/segments', expect.objectContaining({ method: 'POST' })))
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({ start_ms: 45000, end_ms: null })
    // The server's list is adopted wholesale, the new row reads as unlinked, and
    // the next mark logs again rather than ending the set.
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="4"] .tl-name.is-unlinked')).toBeTruthy())
    expect(container.querySelector('.sg-mark').textContent).toContain('Log a tune')
    expect(container.querySelector('.sg-progress strong').textContent).toBe('4')
  })

  it('scrolls the tune it just logged to the bottom of the log', async () => {
    // Logging mode has no cursor to follow, and the new row lands at the end of
    // a long list -- out of sight, one scroll away from the tap that names it.
    const p = allPlaced()
    const logged = { ...p, tunes: [...p.tunes, ganAinm(4, 45000)] }
    global.fetch = vi.fn().mockResolvedValue(jsonResponse({ success: true, tunes: logged.tunes, tune: logged.tunes[3] }, 201))
    const { container } = render(App, { props: { pageData: p } })
    Element.prototype.scrollIntoView.mockClear()
    await fireEvent.keyDown(window, { key: 'm' })
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="4"]')).toBeTruthy())
    await waitFor(() => {
      const calls = Element.prototype.scrollIntoView.mock.calls
      expect(calls.length).toBeGreaterThan(0)
      expect(calls.at(-1)[0]).toEqual({ block: 'end' })
    })
    expect(Element.prototype.scrollIntoView.mock.instances.at(-1).getAttribute('data-tune-id')).toBe('4')
  })

  it('after a written log\'s last tune, M still ends its set, and the mark after that logs', async () => {
    const p = payload()
    // Set 1 (Alpha, Bravo) placed and closed; Charlie, alone in set 2, unplaced.
    p.tunes = p.tunes.map((t, i) => (i < 2 ? { ...t, segment: { start_ms: (i + 1) * 10000, end_ms: i === 1 ? 25000 : null } } : t))
    const calls = []
    global.fetch = vi.fn(async (url, init) => {
      calls.push([url, init?.method])
      if (init?.method === 'POST') return jsonResponse({ success: true, tunes: [...allPlaced().tunes, ganAinm(4, 90000)], tune: ganAinm(4, 90000) }, 201)
      const sent = JSON.parse(init.body)
      return jsonResponse({ success: true, segment: { session_instance_tune_id: 3, start_ms: sent.start_ms, end_ms: sent.end_ms } })
    })
    const { container } = render(App, { props: { pageData: p } })
    expect(container.querySelector('.sg-next-name').textContent).toBe('Charlie Polka')
    await movePlayheadTo(container, 30)
    await fireEvent.keyDown(window, { key: 'm' }) // places Charlie, the last tune
    await waitFor(() => expect(container.querySelector('.sg-mark').textContent).toContain('End of set'))
    await movePlayheadTo(container, 60)
    await fireEvent.keyDown(window, { key: 'm' }) // ends its set (the written log's rule)
    await waitFor(() => expect(container.querySelector('.sg-mark').textContent).toContain('Log a tune'))
    await movePlayheadTo(container, 90)
    await fireEvent.keyDown(window, { key: 'm' }) // logs a new tune
    await waitFor(() => expect(calls.some(([u, m]) => u === '/api/recordings/7/segments' && m === 'POST')).toBe(true))
  })

  it('shows the End-set button on a phone while logging, since M never flips to end', async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })
    try {
      const { container } = render(App, { props: { pageData: allPlaced() } })
      expect(container.querySelector('.sg-end')).toBeTruthy()
      const { container: c2 } = render(App, { props: { pageData: payload() } })
      expect(c2.querySelector('.sg-end')).toBeNull()
    } finally {
      delete window.matchMedia
    }
  })

  it('tapping an unlinked tune\'s name opens the logger\'s search over the tool', async () => {
    const p = allPlaced()
    p.tunes.push(ganAinm(4, 45000))
    global.fetch = vi.fn().mockResolvedValue(jsonResponse({ success: true, results: [] }))
    const { container } = render(App, { props: { pageData: p } })
    await fireEvent.click(container.querySelector('.tl-row[data-tune-id="4"] .tl-main-unlinked'))
    await waitFor(() => expect(container.querySelector('.sg-pick .deep-field')).toBeTruthy())
    expect(container.querySelector('.sg-pick .deep-title').textContent).toBe('Which tune was this?')
    // The tool's keys are off while it is up: M must not log another tune.
    global.fetch.mockClear()
    await fireEvent.keyDown(window, { key: 'm' })
    expect(global.fetch.mock.calls.filter(([u]) => u === '/api/recordings/7/segments')).toHaveLength(0)
  })

  it('a pick names the tune through the recording API and the list adopts it', async () => {
    const p = allPlaced()
    p.tunes.push(ganAinm(4, 45000))
    const named = p.tunes.map((t) => (t.session_instance_tune_id === 4 ? { ...t, tune_id: 101, name: 'Alpha Reel', tune_type: 'Reel' } : t))
    global.fetch = vi.fn(async (url, init) => {
      if (init?.method === 'PUT') return jsonResponse({ success: true, tune: named[3], tunes: named })
      return jsonResponse({ success: true, results: [{ tune_id: 101, name: 'Alpha Reel', tune_type: 'Reel', tunebook_count: 5 }] })
    })
    const { container } = render(App, { props: { pageData: p } })
    await fireEvent.click(container.querySelector('.tl-row[data-tune-id="4"] .tl-main-unlinked'))
    await waitFor(() => expect(container.querySelector('.sg-pick .deep-card')).toBeTruthy())
    // The ＋ rail is the one-tap add.
    await fireEvent.click(container.querySelector('.sg-pick .deep-card .deep-quick'))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/recordings/7/segments/4/tune', expect.objectContaining({ method: 'PUT' })))
    const body = JSON.parse(global.fetch.mock.calls.find(([, i]) => i?.method === 'PUT')[1].body)
    expect(body).toMatchObject({ tune_id: 101, name: 'Alpha Reel' })
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="4"] .tl-name').textContent).toBe('Alpha Reel'))
    expect(container.querySelector('.tl-row[data-tune-id="4"] .tl-name.is-unlinked')).toBeNull()
  })

  it('× on a tune the tool logged removes it from the log, not just its placement', async () => {
    const p = allPlaced()
    p.tunes.push(ganAinm(4, 45000))
    global.fetch = vi.fn().mockResolvedValue(jsonResponse({ success: true, tunes: allPlaced().tunes }))
    const { container } = render(App, { props: { pageData: p } })
    const x = container.querySelector('.tl-row[data-tune-id="4"] .tl-clear')
    expect(x.title).toMatch(/Remove/)
    await fireEvent.click(x)
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/recordings/7/segments/4/unlog', expect.objectContaining({ method: 'POST' })))
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="4"]')).toBeNull())
    // A tune written on the night keeps the plain unplace.
    expect(container.querySelector('.tl-row[data-tune-id="1"] .tl-clear').title).toMatch(/Unplace/)
  })

  it('undo after a mark that logged a tune takes the tune back out', async () => {
    const p = allPlaced()
    global.fetch = vi.fn(async (url, init) => {
      if (url.endsWith('/unlog')) return jsonResponse({ success: true, tunes: allPlaced().tunes })
      return jsonResponse({ success: true, tunes: [...allPlaced().tunes, ganAinm(4, 45000)], tune: ganAinm(4, 45000) }, 201)
    })
    const { container } = render(App, { props: { pageData: p } })
    await fireEvent.keyDown(window, { key: 'm' })
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="4"]')).toBeTruthy())
    await fireEvent.keyDown(window, { key: 'u' })
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/recordings/7/segments/4/unlog', expect.anything()))
    await waitFor(() => expect(container.querySelector('.tl-row[data-tune-id="4"]')).toBeNull())
  })
})
