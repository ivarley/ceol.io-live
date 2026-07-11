// Testable logic for the session-detail page (spec 035 Step 4b) — ported
// behavior-for-behavior from the legacy inline script in templates/session_detail.html.
// Tune rows are the serializer dicts ({tune_id, tune_name, tune_type, play_count,
// tunebook_count, setting_id}) — the legacy tuple format is dead.

// "Search" also matches a bare thesession.org tune id or tune URL.
export function extractTuneId(input) {
  if (!input) return null
  const trimmed = input.trim()
  if (/^\d+$/.test(trimmed)) {
    return parseInt(trimmed)
  }
  const urlMatch = trimmed.match(/thesession\.org\/tunes\/(\d+)/i)
  if (urlMatch) {
    return parseInt(urlMatch[1])
  }
  return null
}

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
    filters: { search: '', type: '', mystatus: '' },
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

export function formatTime(timeStr) {
  if (!timeStr) return ''
  const parts = timeStr.split(':')
  let hour = parseInt(parts[0])
  const minute = parts[1]
  const period = hour >= 12 ? 'pm' : 'am'
  hour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour
  return `${hour}:${minute}${period}`
}

export function formatTimeRange(startTime, endTime) {
  return formatTime(startTime) + '-' + formatTime(endTime)
}

export function instanceTimeLabel(instance) {
  if (instance.start_time && instance.end_time) {
    return formatTimeRange(instance.start_time, instance.end_time)
  }
  if (instance.start_time) return formatTime(instance.start_time) + ' - ?'
  return ''
}

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

// Festival day header, e.g. "Sunday, June 1, 2025" (legacy new Date(...) semantics).
export function festivalDayLabel(dateStr) {
  const dateObj = new Date(dateStr)
  return dateObj.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

// ---- people tab -------------------------------------------------------------------

// Normalize smart quotes to straight quotes (iOS keyboard compatibility).
export function normalizeQuotes(str) {
  return str
    .replace(/[‘’]/g, "'") // Smart single quotes → straight
    .replace(/[“”]/g, '"') // Smart double quotes → straight
}

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

// Regulars/all + free-text search over "First Last" and the instruments list.
export function filterPeople(peopleData, currentFilter, searchQuery) {
  let filtered = peopleData
  if (currentFilter === 'regulars') {
    filtered = filtered.filter((person) => person.is_regular)
  }
  if (searchQuery) {
    filtered = filtered.filter((person) => {
      const fullName = `${person.first_name} ${person.last_name}`.toLowerCase()
      const instruments = person.instruments ? person.instruments.join(' ').toLowerCase() : ''
      return fullName.includes(searchQuery) || instruments.includes(searchQuery)
    })
  }
  return filtered
}
