// Testable logic for the session-detail page (spec 035 Step 4b) — ported
// behavior-for-behavior from the legacy inline script in templates/session_detail.html.
// Tune rows are the serializer dicts ({tune_id, tune_name, tune_type, play_count,
// tunebook_count, setting_id}) — the legacy tuple format is dead.

// extractTuneId ("search" also matches a bare thesession.org tune id or URL),
// normalizeQuotes, formatTime/formatTimeRange and instanceTimeLabel now live in
// src/shared/ — one tested copy for every page bundle.
import { extractTuneId, parseLocalDate } from '../shared/parse.js'

// Sort functions keyed by type (alpha, session, everywhere) and direction.
export const sortFunctions = {
  alpha: {
    asc: (a, b) => (a.tune_name || '').localeCompare(b.tune_name || ''),
    desc: (a, b) => (b.tune_name || '').localeCompare(a.tune_name || ''),
  },
  session: {
    asc: (a, b) => (a.play_count || 0) - (b.play_count || 0),
    desc: (a, b) => (b.play_count || 0) - (a.play_count || 0),
  },
  everywhere: {
    asc: (a, b) => (a.tunebook_count || 0) - (b.tunebook_count || 0),
    desc: (a, b) => (b.tunebook_count || 0) - (a.tunebook_count || 0),
  },
}

// The "My Tunebook" filter's droplist values (legacy #mystatus-filter options).
export const MYSTATUS_OPTIONS = ['', 'all', 'not on list', 'want to learn', 'learning', 'learned']

// Filter + sort the repertoire. `filters.search` is lowercased/trimmed; the name
// match is accent-insensitive via the app-wide AccentUtils when present. The
// my-tunebook filter reads window.TunebookStatus ('all' colors without filtering).
// filters.attended keeps only tunes played on nights the viewer checked in to
// (spec 033 R4 — attended_play_count comes from the serializer, logged-in only).
export function filterAndSortTunes(allTunes, filters, sort, myStatusInstrument) {
  const tb = typeof window !== 'undefined' ? window.TunebookStatus : null
  const accent = typeof window !== 'undefined' ? window.AccentUtils : null
  const filtered = allTunes.filter((tune) => {
    if (filters.search) {
      const searchTuneId = extractTuneId(filters.search)
      const tuneName = tune.tune_name || ''
      const nameMatch = accent
        ? accent.includes(tuneName, filters.search)
        : tuneName.toLowerCase().includes(filters.search)
      const tuneIdMatch = searchTuneId && tune.tune_id === searchTuneId
      if (!nameMatch && !tuneIdMatch) return false
    }
    if (filters.type && tune.tune_type !== filters.type) return false
    if (filters.attended && !(tune.attended_play_count > 0)) return false
    if (
      filters.mystatus &&
      filters.mystatus !== 'all' &&
      tb &&
      tb.isLoaded() &&
      tb.statusFor(tune.tune_id, myStatusInstrument) !== filters.mystatus
    ) {
      return false
    }
    return true
  })
  const sortFn = sortFunctions[sort.type]?.[sort.dir]
  if (sortFn) filtered.sort(sortFn)
  return filtered
}

export function resultsCountLabel(filteredCount, totalCount) {
  if (filteredCount < totalCount) return `Showing ${filteredCount} of ${totalCount} tunes`
  return `${totalCount} tune${totalCount !== 1 ? 's' : ''}`
}

// ---- URL <-> state (the tunes tab's query-string contract) ---------------------

