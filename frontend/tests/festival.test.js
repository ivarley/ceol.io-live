// Spec 056: the year switcher, the festival picker, and "Copy to a new year".
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import YearSwitcher from '../src/festival/YearSwitcher.svelte'
import CopyYearSheet from '../src/festival/CopyYearSheet.svelte'
import FestivalApp from '../src/festivalpage/App.svelte'
import { formatRange } from '../src/festivalpage/logic.js'

const place = { slug: 'oflahertys', name: "O'Flaherty's Irish Music Retreat", kind: 'festival' }
const y2024 = { year: 2024, path: 'oflahertys/2024', initiation_date: '2024-10-24', termination_date: '2024-10-27', logged_instances: 30 }
const y2025 = { year: 2025, path: 'oflahertys/2025', initiation_date: '2025-10-23', termination_date: '2025-10-26', logged_instances: 36 }

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('YearSwitcher', () => {
  it('is a plain year when the festival has one', () => {
    render(YearSwitcher, { festival: { place, years: [y2025] }, currentPath: 'oflahertys/2025' })
    expect(document.querySelector('#festival-year-select')).toBeNull()
    expect(document.body.textContent).toContain('2025')
  })

  it('lists the years newest first and navigates on change', async () => {
    const navigate = vi.fn()
    render(YearSwitcher, {
      festival: { place, years: [y2024, y2025] },
      currentPath: 'oflahertys/2025',
      hrefFor: (p) => `/admin/sessions/${p}`,
      navigate,
    })
    const select = document.querySelector('#festival-year-select')
    expect([...select.options].map((o) => o.textContent)).toEqual(['2025', '2024'])
    expect(select.value).toBe('oflahertys/2025')
    select.value = 'oflahertys/2024'
    await fireEvent.change(select)
    expect(navigate).toHaveBeenCalledWith('/admin/sessions/oflahertys/2024')
  })
})

describe('the festival picker', () => {
  const pageData = (canAdd) => ({
    place,
    years: [y2025, y2024],
    current: null,
    latest: y2025,
    permissions: { can_add_year: canAdd },
  })

  it('first paint renders the embedded years', () => {
    render(FestivalApp, { pageData: pageData(false) })
    const links = [...document.querySelectorAll('.festival-year-link')]
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/sessions/oflahertys/2025', '/sessions/oflahertys/2024'])
    expect(links[0].textContent).toContain('Oct 23 – 26, 2025')
    expect(links[0].textContent).toContain('36 sessions logged')
  })

  it('Add a year is only for admins', () => {
    render(FestivalApp, { pageData: pageData(false) })
    expect(document.querySelector('#festival-add-year')).toBeNull()
    document.body.innerHTML = ''
    render(FestivalApp, { pageData: pageData(true) })
    expect(document.querySelector('#festival-add-year')).toBeTruthy()
  })

  it('formats ranges across months and years', () => {
    expect(formatRange('2025-10-30', '2025-11-02')).toBe('Oct 30 – Nov 2, 2025')
    expect(formatRange('2025-12-30', '2026-01-02')).toBe('Dec 30, 2025 – Jan 2, 2026')
    expect(formatRange('2025-10-23', null)).toBe('Oct 23, 2025')
    expect(formatRange(null, null)).toBe('')
  })
})

describe('CopyYearSheet', () => {
  function open(fetchImpl, navigate = vi.fn()) {
    vi.stubGlobal('fetch', vi.fn(fetchImpl))
    render(CopyYearSheet, { open: true, festival: { place, years: [y2024, y2025] }, source: y2025, navigate })
    return navigate
  }
  const val = (id) => document.querySelector(id).value

  it('defaults to the next year, its nudged dates and name', async () => {
    open(() => {})
    await waitFor(() => expect(document.querySelector('#copyYearYear')).toBeTruthy())
    expect(val('#copyYearYear')).toBe('2026')
    expect(val('#copyYearStart')).toBe('2026-10-22')
    expect(val('#copyYearEnd')).toBe('2026-10-25')
    expect(val('#copyYearName')).toBe("O'Flaherty's Irish Music Retreat 2026")
    expect(document.querySelector('#copyYearPath').textContent).toBe('/sessions/oflahertys/2026')
  })

  it('changing the year moves the dates and the name, back as well as forward', async () => {
    open(() => {})
    await waitFor(() => expect(document.querySelector('#copyYearYear')).toBeTruthy())
    const year = document.querySelector('#copyYearYear')
    year.value = '2023'
    await fireEvent.input(year)
    expect(val('#copyYearStart')).toBe('2023-10-26')
    expect(val('#copyYearName')).toBe("O'Flaherty's Irish Music Retreat 2023")
  })

  it('refuses a year the festival already has, without a round trip', async () => {
    open(() => {})
    await waitFor(() => expect(document.querySelector('#copyYearYear')).toBeTruthy())
    const year = document.querySelector('#copyYearYear')
    year.value = '2024'
    await fireEvent.input(year)
    await fireEvent.submit(document.querySelector('#copyYearForm'))
    expect(document.querySelector('[role="alert"]').textContent).toContain('already has 2024')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('posts and goes to the new year', async () => {
    const navigate = open(() =>
      Promise.resolve({ ok: true, json: async () => ({ success: true, path: 'oflahertys/2026' }) })
    )
    await waitFor(() => expect(document.querySelector('#copyYearYear')).toBeTruthy())
    await fireEvent.submit(document.querySelector('#copyYearForm'))
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/admin/sessions/oflahertys/2026'))
    const [url, opts] = fetch.mock.calls[0]
    expect(url).toBe('/api/sessions/oflahertys/2025/copy-year')
    expect(JSON.parse(opts.body)).toEqual({
      year: 2026,
      initiation_date: '2026-10-22',
      termination_date: '2026-10-25',
      name: "O'Flaherty's Irish Music Retreat 2026",
    })
  })
})
