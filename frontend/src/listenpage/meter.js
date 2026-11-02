// Spec 061 stage 3: the certainty meter's rules, as the iPhone has them
// (ios/Ceol/Ceol/NightRecorder.swift), so the two say the same thing about the same
// audio. Pure: the page feeds it the service's states and a person's taps, and it
// says what to show and which taps to send.
//
// Ad-hoc mode only (stage 4 adds logging): the meter is sure of a tune when a person
// taps it, or by itself at 100%, and lets go of it when the listener moves on.

/** What the meter shows as 100%: sure by itself at this belief. */
export const SURE_AT = 0.995
/** Under this a sure tune is no longer claimed (the listener doubts at the same level). */
export const DOUBT_BELOW = 0.8
/** A sure tune stands at least this long (one step) before the listener can take it back. */
export const HOLD_MS = 4000
/** Candidates under this belief are "weak": at most two of them, faded. */
export const WEAK_BELOW = 0.05

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
   * A state from the service. Returns the tune it became sure of by itself, if it did
   * (for Recent Tunes Heard), else null.
   */
  received(s) {
    this.state = s
    const c = this.confirmed
    if (c != null && (s.t_ms || 0) > this.confirmedAfterMs + HOLD_MS) {
      const mine = (s.top || []).find((x) => x.tune_id === c)
      if (s.shown !== c || notATune(s) || mayHaveChanged(s) || (mine ? mine.p : 0) < DOUBT_BELOW) this.confirmed = null
    }
    if (this.changedFrom && (notATune(s) || (s.shown != null && s.shown !== this.changedFrom.tune_id))) this.changedFrom = null
    return this.selfConfirm(s)
  }

  selfConfirm(s) {
    if (this.confirmed != null || notATune(s) || mayHaveChanged(s)) return null
    const c = (s.top || []).find((x) => x.tune_id === s.shown)
    if (!c || c.p < SURE_AT || this.wrong.has(c.tune_id)) return null
    this.sure(c)
    return c
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

  /** "Wrong tune": the sure tune isn't what is playing. */
  wrongTune() {
    const c = this.confirmed
    if (c == null) return null
    this.wrong.add(c)
    this.confirmed = null
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
