// The Places admin page (spec 055).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/placesadminpage/App.svelte'
import { canDelete, matchesPlace, parentOptions } from '../src/placesadminpage/logic.js'

const houston = { place_id: 1, slug: 'houston', name: 'Houston', kind: 'place', area: 'Texas', country: 'United States', parent: null, town_sessions: 1, paths: 1, children: 1 }
const conroe = { place_id: 2, slug: 'conroe', name: 'Conroe', kind: 'place', area: 'Texas', country: 'United States', parent: { place_id: 1, slug: 'houston', name: 'Houston' }, town_sessions: 2, paths: 1, children: 0 }
const fest = { place_id: 3, slug: 'probefest', name: 'Probe Fest', kind: 'festival', area: null, country: null, parent: { place_id: 2, slug: 'conroe', name: 'Conroe' }, town_sessions: 0, paths: 2, children: 0 }
const waco = { place_id: 4, slug: 'waco', name: 'Waco', kind: 'place', area: 'Texas', country: 'United States', parent: null, town_sessions: 0, paths: 0, children: 0 }
const all = [houston, conroe, fest, waco]

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('parentOptions', () => {
  it('never offers the place itself, anything inside it, or a festival', () => {
    expect(parentOptions(all, houston).map((p) => p.slug)).toEqual(['waco'])
    expect(parentOptions(all, conroe).map((p) => p.slug)).toEqual(['houston', 'waco'])
  })

  it('a new place may go inside any town or metro', () => {
    expect(parentOptions(all, null).map((p) => p.slug)).toEqual(['conroe', 'houston', 'waco'])
  })
})

describe('matchesPlace and canDelete', () => {
  it('searches name, slug, area and parent', () => {
    expect(matchesPlace(conroe, 'hous')).toBe(true)
    expect(matchesPlace(conroe, 'texas')).toBe(true)
    expect(matchesPlace(waco, 'conroe')).toBe(false)
  })

  it('only a place nothing uses can be deleted', () => {
    expect(all.filter(canDelete).map((p) => p.slug)).toEqual(['waco'])
  })
})

describe('the page', () => {
  it('lists the places and filters them', async () => {
    render(App, { pageData: { success: true, places: all } })
    expect(document.querySelectorAll('.place-row')).toHaveLength(4)
    const search = document.querySelector('.places-search-wrap input, input[type="search"], input')
    search.value = 'conroe'
    await fireEvent.input(search)
    await waitFor(() => expect(document.querySelectorAll('.place-row')).toHaveLength(2)) // Conroe, and the festival inside it
  })

  it('editing warns about a rename and saves', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: async () => ({ success: true, places: all, moved: [{ from: 'conroe/x', to: 'conroe-tx/x' }] }) })
    ))
    render(App, { pageData: { success: true, places: all } })
    await fireEvent.click(document.querySelector('[data-slug="conroe"]'))
    await waitFor(() => expect(document.querySelector('#placeSlug')).toBeTruthy())
    expect(document.querySelector('#placeDelete')).toBeNull() // it has sessions
    const slug = document.querySelector('#placeSlug')
    slug.value = 'conroe-tx'
    await fireEvent.input(slug)
    expect(document.querySelector('#placeRenameNote').textContent).toContain('/sessions/conroe-tx/')
    await fireEvent.submit(document.querySelector('#placeForm'))
    await waitFor(() => expect(fetch).toHaveBeenCalled())
    const [url, opts] = fetch.mock.calls[0]
    expect(url).toBe('/api/admin/places/2')
    expect(opts.method).toBe('PUT')
    expect(JSON.parse(opts.body)).toMatchObject({ slug: 'conroe-tx', parent_place_id: 1 })
  })

  it('an unused place offers Delete', async () => {
    render(App, { pageData: { success: true, places: all } })
    await fireEvent.click(document.querySelector('[data-slug="waco"]'))
    await waitFor(() => expect(document.querySelector('#placeDelete')).toBeTruthy())
  })
})
