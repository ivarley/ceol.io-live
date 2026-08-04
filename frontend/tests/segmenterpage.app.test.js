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
    audio_url: 'blob:fake',
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
