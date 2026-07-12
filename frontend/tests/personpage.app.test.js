// Characterization tests for the person-details page view (spec 035 Step 5a):
// first paint comes from the embedded payload, the legacy DOM contract holds
// (#profileTabs ARIA tabs + #profile-tab-select mobile fallback, #edit-btn /
// #save-btn reveal, pane ids #profile/#sessions/#attended/#tunes/#logins — the
// shell's <style> block and e2e/profile select on these), and the ported flows
// (save PUT body, lazy tab loads, leave-session, add-to-session, admin-flavor
// gating, instrument editor) work.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/personpage/App.svelte'

const payload = (over = {}) => ({
  success: true,
  person: {
    id: 5,
    name: 'Ian Varley',
    first_name: 'Ian',
    last_name: 'Varley',
    email: 'ian@example.com',
    sms_number: null,
    city: 'Austin',
    state: 'TX',
    country: 'USA',
    location: 'Austin, TX, USA',
    thesession_user_id: 777,
    active: true,
    instruments: ['Fiddle', 'Whistle'],
  },
  user: {
    user_id: 9,
    username: 'ian',
    user_email: 'ian@example.com',
    email_verified: true,
    is_system_admin: false,
    is_active: true,
    created_at: '2024-01-05T10:30:00',
    last_login: '2026-07-01T20:15:00',
    timezone: 'America/Chicago',
    timezone_display: 'Central Time',
    has_password: true,
    beta_live_logging: false,
    receive_update_emails: true,
  },
  sessions: [
    {
      session_name: 'Mueller Session',
      location: 'Austin, TX, USA',
      role: 'Regular',
      is_admin: false,
      is_regular: true,
      session_path: 'austin/mueller',
    },
    {
      session_name: 'B.D. Riley’s',
      location: 'Austin, TX, USA',
      role: 'Admin',
      is_admin: true,
      is_regular: false,
      session_path: 'austin/bdrileys',
    },
  ],
  is_user_profile: true,
  is_system_admin: false,
  timezone_options: [
    { value: 'UTC', label: 'UTC (UTC+00:00)' },
    { value: 'America/Chicago', label: 'Central Time (UTC-06:00)' },
  ],
  ...over,
})

const adminPayload = (over = {}) =>
  payload({ is_user_profile: false, is_system_admin: true, ...over })

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
    '/instruments': { success: true, instruments: [{ instrument: 'Fiddle', is_auto: true, removal_loss_count: 0 }] },
    '/attended': { success: true, attendance: [] },
    '/tunes-stats': {
      success: true,
      stats: {
        total_tunes: 40,
        learned: 25,
        learning: 10,
        bookmarked: 5,
        by_type: { reel: 30, jig: 10 },
        by_type_detailed: { reel: { total: 30, learned: 20, learning: 8, bookmarked: 2 } },
      },
    },
    '/logins': { success: true, logins: [] },
    '/available-sessions': {
      success: true,
      sessions: [{ session_id: 42, name: 'Other Session', location_name: 'The Pub', location_display: 'Dublin, Ireland' }],
    },
    '/api/person/5/update': { success: true },
  }
  stubFetch()
  window.showMessage = vi.fn()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/me')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  delete window.showMessage
  document.body.classList.remove('modal-open')
})

const ctx = (over = {}) => ({ isUserProfile: true, canonicalInstruments: ['Fiddle', 'Whistle', 'Flute'], ...over })

const renderApp = (pageData = payload(), c = ctx()) => render(App, { pageData, ctx: c })

