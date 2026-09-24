// Characterization tests for the person-details page view (spec 035 Step 5a):
// first paint comes from the embedded payload, the legacy DOM contract holds
// (#profileTabs ARIA tabs, #edit-btn /
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
      role: 'Member',
      is_admin: false,
      relationship: 'member',
      confirmed: true,
      session_path: 'austin/mueller',
    },
    {
      session_name: 'B.D. Riley’s',
      location: 'Austin, TX, USA',
      role: 'Admin',
      is_admin: true,
      relationship: 'visitor',
      confirmed: true,
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
    '/search-sessions': {
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
    // Your profile and the account actions, and nothing else (spec 052 §B1). The
    // tab strip went first, then the section rows that replaced it: four of the five
    // were the same data framed differently and the fifth was not earning its place.
    expect(container.querySelector('#profileTabs')).toBeNull()
    expect(container.querySelector('#profile-tab-select')).toBeNull()
    expect(container.querySelector('#profile-sections')).toBeNull()
    expect(container.querySelector('#account-section')).toBeTruthy()
    // Profile content rendered from the embed.
    expect(container.querySelector('#profile').classList.contains('active')).toBe(true)
    // Connected person: the email lives on the account (User Email), not on the
    // person record — the person-level Email row is hidden.
    expect(container.querySelector('#person-display').textContent).toContain('Ian Varley')
    expect(container.querySelector('#person-display').textContent).not.toContain('ian@example.com')
    expect(container.querySelector('#user-display').textContent).toContain('ian@example.com')
    expect(container.querySelector('#instruments-display').textContent).toBe('Fiddle, Whistle')
    expect(container.querySelector('#user-display').textContent).toContain('Central Time')
    expect(container.querySelector('#user-display').textContent).toContain('2026-07-01 20:15')
    expect(fetch).not.toHaveBeenCalled()
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
          // Connected person: person.email is retired, never written back.
          email: null,
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

  it('no user account: the "not connected" alert shows and the Logins tab is absent', () => {
    const { container } = renderApp(payload({ user: null }))
    expect(container.textContent).toContain('This person is not connected with a user account.')
    expect(container.querySelector('#logins-tab')).toBeNull()
    expect(container.querySelector('#user-edit')).toBeNull()
  })

  it('the tune-logger preference is self-serve: the button shows and POSTs the flip', async () => {
    // The fixture user is opted out (beta_live_logging: false), i.e. on the legacy pill
    // editor, so the button offers the way back to the default live logger.
    fetchRoutes['/beta-logging'] = { success: true, user_id: 9, beta_live_logging: true }
    const { container } = renderApp()
    const btn = container.querySelector('#beta-logging-btn')
    expect(btn.textContent.trim()).toBe('Use live logger')
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
    // No sections and no Account list on somebody else's profile: the account
    // actions are yours, and the sections are gone for everybody.
    expect(container.querySelector('#profile-sections')).toBeNull()
    expect(container.querySelector('#account-section')).toBeNull()
    // The breadcrumb ends at the person; there is no tab left to nest under it.
    expect(container.querySelector('#breadcrumb-tab-name').textContent).toBe('')
    // Danger zone + verify email exist only on the admin flavor; the beta
    // toggle shows on both (self-serve opt-in).
    expect(container.querySelector('#danger-zone')).toBeTruthy()
    expect(container.querySelector('#deactivate-person-btn').textContent.trim()).toBe('Deactivate Ian')
    expect(container.querySelector('#verify-email-btn')).toBeTruthy()
    expect(container.querySelector('#beta-logging-btn')).toBeTruthy()
    // No change-password link on the admin flavor.
    expect(container.textContent).not.toContain('Change My Password')
  })

  it('edit mode on the admin flavor has no is_active or opt-in fields, and never sends is_active', async () => {
    const { container } = renderAdmin()
    await fireEvent.click(container.querySelector('#edit-btn'))
    // Account active is governed by the deactivate/reactivate control (in lockstep
    // with the person), not an edit-form checkbox; opt-in is self-serve only.
    expect(container.querySelector('#is_active')).toBeNull()
    expect(container.querySelector('#receive_update_emails')).toBeNull()
    await fireEvent.click(container.querySelector('#bottom-save-btn'))
    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes('/api/person/5/update'))
      expect(call).toBeTruthy()
      const body = JSON.parse(call[1].body)
      expect(body.user).not.toHaveProperty('is_active')
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
