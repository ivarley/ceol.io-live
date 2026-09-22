// Home's pure logic (spec 052 §B8 Stage 4).
//
// Everything here is a plain function of the payload: no DOM, no fetch, no Svelte.
// That is deliberate. §B5 calls fixture tests for the pure client logic the
// highest-leverage preparation in the whole native plan, because a SwiftUI Home
// screen has to make exactly these decisions — which nights are "today", whether
// one is live, what the tally line says — and the only way to know the two agree
// is to test the rules against the same payload twice.

import { parseLocalDate } from '../shared/parse.js'
import { formatTime, instanceTimeLabel } from '../shared/format.js'

/**
 * The nights happening today, out of the week's list.
 *
 * The Today card is a SUBSET of `upcoming_sessions`, never a second list from the
 * server. A separate list would be a second chance to disagree about a night, and
 * the disagreement would show as a card saying one thing above a row saying another.
 */
export function todaysSessions(upcoming, todayStr) {
  if (!todayStr) return []
  return (upcoming || []).filter((s) => s.date === todayStr)
}

/**
 * Where a night stands: 'live' | 'finished' | 'upcoming'.
 *
 * `is_active` is the server's own liveness flag (the buffer either side of the
 * scheduled time, maintained by the active-sessions job), so the client never tries
 * to decide liveness from a clock it cannot trust to share the session's timezone.
 */
export function sessionStatus(session) {
  if (!session) return 'upcoming'
  if (session.is_active) return 'live'
  if (session.log_complete_date) return 'finished'
  return 'upcoming'
}

/** The status chip's words. "Starts 7:00pm" needs a time; without one, "Today". */
export function statusLabel(session) {
  const status = sessionStatus(session)
  if (status === 'live') return 'Live now'
  if (status === 'finished') return 'Finished'
  const start = formatTime(session?.start_time)
  return start ? `Starts ${start}` : 'Today'
}

/**
 * The Today card's second line: when, where, and — only while it is live — who is
 * there. The head count is meaningless once everyone has gone home, and printing
 * "0 people here" under a finished session reads as a fault rather than a fact.
 */
export function todaySubtitle(session) {
  if (!session) return ''
  const parts = []
  const when = instanceTimeLabel(session)
  if (when) parts.push(when)
  if (session.location_name) parts.push(session.location_name)
  if (sessionStatus(session) === 'live') {
    const n = session.people_here || 0
    if (n > 0) parts.push(`${n} ${n === 1 ? 'person' : 'people'} here`)
  }
  return parts.join(' · ')
}

/**
 * The tally. "so far" only while the night is still running — on a finished log the
 * number is final, and "18 tunes logged so far" would suggest it might still move.
 */
export function tallyLabel(session) {
  const n = session?.tunes_logged || 0
  if (!n) return 'No tunes logged yet'
  const noun = n === 1 ? 'tune' : 'tunes'
  return sessionStatus(session) === 'live'
    ? `${n} ${noun} logged so far`
    : `${n} ${noun} logged`
}

/** Where the card and its View button go: that night's log. */
export function sessionInstanceHref(session) {
  if (!session?.path || !session?.date) return null
  return `/sessions/${session.path}/${session.date}`
}

/** A week row's second line: the time, and whether you have been yet. */
export function weekSubtitle(session, todayStr) {
  const parts = []
  const when = instanceTimeLabel(session)
  if (when) parts.push(when)
  if (session.location_name) parts.push(session.location_name)
  if (session.log_complete_date) parts.push('logged')
  else if (todayStr && session.date < todayStr) parts.push('not logged')
  return parts.join(' · ')
}

/** The weekday over the day of month, for a row's date block. */
export function dowOf(dateStr) {
  return parseLocalDate(dateStr).toLocaleDateString('en-US', { weekday: 'short' })
}

export function domOf(dateStr) {
  return parseLocalDate(dateStr).getDate()
}

/** "Sep 16" — and the year too when it is not the current one. */
export function shortDate(dateStr, currentYear) {
  const d = parseLocalDate(dateStr)
  const opts = { month: 'short', day: 'numeric' }
  if (currentYear && d.getFullYear() !== currentYear) opts.year = 'numeric'
  return d.toLocaleDateString('en-US', opts)
}

/** "2 hours ago" for something edited recently, a date once that stops being useful. */
export function editedLabel(iso, currentYear, now = new Date()) {
  if (!iso) return ''
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return ''
  const mins = Math.floor((now - then) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const opts = { month: 'short', day: 'numeric' }
  if (currentYear && then.getFullYear() !== currentYear) opts.year = 'numeric'
  return then.toLocaleDateString('en-US', opts)
}

/**
 * "Pick up where you left off": the unfinished logs and the half-placed recordings
 * as ONE list, newest edit first.
 *
 * They were two cards. They are one section because they are one thought — work you
 * started and did not finish — and because at most three of each ever appear, so two
 * cards mostly meant two headings above two single rows.
 */
export function continueItems(payload, currentYear) {
  const year = currentYear ?? payload?.current_year
  const logs = (payload?.in_progress_logs || []).map((l) => ({
    kind: 'log',
    key: `log-${l.session_instance_id}`,
    title: `Finish logging ${l.name}`,
    date: l.date,
    lastEdit: l.last_edit,
    detail: shortDate(l.date, year),
    href: `/sessions/${l.path}/${l.date}`,
  }))
  const recordings = (payload?.in_progress_recordings || []).map((r) => ({
    kind: 'recording',
    key: `rec-${r.recording_id}`,
    title: `Place tunes on ${r.label || r.name}`,
    date: r.date,
    lastEdit: r.last_edit,
    detail: `${r.placed} of ${r.tune_count} tunes placed`,
    href: `/admin/recordings/${r.recording_id}/segment`,
  }))
  return [...logs, ...recordings].sort((a, b) => {
    const at = a.lastEdit ? Date.parse(a.lastEdit) : 0
    const bt = b.lastEdit ? Date.parse(b.lastEdit) : 0
    return bt - at
  })
}

/**
 * Apply the queued offline My-Tunes ops to the two counts.
 *
 * The home counts come from the server, so while offline they disagree with the My
 * Tunes page, which is showing the same tunes with the queue applied. This replays
 * the queue against the cached list to close that gap. Lifted verbatim in behaviour
 * from the inline script the Jinja page carried; it is here because it is a rule
 * about numbers, and a rule about numbers should be testable without a browser.
 */
export function adjustedCounts(counts, ops, statusByTuneId) {
  const delta = { 'want to learn': 0, learning: 0, learned: 0 }
  const status = { ...(statusByTuneId || {}) }
  const ordered = [...(ops || [])].sort((a, b) => a.ts - b.ts)
  for (const op of ordered) {
    if (op.type === 'add') {
      if (!(op.tune_id in status)) {
        const s = op.learn_status || 'want to learn'
        if (s in delta) delta[s] += 1
        status[op.tune_id] = s
      }
    } else if (op.type === 'set_status') {
      const old = status[op.tune_id]
      if (old && old in delta) delta[old] -= 1
      if (op.learn_status in delta) delta[op.learn_status] += 1
      status[op.tune_id] = op.learn_status
    } else if (op.type === 'remove') {
      const old = status[op.tune_id]
      if (old && old in delta) delta[old] -= 1
      delete status[op.tune_id]
    }
  }
  return {
    learning: Math.max(0, (counts?.learning || 0) + delta.learning),
    wantToLearn: Math.max(0, (counts?.wantToLearn || 0) + delta['want to learn']),
  }
}
