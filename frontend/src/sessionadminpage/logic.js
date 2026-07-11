// Pure helpers for the session-admin page view (spec 035 Step 5b), ported
// verbatim from the legacy inline script in templates/session_admin.html.

// normalizeQuotes / extractTuneId now come from the shared helpers module
// (src/shared/) — one tested copy for every page bundle. formatTime (the
// recurrence preview's "19:00" -> "7:00pm") lives in src/shared/format.js.
import { normalizeQuotes, extractTuneId } from '../shared/parse.js'

// Generic asc/desc comparator used by the people and tunes tables.
export function compareValues(aValue, bValue, direction) {
  if (aValue < bValue) return direction === 'asc' ? -1 : 1
  if (aValue > bValue) return direction === 'asc' ? 1 : -1
  return 0
}

// People-table sort key per column (legacy filterPeople switch).
export function personSortValue(person, column) {
  switch (column) {
    case 'name':
      return person.name.toLowerCase()
    case 'email':
      return (person.email || '').toLowerCase()
    case 'attendance':
      return person.attendance_count || 0
    case 'last_attended':
      return person.last_attended ? new Date(person.last_attended).getTime() : 0
    default:
      return 0
  }
}

// Tunes-table sort key per column (legacy filterTunes switch).
export function tuneSortValue(tune, column) {
  switch (column) {
    case 'tune_name':
      return tune.tune_name.toLowerCase()
    case 'session_alias':
      return (tune.session_alias || '').toLowerCase()
    case 'tune_type':
      return (tune.tune_type || '').toLowerCase()
    case 'session_key':
      return (tune.session_key || '').toLowerCase()
    case 'setting_key':
      return (tune.setting_key || '').toLowerCase()
    case 'play_count':
      return tune.play_count || 0
    case 'want_to_learn':
      return tune.want_to_learn_count || 0
    case 'learning':
      return tune.learning_count || 0
    case 'learned':
      return tune.learned_count || 0
    default:
      return 0
  }
}

// Legacy tune search: free text over name/alias/type/keys, OR an exact tune-id
// match when the query looks like an id or thesession URL.
export function filterTuneList(tunes, rawQuery) {
  const search = normalizeQuotes(rawQuery.toLowerCase())
  if (!search) return tunes
  const searchTuneId = extractTuneId(rawQuery)
  return tunes.filter((tune) => {
    const tuneIdMatch = searchTuneId && tune.tune_id === searchTuneId
    const textMatch =
      tune.tune_name.toLowerCase().includes(search) ||
      (tune.session_alias || '').toLowerCase().includes(search) ||
      (tune.tune_type && tune.tune_type.toLowerCase().includes(search)) ||
      (tune.session_key || '').toLowerCase().includes(search) ||
      (tune.setting_key || '').toLowerCase().includes(search)
    return tuneIdMatch || textMatch
  })
}
