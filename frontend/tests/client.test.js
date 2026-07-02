import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  bootstrap, sendOp, searchTunes, liveMatch, deepSearch, openStream,
} from '../src/client.js'

const config = { sessionInstanceId: 42, streamingBaseUrl: 'http://stream.test/' }

function mockFetchOnce({ ok = true, status = 200, json = {}, reject = null }) {
  const fn = vi.fn(() => {
    if (reject) return Promise.reject(reject)
    return Promise.resolve({ ok, status, json: () => Promise.resolve(json) })
  })
  global.fetch = fn
  return fn
}

afterEach(() => { vi.restoreAllMocks() })

describe('bootstrap', () => {
  it('returns parsed JSON on success', async () => {
    mockFetchOnce({ json: { records: [1, 2] } })
    expect(await bootstrap(config)).toEqual({ records: [1, 2] })
  })

  it('flags network failures with networkError so the caller can fall back', async () => {
    mockFetchOnce({ reject: new TypeError('Failed to fetch') })
    await expect(bootstrap(config)).rejects.toMatchObject({ networkError: true })
  })

  it('throws on a non-ok response', async () => {
    mockFetchOnce({ ok: false, status: 500 })
    await expect(bootstrap(config)).rejects.toThrow(/bootstrap failed: 500/)
  })
})

describe('sendOp', () => {
  it('posts the op and returns the ack JSON', async () => {
    const fn = mockFetchOnce({ json: { success: true, event_id: 5 } })
    const out = await sendOp(config, 'add_tune', { tune_id: 3 }, 'op-1')
    expect(out).toEqual({ success: true, event_id: 5 })
    const [url, opts] = fn.mock.calls[0]
    expect(url).toBe('/api/live/instances/42/ops')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ op_id: 'op-1', op_type: 'add_tune', tune_id: 3 })
  })

  it('marks a network failure (offline/timeout) as networkError', async () => {
    mockFetchOnce({ reject: new TypeError('Failed to fetch') })
    await expect(sendOp(config, 'add_tune', {}, 'op-2')).rejects.toMatchObject({ networkError: true })
  })

  it('throws with the server-provided error message on !ok', async () => {
    mockFetchOnce({ ok: false, status: 400, json: { error: 'bad op' } })
    await expect(sendOp(config, 'add_tune', {}, 'op-3')).rejects.toThrow('bad op')
  })
})

describe('lenient search helpers', () => {
  it('searchTunes returns the tunes array on success', async () => {
    mockFetchOnce({ json: { tunes: [{ tune_id: 1 }] } })
    expect(await searchTunes(config, 'reel', 7)).toEqual([{ tune_id: 1 }])
  })

  it('searchTunes returns [] on a non-ok response (search is non-critical)', async () => {
    mockFetchOnce({ ok: false, status: 500 })
    expect(await searchTunes(config, 'reel')).toEqual([])
  })

  it('searchTunes returns [] when fetch throws', async () => {
    mockFetchOnce({ reject: new Error('boom') })
    expect(await searchTunes(config, 'reel')).toEqual([])
  })

  it('liveMatch maps tune_name -> name and returns a safe shape on error', async () => {
    mockFetchOnce({ json: { exact_match: true, results: [{ tune_id: 1, tune_name: 'Cooleys', tune_type: 'Reel', in_session_tune: true }] } })
    const out = await liveMatch(config, 'cooleys')
    expect(out.exact_match).toBe(true)
    expect(out.results[0]).toEqual({ tune_id: 1, name: 'Cooleys', tune_type: 'Reel', in_session_tune: true })

    mockFetchOnce({ reject: new Error('offline') })
    expect(await liveMatch(config, 'cooleys')).toEqual({ exact_match: false, results: [] })
  })

  it('deepSearch returns [] on error', async () => {
    mockFetchOnce({ ok: false, status: 500 })
    expect(await deepSearch(config, 'q')).toEqual([])
  })
})

// --- SSE wiring (openStream) ------------------------------------------------
// A minimal fake EventSource records listeners so we can emit server events and
// assert the handler wiring + the onStatus lifecycle.
class FakeEventSource {
  constructor(url, opts) {
    this.url = url
    this.opts = opts
    this.listeners = {}
    FakeEventSource.last = this
  }
  addEventListener(type, cb) { (this.listeners[type] ||= []).push(cb) }
  emit(type, data) { (this.listeners[type] || []).forEach((cb) => cb({ data })) }
  close() { this.closed = true }
}

describe('openStream', () => {
  beforeEach(() => { global.EventSource = FakeEventSource })

  it('builds the URL with the high-water mark and mode, and wires handlers', () => {
    const onOp = vi.fn()
    const onPresence = vi.fn()
    const onTyping = vi.fn()
    const onStatus = vi.fn()
    const es = openStream(config, 17, { onOp, onPresence, onTyping, onStatus }, 'view')

    expect(es.url).toBe('http://stream.test/live/instances/42/events?last_event_id=17&mode=view')
    expect(es.opts.withCredentials).toBe(true)

    es.onopen()
    expect(onStatus).toHaveBeenCalledWith('live')

    es.emit('op', JSON.stringify({ op_type: 'add_tune', record: { id: 1 } }))
    expect(onOp).toHaveBeenCalledWith({ op_type: 'add_tune', record: { id: 1 } })

    es.emit('presence', JSON.stringify({ roster: [{ person_id: 1 }] }))
    expect(onPresence).toHaveBeenCalledWith([{ person_id: 1 }])

    es.emit('typing', JSON.stringify({ typing: [{ person_id: 2 }] }))
    expect(onTyping).toHaveBeenCalledWith([{ person_id: 2 }])
  })

  it('ignores malformed op payloads without throwing', () => {
    const onOp = vi.fn()
    const es = openStream(config, 0, { onOp }, 'edit')
    expect(() => es.emit('op', 'not json{')).not.toThrow()
    expect(onOp).not.toHaveBeenCalled()
  })

  it('defaults an unknown mode to edit', () => {
    const es = openStream(config, 0, {}, undefined)
    expect(es.url).toContain('mode=edit')
  })
})
