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
    // path derives from city + name and shows read-only; timezone guessed from Texas
    expect(document.querySelector('#sessionPathValue').textContent).toBe(
      '/sessions/austin/bd-rileys'
    )
    expect(document.querySelector('#sessionPath')).toBeNull()
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

    // The path is generated, so it isn't one of the fields you're asked to supply
    await fireEvent.click(document.querySelector('#saveSessionBtn'))
    await waitFor(() =>
      expect(document.querySelector('.session-sheet-actions .field-error').textContent).toContain(
        'Name, City, State, Country'
      )
    )
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/add-session'))).toBe(false)
    expect(document.querySelector('#sessionName').classList.contains('is-invalid')).toBe(true)
    expect(document.querySelector('#sessionPathValue').textContent).toBe(
      'Enter a name and city first'
    )

    // Fill the required fields and save — the path follows from name + city
    for (const [id, value] of [
      ['#sessionName', 'New Session'],
      ['#cityName', 'Testville'],
      ['#stateName', 'TX'],
      ['#countryName', 'USA'],
    ]) {
      const el = document.querySelector(id)
      el.value = value
      await fireEvent.input(el)
    }
    expect(document.querySelector('#sessionPathValue').textContent).toBe(
      '/sessions/testville/new-session'
    )
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
      // Editable here too, defaulting to unlinked / regular / the 60-minute window.
      session_type: 'regular',
      active_buffer_minutes_before: 60,
      active_buffer_minutes_after: 60,
    })
  })

  it('carries an edited thesession link, type and active window into the POST', async () => {
    const navigate = vi.fn()
    const { container } = render(App, { pageData: payload(), navigate })
    await fireEvent.click(container.querySelector('a[href="/add-session#here"]'))
    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())

    for (const [id, value] of [
      ['#sessionName', 'Festival Session'],
      ['#cityName', 'Testville'],
      ['#stateName', 'TX'],
      ['#countryName', 'USA'],
      ['#thesessionId', 'https://thesession.org/sessions/6247'],
      ['#activeBufferBefore', '30'],
    ]) {
      const el = document.querySelector(id)
      el.value = value
      await fireEvent.input(el)
    }
    const type = document.querySelector('#sessionType')
    type.value = 'festival'
    await fireEvent.change(type)
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() =>
      expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/add-session'))).toBe(true)
    )
    const [, init] = fetch.mock.calls.find(([u]) => String(u).includes('/api/add-session'))
    expect(JSON.parse(init.body)).toMatchObject({
      thesession_id: 'https://thesession.org/sessions/6247',
      session_type: 'festival',
      active_buffer_minutes_before: 30,
      active_buffer_minutes_after: 60,
    })
  })

  it('refuses to post a tune URL as the thesession link', async () => {
    const { container } = render(App, { pageData: payload(), navigate: vi.fn() })
    await fireEvent.click(container.querySelector('a[href="/add-session#here"]'))
    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())

    for (const [id, value] of [
      ['#sessionName', 'Tune Link Session'],
      ['#cityName', 'Testville'],
      ['#stateName', 'TX'],
      ['#countryName', 'USA'],
      ['#thesessionId', 'https://thesession.org/tunes/182'],
    ]) {
      const el = document.querySelector(id)
      el.value = value
      await fireEvent.input(el)
    }
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    expect(document.querySelector('.session-sheet-actions .field-error').textContent).toContain(
      'thesession.org/sessions/1234'
    )
    expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/add-session'))).toBe(false)
    expect(document.querySelector('#thesessionId').classList.contains('is-invalid')).toBe(true)
  })

  // A path like "/" or "." is non-empty, so the old required-fields check passed
  // it — but it resolves to nothing as a URL, and since every admin route is keyed
  // on the path, the session lands with no screen that can repair it.
  it.each([['/'], ['.'], ['austin/'], ['austin mueller']])(
    'refuses to post an unusable path (%s)',
    async (badPath) => {
      const navigate = vi.fn()
      const { container } = render(App, { pageData: payload(), navigate })
      await fireEvent.click(container.querySelector('a[href="/add-session#here"]'))
      await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())

      for (const [id, value] of [
        ['#sessionName', 'New Session'],
        ['#cityName', 'Testville'],
        ['#stateName', 'TX'],
        ['#countryName', 'USA'],
      ]) {
        const el = document.querySelector(id)
        el.value = value
        await fireEvent.input(el)
      }
      // An unusable path can only be reached deliberately now, via Edit
      await fireEvent.click(document.querySelector('#editPathBtn'))
      await waitFor(() => expect(document.querySelector('#sessionPath')).toBeTruthy())
      const pathInput = document.querySelector('#sessionPath')
      pathInput.value = badPath
      await fireEvent.input(pathInput)

      await fireEvent.click(document.querySelector('#saveSessionBtn'))

      await waitFor(() =>
        expect(
          document.querySelector('.session-sheet-actions .field-error').textContent
        ).toMatch(/Path/i)
      )
      expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/add-session'))).toBe(false)
      expect(navigate).not.toHaveBeenCalled()
      expect(document.querySelector('#sessionPath').classList.contains('is-invalid')).toBe(true)
    }
  )

  // The web address is generated from name + city rather than typed. Asking people
  // to invent a URL slug in a bare required field is what produced a session whose
  // path was "." — it satisfied "non-empty" and resolved to nothing.
  describe('the generated web address', () => {
    async function openEmptySheet() {
      const navigate = vi.fn()
      const { container } = render(App, { pageData: payload(), navigate })
      await fireEvent.click(container.querySelector('a[href="/add-session#here"]'))
      await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())
      return { navigate }
    }

    async function fill(id, value) {
      const el = document.querySelector(id)
      el.value = value
      await fireEvent.input(el)
    }

    it('tracks the name and city as they are typed, with no input to fill in', async () => {
      await openEmptySheet()
      expect(document.querySelector('#sessionPath')).toBeNull()

      await fill('#sessionName', "McGrath's Irish Pub")
      expect(document.querySelector('#sessionPathValue').textContent).toBe(
        '/sessions/mcgraths-irish-pub'
      )

      await fill('#cityName', 'Dublin')
      expect(document.querySelector('#sessionPathValue').textContent).toBe(
        '/sessions/dublin/mcgraths-irish-pub'
      )
    })

    it('Edit swaps in an input seeded with the generated value, and posts the override', async () => {
      const { navigate } = await openEmptySheet()
      await fill('#sessionName', 'New Session')
      await fill('#cityName', 'Testville')
      await fill('#stateName', 'TX')
      await fill('#countryName', 'USA')

      await fireEvent.click(document.querySelector('#editPathBtn'))
      await waitFor(() => expect(document.querySelector('#sessionPath')).toBeTruthy())
      expect(document.querySelector('#sessionPath').value).toBe('testville/new-session')

      await fill('#sessionPath', 'somewhere-else')
      await fireEvent.click(document.querySelector('#saveSessionBtn'))

      await waitFor(() => expect(navigate).toHaveBeenCalledWith('/sessions/somewhere-else'))
      const [, init] = fetch.mock.calls.find(([u]) => String(u).includes('/api/add-session'))
      expect(JSON.parse(init.body).path).toBe('somewhere-else')
    })

    it('an override stops tracking the name, and can be handed back', async () => {
      await openEmptySheet()
      await fill('#sessionName', 'New Session')
      await fill('#cityName', 'Testville')

      await fireEvent.click(document.querySelector('#editPathBtn'))
      await waitFor(() => expect(document.querySelector('#sessionPath')).toBeTruthy())
      await fill('#sessionPath', 'my-own-slug')

      // renaming no longer moves the path out from under the override
      await fill('#sessionName', 'Renamed Session')
      expect(document.querySelector('#sessionPath').value).toBe('my-own-slug')

      await fireEvent.click(document.querySelector('#useGeneratedPathBtn'))
      await waitFor(() => expect(document.querySelector('#sessionPath')).toBeNull())
      expect(document.querySelector('#sessionPathValue').textContent).toBe(
        '/sessions/testville/renamed-session'
      )
    })

    it('drops into manual entry when there is nothing to slugify', async () => {
      await openEmptySheet()
      // No Latin characters to build a slug from, so the generated path is empty
      await fill('#sessionName', '会话')
      await fill('#cityName', '北京')
      await fill('#stateName', 'TX')
      await fill('#countryName', 'USA')
      expect(document.querySelector('#sessionPathValue').textContent).toBe(
        'Enter a name and city first'
      )

      await fireEvent.click(document.querySelector('#saveSessionBtn'))

      await waitFor(() => expect(document.querySelector('#sessionPath')).toBeTruthy())
      expect(document.querySelector('.session-sheet-actions .field-error').textContent).toBe(
        'Path is required'
      )
      expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/add-session'))).toBe(false)
    })

    it('keeps a seeded path that is not what the generator would produce', async () => {
      // An import whose stored path was customized earlier stays as-is
      fetchRoutes['/api/fetch-session-data'] = {
        success: true,
        session_data: {
          id: 1247,
          name: "B.D. Riley's",
          city: 'Austin',
          state: 'Texas',
          country: 'USA',
        },
      }
      const { container } = render(App, { pageData: payload() })
      const input = container.querySelector('#sessionUrl')
      input.value = '1247'
      await fireEvent.input(input)
      await fireEvent.submit(container.querySelector('#sessionUrlForm'))
      await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())

      // the import seeds generatePath's own output, so it stays generated
      expect(document.querySelector('#sessionPath')).toBeNull()
      expect(document.querySelector('#sessionPathValue').textContent).toBe(
        '/sessions/austin/bd-rileys'
      )
    })
  })

  it('saves an IMPORTED session, whose thesession id arrives as a number', async () => {
    // thesession.org's JSON types the id as a number, so the seeded field is not a
    // string. Every other save test types into the field (making it one), which is
    // how a throw on `thesessionId.trim()` left the import flow's Save button dead.
    const navigate = vi.fn()
    const { container } = render(App, { pageData: payload(), navigate })
    const input = container.querySelector('#sessionUrl')
    input.value = '1247'
    await fireEvent.input(input)
    await fireEvent.submit(container.querySelector('#sessionUrlForm'))
    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())
    expect(document.querySelector('#thesessionId').value).toBe('1247')

    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() =>
      expect(fetch.mock.calls.some(([u]) => String(u).includes('/api/add-session'))).toBe(true)
    )
    const [, init] = fetch.mock.calls.find(([u]) => String(u).includes('/api/add-session'))
    expect(JSON.parse(init.body)).toMatchObject({
      thesession_id: '1247',
      name: "B.D. Riley's",
      path: 'austin/bd-rileys',
    })
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/sessions/austin/bd-rileys'))
    expect(document.querySelector('.session-sheet-actions .field-error')).toBeNull()
  })

  it('a failed save keeps the sheet open with the server message', async () => {
    fetchRoutes['/api/add-session'] = { success: false, message: 'Path "x" is already taken' }
    const navigate = vi.fn()
    const { container } = render(App, { pageData: payload(), navigate })
    await fireEvent.click(container.querySelector('a[href="/add-session#here"]'))
    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())

    for (const [id, value] of [
      ['#sessionName', 'New Session'],
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
