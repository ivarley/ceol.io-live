// Tune-detail sheet logic (spec 035 Step 3) — the pure half of the Svelte port of
// the legacy vanilla tune-detail modal (deleted in this step). Everything here is data-in/data-out
// (or window.location/history helpers) so it unit-tests without mounting the
// component. The learn-status resolution rules are NOT re-implemented here: they
// come from mylist.js (the single tested ES copy; static/js/tunebook_status.js is
// its vanilla twin for the remaining non-Svelte pages).
import { listStatus, NOT_ON_LIST } from '../mylist.js'
import { pickAka } from './namematch.js'

// Musical keys list (same order as the legacy modal's key selects)
export const MUSICAL_KEYS = [
  '', 'Amajor', 'Aminor', 'Adorian', 'Amixolydian', 'Bminor', 'Cmajor',
  'Dmajor', 'Dminor', 'Eminor', 'Fmajor', 'Gmajor', 'Dmixolydian',
  'Bmixolydian', 'Edorian', 'Gdorian', 'Gminor', 'Ddorian', 'Cdorian',
  'Fdorian', 'Gmixolydian', 'Emajor', 'Bdorian', 'Emixolydian',
]

// ---- Derived-mode plumbing (the drawer derives its own variant) -----------------

/**
 * Scope implied by the page the drawer opened on: session pages imply their
 * session path, the admin tunes page implies admin. Everything else is global.
 */
export function scopeFromUrl(pathname = window.location.pathname) {
  if (/^\/admin\/tunes(\/\d+)?$/.test(pathname)) return { admin: true }
  const m = pathname.match(/^\/sessions\/(.+)$/)
  if (m) {
    const p = m[1].replace(/\/tunes\/\d+$/, '').replace(/\/(tunes|logs|people)$/, '')
    if (p) return { session: p }
  }
  return null
}

/**
 * Normalize a show() config. New style is { tuneId, ptid?, scope?, ...callbacks };
 * old-style configs (context + apiEndpoint + additionalData — the quarantined
 * pill logger, admin_tunes.html, common_tunes.html) map onto it here so those
 * templates keep working untouched.
 */
export function normalizeShowConfig(raw, pathname = typeof window !== 'undefined' ? window.location.pathname : '/') {
  if (!raw) return raw
  const base = {
    onSave: raw.onSave,
    onStatusChange: raw.onStatusChange,
    expandInstrumentStatus: raw.expandInstrumentStatus,
    initialTab: raw.initialTab,
  }
  if (raw.context !== undefined || raw.apiEndpoint !== undefined) {
    const a = raw.additionalData || {}
    let scope = null
    if (raw.context === 'admin') scope = { admin: true }
    else if (a.sessionPath && !a.global) {
      scope = a.dateOrId ? { session: a.sessionPath, instance: a.dateOrId } : { session: a.sessionPath }
    }
    return {
      ...base,
      tuneId: raw.tuneId ?? null,
      ptid: raw.context === 'my_tunes' ? (a.personTuneId ?? null) : null,
      scope,
      tuneName: a.tuneName,
      tuneType: a.tuneType,
    }
  }
  return {
    ...base,
    tuneId: raw.tuneId ?? null,
    ptid: raw.ptid ?? null,
    scope: raw.scope !== undefined ? raw.scope : scopeFromUrl(pathname),
    tuneName: raw.tuneName,
    tuneType: raw.tuneType,
  }
}

/** THE drawer feed URL for a tune + scope. */
export function detailUrl(tuneId, scope) {
  const q = new URLSearchParams()
  if (scope && scope.session) q.set('session', scope.session)
  if (scope && scope.instance != null) q.set('instance', scope.instance)
  const s = q.toString()
  return `/api/tunes/${tuneId}/detail${s ? `?${s}` : ''}`
}

/**
 * The name chain, most-personal-first (spec 037).
 *
 * A NAME is a label, so the most personal one wins — I want to see a tune by the
 * name I know it under, even when the session I'm looking at calls it something
 * else. (A SETTING is the opposite: it's a record of what was actually played, so
 * the most specific factual layer wins. That precedence lives in the serializer.)
 *
 * `name` is the instance's name_override and `alias` the session's; both are null
 * outside a session scope, so this collapses to [mine, global] on /my-tunes.
 */
export function nameChain(tuneData) {
  if (!tuneData) return []
  const pts = tuneData.person_tune_status
  return [(pts && pts.name_alias) || null, tuneData.name || null, tuneData.alias || null, tuneData.tune_name || null]
}

