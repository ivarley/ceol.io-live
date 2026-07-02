// Pure live-logging state logic, extracted from App.svelte so it can be unit-tested
// without a Svelte component / DOM / network. Everything here operates on plain
// arrays and objects — the component keeps the reactive SvelteMap/$state and calls
// these on `[...byId.values()]`. No imports beyond the (already pure) fractional index.
//
// Silent-bug territory lives here: record ordering, set segmentation, cursor→position
// computation, and temp→real anchor remapping (the offline replay path). Guard it well.

import { generateAppend, generateBetween } from './fracindex.js'

// --- Ordering & segmentation ---------------------------------------------- //

// order_position is a COLLATE "C" (byte-order) string; compare with </> tri-state.
function cmpPos(a, b) {
  return a.order_position < b.order_position ? -1 : a.order_position > b.order_position ? 1 : 0
}

// Non-deleted records (tunes + breaks) in order. Input is any iterable of records.
export function computeOrdered(records) {
  return [...records].filter((r) => !r.deleted).sort(cmpPos)
}

// Split an ordered list into sets on 'break' boundaries. Each segment remembers the
// break record that *ends* it (breakAfter = that break's id, or null for the open set).
// A leading/empty-set break attaches to nothing and is ignored.
export function segmentByBreaks(ordered) {
  const out = []
  let cur = []
  for (const r of ordered) {
    if (r.record_type === 'break') {
      if (cur.length) { out.push({ tunes: cur, breakAfter: r.session_instance_tune_id }); cur = [] }
    } else {
      cur.push(r)
    }
  }
  if (cur.length) out.push({ tunes: cur, breakAfter: null })
  return out
}

export const setsOf = (segments) => segments.map((s) => s.tunes)
export const tunesOf = (ordered) => ordered.filter((r) => r.record_type !== 'break')

// --- Set labels ------------------------------------------------------------ //

// Pluralize a tune type ("Reel"→"Reels", "Waltz"→"Waltzes", "March"→"Marches").
export function pluralType(ty) {
  if (!ty) return ty
  if (/(s|z|ch|sh|x)$/i.test(ty)) return ty + 'es'
  return ty + 's'
}

// Per-set type label: the shared pluralized type, "Mixed" if the set spans types,
// "Unknown" when no tune is matched. Every set gets a pill.
export function setLabel(setTunes) {
  const types = new Set(setTunes.map((t) => t.tune_type).filter(Boolean))
  if (types.size === 0) return 'Unknown'
  if (types.size > 1) return 'Mixed'
  return pluralType([...types][0])
}

// --- Positioning (cursor → optimistic order_position) --------------------- //

// The largest order_position across ALL records (incl. deleted/temp) — new appends
// must sort after everything ever placed, so this scans the full record set.
export function maxPos(records) {
  let m = ''
  for (const r of records) if (r.order_position && r.order_position > m) m = r.order_position
  return m
}

// Server anchors + optimistic order_position for the current cursor.
//   insertAfterId: null = append; {before:id} = insert before; id = insert after.
//   ordered:       the non-deleted ordered list (for neighbor lookup).
//   allRecords:    every record (for the append high-water mark).
export function cursorPos(insertAfterId, ordered, allRecords) {
  const append = () => ({ afterId: null, beforeId: null, position: generateAppend(maxPos(allRecords)) })
  const c = insertAfterId
  if (c == null) return append()
  if (typeof c === 'object' && c.before != null) {
    const idx = ordered.findIndex((r) => r.session_instance_tune_id === c.before)
    if (idx === -1) return append()
    const x = ordered[idx].order_position
    const prev = idx > 0 ? ordered[idx - 1].order_position : null
    return { afterId: null, beforeId: c.before, position: generateBetween(prev, x) }
  }
  const idx = ordered.findIndex((r) => r.session_instance_tune_id === c)
  if (idx === -1) return append()
  const before = ordered[idx].order_position
  const after = idx + 1 < ordered.length ? ordered[idx + 1].order_position : null
  return { afterId: c, beforeId: null, position: generateBetween(before, after) }
}

