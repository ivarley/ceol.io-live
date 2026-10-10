// static/js/offline_data.js — the IndexedDB mirror of the offline bundle. It loads from
// base.html, outside every Vite bundle, so it hand-copies the notation-search rules from
// src/shared/abcquery.js. That copy is exactly the thing that will drift, so it is
// pinned here: a query that matches online must match offline too.
//
// Offline notation matching is INCIPIT-ONLY — the bundle carries `incipit_abc`, never
// the full setting ABC — which is why hits are flagged `abc_scope: 'incipit'`.
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest'

const TUNE = (over) => ({
  tune_id: 1, name: 'Drowsy Maggie', tune_type: 'Reel', tunebook_count: 100,
  incipit_abc: '|:E2BE dEBE|', ...over,
})

let CeolOffline

beforeAll(async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
  await import('../../static/js/offline_data.js')
  CeolOffline = window.CeolOffline
})

// The module's only write path is replaceStore, reached through sync(); drive it with a
// stubbed bundle response so each test starts from a known tunebook.
async function seed(tunes, popular = []) {
  fetch.mockResolvedValue({ ok: true, json: async () => ({ success: true, tunes, popular }) })
  await CeolOffline.sync(true)
}

describe('CeolOffline.searchTunes', () => {
  beforeEach(() => {
    fetch.mockClear()
  })

  it('still finds tunes by name', async () => {
    await seed([TUNE()])
    const out = await CeolOffline.searchTunes('drowsy', 10)
    expect(out.map((t) => t.tune_id)).toEqual([1])
    expect(out[0].abc_only).toBeFalsy()
  })

  it('finds a tune by its opening notes, whitespace ignored', async () => {
    await seed([TUNE()])
    const out = await CeolOffline.searchTunes('E2BE dEBE', 10)
    expect(out.map((t) => t.tune_id)).toEqual([1])
  })

  it('flags notation hits as incipit-scoped, so the UI can say "opening bars"', async () => {
    await seed([TUNE()])
    const [hit] = await CeolOffline.searchTunes('e2bedebe', 10)
    expect(hit.abc_only).toBe(true)
    expect(hit.abc_scope).toBe('incipit')
  })

  it('matches through grace notes and chord symbols, as the server does', async () => {
    await seed([TUNE({ incipit_abc: '|:"Em"{a}G E D {c}B E D|' })])
    expect((await CeolOffline.searchTunes('GEDBED', 10)).map((t) => t.tune_id)).toEqual([1])
  })

  it('ranks name matches above notation matches', async () => {
    await seed([
      TUNE({ tune_id: 1, name: 'Gedbed Reel', incipit_abc: '|:cAAfdd|' }),
      TUNE({ tune_id: 2, name: 'Something Else', incipit_abc: '|:GED BED|' }),
    ])
    expect((await CeolOffline.searchTunes('gedbed', 10)).map((t) => t.tune_id)).toEqual([1, 2])
  })

  it('never lists a tune twice when it matches both ways', async () => {
    await seed([TUNE({ name: 'Gedbed Reel', incipit_abc: '|:GED BED|' })])
    expect(await CeolOffline.searchTunes('gedbed', 10)).toHaveLength(1)
  })

  it('does not notation-match a name query', async () => {
    await seed([TUNE({ name: 'Other', incipit_abc: '|:E2BE dEBE|' })])
    expect(await CeolOffline.searchTunes('drowsy maggie', 10)).toHaveLength(0)
  })

  it('does not notation-match below the shared minimum length', async () => {
    await seed([TUNE({ name: 'Other', incipit_abc: '|:E2BE dEBE|' })])
    expect(await CeolOffline.searchTunes('e2', 10)).toHaveLength(0)
  })
})

// A laptop waking with many ceol.io tabs fires sync() in all of them at once; only the
// tab holding the cross-tab lock may fetch the bundle (2026-10-07 out-of-memory).
describe('CeolOffline.sync across tabs', () => {
  afterEach(() => {
    delete navigator.locks
  })

  it('skips the fetch when another tab holds the sync lock', async () => {
    navigator.locks = { request: vi.fn(async (_name, _opts, cb) => cb(null)) }
    fetch.mockClear()
    await CeolOffline.sync(true)
    expect(navigator.locks.request).toHaveBeenCalledWith(
      'ceol-offline-sync', { ifAvailable: true }, expect.any(Function))
    expect(fetch).not.toHaveBeenCalled()
  })

  it('fetches when it gets the lock', async () => {
    navigator.locks = { request: vi.fn(async (_name, _opts, cb) => cb({ name: 'ceol-offline-sync' })) }
    fetch.mockClear()
    fetch.mockResolvedValue({ ok: true, json: async () => ({ success: true, tunes: [], popular: [] }) })
    await CeolOffline.sync(true)
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

// The bundle carries a version (ETag). The next sync sends it back; a 304 means the copy
// held is current, so nothing is downloaded or rewritten.
describe('CeolOffline.sync with a version', () => {
  const bundle = (tunes, etag) => ({
    ok: true, status: 200,
    headers: { get: (h) => (h === 'ETag' ? etag : null) },
    json: async () => ({ success: true, tunes, popular: [] }),
  })

  it('sends the version it holds, and keeps its copy on a 304', async () => {
    fetch.mockClear()
    fetch.mockResolvedValueOnce(bundle([TUNE({ tune_id: 7, name: 'Kesh' })], '"v1"'))
    await CeolOffline.sync(true)

    fetch.mockResolvedValueOnce({ ok: false, status: 304, headers: { get: () => null } })
    await CeolOffline.sync(true)

    const [, opts] = fetch.mock.calls[1]
    expect(opts.headers['If-None-Match']).toBe('"v1"')
    expect(opts.cache).toBe('no-store')
    expect((await CeolOffline.getTunes()).map((t) => t.tune_id)).toEqual([7])
  })

  it('replaces its copy and its version when the bundle changed', async () => {
    fetch.mockClear()
    fetch.mockResolvedValueOnce(bundle([TUNE({ tune_id: 8, name: 'Banshee' })], '"v2"'))
    await CeolOffline.sync(true)
    fetch.mockResolvedValueOnce({ ok: false, status: 304, headers: { get: () => null } })
    await CeolOffline.sync(true)
    expect(fetch.mock.calls[1][1].headers['If-None-Match']).toBe('"v2"')
    expect((await CeolOffline.getTunes()).map((t) => t.tune_id)).toEqual([8])
  })
})