// Legacy loadStateFromURL: read search/type/mystatus/myinst/sortType/sortDir.
// mystatus applies only when logged in (the control doesn't exist otherwise).
export function stateFromParams(params, isLoggedIn) {
  const state = {
    filters: { search: '', type: '', mystatus: '', attended: false },
    rawSearch: '',
    myStatusInstrument: 'all',
    sort: { type: 'session', dir: 'desc' },
  }
  const searchParam = params.get('search')
  if (searchParam) {
    state.filters.search = searchParam.toLowerCase().trim()
    state.rawSearch = searchParam
  }
  const typeParam = params.get('type')
  if (typeParam) state.filters.type = typeParam
  const myStatusParam = params.get('mystatus')
  if (myStatusParam && isLoggedIn && MYSTATUS_OPTIONS.includes(myStatusParam)) {
    state.filters.mystatus = myStatusParam
    const instParam = params.get('myinst')
    if (instParam) state.myStatusInstrument = instParam // validated once instruments load
  }
  if (params.get('attended') === '1' && isLoggedIn) state.filters.attended = true
  if (params.has('sortType')) state.sort.type = params.get('sortType')
  if (params.has('sortDir')) state.sort.dir = params.get('sortDir')
  return state
}

// Legacy updateURL: write our keys into the current params (preserving everything
// else, e.g. ?tune / ?show); sort params appear only off the session-desc default.
export function applyStateToParams(params, filters, sort, myStatusInstrument) {
  if (filters.search) params.set('search', filters.search)
  else params.delete('search')
  if (filters.type) params.set('type', filters.type)
  else params.delete('type')
  if (filters.mystatus) params.set('mystatus', filters.mystatus)
  else params.delete('mystatus')
  if (filters.mystatus && myStatusInstrument !== 'all') params.set('myinst', myStatusInstrument)
  else params.delete('myinst')
  if (filters.attended) params.set('attended', '1')
  else params.delete('attended')
  if (sort.type !== 'session' || sort.dir !== 'desc') {
    params.set('sortType', sort.type)
    params.set('sortDir', sort.dir)
  } else {
    params.delete('sortType')
    params.delete('sortDir')
  }
  return params
}

// Base session path for tab navigation: strip any tab suffix and a deep-linked
// tune/person id, so switching tabs never carries ids along.
export function basePathOf(pathname) {
  return pathname.replace(/\/(tunes|people|logs)(\/\d+)?$/, '').replace(/\/$/, '')
}

// ---- logs tab -------------------------------------------------------------------

// Moved to src/shared/format.js so the live logger's header can label its own
// times with the identical string the Logs tab shows. Re-exported here because
// LogsTab and this module's tests import it from logic.js.
export { instanceTimeLabel } from '../shared/format.js'

// Faint "(N tunes logged)" suffix; empty when nothing has been logged.
export function tuneCountOf(instance) {
  return instance.tune_count || 0
}

// An instance with no tunes logged renders its link dimmed (class empty-log).
export function isEmptyLog(instance) {
  return (instance.tune_count || 0) === 0
}

// Date-based URL normally; instance-id URL when several instances share a date.
export function instanceUrlId(instance) {
  return instance.multiple_on_date ? instance.session_instance_id : instance.date
}

// The Logs tab's view toggle. "logged" is the default: an instance with nothing
// logged is a placeholder for a night, not a log, and a long-running session
// accumulates far more of those than real logs.
export const LOG_VIEW_OPTIONS = [
  { id: 'logged', label: 'Logged' },
  { id: 'all', label: 'All' },
]

// One instance's fate under the two filters. A tune filter SUPERSEDES the
// all/logged toggle rather than ANDing with it — every instance where a tune was
// played is by definition a logged one, so ANDing could only ever surprise.
export function keepInstance(instance, mode, tuneInstanceIds) {
  if (tuneInstanceIds) return tuneInstanceIds.has(instance.session_instance_id)
  if (mode === 'logged') return !isEmptyLog(instance)
  return true
}

// Filter the year (or festival-day) groups, dropping any section left empty so
// the toggle doesn't leave behind headers with nothing under them.
export function filterInstanceGroups(sortedKeys, groups, mode, tuneInstanceIds) {
  const byKey = {}
  const keys = []
  let total = 0
  for (const key of sortedKeys || []) {
    const kept = (groups[key] || []).filter((i) => keepInstance(i, mode, tuneInstanceIds))
    if (kept.length > 0) {
      byKey[key] = kept
      keys.push(key)
      total += kept.length
    }
  }
  return { sortedKeys: keys, byKey, total }
}

