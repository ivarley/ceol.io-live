// Pure selection-mode logic (spec 029): drag-block computation, drop-target
// enumeration/eligibility, optimistic move keys, clipboard serialization, range
// select, filter-aware select-all. Same philosophy as logstate.js — plain arrays
// and objects, no Svelte/DOM/network, so every rule here is unit-testable. The
// silent-bug territory is the drop machinery: eligibility (which seams are no-ops
// for a given block) and the optimistic fractional keys, which must mirror the
// server's exclude-the-block rule or the settle visibly reorders rows.

import { generateBetween } from './fracindex.js'
import { normName } from './logstate.js'

const rid = (r) => r.session_instance_tune_id

// --- Drag block (what the grab bar lifts, §F) ------------------------------ //

// The grabbed tune plus its CONTIGUOUS run of selected tunes (contiguity is over
// the tune sequence — intervening breaks don't interrupt a run), plus any breaks
// interior to the run's span (they travel with the block: 14 tunes in 4 sets stays
// 4 sets). An unselected grabbed row drags alone; the selection is not consulted.
// Returns { tuneIds, recordIds, setCount } or null (row not draggable).
export function dragBlock(ordered, selectedIds, grabbedId) {
  const tunes = ordered.filter((r) => r.record_type === 'tune')
  const gi = tunes.findIndex((r) => rid(r) === grabbedId)
  if (gi === -1 || tunes[gi]._temp || tunes[gi]._removing) return null
  let lo = gi
  let hi = gi
  if (selectedIds.has(grabbedId)) {
    while (lo > 0 && selectedIds.has(rid(tunes[lo - 1]))) lo--
    while (hi < tunes.length - 1 && selectedIds.has(rid(tunes[hi + 1]))) hi++
  }
  const tuneIds = tunes.slice(lo, hi + 1).map(rid)
  // recordIds = the run's span in the full ordered list (tunes + interior breaks)
  const from = ordered.findIndex((r) => rid(r) === tuneIds[0])
  const to = ordered.findIndex((r) => rid(r) === tuneIds[tuneIds.length - 1])
  const span = ordered.slice(from, to + 1)
  return {
    tuneIds,
    recordIds: span.map(rid),
    setCount: 1 + span.filter((r) => r.record_type === 'break').length,
  }
}

// --- Drop targets (§F) ------------------------------------------------------ //

