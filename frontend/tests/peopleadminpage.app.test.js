// Characterization tests for the /admin/people table (spec 035 final migration):
// first paint comes from the embedded payload, the legacy DOM contract holds
// (#people-search, #add-person-btn, #people-tbody, #addPersonModal,
// #person-input — the e2e suite selects on these), and the ported flows work:
// client-side search, column sorting (dateless rows always last), and the
// 2-step add-person wizard.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/peopleadminpage/App.svelte'

const payload = () => ({
  success: true,
  people: [
    {
      person_id: 1,
      name: 'Ian Varley',
      email: 'ian@ceol.io',
      city: 'Austin',
      state: 'TX',
      country: 'USA',
      thesession_user_id: 12345,
      username: 'ian',
      is_system_admin: true,
      last_login: '2026-07-01T10:30:00',
      session_count: 3,
      session_instance_count: 40,
      latest_session_date: '2026-06-30',
      latest_session_name: 'Mueller Session',
      tune_count: 250,
      last_logged_tune: '2026-06-30T21:15:00',
      last_tunebook_update: '2026-06-29T08:00:00',
    },
    {
      person_id: 2,
      name: 'Sarah OConnor',
      email: 'sarah@example.com',
      city: 'Dublin',
      state: null,
      country: 'Ireland',
      thesession_user_id: null,
      username: 'sarah_fiddle',
      is_system_admin: false,
      last_login: null,
      session_count: 1,
      session_instance_count: 5,
      latest_session_date: null,
      latest_session_name: null,
      tune_count: 12,
      last_logged_tune: null,
      last_tunebook_update: '2026-05-01T12:00:00',
    },
    {
      person_id: 3,
      name: 'No Account',
      email: null,
      city: null,
      state: null,
      country: null,
      thesession_user_id: null,
      username: null,
      is_system_admin: false,
      last_login: null,
      session_count: 0,
      session_instance_count: 0,
      latest_session_date: null,
      latest_session_name: null,
      tune_count: 0,
      last_logged_tune: null,
      last_tunebook_update: null,
    },
  ],
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
  window.matchMedia =
    window.matchMedia ||
    (() => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
  vi.spyOn(window, 'matchMedia').mockReturnValue({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  })
  window.showMessage = vi.fn()
  fetchRoutes = {
    '/api/sessions/list': {
      success: true,
      sessions: [{ session_id: 7, name: 'Mueller Session', display_name: 'Mueller Session (Austin, TX, USA)' }],
    },
    '/api/parse-person-name': { success: true, first_name: 'John', last_name: 'Smith', source: 'manual' },
    '/api/validate-thesession-user': { success: true, first_name: 'Jane', last_name: 'Doe', thesession_user_id: 99, source: 'thesession' },
    '/api/create-person': { success: true, message: 'John Smith has been created successfully', person_id: 42 },
    '/api/admin/people': payload(),
  }
  stubFetch()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

const rowNames = (container) =>
  [...container.querySelectorAll('#people-tbody tr .person-link')].map((a) => a.textContent)

describe('admin people table', () => {
  it('first paint renders the embedded payload with the legacy DOM contract', () => {
    const { container } = render(App, { pageData: payload() })
    expect(container.querySelectorAll('#people-tbody tr')).toHaveLength(3)
    const link = container.querySelector('#people-tbody tr .person-link')
    expect(link.textContent).toBe('Ian Varley')
    expect(link.getAttribute('href')).toBe('/admin/people/1')
    // raw payload values formatted client-side, no Date() re-parsing
    expect(container.querySelector('.person-last-login').textContent.trim()).toBe('2026-07-01 10:30')
    expect(container.querySelector('.person-latest-session').textContent.trim()).toBe('2026-06-30 - Mueller Session')
    // accountless person renders the legacy placeholders
    const last = container.querySelectorAll('#people-tbody tr')[2]
    expect(last.querySelector('.person-username').textContent.trim()).toBe('No account')
    expect(last.querySelector('.person-last-login').textContent.trim()).toBe('N/A')
    // first paint needs no fetch
    expect(fetch).not.toHaveBeenCalled()
  })

  it('search filters rows across name/email/username/location; no-match shows the notice', async () => {
    const { container } = render(App, { pageData: payload() })
    const input = container.querySelector('#people-search')

    input.value = 'dublin'
    await fireEvent.input(input)
    await waitFor(() => expect(rowNames(container)).toEqual(['Sarah OConnor']))

    input.value = 'zzz-nobody'
    await fireEvent.input(input)
    await waitFor(() => {
      expect(container.querySelectorAll('#people-tbody tr')).toHaveLength(0)
      expect(container.querySelector('#no-search-results')).toBeTruthy()
    })
  })

  it('the account droplist hides accountless people and composes with search', async () => {
    const { container } = render(App, { pageData: payload() })
    const select = container.querySelector('#people-account-filter')
    expect(select.value).toBe('all') // default shows everyone

    await fireEvent.change(select, { target: { value: 'users' } })
    await waitFor(() => expect(rowNames(container)).toEqual(['Ian Varley', 'Sarah OConnor']))

    // composes with search: "no account" matches person 3's placeholder text,
    // but the filter keeps her out
    const input = container.querySelector('#people-search')
    input.value = 'no account'
    await fireEvent.input(input)
    await waitFor(() => {
      expect(container.querySelectorAll('#people-tbody tr')).toHaveLength(0)
      expect(container.querySelector('#no-search-results')).toBeTruthy()
    })

    input.value = ''
    await fireEvent.input(input)
    await fireEvent.change(select, { target: { value: 'all' } })
    await waitFor(() => expect(rowNames(container)).toHaveLength(3))
  })

  it('sorting toggles asc/desc and always sinks dateless rows', async () => {
    const { container } = render(App, { pageData: payload() })
    const tunesHeader = container.querySelector('th[data-column="tunes"]')

    await fireEvent.click(tunesHeader)
    expect(rowNames(container)).toEqual(['No Account', 'Sarah OConnor', 'Ian Varley'])
    expect(tunesHeader.classList.contains('asc')).toBe(true)

    await fireEvent.click(tunesHeader)
    expect(rowNames(container)).toEqual(['Ian Varley', 'Sarah OConnor', 'No Account'])
    expect(tunesHeader.classList.contains('desc')).toBe(true)

    // date column: rows with no value sort last in BOTH directions
    const loginHeader = container.querySelector('th[data-column="login"]')
    await fireEvent.click(loginHeader)
    expect(rowNames(container)[0]).toBe('Ian Varley')
    expect(rowNames(container).slice(1)).toEqual(expect.arrayContaining(['Sarah OConnor', 'No Account']))
    await fireEvent.click(loginHeader)
    expect(rowNames(container)[0]).toBe('Ian Varley')
  })

  it('the add-person wizard: name path fills step 2, save posts and refreshes', async () => {
    const { container } = render(App, { pageData: payload() })
    await fireEvent.click(container.querySelector('#add-person-btn'))

    // step 1 (the legacy #addPersonModal/#person-input ids live inside the Sheet)
    await waitFor(() => expect(document.querySelector('#addPersonModal')).toBeTruthy())
    const input = document.querySelector('#person-input')
    input.value = 'John Smith'
    await fireEvent.input(input)
    await fireEvent.click(document.querySelector('#step1-next'))

    // step 2 pre-filled from the parse
    await waitFor(() => expect(document.querySelector('#add-first-name')).toBeTruthy())
    expect(document.querySelector('#add-first-name').value).toBe('John')
    expect(document.querySelector('#add-last-name').value).toBe('Smith')
    // session dropdown fed by /api/sessions/list
    expect(document.querySelectorAll('#add-session-select option')).toHaveLength(2)

    await fireEvent.click(document.querySelector('#step2-save'))
    await waitFor(() => {
      const created = fetch.mock.calls.find(([u]) => String(u).includes('/api/create-person'))
      expect(created).toBeTruthy()
      expect(JSON.parse(created[1].body)).toMatchObject({ first_name: 'John', last_name: 'Smith' })
    })
    // success refetches the table payload instead of reloading the page
    await waitFor(() =>
      expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/admin/people'))).toBe(true)
    )
    expect(window.showMessage).toHaveBeenCalledWith('John Smith has been created successfully', 'success')
  })

  it('a thesession id routes through validate-thesession-user and locks the id field', async () => {
    const { container } = render(App, { pageData: payload() })
    await fireEvent.click(container.querySelector('#add-person-btn'))
    await waitFor(() => expect(document.querySelector('#person-input')).toBeTruthy())

    const input = document.querySelector('#person-input')
    input.value = '99'
    await fireEvent.input(input)
    await fireEvent.click(document.querySelector('#step1-next'))

    await waitFor(() => expect(document.querySelector('#add-thesession-user-id')).toBeTruthy())
    expect(document.querySelector('#add-thesession-user-id').value).toBe('99')
    expect(document.querySelector('#add-first-name').value).toBe('Jane')
    const called = fetch.mock.calls.map(([u]) => String(u))
    expect(called).toContain('/api/validate-thesession-user')
  })

  it('step-1 lookup failures stay on step 1 with the server message', async () => {
    fetchRoutes['/api/parse-person-name'] = { success: false, message: 'Name cannot be empty' }
    const { container } = render(App, { pageData: payload() })
    await fireEvent.click(container.querySelector('#add-person-btn'))
    await waitFor(() => expect(document.querySelector('#person-input')).toBeTruthy())

    const input = document.querySelector('#person-input')
    input.value = 'x'
    await fireEvent.input(input)
    await fireEvent.click(document.querySelector('#step1-next'))

    await waitFor(() =>
      expect(document.querySelector('#step1-error').textContent).toBe('Name cannot be empty')
    )
    expect(document.querySelector('#add-person-form')).toBeNull()
  })
})
