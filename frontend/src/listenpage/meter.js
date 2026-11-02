// Spec 061 stage 3: the certainty meter's rules, as the iPhone has them
// (ios/Ceol/Ceol/NightRecorder.swift), so the two say the same thing about the same
// audio. Pure: the page feeds it the service's states and a person's taps, and it
// says what to show and which taps to send.
//
// The meter is sure of a tune when a person taps it, or by itself at 100%, and lets go
// of it when the listener moves on. In Log mode (stage 4) the page logs what it is sure
// of to a night; the meter keeps the bookkeeping the iPhone keeps for that: the tune it
// logged last (sure again, it isn't logged twice), when each was logged (no tune again
// within ten minutes), and how long nothing has been a tune (a set break).

/** What the meter shows as 100%: sure by itself at this belief. */
export const SURE_AT = 0.995
/** Under this a sure tune is no longer claimed (the listener doubts at the same level). */
export const DOUBT_BELOW = 0.8
/** A sure tune stands at least this long (one step) before the listener can take it back. */
export const HOLD_MS = 4000
/** Candidates under this belief are "weak": at most two of them, faded. */
export const WEAK_BELOW = 0.05
/** A tune logged from here isn't logged by itself again for this long. */
export const RELOG_AFTER_MS = 600 * 1000
/** "Not a tune" this many states running (4 s each) before the set can end (the
 * iPhone's figure, from night 143: 3 steps caught 27 of 28 set breaks). */
export const END_SET_AFTER_STEPS = 3

/** More sure that nothing is being played as a tune than that anything is. */
export function notATune(s) {
  return (s.none ?? 1) > 0.5
}

/** The tune shown may have changed: no tune is claimed until the meter hears which. */
export function mayHaveChanged(s) {
  return s.changing != null && !notATune(s)
}

/** The candidate rows: every strong one, and at most two weak ones. */
export function candidates(s) {
  const top = s.top || []
  const strong = top.filter((c) => c.p >= WEAK_BELOW)
  const weak = top.filter((c) => c.p < WEAK_BELOW).slice(0, 2)
  return [...strong.map((c) => ({ ...c, weak: false })), ...weak.map((c) => ({ ...c, weak: true }))]
}

/** How many of the bar's ten cells are on, and their colour. */
export function bar(p) {
  const on = Math.max(0, Math.min(10, Math.round(p * 10)))
  return Array.from({ length: 10 }, (_, i) => (i >= on ? 'off' : i < 5 ? 'low' : i < 8 ? 'mid' : 'high'))
}

export class Meter {
  constructor() {
    this.state = null // the last state from the service
    this.confirmed = null // the tune it is sure of
    this.confirmedName = null
    this.confirmedType = null
    this.confirmedAfterMs = 0
    this.changedFrom = null // {tune_id, name} after "Tune changed"
    this.wrong = new Set() // said to be wrong: never sure of by itself again this run
    this.notATuneSteps = 0 // states running that said "not a tune"
    this.logged = null // Log mode: the tune last logged (or found logged) from here
    this.loggedRow = null // its row in the night, when this page added it
    this.loggedAt = new Map() // tune_id -> when it was logged from here (ms)
  }

  /** waiting | noTune | figuring | sure */
  get showing() {
    if (this.confirmed != null) return 'sure'
    if (!this.state) return 'waiting'
    if (notATune(this.state)) return 'noTune'
    return 'figuring'
  }

  /** "The tune may have changed (was …)": the name it was, or null. */
  get wasName() {
    if (this.changedFrom) return this.changedFrom.name || null
    const s = this.state
    if (s && mayHaveChanged(s)) return s.changing.name || null
    return null
  }

  get mayHaveChanged() {
    return !!this.changedFrom || (!!this.state && mayHaveChanged(this.state))
  }

  /**
   * A state from the service. When it became sure of a tune by itself, returns
   * {tune, log}: the candidate, and whether it is one to log (not the tune logged last,
   * which is only shown as sure again). Otherwise null.
   */
  received(s, now = Date.now()) {
    this.state = s
    this.notATuneSteps = notATune(s) ? this.notATuneSteps + 1 : 0
    const c = this.confirmed
    if (c != null && (s.t_ms || 0) > this.confirmedAfterMs + HOLD_MS) {
      const mine = (s.top || []).find((x) => x.tune_id === c)
      if (s.shown !== c || notATune(s) || mayHaveChanged(s) || (mine ? mine.p : 0) < DOUBT_BELOW) this.confirmed = null
    }
    if (this.changedFrom && (notATune(s) || (s.shown != null && s.shown !== this.changedFrom.tune_id))) this.changedFrom = null
    return this.selfConfirm(s, now)
  }

