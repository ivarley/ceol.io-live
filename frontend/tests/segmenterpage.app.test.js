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
