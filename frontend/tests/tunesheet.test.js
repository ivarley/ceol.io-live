// Characterization tests for the Svelte tune-detail sheet (spec 035 Step 3) — the
// port of the legacy vanilla tune-detail modal. These pin the legacy DOM
// contract (#tune-detail-modal / #tune-detail-content / the section classes the
// shared stylesheet + e2e suite select on) and the auto-save / offline behaviors.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushSync } from 'svelte'
import { render, waitFor } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import TuneSheet from '../src/tunesheet/TuneSheet.svelte'
import {
  getTuneIdFromUrl,
  extractSettingId,
  validateSettingInput,
  notationDisplay,
  overlayOfflineOps,
} from '../src/tunesheet/logic.js'

const myTunesPayload = (over = {}) => ({
  success: true,
  person_tune: {
    person_tune_id: 11,
    tune_id: 101,
    tune_name: "Cooley's",
    name_alias: null,
    tune_type: 'reel',
    learn_status: 'want to learn',
    heard_count: 2,
    notes: 'first two bars',
    setting_id: null,
    tunebook_count: 9,
    tunebook_count_cached_date: '2026-01-01',
    session_play_count: 3,
    global_play_count: 7,
    person_list_count: 4,
    instruments: [
      { instrument: 'Fiddle', is_auto: true },
      { instrument: 'Flute', is_auto: false },
    ],
    instrument_status: {},
    incipit_abc: 'EBBA!B2 EB',
    abc: 'EBBA!B2 EB!full body',
    ...over,
  },
})

const sessionPayload = (over = {}, status = {}) => ({
  success: true,
  session_tune: {
    tune_id: 202,
    tune_name: 'Banish Misfortune',
    alias: null,
    tune_type: 'jig',
    setting_id: 5,
    key: 'Dmixolydian',
    times_played: 4,
    global_play_count: 12,
    tunebook_count: 44,
    person_tune_status: {
      on_list: true,
      person_tune_id: 55,
      learn_status: 'learning',
      heard_count: 0,
      instruments: [],
      instrument_status: {},
      ...status,
    },
    ...over,
  },
})

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

const opsPosted = () =>
  fetchMock.mock.calls
    .filter(([url]) => String(url).includes('/api/my-tunes/ops'))
    .map(([, opts]) => JSON.parse(opts.body))

