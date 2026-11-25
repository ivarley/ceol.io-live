// The export chooser (/export): where each choice leads, and that the first paint
// renders the three choices from the embedded payload.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, fireEvent } from '@testing-library/svelte'
import App from '../src/exportpage/App.svelte'
import { MY_TUNES_EXPORT, matchSessions, pickerSections, sessionExportHref } from '../src/exportpage/links.js'

describe('export links', () => {
  it('My Tunes opens the list in export mode', () => {
    expect(MY_TUNES_EXPORT).toBe('/my-tunes?export=1')
  })
  it('a session export opens its tab (a path segment) in export mode', () => {
    expect(sessionExportHref('austin/celtic', 'tunes')).toBe('/sessions/austin/celtic/tunes?export=1')
    expect(sessionExportHref('/austin/celtic/', 'logs')).toBe('/sessions/austin/celtic/logs?export=1')
    expect(sessionExportHref('', 'logs')).toBe(null)
  })
  it('your sessions come first and are not listed again under all', () => {
    const { mine, rest } = pickerSections(
      [{ path: 'a', name: 'A' }],
      [
        { path: 'a', name: 'A' },
        { path: 'b', name: 'B' },
      ]
    )
    expect(mine.map((s) => s.path)).toEqual(['a'])
    expect(rest.map((s) => s.path)).toEqual(['b'])
  })
  it('matches on name or place, case-insensitively', () => {
    const list = [
      { path: 'a', name: 'Austin Celtic', place: 'Austin' },
      { path: 'b', name: 'B. D. Riley', place: 'Austin' },
    ]
    expect(matchSessions(list, 'riley').map((s) => s.path)).toEqual(['b'])
    expect(matchSessions(list, 'AUSTIN').map((s) => s.path)).toEqual(['a', 'b'])
    expect(matchSessions(list, '')).toBe(list)
  })
})

describe('the chooser page', () => {
  afterEach(() => vi.restoreAllMocks())

  const payload = {
    success: true,
    my_sessions: [{ path: 'austin/celtic', name: 'Austin Celtic Session', place: 'Austin' }],
    all_sessions: [
      { path: 'austin/celtic', name: 'Austin Celtic Session', place: 'Austin' },
      { path: 'dublin/cobblestone', name: 'The Cobblestone', place: 'Dublin' },
    ],
  }

  it('first paint renders the three choices from the embedded payload', () => {
    const { container } = render(App, { props: { pageData: payload } })
    expect(container.querySelector('#export-my-tunes').getAttribute('href')).toBe('/my-tunes?export=1')
    expect(container.querySelector('#export-session-tunes')).toBeInTheDocument()
    expect(container.querySelector('#export-session-logs')).toBeInTheDocument()
  })

  it('picking a session for logs goes to that session’s logs tab in export mode', async () => {
    const assign = vi.fn()
    vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, assign })
    const { container, getByText } = render(App, { props: { pageData: payload } })
    await fireEvent.click(container.querySelector('#export-session-logs'))
    await fireEvent.click(getByText('The Cobblestone'))
    expect(assign).toHaveBeenCalledWith('/sessions/dublin/cobblestone/logs?export=1')
  })
})