  /** Sure by itself at 100%: never a tune said to be wrong, nor another one logged
   * from here in the last ten minutes. */
  selfConfirm(s, now = Date.now()) {
    if (this.confirmed != null || notATune(s) || mayHaveChanged(s)) return null
    const c = (s.top || []).find((x) => x.tune_id === s.shown)
    if (!c || c.p < SURE_AT || this.wrong.has(c.tune_id)) return null
    if (c.tune_id === this.logged) {
      this.sure(c)
      return { tune: c, log: false }
    }
    if (now - (this.loggedAt.get(c.tune_id) ?? -Infinity) < RELOG_AFTER_MS) return null
    this.sure(c)
    return { tune: c, log: true }
  }

  /** Log mode: the tune was logged (row: the row this page added, or null when someone
   * else had logged it already). */
  markLogged(tuneId, row = null, now = Date.now()) {
    this.logged = tuneId
    this.loggedRow = row
    this.loggedAt.set(tuneId, now)
  }

  /** Log mode ends: nothing is logged from here any more. */
  forgetLogged() {
    this.logged = null
    this.loggedRow = null
  }

  /** The night's open set can end: no tune for long enough, and the log's last row a
   * tune. `ordered` is the night's rows in order. */
  canEndSet(ordered) {
    if (!this.state || !notATune(this.state) || this.notATuneSteps < END_SET_AFTER_STEPS) return false
    const last = ordered[ordered.length - 1]
    return !!last && last.record_type !== 'break'
  }

  sure(c) {
    this.confirmed = c.tune_id
    this.confirmedName = c.name || null
    this.confirmedType = c.type || null
    this.confirmedAfterMs = this.state ? this.state.t_ms || 0 : 0
    this.changedFrom = null
  }

  /** A person taps a candidate: this is it. Returns the tap to send. */
  tapThis(tuneId) {
    const top = (this.state && this.state.top) || []
    const c = top.find((x) => x.tune_id === tuneId) || { tune_id: tuneId }
    this.sure(c)
    return { type: 'tap', action: 'this', tune_id: tuneId, shown: top.map((x) => x.tune_id) }
  }

  /** "None of these": rule out every candidate shown. */
  tapNone() {
    this.confirmed = null
    const top = (this.state && this.state.top) || []
    return { type: 'tap', action: 'none', shown: top.map((x) => x.tune_id) }
  }

  /** "Wrong tune": the sure tune isn't what is playing. Returns the tap to send. In
   * Log mode the page first takes back the row it logged (`loggedRow`), if any. */
  wrongTune() {
    const c = this.confirmed
    if (c == null) return null
    this.wrong.add(c)
    this.confirmed = null
    if (this.logged === c) {
      this.forgetLogged()
      this.loggedAt.delete(c)
    }
    return { type: 'tap', action: 'none', shown: [c], why: 'wrong' }
  }

  /** "Tune changed": it was right and has ended; the listener lets go of it at once. */
  tuneChanged() {
    const c = this.confirmed
    if (c == null) return null
    this.changedFrom = { tune_id: c, name: this.confirmedName }
    this.confirmed = null
    return { type: 'tap', action: 'none', shown: [c], why: 'changed' }
  }
}

/**
 * Whether the night's latest set (the last one with tunes, open or ended) has this tune
 * as its last or second-to-last tune: someone else listening at the same session logged
 * it already. `ordered` is the night's rows in order (`record_type` 'tune' | 'break').
 */
export function latestSetEndsWith(tuneId, ordered) {
  const latest = []
  for (let i = ordered.length - 1; i >= 0; i--) {
    const r = ordered[i]
    if (r.record_type === 'break') {
      if (!latest.length) continue // the break that ended it
      break
    }
    latest.push(r)
  }
  return latest.slice(0, 2).some((r) => r.tune_id === tuneId)
}

// --- Recent Tunes Heard: kept in this browser --------------------------------

export const RECENT_KEY = 'ceol.recentTunesHeard'
export const RECENT_KEEP = 50
export const RECENT_SAME_MS = 600 * 1000

/** The list with this hearing added: newest first; the same tune again within ten
 * minutes is one hearing. */
export function addRecent(list, tune) {
  const last = list[0]
  if (last && last.tune_id === tune.tune_id && tune.heard_at - last.heard_at < RECENT_SAME_MS) return list
  return [tune, ...list].slice(0, RECENT_KEEP)
}

export function loadRecent(storage = globalThis.localStorage) {
  try {
    const list = JSON.parse(storage.getItem(RECENT_KEY) || '[]')
    return Array.isArray(list) ? list.filter((x) => x && Number.isInteger(x.tune_id)) : []
  } catch {
    return []
  }
}

export function saveRecent(list, storage = globalThis.localStorage) {
  try {
    if (list.length) storage.setItem(RECENT_KEY, JSON.stringify(list))
    else storage.removeItem(RECENT_KEY)
  } catch {}
}
