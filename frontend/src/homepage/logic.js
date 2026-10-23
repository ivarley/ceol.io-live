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
import { nightHref } from '../shared/nights.js'
import { t, tn, formatDate } from '../lib/i18n/index.js'

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

/**
 * A festival's rows lead with the instance, as the Logs tab does: at a retreat the
 * thing you need to know is "Lively Session with Richard Hearn at the Alamo Lobby,
 * 9:30pm", and which retreat it is goes without saying. So a festival row's title is
 * the time and the instance's label, and its second line is the festival's name —
 * the reverse of a regular session, whose name is its title.
 */
export function isFestival(session) {
  return (session?.session_type || 'regular') === 'festival'
}

/** The time and the place of an instance, as a row's parts. */
function timeAndPlace(session) {
  const parts = []
  const when = instanceTimeLabel(session)
  if (when) parts.push(when)
  if (session.location_name) parts.push(session.location_name)
  return parts
}

/** A home row's title: the session's name, or at a festival the instance itself. */
export function homeTitle(session) {
  if (!session) return ''
  if (!isFestival(session)) return session.name || ''
  return timeAndPlace(session).join(' · ') || session.name || ''
}

/** The opening parts of a home row's second line: where and when, or at a festival
 *  (where the title already says that) the festival's name. */
function whereAndWhen(session) {
  return isFestival(session) ? [session.name].filter(Boolean) : timeAndPlace(session)
}

/** The status chip's words. "Starts 7:00pm" needs a time; without one, "Today". */
export function statusLabel(session) {
  const status = sessionStatus(session)
  if (status === 'live') return t('Live now')
  if (status === 'finished') return t('Finished')
  const start = formatTime(session?.start_time)
  return start ? t('Starts {time}', { time: start }) : t('Today')
}

/**
 * The Today card's second line: when, where, and — only while it is live — who is
 * there. The head count is meaningless once everyone has gone home, and printing
 * "0 people here" under a finished session reads as a fault rather than a fact.
 */
export function todaySubtitle(session) {
  if (!session) return ''
  const parts = whereAndWhen(session)
  if (sessionStatus(session) === 'live') {
    const n = session.people_here || 0
    if (n > 0) parts.push(tn(n, '{n} person here', '{n} people here'))
  }
  return parts.join(' · ')
}

/**
 * The tally. "so far" only while the night is still running — on a finished log the
 * number is final, and "18 tunes logged so far" would suggest it might still move.
 */
export function tallyLabel(session) {
  const n = session?.tunes_logged || 0
  if (!n) return t('No tunes logged yet')
  return sessionStatus(session) === 'live'
    ? tn(n, '{n} tune logged so far', '{n} tunes logged so far')
    : tn(n, '{n} tune logged', '{n} tunes logged')
}

/** Where the card and its View button go: that night's log (shared/nights.js: by
 *  date, or by id when several nights of the session share the date). */
export function sessionInstanceHref(session) {
  return nightHref(session?.path, session)
}

/**
 * The Today cards and the week's rows, with a session's several nights on one day
 * folded into ONE item.
 *
 * At a festival every room is a night of the one session, so a day has a dozen of
 * them at once. A dozen cards is a strip nobody can page through, and a dozen rows is
 * a wall that buries the rest of the week. The thing to see is the festival itself —
 * "12 sessions today, 4 on now" — and the day's list is where you pick your room. A
 * night on its own (every regular session) is an item as before.
 *
 * Items keep the payload's order (date, then start time). A single night is
 * `{ kind: 'night', night }`; a fold is `{ kind: 'group', ... }` with the nights, the
 * ones on now, and where it opens: the session's list of nights.
 */
export function nightItems(nights) {
  const items = []
  const byKey = new Map()
  for (const night of nights || []) {
    const key = `${night.session_id ?? night.path}|${night.date}`
    let group = byKey.get(key)
    if (!group) {
      group = { kind: 'group', key, name: night.name, path: night.path, date: night.date, nights: [] }
      byKey.set(key, group)
      items.push(group)
    }
    group.nights.push(night)
  }
  return items.map((g) => {
    if (g.nights.length === 1) return { kind: 'night', key: `night-${g.nights[0].session_instance_id}`, night: g.nights[0] }
    const live = g.nights.filter((n) => n.is_active)
    return {
      ...g,
      live,
      liveRooms: live.map((n) => n.location_name).filter(Boolean),
      tunesLogged: g.nights.reduce((sum, n) => sum + (n.tunes_logged || 0), 0),
      allFinished: g.nights.every((n) => n.log_complete_date),
      href: g.path ? `/sessions/${g.path}/logs` : null,
    }
  })
}

