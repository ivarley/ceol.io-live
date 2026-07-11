// The app-wide "Find a tune" overlay (spec 035 Step 3c) — ported from
// hamburger_menu.js. Same DOM contract (.ft-input / .ft-results .ft-item) the
// offline e2e selects on; server search with offline-bundle fallback.
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
})

async function openAndSearch(component, container, q) {
  component.show()
  await waitFor(() => expect(container.querySelector('#find-tune-overlay')).toBeTruthy())
  const input = container.querySelector('.ft-input')
  input.value = q
  await fireEvent.input(input)
  await waitFor(() => expect(container.querySelector('.ft-results .ft-item, .ft-results .ft-empty')).toBeTruthy(), { timeout: 2000 })
}

describe('FindTune overlay', () => {
  it('searches after debounce and renders .ft-item rows with data-tune-id', async () => {
    const { component, container } = render(FindTune)
    await openAndSearch(component, container, 'kesh')
    const items = container.querySelectorAll('.ft-results .ft-item')
    expect(items).toHaveLength(2)
    expect(items[0].dataset.tuneId).toBe('55')
    expect(items[0].textContent).toContain('Kesh, The')
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/tunes/search?q=kesh'), expect.anything())
  })

  it('clicking a result closes the overlay and opens the global drawer view', async () => {
    const { component, container } = render(FindTune)
    await openAndSearch(component, container, 'kesh')
    await fireEvent.click(container.querySelector('.ft-results .ft-item'))
    expect(window.TuneDetailModal.show).toHaveBeenCalledWith(
      expect.objectContaining({
        context: 'session_instance',
        tuneId: 55,
        apiEndpoint: '/api/tunes/55/detail',
        additionalData: expect.objectContaining({ global: true }),
      })
    )
    expect(container.querySelector('#find-tune-overlay')).toBeFalsy()
  })

  it('falls back to the offline bundle when the server search fails', async () => {
    fetch.mockRejectedValue(new TypeError('offline'))
    window.CeolOffline = { searchTunes: vi.fn().mockResolvedValue([TUNES[1]]) }
    const { component, container } = render(FindTune)
    await openAndSearch(component, container, 'drowsy')
    const items = container.querySelectorAll('.ft-results .ft-item')
    expect(items).toHaveLength(1)
    expect(items[0].textContent).toContain('Drowsy Maggie')
    expect(window.CeolOffline.searchTunes).toHaveBeenCalledWith('drowsy', 10)
  })

  it('shows the no-match row and requires 2+ characters', async () => {
    fetch.mockResolvedValue({ json: async () => ({ success: true, tunes: [] }) })
    const { component, container } = render(FindTune)
    await openAndSearch(component, container, 'zzz')
    expect(container.querySelector('.ft-empty')).toBeTruthy()
    const input = container.querySelector('.ft-input')
    input.value = 'z'
    await fireEvent.input(input)
    await new Promise((r) => setTimeout(r, 300))
    expect(container.querySelector('.ft-results').children).toHaveLength(0)
  })
})
