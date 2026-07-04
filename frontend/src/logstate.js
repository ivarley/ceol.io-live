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

// --- thesession.org id parsing (spec 026/028) ------------------------------ //

// Detect a thesession.org tune URL or bare numeric id -> its integer id, else null.
// Mirrors the server's _parse_thesession_id. Shared by the composer's paste detection
// (App) and the deep-search paste-URL import (TuneSearch).
export function parseThesessionId(raw) {
  if (raw == null) return null
  const s = String(raw).trim()
  const m = s.match(/thesession\.org\/tunes\/(\d+)/)
  if (m) return parseInt(m[1], 10)
  return /^\d+$/.test(s) ? parseInt(s, 10) : null
}

// --- insertion-cursor slots (spec 028 keyboard nav) ------------------------ //

// Every insertion-cursor position, top to bottom, matching the seams the live logger
// actually renders. Values mirror `insertAfterId`: `{ before: id }` = a set's start seam,
// `<tuneId>` = the seam after that tune, `null` = the open-set end OR the closed-end
// new-set seam, `{ newSet: nextFirstId }` = a new set in a between-sets gap. Temp
// (optimistic) rows render no seam, so they're skipped. Arrow keys step through this list.
export function computeCursorSlots(segments, endIsOpen, hasOrdered) {
  const slots = []
  for (let si = 0; si < segments.length; si++) {
    const seg = segments[si]
    slots.push({ before: seg.tunes[0].session_instance_tune_id }) // start-of-set seam
    for (let ti = 0; ti < seg.tunes.length; ti++) {
      const r = seg.tunes[ti]
      if (r._temp) continue
      const openLast = endIsOpen && si === segments.length - 1 && ti === seg.tunes.length - 1
      slots.push(openLast ? null : r.session_instance_tune_id)
    }
    if (si < segments.length - 1 && seg.breakAfter != null) {
      slots.push({ newSet: segments[si + 1].tunes[0].session_instance_tune_id }) // new set in the gap
    }
  }
  if (hasOrdered && !endIsOpen) slots.push(null) // closed-end new-set seam
  return slots
}

// The seam-key a cursor slot resolves to (mirrors the App's `activeSeam` derived), so
// cursor-stepping can locate the current position within computeCursorSlots' output.
export function seamKeyFor(s) {
  if (s == null) return 'end'
  if (typeof s === 'object' && s.newSet != null) return `inter:${s.newSet}`
  if (typeof s === 'object' && s.before != null) return `start:${s.before}`
  return `after:${s}`
}

// The action Enter performs on the current cursor seam (spec 028 keyboard nav): a between-sets
// seam (`{ newSet }`) joins the two sets on the break between them; an intra-set after-tune seam
// (`<tuneId>` that isn't a set's last tune) splits there. Start seams, the end, and a set's
// last-tune seam have no action → null. Mirrors the "Join"/"Split" pills the seams render.
export function seamActionFor(insertAfterId, segments) {
  const c = insertAfterId
  if (c != null && typeof c === 'object' && c.newSet != null) {
    for (let i = 0; i < segments.length - 1; i++) {
      if (segments[i + 1].tunes[0].session_instance_tune_id === c.newSet && segments[i].breakAfter != null) {
        return { type: 'join', breakId: segments[i].breakAfter }
      }
    }
    return null
  }
  if (typeof c === 'number') {
    for (const seg of segments) {
      const idx = seg.tunes.findIndex((t) => t.session_instance_tune_id === c)
      if (idx !== -1) return idx < seg.tunes.length - 1 ? { type: 'split', tuneId: c } : null
    }
  }
  return null
}

// --- page-local input history (spec 028: filter box + search box recall) --- //

// Push a used query onto an MRU history list (in place): drop any prior copy, append as newest.
// Blank queries are ignored. Returns the same array for chaining.
export function rememberInHistory(hist, q) {
  const s = (q || '').trim()
  if (!s) return hist
  const i = hist.indexOf(s)
  if (i !== -1) hist.splice(i, 1)
  hist.push(s)
  return hist
}

// Step through history (oldest→newest). `pos` is the current cursor (null = the live draft, not
// yet navigating). dir < 0 = older (Up), dir > 0 = newer (Down). Returns { pos, value } for the
// next state, or null when the move isn't possible (empty history, or Down from the draft — the
// caller handles that, e.g. "Down in an empty filter jumps to the top seam"). Stepping newer past
// the newest returns { pos: null, value: '' } — back to an empty draft.
export function historyStep(hist, pos, dir) {
  const n = hist.length
  if (!n) return null
  if (dir < 0) {
    const next = pos == null ? n - 1 : Math.max(0, pos - 1)
    return { pos: next, value: hist[next] }
  }
  if (pos == null) return null
  if (pos >= n - 1) return { pos: null, value: '' }
  return { pos: pos + 1, value: hist[pos + 1] }
}