// Every eligible drop zone, top to bottom. Each target carries the move_tunes
// anchor fields directly: { key, after_record_id, before_record_id, new_set }.
// Keys extend the app's seam vocabulary: 'top-new' (own set at the very start) and
// 'end-new' (own set below an open end) exist only as drag targets — the cursor
// seams don't offer them.
//
// Eligibility: a zone is a no-op (excluded) when dropping there reproduces the
// current structure — any zone whose adjacent record or anchor is part of the
// block, plus the subtler case of dropping a block that IS a whole set (or run of
// sets) into the new-set gap immediately below itself.
export function dropTargets(ordered, segments, endIsOpen, blockRecordIds) {
  const block = new Set(blockRecordIds)
  const idx = new Map(ordered.map((r, i) => [rid(r), i]))
  const neighborInBlock = (id, dir) => {
    const i = idx.get(id)
    if (i == null) return false
    const nb = ordered[i + dir]
    return nb ? block.has(rid(nb)) : false
  }
  // Is the block a whole set (or whole run of sets)? True when the record just
  // above the block's first record is a break or the list start.
  const first = ordered.find((r) => block.has(rid(r)))
  const fi = first ? idx.get(rid(first)) : -1
  const blockStartsAtSetBoundary = fi <= 0 || ordered[fi - 1].record_type === 'break'

  const out = []
  const add = (key, after, before, newSet) =>
    out.push({ key, after_record_id: after, before_record_id: before, new_set: newSet })

  if (!segments.length) return out
  const firstTune = rid(segments[0].tunes[0])

  // Own set at the very start. The anchor is the first tune; if that's in the
  // block the drop is structurally where the block already is.
  if (!block.has(firstTune)) add('top-new', null, firstTune, true)

  for (let si = 0; si < segments.length; si++) {
    const seg = segments[si]
    const segFirst = rid(seg.tunes[0])
    // start-of-set weld seam: between the preceding break and the set's first tune
    if (!block.has(segFirst) && !neighborInBlock(segFirst, -1)) add(`start:${segFirst}`, null, segFirst, false)
    for (let ti = 0; ti < seg.tunes.length; ti++) {
      const r = seg.tunes[ti]
      if (r._temp) continue
      const id = rid(r)
      const openLast = endIsOpen && si === segments.length - 1 && ti === seg.tunes.length - 1
      if (openLast) {
        // the open end: weld onto the open set, or land as own set below it
        if (!block.has(id)) {
          add('end', null, null, false)
          if (!blockEndsLog(ordered, block) || !blockStartsAtSetBoundary) add('end-new', null, null, true)
        }
        continue
      }
      if (!block.has(id) && !neighborInBlock(id, 1)) add(`after:${id}`, id, null, false)
    }
    if (si < segments.length - 1 && seg.breakAfter != null) {
      const nextFirst = rid(segments[si + 1].tunes[0])
      // no-op case: the block is exactly the set(s) ending right above this gap
      const lastAbove = rid(seg.tunes[seg.tunes.length - 1])
      const noop = block.has(lastAbove) && blockStartsAtSetBoundary
      if (!block.has(nextFirst) && !noop) add(`inter:${nextFirst}`, null, nextFirst, true)
    }
  }
  if (!endIsOpen) {
    // closed end (trailing break): the end target starts a new set there
    const last = ordered[ordered.length - 1]
    if (!last || !block.has(rid(last))) add('end', null, null, true)
  }
  return out
}

function blockEndsLog(ordered, block) {
  const lastTune = [...ordered].reverse().find((r) => r.record_type === 'tune')
  return lastTune ? block.has(rid(lastTune)) : false
}

// --- Optimistic move keys (§F) ---------------------------------------------- //

// Client-side preview of the server's key assignment: destination gap computed
// EXCLUDING the moving rows, keys generated sequentially. Returns
// { positions: Map(recordId -> newKey), tempBreakKeys: {before, after} } where the
// temp break keys are non-null when new_set requires a boundary break on that side
// (mirrors the server: needed only where the block would weld onto a live tune).
export function optimisticMove(ordered, allRecords, blockRecordIds, target) {
  const block = new Set(blockRecordIds)
  const rest = ordered.filter((r) => !block.has(rid(r))) // live, non-moving, in order
  let predPos = null
  let succPos = null
  let predRec = null
  let succRec = null
  const findIn = (id) => rest.findIndex((r) => rid(r) === id)

  let i
  if (target.before_record_id != null && (i = findIn(target.before_record_id)) !== -1) {
    succRec = rest[i]
    succPos = succRec.order_position
    predRec = i > 0 ? rest[i - 1] : null
    predPos = predRec ? predRec.order_position : null
  } else if (target.after_record_id != null && (i = findIn(target.after_record_id)) !== -1) {
    predRec = rest[i]
    predPos = predRec.order_position
    succRec = i + 1 < rest.length ? rest[i + 1] : null
    succPos = succRec ? succRec.order_position : null
  } else {
    // append: after everything non-block ever placed (incl. temp/deleted spacers)
    for (const r of allRecords) {
      if (!block.has(rid(r)) && r.order_position && (predPos == null || r.order_position > predPos)) {
        predPos = r.order_position
      }
    }
    predRec = rest.length ? rest[rest.length - 1] : null
  }

  const needBefore = !!target.new_set && predRec != null && predRec.record_type === 'tune'
  const needAfter = !!target.new_set && succRec != null && succRec.record_type === 'tune'

  const positions = new Map()
  const tempBreakKeys = { before: null, after: null }
  let prev = predPos
  if (needBefore) {
    prev = generateBetween(prev, succPos)
    tempBreakKeys.before = prev
  }
  // moving records keep their internal order — feed them in current order
  for (const r of ordered) {
    if (!block.has(rid(r))) continue
    prev = generateBetween(prev, succPos)
    positions.set(rid(r), prev)
  }
  if (needAfter) tempBreakKeys.after = generateBetween(prev, succPos)
  return { positions, tempBreakKeys }
}

