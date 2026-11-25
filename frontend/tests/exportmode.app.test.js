// Export mode on the pages that have the filters (the profile's Export my data):
// `?export=1` puts the banner at the top and the bar at the bottom, quiets editing
// (no + button), and sends the FILTERED list in display order; Leave restores the
// page without a reload, keeping the filters.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import MyTunes from '../src/mytunespage/App.svelte'
import SessionPage from '../src/sessionpage/App.svelte'

const myTunesPayload = () => ({
  success: true,
  tunes: [
    { person_tune_id: 11, tune_id: 101, tune_name: "Cooley's", tune_type: 'reel', learn_status: 'want to learn', heard_count: 2, notes: null, setting_id: null, tunebook_count: 9, session_play_count: 0, instrument_status: {} },
    { person_tune_id: 12, tune_id: 102, tune_name: 'Banish Misfortune', tune_type: 'jig', learn_status: 'learned', heard_count: 0, notes: null, setting_id: 4, tunebook_count: 3, session_play_count: 1, instrument_status: {} },
    { person_tune_id: 13, tune_id: 103, tune_name: 'The Kesh', tune_type: 'jig', learn_status: 'learned', heard_count: 0, notes: null, setting_id: null, tunebook_count: 5, session_play_count: 1, instrument_status: {} },
  ],
  instruments: [{ instrument: 'Fiddle', is_auto: true }],
  pagination: { page: 1, has_next: false },
  filters: { learn_status: null, tune_type: null, search: '' },
})

const sessionPayload = () => ({
  success: true,
  session: { session_id: 7, name: 'Test Session', path: 'test', session_type: 'regular', location_name: 'The Pub', timezone: 'UTC' },
  permissions: { is_logged_in: true, is_session_admin: false, is_session_member: true, relationship: 'member', is_confirmed: true, can_view_people: true },
  today_in_session_tz: '2026-07-10',
  default_tab: 'tunes',
  tunes: [
    { tune_id: 101, tune_name: "Cooley's", tune_type: 'reel', play_count: 5, tunebook_count: 900, setting_id: null },
    { tune_id: 102, tune_name: 'Banish Misfortune', tune_type: 'jig', play_count: 2, tunebook_count: 300, setting_id: 4 },
  ],
  total_tunes_count: 2,
  has_more_tunes: false,
  popular_tunes: [],
})

const logs = {
  success: true,
  session_type: 'regular',
  sorted_years: [2025, 2024],
  instances_by_year: {
    2025: [{ date: '2025-06-01', session_instance_id: 11, multiple_on_date: false, tune_count: 3, start_time: null, end_time: null, location_override: null }],
    2024: [{ date: '2024-05-01', session_instance_id: 10, multiple_on_date: false, tune_count: 0, start_time: null, end_time: null, location_override: null }],
  },
  instances_by_day: {},
  sorted_days: [],
}

let posted
function stubFetch(routes) {
  posted = []
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url, init) => {
      const u = String(url)
      if (u.startsWith('/api/export/')) {
        posted.push([u, JSON.parse(init.body)])
        return Promise.resolve({
          ok: true,
          status: 200,
          blob: async () => new Blob(['{}'], { type: 'application/json' }),
          headers: new Headers({ 'Content-Disposition': 'attachment; filename="x.json"' }),
        })
      }
      const match = Object.keys(routes).find((k) => u.includes(k))
      const body = match ? routes[match] : { success: false, message: `no stub for ${u}` }
      return Promise.resolve({ ok: true, json: async () => (typeof body === 'function' ? body() : body) })
    })
  )
}

beforeEach(() => {
  vi.spyOn(window, 'matchMedia').mockReturnValue({ matches: false, addEventListener() {}, removeEventListener() {} })
  window.showMessage = vi.fn()
  window.TuneDetailModal = { show: vi.fn(), close: vi.fn(), getTuneIdFromUrl: () => null }
  window.TunebookStatus = { isLoaded: () => false, load: vi.fn().mockResolvedValue(), statusFor: () => 'not on list', classFor: (st) => 'ls-' + st, getInstruments: () => [] }
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
  globalThis.URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  Element.prototype.scrollIntoView = vi.fn()
  window.scrollBy = vi.fn()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.classList.remove('has-export-bar')
  window.history.replaceState({}, '', '/')
})

