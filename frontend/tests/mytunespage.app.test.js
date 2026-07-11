// Characterization tests for the My Tunes page view: first paint comes from the
// embedded payload (no fetch needed), and the legacy card/DOM contract holds
// (.tune-card, data-tune-id, .status-badge — my_tunes_mobile.css and the e2e
// suite select on these).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/mytunespage/App.svelte'

const payload = () => ({
  success: true,
  tunes: [
    {
      person_tune_id: 11,
      tune_id: 101,
      tune_name: "Cooley's",
      tune_type: 'reel',
      learn_status: 'want to learn',
      heard_count: 2,
      notes: null,
      setting_id: null,
      tunebook_count: 9,
      session_play_count: 0,
      instrument_status: {},
    },
    {
      person_tune_id: 12,
      tune_id: 102,
      tune_name: 'Banish Misfortune',
      tune_type: 'jig',
      learn_status: 'learned',
      heard_count: 0,
      notes: null,
      setting_id: 4,
      tunebook_count: 3,
      session_play_count: 1,
      instrument_status: {},
    },
  ],
  instruments: [{ instrument: 'Fiddle', is_auto: true }],
  pagination: { page: 1, has_next: false },
  filters: { learn_status: null, tune_type: null, search: '' },
})

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
  window.TuneDetailModal = { show: vi.fn(), close: vi.fn(), getTuneIdFromUrl: () => null }
  // The background refetch echoes the embed (as the real API would); ops POSTs
  // resolve success.
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url) => {
      if (String(url).includes('/api/my-tunes/ops')) {
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) })
      }
      return Promise.resolve({ ok: true, json: async () => payload() })
    })
  )
  window.history.replaceState({}, '', '/my-tunes')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('My Tunes page view', () => {
  it('first paint renders the embedded payload with the legacy DOM contract', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="101"]')).toBeTruthy())
    const card = container.querySelector('.tune-card[data-tune-id="101"]')
    expect(card.getAttribute('data-person-tune-id')).toBe('11')
    expect(card.querySelector('.status-badge').textContent).toBe('want to learn')
    expect(container.querySelectorAll('#tunes-grid .tune-card')).toHaveLength(2)
  })

  it('tapping the status badge cycles optimistically and posts the op', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="101"] .status-badge')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tune-card[data-tune-id="101"] .status-badge'))
    await waitFor(() => {
      expect(container.querySelector('.tune-card[data-tune-id="101"] .status-badge').textContent).toBe('learning')
    })
    const opCall = fetch.mock.calls.find(([url]) => String(url).includes('/api/my-tunes/ops'))
    expect(opCall).toBeTruthy()
    expect(JSON.parse(opCall[1].body)).toMatchObject({ type: 'set_status', tune_id: 101, learn_status: 'learning' })
  })

  it('clicking a card opens the shared drawer with the my_tunes context', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="102"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tune-card[data-tune-id="102"]'))
    expect(window.TuneDetailModal.show).toHaveBeenCalledWith(
      expect.objectContaining({ context: 'my_tunes', apiEndpoint: '/api/my-tunes/12' })
    )
  })

  it('heard + shows the N -> N+1 toast and sends an absolute set_heard', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="101"] .increment-heard-btn')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tune-card[data-tune-id="101"] .increment-heard-btn'))
    expect(window.showMessage).toHaveBeenCalledWith('Heard count: 2 → 3', 'success')
    await waitFor(() => {
      const opCall = fetch.mock.calls.find(
        ([url, init]) => String(url).includes('/api/my-tunes/ops') && init && JSON.parse(init.body).type === 'set_heard'
      )
      expect(opCall).toBeTruthy()
      expect(JSON.parse(opCall[1].body)).toMatchObject({ tune_id: 101, heard_count: 3 })
    })
  })

  it('search filters the visible cards (debounced)', async () => {
    vi.useFakeTimers()
    try {
      const { container } = render(App, { pageData: payload() })
      await vi.waitFor(() => {
        if (!container.querySelector('.tune-card[data-tune-id="101"]')) throw new Error('not yet')
      })
      const input = container.querySelector('#search-input')
      input.value = 'banish'
      input.dispatchEvent(new Event('input', { bubbles: true }))
      await vi.advanceTimersByTimeAsync(350)
      await vi.waitFor(() => {
        expect(container.querySelectorAll('#tunes-grid [data-tune-id]')).toHaveLength(1)
        expect(container.querySelector('[data-tune-id="102"]')).toBeTruthy()
      })
    } finally {
      vi.useRealTimers()
    }
  })
})
