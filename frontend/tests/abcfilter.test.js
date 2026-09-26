// The one notation-matching mechanism behind the three screens that filter a list they
// already hold (My Tunes, a session's Tunes tab, the admin tunes tab). What matters here
// is what it does NOT do: no request for an ordinary name query, no stale result winning
// over a newer one, and no error surfaced when the network is gone.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushSync } from 'svelte'
import { createAbcMatcher } from '../src/shared/abcfilter.svelte.js'

const IDS = () => [1, 2, 3]

// The matcher debounces by 150ms on top of its callers' own SearchField debounce.
const settle = async () => {
  await vi.advanceTimersByTimeAsync(200)
  await Promise.resolve()
  flushSync()
}

const ok = (tune_ids) => ({ ok: true, json: async () => ({ success: true, tune_ids }) })

describe('createAbcMatcher', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    global.fetch = vi.fn()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('never calls the server for an ordinary name query', async () => {
    const m = createAbcMatcher()
    m.update('Drowsy Maggie', IDS, 3)
    await settle()
    expect(fetch).not.toHaveBeenCalled()
    expect(m.ids.size).toBe(0)
  })

  it('never calls the server for a query below the shared minimum length', async () => {
    const m = createAbcMatcher()
    m.update('ge', IDS, 3)
    await settle()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('posts the visible ids and exposes the matching subset', async () => {
    fetch.mockResolvedValue(ok([2]))
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await settle()
    const [url, opts] = fetch.mock.calls[0]
    expect(url).toBe('/api/tunes/abc-filter')
    expect(JSON.parse(opts.body)).toEqual({ q: 'gedbed', tune_ids: [1, 2, 3] })
    expect([...m.ids]).toEqual([2])
  })

  it('clears immediately when the query stops looking like notes', async () => {
    fetch.mockResolvedValue(ok([2]))
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await settle()
    expect(m.ids.size).toBe(1)
    m.update('Drowsy Maggie', IDS, 3)
    flushSync()
    expect(m.ids.size).toBe(0) // synchronous — the sync filter must not lag a keystroke
  })

  it('lets the newest query win when responses land out of order', async () => {
    let resolveFirst
    fetch
      .mockReturnValueOnce(new Promise((r) => (resolveFirst = () => r(ok([1])))))
      .mockResolvedValueOnce(ok([3]))
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await vi.advanceTimersByTimeAsync(200)
    m.update('bedged', IDS, 3)
    await settle()
    resolveFirst() // the stale one answers last
    await Promise.resolve()
    flushSync()
    expect([...m.ids]).toEqual([3])
  })

  it('degrades to name-only when the request fails', async () => {
    fetch.mockRejectedValue(new Error('offline'))
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await settle()
    expect(m.ids.size).toBe(0)
  })

  it('degrades to name-only on a non-ok response', async () => {
    fetch.mockResolvedValue({ ok: false, json: async () => ({ success: false }) })
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await settle()
    expect(m.ids.size).toBe(0)
  })

  it('does not ask the server while offline', async () => {
    const spy = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await settle()
    expect(fetch).not.toHaveBeenCalled()
    spy.mockRestore()
  })

  it('reads the id list only when a request actually fires', async () => {
    fetch.mockResolvedValue(ok([]))
    const getIds = vi.fn(IDS)
    const m = createAbcMatcher()
    m.update('Drowsy Maggie', getIds, 3)
    await settle()
    expect(getIds).not.toHaveBeenCalled() // unrelated list churn must not cost anything
    m.update('gedbed', getIds, 3)
    await settle()
    expect(getIds).toHaveBeenCalledTimes(1)
  })

  it('retries once the list arrives, so a deep-linked search is not stranded', async () => {
    // These pages load their tunes AFTER mount. A ?search= in the URL therefore runs
    // against an empty list; without the retry the query would never be answered.
    fetch.mockResolvedValue(ok([1]))
    const m = createAbcMatcher()
    let list = []
    m.update('gedbed', () => list, list.length)
    await settle()
    expect(fetch).not.toHaveBeenCalled()

    list = IDS()
    m.update('gedbed', () => list, list.length)
    await settle()
    expect(fetch).toHaveBeenCalledTimes(1)
    expect([...m.ids]).toEqual([1])
  })

  it('retries the same needle after a failure', async () => {
    fetch.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(ok([2]))
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await settle()
    expect(m.ids.size).toBe(0)
    m.update('gedbed', IDS, 3)
    await settle()
    expect([...m.ids]).toEqual([2])
  })

  it('retries after coming back online', async () => {
    const spy = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    fetch.mockResolvedValue(ok([1]))
    const m = createAbcMatcher()
    m.update('gedbed', IDS, 3)
    await settle()
    expect(fetch).not.toHaveBeenCalled()

    spy.mockReturnValue(true)
    m.update('gedbed', IDS, 3)
    await settle()
    expect([...m.ids]).toEqual([1])
    spy.mockRestore()
  })

  it('does not re-query an unchanged needle', async () => {
    fetch.mockResolvedValue(ok([1]))
    const m = createAbcMatcher()
    m.update('ged bed', IDS, 3)
    await settle()
    m.update('  gedbed  ', IDS, 3) // same notes, different keystrokes
    await settle()
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
