// The add-a-session sheet (spec 052 §B9).
//
// These carry over from the page this replaced: the ported flows (ID/URL import,
// search, the already-here Dialog, the manual flow, the gated save) and every
// rule the old wizard had pinned — the generated web address, the refused
// unusable paths, the refused tune URL. The field ids are unchanged, so those
// assertions are the same ones; what changed is how you reach them.
//
// What is new here is the shape: two stacked sheets instead of a page plus a
// sheet, a search that runs as you type, an offer instead of a guess when you
// type bare digits, an error that does not erase itself, and an Advanced section
// that has to open itself when the thing you got wrong is inside it.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import AddSessionSheet from '../src/addsession/AddSessionSheet.svelte'
import {
  parseSessionInput,
  generatePath,
  guessTimezone,
  parseTheSessionRecurrence,
  summarizeRecurrence,
} from '../src/addsession/logic.js'

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
    // The GET (payload) and the POST (create) share a path; the stub keys on the
    // path, so this body has to satisfy both readers.
    '/api/add-session': { ...payload(), session_path: 'austin/bd-rileys' },
  }
  stubFetch()
  window.history.replaceState({}, '', '/sessions')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

/** Type into the search box and flush the debounce the way Enter does. */
async function search(text) {
  const input = document.querySelector('#sessionUrl')
  input.value = text
  await fireEvent.input(input)
  await fireEvent.keyDown(input, { key: 'Enter' })
}

function open(props = {}) {
  return render(AddSessionSheet, { open: true, navigate: vi.fn(), ...props })
}

async function openDetails(props = {}) {
  const r = open(props)
  await fireEvent.click(document.querySelector('#add-manually'))
  await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())
  return r
}

async function fill(id, value) {
  const el = document.querySelector(id)
  el.value = value
  await fireEvent.input(el)
}

async function fillRequired(name = 'New Session') {
  await fill('#sessionName', name)
  await fill('#cityName', 'Testville')
  await fill('#stateName', 'TX')
  await fill('#countryName', 'USA')
}

async function openAdvanced() {
  await fireEvent.click(document.querySelector('#advanced-toggle'))
  await waitFor(() => expect(document.querySelector('#advanced-section')).toBeTruthy())
}

const postedTo = (path) => fetch.mock.calls.some(([u]) => String(u).includes(path))
// The sheet GETs /api/add-session for its payload and POSTs to the same path to
// create, so matching on the path alone finds the GET first — and a GET has no body.
const createCalls = () =>
  fetch.mock.calls.filter(([u, init]) => String(u).includes('/api/add-session') && init?.body)
const created = () => createCalls().length > 0
const createdBody = () => JSON.parse(createCalls()[0][1].body)

