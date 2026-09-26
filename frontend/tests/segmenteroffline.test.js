// static/js/segmenter_offline.js — the recording segmenter's offline store
// (spec 050 "Offline"): a coalescing write queue for marks, a mirror of the
// tool's working copy, and saved audio. Loaded from base.html outside every
// Vite bundle, so it is exercised here as the global it installs.
import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest'

let SO

beforeAll(async () => {
  vi.stubGlobal('fetch', vi.fn())
  await import('../../static/js/segmenter_offline.js')
  SO = window.SegmenterOffline
})

// fake-indexeddb backs one process-wide database and the module caches its
// connection, so tests isolate by recording id rather than by resetting the store.
let nextRec = 5000
const freshRec = () => ++nextRec

const ok = (body) => ({ ok: true, status: 200, json: async () => body })
const refused = (status, error) => ({ ok: false, status, json: async () => ({ success: false, error }) })
const offlineFailure = () => Promise.reject(new TypeError('Failed to fetch'))

const put = (rec, sit, start_ms, end_ms = null) => ({
  recording_id: rec, session_instance_tune_id: sit, kind: 'put', start_ms, end_ms,
})
const clear = (rec, sit) => ({ recording_id: rec, session_instance_tune_id: sit, kind: 'delete' })

beforeEach(() => {
  fetch.mockReset()
})

describe('submit', () => {
  it('PUTs the placement and leaves nothing queued when the server answers', async () => {
    const rec = freshRec()
    fetch.mockResolvedValue(ok({ success: true, segment: { start_ms: 1000, end_ms: null } }))
    const r = await SO.submit(put(rec, 1, 1000))
    expect(r).toMatchObject({ online: true, queued: false })
    expect(r.data.segment.start_ms).toBe(1000)
    expect(fetch).toHaveBeenCalledWith(
      `/api/recordings/${rec}/segments/1`,
      expect.objectContaining({ method: 'PUT', body: JSON.stringify({ start_ms: 1000, end_ms: null }) }),
    )
    expect(await SO.pending(rec)).toEqual([])
  })

  it('DELETEs a clear with no body', async () => {
    const rec = freshRec()
    fetch.mockResolvedValue(ok({ success: true }))
    await SO.submit(clear(rec, 2))
    const [, init] = fetch.mock.calls[0]
    expect(init.method).toBe('DELETE')
    expect(init.body).toBeUndefined()
  })

  it('queues the op and announces it when the network is gone', async () => {
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    const heard = vi.fn()
    window.addEventListener('segmenter-queued', heard)
    const r = await SO.submit(put(rec, 1, 1000))
    window.removeEventListener('segmenter-queued', heard)
    expect(r).toEqual({ online: false, queued: true })
    expect(heard).toHaveBeenCalled()
    const q = await SO.pending(rec)
    expect(q).toHaveLength(1)
    expect(q[0]).toMatchObject({ session_instance_tune_id: 1, kind: 'put', start_ms: 1000 })
  })

  it('keeps ONE entry per tune — the latest placement wins', async () => {
    // Every op is the final state of one tune, so re-marking offline replaces
    // the earlier op instead of replaying both.
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(rec, 1, 1000))
    await SO.submit(put(rec, 1, 2500))
    await SO.submit(put(rec, 2, 9000))
    const q = await SO.pending(rec)
    expect(q.map((o) => [o.session_instance_tune_id, o.start_ms])).toEqual([[1, 2500], [2, 9000]])
  })

  it('a clear after an offline placement replaces it with the delete', async () => {
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(rec, 1, 1000))
    await SO.submit(clear(rec, 1))
    const q = await SO.pending(rec)
    expect(q).toHaveLength(1)
    expect(q[0].kind).toBe('delete')
  })

  it('a server refusal rejects and is NOT queued — it cannot succeed on replay', async () => {
    const rec = freshRec()
    fetch.mockResolvedValue(refused(400, 'end_ms must be after start_ms'))
    await expect(SO.submit(put(rec, 1, 5000, 4000))).rejects.toThrow('end_ms must be after start_ms')
    expect(await SO.pending(rec)).toEqual([])
  })

  it('an online send supersedes an older queued op for the same tune', async () => {
    // Reconnected but not yet flushed: the new placement goes straight out, and
    // the stale one must not replay behind it and put the mark back.
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(rec, 1, 1000))
    fetch.mockResolvedValue(ok({ success: true, segment: {} }))
    await SO.submit(put(rec, 1, 3000))
    expect(await SO.pending(rec)).toEqual([])
  })

  it('scopes pending() to one recording when asked', async () => {
    const a = freshRec()
    const b = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(a, 1, 1))
    await SO.submit(put(b, 1, 1))
    expect((await SO.pending(a)).map((o) => o.recording_id)).toEqual([a])
  })
})