describe('My Tunes in export mode', () => {
  beforeEach(() => {
    stubFetch({ '/api/my-tunes': myTunesPayload() })
    window.history.replaceState({}, '', '/my-tunes?status=learned&export=1')
  })

  it('shows the banner and the bar, hides the + button, reserves room, and counts the filtered list', async () => {
    const { container } = render(MyTunes, { pageData: myTunesPayload() })
    await waitFor(() => expect(container.querySelectorAll('#tunes-grid .tune-card')).toHaveLength(2))
    expect(container.querySelector('#export-banner')).toBeInTheDocument()
    expect(container.querySelector('#export-bar')).toBeInTheDocument()
    expect(container.querySelector('#add-tune-btn')).toBeNull()
    expect(document.body.classList.contains('has-export-bar')).toBe(true)
    expect(container.querySelector('#export-download').textContent).toBe('Download 2 tunes')
    // The flag survives the page's own URL writing.
    expect(new URLSearchParams(window.location.search).get('export')).toBe('1')
    expect(new URLSearchParams(window.location.search).get('status')).toBe('learned')
  })

  it('Download posts the filtered ids in display order with the filter summary and the chosen format', async () => {
    const { container } = render(MyTunes, { pageData: myTunesPayload() })
    await waitFor(() => expect(container.querySelectorAll('#tunes-grid .tune-card')).toHaveLength(2))
    await fireEvent.click(container.querySelector('#export-bar [data-format="csv"]'))
    await fireEvent.click(container.querySelector('#export-download'))
    await waitFor(() => expect(posted).toHaveLength(1))
    const [url, body] = posted[0]
    expect(url).toBe('/api/export/my-tunes')
    expect(body.format).toBe('csv')
    expect(body.tune_ids).toEqual([102, 103]) // a-z: Banish Misfortune, The Kesh
    expect(body.filters).toEqual(['Status: Learned', 'Sort: Name (a-z), ascending'])
  })

  it('Leave drops the flag, keeps the filters, and brings the + button back without a reload', async () => {
    const { container } = render(MyTunes, { pageData: myTunesPayload() })
    await waitFor(() => expect(container.querySelector('#export-banner')).toBeInTheDocument())
    await fireEvent.click(container.querySelector('#export-leave'))
    await waitFor(() => expect(container.querySelector('#export-banner')).toBeNull())
    expect(container.querySelector('#export-bar')).toBeNull()
    expect(container.querySelector('#add-tune-btn')).toBeInTheDocument()
    expect(document.body.classList.contains('has-export-bar')).toBe(false)
    expect(window.location.search).toBe('?status=learned')
  })
})

describe('the session page in export mode', () => {
  beforeEach(() => {
    stubFetch({
      '/tunes/remaining': { success: true, tunes: [] },
      '/active_instance': { success: true, active_instance_ids: [] },
      '/logs': logs,
      '/people': { success: true, people: [] },
    })
  })

  it('on the Tunes tab: banner names the session, + is hidden, Download sends the tunes', async () => {
    window.history.replaceState({}, '', '/sessions/test/tunes?export=1')
    const { container } = render(SessionPage, { pageData: sessionPayload(), ctx: { activeTab: 'tunes' } })
    await waitFor(() => expect(container.querySelector('#export-banner')).toBeInTheDocument())
    expect(container.querySelector('#export-banner').textContent).toContain('Exporting Test Session')
    expect(container.querySelector('#add-session-tune-btn')).toBeNull()
    expect(container.querySelector('#select-tunes-btn')).toBeNull()
    await waitFor(() => expect(container.querySelector('#export-download').textContent).toBe('Download 2 tunes'))
    await fireEvent.click(container.querySelector('#export-download'))
    await waitFor(() => expect(posted).toHaveLength(1))
    expect(posted[0][0]).toBe('/api/export/sessions/test/tunes')
    expect(posted[0][1]).toMatchObject({ format: 'json', tune_ids: [101, 102], filters: ['Sort: session, descending'] })
  })

  it('on the Logs tab: counts the logged nights and sends their ids', async () => {
    window.history.replaceState({}, '', '/sessions/test/logs?export=1')
    const { container } = render(SessionPage, { pageData: sessionPayload(), ctx: { activeTab: 'logs' } })
    await waitFor(() => expect(container.querySelector('#export-download').textContent).toBe('Download 1 night'))
    expect(container.querySelector('#add-session-btn')).toBeNull()
    await fireEvent.click(container.querySelector('#export-download'))
    await waitFor(() => expect(posted).toHaveLength(1))
    expect(posted[0][0]).toBe('/api/export/sessions/test/logs')
    expect(posted[0][1]).toMatchObject({ format: 'json', instance_ids: [11], filters: ['Nights: Logged'] })
  })

  it('?tab=logs lands on the Logs tab when the path did not say', async () => {
    window.history.replaceState({}, '', '/sessions/test?tab=logs&export=1')
    const { container } = render(SessionPage, { pageData: sessionPayload(), ctx: {} })
    await waitFor(() => expect(container.querySelector('#export-download').textContent).toBe('Download 1 night'))
  })

  it('on the People tab the bar is disabled and says why', async () => {
    window.history.replaceState({}, '', '/sessions/test/people?export=1')
    const { container } = render(SessionPage, { pageData: sessionPayload(), ctx: { activeTab: 'people' } })
    await waitFor(() => expect(container.querySelector('#export-bar')).toBeInTheDocument())
    expect(container.querySelector('#export-download').disabled).toBe(true)
    expect(container.querySelector('#export-bar').textContent).toContain('Nothing to export on this tab')
  })
})
