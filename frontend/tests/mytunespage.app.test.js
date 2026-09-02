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
    // The badge shows the page's wording; the stored value stays 'want to learn'.
    expect(card.querySelector('.status-badge').textContent).toBe('To Learn')
    expect(container.querySelectorAll('#tunes-grid .tune-card')).toHaveLength(2)
  })

  it('tapping the status badge cycles optimistically and posts the op', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="101"] .status-badge')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tune-card[data-tune-id="101"] .status-badge'))
    await waitFor(() => {
      expect(container.querySelector('.tune-card[data-tune-id="101"] .status-badge').textContent).toBe('Learning')
    })
    const opCall = fetch.mock.calls.find(([url]) => String(url).includes('/api/my-tunes/ops'))
    expect(opCall).toBeTruthy()
    expect(JSON.parse(opCall[1].body)).toMatchObject({ type: 'set_status', tune_id: 101, learn_status: 'learning' })
  })

  it('clicking a card opens the shared drawer with the tune identity (+ ptid deep-link key)', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="102"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tune-card[data-tune-id="102"]'))
    expect(window.TuneDetailModal.show).toHaveBeenCalledWith(
      expect.objectContaining({ tuneId: 102, ptid: 12, scope: null })
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

// "What am I learning right now?" is the question the page exists to answer, so the
// status filter sits in the open. Everything else stays behind the filter drawer.
describe('the status filter lives outside the filter drawer', () => {
  const statusBtn = (container, id) => container.querySelector(`.filter-status-row [data-status="${id}"]`)

  it('filters from first paint, with the drawer never opened', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(2))
    expect(container.querySelector('#filter-panel')).toBeNull() // drawer still shut

    await fireEvent.click(statusBtn(container, 'learned'))
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(1))
    expect(container.querySelector('.tune-card').dataset.tuneId).toBe('102')
    expect(statusBtn(container, 'learned').classList.contains('active')).toBe(true)
    expect(new URL(window.location).searchParams.get('status')).toBe('learned')

    await fireEvent.click(statusBtn(container, ''))
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(2))
  })

  it('is not duplicated inside the drawer, or by a pill', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(2))
    await fireEvent.click(statusBtn(container, 'learned'))

    // A pill stands in for a control you can't see; this one is right there.
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(1))
    expect(container.querySelector('#active-filter-pills')).toBeNull()
    // ...and the drawer button doesn't claim to be hiding something either.
    expect(container.querySelector('#filter-panel-toggle').classList.contains('active')).toBe(false)

    await fireEvent.click(container.querySelector('#filter-panel-toggle'))
    await waitFor(() => expect(container.querySelector('#filter-panel')).toBeTruthy())
    // One status control on the page, and it's the one outside the drawer.
    expect(container.querySelector('#filter-panel [data-status]')).toBeNull()
    expect(statusBtn(container, 'learned')).toBeTruthy()
  })

  it('Clear Filters still resets it, wherever it lives', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(2))
    await fireEvent.click(statusBtn(container, 'learned'))
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(1))

    await fireEvent.click(container.querySelector('#filter-panel-toggle'))
    await waitFor(() => expect(container.querySelector('#clear-filters-btn')).toBeTruthy())
    await fireEvent.click(container.querySelector('#clear-filters-btn'))
    await waitFor(() => expect(container.querySelectorAll('.tune-card')).toHaveLength(2))
    expect(statusBtn(container, '').classList.contains('active')).toBe(true)
  })
})

describe('drawer status-change notifications (chained tunes)', () => {
  it('updates the matching card for a tune already on the page', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="101"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tune-card[data-tune-id="101"]'))
    const config = window.TuneDetailModal.show.mock.calls[0][0]

    config.onStatusChange({
      tune_id: 101,
      learn_status: 'learned',
      instrument_status: {},
      on_list: true,
      person_tune_id: 11,
    })
    await waitFor(() =>
      expect(container.querySelector('.tune-card[data-tune-id="101"] .status-badge').textContent).toBe('Learned')
    )
  })

  it('adds a card when a tune with no card (chained drawer navigation) joins the list', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url, opts = {}) => {
        if (String(url).includes('/api/my-tunes/77')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              success: true,
              person_tune: {
                person_tune_id: 77,
                tune_id: 999,
                tune_name: 'The Chained Reel',
                tune_type: 'reel',
                learn_status: 'want to learn',
                heard_count: 0,
                notes: null,
                setting_id: null,
                tunebook_count: 2,
                session_play_count: 0,
                instrument_status: {},
              },
            }),
          })
        }
        return Promise.resolve({ ok: true, json: async () => payload() })
      })
    )
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="101"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tune-card[data-tune-id="101"]'))
    const config = window.TuneDetailModal.show.mock.calls[0][0]

    // A tune 20 links deep in Played With chaining was added to the list: the
    // host fetches its full row and the card appears without a reload.
    config.onStatusChange({
      tune_id: 999,
      learn_status: 'want to learn',
      instrument_status: {},
      on_list: true,
      person_tune_id: 77,
    })
    await waitFor(() => expect(container.querySelector('.tune-card[data-tune-id="999"]')).toBeTruthy())
    expect(container.querySelectorAll('#tunes-grid .tune-card')).toHaveLength(3)
    expect(container.querySelector('.tune-card[data-tune-id="999"] .status-badge').textContent).toBe('To Learn')
  })

  it('the add button opens the bundled-in add pane seeded with the current search', async () => {
    const { container } = render(App, { pageData: payload() })
    await waitFor(() => expect(container.querySelector('#add-tune-btn')).toBeTruthy())
    // The no-JS fallback href is the folded-away add page's redirect target.
    expect(container.querySelector('#add-tune-btn').getAttribute('href')).toBe('/my-tunes?add=1')
    expect(document.querySelector('.mt-add-pane')).toBeNull()
    await fireEvent.click(container.querySelector('#add-tune-btn'))
    expect(document.querySelector('.mt-add-pane')).toBeTruthy()
  })

  it('?add=1&q= landing (the folded-away add page redirect) auto-opens the pane and strips the params', async () => {
    window.history.replaceState({}, '', '/my-tunes?add=1&q=kesh')
    render(App, { pageData: payload() })
    await waitFor(() => expect(document.querySelector('.mt-add-pane')).toBeTruthy())
    expect(document.querySelector('.mt-add-pane .deep-field').value).toBe('kesh')
    // One-shot params are stripped so a refresh doesn't reopen the pane.
    expect(window.location.search).not.toContain('add=1')
    expect(window.location.search).not.toContain('q=kesh')
  })
})
