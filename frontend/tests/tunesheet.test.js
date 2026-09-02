// Tests for the Svelte tune-detail sheet (spec 035 Step 3, derived-mode
// refactor). These pin the legacy DOM contract (#tune-detail-modal /
// #tune-detail-content / the section classes the shared stylesheet + e2e suite
// select on), the auto-save / offline behaviors, and the NEW invariants: one
// payload endpoint feeds the drawer and the variant is DERIVED from it
// (viewer.logged_in, person_tune_status.on_list, the scope) rather than
// declared by call sites.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushSync } from 'svelte'
import { render, waitFor, cleanup } from '@testing-library/svelte'
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
  isEditableScope,
  historyUrl,
  playedWithScopeOptions,
} from '../src/tunesheet/logic.js'

// ---- spec 033 scope matrices (pure) ----------------------------------------------

describe('the History droplist — the ONE scope control (spec 037)', () => {
  const ids = (opts) => opts.map((o) => o.id)
  const instances = [
    { session_instance_id: 9, date: '2026-01-01', start_time: null, location_override: null, positions: [] },
  ]

  it('reads as one sentence: the session, then its nights, then the wide lenses', () => {
    const opts = historyScopeOptions(instances, 'The Cobblestone', { inSession: true, loggedIn: true })
    expect(opts.map((o) => o.label)).toEqual([
      'At The Cobblestone',
      '… on Thu 1 Jan 2026',
      'At a different session …',
      'All My Sessions',
      'All Sessions',
    ])
  })

  it('drops the session rows when no session is in scope, and My Sessions when logged out', () => {
    expect(ids(historyScopeOptions([], null, { inSession: false, loggedIn: true }))).toEqual(['member', 'all'])
    expect(ids(historyScopeOptions([], null, { inSession: false, loggedIn: false }))).toEqual(['all'])
    expect(ids(historyScopeOptions(instances, 'X', { inSession: true, loggedIn: false }))).toEqual([
      'general', '9', '__other__', 'all',
    ])
  })

  it('marks only a session and its instances as editable', () => {
    // "What we call it" is a fact about a session or a performance. It means nothing
    // across all of them, so the wide lenses carry no form.
    const opts = historyScopeOptions(instances, 'X', { inSession: true, loggedIn: true })
    const editable = opts.filter((o) => o.editable).map((o) => o.id)
    expect(editable).toEqual(['general', '9'])
    expect(isEditableScope('general')).toBe(true)
    expect(isEditableScope('9')).toBe(true)
    expect(isEditableScope('member')).toBe(false)
    expect(isEditableScope('all')).toBe(false)
    expect(isEditableScope('__other__')).toBe(false)
  })

  it('builds the request for each scope, with "while I was there" as a FILTER on top', () => {
    // The filter ANDs onto any scope — which is the whole reason it stopped being one of a
    // set of mutually-exclusive Seg options. "Nights at Mueller I was actually there for"
    // was not expressible before.
    expect(historyUrl(7, 'general', 'austin/mueller', false)).toBe(
      '/api/tunes/7/history?session_path=austin%2Fmueller'
    )
    expect(historyUrl(7, 'general', 'austin/mueller', true)).toBe(
      '/api/tunes/7/history?session_path=austin%2Fmueller&attended=1'
    )
    expect(historyUrl(7, 'member', null, false)).toBe('/api/tunes/7/history?scope=member')
    expect(historyUrl(7, 'member', null, true)).toBe('/api/tunes/7/history?scope=member&attended=1')
    expect(historyUrl(7, 'all', null, false)).toBe('/api/tunes/7/history')
    expect(historyUrl(7, 'all', null, true)).toBe('/api/tunes/7/history?attended=1')
  })
})

