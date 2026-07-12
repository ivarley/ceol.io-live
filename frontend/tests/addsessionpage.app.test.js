// Characterization tests for the /add-session wizard (spec 035 final migration):
// first paint comes from the embedded payload (no fetch), the legacy DOM
// contract holds (#sessionUrlForm, #sessionUrl, the "Add A New Session" h1 —
// the e2e suite selects on these), and the ported flows work: ID/URL import
// (check-existing -> fetch -> review Sheet), search results, the existing-
// session Dialog, the empty-session flow, and the gated save.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/addsessionpage/App.svelte'
import {
  parseSessionInput,
  generatePath,
  guessTimezone,
  parseTheSessionRecurrence,
  summarizeRecurrence,
} from '../src/addsessionpage/logic.js'

const payload = () => ({
  success: true,
  timezone_options: [
    { value: 'America/Chicago', label: 'US Central (UTC-06:00)' },
    { value: 'America/New_York', label: 'US Eastern (UTC-05:00)' },
    { value: 'Europe/Dublin', label: 'Ireland (UTC+00:00)' },
  ],
  default_timezone: 'America/Chicago',
  viewer: { logged_in: true },
})

const sessionData = (over = {}) => ({
  id: 1247,
  name: "B.D. Riley's",
  inception_date: '2017-04-21',
  location_name: "B.D. Riley's",
  location_phone: '512-555-1234',
  location_website: 'https://example.com',
  city: 'Austin',
  state: 'Texas',
  country: 'United States',
  recurrence: 'Every Tuesday @ 8pm',
  comments: [],
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
  window.matchMedia =
    window.matchMedia ||
    (() => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
  vi.spyOn(window, 'matchMedia').mockReturnValue({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  })
  fetchRoutes = {
    '/api/check-existing-session': { exists: false },
    '/api/fetch-session-data': { success: true, session_data: sessionData() },
    '/api/search-sessions': { success: true, results: [] },
    '/api/add-session': { success: true, session_path: 'austin/bd-rileys' },
  }
  stubFetch()
  window.history.replaceState({}, '', '/add-session')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('add-session wizard', () => {
  it('first paint renders the embedded payload with the legacy DOM contract', () => {
    const { container } = render(App, { pageData: payload() })
    expect(container.querySelector('h1.docs-heading').textContent).toBe('Add A New Session')
    expect(container.querySelector('#sessionUrlForm')).toBeTruthy()
    expect(container.querySelector('#sessionUrl')).toBeTruthy()
    // Payload-light page: first paint fires no fetch.
    expect(fetch).not.toHaveBeenCalled()
  })

  it('a thesession id opens the review sheet seeded from the fetched data', async () => {
    const { container } = render(App, { pageData: payload() })
    const input = container.querySelector('#sessionUrl')
    input.value = '1247'
    await fireEvent.input(input)
    await fireEvent.submit(container.querySelector('#sessionUrlForm'))

    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())
    expect(document.querySelector('#sessionName').value).toBe("B.D. Riley's")
    // path derives from city + name; timezone guessed from Texas
    expect(document.querySelector('#sessionPath').value).toBe('austin/bd-rileys')
    expect(document.querySelector('#timezone').value).toBe('America/Chicago')
    // "Every Tuesday @ 8pm" parses into the schedule summary
    expect(document.querySelector('#recurrence-summary-text').textContent).toBe(
      'Tuesdays from 8pm-11pm'
    )
    const posted = fetch.mock.calls.map(([u]) => String(u))
    expect(posted).toContain('/api/check-existing-session')
    expect(posted).toContain('/api/fetch-session-data')
  })

  it('an id already in the database shows the error with a link instead', async () => {
    fetchRoutes['/api/check-existing-session'] = { exists: true, session_path: '/sessions/austin/mueller' }
    const { container } = render(App, { pageData: payload() })
    const input = container.querySelector('#sessionUrl')
    input.value = '6247'
    await fireEvent.input(input)
    await fireEvent.submit(container.querySelector('#sessionUrlForm'))

    await waitFor(() => expect(container.querySelector('#errorAlert')).toBeTruthy())
    expect(container.querySelector('#errorAlert a').getAttribute('href')).toBe('/sessions/austin/mueller')
    expect(document.querySelector('#sessionDetailsForm')).toBeNull()
  })

  it('a search term lists results; picking an existing one raises the Go dialog', async () => {
    fetchRoutes['/api/search-sessions'] = {
      success: true,
      results: [
        { id: 11, name: 'Fresh Session', display_text: 'Fresh, TX', exists_in_db: false, session_path: null },
        { id: 22, name: 'Mueller Session', display_text: 'Austin, TX', exists_in_db: true, session_path: '/sessions/austin/mueller' },
      ],
    }
    const navigate = vi.fn()
    const { container } = render(App, { pageData: payload(), navigate })
    const input = container.querySelector('#sessionUrl')
    input.value = 'mueller'
    await fireEvent.input(input)
    await fireEvent.submit(container.querySelector('#sessionUrlForm'))

    await waitFor(() =>
      expect(container.querySelectorAll('#searchResultsList .search-result-item')).toHaveLength(2)
    )
    const existing = container.querySelectorAll('.search-result-item')[1]
    expect(existing.classList.contains('existing')).toBe(true)
    await fireEvent.click(existing)

    // decisions are Dialogs: confirm navigates to the existing session
    await waitFor(() => expect(document.querySelector('.kit-dialog')).toBeTruthy())
    const go = [...document.querySelectorAll('.kit-dialog button')].find((b) => b.textContent.trim() === 'Go')
    await fireEvent.click(go)
    expect(navigate).toHaveBeenCalledWith('/sessions/austin/mueller')
  })

  it('the empty-session flow validates required fields, then posts and redirects', async () => {
    const navigate = vi.fn()
    const { container } = render(App, { pageData: payload(), navigate })
    await fireEvent.click(container.querySelector('a[href="/add-session#here"]'))

    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())
    expect(document.querySelector('#sessionName').value).toBe('')

    // Save with everything empty: inline error, no POST
    await fireEvent.click(document.querySelector('#saveSessionBtn'))
    await waitFor(() =>
      expect(document.querySelector('.session-sheet-actions .field-error').textContent).toContain(
        'Name, Path, City, State, Country'
      )
    )
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/add-session'))).toBe(false)
    expect(document.querySelector('#sessionName').classList.contains('is-invalid')).toBe(true)

    // Fill the required fields and save
    for (const [id, value] of [
      ['#sessionName', 'New Session'],
      ['#sessionPath', 'testville/new-session'],
      ['#cityName', 'Testville'],
      ['#stateName', 'TX'],
      ['#countryName', 'USA'],
    ]) {
      const el = document.querySelector(id)
      el.value = value
      await fireEvent.input(el)
    }
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/sessions/testville/new-session'))
    const [, init] = fetch.mock.calls.find(([u]) => String(u).includes('/api/add-session'))
    const body = JSON.parse(init.body)
    expect(body).toMatchObject({
      name: 'New Session',
      path: 'testville/new-session',
      city: 'Testville',
      state: 'TX',
      country: 'USA',
      timezone: 'America/Chicago',
      recurrence: null,
      add_current_user: true,
      add_current_user_role: 'admin',
    })
  })

  it('a failed save keeps the sheet open with the server message', async () => {
    fetchRoutes['/api/add-session'] = { success: false, message: 'Path "x" is already taken' }
    const navigate = vi.fn()
    const { container } = render(App, { pageData: payload(), navigate })
    await fireEvent.click(container.querySelector('a[href="/add-session#here"]'))
    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())

    for (const [id, value] of [
      ['#sessionName', 'New Session'],
      ['#sessionPath', 'x'],
      ['#cityName', 'T'],
      ['#stateName', 'TX'],
      ['#countryName', 'USA'],
    ]) {
      const el = document.querySelector(id)
      el.value = value
      await fireEvent.input(el)
    }
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() =>
      expect(document.querySelector('.session-sheet-actions .field-error').textContent).toBe(
        'Path "x" is already taken'
      )
    )
    expect(navigate).not.toHaveBeenCalled()
    expect(document.querySelector('#sessionDetailsForm')).toBeTruthy()
  })
})