// --- Anchor remapping (offline replay, #5b) ------------------------------- //

// Replace temp anchor/target ids in an op payload with their real server ids.
// Unresolved anchors (after/before) fall back to null (append) rather than erroring;
// an unresolved record_id target means the row never persisted → skip the op.
// Returns a COPY (the caller keeps entry.payload for temp-keyed local lookups).
export function remapAnchors(payload, tempToReal) {
  const p = { ...payload }
  const isTemp = (v) => typeof v === 'string' && v.startsWith('temp-')
  const fixAnchor = (v) => (isTemp(v) ? (tempToReal.get(v) ?? null) : v)
  if ('after_record_id' in p) p.after_record_id = fixAnchor(p.after_record_id)
  if ('before_record_id' in p) p.before_record_id = fixAnchor(p.before_record_id)
  if (isTemp(p.record_id)) {
    const real = tempToReal.get(p.record_id)
    if (real == null) return { payload: p, skip: true }
    p.record_id = real
  }
  return { payload: p, skip: false }
}

// --- Name normalization & matching ---------------------------------------- //

export const stripThe = (s) => s.replace(/^the\s+/, '')

// Mirror the server matcher (normalize_quotes + unaccent + lower). Smart-quote code
// points are \u-escaped, never written literally — editors silently auto-correct
// literal smart quotes back to ASCII, which would turn the fold into a no-op.
export function normName(s) {
  return (s || '')
    .replace(/[\u2018\u2019\u201b\u02bc\u2032\u0060\u00b4]/g, "'") // smart singles -> '
    .replace(/[\u201c\u201d\u201e\u2033\u00ab\u00bb]/g, '"')       // smart doubles -> "
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')             // unaccent (strip diacritics)
    .trim().toLowerCase()
}

// Notation normalizer for the ABC index: strip whitespace (meaningless in ABC) + lower.
export const normAbc = (s) => (s || '').replace(/\s+/g, '').toLowerCase()

// The existing tune a PURE APPEND would collapse into, mirroring the server merge rule
// (_find_corroboration_target §H30): same tune already live in the OPEN set (after the
// last break) — by tune_id when linked, else by identical normalized name when unlinked.
// Skips optimistic/temp rows. Returns the target record or null.
export function openSetMergeTarget(payload, ordered) {
  let start = 0
  for (let i = ordered.length - 1; i >= 0; i--) {
    if (ordered[i].record_type === 'break') { start = i + 1; break }
  }
  const wantId = payload.tune_id ?? null
  const wantName = wantId == null ? normName(payload.name || '') : null
  for (let i = start; i < ordered.length; i++) {
    const r = ordered[i]
    if (r.record_type !== 'tune' || r.deleted || r._temp) continue
    if (wantId != null) { if (r.tune_id === wantId) return r }
    else if (wantName && !r.tune_id && normName(r.name || '') === wantName) return r
  }
  return null
}

// --- Search result merge (§D) --------------------------------------------- //

// Stable-append merge: keep every already-shown LOCAL result pinned in place (so
// nothing the user is about to tap moves), enrich it with the server's richer fields
// (in-session badge / notation), and append only the server-ONLY tunes below.
export function mergeStable(localList, serverList) {
  const sById = new Map(serverList.filter((r) => r.tune_id != null).map((r) => [r.tune_id, r]))
  const seen = new Set(localList.map((r) => r.tune_id))
  const merged = localList.map((r) => {
    const s = sById.get(r.tune_id)
    return s ? { ...r, in_session_tune: s.in_session_tune, abc: s.abc ?? r.abc } : r
  })
  const extra = serverList.filter((r) => r.tune_id != null && !seen.has(r.tune_id))
  return [...merged, ...extra].slice(0, 8)
}