describe('flush', () => {
  it('replays oldest-first, clears what lands, and reports the drain', async () => {
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(rec, 1, 1000))
    await SO.submit(put(rec, 2, 2000))
    fetch.mockClear() // the two failed attempts above are not replays
    fetch.mockResolvedValue(ok({ success: true, segment: {} }))
    const synced = vi.fn()
    window.addEventListener('segmenter-synced', synced)
    await SO.flush()
    window.removeEventListener('segmenter-synced', synced)
    // flush() drains EVERY recording's queue, including what earlier tests
    // left behind, so look only at this recording's calls.
    const mine = fetch.mock.calls.map((c) => c[0]).filter((u) => u.startsWith(`/api/recordings/${rec}/`))
    expect(mine).toEqual([`/api/recordings/${rec}/segments/1`, `/api/recordings/${rec}/segments/2`])
    expect(await SO.pending(rec)).toEqual([])
    const detail = synced.mock.calls[0][0].detail
    expect(detail.cleared).toBeGreaterThanOrEqual(2)
    expect(detail.rejected.filter((r) => r.recording_id === rec)).toEqual([])
    expect(detail.recording_ids).toContain(rec)
  })

  it('stops at the first network failure and keeps the rest', async () => {
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(rec, 1, 1000))
    await SO.submit(put(rec, 2, 2000))
    // Still offline: nothing should be dropped.
    await SO.flush()
    expect(await SO.pending(rec)).toHaveLength(2)
  })

  it('discards a refused op and names it, so the page can put the mark back', async () => {
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(rec, 1, 1000))
    fetch.mockResolvedValue(refused(400, 'That tune has been deleted from the log'))
    const synced = vi.fn()
    window.addEventListener('segmenter-synced', synced)
    await SO.flush()
    window.removeEventListener('segmenter-synced', synced)
    expect(await SO.pending(rec)).toEqual([])
    const detail = synced.mock.calls[0][0].detail
    expect(detail.rejected.filter((r) => r.recording_id === rec)).toEqual([
      expect.objectContaining({ recording_id: rec, session_instance_tune_id: 1, error: 'That tune has been deleted from the log' }),
    ])
  })

  it('a delete the server never had is not a rejection worth reporting', async () => {
    // Placed then cleared, both offline: the queue holds only the delete, and
    // the server answers 404 because it never saw the placement. That is the
    // state being asked for.
    const rec = freshRec()
    fetch.mockImplementation(offlineFailure)
    await SO.submit(put(rec, 1, 1000))
    await SO.submit(clear(rec, 1))
    fetch.mockResolvedValue(refused(404, 'No segment for that tune'))
    const synced = vi.fn()
    window.addEventListener('segmenter-synced', synced)
    await SO.flush()
    window.removeEventListener('segmenter-synced', synced)
    expect(synced.mock.calls[0][0].detail.rejected.filter((r) => r.recording_id === rec)).toEqual([])
    expect(await SO.pending(rec)).toEqual([])
  })
})

describe('mirror', () => {
  it('round-trips the working copy with the payload stamp it grew from', async () => {
    const rec = freshRec()
    const tunes = [{ session_instance_tune_id: 1, name: 'A', segment: { start_ms: 5, end_ms: null } }]
    await SO.mirrorPut(rec, { generated_at: '2026-09-20T10:00:00+00:00', tunes })
    const m = await SO.mirrorGet(rec)
    expect(m.generated_at).toBe('2026-09-20T10:00:00+00:00')
    expect(m.tunes).toEqual(tunes)
  })

  it('is empty for a recording never opened', async () => {
    expect(await SO.mirrorGet(freshRec())).toBeUndefined()
  })
})

describe('saved audio', () => {
  // A streaming body of two chunks, so progress is reported along the way.
  function streamingResponse(bytes, type = 'audio/mp4') {
    const chunks = [bytes.slice(0, 3), bytes.slice(3)]
    let i = 0
    return {
      ok: true,
      status: 200,
      headers: new Headers({ 'Content-Type': type, 'Content-Length': String(bytes.length) }),
      body: {
        getReader: () => ({
          read: async () => (i < chunks.length ? { done: false, value: chunks[i++] } : { done: true }),
        }),
      },
    }
  }

  it('downloads the encode, stores it as a Blob, and reports progress', async () => {
    const rec = freshRec()
    const bytes = new Uint8Array([1, 2, 3, 4, 5])
    fetch.mockResolvedValue(streamingResponse(bytes))
    const progress = vi.fn()
    const source = { id: 'proxy', url: 'https://bucket/proxy.m4a?sig', mime_type: 'audio/mp4', size_bytes: 5 }
    const entry = await SO.saveAudio(rec, source, { onProgress: progress })
    expect(fetch).toHaveBeenCalledWith(source.url, expect.objectContaining({ mode: 'cors' }))
    expect(entry.size_bytes).toBe(5)
    expect(progress).toHaveBeenLastCalledWith({ loaded: 5, total: 5 })

    // fake-indexeddb's structured clone does not carry a jsdom Blob's bytes,
    // so the stored row is checked by its recorded size rather than blob.size.
    const stored = await SO.audioGet(rec, 'proxy')
    expect(stored.size_bytes).toBe(5)
    expect(stored.blob).toBeTruthy()
    expect(stored.mime_type).toBe('audio/mp4')
    expect((await SO.audioList(rec)).map((a) => a.source_id)).toEqual(['proxy'])
  })

  it('forgets a copy on request', async () => {
    const rec = freshRec()
    fetch.mockResolvedValue(streamingResponse(new Uint8Array([9, 9, 9, 9])))
    await SO.saveAudio(rec, { id: 'proxy', url: 'https://bucket/x', size_bytes: 4 })
    await SO.audioDelete(rec, 'proxy')
    expect(await SO.audioList(rec)).toEqual([])
  })

  it('surfaces an HTTP failure rather than storing an error page as audio', async () => {
    const rec = freshRec()
    fetch.mockResolvedValue({ ok: false, status: 403, headers: new Headers() })
    await expect(SO.saveAudio(rec, { id: 'proxy', url: 'https://bucket/expired' })).rejects.toThrow('HTTP 403')
    expect(await SO.audioList(rec)).toEqual([])
  })
})