describe('add-session logic', () => {
  it('classifies the input box (URL, bare id, search term)', () => {
    expect(parseSessionInput('https://thesession.org/sessions/6247')).toEqual({ kind: 'id', id: '6247' })
    expect(parseSessionInput('http://thesession.org/sessions/6247/extra')).toEqual({ kind: 'id', id: '6247' })
    expect(parseSessionInput(' 1247 ')).toEqual({ kind: 'id', id: '1247' })
    expect(parseSessionInput("murphy's pub")).toEqual({ kind: 'search', query: "murphy's pub" })
  })

  it('generates city/name slugs', () => {
    expect(generatePath('Austin', "B.D. Riley's")).toBe('austin/bd-rileys')
    expect(generatePath('', 'The Session')).toBe('the-session')
    expect(generatePath('Cork', '')).toBe('cork')
  })

  it('guesses timezones from country/state', () => {
    expect(guessTimezone('Ireland', '')).toBe('Europe/Dublin')
    expect(guessTimezone('England', '')).toBe('Europe/London')
    expect(guessTimezone('United States', 'Texas')).toBe('America/Chicago')
    expect(guessTimezone('USA', 'Arizona')).toBe('America/Phoenix')
    expect(guessTimezone('France', '')).toBe('America/Chicago')
    expect(guessTimezone('France', '', 'UTC')).toBe('UTC')
  })

  it('parses thesession schedule text (weekly, nth-weekday, comments fallback)', () => {
    expect(parseTheSessionRecurrence('Every Tuesday @ 8pm', [])).toEqual({
      type: 'weekly',
      weekday: 'tuesday',
      every_n_weeks: 1,
      start_time: '20:00',
      end_time: '23:00',
    })
    expect(parseTheSessionRecurrence('First and third Mondays, 7pm to 9pm', [])).toEqual({
      type: 'monthly_nth_weekday',
      weekday: 'monday',
      which: [1, 3],
      start_time: '19:00',
      end_time: '21:00',
    })
    // no weekday anywhere -> null; weekday from comments when schedule lacks one
    expect(parseTheSessionRecurrence('', [])).toBeNull()
    expect(
      parseTheSessionRecurrence('', [{ date: '2025-01-01', content: 'We meet Sundays at 3pm now' }])
    ).toMatchObject({ type: 'weekly', weekday: 'sunday', start_time: '15:00' })
  })

  it('summarizes the editor state into the legacy summary + JSON', () => {
    expect(summarizeRecurrence({ type: '', weekday: null })).toEqual({ summary: 'No schedule set', json: null })
    expect(summarizeRecurrence({ type: 'weekly', weekday: null })).toEqual({ summary: 'Select a day...', json: null })
    const weekly = summarizeRecurrence({
      type: 'weekly', weekday: 'tuesday', frequency: 2, which: [], startTime: '19:00', endTime: '22:30',
    })
    expect(weekly.summary).toBe('Every other Tuesday from 7pm-10:30pm')
    expect(JSON.parse(weekly.json)).toEqual({
      schedules: [{ type: 'weekly', weekday: 'tuesday', start_time: '19:00', end_time: '22:30', every_n_weeks: 2 }],
    })
    const monthly = summarizeRecurrence({
      type: 'monthly_nth_weekday', weekday: 'sunday', which: [1, -1], startTime: '14:00', endTime: '17:00',
    })
    expect(monthly.summary).toBe('1st & last Sunday from 2pm-5pm')
  })
})
