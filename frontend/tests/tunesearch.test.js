// The shared deep search (TuneSearch.svelte) behind all three add surfaces: the live
// logger's pane/modal, the My Tunes add pane, and the session-tunes add pane. These
// cover the paste-a-thesession.org-link path — pasting a URL anywhere you can type a
// tune name resolves to THAT tune, and a ?setting=/#setting deep link rides along as
// the chosen setting (which each surface then applies at its own scope).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor, fireEvent } from '@testing-library/svelte'

const deepSearch = vi.fn(async () => [])
const thesessionPreview = vi.fn(async () => ({ is_local: false, name: 'Cooley’s', tune_type: 'Reel', settings: [] }))
const tunePreview = vi.fn(async () => ({ tune_id: 1, name: 'Cooley’s', settings: [], aliases: [] }))

vi.mock('../src/client.js', () => ({
  deepSearch: (...a) => deepSearch(...a),
  thesessionSearch: vi.fn(async () => []),
  thesessionPreview: (...a) => thesessionPreview(...a),
  tunePreview: (...a) => tunePreview(...a),
  settingImage: vi.fn(() => Promise.resolve({ image: null })),
  renderRemoteAbc: vi.fn(() => Promise.resolve({ image: null })),
  fetchIncipit: vi.fn(async () => null),
}))

const URL_WITH_SETTING = 'https://thesession.org/tunes/8645?setting=44656#setting44656'
const config = { searchApiBase: '/api/my-tunes' }

let TuneSearch
beforeEach(async () => {
  vi.clearAllMocks()
  TuneSearch = (await import('../src/TuneSearch.svelte')).default
})

// The preview is the "resolved" state: its header/skeleton replaces the search body.
const previewShowing = () => !!document.querySelector('.pv-wrap, .pv-head, [class^="pv-"]')

async function typeInto(input, value, inputType) {
  input.value = value
  await fireEvent.input(input, inputType ? { inputType } : {})
}

describe('TuneSearch paste-a-link', () => {
  it('jumps to the pasted tune preview and re-seeds the search with its real name', async () => {
    render(TuneSearch, { props: { config, onAdd: vi.fn() } })
    const input = document.querySelector('.deep-field')
    await typeInto(input, URL_WITH_SETTING, 'insertFromPaste')
    await waitFor(() => expect(previewShowing()).toBe(true))
    // The preview loads the tune the link named...
    expect(thesessionPreview).toHaveBeenCalledWith(config, 8645)
    // ...and the search underneath re-seeds with its real name (never the URL string),
    // so backing out of the preview lands on relevant results.
    await waitFor(() => expect(deepSearch).toHaveBeenCalledWith(config, 'Cooley’s', null, null, 'mixed'))
    expect(deepSearch).not.toHaveBeenCalledWith(config, URL_WITH_SETTING, null, null, 'mixed')
  })

  it('does not jump while a URL is being typed, but offers the row and honors Enter', async () => {
    render(TuneSearch, { props: { config, onAdd: vi.fn() } })
    const input = document.querySelector('.deep-field')
    // Character-by-character entry: parses as soon as ".../tunes/8" does — must NOT jump.
    for (const v of ['https://thesession.org/tunes/8', 'https://thesession.org/tunes/86']) {
      await typeInto(input, v, 'insertText')
    }
    expect(previewShowing()).toBe(false)
    const row = document.querySelector('.deep-asis-remote')
    expect(row.textContent).toContain('#86')
    await fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(previewShowing()).toBe(true))
    expect(thesessionPreview).toHaveBeenCalledWith(config, 86)
  })

  it('never runs a name search for a link, and says so in the empty state', async () => {
    render(TuneSearch, { props: { config, onAdd: vi.fn() } })
    const input = document.querySelector('.deep-field')
    await typeInto(input, 'https://thesession.org/tunes/8645', 'insertText')
    await new Promise((r) => setTimeout(r, 250)) // past the search debounce
    expect(deepSearch).not.toHaveBeenCalled()
    expect(document.querySelector('.deep-empty').textContent).toContain('thesession.org tune link')
    // A URL is not a tune name — the as-is escape must not offer to log it as one.
    expect(document.querySelector('.deep-asis:not(.deep-asis-remote)')).toBeFalsy()
  })

  it('resolves a link handed in as the initial query (the page-search handoff)', async () => {
    render(TuneSearch, { props: { config, initialQuery: URL_WITH_SETTING, variant: 'modal', onAdd: vi.fn() } })
    await waitFor(() => expect(previewShowing()).toBe(true))
    expect(thesessionPreview).toHaveBeenCalledWith(config, 8645)
  })

  it('runs a normal name search for ordinary text', async () => {
    render(TuneSearch, { props: { config, onAdd: vi.fn() } })
    const input = document.querySelector('.deep-field')
    await typeInto(input, 'cooley', 'insertText')
    await waitFor(() => expect(deepSearch).toHaveBeenCalledWith(config, 'cooley', null, null, 'mixed'))
    expect(previewShowing()).toBe(false)
  })
})
