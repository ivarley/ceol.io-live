import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/svelte'
import { openStream } from '../src/client.js'

// ?edit=1 opens the logger straight in edit mode. The segmenter's "Fix the log"
// is the caller (spec 050): timestamping is where you discover a tune nobody
// wrote down, and landing in view mode would cost a tap before the one-line
// correction that was the whole point of the trip.
//
// Three things are worth pinning: the stream is opened ALREADY in edit mode
// (rather than connecting as a viewer and immediately reconnecting), the flag
// does not survive in the URL, and it cannot unlock a log that is finished.

let snapshot
const makeSnapshot = (over = {}) => ({
  session_id: 1,
  session_name: 'Test Session',
  session_date: 'Sun · Feb 1, 2026',
  instance_date: '2026-02-01',
  current_person: { person_id: 2, first_name: 'Ian' },
  last_event_id: 0,
  log_complete: false,
  records: [
    { session_instance_tune_id: 1, tune_id: 11, name: 'The Silver Spear', order_position: 'A', record_type: 'tune', deleted: false, tune_type: 'Reel' },
  ],
  ...over,
})

vi.mock('../src/client.js', () => ({
  bootstrap: vi.fn(async () => snapshot),
  vocabulary: vi.fn(async () => ({ known_tunes: [], known_aliases: [] })),
  openStream: vi.fn(() => ({ close: () => {} })),
  livePeople: vi.fn(async () => []),
  peopleSearch: vi.fn(async () => []),
  sendOp: vi.fn(async () => ({ success: true })),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
  myTunesList: vi.fn(async () => ({ tunes: [] })),
  myTunesOp: vi.fn(async () => ({ success: true })),
  probeServers: vi.fn(async () => ({ app: true, stream: true })),
}))

const config = (over = {}) => ({
  sessionInstanceId: 90,
  sessionPath: 'austin/mueller',
  instanceDate: '2026-02-01',
  currentPerson: { person_id: 2, first_name: 'Ian' },
  canEdit: true,
  streamingBaseUrl: 'http://stream.test/',
  ...over,
})

let App
beforeEach(async () => {
  document.body.innerHTML = ''
  snapshot = makeSnapshot()
  vi.mocked(openStream).mockClear()
  window.history.replaceState({}, '', '/live/instances/90?edit=1')
  App = (await import('../src/App.svelte')).default
})

afterEach(() => {
  window.history.replaceState({}, '', '/')
})

describe('?edit=1 (spec 050 round trip)', () => {
  it('opens in edit mode', async () => {
    const { container } = render(App, { props: { config: config() } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
    expect(container.querySelector('.composer')).toBeTruthy()
    expect(container.querySelector('main.view-mode')).toBeNull()
  })

  it('opens the stream already in edit mode, not as a viewer first', async () => {
    // Asserted on the stream rather than only on the UI: setting the mode after
    // connecting would open it as a viewer and immediately re-open it, and the
    // server reads presence off that flag -- so a 'view' anywhere in this list
    // is the bug, whatever else reconnects during the test.
    render(App, { props: { config: config() } })
    await waitFor(() => expect(openStream).toHaveBeenCalled())
    expect(openStream.mock.calls.map((c) => c[3])).not.toContain('view')
    expect(openStream.mock.calls[0][3]).toBe('edit')
  })

  it('strips the flag from the URL so a reload does not re-assert it', async () => {
    const { container } = render(App, { props: { config: config() } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
    expect(window.location.search).toBe('')
  })

  it('is ignored on a finished log — completion locks editing for everyone', async () => {
    snapshot = makeSnapshot({ log_complete: true })
    const { container } = render(App, { props: { config: config() } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
    expect(container.querySelector('.composer')).toBeNull()
    expect(container.querySelector('main.view-mode')).toBeTruthy()
  })

  it('is ignored when signed out', async () => {
    snapshot = makeSnapshot({ current_person: null, can_edit: false })
    const { container } = render(App, { props: { config: config({ canEdit: false, currentPerson: null }) } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
    expect(container.querySelector('.composer')).toBeNull()
    expect(container.querySelector('main.view-mode')).toBeTruthy()
  })

  it('leaves an ordinary visit in view mode', async () => {
    window.history.replaceState({}, '', '/live/instances/90')
    const { container } = render(App, { props: { config: config() } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
    expect(container.querySelector('main.view-mode')).toBeTruthy()
  })
})
