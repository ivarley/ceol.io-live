// The My Tunes add pane (AddTuneApp) driven end to end from a PASTED thesession.org
// link: the ?setting=/#setting deep link must ride the add all the way to the POST,
// and a tune that turns out to be already on the list must not silently swallow it.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor, fireEvent } from '@testing-library/svelte'

const SETTINGS = [
  { setting_id: 8006, key: 'Edorian', abc: 'A', incipit_abc: 'A' },
  { setting_id: 19237, key: 'Edorian', abc: 'B', incipit_abc: 'B' },
  { setting_id: 29513, key: 'Edorian', abc: 'C', incipit_abc: 'C' },
  { setting_id: 34003, key: 'Edorian', abc: 'D', incipit_abc: 'D' },
]

// The tune is in the local catalog with ONE imported setting; the rest arrive from the
// thesession.org backfill, exactly as they do for a real paste.
const tunePreview = vi.fn(async () => ({
  tune_id: 8006,
  name: 'Scatter The Dew',
  tune_type: 'Hop Jig',
  settings: [SETTINGS[0]],
  aliases: [],
  session_setting_id: null,
}))
const thesessionPreview = vi.fn(async (cfg, id, full) =>
  full
    ? { tune_id: 8006, settings: SETTINGS, aliases: ['Sciap An Druct'] }
    : { is_local: true, tune_id: 8006, name: 'Spatter The Dew', tune_type: 'slip jig', settings: [] }
)

vi.mock('../src/client.js', () => ({
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  thesessionPreview: (...a) => thesessionPreview(...a),
  tunePreview: (...a) => tunePreview(...a),
  settingImage: vi.fn(() => Promise.resolve({ image: null })),
  renderRemoteAbc: vi.fn(() => Promise.resolve({ image: null })),
  fetchIncipit: vi.fn(async () => null),
}))

const PASTED = 'https://thesession.org/tunes/8006#setting29513'

let AddTuneApp
beforeEach(async () => {
  vi.clearAllMocks()
  delete window.MyTunesOffline
  AddTuneApp = (await import('../src/mytunes/AddTuneApp.svelte')).default
})

// Open the pane on the pasted link and wait for the pager to land on that setting.
async function openOnPastedSetting(onAdded, onAlready) {
  const { component } = render(AddTuneApp, {})
  component.open({ instruments: [], query: PASTED, onAdded, onAlready })
  await waitFor(() => expect(document.querySelector('.mt-submit')).toBeTruthy())
  await waitFor(() =>
    expect(document.querySelector('.pv-setlabel').textContent).toContain('#29513')
  )
}

describe('AddTuneApp: a pasted link with a setting', () => {
  it('sends the deep-linked setting with the add', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 201,
      json: async () => ({ success: true, person_tune: { tune_id: 8006 } }),
    }))
    globalThis.fetch = fetchMock
    const onAdded = vi.fn()
    await openOnPastedSetting(onAdded, vi.fn())

    // The pager landed on the URL's setting — 3rd of the 4 the backfill brought in.
    expect(document.querySelector('.pv-setlabel').textContent).toContain('Setting 3 of 4')
    await fireEvent.click(document.querySelector('.mt-submit'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/my-tunes')
    expect(JSON.parse(opts.body).setting_id).toBe(29513)
  })

  it('reports what the server applied when the tune was already on the list', async () => {
    // A pasted link resolves to a synthetic result with no on_list flag, so the pane
    // offers the full add form for a tune you may already have. The 409 answer is not
    // a dead end: the server applies the chosen setting to the existing row and says so.
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({
        success: false,
        error: 'PersonTune already exists for person 2 and tune 8006',
        applied: { setting_id: 29513 },
        person_tune: { tune_id: 8006 },
      }),
    }))
    const onAdded = vi.fn()
    const onAlready = vi.fn()
    await openOnPastedSetting(onAdded, onAlready)
    await fireEvent.click(document.querySelector('.mt-submit'))

    await waitFor(() => expect(onAlready).toHaveBeenCalled())
    expect(onAdded).not.toHaveBeenCalled()
    expect(onAlready).toHaveBeenCalledWith(8006, 'Scatter The Dew', { setting_id: 29513 })
    // The form must not be left showing an error — this outcome is a success.
    expect(document.querySelector('.mt-error')).toBeNull()
  })

  it('hands on an empty applied map when the server carried nothing over', async () => {
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({ success: false, error: 'already exists' }),
    }))
    const onAlready = vi.fn()
    await openOnPastedSetting(vi.fn(), onAlready)
    await fireEvent.click(document.querySelector('.mt-submit'))
    await waitFor(() => expect(onAlready).toHaveBeenCalled())
    expect(onAlready.mock.calls[0][2]).toEqual({})
  })
})