beforeEach(() => {
  delete window.MyTunesOffline
  delete window.CeolOffline
  delete window.activeSession
  window.history.replaceState({}, '', '/my-tunes')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('getTuneIdFromUrl', () => {
  it('reads path-based session tune ids', () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/tunes/123')
    expect(getTuneIdFromUrl()).toBe(123)
  })
  it('reads path-based admin tune ids', () => {
    window.history.replaceState({}, '', '/admin/tunes/77')
    expect(getTuneIdFromUrl()).toBe(77)
  })
  it('reads ptid on my-tunes pages', () => {
    window.history.replaceState({}, '', '/my-tunes?ptid=42')
    expect(getTuneIdFromUrl()).toBe(42)
  })
  it('reads tune param elsewhere', () => {
    window.history.replaceState({}, '', '/?tune=9')
    expect(getTuneIdFromUrl()).toBe(9)
  })
  it('returns null when absent', () => {
    window.history.replaceState({}, '', '/my-tunes')
    expect(getTuneIdFromUrl()).toBeNull()
  })
})

describe('setting input parsing', () => {
  it('extracts ids from numbers, query params, and anchors', () => {
    expect(extractSettingId('123')).toBe(123)
    expect(extractSettingId('https://thesession.org/tunes/1?setting=456')).toBe(456)
    expect(extractSettingId('https://thesession.org/tunes/1#setting789')).toBe(789)
    expect(extractSettingId('  ')).toBeNull()
  })
  it('silently discards a URL for the wrong tune', () => {
    expect(validateSettingInput('https://thesession.org/tunes/999#setting5', 101)).toEqual({
      valid: true,
      settingId: null,
    })
  })
  it('rejects garbage with an error', () => {
    expect(validateSettingInput('not a url', 101).valid).toBe(false)
  })
})

describe('notation display resolution', () => {
  const t = { incipit_abc: 'inc!ipit', abc: 'fu!ll', incipit_image: 'III', image: 'FFF' }
  it('resolves the requested mode/size', () => {
    expect(notationDisplay(t, 'dots', 'incipit')).toMatchObject({ kind: 'img', size: 'incipit', src: 'III' })
    expect(notationDisplay(t, 'abc', 'full')).toMatchObject({ kind: 'pre', size: 'full', text: 'fu\nll' })
  })
  it('falls back like the legacy chain (incipit first, then full)', () => {
    expect(notationDisplay({ image: 'FFF' }, 'dots', 'incipit')).toMatchObject({ size: 'full', src: 'FFF' })
    expect(notationDisplay({ incipit_abc: 'a' }, 'abc', 'full')).toMatchObject({ size: 'incipit' })
    expect(notationDisplay({}, 'dots', 'incipit')).toBeNull()
  })
})

describe('offline op overlay', () => {
  it('applies queued ops in ts order and aliases name -> tune_name', () => {
    const t = overlayOfflineOps(
      { name: 'The Butterfly', tune_id: 9 },
      [
        { tune_id: 9, ts: 2, type: 'set_status', learn_status: 'learning' },
        { tune_id: 9, ts: 1, type: 'add' },
        { tune_id: 9, ts: 3, type: 'set_heard', heard_count: 5 },
        { tune_id: 8, ts: 4, type: 'set_status', learn_status: 'learned' },
      ],
      9
    )
    expect(t.tune_name).toBe('The Butterfly')
    expect(t.learn_status).toBe('learning')
    expect(t.heard_count).toBe(5)
  })
})

describe('TuneSheet component', () => {
  it('always renders the legacy modal container (hidden) from mount', () => {
    stubFetch([])
    const { container } = render(TuneSheet)
    const overlay = container.querySelector('#tune-detail-modal.modal-overlay')
    expect(overlay).toBeTruthy()
    expect(overlay.style.display).toBe('none')
    expect(overlay.querySelector('.modal-dialog #tune-detail-content')).toBeTruthy()
  })

  it('show() in my_tunes context renders the full section set and sets ?ptid', async () => {
    stubFetch([['/api/my-tunes/11', myTunesPayload()]])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, tuneName: "Cooley's", tuneType: 'reel', isUserLoggedIn: true },
    })
    flushSync()
    const overlay = container.querySelector('#tune-detail-modal')
    expect(overlay.style.display).toBe('flex')
    expect(new URL(window.location).searchParams.get('ptid')).toBe('11')

    await waitFor(() => expect(container.querySelector('.tunebook-status-section')).toBeTruthy())
    expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe("Cooley's")
    expect(container.querySelector('.tune-type-pill').textContent).toBe('reel')
    // status control tinted by the roll-up, seg buttons present
    expect(container.querySelector('.tunebook-status-section.tunebook-status-want-to-learn')).toBeTruthy()
    expect(container.querySelectorAll('.tsc-main-block .tunebook-status-opt').length).toBe(3)
    // 2 instruments -> expand toggle offered
    expect(container.querySelector('.tsc-expand-link').textContent.trim()).toBe('View By Instrument')
    // heard count section (status is want-to-learn and a person_tune_id exists)
    expect(container.querySelector('#heard-count-value').textContent).toBe('2')
    // notation + notes + save/cancel + links + tabs
    expect(container.querySelector('.abc-notation-section')).toBeTruthy()
    expect(container.querySelector('#notes-textarea').value).toBe('first two bars')
    expect(container.querySelector('#save-btn')).toBeTruthy()
    expect(container.querySelector('#save-btn').disabled).toBe(true)
    expect(container.querySelector('.modal-additional-links').textContent).toContain('Remove From My Tunes')
    expect(container.querySelector('#stats-tab.active')).toBeTruthy()
    expect(container.querySelector('#tunebook-count').textContent).toBe('9')
    // configure section exists but is collapsed
    expect(container.querySelector('#configure-section').style.display).toBe('none')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
  })

  it('status tap posts a set_status op and re-tints the section', async () => {
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/my-tunes/11', myTunesPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.tunebook-status-seg')).toBeTruthy())

    await fireEvent.click(container.querySelector('.tsc-main-block .tunebook-status-opt[data-status="learning"]'))
    // optimistic re-tint + active state
    expect(container.querySelector('.tunebook-status-section.tunebook-status-learning')).toBeTruthy()
    expect(container.querySelector('.tsc-main-block .tunebook-status-opt.active').dataset.status).toBe('learning')
    await waitFor(() => expect(opsPosted()).toContainEqual({ type: 'set_status', tune_id: 101, learn_status: 'learning' }))
  })

  it('setting overall status to learned hides the heard-count section', async () => {
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/my-tunes/11', myTunesPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.heard-count-section')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tsc-main-block .tunebook-status-opt[data-status="learned"]'))
    expect(container.querySelector('.heard-count-section')).toBeFalsy()
  })

  it('heard + posts an ABSOLUTE set_heard and updates the label; minus disabled at 0', async () => {
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/my-tunes/11', myTunesPayload({ heard_count: 0 })],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.heard-count-section')).toBeTruthy())
    expect(container.querySelector('.heard-count-btn-minus').disabled).toBe(true)
    expect(container.querySelector('.heard-count-label').textContent).toContain('0 times')

    await fireEvent.click(container.querySelector('.heard-count-btn-plus'))
    expect(container.querySelector('#heard-count-value').textContent).toBe('1')
    expect(container.querySelector('.heard-count-label').textContent).toContain('1 time')
    expect(container.querySelector('.heard-count-btn-minus').disabled).toBe(false)
    await waitFor(() => expect(opsPosted()).toContainEqual({ type: 'set_heard', tune_id: 101, heard_count: 1 }))
  })

  it('per-instrument expand reveals blocks; instrument tap posts set_instrument_status', async () => {
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/my-tunes/11', myTunesPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.tsc-expand-link')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tsc-expand-link'))
    const blocks = container.querySelectorAll('.tsc-instruments .tsc-inst-block')
    expect(blocks.length).toBe(2)
    // Fiddle (auto) shows the 3-way seg following the base status; Flute (manual,
    // untracked) shows the red not-on-list bar.
    expect(blocks[0].querySelector('.tunebook-status-opt.active').dataset.status).toBe('want to learn')
    expect(blocks[1].querySelector('.tsc-notlist-add')).toBeTruthy()

    await fireEvent.click(blocks[0].querySelector('.tunebook-status-opt[data-status="learned"]'))
    await waitFor(() =>
      expect(opsPosted()).toContainEqual({
        type: 'set_instrument_status',
        tune_id: 101,
        instrument: 'Fiddle',
        status: 'learned',
      })
    )
  })

  it('not-on-list session view shows the red bar; Add posts an add op and refetches', async () => {
    // On a non-my-tunes page (the generic Find-a-tune flow): an add refreshes
    // the global view in place — my-tunes-page adds instead upgrade the variant
    // (covered in the chaining describe below).
    window.history.replaceState({}, '', '/')
    let onList = false
    stubFetch([
      ['/api/my-tunes/ops', () => ({ success: true })],
      [
        '/api/tunes/202/detail',
        () => (onList ? sessionPayload() : sessionPayload({}, { on_list: false, person_tune_id: null })),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'session_instance',
      tuneId: 202,
      apiEndpoint: '/api/tunes/202/detail',
      additionalData: { isUserLoggedIn: true, global: true },
    })
    await waitFor(() => expect(container.querySelector('.tunebook-status-not-on-list')).toBeTruthy())
    expect(container.querySelector('.tsc-notlist-label').textContent).toContain('not on your list')
    // read-only global view: no Save/Cancel, no configure link
    expect(container.querySelector('#save-btn')).toBeFalsy()
    expect(container.querySelector('.modal-additional-links')).toBeFalsy()

    onList = true
    await fireEvent.click(container.querySelector('.tsc-notlist-add'))
    await waitFor(() =>
      expect(opsPosted()).toContainEqual(
        expect.objectContaining({ type: 'add', tune_id: 202, learn_status: 'want to learn' })
      )
    )
    // online add refetches and re-renders the on-list control
    await waitFor(() => expect(container.querySelector('.tunebook-status-section.tunebook-status-learning')).toBeTruthy())
  })

  it('notation mode tabs switch dots/abc and clicking the display toggles incipit/full', async () => {
    stubFetch([
      [
        '/api/my-tunes/11',
        myTunesPayload({ incipit_image: 'AAA', image: 'BBB', incipit_abc: 'inc!1', abc: 'full!2' }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.abc-notation-display')).toBeTruthy())
    const display = container.querySelector('.abc-notation-display')
    // starts in dots/incipit
    expect(display.dataset.currentMode).toBe('dots')
    expect(display.querySelector('img.abc-notation-incipit')).toBeTruthy()
    // click toggles to full (both sizes available)
    await fireEvent.click(display)
    expect(display.dataset.currentSize).toBe('full')
    expect(display.querySelector('img.abc-notation-full')).toBeTruthy()
    // switch to abc keeps the size
    await fireEvent.click(container.querySelector('.notation-mode-tab[data-mode="abc"]'))
    expect(display.querySelector('pre.abc-notation-full').textContent).toBe('full\n2')
    expect(container.querySelector('.notation-mode-tab[data-mode="abc"]').classList.contains('active')).toBe(true)
  })

  it('admin context: configure always visible, name field, no status/heard sections', async () => {
    window.history.replaceState({}, '', '/admin/tunes')
    stubFetch([
      ['/api/admin/tunes/303', { success: true, tune: { tune_id: 303, name: 'The Sligo Maid', tune_type: 'reel', global_play_count: 2, session_count: 1, tunebook_count: 5 } }],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'admin',
      tuneId: 303,
      apiEndpoint: '/api/admin/tunes/303',
      additionalData: { isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('#configure-section')).toBeTruthy())
    expect(window.location.pathname).toBe('/admin/tunes/303')
    expect(container.querySelector('#configure-section').style.display).toBe('block')
    expect(container.querySelector('#tune-name-input').value).toBe('The Sligo Maid')
    expect(container.querySelector('.tunebook-status-section')).toBeFalsy()
    expect(container.querySelector('.heard-count-section')).toBeFalsy()
    // dirty-check enables save
    expect(container.querySelector('#save-btn').disabled).toBe(true)
    await fireEvent.input(container.querySelector('#tune-name-input'), { target: { value: 'Renamed' } })
    expect(container.querySelector('#save-btn').disabled).toBe(false)
  })

  it('session context save PUTs only changed fields and calls onSave', async () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/tunes')
    const onSave = vi.fn()
    stubFetch([
      [
        '/api/sessions/austin/mueller/tunes/202',
        (url, opts) => (opts.method === 'PUT' ? { success: true } : sessionPayload()),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'session',
      tuneId: 202,
      apiEndpoint: '/api/sessions/austin/mueller/tunes/202',
      onSave,
      additionalData: { sessionPath: 'austin/mueller', isUserLoggedIn: true, isSessionAdmin: true },
    })
    await waitFor(() => expect(container.querySelector('#alias-input')).toBeTruthy())
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes/202')
    expect(container.querySelector('.modal-additional-links').textContent).toContain('Remove From Session')

    await fireEvent.input(container.querySelector('#alias-input'), { target: { value: 'The Banish' } })
    expect(container.querySelector('#save-btn').disabled).toBe(false)
    await fireEvent.click(container.querySelector('#save-btn'))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    const put = fetchMock.mock.calls.find(([, opts]) => opts && opts.method === 'PUT')
    expect(JSON.parse(put[1].body)).toEqual({ alias: 'The Banish' })
    expect(container.querySelector('#save-btn').textContent.trim()).toBe('Saved!')
    // URL param cleaned before onSave
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes')
  })

  it('offline fallback renders from CeolOffline with pending ops overlaid', async () => {
    // A network failure (offline) REJECTS — a 404 would instead hit the
    // dead-ptid friendly-error branch, exactly as in the legacy modal.
    fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)
    window.CeolOffline = {
      getTune: vi.fn().mockResolvedValue({
        tune_id: 909,
        name: 'The Butterfly',
        tune_type: 'slip jig',
        incipit_abc: 'B2E!E2B',
      }),
    }
    window.MyTunesOffline = {
      pending: vi.fn().mockResolvedValue([
        { tune_id: 909, ts: 1, type: 'add', learn_status: 'want to learn' },
        { tune_id: 909, ts: 2, type: 'set_status', learn_status: 'learning' },
      ]),
      submit: vi.fn().mockResolvedValue({ online: false, queued: true }),
    }
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 909,
      apiEndpoint: '/api/my-tunes/pending-909',
      additionalData: { personTuneId: 'pending-909', isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe('The Butterfly'))
    expect(container.textContent).not.toContain('Failed to load')
    // queued set_status op overlaid -> learning active
    expect(container.querySelector('.tunebook-status-opt.active').dataset.status).toBe('learning')
    // incipit notation renders from the cached bundle
    expect(container.querySelector('.abc-notation-text').textContent).toBe('B2E\nE2B')
  })

  it('dead my_tunes deep link (404) shows the friendly merge notice and cleans the URL', async () => {
    window.history.replaceState({}, '', '/my-tunes?ptid=999')
    stubFetch([]) // 404 everything
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: null,
      apiEndpoint: '/api/my-tunes/999',
      additionalData: { personTuneId: 999, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.modal-error')).toBeTruthy())
    expect(container.querySelector('.modal-error').textContent).toContain('no longer exists')
    expect(new URL(window.location).searchParams.get('ptid')).toBeNull()
  })

  it('redirected_from heals the config and shows the merged notice', async () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/tunes')
    stubFetch([
      ['/api/sessions/austin/mueller/tunes/100', { ...sessionPayload({ tune_id: 200 }), redirected_from: 100 }],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'session',
      tuneId: 100,
      apiEndpoint: '/api/sessions/austin/mueller/tunes/100',
      additionalData: { sessionPath: 'austin/mueller', isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.tune-merged-notice')).toBeTruthy())
    expect(container.querySelector('.tune-merged-notice').textContent).toContain('Tune #100 was merged into')
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes/200')
  })

  it('close removes the URL param and hides after the 300ms fade', async () => {
    // Only fake the timeout clock: Svelte's DOM flush rides the microtask queue.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    stubFetch([['/api/my-tunes/11', myTunesPayload()]])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    flushSync()
    const overlay = container.querySelector('#tune-detail-modal')
    expect(overlay.style.display).toBe('flex')
    vi.advanceTimersByTime(20)
    flushSync()
    expect(overlay.className).toContain('show')

    component.close()
    flushSync()
    expect(new URL(window.location).searchParams.get('ptid')).toBeNull()
    expect(overlay.className).not.toContain('show')
    expect(overlay.style.display).toBe('flex') // still visible during the fade
    vi.advanceTimersByTime(300)
    flushSync()
    expect(overlay.style.display).toBe('none')
    vi.useRealTimers()
  })
})

describe('TuneSheet — in-drawer chaining, host notification, roll-up reset, generate notation', () => {
  const playedWith = (ids) => ({
    success: true,
    tunes: ids.map((id) => ({ tune_id: id, name: `Tune #${id}`, count: 2 })),
  })

  it('Played With chaining from my_tunes reopens the SAME variant (notes/config/ptid) and inherits callbacks', async () => {
    const onStatusChange = vi.fn()
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/my-tunes/11', myTunesPayload()],
      ['/api/my-tunes/55', myTunesPayload({ person_tune_id: 55, tune_id: 202, tune_name: 'Banish Misfortune', notes: 'chained notes' })],
      ['/api/tunes/101/played-with', playedWith([202])],
      ['/api/tunes/202/detail', sessionPayload()], // person_tune_status.person_tune_id: 55 (on list)
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      onStatusChange,
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.modal-tab[data-tab="played-with"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="played-with"]'))
    await waitFor(() => expect(container.querySelector('.played-with-item[data-tune-id="202"]')).toBeTruthy())

    await fireEvent.click(container.querySelector('.played-with-item[data-tune-id="202"]'))
    // resolves the ptid via the global detail endpoint, then opens the full my_tunes variant
    await waitFor(() => expect(container.querySelector('#notes-textarea')).toBeTruthy())
    expect(container.querySelector('#notes-textarea').value).toBe('chained notes')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
    expect(container.querySelector('.modal-additional-links').textContent).toContain('Remove From My Tunes')
    expect(new URL(window.location).searchParams.get('ptid')).toBe('55')

    // the host callback was inherited: a status change on the CHAINED tune notifies it
    await fireEvent.click(container.querySelector('.tsc-main-block .tunebook-status-opt[data-status="learned"]'))
    await waitFor(() =>
      expect(onStatusChange).toHaveBeenCalledWith(
        expect.objectContaining({ tune_id: 202, learn_status: 'learned', on_list: true, person_tune_id: 55 })
      )
    )
  })

  it('chained not-on-list tune degrades to the Add view; adding notifies the host with the new identity', async () => {
    const onStatusChange = vi.fn()
    let onList = false
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/my-tunes/77', myTunesPayload({ person_tune_id: 77, tune_id: 303, tune_name: 'The Chained', notes: 'now mine' })],
      ['/api/my-tunes/11', myTunesPayload()],
      ['/api/tunes/101/played-with', playedWith([303])],
      ['/api/tunes/303/played-with', playedWith([])],
      ['/api/tunes/303/history', { success: true, play_instances: [] }],
      [
        '/api/tunes/303/detail',
        () =>
          onList
            ? sessionPayload({ tune_id: 303 }, { person_tune_id: 77, learn_status: 'want to learn' })
            : sessionPayload({ tune_id: 303 }, { on_list: false, person_tune_id: null, learn_status: null }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      onStatusChange,
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.modal-tab[data-tab="played-with"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="played-with"]'))
    await waitFor(() => expect(container.querySelector('.played-with-item[data-tune-id="303"]')).toBeTruthy())

    await fireEvent.click(container.querySelector('.played-with-item[data-tune-id="303"]'))
    await waitFor(() => expect(container.querySelector('.tsc-notlist-add')).toBeTruthy())

    // put the user on a non-default tab: the in-place upgrade must keep it
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="played-with"]'))

    onList = true
    await fireEvent.click(container.querySelector('.tsc-notlist-add'))
    // the refetched payload carries the new person_tune identity -> host notified
    await waitFor(() =>
      expect(onStatusChange).toHaveBeenCalledWith(
        expect.objectContaining({ tune_id: 303, on_list: true, person_tune_id: 77, learn_status: 'want to learn' })
      )
    )

    // ...and the drawer upgrades IN PLACE (no close) to the full my_tunes
    // variant the tune would have opened as had it been on the list.
    await waitFor(() => expect(container.querySelector('#notes-textarea')).toBeTruthy())
    expect(container.querySelector('#tune-detail-modal').style.display).toBe('flex')
    expect(container.querySelector('#notes-textarea').value).toBe('now mine')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
    expect(container.querySelector('.modal-additional-links').textContent).toContain('Remove From My Tunes')
    expect(new URL(window.location).searchParams.get('ptid')).toBe('77')
    // the tab the user was on survives the upgrade
    expect(container.querySelector('#played-with-tab.active')).toBeTruthy()
    // the my_tunes history scope toggle (My sessions / All sessions) is offered
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="history"]'))
    await waitFor(() =>
      expect([...container.querySelectorAll('#history-tab .history-scope-btn')].map((b) => b.textContent.trim())).toEqual([
        'My sessions',
        'All sessions',
      ])
    )
    // the host was notified exactly once — the upgrade reload doesn't re-notify
    expect(onStatusChange).toHaveBeenCalledTimes(1)
  })

  it('session-scoped chaining still carries the session AND now the callbacks', async () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/tunes')
    const onSave = vi.fn()
    stubFetch([
      ['/api/tunes/202/played-with', playedWith([404])],
      ['/api/sessions/austin/mueller/tunes/404', sessionPayload({ tune_id: 404, tune_name: 'The Chained' })],
      ['/api/sessions/austin/mueller/tunes/202', sessionPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'session',
      tuneId: 202,
      apiEndpoint: '/api/sessions/austin/mueller/tunes/202',
      onSave,
      additionalData: { sessionPath: 'austin/mueller', isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.modal-tab[data-tab="played-with"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="played-with"]'))
    await waitFor(() => expect(container.querySelector('.played-with-item[data-tune-id="404"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.played-with-item[data-tune-id="404"]'))
    await waitFor(() =>
      expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe('The Chained')
    )
    // still the session variant: the session-scoped history toggle is offered
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes/404')
    expect(container.querySelector('#alias-input')).toBeTruthy()
  })

  it('the per-instrument roll-up resets to collapsed when the drawer shows another tune', async () => {
    stubFetch([
      ['/api/my-tunes/11', myTunesPayload()],
      ['/api/my-tunes/12', myTunesPayload({ person_tune_id: 12, tune_id: 102, tune_name: 'The Second' })],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.tsc-expand-link')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tsc-expand-link'))
    expect(container.querySelector('.tsc-instruments')).toBeTruthy()

    component.show({
      context: 'my_tunes',
      tuneId: 102,
      apiEndpoint: '/api/my-tunes/12',
      additionalData: { personTuneId: 12, isUserLoggedIn: true },
    })
    await waitFor(() =>
      expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe('The Second')
    )
    expect(container.querySelector('.tsc-instruments')).toBeFalsy()
    expect(container.querySelector('.tsc-expand-link').textContent.trim()).toBe('View By Instrument')
  })

  it('expandInstrumentStatus still opens the roll-up pre-expanded', async () => {
    stubFetch([['/api/my-tunes/11', myTunesPayload()]])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      expandInstrumentStatus: true,
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.tsc-instruments')).toBeTruthy())
  })

  it('no cached notation -> Generate Notation runs the settings-cache action and renders in place', async () => {
    stubFetch([
      [
        '/api/tunes/101/settings/cache',
        { success: true, setting: { setting_id: 9, abc: 'full!abc', incipit_abc: 'inc!abc', image: null, incipit_image: null } },
      ],
      [
        '/api/my-tunes/11',
        (url, opts) =>
          opts.method === 'PUT'
            ? { success: true }
            : myTunesPayload({ abc: null, incipit_abc: null }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.generate-notation-link')).toBeTruthy())
    expect(container.querySelector('.abc-notation-display')).toBeFalsy()

    await fireEvent.click(container.querySelector('.generate-notation-link'))
    await waitFor(() => expect(container.querySelector('.abc-notation-text')).toBeTruthy())
    expect(container.querySelector('.abc-notation-text').textContent).toBe('inc\nabc')
    // The empty-state section is gone; the fetch yielded abc but no rendered
    // image, so the toggle spot (correctly) still offers Generate Notation.
    expect(container.querySelector('.abc-notation-empty')).toBeFalsy()
    expect(container.querySelector('.notation-mode-tabs .generate-notation-link')).toBeTruthy()
    const cacheCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/settings/cache'))
    expect(cacheCall[1].method).toBe('POST')
  })

  it('abc cached but no rendered image -> Generate Notation replaces the notes/abc toggle and switches to dots', async () => {
    stubFetch([
      [
        '/api/tunes/101/settings/cache',
        {
          success: true,
          setting: { setting_id: 9, abc: 'full!abc', incipit_abc: 'inc!abc', image: null, incipit_image: 'IMGDATA' },
        },
      ],
      [
        '/api/my-tunes/11',
        (url, opts) =>
          opts.method === 'PUT'
            ? { success: true }
            : myTunesPayload({ abc: 'full!abc', incipit_abc: 'inc!abc', image: null, incipit_image: null }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    // abc text renders, but with no dots view there's no notes/abc toggle —
    // the Generate Notation affordance sits in its place.
    await waitFor(() => expect(container.querySelector('.abc-notation-text')).toBeTruthy())
    expect(container.querySelector('.notation-mode-tab')).toBeFalsy()
    const link = container.querySelector('.notation-mode-tabs .generate-notation-link')
    expect(link).toBeTruthy()

    await fireEvent.click(link)
    // The fetch produced an image: the drawer switches to dots and the real
    // toggle takes the affordance's place.
    await waitFor(() => expect(container.querySelector('.abc-notation-image')).toBeTruthy())
    expect(container.querySelectorAll('.notation-mode-tab').length).toBe(2)
    expect(container.querySelector('.generate-notation-link')).toBeFalsy()
  })

  it('Generate Notation failure surfaces through the toast pattern', async () => {
    window.showMessage = vi.fn()
    stubFetch([
      ['/api/tunes/101/settings/cache', { success: false, message: 'nope' }],
      ['/api/my-tunes/11', myTunesPayload({ abc: null, incipit_abc: null })],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'my_tunes',
      tuneId: 101,
      apiEndpoint: '/api/my-tunes/11',
      additionalData: { personTuneId: 11, isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('.generate-notation-link')).toBeTruthy())
    await fireEvent.click(container.querySelector('.generate-notation-link'))
    await waitFor(() =>
      expect(window.showMessage).toHaveBeenCalledWith('Could not fetch notation for this tune', 'error')
    )
    // the affordance stays for a retry
    expect(container.querySelector('.generate-notation-link')).toBeTruthy()
    delete window.showMessage
  })
})
