// Characterization tests for the session-admin page view (spec 035 Step 5b):
// first paint comes from the embedded payload (details form pre-filled, timezone
// dropdown fed from the payload), tab switching stays URL-based (each tab is a
// wrapper route), and the ported flows work: details save PUT body,
// termination/reactivation, recurrence editing, people/tunes tables
// (filter/search/sort), logs + SessionInstanceModal interop + add-instance
// modal, and the local-cache preview/save.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/sessionadminpage/App.svelte'
import { extractTuneId, normalizeQuotes } from '../src/shared/parse.js'
import { formatTime } from '../src/shared/format.js'

const payload = (over = {}) => ({
  success: true,
  session: {
    session_id: 7,
    name: 'Mueller Session',
    path: 'austin/mueller',
    location_name: 'B.D. Riley’s',
    location_website: 'https://example.com',
    location_phone: '512-555-1234',
    location_street: '123 Main St',
    city: 'Austin',
    state: 'TX',
    country: 'USA',
    comments: 'Weekly session',
    unlisted_address: false,
    initiation_date: '2020-01-05',
    termination_date: null,
    recurrence: '{"schedules": [{"type": "weekly", "weekday": "tuesday", "start_time": "19:00", "end_time": "22:00", "every_n_weeks": 1}]}',
    recurrence_readable: 'Tuesdays from 7:00pm to 10:00pm',
    timezone: 'America/Chicago',
    timezone_display: 'Central Time',
    auto_create_instances: true,
    auto_create_hours_ahead: 48,
    live_cache_session_limit: 200,
    live_cache_global_limit: 25,
  },
  timezone_options: [
    { value: 'UTC', label: 'UTC (UTC+00:00)' },
    { value: 'America/Chicago', label: 'Central Time (UTC-06:00)' },
  ],
  ...over,
})

const ctx = (over = {}) => ({
  activeTab: 'details',
  sessionPath: 'austin/mueller',
  isSystemAdmin: true,
  ...over,
})

let fetchRoutes

function stubFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url) => {
      const u = String(url)
      const match = Object.keys(fetchRoutes).find((k) => u.includes(k))
      const body = match ? fetchRoutes[match] : { success: false, message: `no stub for ${u}` }
      return Promise.resolve({ ok: true, json: async () => (typeof body === 'function' ? body() : body) })
    })
  )
}

beforeEach(() => {
  fetchRoutes = {
    '/admin-update': { success: true, message: 'Saved' },
    '/people': {
      success: true,
      players: [
        { person_id: 1, name: 'Ann Malone', email: 'ann@x.com', relationship: 'member', confirmed: true, archived: false, is_admin: true, is_system_admin: false, username: 'ann', attendance_count: 9, last_attended: '2026-06-01' },
        { person_id: 2, name: 'Bob Casey', email: null, relationship: 'visitor', confirmed: false, archived: false, is_admin: false, is_system_admin: false, username: null, attendance_count: 2, last_attended: null },
      ],
    },
    '/tunes': {
      success: true,
      tunes: [
        { tune_id: 101, tune_name: "Cooley's", session_alias: '', tune_type: 'reel', session_key: 'Edor', setting_key: 'Edor', play_count: 12, want_to_learn_count: 1, learning_count: 0, learned_count: 3 },
        { tune_id: 202, tune_name: 'Banish Misfortune', session_alias: 'Banish', tune_type: 'jig', session_key: '', setting_key: 'Dmix', play_count: 4, want_to_learn_count: 0, learning_count: 2, learned_count: 0 },
      ],
    },
    '/logs': {
      success: true,
      logs: [
        { session_instance_id: 11, date: '2026-06-02', tune_count: 14, attendance_count: 6, is_cancelled: false },
        { session_instance_id: 10, date: '2026-05-26', tune_count: 0, attendance_count: 0, is_cancelled: true },
      ],
    },
    '/tune-cache': {
      success: true,
      session_count: 2,
      global_count: 1,
      tunes: [
        { tune_id: 101, name: "Cooley's", alias: null, tune_type: 'reel', tier: 'session', plays: 12 },
        { tune_id: 202, name: 'Banish Misfortune', alias: null, tune_type: 'jig', tier: 'session', plays: 4 },
        { tune_id: 303, name: 'The Kesh', alias: null, tune_type: 'jig', tier: 'global', tunebook_count: 5000 },
      ],
    },
    '/next_instance_suggestion': { success: true, date: '2026-07-14', start_time: '19:00', end_time: '22:00' },
    '/add_instance': { success: true, message: 'Instance added' },
    '/terminate': { success: true },
    '/reactivate': { success: true },
  }
  stubFetch()
  window.showMessage = vi.fn()
  window.history.replaceState({}, '', '/admin/sessions/austin/mueller')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  delete window.showMessage
})

