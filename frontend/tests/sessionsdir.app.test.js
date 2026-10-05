// The sessions directory as a place page (spec 055) and its festival rows (spec 056).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent } from '@testing-library/svelte'
import App from '../src/sessionsdir/App.svelte'

const austin = { slug: 'austin', name: 'Austin' }
const row = (over) => ({
  session_id: 1,
  kind: 'session',
  name: 'Mueller Session',
  path: 'austin/mueller',
  city: 'Austin',
  state: 'Texas',
  country: 'United States',
  termination_date: null,
  recurrence: null,
  user_is_member: false,
  user_relationship: null,
  location_name: 'BD Riley’s',
  active_instances: [],
  place: austin,
  ...over,
})
const festival = row({
  session_id: 6,
  kind: 'festival',
  name: 'Hill Country Trad Fest',
  path: 'hill-country-fest',
  years: 2,
  active_instances: [
    { session_instance_id: 100, date: '2026-06-05', start_time: '19:00:00', end_time: null, location_override: null, path: 'hill-country-fest/2026' },
  ],
})

let assigned
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {}))) // the refresh never lands
  assigned = null
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, search: '', pathname: '/sessions', href: '', set href(v) { assigned = v } },
  })
})
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('a place page', () => {
  const pageData = {
    success: true,
    sessions: [row({}), festival],
    viewer_country: 'United States',
    place: {
      slug: 'houston', name: 'Houston', kind: 'place', area: 'Texas', country: 'United States',
      parent: null, children: [{ slug: 'conroe', name: 'Conroe' }, { slug: 'spring', name: 'Spring' }],
    },
  }

  it('names the place and links its children', () => {
    render(App, { pageData, isLoggedIn: true })
    expect(document.querySelector('.place-name').textContent).toBe('Houston')
    const links = [...document.querySelectorAll('#place-children a')].map((a) => a.getAttribute('href'))
    expect(links).toEqual(['/sessions/conroe', '/sessions/spring'])
  })

  it('opens on All Active, not My Sessions', () => {
    render(App, { pageData, isLoggedIn: true })
    expect(document.querySelector('#count-filter-type').textContent).toBe('active sessions')
    expect(document.querySelector('#count-number').textContent).toBe('2')
  })

  it('refreshes from the scoped API', () => {
    render(App, { pageData, isLoggedIn: true })
    expect(fetch.mock.calls[0][0]).toBe('/api/sessions/with-today-status?place=houston')
  })
})

describe('the rows', () => {
  const pageData = { success: true, sessions: [row({}), festival], viewer_country: 'United States' }

  it("a row's place goes to the place page, not the session", async () => {
    render(App, { pageData, isLoggedIn: false })
    const place = document.querySelector('.session-row-place')
    expect(place.textContent).toBe('Austin, Texas')
    await fireEvent.click(place)
    expect(assigned).toBe('/sessions/austin')
  })

  it('a festival is one row, labelled, linking to the festival', () => {
    render(App, { pageData, isLoggedIn: false })
    const fest = document.querySelector('[data-session-path="hill-country-fest"]')
    expect(fest.getAttribute('href')).toBe('/sessions/hill-country-fest')
    expect(fest.querySelector('.session-row-kind').textContent).toBe('Festival')
  })

  it("On Now on a festival row goes to that year's night", async () => {
    render(App, { pageData, isLoggedIn: false })
    await fireEvent.click(document.querySelector('[data-session-path="hill-country-fest"] .btn-goto-today'))
    expect(assigned).toBe('/sessions/hill-country-fest/2026/2026-06-05')
  })
})
