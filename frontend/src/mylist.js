// My-list (tunebook) status logic for the live logger's highlight mode. Pure —
// plain objects in, plain values out, no Svelte/DOM/network — so the roll-up and
// the bulk-op planning are unit-testable. Exactly TWO copies of the resolution
// rules exist: this ES module (bundled + unit-tested; also imported by the Svelte
// tune-detail sheet in src/tunesheet/) and its vanilla twin
// static/js/tunebook_status.js (window.TunebookStatus), which the remaining
// vanilla pages delegate to. Keep them in sync — and keep both matching the
// server's /api/my-tunes/ops semantics (see setTunebookStatus in
// src/tunesheet/TuneSheet.svelte for the overall-set behavior this module's
// planStatusOps mirrors).

export const STATUSES = ['want to learn', 'learning', 'learned']
export const NOT_ON_LIST = 'not on list'
export const STATUS_RANK = { 'want to learn': 1, learning: 2, learned: 3 }

// How a status is WORDED to a person, everywhere in the app. 'want to learn' reads as
// "To Learn": it names a shelf, not a wish, and it makes the three statuses one scale
// (To Learn -> Learning -> Learned) on the home page, the My Tunes filter and cards,
// the add pane, the tune-detail sheet and the session pages alike. Display only — the
// stored value, the ops vocabulary and the ?status= URLs all stay 'want to learn'.
export const STATUS_LABELS = {
  'want to learn': 'To Learn',
  learning: 'Learning',
  learned: 'Learned',
}

const hasOwn = (o, k) => Object.prototype.hasOwnProperty.call(o || {}, k)

// One instrument's status for an on-list entry: sparse override wins; else an auto
// instrument follows the base learn_status; a manual one without a row is untracked.
function instStatus(entry, inst) {
  if (hasOwn(entry.instrument_status, inst.instrument)) return entry.instrument_status[inst.instrument]
  return inst.is_auto ? entry.learn_status : null
}

// A per-instrument scope only means anything when the person plays 2+ instruments —
// below that the modal's roll-up IS the base learn_status, so we operate on it.
const scopedTo = (instruments, scope) =>
  scope !== 'all' && instruments.length >= 2 && instruments.some((i) => i.instrument === scope)

// The status to display for a tune under `scope` ('all' or an instrument name).
// entry = {learn_status, instrument_status} or undefined (not on the list).
// 'all' = the modal's roll-up: furthest-along status across instruments that have
// one; with 0/1 instruments it's simply the base learn_status.
export function listStatus(entry, instruments, scope = 'all') {
  if (!entry) return NOT_ON_LIST
  const insts = instruments || []
  if (scopedTo(insts, scope)) {
    const inst = insts.find((i) => i.instrument === scope)
    return instStatus(entry, inst) || NOT_ON_LIST
  }
  if (insts.length < 2) return entry.learn_status
  let best = null
  for (const inst of insts) {
    const st = instStatus(entry, inst)
    if (st && (!best || STATUS_RANK[st] > STATUS_RANK[best])) best = st
  }
  return best || entry.learn_status
}

// css class token for a status ('learned' -> 'ls-learned', NOT_ON_LIST -> 'ls-not-on-list')
export const statusClass = (st) => 'ls-' + st.replace(/ /g, '-')

// Plan the /api/my-tunes/ops calls that set `target` on each tune under `scope`.
// Returns [{tune_id, ops: [{type, ...}]}], omitting tunes that need no change.
//   - not on list, overall scope  -> add directly at the target status
//   - not on list, instrument scope -> add (base defaults to 'want to learn') +
//     the instrument override
//   - on list, overall scope -> set_status + realign AUTO overrides to follow it
//     (exactly what the modal's main segmented control does); manual overrides are
//     curated and left alone — so this is skippable only when the base already
//     matches AND no auto override exists
//   - on list, instrument scope -> one absolute set_instrument_status (the server
//     snap-backs an auto override equal to the base by deleting the row)
export function planStatusOps(tuneIds, entryFor, instruments, scope, target) {
  const insts = instruments || []
  const scoped = scopedTo(insts, scope)
  const plans = []
  for (const tune_id of tuneIds) {
    const entry = entryFor(tune_id)
    const ops = []
    if (!entry) {
      if (scoped) {
        ops.push({ type: 'add' }, { type: 'set_instrument_status', instrument: scope, status: target })
      } else {
        ops.push({ type: 'add', learn_status: target })
      }
    } else if (scoped) {
      if (listStatus(entry, insts, scope) === target) continue
      ops.push({ type: 'set_instrument_status', instrument: scope, status: target })
    } else {
      const autoOverridden = insts.filter((i) => i.is_auto && hasOwn(entry.instrument_status, i.instrument))
      if (entry.learn_status === target && !autoOverridden.length) continue
      ops.push({ type: 'set_status', learn_status: target })
      for (const i of autoOverridden) {
        ops.push({ type: 'set_instrument_status', instrument: i.instrument, status: null })
      }
    }
    plans.push({ tune_id, ops })
  }
  return plans
}

// The local mirror of what the server ends up storing after planStatusOps' ops for
// one tune apply — used to update the cached list optimistically without a refetch.
export function applyStatusLocally(entry, instruments, scope, target) {
  const insts = instruments || []
  const scoped = scopedTo(insts, scope)
  const next = entry
    ? { ...entry, instrument_status: { ...(entry.instrument_status || {}) } }
    : { learn_status: scoped ? 'want to learn' : target, instrument_status: {} }
  if (scoped) {
    const inst = insts.find((i) => i.instrument === scope)
    // server snap-back: an auto override equal to the base is stored as no row
    if (inst.is_auto && target === next.learn_status) delete next.instrument_status[scope]
    else next.instrument_status[scope] = target
  } else {
    next.learn_status = target
    for (const i of insts) if (i.is_auto) delete next.instrument_status[i.instrument]
  }
  return next
}