/** Display name for the header: the first name in the chain that exists. */
export function getDisplayName(tuneData, mode) {
  if (!tuneData) return 'Unknown'
  // Admin mode is untouched by 037 (see spec 036) — it names the canonical tune.
  if (mode === 'admin') return tuneData.tune_name || 'Unknown'
  return nameChain(tuneData).find((n) => n) || 'Unknown'
}

/**
 * The `aka` subtitle: the next name BELOW the title that is meaningfully a different
 * name (not just a different spelling of it). Exactly one, or null. So a tune I call
 * "The Burren" that the world calls "Michael Creamer's" says so, while "Silver Spear"
 * never earns "aka The Silver Spear".
 */
export function getAkaName(tuneData, mode) {
  if (!tuneData || mode === 'admin') return null
  return pickAka(nameChain(tuneData))
}

// --- The Session tab (spec 037) -------------------------------------------------

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** "Tue 8 Jul 2026" — parsed as local, not UTC, so the date never slips a day. */
function formatInstanceDate(iso) {
  const [y, m, d] = String(iso || '').split('-').map(Number)
  if (!y || !m || !d) return String(iso || '')
  const dt = new Date(y, m - 1, d)
  return `${DAYS[dt.getDay()]} ${d} ${MONTHS[m - 1]} ${y}`
}