describe('person details page view (user profile flavor)', () => {
  it('first paint renders the embedded payload with the legacy DOM contract (no fetch needed)', () => {
    const { container } = renderApp()
    expect(container.querySelector('h1.docs-heading').textContent).toBe('Profile: Ian Varley')
    expect(container.querySelector('#profileTabs')).toBeTruthy()
    // Desktop = real ARIA tabs; mobile fallback = a <select>.
    const tabs = container.querySelectorAll('#profileTabs [role="tab"]')
    expect([...tabs].map((t) => t.textContent)).toEqual(['Profile', 'My Sessions', "I've Attended", 'Tunes', 'Logins'])
    expect(container.querySelector('#profile-tab-select')).toBeTruthy()
    // Profile pane active; person + account info rendered from the embed.
    expect(container.querySelector('#profile').classList.contains('active')).toBe(true)
    expect(container.querySelector('#person-display').textContent).toContain('ian@example.com')
    expect(container.querySelector('#instruments-display').textContent).toBe('Fiddle, Whistle')
    expect(container.querySelector('#user-display').textContent).toContain('Central Time')
    expect(container.querySelector('#user-display').textContent).toContain('2026-07-01 20:15')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('tab clicks activate panes, update the URL, and lazy-load exactly once', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#sessions-tab'))
    expect(container.querySelector('#sessions').classList.contains('show')).toBe(true)
    expect(new URLSearchParams(window.location.search).get('tab')).toBe('sessions')
    expect(container.querySelector('.session-card[data-session-path="austin/mueller"]')).toBeTruthy()

    // Attended lazy-loads on first activation only.
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/attended'))).toBe(false)
    await fireEvent.click(container.querySelector('#attended-tab'))
    await waitFor(() => {
      expect(container.querySelector('#attended-content .alert-info')).toBeTruthy()
    })
    const calls = () => fetch.mock.calls.filter(([u]) => String(u).includes('/attended')).length
    expect(calls()).toBe(1)
    await fireEvent.click(container.querySelector('#profile-tab'))
    expect(new URLSearchParams(window.location.search).get('tab')).toBeNull()
    await fireEvent.click(container.querySelector('#attended-tab'))
    expect(calls()).toBe(1)
  })

  it('the mobile <select> switches tabs too', async () => {
    const { container } = renderApp()
    const select = container.querySelector('#profile-tab-select')
    select.value = 'tunes'
    await fireEvent.change(select)
    expect(container.querySelector('#tunes').classList.contains('active')).toBe(true)
    await waitFor(() => {
      expect(container.querySelector('#tunes-content .stat-value')).toBeTruthy()
    })
    expect(container.querySelector('#tunes-content').textContent).toContain('40')
  })

  it('?tab= in the URL selects the initial tab without rewriting the URL', async () => {
    window.history.replaceState({}, '', '/me?tab=sessions')
    const { container } = renderApp()
    expect(container.querySelector('#sessions').classList.contains('active')).toBe(true)
    expect(container.querySelector('#profile-tab-select').value).toBe('sessions')
    expect(window.location.search).toBe('?tab=sessions')
  })

  it('Edit reveals Save/Cancel + the edit forms, loads the live instrument editor', async () => {
    const { container } = renderApp()
    expect(container.querySelector('#edit-buttons').style.display).toBe('none')
    await fireEvent.click(container.querySelector('#edit-btn'))
    expect(container.querySelector('#edit-buttons').style.display).toBe('block')
    expect(container.querySelector('#save-btn')).toBeVisible()
    expect(container.querySelector('#bottom-edit-buttons').style.display).toBe('block')
    expect(container.querySelector('#person-edit').style.display).toBe('block')
    expect(container.querySelector('#person-display').style.display).toBe('none')
    // Live instrument editor loads immediately (decoupled from Save).
    await waitFor(() => {
      expect(container.querySelector('#instrument-rows .instrument-row')).toBeTruthy()
    })
    expect(container.querySelector('.instrument-row-badge').textContent).toBe('Auto')
    // Cancel restores display mode.
    await fireEvent.click(container.querySelector('#cancel-btn'))
    expect(container.querySelector('#person-edit').style.display).toBe('none')
  })

  it('Save PUTs the legacy /api/person/<id>/update body (person + user + flags)', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#edit-btn'))
    const first = container.querySelector('#first_name')
    first.value = 'Iain'
    await fireEvent.input(first)
    const optIn = container.querySelector('#receive_update_emails')
    await fireEvent.click(optIn)
    await fireEvent.click(container.querySelector('#save-btn'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/person/5/update'))
      expect(call).toBeTruthy()
      expect(call[1].method).toBe('PUT')
      expect(JSON.parse(call[1].body)).toEqual({
        person_id: 5,
        person: {
          first_name: 'Iain',
          last_name: 'Varley',
          email: 'ian@example.com',
          sms_number: null,
          city: 'Austin',
          state: 'TX',
          country: 'USA',
          thesession_user_id: '777',
        },
        user: {
          username: 'ian',
          user_email: 'ian@example.com',
          timezone: 'America/Chicago',
          user_id: 9,
          receive_update_emails: false,
        },
      })
      expect(sessionStorage.getItem('personSavedMessage')).toBe('Profile updated successfully')
    })
  })

  it('the instrument typeahead adds an instrument and PUTs the full name list', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#edit-btn'))
    await waitFor(() => expect(container.querySelector('#instrument-rows .instrument-row')).toBeTruthy())
    const input = container.querySelector('#instrument-typeahead')
    input.value = 'Flu'
    await fireEvent.input(input)
    const options = [...container.querySelectorAll('.typeahead-option')]
    expect(options.map((o) => o.textContent)).toEqual(['Flute', 'Add "Flu"'])
    await fireEvent.click(options[0])
    await waitFor(() => {
      const put = fetch.mock.calls.find(
        ([u, init]) => String(u).includes('/api/person/5/instruments') && init && init.method === 'PUT'
      )
      expect(put).toBeTruthy()
      expect(JSON.parse(put[1].body)).toEqual({ instruments: ['Fiddle', 'Flute'] })
    })
  })

  it('user profile: leave-session button removes the card and the empty state offers the first-session link', async () => {
    fetchRoutes['/leave'] = { success: true, message: 'You have left the session' }
    const { container } = renderApp(payload({ sessions: [payload().sessions[0]] }))
    await fireEvent.click(container.querySelector('#sessions-tab'))
    await fireEvent.click(container.querySelector('.leave-session-btn'))
    // Decision -> kit Dialog (spec 035): explicit verb, no native confirm.
    await fireEvent.click(document.querySelector('.kit-dialog-confirm'))
    await waitFor(() => {
      expect(container.querySelector('.session-card')).toBeNull()
    })
    expect(container.querySelector('#sessions #add-to-session-link').textContent).toBe('add your first session')
    expect(window.showMessage).toHaveBeenCalledWith('You have left the session', 'success')
  })

  it('the add-to-session sheet searches and POSTs /api/add-person-to-session with the picked role', async () => {
    fetchRoutes['/api/add-person-to-session'] = { success: true, message: 'Added!' }
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#sessions-tab'))
    await fireEvent.click(container.querySelector('#add-to-session-link'))
    // Kit Sheet (portaled to document.body) with the legacy title + body markup.
    expect(document.querySelector('.kit-sheet-title').textContent).toBe('Add me to a Session')
    await waitFor(() => {
      expect(document.querySelector('#sessions-results .session-name').textContent).toBe('Other Session')
    })
    expect(document.querySelector('.session-location').textContent).toBe('The Pub - Dublin, Ireland')
    await fireEvent.click(document.querySelector('#role-attendee'))
    await fireEvent.click(document.querySelector('.add-session-btn'))
    // Decision -> kit Dialog (spec 035) carrying the person/session/role.
    expect(document.querySelector('.kit-dialog-title').textContent).toBe(
      'Add Ian Varley to "Other Session"?'
    )
    expect(document.querySelector('.kit-dialog-desc').textContent).toBe(
      'Ian Varley will be added as a attendee.'
    )
    await fireEvent.click(document.querySelector('.kit-dialog-confirm'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/add-person-to-session'))
      expect(call).toBeTruthy()
      expect(JSON.parse(call[1].body)).toEqual({ person_id: 5, session_id: 42, role: 'attendee' })
      expect(sessionStorage.getItem('personSavedMessage')).toBe('Added!')
    })
  })

  it('the tunes tab type filter re-slices the loaded stats and updates the tune-list link', async () => {
    const { container } = renderApp()
    await fireEvent.click(container.querySelector('#tunes-tab'))
    await waitFor(() => expect(container.querySelector('#tune-type-filter')).toBeTruthy())
    const select = container.querySelector('#tune-type-filter')
    select.value = 'reel'
    await fireEvent.change(select)
    expect(container.querySelector('.stat-value').textContent).toBe('30')
    expect(container.querySelector('a.tune-list-link').getAttribute('href')).toBe('/my-tunes?type=reel')
    // Only one fetch — the type filter is client-side.
    expect(fetch.mock.calls.filter(([u]) => String(u).includes('/tunes-stats')).length).toBe(1)
  })

  it('no user account: the "not connected" alert shows and the Logins tab is absent', () => {
    const { container } = renderApp(payload({ user: null }))
    expect(container.textContent).toContain('This person is not connected with a user account.')
    expect(container.querySelector('#logins-tab')).toBeNull()
    expect(container.querySelector('#user-edit')).toBeNull()
  })

  it('the beta live-editor toggle is self-serve: the button shows and POSTs the flip', async () => {
    fetchRoutes['/beta-logging'] = { success: true, user_id: 9, beta_live_logging: true }
    const { container } = renderApp()
    const btn = container.querySelector('#beta-logging-btn')
    expect(btn.textContent.trim()).toBe('Turn on')
    await fireEvent.click(btn)
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/beta-logging'))
      expect(call).toBeTruthy()
      expect(String(call[0])).toBe('/api/users/9/beta-logging')
      expect(JSON.parse(call[1].body)).toEqual({ enabled: true })
    })
  })
})

