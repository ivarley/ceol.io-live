// Export mode's round trip (src/lib/export.js): the URL flag, and the
// check → warm → download sequence against the server contract
// (POST <url> {format, ids, filters[, check]}; GET /api/tunes/settings/<id>/image?kind=full).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  filenameFrom,
  isExportMode,
  leaveExportMode,
  runExport,
  urlWithoutExport,
  warmNotation,
  withExportParam,
  ExportError,
  EXPORT_EVENT,
} from '../src/lib/export.js'

const jsonRes = (body, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => body,
  headers: new Headers(),
})
const fileRes = (name, type = 'application/pdf') => ({
  ok: true,
  status: 200,
  blob: async () => new Blob(['x'], { type }),
  headers: new Headers({ 'Content-Disposition': `attachment; filename="${name}"` }),
})

describe('the export flag', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/my-tunes?status=learning&export=1&sortType=plays')
  })
  afterEach(() => {
    window.history.replaceState({}, '', '/')
  })

  it('reads export=1', () => {
    expect(isExportMode()).toBe(true)
    expect(isExportMode('?status=learning')).toBe(false)
  })

  it('leaveExportMode drops only the flag and announces the change', () => {
    const heard = vi.fn()
    window.addEventListener(EXPORT_EVENT, heard)
    leaveExportMode()
    expect(window.location.pathname + window.location.search).toBe('/my-tunes?status=learning&sortType=plays')
    expect(isExportMode()).toBe(false)
    expect(heard).toHaveBeenCalledTimes(1)
    window.removeEventListener(EXPORT_EVENT, heard)
  })

  it('urlWithoutExport keeps the hash', () => {
    expect(urlWithoutExport({ pathname: '/p', search: '?export=1&a=1', hash: '#x' })).toBe('/p?a=1#x')
    expect(urlWithoutExport({ pathname: '/p', search: '?export=1', hash: '' })).toBe('/p')
  })

  it('withExportParam adds or removes the flag on a page-built param set', () => {
    expect(withExportParam(new URLSearchParams('a=1'), true).toString()).toBe('a=1&export=1')
    expect(withExportParam(new URLSearchParams('a=1&export=1'), false).toString()).toBe('a=1')
  })
})

describe('filenameFrom', () => {
  it('prefers the RFC 5987 form, then the quoted one', () => {
    expect(filenameFrom(`attachment; filename="a.csv"; filename*=UTF-8''Se%C3%A1n.csv`)).toBe('Seán.csv')
    expect(filenameFrom('attachment; filename="my-tunes.json"')).toBe('my-tunes.json')
    // Flask leaves the plain form unquoted when the name needs no quoting.
    expect(filenameFrom('attachment; filename=ceol-my-tunes-2026-11-24.json')).toBe('ceol-my-tunes-2026-11-24.json')
    expect(filenameFrom(null)).toBe(null)
  })
})

describe('runExport', () => {
  let clicks
  beforeEach(() => {
    clicks = []
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      clicks.push(this.download)
    })
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('json: one POST, then the file is handed to the browser', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(fileRes('my-tunes.json', 'application/json'))
    const name = await runExport({
      url: '/api/export/my-tunes',
      format: 'json',
      body: { tune_ids: [3, 1, 2], filters: ['Status: Learning'] },
      fetchFn,
    })
    expect(fetchFn).toHaveBeenCalledTimes(1)
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/export/my-tunes')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ tune_ids: [3, 1, 2], filters: ['Status: Learning'], format: 'json' })
    expect(name).toBe('my-tunes.json')
    expect(clicks).toEqual(['my-tunes.json'])
  })

  it('pdf: check, warm each missing setting (reporting progress), then fetch the file', async () => {
    const progress = []
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(jsonRes({ success: true, missing_setting_ids: [11, 12, 13], total: 40 }))
      .mockResolvedValueOnce(jsonRes({ success: true, image: 'a' }))
      .mockResolvedValueOnce(jsonRes({ success: true, image: 'b' }))
      .mockResolvedValueOnce(jsonRes({ success: true, image: 'c' }))
      .mockResolvedValueOnce(fileRes('tunes.pdf'))
    await runExport({
      url: '/api/export/sessions/austin/tunes',
      format: 'pdf',
      body: { tune_ids: [1], filters: [] },
      onProgress: (p) => progress.push(p),
      fetchFn,
    })
    const calls = fetchFn.mock.calls.map(([u, i]) => [u, i?.method || 'GET', i?.body ? JSON.parse(i.body) : null])
    expect(calls[0]).toEqual(['/api/export/sessions/austin/tunes', 'POST', { tune_ids: [1], filters: [], format: 'pdf', check: true }])
    expect(calls.slice(1, 4).map((c) => c[0]).sort()).toEqual([
      '/api/tunes/settings/11/image?kind=full',
      '/api/tunes/settings/12/image?kind=full',
      '/api/tunes/settings/13/image?kind=full',
    ])
    expect(calls[4]).toEqual(['/api/export/sessions/austin/tunes', 'POST', { tune_ids: [1], filters: [], format: 'pdf' }])
    expect(progress.at(0)).toEqual({ done: 0, total: 3 })
    expect(progress.at(-2)).toEqual({ done: 3, total: 3 })
    expect(progress.at(-1)).toBe(null)
    expect(clicks).toEqual(['tunes.pdf'])
  })

  it('pdf with nothing to warm skips the image requests', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(jsonRes({ success: true, missing_setting_ids: [], total: 2 }))
      .mockResolvedValueOnce(fileRes('tunes.pdf'))
    await runExport({ url: '/x', format: 'pdf', body: { tune_ids: [1] }, fetchFn })
    expect(fetchFn).toHaveBeenCalledTimes(2)
  })

  it("surfaces the server's own message on a refusal", async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(jsonRes({ success: false, error: 'Too many tunes', message: 'Too many tunes to export at once.' }, false, 413))
    await expect(runExport({ url: '/x', format: 'csv', body: {}, fetchFn })).rejects.toMatchObject({
      message: 'Too many tunes to export at once.',
      status: 413,
    })
    expect(clicks).toEqual([])
  })

  it('refuses an unknown format before touching the network', async () => {
    const fetchFn = vi.fn()
    await expect(runExport({ url: '/x', format: 'xlsx', body: {}, fetchFn })).rejects.toBeInstanceOf(ExportError)
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('warmNotation runs two at a time and shrugs off a failed image', async () => {
    let inFlight = 0
    let peak = 0
    const fetchFn = vi.fn().mockImplementation(async (url) => {
      inFlight++
      peak = Math.max(peak, inFlight)
      await new Promise((r) => setTimeout(r, 1))
      inFlight--
      if (url.includes('/2/')) throw new Error('boom')
      return jsonRes({ success: true })
    })
    const progress = []
    await warmNotation([1, 2, 3, 4, 5], { fetchFn, onProgress: (p) => progress.push(p.done) })
    expect(fetchFn).toHaveBeenCalledTimes(5)
    expect(peak).toBeLessThanOrEqual(2)
    expect(progress.at(-1)).toBe(5)
  })
})