// The <ul> under a filtered date: every time the chosen tune came round that
// night, linked at the exact record. Same deep link the tune drawer's History tab
// uses (?highlight=<session_instance_tune_id>, with ?tune= for the legacy page),
// and the same "Set 3, tune 2" coordinates — one vocabulary for one idea.
export function tunePlayLinks(playsByInstance, instance, sessionPath, tuneId) {
  const positions = playsByInstance ? playsByInstance.get(instance.session_instance_id) : null
  return (positions || []).map((p) => ({
    key: p.session_instance_tune_id,
    name: p.name,
    where: `set ${p.set_number}, tune ${p.position_in_set}`,
    href:
      `/sessions/${sessionPath}/${instance.session_instance_id}` +
      `?highlight=${p.session_instance_tune_id}&tune=${tuneId}`,
  }))
}

// Autocomplete matches for the tune filter box. Accent-insensitive via the
// app-wide AccentUtils when present (same rule as the Tunes tab search);
// prefix matches lead, then the tunes played most often here.
export function matchLoggedTunes(tunes, query, limit = 8) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return []
  const accent = typeof window !== 'undefined' ? window.AccentUtils : null
  const matches = (tunes || []).filter((t) =>
    accent ? accent.includes(t.name || '', q) : (t.name || '').toLowerCase().includes(q)
  )
  matches.sort((a, b) => {
    const ap = (a.name || '').toLowerCase().startsWith(q) ? 0 : 1
    const bp = (b.name || '').toLowerCase().startsWith(q) ? 0 : 1
    if (ap !== bp) return ap - bp
    if ((b.log_count || 0) !== (a.log_count || 0)) return (b.log_count || 0) - (a.log_count || 0)
    return (a.name || '').localeCompare(b.name || '')
  })
  return matches.slice(0, limit)
}

// Festival day header, e.g. "Sunday, June 1, 2025". Parsed as a LOCAL date —
// the legacy new Date("YYYY-MM-DD") semantics rendered the previous day west
// of UTC (same bug class as the admin logs tab).
export function festivalDayLabel(dateStr) {
  const dateObj = parseLocalDate(dateStr)
  return dateObj.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

// ---- people tab -------------------------------------------------------------------

// Accept a bare numeric id or a thesession.org members/sessions URL.
export function parseTheSessionId(input) {
  if (!input || input.trim() === '') return null
  input = input.trim()
  if (/^\d+$/.test(input)) {
    return parseInt(input)
  }
  const urlMatch = input.match(/thesession\.org\/(members|sessions)\/(\d+)/)
  if (urlMatch) {
    return parseInt(urlMatch[2])
  }
  return null
}

/**
 * People-tab filter (spec 034): members / visitors / archived, plus free-text search over
 * "First Last" and the instruments list.
 *
 * The old All/Regulars toggle died with is_regular. Note the axes are NOT parallel:
 * archived is orthogonal to member/visitor (you can archive either), so the members and
 * visitors views both exclude archived people, and "archived" is its own view that shows
 * them regardless of relationship. Otherwise someone archived would simply vanish.
 *
 * Search always wins over the archived rule: a search that matched nothing because the
 * person was archived is exactly how duplicate people get created.
 */
export function filterPeople(peopleData, currentFilter, searchQuery) {
  let filtered = peopleData

  if (currentFilter === 'archived') {
    filtered = filtered.filter((person) => person.archived)
  } else if (currentFilter === 'visitors') {
    filtered = filtered.filter((person) => person.relationship === 'visitor' && !person.archived)
  } else {
    filtered = filtered.filter((person) => person.relationship !== 'visitor' && !person.archived)
  }

  if (searchQuery) {
    // Search the WHOLE roster, archived included — hidden must never mean unfindable.
    filtered = peopleData.filter((person) => {
      const fullName = `${person.first_name} ${person.last_name}`.toLowerCase()
      const instruments = person.instruments ? person.instruments.join(' ').toLowerCase() : ''
      return fullName.includes(searchQuery) || instruments.includes(searchQuery)
    })
  }
  return filtered
}
