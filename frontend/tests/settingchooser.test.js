// The setting chooser (opened from the tune drawer): pages every setting of a tune
// with its full notation, opens on the one in use, and renders ahead of the user so
// paging feels instant.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, waitFor, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import SettingChooser from '../src/tunesheet/SettingChooser.svelte'

const local = (id) => ({ setting_id: id, key: 'Dmajor', abc: `abc-${id}`, incipit_abc: `inc-${id}`, incipit_image: null })

let fetchMock
function stubFetch(routes) {
  fetchMock = vi.fn().mockImplementation((url, opts = {}) => {
    for (const [match, responder] of routes) {
      if (String(url).includes(match)) {
        const body = typeof responder === 'function' ? responder(url, opts) : responder
        return Promise.resolve({ ok: true, status: 200, json: async () => body })
      }
    }
    return Promise.resolve({ ok: false, status: 404, json: async () => ({ success: false }) })
  })
  vi.stubGlobal('fetch', fetchMock)
}
const urls = () => fetchMock.mock.calls.map(([u]) => String(u))
const remoteRenders = () =>
  fetchMock.mock.calls.filter(([u]) => String(u).includes('/render-abc')).map(([, o]) => JSON.parse(o.body))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

// client.js caches previews and images for the page's lifetime, so every test uses
// its own tune and setting ids.
function routesFor(tuneId, localIds, allIds) {
  return [
    [`/api/tunes/${tuneId}/preview`, { success: true, tune_id: tuneId, settings: localIds.map(local) }],
    [
      `/api/tunes/thesession/${tuneId}/preview`,
      { success: true, tune_id: tuneId, settings: allIds.map((id) => ({ setting_id: id, key: 'Gmajor', abc: `abc-${id}`, incipit_abc: `inc-${id}` })) },
    ],
    ['/api/tunes/settings/', (url) => ({ success: true, image: `IMG-${String(url).match(/settings\/(\d+)/)[1]}` })],
    ['/api/tunes/render-abc', (url, opts) => ({ success: true, image: `R-${JSON.parse(opts.body).abc}` })],
  ]
}

describe('SettingChooser', () => {
  it('opens on the setting in use, in thesession.org order, with its full notation', async () => {
    stubFetch(routesFor(501, [5120], [5110, 5120, 5130, 5140]))
    render(SettingChooser, { open: true, tuneId: 501, tuneName: 'The Kesh', tuneType: 'jig', currentSettingId: 5120, heading: 'Which?', onChoose: vi.fn() })

    // The backfill merges the settings we don't hold in setting order, and the pager
    // stays on the one in use rather than jumping to the new first.
    await waitFor(() => expect(document.body.textContent).toContain('Setting 2 of 4'))
    expect(document.body.textContent).toContain('#5120')
    expect(document.body.textContent).toContain('in use')
    await waitFor(() => expect(document.querySelector('.sc-notation img')?.src).toContain('IMG-5120'))
    expect(urls()).toContain('/api/tunes/settings/5120/image?kind=full')
    const use = screen.getByRole('button', { name: 'This is the one in use' })
    expect(use.disabled).toBe(true)
  })

  it('renders the next two settings before the user gets there, and none behind', async () => {
    stubFetch(routesFor(502, [5210, 5220], [5210, 5220, 5230, 5240, 5250]))
    render(SettingChooser, { open: true, tuneId: 502, tuneType: 'reel', currentSettingId: 5220, onChoose: vi.fn() })

    // 5220 is in view: 5230 and 5240 (only thesession.org has them) render ahead; 5250
    // is three away and 5210 is behind, so neither is asked for yet.
    await waitFor(() => expect(remoteRenders().map((b) => b.abc)).toEqual(['abc-5230', 'abc-5240']))
    expect(remoteRenders().every((b) => b.kind === 'full' && b.tune_type === 'reel')).toBe(true)
    expect(urls().some((u) => u.includes('/settings/5210/'))).toBe(false)

    // Paging on is instant — the image is already here — and the run moves with you.
    await fireEvent.click(screen.getByRole('button', { name: 'Next setting' }))
    expect(document.querySelector('.sc-notation img').src).toContain('R-abc-5230')
    await waitFor(() => expect(remoteRenders().map((b) => b.abc)).toContain('abc-5250'))
  })

  it('hands the picked setting and its image to the drawer, and closes once saved', async () => {
    stubFetch(routesFor(503, [5310], [5310, 5320]))
    const onChoose = vi.fn().mockResolvedValue(true)
    render(SettingChooser, { open: true, tuneId: 503, currentSettingId: 5310, onChoose })
    await waitFor(() => expect(document.body.textContent).toContain('Setting 1 of 2'))

    await fireEvent.click(screen.getByRole('button', { name: 'Next setting' }))
    await waitFor(() => expect(document.querySelector('.sc-notation img')?.src).toContain('R-abc-5320'))
    await fireEvent.click(screen.getByRole('button', { name: 'Use this setting' }))
    await waitFor(() => expect(onChoose).toHaveBeenCalled())
    const [picked, image] = onChoose.mock.calls[0]
    expect(picked).toMatchObject({ setting_id: 5320, remote: true })
    expect(image).toBe('R-abc-5320')
    await waitFor(() => expect(document.querySelector('.sc-notation')).toBeNull())
  })

  it('stays open when the save fails', async () => {
    stubFetch(routesFor(504, [5410, 5420], [5410, 5420]))
    const onChoose = vi.fn().mockResolvedValue(false)
    render(SettingChooser, { open: true, tuneId: 504, currentSettingId: 5410, onChoose })
    await waitFor(() => expect(document.body.textContent).toContain('Setting 1 of 2'))
    await fireEvent.click(screen.getByRole('button', { name: 'Next setting' }))
    await fireEvent.click(screen.getByRole('button', { name: 'Use this setting' }))
    await waitFor(() => expect(onChoose).toHaveBeenCalled())
    expect(document.querySelector('.sc-notation')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Use this setting' }).disabled).toBe(false)
  })
})
