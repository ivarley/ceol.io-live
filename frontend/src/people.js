// Who's there, in the live logger (spec 024 §F, spec 034): the loggers' colours and
// initials, whose colour a logged tune carries, who else is typing, and how the
// attendance picker groups a session's people. Pure, like logstate.js, so the native
// app is held to the same answers (people.fixtures.json).

import { instanceTimeLabel } from './shared/format.js'

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

// --- Someone else's change, said in a line (spec 024 §E) ---------------------- //

// How many activity lines show at once; the oldest drops off.
export const MAX_ACTIVITY = 3

// What the actor did, from the op event: "added The Kesh", "ended a set"; null for
// an op not worth a line.
export function remoteLabel(d) {
  const n = d.record?.name || (d.record?.tune_id ? `#${d.record.tune_id}` : 'a tune')
  switch (d.op_type) {
    case 'add_tune': return `added ${n}`
    case 'corroborate': return `also logged ${n}`
    case 'change_tune': return `edited ${n}`
    case 'remove_tune': return `removed ${n}`
    case 'move_tunes': { const c = d.moved_ids?.length || 0; return `moved ${c} tune${c === 1 ? '' : 's'}` }
    case 'remove_tunes': { const c = d.records?.length || 0; return `removed ${c} tune${c === 1 ? '' : 's'}` }
    case 'restore_tunes': { const c = d.records?.length || 0; return `restored ${c} tune${c === 1 ? '' : 's'}` }
    case 'set_break': return d.removed ? 'removed a break' : 'ended a set'
    case 'attribute_set_starter': return d.person ? `set ${d.person.display_name} as starting a set` : 'cleared a set starter'
    case 'set_confidence': return `confirmed ${n}`
    case 'attendance_add': return d.person ? `checked in ${d.person.display_name}` : 'updated attendance'
    case 'attendance_create_person': return d.person ? `added ${d.person.display_name}` : 'added a player'
    case 'attendance_remove': return d.person ? `checked out ${d.person.display_name}` : 'updated attendance'
    case 'edit_notes': return 'edited the notes'
    // One op, up to two distinct edits — say which actually happened, or the
    // line claims someone re-dated a log when they only fixed the end time.
    case 'set_date': {
      const movedDate = d.previous_date != null && d.date !== d.previous_date
      const movedTimes =
        ('start_time' in d && d.start_time !== d.previous_start_time) ||
        ('end_time' in d && d.end_time !== d.previous_end_time)
      const when = instanceTimeLabel({ start_time: d.start_time, end_time: d.end_time })
      if (movedDate && movedTimes && d.session_date) return `re-dated this log to ${d.session_date}${when ? `, ${when}` : ''}`
      if (movedDate) return d.session_date ? `re-dated this log to ${d.session_date}` : 're-dated this log'
      if (movedTimes) return when ? `set this log's time to ${when}` : "cleared this log's time"
      return 're-dated this log'
    }
    case 'set_name': return d.instance_name ? `named this log "${d.instance_name}"` : "cleared this log's name"
    default: return null
  }
}

// The whole line, or null: someone's name and what they did. Your own changes are
// skipped while you're editing (you just made them); in view mode every change is
// shown, even one from your account in another window.
export function activityText(d, myPersonId, viewing) {
  if (!d.actor || d.actor.person_id == null) return null
  if (!viewing && d.actor.person_id === myPersonId) return null
  const label = remoteLabel(d)
  if (!label) return null
  return `${d.actor.name || 'Someone'} ${label}`
}
