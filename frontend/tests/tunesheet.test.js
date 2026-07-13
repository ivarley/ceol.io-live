// Tests for the Svelte tune-detail sheet (spec 035 Step 3, derived-mode
// refactor). These pin the legacy DOM contract (#tune-detail-modal /
// #tune-detail-content / the section classes the shared stylesheet + e2e suite
// select on), the auto-save / offline behaviors, and the NEW invariants: one
// payload endpoint feeds the drawer and the variant is DERIVED from it
// (viewer.logged_in, person_tune_status.on_list, the scope) rather than
// declared by call sites.
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
  scopeFromUrl,
  normalizeShowConfig,
  detailUrl,
  historyScopeOptions,
  playedWithScopeOptions,
} from '../src/tunesheet/logic.js'

// ---- spec 033 scope matrices (pure) ----------------------------------------------

describe('scope option matrices (spec 033)', () => {
  const keys = (opts) => opts.map((o) => o.key)
  const sessScope = { session: 'austin/mueller' }

  it('history: session modes lead with This session; personal lenses need login', () => {
    expect(keys(historyScopeOptions('session', sessScope, true))).toEqual([
      'session', 'member', 'attended', 'all',
    ])
    expect(keys(historyScopeOptions('session_instance', sessScope, false))).toEqual(['session', 'all'])
  })

  it('history: my_tunes defaults to member; global/admin default to all', () => {
    expect(keys(historyScopeOptions('my_tunes', null, true))).toEqual(['member', 'attended', 'all'])
    expect(keys(historyScopeOptions('global', null, true))).toEqual(['all', 'member', 'attended'])
    expect(keys(historyScopeOptions('global', null, false))).toEqual(['all'])
    expect(keys(historyScopeOptions('admin', null, true))).toEqual(['all', 'member', 'attended'])
  })

  it('played-with mirrors the matrix with its own labels', () => {
    expect(keys(playedWithScopeOptions('session', sessScope, true))).toEqual([
      'session', 'member', 'attended', 'all',
    ])
    expect(keys(playedWithScopeOptions('session', sessScope, false))).toEqual(['session', 'all'])
    expect(keys(playedWithScopeOptions('my_tunes', null, true))).toEqual(['member', 'attended', 'all'])
    expect(keys(playedWithScopeOptions('global', null, false))).toEqual(['all'])
    const labels = playedWithScopeOptions('session', sessScope, true).map((o) => o.label)
    expect(labels).toEqual(['At This Session', 'At My Sessions', 'While I Was There', 'Globally'])
  })
})

// ---- payload builders (the ONE drawer feed shape) --------------------------------

const fullPts = (over = {}) => ({
  on_list: true,
  person_tune_id: 11,
  learn_status: 'want to learn',
  heard_count: 2,
  learned_date: null,
  notes: 'first two bars',
  name_alias: null,
  setting_id: null,
  session_play_count: 3,
  instruments: [
    { instrument: 'Fiddle', is_auto: true },
    { instrument: 'Flute', is_auto: false },
  ],
  instrument_status: {},
  ...over,
})

const notOnListPts = {
  on_list: false,
  person_tune_id: null,
  learn_status: null,
  heard_count: null,
  instruments: [],
  instrument_status: {},
}