// --- Clipboard (§D) ---------------------------------------------------------- //

// Selected tunes grouped by set, in log order: plain text (lines = sets, commas =
// tunes — the old pill logger's system-clipboard format) + the rich internal form.
// Returns null for an empty selection.
export function serializeClipboard(segments, selectedIds) {
  const rich = []
  for (const seg of segments) {
    const picked = seg.tunes.filter((t) => selectedIds.has(rid(t)))
    if (picked.length) {
      rich.push(picked.map((t) => ({
        tune_id: t.tune_id ?? null,
        name: t.name || (t.tune_id ? `#${t.tune_id}` : ''),
        tune_type: t.tune_type ?? null,
      })))
    }
  }
  if (!rich.length) return null
  const text = rich.map((set) => set.map((t) => t.name).join(', ')).join('\n')
  return { text, rich }
}

// System-clipboard text -> paste plan (§D three-case resolution):
//   1. byte-identical to our last copy -> the internal rich data (links survive);
//   2. JSON array -> old-logger pill format (array of sets, or old-old flat array);
//   3. plain text -> lines/commas, names only (server matching links what it can).
// Returns { kind: 'internal'|'json'|'text', sets: [[{tune_id, name}]] } or null.
export function parseClipboard(text, lastCopy) {
  const raw = (text || '').trim()
  if (!raw) return null
  if (lastCopy && text === lastCopy.text) return { kind: 'internal', sets: lastCopy.rich }
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length) {
      const pill = (p) => ({ tune_id: p.tuneId ?? p.tune_id ?? null, name: p.tuneName ?? p.name ?? '' })
      const sets = Array.isArray(parsed[0])
        ? parsed.map((set) => set.map(pill))
        : [parsed.map(pill)] // old-old flat pill array = one set
      const clean = sets.map((s) => s.filter((t) => t.name || t.tune_id != null)).filter((s) => s.length)
      if (clean.length) return { kind: 'json', sets: clean }
    }
  } catch {
    /* not JSON — fall through to plain text */
  }
  const sets = raw.split('\n')
    .map((line) => line.split(',').map((n) => n.trim()).filter(Boolean).map((name) => ({ tune_id: null, name })))
    .filter((s) => s.length)
  return sets.length ? { kind: 'text', sets } : null
}

// --- Range select & filter-aware select-all (§B) ----------------------------- //

// Tune ids between anchor and target inclusive (either direction, across breaks).
// A vanished anchor degrades to just the target.
export function rangeBetween(ordered, anchorId, targetId) {
  const tunes = ordered.filter((r) => r.record_type === 'tune')
  const a = tunes.findIndex((r) => rid(r) === anchorId)
  const b = tunes.findIndex((r) => rid(r) === targetId)
  if (b === -1) return []
  if (a === -1) return [targetId]
  const [lo, hi] = a < b ? [a, b] : [b, a]
  return tunes.slice(lo, hi + 1).map(rid)
}

export function matchesFilter(r, query) {
  return normName(r.name || '').includes(normName(query))
}

// "Select all": every settled tune — or, with a filter active, only the MATCHING
// tunes (not their whole sets: selecting a whole set because one member matched
// would make a following bulk Delete over-delete).
export function selectableIds(segments, filterText) {
  const q = (filterText || '').trim()
  const out = []
  for (const seg of segments) {
    for (const t of seg.tunes) {
      if (t._temp || t._removing) continue
      if (!q || matchesFilter(t, q)) out.push(rid(t))
    }
  }
  return out
}
