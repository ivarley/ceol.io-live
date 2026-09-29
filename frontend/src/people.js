// Who's there, in the live logger (spec 024 §F, spec 034): the loggers' colours and
// initials, whose colour a logged tune carries, who else is typing, and how the
// attendance picker groups a session's people. Pure, like logstate.js, so the native
// app is held to the same answers (people.fixtures.json).

// Player colours, by the persisted per-session index (the roster's arrival_seq, a
// record's logged_by_color). No yellow or gold: that's the insertion point's.
export const PALETTE = ['#4f9dff', '#46d27a', '#ef8b3d', '#e0594b', '#b07cff', '#3fd0c9', '#ff8fab', '#9ab0c0']

export const colorFor = (seq) => PALETTE[((seq % PALETTE.length) + PALETTE.length) % PALETTE.length]

// "Sarah O'Connor" -> "SO"; one word -> its first two letters; nothing -> "?".
export function initials(name) {
  const words = (name || '').trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[words.length - 1][0]).toUpperCase()
}

// A row's logger colour index: only for someone else's rows (a solo session tints
// nothing); the persisted colour, else the live roster's for that person; else null.
export function loggerColorIdx(r, myPersonId, roster = []) {
  if (r.logged_by_person_id != null && myPersonId != null && r.logged_by_person_id === myPersonId) return null
  if (r.logged_by_color != null) return r.logged_by_color
  if (r.logged_by_person_id != null) {
    const p = roster.find((x) => x.person_id === r.logged_by_person_id)
    if (p) return p.arrival_seq
  }
  return null
}

// Everyone typing but me (the typing event includes the typist).
export const othersTyping = (typers, myPersonId) => (typers || []).filter((t) => t.person_id !== myPersonId)

// The attendance picker's groups, in the server's order within each: checked in (even
// if archived: they're here), then not checked in, then the archived — who show only
// when a search finds them. The query matches display names, case-insensitively.
export function pickerTiers(people, query) {
  const q = (query || '').trim().toLowerCase()
  const matches = (p) => !q || (p.display_name || '').toLowerCase().includes(q)
  const visible = (people || []).filter((p) => matches(p) && (!p.archived || q || p.attending))
  const away = visible.filter((p) => !p.attending)
  return {
    here: visible.filter((p) => p.attending),
    roster: away.filter((p) => !p.archived),
    archived: away.filter((p) => p.archived),
  }
}

// "Add Mary Kate Quinn" -> first "Mary", last "Kate Quinn".
export function splitName(query) {
  const parts = (query || '').trim().split(/\s+/)
  return { first: parts[0] || '', last: parts.slice(1).join(' ') }
}
