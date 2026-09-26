// static/js/offline_data.js — the IndexedDB mirror of the offline bundle. It loads from
// base.html, outside every Vite bundle, so it hand-copies the notation-search rules from
// src/shared/abcquery.js. That copy is exactly the thing that will drift, so it is
// pinned here: a query that matches online must match offline too.
//
// Offline notation matching is INCIPIT-ONLY — the bundle carries `incipit_abc`, never
// the full setting ABC — which is why hits are flagged `abc_scope: 'incipit'`.
import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest'

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