const detailPayload = ({ tune = {}, pts, viewer = {}, redirected_from = null } = {}) => ({
  success: true,
  redirected_from,
  viewer: { logged_in: true, is_admin: false, is_session_admin: false, ...viewer },
  session_tune: {
    tune_id: 101,
    tune_name: "Cooley's",
    tune_type: 'reel',
    alias: null,
    aliases: [],
    key: null,
    name: null,
    key_override: null,
    setting_override: null,
    setting_id: null,
    setting_key: null,
    abc: 'EBBA!B2 EB!full body',
    incipit_abc: 'EBBA!B2 EB',
    image: null,
    incipit_image: null,
    tunebook_count: 9,
    tunebook_count_cached_date: '2026-01-01',
    times_played: 0,
    global_play_count: 7,
    person_list_count: 4,
    session_count: 2,
    session_scope: null,
    person_tune_status: pts === undefined ? fullPts() : pts,
    ...tune,
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

describe('scope derivation + config normalization (derived-mode refactor)', () => {
  it('derives scope from the page URL', () => {
    expect(scopeFromUrl('/sessions/austin/mueller')).toEqual({ session: 'austin/mueller' })
    expect(scopeFromUrl('/sessions/austin/mueller/tunes')).toEqual({ session: 'austin/mueller' })
    expect(scopeFromUrl('/sessions/austin/mueller/tunes/55')).toEqual({ session: 'austin/mueller' })
    expect(scopeFromUrl('/sessions/austin/mueller/logs')).toEqual({ session: 'austin/mueller' })
    expect(scopeFromUrl('/admin/tunes')).toEqual({ admin: true })
    expect(scopeFromUrl('/admin/tunes/9')).toEqual({ admin: true })
    expect(scopeFromUrl('/my-tunes')).toBeNull()
    expect(scopeFromUrl('/')).toBeNull()
    expect(scopeFromUrl('/live/instances/12')).toBeNull()
  })

  it('new-style configs default their scope from the URL only when not given', () => {
    const c = normalizeShowConfig({ tuneId: 5 }, '/sessions/a/b/tunes')
    expect(c.scope).toEqual({ session: 'a/b' })
    const explicit = normalizeShowConfig({ tuneId: 5, scope: null }, '/sessions/a/b/tunes')
    expect(explicit.scope).toBeNull()
  })

  it('maps the old-style pill-logger config (context + apiEndpoint) onto the new call', () => {
    const c = normalizeShowConfig({
      context: 'session_instance',
      tuneId: 7,
      apiEndpoint: '/api/sessions/a/b/2026-01-01/tunes/7',
      additionalData: { sessionPath: 'a/b', dateOrId: '2026-01-01', tuneName: 'X', isUserLoggedIn: true },
    })
    expect(c).toMatchObject({ tuneId: 7, scope: { session: 'a/b', instance: '2026-01-01' }, tuneName: 'X' })
  })

  it('maps old-style admin, my_tunes, and legacy-global configs', () => {
    expect(normalizeShowConfig({ context: 'admin', tuneId: 3, apiEndpoint: '/api/admin/tunes/3' }).scope).toEqual({
      admin: true,
    })
    const mt = normalizeShowConfig({
      context: 'my_tunes',
      tuneId: 4,
      apiEndpoint: '/api/my-tunes/44',
      additionalData: { personTuneId: 44 },
    })
    expect(mt).toMatchObject({ tuneId: 4, ptid: 44, scope: null })
    const g = normalizeShowConfig({
      context: 'session_instance',
      tuneId: 5,
      apiEndpoint: '/api/tunes/5/detail',
      additionalData: { global: true, sessionPath: 'a/b' },
    })
    expect(g.scope).toBeNull()
  })

  it('builds the one detail URL from tune + scope', () => {
    expect(detailUrl(5, null)).toBe('/api/tunes/5/detail')
    expect(detailUrl(5, { session: 'a/b' })).toBe('/api/tunes/5/detail?session=a%2Fb')
    expect(detailUrl(5, { session: 'a/b', instance: 9 })).toBe('/api/tunes/5/detail?session=a%2Fb&instance=9')
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

  it('an on-list tune derives the full my-tunes variant and sets ?ptid', async () => {
    stubFetch([['/api/tunes/101/detail', detailPayload()]])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null, tuneName: "Cooley's", tuneType: 'reel' })
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
    // the shape-drift fix: "Last Updated" shows in the my-tunes variant too
    expect(container.querySelector('.stat-note').textContent).toContain('Last Updated 2026-01-01')
    // configure section exists but is collapsed
    expect(container.querySelector('#configure-section').style.display).toBe('none')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
  })

  it('a logged-out viewer on a SESSION page gets no Configure This Tune link', async () => {
    stubFetch([
      [
        '/api/tunes/101/detail',
        detailPayload({
          tune: { session_scope: { path: 'austin/mueller', instance: null, in_repertoire: true } },
          pts: null,
          viewer: { logged_in: false },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, scope: { session: 'austin/mueller' } })
    await waitFor(() => expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe("Cooley's"))
    // session variant renders (notation etc.), but nothing writable for anons
    expect(container.querySelector('.abc-notation-section')).toBeTruthy()
    const linkTexts = [...container.querySelectorAll('.modal-additional-links a')].map((a) => a.textContent)
    expect(linkTexts.join()).not.toMatch(/Configure This Tune|Remove/)
    expect(container.querySelector('#configure-section')).toBeFalsy()
  })

  it('a logged-out viewer derives the read-only view: no status seg, no save, no Generate Notation', async () => {
    stubFetch([
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: { tune_id: 202, tune_name: 'Banish Misfortune', tune_type: 'jig', abc: null, incipit_abc: null },
          pts: null,
          viewer: { logged_in: false },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: null })
    await waitFor(() => expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe('Banish Misfortune'))
    expect(container.querySelector('.tunebook-status-section')).toBeFalsy()
    expect(container.querySelector('#save-btn')).toBeFalsy()
    expect(container.querySelector('.modal-additional-links')).toBeFalsy()
    expect(container.querySelector('.generate-notation-link')).toBeFalsy()
    expect(container.querySelector('.heard-count-section')).toBeFalsy()
  })

  it('status tap posts a set_status op and re-tints the section', async () => {
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/tunes/101/detail', detailPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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
      ['/api/tunes/101/detail', detailPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
    await waitFor(() => expect(container.querySelector('.heard-count-section')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tsc-main-block .tunebook-status-opt[data-status="learned"]'))
    expect(container.querySelector('.heard-count-section')).toBeFalsy()
  })

  it('heard + posts an ABSOLUTE set_heard and updates the label; minus disabled at 0', async () => {
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/tunes/101/detail', detailPayload({ pts: fullPts({ heard_count: 0 }) })],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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
      ['/api/tunes/101/detail', detailPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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

  it('logged-in + not-on-list derives the Add view; Add posts an add op and refetches', async () => {
    // On a non-my-tunes page (the generic Find-a-tune flow): an add refreshes
    // the payload in place — my-tunes-page adds instead upgrade to the full
    // variant (covered in the chaining describe below).
    window.history.replaceState({}, '', '/')
    let onList = false
    stubFetch([
      ['/api/my-tunes/ops', () => ({ success: true })],
      [
        '/api/tunes/202/detail',
        () =>
          detailPayload({
            tune: { tune_id: 202, tune_name: 'Banish Misfortune', tune_type: 'jig' },
            pts: onList ? fullPts({ person_tune_id: 55, learn_status: 'learning' }) : notOnListPts,
          }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202 })
    await waitFor(() => expect(container.querySelector('.tunebook-status-not-on-list')).toBeTruthy())
    expect(container.querySelector('.tsc-notlist-label').textContent).toContain('not on your list')
    // the Add view carries no editing chrome: no Save/Cancel, no configure link
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
        '/api/tunes/101/detail',
        detailPayload({ tune: { incipit_image: 'AAA', image: 'BBB', incipit_abc: 'inc!1', abc: 'full!2' } }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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

  it('the admin tunes page derives the admin variant: name field, no status/heard, repertoire stats', async () => {
    window.history.replaceState({}, '', '/admin/tunes')
    stubFetch([
      [
        '/api/tunes/303/detail',
        detailPayload({
          tune: { tune_id: 303, tune_name: 'The Sligo Maid', tunebook_count: 5, session_count: 1, global_play_count: 2 },
          viewer: { is_admin: true },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 303 }) // scope {admin:true} derived from the URL
    await waitFor(() => expect(container.querySelector('#configure-section')).toBeTruthy())
    expect(window.location.pathname).toBe('/admin/tunes/303')
    expect(container.querySelector('#configure-section').style.display).toBe('block')
    expect(container.querySelector('#tune-name-input').value).toBe('The Sligo Maid')
    expect(container.querySelector('.tunebook-status-section')).toBeFalsy()
    expect(container.querySelector('.heard-count-section')).toBeFalsy()
    expect(container.querySelector('#stats-tab').textContent).toContain('In the repertoire of')
    // dirty-check enables save
    expect(container.querySelector('#save-btn').disabled).toBe(true)
    await fireEvent.input(container.querySelector('#tune-name-input'), { target: { value: 'Renamed' } })
    expect(container.querySelector('#save-btn').disabled).toBe(false)
  })

  it('a session scope derives the session variant: save PUTs only changed fields and calls onSave', async () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/tunes')
    const onSave = vi.fn()
    stubFetch([
      [
        '/api/sessions/austin/mueller/tunes/202',
        (url, opts) => (opts.method === 'PUT' ? { success: true } : { success: false }),
      ],
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: {
            tune_id: 202,
            tune_name: 'Banish Misfortune',
            tune_type: 'jig',
            setting_id: 5,
            key: 'Dmixolydian',
            times_played: 4,
            session_scope: { path: 'austin/mueller', instance: null, in_repertoire: true },
          },
          pts: fullPts({ person_tune_id: 55, learn_status: 'learning' }),
          viewer: { is_session_admin: true },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: { session: 'austin/mueller' }, onSave })
    await waitFor(() => expect(container.querySelector('#alias-input')).toBeTruthy())
    expect(fetchMock.mock.calls[0][0]).toBe('/api/tunes/202/detail?session=austin%2Fmueller')
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes/202')
    // the payload's is_session_admin gates the remove link (no call-site flag)
    expect(container.querySelector('.modal-additional-links').textContent).toContain('Remove From Session')
    expect(container.querySelector('#stats-tab').textContent).toContain('at this session')

    await fireEvent.input(container.querySelector('#alias-input'), { target: { value: 'The Banish' } })
    expect(container.querySelector('#save-btn').disabled).toBe(false)
    await fireEvent.click(container.querySelector('#save-btn'))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    const put = fetchMock.mock.calls.find(([, opts]) => opts && opts.method === 'PUT')
    expect(put[0]).toBe('/api/sessions/austin/mueller/tunes/202')
    expect(JSON.parse(put[1].body)).toEqual({ alias: 'The Banish' })
    expect(container.querySelector('#save-btn').textContent.trim()).toBe('Saved!')
    // URL param cleaned before onSave
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes')
  })

  it('an old-style pill-logger config maps through the shim onto the instance variant', async () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/2026-01-01')
    stubFetch([
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: {
            tune_id: 202,
            tune_name: 'Banish Misfortune',
            name: 'That Night',
            key_override: 'Aminor',
            session_scope: { path: 'austin/mueller', instance: 9, in_repertoire: true },
          },
          pts: fullPts({ person_tune_id: 55 }),
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({
      context: 'session_instance',
      tuneId: 202,
      apiEndpoint: '/api/sessions/austin/mueller/2026-01-01/tunes/202',
      additionalData: { sessionPath: 'austin/mueller', dateOrId: '2026-01-01', isUserLoggedIn: true },
    })
    await waitFor(() => expect(container.querySelector('#alias-input')).toBeTruthy())
    // the shim built the scoped feed URL
    expect(fetchMock.mock.calls[0][0]).toContain('/api/tunes/202/detail?session=austin%2Fmueller&instance=2026-01-01')
    // instance wording
    expect(container.textContent).toContain('In this case, we called it:')
  })

  it('offline fallback renders from CeolOffline with pending ops overlaid (derivation included)', async () => {
    // A network failure (offline) REJECTS — the drawer then derives its facts
    // from the bundle: logged_in true, on-list from the overlaid learn_status.
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
    component.show({ tuneId: 909, ptid: 'pending-909', scope: null })
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
    // a ?ptid the host page could not resolve to a tune_id
    component.show({ tuneId: null, ptid: 999, scope: null })
    await waitFor(() => expect(container.querySelector('.modal-error')).toBeTruthy())
    expect(container.querySelector('.modal-error').textContent).toContain('no longer exists')
    expect(new URL(window.location).searchParams.get('ptid')).toBeNull()
  })

  it('redirected_from heals the config and shows the merged notice', async () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/tunes')
    stubFetch([
      [
        '/api/tunes/100/detail',
        detailPayload({
          tune: { tune_id: 200, tune_name: 'Banish Misfortune' },
          pts: fullPts({ person_tune_id: 55 }),
          redirected_from: 100,
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 100, scope: { session: 'austin/mueller' } })
    await waitFor(() => expect(container.querySelector('.tune-merged-notice')).toBeTruthy())
    expect(container.querySelector('.tune-merged-notice').textContent).toContain('Tune #100 was merged into')
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes/200')
  })

  it('close removes the URL param and hides after the 300ms fade', async () => {
    // Only fake the timeout clock: Svelte's DOM flush rides the microtask queue.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    stubFetch([['/api/tunes/101/detail', detailPayload()]])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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

describe('TuneSheet — chaining, host notification, roll-up reset, generate notation', () => {
  const playedWith = (ids) => ({
    success: true,
    tunes: ids.map((id) => ({ tune_id: id, name: `Tune #${id}`, count: 2 })),
  })

  it('Played With chaining keeps the derived variant (notes/config/ptid) and the callbacks', async () => {
    const onStatusChange = vi.fn()
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/tunes/101/played-with', playedWith([202])],
      ['/api/tunes/101/detail', detailPayload()],
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: { tune_id: 202, tune_name: 'Banish Misfortune', tune_type: 'jig' },
          pts: fullPts({ person_tune_id: 55, notes: 'chained notes' }),
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null, onStatusChange })
    await waitFor(() => expect(container.querySelector('.modal-tab[data-tab="played-with"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="played-with"]'))
    await waitFor(() => expect(container.querySelector('.played-with-item[data-tune-id="202"]')).toBeTruthy())

    await fireEvent.click(container.querySelector('.played-with-item[data-tune-id="202"]'))
    // the payload's on_list derives the full my-tunes variant — no resolver hop
    await waitFor(() => expect(container.querySelector('#notes-textarea')).toBeTruthy())
    expect(container.querySelector('#notes-textarea').value).toBe('chained notes')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
    expect(container.querySelector('.modal-additional-links').textContent).toContain('Remove From My Tunes')
    // the URL learned the chained tune's ptid from the payload
    expect(new URL(window.location).searchParams.get('ptid')).toBe('55')

    // the host callback was inherited: a status change on the CHAINED tune notifies it
    await fireEvent.click(container.querySelector('.tsc-main-block .tunebook-status-opt[data-status="learned"]'))
    await waitFor(() =>
      expect(onStatusChange).toHaveBeenCalledWith(
        expect.objectContaining({ tune_id: 202, learn_status: 'learned', on_list: true, person_tune_id: 55 })
      )
    )
  })

  it('chained not-on-list tune shows the Add view; adding upgrades IN PLACE and notifies the host once', async () => {
    const onStatusChange = vi.fn()
    let onList = false
    stubFetch([
      ['/api/my-tunes/ops', { success: true }],
      ['/api/tunes/101/played-with', playedWith([303])],
      ['/api/tunes/303/played-with', playedWith([])],
      ['/api/tunes/303/history', { success: true, play_instances: [] }],
      ['/api/tunes/101/detail', detailPayload()],
      [
        '/api/tunes/303/detail',
        () =>
          detailPayload({
            tune: { tune_id: 303, tune_name: 'The Chained', tune_type: 'reel' },
            pts: onList ? fullPts({ person_tune_id: 77, notes: 'now mine' }) : notOnListPts,
          }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null, onStatusChange })
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

    // ...and the flipped on_list DERIVES the full my-tunes variant in place (no close)
    await waitFor(() => expect(container.querySelector('#notes-textarea')).toBeTruthy())
    expect(container.querySelector('#tune-detail-modal').style.display).toBe('flex')
    expect(container.querySelector('#notes-textarea').value).toBe('now mine')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
    expect(container.querySelector('.modal-additional-links').textContent).toContain('Remove From My Tunes')
    expect(new URL(window.location).searchParams.get('ptid')).toBe('77')
    // the tab the user was on survives the upgrade
    expect(container.querySelector('#played-with-tab.active')).toBeTruthy()
    // the my-tunes history scope toggle (My sessions / Attended / All sessions) is offered
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="history"]'))
    await waitFor(() =>
      expect([...container.querySelectorAll('#history-tab .history-scope-btn')].map((b) => b.textContent.trim())).toEqual([
        'My sessions',
        'Attended',
        'All sessions',
      ])
    )
    // the host was notified exactly once — the derived upgrade doesn't re-notify
    expect(onStatusChange).toHaveBeenCalledTimes(1)
  })

  it('session-scoped chaining carries the same scope (and callbacks)', async () => {
    window.history.replaceState({}, '', '/sessions/austin/mueller/tunes')
    stubFetch([
      ['/api/tunes/202/played-with', playedWith([404])],
      [
        '/api/tunes/404/detail',
        detailPayload({
          tune: {
            tune_id: 404,
            tune_name: 'The Chained',
            session_scope: { path: 'austin/mueller', instance: null, in_repertoire: true },
          },
          pts: fullPts({ person_tune_id: 66 }),
        }),
      ],
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: {
            tune_id: 202,
            tune_name: 'Banish Misfortune',
            session_scope: { path: 'austin/mueller', instance: null, in_repertoire: true },
          },
          pts: fullPts({ person_tune_id: 55 }),
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: { session: 'austin/mueller' } })
    await waitFor(() => expect(container.querySelector('.modal-tab[data-tab="played-with"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="played-with"]'))
    await waitFor(() => expect(container.querySelector('.played-with-item[data-tune-id="404"]')).toBeTruthy())
    await fireEvent.click(container.querySelector('.played-with-item[data-tune-id="404"]'))
    await waitFor(() => expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe('The Chained'))
    // still the session variant: scoped fetch, path URL, session config fields
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/api/tunes/404/detail?session=austin%2Fmueller'))).toBe(
      true
    )
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes/404')
    expect(container.querySelector('#alias-input')).toBeTruthy()
  })

  it('the per-instrument roll-up resets to collapsed when the drawer shows another tune', async () => {
    stubFetch([
      ['/api/tunes/101/detail', detailPayload()],
      [
        '/api/tunes/102/detail',
        detailPayload({ tune: { tune_id: 102, tune_name: 'The Second' }, pts: fullPts({ person_tune_id: 12 }) }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
    await waitFor(() => expect(container.querySelector('.tsc-expand-link')).toBeTruthy())
    await fireEvent.click(container.querySelector('.tsc-expand-link'))
    expect(container.querySelector('.tsc-instruments')).toBeTruthy()

    component.show({ tuneId: 102, ptid: 12, scope: null })
    await waitFor(() => expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe('The Second'))
    expect(container.querySelector('.tsc-instruments')).toBeFalsy()
    expect(container.querySelector('.tsc-expand-link').textContent.trim()).toBe('View By Instrument')
  })

  it('expandInstrumentStatus still opens the roll-up pre-expanded', async () => {
    stubFetch([['/api/tunes/101/detail', detailPayload()]])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null, expandInstrumentStatus: true })
    await waitFor(() => expect(container.querySelector('.tsc-instruments')).toBeTruthy())
  })

  it('no cached notation -> Generate Notation runs the settings-cache action and renders in place', async () => {
    stubFetch([
      [
        '/api/tunes/101/settings/cache',
        { success: true, setting: { setting_id: 9, abc: 'full!abc', incipit_abc: 'inc!abc', image: null, incipit_image: null } },
      ],
      ['/api/my-tunes/11', (url, opts) => (opts.method === 'PUT' ? { success: true } : { success: false })],
      ['/api/tunes/101/detail', detailPayload({ tune: { abc: null, incipit_abc: null } })],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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
    // the setting id was saved through the my-tunes variant's PUT target
    const put = fetchMock.mock.calls.find(([, opts]) => opts && opts.method === 'PUT')
    expect(put[0]).toBe('/api/my-tunes/11')
  })

  it('abc cached but no rendered image -> Generate Notation sits in the toggle spot and switches to dots', async () => {
    // The DEFAULT payload is exactly this state (abc + incipit_abc, no images) —
    // the same state every seeded tune is in, and the regression the user hit
    // twice: the link must appear where the notes/abc toggle would sit.
    stubFetch([
      [
        '/api/tunes/101/settings/cache',
        {
          success: true,
          setting: { setting_id: 9, abc: 'full!abc', incipit_abc: 'inc!abc', image: null, incipit_image: 'IMGDATA' },
        },
      ],
      ['/api/my-tunes/11', (url, opts) => (opts.method === 'PUT' ? { success: true } : { success: false })],
      ['/api/tunes/101/detail', detailPayload()],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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
      ['/api/tunes/101/detail', detailPayload({ tune: { abc: null, incipit_abc: null } })],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
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

describe('DRIFT GUARD: offline bundle parity with the API detail payload', () => {
  // ONE tune's facts, expressed both ways:
  //   - as the API detail payload (GET /api/tunes/<id>/detail), and
  //   - as an offline bundle entry (one GET /api/offline/bundle tunes[] dict, the
  //     shape api_person_tune_routes.get_offline_bundle documents) fed through the
  //     offline path (fetch fails -> CeolOffline.getTune -> offlinePayload).
  // The drawer must render the SAME load-bearing UI from both. When a future
  // drawer field exists online but the bundle silently lacks it, the two digests
  // diverge and this test fails — instead of the user noticing a blank offline.
  const bundleEntry = {
    person_tune_id: 11,
    tune_id: 101,
    tune_name: "Cooley's",
    name: "Cooley's",
    tune_type: 'reel',
    learn_status: 'want to learn',
    heard_count: 2,
    notes: 'first two bars',
    name_alias: 'Cooleys (mine)',
    setting_id: 4321,
    learned_date: null,
    tunebook_count: 9,
    tunebook_count_cached_date: '2026-01-01',
    setting_key: 'Edorian',
    incipit_abc: 'EBBA!B2 EB',
    incipit_image: null,
    global_play_count: 7,
    person_list_count: 4,
    instruments: [
      { instrument: 'Fiddle', is_auto: true },
      { instrument: 'Flute', is_auto: false },
    ],
    instrument_status: {},
    session_play_count: 3,
  }

  // The SAME facts as the online payload. Online-only extras (full-size abc/image,
  // the session-scope fields) sit at their unscoped defaults — exactly what the
  // offline path synthesizes, so any other difference is real drift.
  const onlinePayload = detailPayload({
    tune: { setting_id: 4321, setting_key: 'Edorian', abc: null, incipit_abc: 'EBBA!B2 EB' },
    pts: fullPts({ name_alias: 'Cooleys (mine)', setting_id: 4321 }),
  })

  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim()
  const digest = (c) => ({
    title: norm(c.querySelector('.modal-tune-title')?.textContent),
    typePill: norm(c.querySelector('.tune-type-pill')?.textContent),
    activeStatus: c.querySelector('.tsc-main-block .tunebook-status-opt.active')?.dataset.status,
    statusTint: [...(c.querySelector('.tunebook-status-section')?.classList || [])]
      .filter((cl) => cl.startsWith('tunebook-status-') && cl !== 'tunebook-status-section')
      .join(' '),
    instrumentExpand: norm(c.querySelector('.tsc-expand-link')?.textContent),
    heard: norm(c.querySelector('#heard-count-value')?.textContent),
    notation: c.querySelector('.abc-notation-text')?.textContent,
    notes: c.querySelector('#notes-textarea')?.value,
    nameAlias: c.querySelector('#name-alias-input')?.value,
    settingField: c.querySelector('#setting-input')?.value,
    removeLink: /Remove From My Tunes/.test(c.querySelector('.modal-additional-links')?.textContent || ''),
    // The whole Stats tab: tunebook count row (incl. "Last Updated"), list count,
    // my-sessions and all-sessions play counts.
    statsTab: norm(c.querySelector('#stats-tab')?.textContent),
  })

  it('renders the same load-bearing UI online and offline', async () => {
    // Online render: the API detail payload.
    stubFetch([['/api/tunes/101/detail', onlinePayload]])
    const online = render(TuneSheet)
    online.component.show({ tuneId: 101, scope: null })
    await waitFor(() =>
      expect(online.container.querySelector('.modal-tune-title')?.textContent).toContain('Cooleys (mine)')
    )
    const onlineDigest = digest(online.container)
    online.unmount()

    // Sanity-pin the online side first so "both blank" can never pass.
    expect(onlineDigest.activeStatus).toBe('want to learn')
    expect(onlineDigest.statusTint).toBe('tunebook-status-want-to-learn')
    expect(onlineDigest.instrumentExpand).toBe('View By Instrument')
    expect(onlineDigest.heard).toBe('2')
    expect(onlineDigest.notation).toBe('EBBA\nB2 EB')
    expect(onlineDigest.notes).toBe('first two bars')
    expect(onlineDigest.nameAlias).toBe('Cooleys (mine)')
    expect(onlineDigest.settingField).toBe('4321')
    expect(onlineDigest.statsTab).toContain('Saved in 4 tune lists on Ceol.io')
    expect(onlineDigest.statsTab).toContain('Saved in 9 tunebooks on TheSession.org')
    expect(onlineDigest.statsTab).toContain('Last Updated 2026-01-01')
    expect(onlineDigest.statsTab).toContain('Logged 3 times at my sessions')
    expect(onlineDigest.statsTab).toContain('Logged 7 times at all sessions')

    // Offline render: network dead, the SAME tune served from the cached bundle.
    fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)
    window.CeolOffline = { getTune: vi.fn().mockResolvedValue({ ...bundleEntry }) }
    window.MyTunesOffline = {
      pending: vi.fn().mockResolvedValue([]),
      submit: vi.fn().mockResolvedValue({ online: false, queued: true }),
    }
    const offline = render(TuneSheet)
    offline.component.show({ tuneId: 101, scope: null })
    await waitFor(() =>
      expect(offline.container.querySelector('.modal-tune-title')?.textContent).toContain('Cooleys (mine)')
    )
    expect(digest(offline.container)).toEqual(onlineDigest)
  })
})