const renderApp = (pageData = payload(), c = ctx()) => render(App, { pageData, ctx: c })

describe('session admin page view', () => {
  it('details first paint: breadcrumb, URL-based tabs, pre-filled form, payload-fed timezone dropdown', () => {
    const { container } = renderApp()
    // System-admin breadcrumb.
    const crumbs = [...container.querySelectorAll('.admin-breadcrumb a')].map((a) => a.textContent)
    expect(crumbs).toEqual(['Admin', 'Sessions'])
    expect(container.querySelector('.breadcrumb-current').textContent).toBe('Mueller Session')
    // Tabs are wrapper-route links; details is active.
    const tabs = [...container.querySelectorAll('#session-admin-tabs .nav-link')]
    expect(tabs.map((t) => t.textContent.trim())).toEqual(['Details', 'Tunes', 'Members', 'Logs', 'Local Cache'])
    expect(tabs[0].classList.contains('active')).toBe(true)
    expect(tabs[3].getAttribute('href')).toBe('/admin/sessions/austin/mueller/logs')
    // Mobile <select> mirrors the active tab.
    expect(container.querySelector('#session-admin-mobile-select').value).toBe('details')
    // Form pre-filled from the embed; timezone options come from the payload.
    expect(container.querySelector('#session-name').value).toBe('Mueller Session')
    expect(container.querySelector('#auto-create-hours').value).toBe('48')
    const tz = container.querySelector('#timezone')
    expect(tz.value).toBe('America/Chicago')
    expect([...tz.options].map((o) => o.textContent)).toEqual(['UTC (UTC+00:00)', 'Central Time (UTC-06:00)'])
    // Only the active pane is shown; nothing fetched for inactive tabs.
    expect(container.querySelector('#details').classList.contains('active')).toBe(true)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('non-system-admins get the "My Sessions" breadcrumb', () => {
    const { container } = renderApp(payload(), ctx({ isSystemAdmin: false }))
    const crumbs = [...container.querySelectorAll('.admin-breadcrumb a')].map((a) => a.textContent)
    expect(crumbs).toEqual(['My Sessions'])
  })

  it('Save Changes PUTs the legacy /admin-update body', async () => {
    const { container } = renderApp()
    const name = container.querySelector('#session-name')
    name.value = 'Renamed Session'
    await fireEvent.input(name)
    await fireEvent.submit(container.querySelector('#session-details-form'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/sessions/austin/mueller/admin-update'))
      expect(call).toBeTruthy()
      expect(call[1].method).toBe('PUT')
      expect(JSON.parse(call[1].body)).toEqual({
        name: 'Renamed Session',
        path: 'austin/mueller',
        location_name: 'B.D. Riley’s',
        location_street: '123 Main St',
        city: 'Austin',
        state: 'TX',
        country: 'USA',
        timezone: 'America/Chicago',
        location_website: 'https://example.com',
        location_phone: '512-555-1234',
        initiation_date: '2020-01-05',
        unlisted_address: false,
        comments: 'Weekly session',
        auto_create_instances: true,
        auto_create_hours_ahead: 48,
      })
      expect(window.showMessage).toHaveBeenCalledWith('Saved', 'success')
    })
  })

  it('an empty session name blocks the save with an error toast', async () => {
    const { container } = renderApp()
    const name = container.querySelector('#session-name')
    name.value = ''
    await fireEvent.input(name)
    await fireEvent.submit(container.querySelector('#session-details-form'))
    expect(window.showMessage).toHaveBeenCalledWith('Session name is required', 'error')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('termination flow: sheet requires a date, then PUTs /terminate', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#deactivate-session-link'))
    // Kit Sheet (portaled to document.body) with the destructive commit in the footer.
    expect(document.querySelector('.kit-sheet-title').textContent).toBe('Set Session End Date')
    expect(document.querySelector('#save-termination-date').textContent.trim()).toBe('Terminate session')
    // Empty date -> inline sheet error, no request.
    await fireEvent.click(document.querySelector('#save-termination-date'))
    expect(document.querySelector('#modal-error-message').textContent).toBe('Please select a date.')
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/terminate'))).toBe(false)
    // With a date -> PUT terminate.
    const date = document.querySelector('#modal-termination-date')
    date.value = '2026-07-01'
    await fireEvent.input(date)
    await fireEvent.click(document.querySelector('#save-termination-date'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/admin/sessions/austin/mueller/terminate'))
      expect(call).toBeTruthy()
      expect(JSON.parse(call[1].body)).toEqual({ termination_date: '2026-07-01' })
    })
  })

  it('terminated sessions show the termination date + reactivate link, which confirms and PUTs /reactivate', async () => {
    const p = payload()
    p.session.termination_date = '2025-12-31'
    const { container } = renderApp(p)
    expect(container.querySelector('#termination-date').value).toBe('2025-12-31')
    expect(container.querySelector('#deactivate-session-link')).toBeNull()
    await fireEvent.click(container.querySelector('#reactivate-session-link'))
    // Decision -> kit Dialog (spec 035): explicit verb, no native confirm.
    expect(document.querySelector('.kit-dialog-title').textContent).toBe('Reactivate this session?')
    await fireEvent.click(document.querySelector('.kit-dialog-confirm'))
    await waitFor(() => {
      expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/admin/sessions/austin/mueller/reactivate'))).toBe(true)
    })
  })

  it('recurrence edit mode loads the existing schedule and Save PUTs the rebuilt JSON', async () => {
    const { container } = renderApp()
    expect(container.querySelector('.recurrence-text').textContent).toBe('Tuesdays from 7:00pm to 10:00pm')
    await fireEvent.click(container.querySelector('#recurrence-readonly-view .btn'))
    // One schedule form, tuesday active, weekly options visible.
    expect(container.querySelectorAll('.schedule-form')).toHaveLength(1)
    expect(container.querySelector('.weekday-btn.active').getAttribute('data-weekday')).toBe('tuesday')
    expect(container.querySelector('#recurrence-preview-list').textContent).toContain('tuesdays from 7:00pm to 10:00pm')
    // Move it to Wednesday and save.
    await fireEvent.click(container.querySelector('.weekday-btn[data-weekday="wednesday"]'))
    await fireEvent.click(container.querySelector('#recurrence-edit-view .btn-primary:not(.btn-outline-primary)'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/admin-update'))
      expect(call).toBeTruthy()
      const body = JSON.parse(call[1].body)
      expect(Object.keys(body)).toEqual(['recurrence'])
      expect(JSON.parse(body.recurrence)).toEqual({
        schedules: [{ type: 'weekly', weekday: 'wednesday', start_time: '19:00', end_time: '22:00', every_n_weeks: 1 }],
      })
    })
  })

  it('people tab: fetches once, defaults to Members Only, search + Everyone widen/narrow the table', async () => {
    const { container } = renderApp(payload(), ctx({ activeTab: 'people' }))
    await waitFor(() => {
      expect(container.querySelectorAll('#people-content tbody tr')).toHaveLength(1)
    })
    expect(container.querySelector('.person-link').textContent.trim()).toBe('Ann Malone')
    expect(container.querySelector('.person-link').getAttribute('href')).toBe('/admin/sessions/austin/mueller/people/1')
    // Spec 034: no "Regular" badge any more -- Ann is simply a member, which is the default view.
    expect(container.querySelector('.person-status').textContent).not.toContain('Regular')
    expect(container.querySelector('.person-admin').textContent).toContain('Session')
    // Everyone shows Bob too (null email renders "No email").
    const filter = container.querySelector('#people-filter')
    filter.value = 'everyone'
    await fireEvent.change(filter)
    expect(container.querySelectorAll('#people-content tbody tr')).toHaveLength(2)
    expect(container.textContent).toContain('No email')
    // Search narrows.
    const search = container.querySelector('#people-search')
    search.value = 'bob'
    await fireEvent.input(search)
    expect(container.querySelectorAll('#people-content tbody tr')).toHaveLength(1)
    expect(container.querySelector('.person-name').textContent).toContain('Bob Casey')
  })

  it('people tab: clicking a column header sorts, clicking again flips direction', async () => {
    const { container } = renderApp(payload(), ctx({ activeTab: 'people' }))
    await waitFor(() => expect(container.querySelector('#people-content tbody tr')).toBeTruthy())
    const filter = container.querySelector('#people-filter')
    filter.value = 'everyone'
    await fireEvent.change(filter)
    const attendanceHeader = [...container.querySelectorAll('th')].find((th) => th.textContent.startsWith('Attendance'))
    await fireEvent.click(attendanceHeader)
    let names = [...container.querySelectorAll('.person-name')].map((td) => td.textContent.trim())
    expect(names).toEqual(['Bob Casey', 'Ann Malone']) // asc by attendance (2, 9)
    await fireEvent.click(attendanceHeader)
    names = [...container.querySelectorAll('.person-name')].map((td) => td.textContent.trim())
    expect(names).toEqual(['Ann Malone', 'Bob Casey']) // desc
    expect(attendanceHeader.textContent).toContain('↓')
  })

  it('tunes tab: renders the grid and search matches text or a thesession URL/id', async () => {
    const { container } = renderApp(payload(), ctx({ activeTab: 'tunes' }))
    await waitFor(() => {
      expect(container.querySelectorAll('#tunes-table tbody tr')).toHaveLength(2)
    })
    // Default alpha sort: Banish first.
    expect(container.querySelector('.tune-name a').textContent.trim()).toBe('Banish Misfortune')
    expect(container.querySelector('.tune-name a').getAttribute('href')).toBe('/sessions/austin/mueller/tunes/202')
    // Free-text search.
    const search = container.querySelector('#tunes-search')
    search.value = 'cooley'
    await fireEvent.input(search)
    expect(container.querySelectorAll('#tunes-table tbody tr')).toHaveLength(1)
    // thesession URL search resolves to the tune id.
    search.value = 'https://thesession.org/tunes/202'
    await fireEvent.input(search)
    expect(container.querySelectorAll('#tunes-table tbody tr')).toHaveLength(1)
    expect(container.querySelector('.tune-name a').textContent.trim()).toBe('Banish Misfortune')
  })

  it('logs tab: rows open the instance sheet; the add-instance sheet prefills the suggestion and POSTs', async () => {
    const { container } = renderApp(payload(), ctx({ activeTab: 'logs' }))
    await waitFor(() => {
      expect(container.querySelectorAll('#logs-table .log-row')).toHaveLength(2)
    })
    expect(container.querySelector('.log-row[data-instance-id="10"] .log-status').textContent).toContain('Cancelled')
    // Row click opens the bundled InstanceSheet (kit Sheet, portaled to document.body),
    // which loads its details from the same admin logs endpoint.
    await fireEvent.click(container.querySelector('.log-row[data-instance-id="11"]'))
    await waitFor(() => {
      expect(document.querySelector('.instance-info-value a')).toBeTruthy()
    })
    expect(document.querySelector('.instance-modal-subtitle').textContent).toBe('austin/mueller')
    expect(document.querySelector('.instance-info-value a').textContent).toContain('14 tunes')
    expect(document.querySelector('.instance-info-value a').getAttribute('href')).toBe('/sessions/austin/mueller/2026-06-02')
    expect(document.querySelector('.instance-status-badge').textContent.trim()).toBe('Held')
    // Close it (kit Cancel) before exercising the add-instance sheet.
    await fireEvent.click(document.querySelector('.kit-sheet-cancel'))

    await fireEvent.click(container.querySelector('#add-session-instance-btn'))
    await waitFor(() => {
      expect(document.querySelector('#session-date-input').value).toBe('2026-07-14')
      expect(document.querySelector('#session-start-time-input').value).toBe('19:00')
    })
    expect(document.querySelector('#session-location-input').placeholder).toBe('The usual: B.D. Riley’s')
    await fireEvent.click(document.querySelector('#add-session-confirm-btn'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/add_instance'))
      expect(call).toBeTruthy()
      expect(JSON.parse(call[1].body)).toEqual({ date: '2026-07-14', start_time: '19:00', end_time: '22:00' })
      expect(window.showMessage).toHaveBeenCalledWith('Instance added', 'success')
    })
    // Sheet closed + logs re-fetched (initial load, the instance sheet's detail
    // fetch, then the reload after adding).
    expect(document.querySelector('#session-date-input')).toBeNull()
    expect(fetch.mock.calls.filter(([u]) => String(u).includes('/api/admin/sessions/austin/mueller/logs')).length).toBe(3)
  })

  it('logs tab: ?instance= deep link auto-opens the instance sheet and clears the querystring', async () => {
    window.history.replaceState({}, '', '/admin/sessions/austin/mueller/logs?instance=10')
    renderApp(payload(), ctx({ activeTab: 'logs' }))
    await waitFor(() => {
      expect(document.querySelector('.instance-status-badge')).toBeTruthy()
    })
    expect(document.querySelector('.instance-status-badge').textContent.trim()).toBe('Cancelled')
    expect(document.querySelector('.instance-info-value a').getAttribute('href')).toBe('/sessions/austin/mueller/2026-05-26')
    expect(window.location.search).toBe('')
  })

  it('cache tab: loads the preview with n/m, renders the summary + tiers, and Save PUTs the limits', async () => {
    const { container } = renderApp(payload(), ctx({ activeTab: 'cache' }))
    await waitFor(() => {
      expect(container.querySelectorAll('#cache-table tbody tr')).toHaveLength(3)
    })
    const previewCall = fetch.mock.calls.find(([u]) => String(u).includes('/tune-cache'))
    expect(String(previewCall[0])).toContain('n=200')
    expect(String(previewCall[0])).toContain('m=25')
    expect(container.querySelector('#cache-summary').textContent.replace(/\s+/g, ' ')).toContain(
      'Caching 2 session tunes + 1 globally-popular = 3 total'
    )
    expect(container.querySelectorAll('#cache-table .badge-primary')).toHaveLength(2)
    expect(container.querySelector('#cache-table').textContent).toContain('5,000 tunebooks')

    const n = container.querySelector('#cache-session-limit')
    n.value = '50'
    await fireEvent.input(n)
    await fireEvent.click(container.querySelector('#cache-save-btn'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u, init]) => String(u).includes('/admin-update') && init?.method === 'PUT')
      expect(call).toBeTruthy()
      expect(JSON.parse(call[1].body)).toEqual({ live_cache_session_limit: 50, live_cache_global_limit: 25 })
      expect(window.showMessage).toHaveBeenCalledWith('Local cache settings saved', 'success')
    })
  })
})

describe('session admin logic helpers', () => {
  it('extractTuneId accepts bare ids and thesession URLs', () => {
    expect(extractTuneId('123')).toBe(123)
    expect(extractTuneId(' https://thesession.org/tunes/456 ')).toBe(456)
    expect(extractTuneId('cooley')).toBeNull()
    expect(extractTuneId('')).toBeNull()
  })

  it('normalizeQuotes straightens smart quotes', () => {
    expect(normalizeQuotes('O’Neill “the collector”')).toBe('O\'Neill "the collector"')
  })

  it('formatTime renders 12-hour am/pm', () => {
    expect(formatTime('19:00')).toBe('7:00pm')
    expect(formatTime('00:30')).toBe('12:30am')
    expect(formatTime('12:15')).toBe('12:15pm')
  })
})
