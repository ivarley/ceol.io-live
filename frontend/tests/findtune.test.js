// The app-wide "Find a tune" sheet (spec 035 Step 3c) — ported from
// hamburger_menu.js, chrome now the kit Sheet (portaled to document.body).
// Same BODY contract (.ft-input / .ft-results .ft-item) the offline e2e
// selects on; server search with offline-bundle fallback.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor, fireEvent } from '@testing-library/svelte'
import FindTune from '../src/tunesheet/FindTune.svelte'

const TUNES = [
  { tune_id: 55, name: 'Kesh, The', tune_type: 'Jig' },
  { tune_id: 27, name: 'Drowsy Maggie', tune_type: 'Reel' },
]

beforeEach(() => {
  window.TuneDetailModal = { show: vi.fn() }
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ json: async () => ({ success: true, tunes: TUNES }) })
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  delete window.CeolOffline
  delete window.CEOL_AUTHED
})

async function openAndSearch(component, q) {
  component.show()
  await waitFor(() => expect(document.querySelector('.ft-input')).toBeTruthy())
  const input = document.querySelector('.ft-input')
  input.value = q
  await fireEvent.input(input)
  await waitFor(() => expect(document.querySelector('.ft-results .ft-item, .ft-results .ft-empty')).toBeTruthy(), { timeout: 2000 })
}

describe('FindTune overlay', () => {
  it('searches after debounce and renders .ft-item rows with data-tune-id', async () => {
    const { component } = render(FindTune)
    await openAndSearch(component, 'kesh')
    expect(document.querySelector('.kit-sheet-title').textContent).toBe('Find a tune')
    const items = document.querySelectorAll('.ft-results .ft-item')
    expect(items).toHaveLength(2)
    expect(items[0].dataset.tuneId).toBe('55')
    expect(items[0].textContent).toContain('Kesh, The')
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/tunes/search?q=kesh'), expect.anything())
  })

  it('marks results that matched the NOTATION rather than the name', async () => {
    // The server blends notation matches into the same list; without the mark a search
    // by notes reads as a list of tunes with no visible reason for being there.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: async () => ({
          success: true,
          tunes: [
            { tune_id: 27, name: 'Drowsy Maggie', tune_type: 'Reel', abc_only: true },
            { tune_id: 55, name: 'Kesh, The', tune_type: 'Jig', abc_only: false },
          ],
        }),
      })
    )
    const { component } = render(FindTune)
    await openAndSearch(component, 'gedbed')
    const items = document.querySelectorAll('.ft-results .ft-item')
    expect(items[0].querySelector('.ft-abc')).toBeTruthy()
    expect(items[1].querySelector('.ft-abc')).toBeFalsy()
  })

  it('says "opening bars" for an offline notation match, which is incipit-only', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    window.CeolOffline = {
      searchTunes: vi.fn().mockResolvedValue([
        { tune_id: 27, name: 'Drowsy Maggie', tune_type: 'Reel', abc_only: true, abc_scope: 'incipit' },
      ]),
    }
    const { component } = render(FindTune)
    await openAndSearch(component, 'gedbed')
    expect(document.querySelector('.ft-results .ft-item .ft-abc').title).toContain('opening bars')
  })

  it('clicking a result closes the sheet and opens the global drawer view', async () => {
    const { component } = render(FindTune)
    await openAndSearch(component, 'kesh')
    await fireEvent.click(document.querySelector('.ft-results .ft-item'))
    // New show() API: identity only — the drawer derives its variant from the
    // payload, and its scope from the URL (global here, off a session page).
    expect(window.TuneDetailModal.show).toHaveBeenCalledWith(
      expect.objectContaining({ tuneId: 55, tuneName: 'Kesh, The' })
    )
    expect(document.querySelector('.ft-input')).toBeFalsy()
  })

  it('falls back to the offline bundle when the server search fails', async () => {
    fetch.mockRejectedValue(new TypeError('offline'))
    window.CeolOffline = { searchTunes: vi.fn().mockResolvedValue([TUNES[1]]) }
    const { component } = render(FindTune)
    await openAndSearch(component, 'drowsy')
    const items = document.querySelectorAll('.ft-results .ft-item')
    expect(items).toHaveLength(1)
    expect(items[0].textContent).toContain('Drowsy Maggie')
    expect(window.CeolOffline.searchTunes).toHaveBeenCalledWith('drowsy', 10)
  })

  // Paste-a-link: the server resolves an id/URL query to that one tune, so the overlay
  // just passes it through — but the "nothing found" case means "not imported yet", not
  // "no such name", and hands off to the add pane carrying the link (setting included).
  it('resolves a pasted thesession.org URL to its tune', async () => {
    fetch.mockResolvedValue({
      json: async () => ({ success: true, tunes: [TUNES[0]], query_tune_id: 55 }),
    })
    const { component } = render(FindTune)
    await openAndSearch(component, 'https://thesession.org/tunes/55#setting123')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent('https://thesession.org/tunes/55#setting123')),
      expect.anything()
    )
    const items = document.querySelectorAll('.ft-results .ft-item')
    expect(items).toHaveLength(1)
    expect(items[0].dataset.tuneId).toBe('55')
  })

  it('offers the add pane (link and setting intact) for a tune not in the library', async () => {
    window.CEOL_AUTHED = true
    fetch.mockResolvedValue({ json: async () => ({ success: true, tunes: [], query_tune_id: 8645 }) })
    window.CeolOffline = { searchTunes: vi.fn().mockResolvedValue([TUNES[1]]) }
    const { component } = render(FindTune)
    await openAndSearch(component, 'https://thesession.org/tunes/8645#setting44656')
    // The offline bundle is a NAME index — never consulted for a link lookup.
    expect(window.CeolOffline.searchTunes).not.toHaveBeenCalled()
    const link = document.querySelector('.ft-empty .ft-import')
    expect(document.querySelector('.ft-empty').textContent).toContain('8645')
    expect(link.getAttribute('href')).toBe(
      '/my-tunes?add=1&q=' + encodeURIComponent('https://thesession.org/tunes/8645#setting44656')
    )
  })

  it('sends a logged-out viewer to thesession.org instead of the add pane', async () => {
    fetch.mockResolvedValue({ json: async () => ({ success: true, tunes: [], query_tune_id: 8645 }) })
    const { component } = render(FindTune)
    await openAndSearch(component, 'https://thesession.org/tunes/8645')
    expect(document.querySelector('.ft-empty .ft-import').getAttribute('href')).toBe(
      'https://thesession.org/tunes/8645'
    )
  })

  it('shows the no-match row and requires 2+ characters', async () => {
    fetch.mockResolvedValue({ json: async () => ({ success: true, tunes: [] }) })
    const { component } = render(FindTune)
    await openAndSearch(component, 'zzz')
    expect(document.querySelector('.ft-empty')).toBeTruthy()
    const input = document.querySelector('.ft-input')
    input.value = 'z'
    await fireEvent.input(input)
    await new Promise((r) => setTimeout(r, 300))
    expect(document.querySelector('.ft-results').children).toHaveLength(0)
  })
})