describe('person details page view (admin flavor)', () => {
  const renderAdmin = (pageData = adminPayload()) => renderApp(pageData, ctx({ isUserProfile: false }))

  it('renders the breadcrumb (not the Profile h1), danger zone, and admin-only account buttons', () => {
    const { container } = renderAdmin(
      adminPayload({ user: { ...payload().user, email_verified: false } })
    )
    expect(container.querySelector('h1')).toBeNull()
    expect(container.querySelector('.admin-breadcrumb')).toBeTruthy()
    expect(container.querySelector('#breadcrumb-person-name').textContent).toBe('Ian Varley')
    // Tabs use the admin labels.
    const tabs = [...container.querySelectorAll('#profileTabs [role="tab"]')].map((t) => t.textContent)
    expect(tabs).toEqual(['Profile', 'Sessions', 'Attended', 'Tunes', 'Logins'])
    // Danger zone + verify email exist only on the admin flavor; the beta
    // toggle shows on both (self-serve opt-in).
    expect(container.querySelector('#danger-zone')).toBeTruthy()
    expect(container.querySelector('#deactivate-person-btn').textContent.trim()).toBe('Deactivate Ian')
    expect(container.querySelector('#verify-email-btn')).toBeTruthy()
    expect(container.querySelector('#beta-logging-btn')).toBeTruthy()
    // No change-password link on the admin flavor.
    expect(container.textContent).not.toContain('Change My Password')
  })

  it('switching tabs nests the breadcrumb (person name becomes a link back to Profile)', async () => {
    const { container } = renderAdmin()
    await fireEvent.click(container.querySelector('#tunes-tab'))
    expect(container.querySelector('#breadcrumb-tab-name').textContent).toBe('Tunes')
    expect(container.querySelector('#breadcrumb-person-name a')).toBeTruthy()
    await fireEvent.click(container.querySelector('#breadcrumb-person-name a'))
    expect(container.querySelector('#profile').classList.contains('active')).toBe(true)
  })

  it('system admin sees the per-session Admin switch (no leave buttons) and it PUTs + updates the badge', async () => {
    fetchRoutes['/admin'] = { success: true }
    const { container } = renderAdmin()
    await fireEvent.click(container.querySelector('#sessions-tab'))
    expect(container.querySelector('.leave-session-btn')).toBeNull()
    const toggle = container.querySelector('.admin-toggle[data-session-path="austin/mueller"]')
    expect(toggle.checked).toBe(false)
    toggle.checked = true
    await fireEvent.change(toggle)
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) =>
        String(u).includes('/api/admin/sessions/austin/mueller/people/5/admin')
      )
      expect(call).toBeTruthy()
      expect(JSON.parse(call[1].body)).toEqual({ is_admin: true })
      expect(container.querySelector('.session-role-badge[data-session-path="austin/mueller"]').textContent).toBe('Admin')
    })
  })

  it('edit mode on the admin flavor exposes is_active (not receive_update_emails) and sends it', async () => {
    const { container } = renderAdmin()
    await fireEvent.click(container.querySelector('#edit-btn'))
    expect(container.querySelector('#is_active')).toBeTruthy()
    expect(container.querySelector('#receive_update_emails')).toBeNull()
    await fireEvent.click(container.querySelector('#bottom-save-btn'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/person/5/update'))
      expect(call).toBeTruthy()
      const body = JSON.parse(call[1].body)
      expect(body.user.is_active).toBe(true)
      expect(body.user).not.toHaveProperty('receive_update_emails')
    })
  })

  it('deactivate person: confirm + PUT /api/admin/person/<id>/active', async () => {
    fetchRoutes['/api/admin/person/5/active'] = { success: true, message: 'Deactivated' }
    const { container } = renderAdmin()
    await fireEvent.click(container.querySelector('#deactivate-person-btn'))
    // Destructive decision -> kit Dialog with the explicit verb.
    expect(document.querySelector('.kit-dialog-title').textContent).toBe('Deactivate Ian Varley?')
    const confirmBtn = document.querySelector('.kit-dialog-confirm')
    expect(confirmBtn.textContent.trim()).toBe('Deactivate person')
    expect(confirmBtn.classList.contains('destructive')).toBe(true)
    await fireEvent.click(confirmBtn)
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/admin/person/5/active'))
      expect(call).toBeTruthy()
      expect(JSON.parse(call[1].body)).toEqual({ active: false })
    })
  })
})