describe('add-session sheet: finding the session', () => {
  it('opens on the search field, with the manual way out already visible', async () => {
    open()
    expect(document.querySelector('#sessionUrl')).toBeTruthy()
    // The escape hatch for a session that isn't on thesession.org used to be a
    // hyperlink inside a paragraph. It is a row, and it is there before you search.
    expect(document.querySelector('#add-manually')).toBeTruthy()
    // No heading, no intro, no bulleted lesson in what you may type.
    expect(document.querySelector('h1')).toBeNull()
  })

  it('fetches the timezone payload once, when it opens', async () => {
    open()
    await waitFor(() => expect(postedTo('/api/add-session')).toBe(true))
    const gets = fetch.mock.calls.filter(([u, init]) => String(u).includes('/api/add-session') && !init)
    expect(gets).toHaveLength(1)
  })

  it('a pasted thesession link resolves straight through to the details', async () => {
    open()
    await search('https://thesession.org/sessions/1247')

    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())
    expect(document.querySelector('#sessionName').value).toBe("B.D. Riley's")
    // timezone guessed from Texas; the schedule text parsed into a summary
    expect(document.querySelector('#timezone').value).toBe('America/Chicago')
    expect(document.querySelector('#recurrence-summary-text').textContent).toBe(
      'Tuesdays from 8pm-11pm'
    )
    expect(postedTo('/api/check-existing-session')).toBe(true)
    expect(postedTo('/api/fetch-session-data')).toBe(true)
  })

  it('bare digits are offered, not resolved — a pause mid-number is not a choice', async () => {
    open()
    await search('124')

    // Typing "1247" settles on "124" if you pause. Opening session 124 on that
    // basis would be a wrong answer delivered confidently, so it asks instead.
    expect(postedTo('/api/check-existing-session')).toBe(false)
    const offer = document.querySelector('#open-session-id')
    expect(offer).toBeTruthy()
    expect(offer.textContent).toContain('124')

    await fireEvent.click(offer)
    await waitFor(() => expect(postedTo('/api/check-existing-session')).toBe(true))
  })

  it('a short query searches nothing', async () => {
    open()
    await search('bd')
    expect(postedTo('/api/search-sessions')).toBe(false)
  })

  it('lists results as rows, without repeating the name in the place', async () => {
    fetchRoutes['/api/search-sessions'] = {
      success: true,
      results: [
        {
          id: 11,
          name: 'Celtic Crossing',
          // thesession.org leads with the name more often than not.
          display_text: 'Celtic Crossing, Memphis, Tennessee, USA',
          exists_in_db: false,
          session_path: null,
        },
      ],
    }
    open()
    await search('memphis')

    await waitFor(() =>
      expect(document.querySelectorAll('#searchResultsList .search-result-item')).toHaveLength(1)
    )
    const row = document.querySelector('.search-result-item')
    expect(row.querySelector('.kit-row-title').textContent).toBe('Celtic Crossing')
    expect(row.querySelector('.kit-row-sub').textContent).toBe('Memphis, Tennessee, USA')
  })

  it('picking a session that is already here raises the Dialog', async () => {
    fetchRoutes['/api/search-sessions'] = {
      success: true,
      results: [
        { id: 11, name: 'Fresh Session', display_text: 'Fresh, TX', exists_in_db: false, session_path: null },
        { id: 22, name: 'Mueller Session', display_text: 'Austin, TX', exists_in_db: true, session_path: '/sessions/austin/mueller' },
      ],
    }
    const navigate = vi.fn()
    open({ navigate })
    await search('mueller')

    await waitFor(() =>
      expect(document.querySelectorAll('#searchResultsList .search-result-item')).toHaveLength(2)
    )
    const existing = document.querySelectorAll('.search-result-item')[1]
    expect(existing.classList.contains('existing')).toBe(true)
    await fireEvent.click(existing)

    await waitFor(() => expect(document.querySelector('.kit-dialog')).toBeTruthy())
    const go = [...document.querySelectorAll('.kit-dialog button')].find(
      (b) => b.textContent.trim() === 'Open it'
    )
    await fireEvent.click(go)
    expect(navigate).toHaveBeenCalledWith('/sessions/austin/mueller')
  })

  it('an id already in the database says so, with a link, and opens nothing', async () => {
    fetchRoutes['/api/check-existing-session'] = {
      exists: true,
      session_path: '/sessions/austin/mueller',
    }
    open()
    await search('https://thesession.org/sessions/6247')

    await waitFor(() => expect(document.querySelector('#errorAlert')).toBeTruthy())
    expect(document.querySelector('#errorAlert a').getAttribute('href')).toBe(
      '/sessions/austin/mueller'
    )
    expect(document.querySelector('#sessionDetailsForm')).toBeNull()
  })

  it('an error stays until you do something about it', async () => {
    // The old one cleared itself after five seconds: long enough to start reading
    // and not long enough to finish.
    vi.useFakeTimers()
    try {
      fetchRoutes['/api/check-existing-session'] = { exists: true, session_path: '/sessions/x' }
      open()
      const input = document.querySelector('#sessionUrl')
      input.value = 'https://thesession.org/sessions/6247'
      await fireEvent.input(input)
      await fireEvent.keyDown(input, { key: 'Enter' })
      await vi.advanceTimersByTimeAsync(50)
      expect(document.querySelector('#errorAlert')).toBeTruthy()

      await vi.advanceTimersByTimeAsync(30000)
      expect(document.querySelector('#errorAlert')).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('add-session sheet: the details', () => {
  it('closing the details uncovers the search that produced it', async () => {
    fetchRoutes['/api/search-sessions'] = {
      success: true,
      results: [
        { id: 11, name: 'Fresh Session', display_text: 'Fresh, TX', exists_in_db: false, session_path: null },
      ],
    }
    open()
    await search('fresh')
    await waitFor(() => expect(document.querySelector('.search-result-item')).toBeTruthy())
    await fireEvent.click(document.querySelector('.search-result-item'))
    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())

    // Back, not Cancel: stage 1 is underneath, so a wrong pick costs one tap.
    const back = document.querySelector('.kit-sheet-back')
    expect(back.textContent).toContain('Back')
    await fireEvent.click(back)

    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeNull())
    expect(document.querySelector('#sessionUrl')).toBeTruthy()
    expect(document.querySelector('.search-result-item')).toBeTruthy()
  })

  it('the manual flow validates required fields, then posts and redirects', async () => {
    const navigate = vi.fn()
    await openDetails({ navigate })
    expect(document.querySelector('#sessionName').value).toBe('')

    // The path is generated, so it isn't one of the fields you're asked to supply
    await fireEvent.click(document.querySelector('#saveSessionBtn'))
    await waitFor(() =>
      expect(document.querySelector('.session-sheet-actions .field-error').textContent).toContain(
        'Name, City, State, Country'
      )
    )
    expect(created()).toBe(false)
    expect(document.querySelector('#sessionName').classList.contains('is-invalid')).toBe(true)

    await fillRequired()
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/sessions/testville/new-session'))
    expect(createdBody()).toMatchObject({
      name: 'New Session',
      path: 'testville/new-session',
      city: 'Testville',
      state: 'TX',
      country: 'USA',
      timezone: 'America/Chicago',
      recurrence: null,
      add_current_user: true,
      add_current_user_role: 'admin',
      session_type: 'regular',
      active_buffer_minutes_before: 60,
      active_buffer_minutes_after: 60,
    })
  })

  it('?acu=false still pre-unchecks "Add me as"', async () => {
    const navigate = vi.fn()
    await openDetails({ navigate, addMeDefault: false })
    expect(document.querySelector('#addCurrentUser').checked).toBe(false)
    await fillRequired()
    await fireEvent.click(document.querySelector('#saveSessionBtn'))
    await waitFor(() => expect(navigate).toHaveBeenCalled())
    expect(createdBody()).toMatchObject({
      add_current_user: false,
      add_current_user_role: null,
    })
  })

  it('a failed save keeps the sheet open with the server message', async () => {
    fetchRoutes['/api/add-session'] = { success: false, message: 'Path "x" is already taken' }
    const navigate = vi.fn()
    await openDetails({ navigate })
    await fillRequired()
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() =>
      expect(document.querySelector('.session-sheet-actions .field-error').textContent).toBe(
        'Path "x" is already taken'
      )
    )
    expect(navigate).not.toHaveBeenCalled()
    expect(document.querySelector('#sessionDetailsForm')).toBeTruthy()
  })

  it('the settings whose defaults are right start folded away', async () => {
    await openDetails()
    // The main path is name, venue, where, when and "add me as" — not the active
    // window, which nobody new understands and almost nobody changes.
    expect(document.querySelector('#advanced-section')).toBeNull()
    expect(document.querySelector('#activeBufferBefore')).toBeNull()
    expect(document.querySelector('#sessionPathValue')).toBeNull()

    await openAdvanced()
    expect(document.querySelector('#activeBufferBefore')).toBeTruthy()
    expect(document.querySelector('#sessionPathValue')).toBeTruthy()
  })

  it('carries an edited thesession link, type and active window into the POST', async () => {
    const navigate = vi.fn()
    await openDetails({ navigate })
    await fillRequired('Festival Session')
    await openAdvanced()
    await fill('#thesessionId', 'https://thesession.org/sessions/6247')
    await fill('#activeBufferBefore', '30')
    const type = document.querySelector('#sessionType')
    type.value = 'festival'
    await fireEvent.change(type)
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() => expect(navigate).toHaveBeenCalled())
    expect(createdBody()).toMatchObject({
      thesession_id: 'https://thesession.org/sessions/6247',
      session_type: 'festival',
      active_buffer_minutes_before: 30,
      active_buffer_minutes_after: 60,
    })
  })

  it('refuses to post a tune URL as the thesession link, and opens Advanced to show you', async () => {
    await openDetails()
    await fillRequired('Tune Link Session')
    await openAdvanced()
    await fill('#thesessionId', 'https://thesession.org/tunes/182')
    // Fold it away again: the error has to bring it back, or it points at a
    // control that isn't on the screen.
    await fireEvent.click(document.querySelector('#advanced-toggle'))
    await waitFor(() => expect(document.querySelector('#advanced-section')).toBeNull())

    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() => expect(document.querySelector('#advanced-section')).toBeTruthy())
    expect(document.querySelector('.session-sheet-actions .field-error').textContent).toContain(
      'thesession.org/sessions/1234'
    )
    expect(document.querySelector('#thesessionId').classList.contains('is-invalid')).toBe(true)
    expect(created()).toBe(false)
  })
})

