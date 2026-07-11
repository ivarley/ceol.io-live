// Characterization tests for the session-detail page view (spec 035 Step 4b):
// first paint comes from the embedded payload, the legacy DOM contract holds
// (#tunes-list, .tune-row[data-tune-id], #results-count-text, .tab-button[data-tab],
// year sections — the shell's <style> block and the e2e suite select on these),
// and the ported flows (remaining merge, selection/copy, logs, deep links) work.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/sessionpage/App.svelte'

const payload = (over = {}) => ({
  success: true,
  session: {
    session_id: 7,
    name: 'Test Session',
    path: 'test',
    session_type: 'regular',
    location_name: 'The Pub',
    timezone: 'UTC',
  },
  permissions: { is_logged_in: true, is_session_admin: false, is_session_member: true },
  today_in_session_tz: '2026-07-10',
  default_tab: 'tunes',
  tunes: [
    { tune_id: 101, tune_name: "Cooley's", tune_type: 'reel', play_count: 5, tunebook_count: 900, setting_id: null },
    { tune_id: 102, tune_name: 'Banish Misfortune', tune_type: 'jig', play_count: 2, tunebook_count: 300, setting_id: 4 },
  ],
  total_tunes_count: 2,
  has_more_tunes: false,
  popular_tunes: [],
  ...over,
})

const regularLogs = {
  success: true,
  session_type: 'regular',
  sorted_years: [2025, 2024],
  instances_by_year: {
    2025: [
      { date: '2025-06-01', session_instance_id: 11, multiple_on_date: false, tune_count: 3, start_time: null, end_time: null, location_override: null },
    ],
    2024: [
      { date: '2024-05-01', session_instance_id: 10, multiple_on_date: false, tune_count: 0, start_time: null, end_time: null, location_override: null },
    ],
  },
  instances_by_day: {},
  sorted_days: [],
}

const festivalLogs = {
  success: true,
  session_type: 'festival',
  sorted_years: [],
  instances_by_year: {},
  sorted_days: ['2025-06-01'],
  instances_by_day: {
    '2025-06-01': [
      { date: '2025-06-01', session_instance_id: 21, multiple_on_date: false, tune_count: 0, start_time: '19:00:00', end_time: '22:00:00', location_override: null },
    ],
  },
}

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
    '/tunes/remaining': { success: true, tunes: [] },
    '/active_instance': { success: true, active_instance_ids: [] },
    '/logs': regularLogs,
    '/people': { success: true, people: [] },
    '/api/user/admin-sessions': { success: true, sessions: [{ path: 'other', name: 'Other Session' }] },
    '/api/tunes/copy': { success: true, message: 'Copied 2 tunes', redirect_url: '/my-tunes' },
  }
  stubFetch()
  window.showMessage = vi.fn()
  window.TuneDetailModal = { show: vi.fn(), close: vi.fn() }
  window.TunebookStatus = {
    isLoaded: () => false,
    load: vi.fn().mockResolvedValue(),
    statusFor: () => 'not on list',
    classFor: (st) => 'ls-' + st.replace(/ /g, '-'),
    getInstruments: () => [],
  }
  sessionStorage.clear()
  // jsdom implements neither; the ?show= landing flow calls both.
  Element.prototype.scrollIntoView = vi.fn()
  window.scrollBy = vi.fn()
  window.history.replaceState({}, '', '/sessions/test/tunes')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  delete window.TuneDetailModal
  delete window.TunebookStatus
  delete window.showMessage
  delete window.SessionTuneAddPane
})

const renderApp = (pageData = payload(), ctx = { activeTab: 'tunes' }) =>
  render(App, { pageData, ctx })