/** "2:00pm" from a "14:00:00" time. */
function formatInstanceTime(t) {
  if (!t) return ''
  const [hRaw, min] = String(t).split(':')
  const h = Number(hRaw)
  if (Number.isNaN(h)) return ''
  const suffix = h < 12 ? 'am' : 'pm'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}:${min || '00'}${suffix}`
}

/** The droplist row that re-scopes the drawer to one of my other sessions. */
export const OTHER_SESSION = '__other__'

/**
 * The History tab's droplist — the ONE scope control (spec 037). It replaced the History
 * tab's Seg and the Session tab's separate droplist, because after the merge they were
 * asking the same question: *which plays of this tune am I looking at?*
 *
 *   At The Cobblestone            <- the session's own row; editable
 *   … on Tue 8 Jul 2026           <- one instance; editable
 *   … on Sat 14 Feb · Gus O'Connor's
 *   At a different session …      <- an errand, not a target
 *   All My Sessions               <- read-only lens
 *   All Sessions
 *
 * It reads as one sentence continued down the list. The session rows appear only when a
 * session is in scope; the wide lenses always do. Only the session rows are EDITABLE —
 * "what we call it" is a fact about a session or a performance, and means nothing across
 * all of them.
 *
 * Labelling an instance: the date, plus location_override when set — that's what tells
 * two same-date instances apart at a festival, and how the session's Logs tab already
 * labels them. start_time is appended ONLY to break a remaining tie, so the ordinary
 * weekly session stays clean.
 */
export function historyScopeOptions(playedInstances, sessionName, { inSession = false, loggedIn = false } = {}) {
  const options = []

  if (inSession) {
    options.push({ id: 'general', label: `At ${sessionName || 'this session'}`, editable: true })

    const instances = playedInstances || []
    // Which labels would still collide once the date and venue are shown?
    const counts = {}
    for (const i of instances) {
      const k = `${i.date}|${i.location_override || ''}`
      counts[k] = (counts[k] || 0) + 1
    }
    for (const i of instances) {
      const parts = [formatInstanceDate(i.date)]
      if (i.location_override) parts.push(i.location_override)
      if (counts[`${i.date}|${i.location_override || ''}`] > 1) {
        const t = formatInstanceTime(i.start_time)
        if (t) parts.push(t)
      }
      options.push({
        id: String(i.session_instance_id),
        label: `… on ${parts.join(' · ')}`,
        editable: true,
      })
    }

    options.push({ id: OTHER_SESSION, label: 'At a different session …', editable: false })
  }

  if (loggedIn) options.push({ id: 'member', label: 'All My Sessions', editable: false })
  options.push({ id: 'all', label: 'All Sessions', editable: false })
  return options
}

/** Is this droplist row one you can edit? Only a session's own row, or one instance. */
export function isEditableScope(id) {
  return id === 'general' || /^\d+$/.test(String(id))
}

/** The history request for a droplist row + the "while I was there" filter. */
export function historyUrl(tuneId, scopeId, sessionPath, attendedOnly) {
  const q = new URLSearchParams()
  if (scopeId === 'general' && sessionPath) q.set('session_path', sessionPath)
  else if (scopeId === 'member') q.set('scope', 'member')
  if (attendedOnly) q.set('attended', '1')
  const s = q.toString()
  return `/api/tunes/${tuneId}/history${s ? `?${s}` : ''}`
}

/**
 * "Set 3, tune 2" — where this tune came round on a given night. Usually one entry;
 * a tune played twice that night has two. Each links into the logger at that exact
 * record via the same ?highlight=<session_instance_tune_id> deep link the History tab
 * uses (the legacy /sessions/<path>/<instance> URL redirects beta users to the live
 * screen, and deliberately drops ?tune=, which there would mean "append this tune").
 */
export function instancePositions(playedInstances, instanceId, sessionPath, tuneId) {
  const inst = (playedInstances || []).find((i) => String(i.session_instance_id) === String(instanceId))
  if (!inst) return []
  return (inst.positions || []).map((p) => ({
    label: `Set ${p.set_number}, tune ${p.position_in_set}`,
    href: `/sessions/${sessionPath}/${inst.session_instance_id}?highlight=${p.session_instance_tune_id}&tune=${tuneId}`,
  }))
}

/**
 * Which droplist option to land on. The instance in scope when the drawer was opened
 * from the live logger; else ?siid=; else ?date= (earliest instance that day, since a
 * festival can run several on one date); else "In General".
 */
export function initialSessionScope(playedInstances, scopeInstanceId, search = '') {
  const instances = playedInstances || []
  const has = (id) => instances.some((i) => String(i.session_instance_id) === String(id))

  if (scopeInstanceId != null && has(scopeInstanceId)) return String(scopeInstanceId)

  const params = new URLSearchParams(search || '')
  const siid = params.get('siid')
  if (siid && has(siid)) return String(siid)

  const date = params.get('date')
  if (date) {
    const onDate = instances
      .filter((i) => i.date === date)
      .sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')))
    if (onDate.length) return String(onDate[0].session_instance_id)
  }
  return 'general'
}

/** Meter (time signature) for a tune type — used in the abctools ABC header. */
export function getMeterForTuneType(tuneType) {
  const meterMap = {
    polka: '2/4',
    barndance: '4/4',
    hornpipe: '4/4',
    waltz: '3/4',
    reel: '4/4',
    'hop jig': '9/8',
    jig: '6/8',
    'set dance': '6/8',
    march: '4/4',
    mazurka: '3/4',
    slide: '12/8',
  }
  return meterMap[(tuneType || '').toLowerCase()] || ''
}

/** Extract a setting ID from a bare number or a thesession.org URL; null if none. */
export function extractSettingId(input) {
  if (!input || input.trim() === '') return null
  const trimmed = input.trim()
  if (/^\d+$/.test(trimmed)) return parseInt(trimmed)
  const queryMatch = trimmed.match(/[?&]setting=(\d+)/)
  if (queryMatch) return parseInt(queryMatch[1])
  const hashMatch = trimmed.match(/#setting(\d+)/)
  if (hashMatch) return parseInt(hashMatch[1])
  return null
}

/**
 * Validate a setting input (number or thesession.org URL). A URL whose tune id
 * doesn't match the current tune is silently discarded (valid, settingId null).
 */
export function validateSettingInput(input, expectedTuneId) {
  if (!input) return { valid: true, settingId: null }
  if (/^\d+$/.test(input)) return { valid: true, settingId: parseInt(input) }
  if (input.includes('thesession.org')) {
    const settingId = extractSettingId(input)
    if (settingId === null) {
      return { valid: false, error: 'Could not extract setting ID from URL' }
    }
    const tuneIdMatch = input.match(/thesession\.org\/tunes\/(\d+)/)
    if (tuneIdMatch) {
      const urlTuneId = parseInt(tuneIdMatch[1])
      if (urlTuneId !== expectedTuneId) {
        return { valid: true, settingId: null } // wrong tune — silently discard
      }
    }
    return { valid: true, settingId: settingId }
  }
  return { valid: false, error: 'Please enter a number or paste a valid TheSession.org URL' }
}

/** Played With scopes for the derived mode; first entry is the default.
 *  (History's Seg is gone — its scopes became the merged droplist above. Played With
 *  keeps its own: coupling it to the History scope would be over-fitting.) */
export function playedWithScopeOptions(mode, scope, loggedIn = false) {
  const mine = loggedIn
    ? [
        { key: 'member', label: 'At My Sessions' },
        { key: 'attended', label: 'While I Was There' },
      ]
    : []
  if ((mode === 'session' || mode === 'session_instance') && scope && scope.session) {
    return [{ key: 'session', label: 'At This Session' }, ...mine, { key: 'all', label: 'Globally' }]
  }
  if (mode === 'my_tunes') {
    return [...mine, { key: 'all', label: 'Globally' }]
  }
  return [{ key: 'all', label: 'Globally' }, ...mine]
}

// --- URL param management (identical to the legacy modal) ------------------------

export function updateUrlWithTune(tuneId, context) {
  const pathname = window.location.pathname
  if (pathname.includes('/sessions/') && !pathname.includes('/my-tunes')) {
    // Session context: path-based URL
    let basePath = pathname.replace(/\/tunes\/\d+$/, '')
    if (!basePath.endsWith('/tunes')) {
      basePath = basePath.replace(/\/(logs|people)$/, '') + '/tunes'
    }
    window.history.replaceState({}, '', `${basePath}/${tuneId}`)
  } else if (pathname.match(/^\/admin\/tunes(\/\d+)?$/)) {
    window.history.replaceState({}, '', `/admin/tunes/${tuneId}`)
  } else {
    const url = new URL(window.location)
    const paramName = context === 'my_tunes' ? 'ptid' : 'tune'
    url.searchParams.set(paramName, tuneId)
    // In-drawer chaining can hop between contexts (my_tunes <-> global view);
    // drop the other context's param so a stale one never lingers in the URL.
    url.searchParams.delete(context === 'my_tunes' ? 'tune' : 'ptid')
    window.history.replaceState({}, '', url)
  }
}

export function removeUrlTuneParam(context) {
  const pathname = window.location.pathname
  if (pathname.includes('/sessions/') && !pathname.includes('/my-tunes')) {
    window.history.replaceState({}, '', pathname.replace(/\/tunes\/\d+$/, '/tunes'))
  } else if (pathname.match(/^\/admin\/tunes\/\d+$/)) {
    window.history.replaceState({}, '', '/admin/tunes')
  } else {
    const url = new URL(window.location)
    // Clear both drawer params: a chained drawer may have visited both contexts.
    url.searchParams.delete('ptid')
    url.searchParams.delete('tune')
    window.history.replaceState({}, '', url)
  }
}

/** Tune (or person_tune) id from the current URL, exactly as the legacy modal. */
export function getTuneIdFromUrl() {
  const pathname = window.location.pathname
  if (pathname.includes('/sessions/') && !pathname.includes('/my-tunes')) {
    const match = pathname.match(/\/tunes\/(\d+)$/)
    if (match) return parseInt(match[1], 10)
  }
  const adminTunesMatch = pathname.match(/^\/admin\/tunes\/(\d+)$/)
  if (adminTunesMatch) return parseInt(adminTunesMatch[1], 10)
  const urlParams = new URLSearchParams(window.location.search)
  const paramName = pathname.includes('/my-tunes') ? 'ptid' : 'tune'
  const tuneParam = urlParams.get(paramName)
  return tuneParam ? parseInt(tuneParam, 10) : null
}

// --- Per-instrument status plumbing --------------------------------------------
// The consolidated detail payload always nests person data under
// person_tune_status, so the old per-context branching is gone.

export function getInstrumentData(tuneData) {
  const s = (tuneData && tuneData.person_tune_status) || {}
  return { instruments: s.instruments || [], overrides: s.instrument_status || {} }
}

export function getModalLearnStatus(tuneData) {
  return (tuneData && tuneData.person_tune_status && tuneData.person_tune_status.learn_status) || 'want to learn'
}

export function setInstrumentOverrides(tuneData, overrides) {
  if (tuneData && tuneData.person_tune_status) {
    tuneData.person_tune_status.instrument_status = overrides
  }
}

// One instrument's resolved status (override wins; auto follows learn_status;
// manual without a row is untracked = null). Delegates to mylist.js — the
// per-instrument blocks only render at 2+ instruments, where listStatus's
// instrument scoping applies.
export function resolveInstStatus(tuneData, inst) {
  const { instruments, overrides } = getInstrumentData(tuneData)
  const st = listStatus(
    { learn_status: getModalLearnStatus(tuneData), instrument_status: overrides || {} },
    instruments,
    inst.instrument
  )
  return st === NOT_ON_LIST ? null : st
}

// The tune's overall status = the roll-up: furthest-along status across all
// instruments that have one (auto follow learn_status; manual only when tracked).
export function rollupStatus(tuneData) {
  const { instruments, overrides } = getInstrumentData(tuneData)
  return listStatus(
    { learn_status: getModalLearnStatus(tuneData), instrument_status: overrides || {} },
    instruments,
    'all'
  )
}

// --- Offline fallback -------------------------------------------------------------

/**
 * Overlay not-yet-synced My-Tunes ops onto a cached offline tune copy so the
 * drawer reflects offline edits. Returns a new object; does not mutate `tune`.
 */
export function overlayOfflineOps(tune, ops, tuneId) {
  const t = Object.assign({}, tune)
  // Popular-catalog tunes carry only `name`; the renderer reads `tune_name`.
  if (!t.tune_name && t.name) t.tune_name = t.name
  ;(ops || [])
    .filter((o) => Number(o.tune_id) === Number(tuneId))
    .sort((a, b) => a.ts - b.ts)
    .forEach((o) => {
      if (o.type === 'set_status') t.learn_status = o.learn_status
      else if (o.type === 'set_heard') t.heard_count = o.heard_count
      else if (o.type === 'set_notes') t.notes = o.notes
      else if (o.type === 'add' && !t.learn_status) t.learn_status = o.learn_status || 'want to learn'
    })
  return t
}

/**
 * Synthesize the drawer payload from an offline bundle tune + queued ops so the
 * derived-mode rendering works without the API: a cached bundle implies an
 * authenticated sync (logged_in true), and on-list = the overlaid tune carries
 * a learn_status (bundle "my tunes" entries and queued adds do; popular-catalog
 * entries don't, which renders the Add view exactly as online).
 */
export function offlinePayload(cachedTune, ops, tuneId) {
  const t = overlayOfflineOps(cachedTune, ops, tuneId)
  const onList = !!t.learn_status
  return {
    success: true,
    viewer: { logged_in: true, is_admin: false },
    session_tune: {
      tune_id: t.tune_id != null ? t.tune_id : tuneId,
      tune_name: t.tune_name || t.name,
      tune_type: t.tune_type,
      alias: null,
      aliases: [],
      key: null,
      name: null,
      key_override: null,
      setting_override: null,
      setting_id: t.setting_id || null,
      setting_key: t.setting_key || null,
      abc: t.abc || null,
      incipit_abc: t.incipit_abc || null,
      image: t.image || null,
      incipit_image: t.incipit_image || null,
      tunebook_count: t.tunebook_count || 0,
      tunebook_count_cached_date: t.tunebook_count_cached_date || null,
      times_played: 0,
      global_play_count: t.global_play_count,
      person_list_count: t.person_list_count != null ? t.person_list_count : null,
      session_count: null,
      session_scope: null,
      person_tune_status: onList
        ? {
            on_list: true,
            person_tune_id: t.person_tune_id != null ? t.person_tune_id : null,
            learn_status: t.learn_status,
            heard_count: t.heard_count || 0,
            learned_date: t.learned_date || null,
            notes: t.notes || null,
            name_alias: t.name_alias || null,
            setting_id: t.setting_id || null,
            key: t.key || null,
            instruments: t.instruments || [],
            instrument_status: t.instrument_status || {},
            session_play_count: t.session_play_count,
            member_play_count: t.member_play_count,
            attended_play_count: t.attended_play_count,
          }
        : {
            on_list: false,
            person_tune_id: null,
            learn_status: null,
            heard_count: null,
            instruments: [],
            instrument_status: {},
          },
    },
  }
}

/**
 * Synthesize the drawer payload from a GET /api/my-tunes/<ptid> response — the
 * ptid-only deep-link resolution path (a ?ptid URL whose tune the host page
 * couldn't map to a tune_id; the endpoint's 404 is the merged-away signal).
 */
export function personTunePayload(pt) {
  return {
    success: true,
    viewer: { logged_in: true, is_admin: false },
    session_tune: {
      tune_id: pt.tune_id,
      tune_name: pt.tune_name,
      tune_type: pt.tune_type,
      alias: null,
      aliases: [],
      key: null,
      name: null,
      key_override: null,
      setting_override: null,
      setting_id: pt.setting_id || null,
      setting_key: pt.setting_key || null,
      abc: pt.abc || null,
      incipit_abc: pt.incipit_abc || null,
      image: pt.image || null,
      incipit_image: pt.incipit_image || null,
      tunebook_count: pt.tunebook_count,
      tunebook_count_cached_date: pt.tunebook_count_cached_date || null,
      times_played: 0,
      global_play_count: pt.global_play_count,
      person_list_count: pt.person_list_count != null ? pt.person_list_count : null,
      session_count: null,
      session_scope: null,
      person_tune_status: {
        ...pt,
        on_list: true,
        instruments: pt.instruments || [],
        instrument_status: pt.instrument_status || {},
      },
    },
  }
}

// --- External links ---------------------------------------------------------------

/** thesession.org tune URL, with a #setting anchor when a setting is chosen. */
export function theSessionUrl(tuneData) {
  if (!tuneData.tune_id) return ''
  const baseUrl = `https://thesession.org/tunes/${tuneData.tune_id}`
  const settingId = tuneData.setting_id || tuneData.setting_override
  return settingId ? `${baseUrl}#setting${settingId}` : baseUrl
}