// A path like "/" or "." is non-empty, so the old required-fields check passed it
// — but it resolves to nothing as a URL, and since every admin route is keyed on
// the path, the session lands with no screen that can repair it.
describe('the generated web address', () => {
  it('tracks the name and city as they are typed, with no input to fill in', async () => {
    await openDetails()
    await fill('#sessionName', "McGrath's Irish Pub")
    await fill('#cityName', 'Dublin')
    await openAdvanced()

    expect(document.querySelector('#sessionPath')).toBeNull()
    expect(document.querySelector('#sessionPathValue').textContent).toBe(
      '/sessions/dublin/mcgraths-irish-pub'
    )
  })

  it('Edit swaps in an input seeded with the generated value, and posts the override', async () => {
    const navigate = vi.fn()
    await openDetails({ navigate })
    await fillRequired()
    await openAdvanced()

    await fireEvent.click(document.querySelector('#editPathBtn'))
    await waitFor(() => expect(document.querySelector('#sessionPath')).toBeTruthy())
    expect(document.querySelector('#sessionPath').value).toBe('testville/new-session')

    await fill('#sessionPath', 'somewhere-else')
    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/sessions/somewhere-else'))
    expect(createdBody().path).toBe('somewhere-else')
  })

  it('an override stops tracking the name, and can be handed back', async () => {
    await openDetails()
    await fill('#sessionName', 'New Session')
    await fill('#cityName', 'Testville')
    await openAdvanced()

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

  it.each([['/'], ['.'], ['austin/'], ['austin mueller']])(
    'refuses to post an unusable path (%s)',
    async (badPath) => {
      const navigate = vi.fn()
      await openDetails({ navigate })
      await fillRequired()
      await openAdvanced()

      // An unusable path can only be reached deliberately, via Edit
      await fireEvent.click(document.querySelector('#editPathBtn'))
      await waitFor(() => expect(document.querySelector('#sessionPath')).toBeTruthy())
      await fill('#sessionPath', badPath)

      await fireEvent.click(document.querySelector('#saveSessionBtn'))

      await waitFor(() =>
        expect(document.querySelector('.session-sheet-actions .field-error').textContent).toMatch(/Path/i)
      )
      expect(created()).toBe(false)
      expect(navigate).not.toHaveBeenCalled()
      expect(document.querySelector('#sessionPath').classList.contains('is-invalid')).toBe(true)
    }
  )

  it('drops into manual entry, and opens Advanced, when there is nothing to slugify', async () => {
    await openDetails()
    // No Latin characters to build a slug from, so the generated path is empty
    await fill('#sessionName', '会话')
    await fill('#cityName', '北京')
    await fill('#stateName', 'TX')
    await fill('#countryName', 'USA')
    expect(document.querySelector('#advanced-section')).toBeNull()

    await fireEvent.click(document.querySelector('#saveSessionBtn'))

    await waitFor(() => expect(document.querySelector('#sessionPath')).toBeTruthy())
    expect(document.querySelector('#advanced-section')).toBeTruthy()
    expect(document.querySelector('.session-sheet-actions .field-error').textContent).toBe(
      'Path is required'
    )
    expect(created()).toBe(false)
  })

  it('keeps a seeded path that is not what the generator would produce', async () => {
    fetchRoutes['/api/fetch-session-data'] = {
      success: true,
      session_data: { id: 1247, name: "B.D. Riley's", city: 'Austin', state: 'Texas', country: 'USA' },
    }
    open()
    await search('https://thesession.org/sessions/1247')
    await waitFor(() => expect(document.querySelector('#sessionDetailsForm')).toBeTruthy())
    await openAdvanced()

    // the import seeds generatePath's own output, so it stays generated
    expect(document.querySelector('#sessionPath')).toBeNull()
    expect(document.querySelector('#sessionPathValue').textContent).toBe(
      '/sessions/austin/bd-rileys'
    )
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

  it('summarizes the editor state into the summary line + JSON', () => {
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