describe('session detail page view', () => {
  it('first paint renders the embedded tunes with the legacy DOM contract (no fetch needed)', () => {
    const { container } = renderApp()
    const rows = container.querySelectorAll('#tunes-list .tune-row')
    expect(rows).toHaveLength(2)
    // Default sort session-desc: Cooley's (5 plays) first, with its play-count badge.
    expect(rows[0].getAttribute('data-tune-id')).toBe('101')
    expect(rows[0].querySelector('.tune-name').textContent).toBe("Cooley's")
    expect(rows[0].querySelector('.tune-count-badge').textContent).toBe('5')
    expect(container.querySelector('#results-count-text').textContent).toBe('2 tunes')
    // has_more_tunes false: no /tunes/remaining call.
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/tunes/remaining'))).toBe(false)
  })

  it('merges /tunes/remaining rows (dicts) into the list', async () => {
    fetchRoutes['/tunes/remaining'] = {
      success: true,
      tunes: [{ tune_id: 103, tune_name: 'The Ashplant', tune_type: 'reel', play_count: 1, tunebook_count: 50, setting_id: null }],
    }
    const { container } = renderApp(payload({ has_more_tunes: true, total_tunes_count: 3 }))
    await waitFor(() => {
      expect(container.querySelectorAll('#tunes-list .tune-row')).toHaveLength(3)
    })
    expect(container.querySelector('.tune-row[data-tune-id="103"] .tune-name').textContent).toBe('The Ashplant')
    expect(container.querySelector('#results-count-text').textContent).toBe('3 tunes')
  })

  it('search filters the rows (debounced) and round-trips through the URL', async () => {
    vi.useFakeTimers()
    try {
      const { container } = renderApp()
      const input = container.querySelector('#tune-search')
      input.value = 'Banish'
      input.dispatchEvent(new Event('input', { bubbles: true }))
      await vi.advanceTimersByTimeAsync(350)
      await vi.waitFor(() => {
        expect(container.querySelectorAll('#tunes-list .tune-row')).toHaveLength(1)
        expect(container.querySelector('.tune-row[data-tune-id="102"]')).toBeTruthy()
      })
      expect(container.querySelector('#results-count-text').textContent).toBe('Showing 1 of 2 tunes')
      expect(new URLSearchParams(window.location.search).get('search')).toBe('banish')
    } finally {
      vi.useRealTimers()
    }
  })

  it('reads initial filter/sort state from the URL', () => {
    window.history.replaceState({}, '', '/sessions/test/tunes?type=jig&sortType=alpha&sortDir=asc')
    const { container } = renderApp()
    const rows = container.querySelectorAll('#tunes-list .tune-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].getAttribute('data-tune-id')).toBe('102')
    // Alpha sort shows no count badge, just the type.
    expect(rows[0].querySelector('.tune-count-badge')).toBeNull()
    expect(rows[0].querySelector('.tune-type').textContent).toBe('jig')
  })

  it('sort mode buttons switch the badge column (session plays vs everywhere tunebooks)', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#filter-panel-toggle'))
    expect(container.querySelector('#filter-panel')).toBeTruthy()
    await fireEvent.click(container.querySelector('.filter-sort-btn[data-sort="everywhere"]'))
    const first = container.querySelector('#tunes-list .tune-row')
    expect(first.getAttribute('data-tune-id')).toBe('101')
    expect(first.querySelector('.tune-count-badge').textContent).toBe('900')
    // Clicking the active mode again toggles direction.
    await fireEvent.click(container.querySelector('.filter-sort-btn[data-sort="everywhere"]'))
    expect(container.querySelector('#tunes-list .tune-row').getAttribute('data-tune-id')).toBe('102')
    expect(container.querySelector('#sort-direction-icon').textContent).toBe('↑')
  })

  it('selection mode + the Copy To flow: select, confirm, POST, sessionStorage handoff', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#filter-panel-toggle'))
    await fireEvent.click(container.querySelector('#select-tunes-btn'))
    expect(container.querySelector('#select-all-row').classList.contains('visible')).toBe(true)
    expect(container.querySelector('#copy-to-btn').disabled).toBe(true)

    // Row click toggles selection instead of opening the modal.
    await fireEvent.click(container.querySelector('.tune-row[data-tune-id="101"]'))
    expect(window.TuneDetailModal.show).not.toHaveBeenCalled()
    expect(container.querySelector('.tune-select-checkbox[data-tune-id="101"]').checked).toBe(true)
    expect(container.querySelector('#copy-to-btn').disabled).toBe(false)

    await fireEvent.click(container.querySelector('#copy-to-btn'))
    await waitFor(() => {
      expect(container.querySelector('#copy-modal-overlay').classList.contains('hidden')).toBe(false)
      expect(container.textContent).toContain('Other Session')
    })
    expect(container.querySelector('#copy-next-btn').disabled).toBe(true)

    // Pick My Tunes (learn-status step appears), go to confirmation, copy.
    await fireEvent.click(container.querySelector('.copy-destination-option'))
    expect(container.querySelector('#my-tunes-status-options').classList.contains('visible')).toBe(true)
    await fireEvent.click(container.querySelector('#copy-next-btn'))
    expect(container.querySelector('#copy-confirm-message').textContent).toContain(
      '1 tune will be copied to My Tunes (as "want to learn")'
    )
    await fireEvent.click(container.querySelector('#copy-confirm-btn'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/tunes/copy'))
      expect(call).toBeTruthy()
      expect(JSON.parse(call[1].body)).toMatchObject({
        tune_ids: [101],
        destination_type: 'my_tunes',
        learn_status: 'want to learn',
      })
      expect(sessionStorage.getItem('copyTunesMessage')).toBe('Copied 2 tunes')
    })
  })

  it('lazy-loads and renders regular logs (years, counts, empty-log dimming)', async () => {
    const { container } = renderApp(payload(), { activeTab: 'logs' })
    await waitFor(() => {
      expect(container.querySelectorAll('#logs-tab .year-section')).toHaveLength(2)
    })
    expect(container.querySelector('.year-title').textContent).toBe('2025')
    const link2025 = container.querySelector('a[data-instance-id="11"]')
    expect(link2025.getAttribute('href')).toBe('/sessions/test/2025-06-01')
    expect(link2025.classList.contains('empty-log')).toBe(false)
    expect(container.querySelector('#logs-tab').textContent).toContain('(3 tunes logged)')
    expect(container.querySelector('a[data-instance-id="10"]').classList.contains('empty-log')).toBe(true)
    // Latest year gets the Add link (logged in).
    expect(container.querySelector('.year-add-link#add-session-btn')).toBeTruthy()
    // Collapsing a year hides its rows.
    await fireEvent.click(container.querySelector('.year-toggle[data-year="2025"]'))
    expect(container.querySelector('.year-toggle[data-year="2025"]').textContent).toBe('▶')
    expect(container.querySelector('.year-content-row[data-year="2025"]').style.display).toBe('none')
  })

  it('festival sessions label the logs tab "Sessions", order it first, and render by day', async () => {
    fetchRoutes['/logs'] = festivalLogs
    const { container } = renderApp(
      payload({
        session: { ...payload().session, session_type: 'festival' },
        default_tab: 'logs',
      }),
      { activeTab: null }
    )
    const buttons = container.querySelectorAll('.tab-button')
    expect(buttons[0].textContent).toBe('Sessions')
    expect(buttons[0].getAttribute('data-tab')).toBe('logs')
    expect(buttons[0].classList.contains('active')).toBe(true)
    await waitFor(() => {
      expect(container.querySelector('#logs-tab .year-title')).toBeTruthy()
    })
    expect(container.querySelector('.year-title').textContent).toContain('2025')
    expect(container.querySelector('.instance-location-cell a').textContent.trim()).toBe('The Pub')
    expect(container.querySelector('.instance-time-cell').textContent).toBe('7:00pm-10:00pm')
  })

  it('tab switching pushes a path-based URL and lazy-loads the target tab', async () => {
    const { container } = renderApp()
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/sessions/test/logs'))).toBe(false)
    await fireEvent.click(container.querySelector('.tab-button[data-tab="logs"]'))
    expect(window.location.pathname).toBe('/sessions/test/logs')
    expect(container.querySelector('#logs-tab').classList.contains('active')).toBe(true)
    expect(container.querySelector('#tunes-tab').classList.contains('active')).toBe(false)
    await waitFor(() => {
      expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/sessions/test/logs'))).toBe(true)
    })
  })

  it('a deep-linked tune id opens the shared drawer with the session context', async () => {
    renderApp(payload(), { activeTab: 'tunes', tuneId: 102 })
    await waitFor(() => {
      expect(window.TuneDetailModal.show).toHaveBeenCalledWith(
        expect.objectContaining({
          context: 'session',
          tuneId: 102,
          apiEndpoint: '/api/sessions/test/tunes/102',
        })
      )
    })
  })

  it('clicking a row (outside selection mode) opens the drawer', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('.tune-row[data-tune-id="101"]'))
    expect(window.TuneDetailModal.show).toHaveBeenCalledWith(
      expect.objectContaining({ context: 'session', tuneId: 101 })
    )
  })

  it('the People tab (members only) fetches and renders people on first view', async () => {
    fetchRoutes['/people'] = {
      success: true,
      people: [
        { person_id: 1, first_name: 'Ann', last_name: 'Malone', instruments: ['Fiddle'], is_regular: true, has_user_account: true, attendance_count: 4 },
      ],
    }
    const { container } = renderApp()
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/sessions/test/people'))).toBe(false)
    await fireEvent.click(container.querySelector('.tab-button[data-tab="people"]'))
    await waitFor(() => {
      expect(container.querySelector('#people-list .person-row .person-name').textContent).toBe('Ann Malone')
    })
    expect(container.querySelector('.person-attendance-badge').textContent).toBe('4')
  })

  it('logged out: public tunes+logs, no People tab, no add/selection affordances', () => {
    const { container } = renderApp(
      payload({ permissions: { is_logged_in: false, is_session_admin: false, is_session_member: false } })
    )
    expect(container.querySelector('.tab-button[data-tab="people"]')).toBeNull()
    expect(container.querySelector('#add-session-tune-btn')).toBeNull()
    expect(container.querySelector('#copy-modal-overlay')).toBeNull()
    expect(container.querySelectorAll('#tunes-list .tune-row')).toHaveLength(2)
  })

  it('the add-tune button opens window.SessionTuneAddPane with the current query', async () => {
    window.SessionTuneAddPane = { open: vi.fn() }
    const { container } = renderApp()
    const input = container.querySelector('#tune-search')
    input.value = 'kesh'
    await fireEvent.input(input)
    await fireEvent.click(container.querySelector('#add-session-tune-btn'))
    expect(window.SessionTuneAddPane.open).toHaveBeenCalledWith(
      expect.objectContaining({ sessionPath: 'test', query: 'kesh' })
    )
  })

  it('?added= landing shows the success toast', () => {
    window.history.replaceState({}, '', '/sessions/test/tunes?show=101&added=Cooley%27s')
    renderApp()
    expect(window.showMessage).toHaveBeenCalledWith('Successfully added "Cooley\'s" to the session!', 'success')
  })
})
