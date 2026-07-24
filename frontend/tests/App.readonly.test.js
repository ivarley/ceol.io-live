import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/svelte'

// The live screen mounted as a LOGGED-OUT visitor (config.canEdit === false): it is the
// public session-instance page now, so it must render the log and nothing else — no
// composer, no edit affordances, no people, and no stream unless the session is
// actually under way. The server enforces all of this too (see
// tests/integration/test_live_logging_public.py); this pins the UI half.

const publicSnapshot = (over = {}) => ({
  session_id: 1,
  session_name: 'Test Session',
  session_date: '2026-02-01',
  // signed out: the server sends no person and strips people off every record
  current_person: null,
  can_edit: false,
  instance_active: false,
  last_event_id: 4,
  log_complete: false,
  notes: 'Great night',
  records: [
    { session_instance_tune_id: 1, tune_id: 11, name: 'The Silver Spear', order_position: 'A', record_type: 'tune', deleted: false, tune_type: 'Reel' },
    { session_instance_tune_id: 2, tune_id: 12, name: "Cooley's", order_position: 'B', record_type: 'tune', deleted: false, tune_type: 'Reel' },
  ],
  ...over,
})

let snapshot = publicSnapshot()
const openStream = vi.fn(() => ({ close: () => {} }))
const livePeople = vi.fn(async () => [])
const vocabulary = vi.fn(async () => ({ known_tunes: [], known_aliases: [] }))

vi.mock('../src/client.js', () => ({
  bootstrap: vi.fn(async () => snapshot),
  vocabulary: (...a) => vocabulary(...a),
  openStream: (...a) => openStream(...a),
  livePeople: (...a) => livePeople(...a),
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

const publicConfig = (over = {}) => ({
  sessionInstanceId: 90,
  sessionPath: 'austin/mueller',
  currentPerson: null,
  canEdit: false,
  instanceActive: false,
  streamingBaseUrl: 'http://stream.test/',
  trackAttendance: true,
  trackSetStarters: true,
  ...over,
})

let App
beforeEach(async () => {
  document.body.innerHTML = ''
  snapshot = publicSnapshot()
  openStream.mockClear()
  livePeople.mockClear()
  vocabulary.mockClear()
  App = (await import('../src/App.svelte')).default
})

const rows = (c) => c.querySelectorAll('.tune-row .name')

describe('live screen, signed out', () => {
  it('renders the tune log', async () => {
    const { container } = render(App, { props: { config: publicConfig() } })
    await waitFor(() => expect(rows(container).length).toBe(2))
    expect([...rows(container)].map((n) => n.textContent.trim())).toEqual(['The Silver Spear', "Cooley's"])
  })

  it('offers no way to edit', async () => {
    const { container } = render(App, { props: { config: publicConfig() } })
    await waitFor(() => expect(rows(container).length).toBe(2))
    expect(container.querySelector('.composer')).toBeNull()
    expect(container.querySelector('.editbtn')).toBeNull()
    expect(container.querySelector('.hc-mark')).toBeNull() // "mark this log complete"
    expect(container.querySelector('.hn-area')).toBeNull() // notes textarea
    expect(container.querySelector('.listmode-btn')).toBeNull() // my-list highlight
    expect(container.querySelector('main.view-mode')).toBeTruthy()
    expect(container.querySelector('.viewbar-login')).toBeTruthy()
  })

  it('shows session notes read-only when the header is expanded', async () => {
    const { container } = render(App, { props: { config: publicConfig() } })
    await waitFor(() => expect(rows(container).length).toBe(2))
    container.querySelector('.topbar-row').click()
    await waitFor(() => expect(container.querySelector('.header-notes-ro')).toBeTruthy())
    expect(container.querySelector('.header-notes-ro').textContent).toContain('Great night')
    expect(container.querySelector('.header-attend')).toBeNull()
  })

  it('never asks for people or vocabulary (both are login-gated)', async () => {
    render(App, { props: { config: publicConfig() } })
    await waitFor(() => expect(document.querySelectorAll('.tune-row').length).toBe(2))
    expect(livePeople).not.toHaveBeenCalled()
    expect(vocabulary).not.toHaveBeenCalled()
  })

  it('does not stream when the session is not under way', async () => {
    render(App, { props: { config: publicConfig() } })
    await waitFor(() => expect(document.querySelectorAll('.tune-row').length).toBe(2))
    expect(openStream).not.toHaveBeenCalled()
  })

  it('streams in view mode while the session IS under way', async () => {
    snapshot = publicSnapshot({ instance_active: true })
    render(App, { props: { config: publicConfig({ instanceActive: true }) } })
    await waitFor(() => expect(openStream).toHaveBeenCalled())
    expect(openStream.mock.calls[0][3]).toBe('view')
    // presence/typing handlers are deliberately absent: a viewer is told about neither
    const handlers = openStream.mock.calls[0][2]
    expect(handlers.onPresence).toBeUndefined()
    expect(handlers.onTyping).toBeUndefined()
  })

  it('trusts the bootstrap over the page config when the session has ended', async () => {
    // page loaded while active, bootstrap now says otherwise -> settle into static
    snapshot = publicSnapshot({ instance_active: false })
    render(App, { props: { config: publicConfig({ instanceActive: true }) } })
    await waitFor(() => expect(document.querySelectorAll('.tune-row').length).toBe(2))
    expect(openStream).not.toHaveBeenCalled()
  })
})