/**
 * michaeleskin.com abctools URL for the tune's ABC (LZ-compressed). Returns ''
 * when there is no ABC or window.LZString isn't loaded.
 */
export function abcToolsUrl(tuneData) {
  const abc = tuneData.abc || tuneData.incipit_abc
  if (!abc) return ''
  const LZString = typeof window !== 'undefined' ? window.LZString : undefined
  if (!LZString) return ''
  const abcBody = abc.replace(/!/g, '\n')
  const tuneName = tuneData.tune_name || tuneData.name || tuneData.name_alias || tuneData.alias || 'Tune'
  const tuneType = tuneData.tune_type || ''
  const tuneKey = tuneData.setting_key || tuneData.key || tuneData.key_override || ''
  const meter = getMeterForTuneType(tuneType)
  const formattedAbc = `X: 1
T: ${tuneName}
R: ${tuneType}${meter ? `\nM: ${meter}` : ''}
L: 1/8
K: ${tuneKey}
${abcBody}`
  const compressed = LZString.compressToEncodedURIComponent(formattedAbc)
  return `https://michaeleskin.com/abctools/abctools.html?lzw=${compressed}&format=noten&ssp=45&name=${encodeURIComponent(tuneName)}&play=1`
}

// --- ABC notation display state machine --------------------------------------------