/** A fold's status chip: how many are on now; else finished, or when the first starts. */
export function groupStatus(group) {
  if (group.live.length) return 'live'
  if (group.allFinished) return 'finished'
  return 'upcoming'
}

export function groupStatusLabel(group) {
  const status = groupStatus(group)
  if (status === 'live') return tn(group.live.length, '{n} on now', '{n} on now')
  if (status === 'finished') return t('Finished')
  const start = formatTime(group.nights[0]?.start_time)
  return start ? t('Starts {time}', { time: start }) : t('Today')
}

/** A fold's second line: how many sessions the day holds. */
export function groupSubtitle(group) {
  return tn(group.nights.length, '{n} session today', '{n} sessions today')
}

/** A fold's third line: the rooms on now by name — the thing you are choosing
 *  between — or, with none on, the day's tally. */
export function groupTally(group) {
  if (group.liveRooms.length) return group.liveRooms.join(', ')
  return tallyLabel({ tunes_logged: group.tunesLogged, is_active: false })
}

/** A week row for a fold: the count, and the ones on now or that it is all logged. */
export function groupWeekSubtitle(group, todayStr) {
  const parts = [tn(group.nights.length, '{n} session', '{n} sessions')]
  if (group.live.length) parts.push(tn(group.live.length, '{n} on now', '{n} on now'))
  else if (group.allFinished) parts.push(t('logged'))
  else if (todayStr && group.date < todayStr) parts.push(t('not logged'))
  return parts.join(' · ')
}

/** A week row's second line: the time, and whether you have been yet. */
export function weekSubtitle(session, todayStr) {
  const parts = whereAndWhen(session)
  if (session.log_complete_date) parts.push(t('logged'))
  else if (todayStr && session.date < todayStr) parts.push(t('not logged'))
  return parts.join(' · ')
}

/** The weekday over the day of month, for a row's date block. */
export function dowOf(dateStr) {
  return formatDate(parseLocalDate(dateStr), { weekday: 'short' })
}

export function domOf(dateStr) {
  return parseLocalDate(dateStr).getDate()
}

/** "Sep 16" — and the year too when it is not the current one. */
export function shortDate(dateStr, currentYear) {
  const d = parseLocalDate(dateStr)
  const opts = { month: 'short', day: 'numeric' }
  if (currentYear && d.getFullYear() !== currentYear) opts.year = 'numeric'
  return formatDate(d, opts)
}

/** "2 hours ago" for something edited recently, a date once that stops being useful. */
export function editedLabel(iso, currentYear, now = new Date()) {
  if (!iso) return ''
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return ''
  const mins = Math.floor((now - then) / 60000)
  if (mins < 1) return t('just now')
  if (mins < 60) return tn(mins, '{n} minute ago', '{n} minutes ago')
  const hours = Math.floor(mins / 60)
  if (hours < 24) return tn(hours, '{n} hour ago', '{n} hours ago')
  const opts = { month: 'short', day: 'numeric' }
  if (currentYear && then.getFullYear() !== currentYear) opts.year = 'numeric'
  return formatDate(then, opts)
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
    title: t('Finish logging {name}', { name: l.name }),
    date: l.date,
    lastEdit: l.last_edit,
    detail: shortDate(l.date, year),
    href: nightHref(l.path, l),
  }))
  const recordings = (payload?.in_progress_recordings || []).map((r) => ({
    kind: 'recording',
    key: `rec-${r.recording_id}`,
    title: t('Place tunes on {name}', { name: r.label || r.name }),
    date: r.date,
    lastEdit: r.last_edit,
    detail: tn(r.tune_count, '{placed} of {n} tunes placed', '{placed} of {n} tunes placed', { placed: r.placed }),
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
