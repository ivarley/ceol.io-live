// Spec 057: the language setting on /me.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import LanguageSetting from '../src/personpage/LanguageSetting.svelte'

afterEach(() => {
  vi.unstubAllGlobals()
  delete window.__CEOL_LANG__
  document.body.innerHTML = ''
})

describe('LanguageSetting', () => {
  it('names each language in itself, whatever the page language', () => {
    window.__CEOL_LANG__ = 'ga'
    render(LanguageSetting, { language: 'ga' })
    const labels = [...document.querySelectorAll('[data-language]')].map((b) => b.textContent.trim())
    expect(labels).toEqual(['English', 'Gaeilge'])
    expect(document.querySelector('.kit-group-head').textContent).toBe('Teanga')
  })

  it('saves the choice and reloads', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: async () => ({ success: true }) })))
    const reload = vi.fn()
    render(LanguageSetting, { language: 'en', reload })
    await fireEvent.click(document.querySelector('[data-language="ga"]'))
    await waitFor(() => expect(reload).toHaveBeenCalled())
    const [url, opts] = fetch.mock.calls[0]
    expect(url).toBe('/api/me/profile')
    expect(JSON.parse(opts.body)).toEqual({ language: 'ga' })
  })

  it('choosing the current language does nothing', async () => {
    vi.stubGlobal('fetch', vi.fn())
    render(LanguageSetting, { language: 'en' })
    await fireEvent.click(document.querySelector('[data-language="en"]'))
    expect(fetch).not.toHaveBeenCalled()
  })
})