/** What the notation section can show for this tune. */
export function notationInfo(tuneData) {
  const hasDots = !!(tuneData.incipit_image || tuneData.image)
  const hasAbc = !!(tuneData.incipit_abc || tuneData.abc)
  return {
    hasDots,
    hasAbc,
    hasAny: hasDots || hasAbc,
    initialMode: hasDots ? 'dots' : 'abc',
    canToggleSize: !!((tuneData.incipit_image && tuneData.image) || (tuneData.incipit_abc && tuneData.abc)),
  }
}

/**
 * Resolve what to display for (mode, size), with the legacy fallback chain
 * (requested size, else incipit, else full). Returns
 * {kind:'img'|'pre', size:'incipit'|'full', src?|text?} or null.
 */
export function notationDisplay(tuneData, mode, size) {
  if (mode === 'dots') {
    if (size === 'incipit' && tuneData.incipit_image) return { kind: 'img', size: 'incipit', src: tuneData.incipit_image }
    if (size === 'full' && tuneData.image) return { kind: 'img', size: 'full', src: tuneData.image }
    if (tuneData.incipit_image) return { kind: 'img', size: 'incipit', src: tuneData.incipit_image }
    if (tuneData.image) return { kind: 'img', size: 'full', src: tuneData.image }
    return null
  }
  if (size === 'incipit' && tuneData.incipit_abc) return { kind: 'pre', size: 'incipit', text: tuneData.incipit_abc.replace(/!/g, '\n') }
  if (size === 'full' && tuneData.abc) return { kind: 'pre', size: 'full', text: tuneData.abc.replace(/!/g, '\n') }
  if (tuneData.incipit_abc) return { kind: 'pre', size: 'incipit', text: tuneData.incipit_abc.replace(/!/g, '\n') }
  if (tuneData.abc) return { kind: 'pre', size: 'full', text: tuneData.abc.replace(/!/g, '\n') }
  return null
}

// --- Op submission ------------------------------------------------------------------

/**
 * Submit a My-Tunes op through the offline queue if present (queues when offline),
 * else POST it straight to the idempotent ops endpoint. Resolves on success OR
 * offline-queue; rejects only when the server rejects the op (caller reverts).
 */
export function submitMyTunesOp(op) {
  if (window.MyTunesOffline) return window.MyTunesOffline.submit(op)
  return fetch('/api/my-tunes/ops', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(op),
  })
    .then((r) => r.json())
    .then((d) => {
      if (!d.success) throw new Error(d.error || 'op failed')
      return { online: true, data: d }
    })
}