describe('scope option matrices (spec 033)', () => {
  const keys = (opts) => opts.map((o) => o.key)
  const sessScope = { session: 'austin/mueller' }

  it('played-with keeps its own Seg (coupling it to the History droplist would over-fit)', () => {
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
  tags: ['practice', 'session'],
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

// The session_scope block the Session tab reads (spec 037). can_edit_session is the
// admin gate on what the session plays IN GENERAL; can_edit_instance is the weaker
// member gate on what got played on one night; can_remove_from_session is false the
// moment the tune has any plays here.
const sessScope = (o = {}) => ({
  path: 'austin/mueller',
  session_name: 'Mueller Session',
  instance: null,
  date_or_id: null,
  in_repertoire: true,
  played_instances: [],
  can_edit_session: false,
  can_edit_instance: false,
  can_remove_from_session: false,
  ...o,
})

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

// A tune imported from thesession.org lands with ABC only — its PNGs are rendered on
// demand, and until the drawer did that itself, every tune added through the My Tunes
// pane showed abc text and waited for someone to press Generate Notation.
describe('lazy notation render (imported tunes arrive as ABC only)', () => {
  const noImages = {
    tune: { setting_id: 5150, abc: 'EBBA!B2 EB!full body', incipit_abc: 'EBBA!B2 EB', image: null, incipit_image: null },
  }
  const settingImageCalls = () =>
    fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes('/setting-image/'))

  it('renders and shows the missing dots, incipit first then the full staff', async () => {
    stubFetch([
      ['/api/tunes/101/detail', detailPayload(noImages)],
      ['/setting-image/5150?kind=incipit', { success: true, image: 'INCIPIT-PNG' }],
      ['/setting-image/5150?kind=full', { success: true, image: 'FULL-PNG' }],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })

    // The abc text is what's on screen until the render lands...
    await waitFor(() => expect(container.querySelector('.abc-notation-text')).toBeTruthy())
    // ...then the dots replace it, without anyone pressing Generate Notation.
    await waitFor(() => {
      const img = container.querySelector('.abc-notation-image')
      expect(img).toBeTruthy()
      expect(img.getAttribute('src')).toBe('data:image/png;base64,INCIPIT-PNG')
    })
    // Both sizes get rendered, so the incipit/full toggle isn't a dead control.
    await waitFor(() => expect(settingImageCalls()).toHaveLength(2))
    expect(settingImageCalls()[0]).toContain('kind=incipit')
    expect(settingImageCalls()[1]).toContain('kind=full')
  })

  it('asks once per setting, however often the drawer re-renders', async () => {
    stubFetch([
      ['/api/tunes/101/detail', detailPayload(noImages)],
      ['/setting-image/', { success: true, image: 'PNG' }],
    ])
    const { component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
    await waitFor(() => expect(settingImageCalls().length).toBe(2))
    component.close()
    component.show({ tuneId: 101, ptid: 11, scope: null })
    await new Promise((r) => setTimeout(r, 50))
    expect(settingImageCalls()).toHaveLength(2) // the cached PNGs are already in the payload's future
  })

  it('never renders for a tune that already has its notation, or for a logged-out viewer', async () => {
    stubFetch([['/api/tunes/101/detail', detailPayload({ tune: { setting_id: 5150, incipit_image: 'ALREADY' } })]])
    const { component } = render(TuneSheet)
    component.show({ tuneId: 101, ptid: 11, scope: null })
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 50))
    expect(settingImageCalls()).toHaveLength(0)

    cleanup()
    stubFetch([['/api/tunes/101/detail', detailPayload({ ...noImages, viewer: { logged_in: false } })]])
    const second = render(TuneSheet)
    second.component.show({ tuneId: 101, scope: null })
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 50))
    // Rendering writes to the catalog — it needs a signed-in viewer (same gate as
    // the Generate Notation affordance).
    expect(settingImageCalls()).toHaveLength(0)
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
    // 2 instruments -> expand toggle offered, now living in the action row
    expect(container.querySelector('.tsc-expand-link').textContent.trim()).toBe('View By Instrument')
    // heard count section (status is want-to-learn and a person_tune_id exists)
    expect(container.querySelector('#heard-count-value').textContent).toBe('2')
    expect(container.querySelector('.abc-notation-section')).toBeTruthy()
    // Remove From My Tunes moved out of the footer links and into the action row.
    expect(container.querySelector('.tsc-action-row .tsc-action-danger').textContent).toContain('Remove From My Tunes')
    expect(container.querySelector('.modal-additional-links')).toBeFalsy()
    // The drawer now opens on My List (the personal tab); History is still present (the
    // next tab) and, with no session in scope, its droplist offers only the wide lenses.
    expect(container.querySelector('#my-list-tab.active')).toBeTruthy()
    expect([...container.querySelector('#sess-scope-select').options].map((o) => o.value)).toEqual([
      'member',
      'all',
    ])
    expect(container.querySelector('#tunebook-count').textContent).toBe('9')
    expect(container.querySelector('.stat-note').textContent).toContain('Last Updated 2026-01-01')
    // The canonical name + id moved out of the config header and into Stats.
    expect(container.querySelector('.stat-canonical').textContent).toContain("Canonical name: Cooley's (#101)")

    // Personal config is collapsed behind Configure — and the title no longer opens it.
    expect(container.querySelector('#configure-section')).toBeFalsy()
    expect(container.querySelector('.modal-tune-title-clickable')).toBeFalsy()
    await fireEvent.click(container.querySelector('.tsc-action-row .tsc-action-link'))
    expect(container.querySelector('#configure-section')).toBeTruthy()
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
    expect(container.querySelector('#my-key-select')).toBeTruthy()
    // My Notes now always renders in its own panel, NOT behind Configure.
    expect(container.querySelector('#notes-textarea').value).toBe('first two bars')
    expect(container.querySelector('#save-btn').disabled).toBe(true)
  })

  it('notes auto-save on blur via a scoped PUT (no Save button involved)', async () => {
    const puts = []
    stubFetch([
      ['/api/tunes/101/detail', detailPayload({ pts: fullPts({ person_tune_id: 11 }) })],
      [
        '/api/my-tunes/11',
        (url, opts) => {
          puts.push(JSON.parse(opts.body))
          return { success: true }
        },
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, scope: null })
    await waitFor(() => expect(container.querySelector('#notes-textarea')).toBeTruthy())

    // Notes are always visible — no Configure click needed. Edit + blur = save.
    const notes = container.querySelector('#notes-textarea')
    await fireEvent.input(notes, { target: { value: 'new note' } })
    await fireEvent.blur(notes)

    await waitFor(() => expect(puts).toEqual([{ notes: 'new note' }]))
    // A no-op blur (no change) must NOT fire another PUT.
    await fireEvent.blur(notes)
    expect(puts).toEqual([{ notes: 'new note' }])
  })

  it('tags auto-save on blur; the Configure Save button covers only name/setting/key', async () => {
    const puts = []
    stubFetch([
      ['/api/tunes/101/detail', detailPayload({ pts: fullPts({ person_tune_id: 11, tags: ['old'] }) })],
      [
        '/api/my-tunes/11',
        (url, opts) => {
          puts.push(JSON.parse(opts.body))
          return { success: true }
        },
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, scope: null })
    await waitFor(() => expect(container.querySelector('#tags-input')).toBeTruthy())

    // Add a tag, then move focus out of the tag box entirely → save just the tags.
    const tagField = container.querySelector('#tags-input')
    await fireEvent.input(tagField, { target: { value: 'new' } })
    await fireEvent.keyDown(tagField, { key: 'Enter' })
    await fireEvent.focusOut(tagField, { relatedTarget: document.body })
    await waitFor(() => expect(puts).toEqual([{ tags: ['old', 'new'] }]))
  })

  it('a logged-out viewer on a SESSION page can READ the Session tab but not edit it', async () => {
    stubFetch([
      [
        '/api/tunes/101/detail',
        detailPayload({
          tune: { alias: 'The Cooley', key: 'Edorian', session_scope: sessScope() },
          pts: null,
          viewer: { logged_in: false },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 101, scope: { session: 'austin/mueller' } })
    await waitFor(() => expect(container.querySelector('#history-tab')).toBeTruthy())
    expect(container.querySelector('.abc-notation-section')).toBeTruthy()
    // Anyone may see what a session plays; only an admin may change it.
    expect(container.querySelector('.sess-form-readonly')).toBeTruthy()
    expect(container.querySelector('#sess-alias-input')).toBeFalsy()
    expect(container.querySelector('#history-tab').textContent).toContain('The Cooley')
    expect(container.querySelector('#history-tab').textContent).toContain('Edorian')
    // Nothing writable for an anon: no personal config, no removes.
    expect(container.querySelector('#configure-section')).toBeFalsy()
    expect(container.querySelector('.tsc-action-row')).toBeFalsy()
    expect(container.textContent).not.toContain('Remove From Session')
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
    expect(container.querySelector('.tsc-action-row')).toBeFalsy()
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
    expect(container.querySelector('#tune-name-input').value).toBe('The Sligo Maid')
    expect(container.querySelector('.tunebook-status-section')).toBeFalsy()
    expect(container.querySelector('.heard-count-section')).toBeFalsy()
    expect(container.querySelector('#stats-tab').textContent).toContain('In the repertoire of')
    // dirty-check enables save
    const saveBtn = container.querySelector('#configure-section .btn-primary')
    expect(saveBtn.disabled).toBe(true)
    await fireEvent.input(container.querySelector('#tune-name-input'), { target: { value: 'Renamed' } })
    expect(saveBtn.disabled).toBe(false)
  })

  it('a session scope: My List is leftmost + default, session History is next, and In General PUTs only changed fields', async () => {
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
            session_scope: sessScope({ can_edit_session: true, can_edit_instance: true }),
          },
          pts: fullPts({ person_tune_id: 55, learn_status: 'learning' }),
          viewer: { is_session_admin: true },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: { session: 'austin/mueller' }, onSave })
    await waitFor(() => expect(container.querySelector('#history-tab')).toBeTruthy())
    expect(fetchMock.mock.calls[0][0]).toBe('/api/tunes/202/detail?session=austin%2Fmueller')
    expect(window.location.pathname).toBe('/sessions/austin/mueller/tunes/202')

    // My List is leftmost and the drawer opens on it; the session's History is the next
    // tab. Its droplist IS that tab's heading — it names the session, and the rest of the
    // list continues the sentence downward.
    expect([...container.querySelectorAll('.modal-tab')].map((t) => t.dataset.tab)).toEqual([
      'my-list',
      'history',
      'stats',
      'played-with',
    ])
    expect(container.querySelector('#my-list-tab.active')).toBeTruthy()
    const scopeSel = container.querySelector('#sess-scope-select')
    expect(scopeSel.value).toBe('general')
    expect(scopeSel.options[0].text).toBe('At Mueller Session')
    expect([...scopeSel.options].map((o) => o.text)).toEqual([
      'At Mueller Session',
      'At a different session …',
      'All My Sessions',
      'All Sessions',
    ])
    expect(container.querySelector('.sess-name')).toBeFalsy() // the old linked title is gone

    // The count line above the list. (There's no longer a link "over to History" — the
    // history is right here; that was the whole point of merging the two tabs.)
    expect(container.querySelector('.hist-summary').textContent.trim()).toBe(
      'Played 4 times at this session'
    )

    // The personal form is still here, on a session surface — that's the point of 037.
    expect(container.querySelector('.tsc-action-row')).toBeTruthy()

    // The edit form waits until it's asked for.
    expect(container.querySelector('#sess-alias-input')).toBeFalsy()
    expect(container.querySelector('.sess-edit-link').textContent).toContain(
      'Update name, setting or key for this tune at this session'
    )
    await fireEvent.click(container.querySelector('.sess-edit-link'))
    expect(container.querySelector('#history-tab').textContent).toContain('We call this:') // present tense

    const save = () => container.querySelector('.sess-form .btn-primary')
    expect(save().disabled).toBe(true)
    await fireEvent.input(container.querySelector('#sess-alias-input'), { target: { value: 'The Banish' } })
    expect(save().disabled).toBe(false)
    await fireEvent.click(save())
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    const put = fetchMock.mock.calls.find(([, opts]) => opts && opts.method === 'PUT')
    expect(put[0]).toBe('/api/sessions/austin/mueller/tunes/202')
    expect(JSON.parse(put[1].body)).toEqual({ alias: 'The Banish' })
  })

  it('the list loads for the selected scope; "while I was there" filters it and marks the nights', async () => {
    const night = (id, attended) => ({
      full_name: `Mueller - 2026-0${id}-01`,
      session_name: 'Mueller Session',
      session_path: 'austin/mueller',
      date: `2026-0${id}-01`,
      set_number: 1,
      position_in_set: 2,
      session_instance_id: id,
      session_instance_tune_id: 500 + id,
      attended,
      link: `/sessions/austin/mueller/${id}?highlight=${500 + id}&tune=202`,
    })
    stubFetch([
      // The filter is a separate request, not a client-side sieve — the 100-instance cap
      // means filtering in the client would silently drop nights past the cap.
      [
        'history?session_path=austin%2Fmueller&attended=1',
        { success: true, play_instances: [night(2, true)], truncated: false },
      ],
      [
        'history?session_path=austin%2Fmueller',
        { success: true, play_instances: [night(1, false), night(2, true)], truncated: false },
      ],
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: { tune_id: 202, times_played: 2, session_scope: sessScope({ can_edit_session: true }) },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: { session: 'austin/mueller' } })

    // The drawer opens straight onto History and the list arrives async.
    await waitFor(() => expect(container.querySelectorAll('.history-item').length).toBe(2))
    expect(container.querySelector('.hist-summary').textContent.trim()).toBe(
      'Played 2 times at this session'
    )
    // The night I was there is MARKED, not merely filterable — a quiet check on the row,
    // with the words behind hover/tap rather than shouted in a chip.
    const items = [...container.querySelectorAll('.history-item')]
    expect(items[0].querySelector('.history-attended-mark')).toBeFalsy()
    const mark = items[1].querySelector('.history-attended-mark')
    expect(mark).toBeTruthy()
    expect(mark.getAttribute('title')).toBe('You were there')
    expect(mark.getAttribute('aria-label')).toBe('You were there')

    // Flipping the filter re-asks the question at the same scope.
    await fireEvent.click(container.querySelector('.hist-filter input'))
    await waitFor(() => expect(container.querySelectorAll('.history-item').length).toBe(1))
    // The payload's counts don't know about the filter, so the summary steps aside. (That
    // the filter holds the right edge rather than sliding into the gap is a CSS concern —
    // margin-left:auto on .hist-filter — and this component has no <style> block, so the
    // stylesheet isn't loaded here. Verified in the browser, not asserted here.)
    expect(container.querySelector('.hist-summary')).toBeFalsy()
    expect(container.querySelector('.hist-filter')).toBeTruthy()
  })

  it('an instance scope answers from the payload — no history request at all', async () => {
    stubFetch([
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: {
            tune_id: 202,
            session_scope: sessScope({
              instance: 9,
              can_edit_instance: true,
              played_instances: [
                {
                  session_instance_id: 9,
                  date: '2026-01-01',
                  start_time: null,
                  location_override: null,
                  positions: [{ session_instance_tune_id: 501, set_number: 3, position_in_set: 2 }],
                },
              ],
            }),
          },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: { session: 'austin/mueller', instance: 9 } })
    await waitFor(() => expect(container.querySelector('.history-item')).toBeTruthy())
    expect(container.querySelector('.history-item a').textContent.trim()).toBe('Set 3, tune 2')
    // The payload already carries that night's coordinates, so nothing was fetched for it.
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/history'))).toBe(false)
  })

  it('offline, the history says so rather than failing', async () => {
    stubFetch([
      ['/api/tunes/202/detail', detailPayload({ tune: { tune_id: 202, session_scope: null } })],
    ])
    const onLine = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    try {
      const { container, component } = render(TuneSheet)
      component.show({ tuneId: 202, scope: null })
      await waitFor(() => expect(container.querySelector('#history-list-container')).toBeTruthy())
      expect(container.querySelector('.no-history').textContent).toContain(
        "Play history isn't available offline"
      )
      // ...and it didn't even try: history is a live query, not part of the offline bundle.
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/history'))).toBe(false)
    } finally {
      onLine.mockRestore()
    }
  })

  it('"At a different session ..." re-scopes the whole drawer, and excludes visitor sessions', async () => {
    stubFetch([
      [
        '/api/my-sessions',
        {
          success: true,
          sessions: [
            { path: 'austin/mueller', name: 'Mueller Session', relationship: 'member' },
            { path: 'dublin/cobblestone', name: 'The Cobblestone', relationship: 'member' },
            { path: 'doolin/mcganns', name: "McGann's", relationship: 'visitor' },
          ],
        },
      ],
      [
        '/api/tunes/202/detail?session=dublin%2Fcobblestone',
        detailPayload({
          tune: {
            tune_id: 202,
            tune_name: 'Banish Misfortune',
            alias: 'The Cobblestone Name',
            times_played: 9,
            session_scope: sessScope({
              path: 'dublin/cobblestone',
              session_name: 'The Cobblestone',
              can_edit_session: true,
            }),
          },
        }),
      ],
      [
        '/api/tunes/202/detail',
        detailPayload({
          tune: { tune_id: 202, tune_name: 'Banish Misfortune', session_scope: sessScope() },
        }),
      ],
    ])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: { session: 'austin/mueller' } })
    await waitFor(() => expect(container.querySelector('#sess-scope-select')).toBeTruthy())

    const sel = container.querySelector('#sess-scope-select')
    sel.value = '__other__'
    await fireEvent.change(sel)

    // The sentinel row is an errand, not a target: the select snaps back, so cancelling
    // the picker can't strand it on a row that means nothing.
    expect(sel.value).toBe('general')

    // The picker offers my OTHER member sessions. Not the one I'm already on, and not a
    // session I merely visited once — that isn't a repertoire I have a view on.
    await waitFor(() => expect(document.querySelector('.kit-list-row')).toBeTruthy())
    const rows = [...document.querySelectorAll('.kit-list-row')].map((r) => r.textContent)
    expect(rows.join('|')).toContain('The Cobblestone')
    expect(rows.join('|')).not.toContain('Mueller Session')
    expect(rows.join('|')).not.toContain("McGann's")

    // Picking one re-scopes the whole drawer: the payload, the session name, the counts.
    await fireEvent.click(document.querySelector('.kit-list-row'))
    await waitFor(() =>
      expect(container.querySelector('#sess-scope-select').options[0].text).toBe('At The Cobblestone')
    )
    expect(container.querySelector('.hist-summary').textContent).toContain('Played 9 times at this session')
    // ...and it does NOT rewrite the URL — the page behind the drawer is still Mueller.
    expect(window.location.pathname).not.toContain('cobblestone')
  })

  it('Remove From Session only renders for a tune with no plays here', async () => {
    const payload = (o) =>
      detailPayload({
        tune: { tune_id: 202, tune_name: 'Banish Misfortune', session_scope: sessScope(o) },
        viewer: { is_session_admin: true },
      })
    // Has plays -> the option is simply absent. No explanation, it just isn't offered.
    stubFetch([['/api/tunes/202/detail', payload({ can_edit_session: true, can_remove_from_session: false })]])
    const { container, component } = render(TuneSheet)
    component.show({ tuneId: 202, scope: { session: 'austin/mueller' } })
    await waitFor(() => expect(container.querySelector('#history-tab')).toBeTruthy())
    expect(container.textContent).not.toContain('Remove From Session')

    cleanup()
    stubFetch([['/api/tunes/202/detail', payload({ can_edit_session: true, can_remove_from_session: true })]])
    const second = render(TuneSheet)
    second.component.show({ tuneId: 202, scope: { session: 'austin/mueller' } })
    await waitFor(() => expect(second.container.querySelector('#history-tab')).toBeTruthy())
    expect(second.container.textContent).toContain('Remove From Session')
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
            session_scope: sessScope({
              instance: 9,
              can_edit_instance: true,
              played_instances: [
                {
                  session_instance_id: 9,
                  date: '2026-01-01',
                  start_time: null,
                  location_override: null,
                  // Played twice that night — two sets, so two links.
                  positions: [
                    { session_instance_tune_id: 501, set_number: 3, position_in_set: 2 },
                    { session_instance_tune_id: 512, set_number: 17, position_in_set: 1 },
                  ],
                },
              ],
            }),
          },
          pts: fullPts({ person_tune_id: 55, name_alias: 'The Banisher' }),
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
    await waitFor(() => expect(container.querySelector('#history-tab')).toBeTruthy())
    // the shim built the scoped feed URL
    expect(fetchMock.mock.calls[0][0]).toContain('/api/tunes/202/detail?session=austin%2Fmueller&instance=2026-01-01')

    // The instance in scope pre-selects, and the droplist row continues the sentence.
    const scopeSel = container.querySelector('#sess-scope-select')
    expect(scopeSel.value).toBe('9')
    expect(scopeSel.options[1].text).toBe('… on Thu 1 Jan 2026')

    // At an instance scope the "history" IS where it came round that night — the same
    // thing at finer granularity, which is the point of the merge. Each links into the
    // logger at that exact record.
    const positions = [...container.querySelectorAll('.history-item a')]
    expect(positions.map((p) => p.textContent.trim())).toEqual(['Set 3, tune 2', 'Set 17, tune 1'])
    expect(positions[0].getAttribute('href')).toBe(
      '/sessions/austin/mueller/9?highlight=501&tune=202'
    )

    // Past tense on the disclosure and the form.
    expect(container.querySelector('.sess-edit-link').textContent).toContain(
      'Update name, setting or key for this tune on this date'
    )
    await fireEvent.click(container.querySelector('.sess-edit-link'))
    expect(container.querySelector('#history-tab').textContent).toContain('We called it:')
    expect(container.querySelector('#sess-alias-input').value).toBe('That Night')

    // The NAME chain: a name is a label, so the most personal one wins — my alias beats
    // the instance's name beats the session's beats the canonical one. And the aka line
    // surfaces the next name down that is meaningfully DIFFERENT (not just respelled).
    expect(container.querySelector('.modal-tune-title').textContent.trim()).toBe('The Banisher')
    expect(container.querySelector('.modal-tune-aka').textContent.trim()).toBe('aka That Night')
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
    const noticeLink = container.querySelector('.tune-merged-notice a')
    expect(noticeLink).toBeTruthy()
    expect(noticeLink.getAttribute('href')).toBe('/sessions/austin/mueller/tunes/200')
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
    await waitFor(() => expect(container.querySelector('.tsc-action-row')).toBeTruthy())
    expect(container.querySelector('.tsc-action-danger').textContent).toContain('Remove From My Tunes')
    // Personal config is collapsed by default; the chained tune's own values seed it.
    await fireEvent.click(container.querySelector('.tsc-action-row .tsc-action-link'))
    expect(container.querySelector('#notes-textarea').value).toBe('chained notes')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
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
    await waitFor(() => expect(container.querySelector('.tsc-action-row')).toBeTruthy())
    expect(container.querySelector('#tune-detail-modal').style.display).toBe('flex')
    expect(container.querySelector('.tsc-action-danger').textContent).toContain('Remove From My Tunes')
    await fireEvent.click(container.querySelector('.tsc-action-row .tsc-action-link'))
    expect(container.querySelector('#notes-textarea').value).toBe('now mine')
    expect(container.querySelector('#name-alias-input')).toBeTruthy()
    expect(new URL(window.location).searchParams.get('ptid')).toBe('77')
    // the tab the user was on survives the upgrade
    expect(container.querySelector('#played-with-tab.active')).toBeTruthy()
    // the History droplist offers the wide lenses (no session in scope here)
    await fireEvent.click(container.querySelector('.modal-tab[data-tab="history"]'))
    await waitFor(() =>
      expect([...container.querySelector('#sess-scope-select').options].map((o) => o.text)).toEqual([
        'All My Sessions',
        'All Sessions',
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
            session_scope: sessScope({ can_edit_session: true }),
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
            session_scope: sessScope({ can_edit_session: true }),
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
    expect(container.querySelector('#sess-scope-select')).toBeTruthy()
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
    tags: ['practice', 'session'],
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
  // Personal config is collapsed by default, so the digest has to open it to see the
  // fields — the offline path must render them identically once expanded.
  const openConfig = async (c) => {
    const link = c.querySelector('.tsc-action-row .tsc-action-link')
    if (link) await fireEvent.click(link)
  }
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
    // The tag chips, in order — the TagInput renders one .kit-chip-body per tag.
    tags: [...c.querySelectorAll('.kit-taginput .kit-chip-body')].map((e) => norm(e.textContent)).join(','),
    nameAlias: c.querySelector('#name-alias-input')?.value,
    settingField: c.querySelector('#setting-input')?.value,
    myKey: c.querySelector('#my-key-select')?.value,
    removeLink: /Remove From My Tunes/.test(c.querySelector('.tsc-action-danger')?.textContent || ''),
    // The whole Stats tab: tunebook count row (incl. "Last Updated"), list count,
    // my-sessions and all-sessions play counts, and the canonical-name line.
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
    await openConfig(online.container)
    const onlineDigest = digest(online.container)
    online.unmount()

    // Sanity-pin the online side first so "both blank" can never pass.
    expect(onlineDigest.removeLink).toBe(true)
    expect(onlineDigest.activeStatus).toBe('want to learn')
    expect(onlineDigest.statusTint).toBe('tunebook-status-want-to-learn')
    expect(onlineDigest.instrumentExpand).toBe('View By Instrument')
    expect(onlineDigest.heard).toBe('2')
    expect(onlineDigest.notation).toBe('EBBA\nB2 EB')
    expect(onlineDigest.notes).toBe('first two bars')
    expect(onlineDigest.tags).toBe('practice,session')
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
    await openConfig(offline.container)
    expect(digest(offline.container)).toEqual(onlineDigest)
  })
})
