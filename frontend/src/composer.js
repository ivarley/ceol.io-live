// The live logger's composer rules (spec 024 fast path, spec 052 §B5): the session's
// vocabulary as a match index, the instant exact and type-ahead matches over it, which
// set the cursor is building, the "likely next tune", what Enter does with the text,
// and what a server match verdict means. Pure, like logstate.js, so the native app can
// be held to the same answers (composer.fixtures.json).
//
// The index is plain JSON (objects keyed by string, arrays of ids) rather than Maps and
// Sets, so a fixture can pin it and another client can read it.

import { normName, stripThe } from './logstate.js'
import { abcNeedle, normAbc } from './shared/abcquery.js'

const rid = (r) => r.session_instance_tune_id

// --- The vocabulary index ---------------------------------------------------- //

// From the vocabulary endpoint's known_tunes / known_aliases. Normalization mirrors the
// server matcher (find_matching_tune): apostrophe fold, unaccent, lower; "The"
// flexibility on the name tier only.
//   alias:  normName(alias) -> [tune_id]
//   name:   normName(name) and stripThe(normName(name)) -> [tune_id]
//   byId:   tune_id -> {tune_id, name, tune_type}
//   list:   vocabulary order, deduped by tune_id (first wins), for substring matching:
//           {tune_id, name, tune_type, nn, aliases, abc, idx}
//   next:   tune_id -> the tune that usually follows it here
// Returns null when there is no vocabulary at all.
export function buildVocabIndex(known, aliases) {
  if (!known && !aliases) return null
  const index = { alias: {}, name: {}, byId: {}, list: [], next: {} }
  const add = (map, key, id) => {
    if (!key) return
    const ids = map[key] || (map[key] = [])
    if (!ids.includes(id)) ids.push(id)
  }
  const listById = {}
  const ensure = (id, name, tuneType) => {
    let e = listById[id]
    if (!e) {
      e = { tune_id: id, name, tune_type: tuneType ?? null, nn: normName(name), aliases: [], abc: '' }
      listById[id] = e
      index.list.push(e)
    }
    return e
  }
  for (const t of known || []) {
    if (!t.tune_id) continue
    if (t.next) index.next[t.tune_id] = t.next
    index.byId[t.tune_id] = { tune_id: t.tune_id, name: t.name, tune_type: t.tune_type ?? null }
    const n = normName(t.name)
    add(index.name, n, t.tune_id)
    add(index.name, stripThe(n), t.tune_id) // "The X" <-> "X", both ways
    const e = ensure(t.tune_id, t.name, t.tune_type)
    if (t.abc) e.abc = normAbc(t.abc)
    if (t.alias) {
      add(index.alias, normName(t.alias), t.tune_id)
      e.aliases.push(normName(t.alias))
    }
  }
  for (const a of aliases || []) {
    if (!a.tune_id || !a.alias) continue
    add(index.alias, normName(a.alias), a.tune_id)
    if (!index.byId[a.tune_id]) index.byId[a.tune_id] = { tune_id: a.tune_id, name: a.name || a.alias, tune_type: a.tune_type ?? null }
    ensure(a.tune_id, a.name || a.alias, a.tune_type).aliases.push(normName(a.alias))
  }
  index.list.forEach((e, i) => { e.idx = i })
  return index
}

// A UNIQUE exact known tune for the text, or null (no match, or several: the server
// decides those, and never guesses). The alias tier wins, as on the server.
export function resolveLocal(index, q) {
  if (!index) return null
  const qn = normName(q)
  if (!qn) return null
  const aIds = index.alias[qn]
  if (aIds && aIds.length === 1) return index.byId[aIds[0]] || null
  if (aIds && aIds.length > 1) return null
  const ids = new Set()
  for (const key of new Set([qn, stripThe(qn)])) for (const id of index.name[key] || []) ids.add(id)
  if (ids.size === 1) return index.byId[[...ids][0]] || null
  return null
}

// The instant type-ahead: substring matches over names and aliases (2+ characters), then
// notation matches for note-only input (abcNeedle's minimum), marked abc:true and after
// every name match. Each group: tunes already in the set last, the set's own type first,
// then vocabulary order (session plays, then global popularity), then name.
export function resolveLocalMany(index, q, limit = 8, preferType = null, inSetIds = []) {
  if (!index) return []
  const qn = normName(q)
  const inSet = new Set(inSetIds)
  const cmp = (a, b) => {
    const ia = inSet.has(a.tune_id) ? 1 : 0
    const ib = inSet.has(b.tune_id) ? 1 : 0
    if (ia !== ib) return ia - ib
    const pa = preferType && a.tune_type === preferType ? 0 : 1
    const pb = preferType && b.tune_type === preferType ? 0 : 1
    if (pa !== pb) return pa - pb
    if (a.idx !== b.idx) return a.idx - b.idx
    return a.nn < b.nn ? -1 : a.nn > b.nn ? 1 : 0
  }
  const nameHits = []
  if (qn.length >= 2) {
    for (const e of index.list) {
      if (e.nn.includes(qn) || e.aliases.some((a) => a.includes(qn))) nameHits.push(e)
    }
    nameHits.sort(cmp)
  }
  const abcHits = []
  const an = abcNeedle(q)
  if (an) {
    const seen = new Set(nameHits.map((e) => e.tune_id))
    for (const e of index.list) {
      if (e.abc && !seen.has(e.tune_id) && e.abc.includes(an)) abcHits.push(e)
    }
    abcHits.sort(cmp)
  }
  return [
    ...nameHits.map((e) => ({ tune_id: e.tune_id, name: e.name, tune_type: e.tune_type })),
    ...abcHits.map((e) => ({ tune_id: e.tune_id, name: e.name, tune_type: e.tune_type, abc: true })),
  ].slice(0, limit)
}

// --- The set being built ------------------------------------------------------- //

// The set the cursor is adding to: the open last set at the end; the anchor's set
// otherwise; none for a new-set gap (or a closed end). `insertAfterId` is the logger's
// cursor: null (end), an id (after it), {before: id}, or {newSet: id}.
export function cursorSegment(segments, endIsOpen, insertAfterId) {
  const c = insertAfterId
  if (c == null) return endIsOpen && segments.length ? segments[segments.length - 1] : null
  if (typeof c === 'object') {
    if (c.newSet != null) return null
    return segments.find((s) => s.tunes.some((t) => rid(t) === c.before)) || null
  }
  return segments.find((s) => s.tunes.some((t) => rid(t) === c)) || null
}

// The set's tune type when all its typed tunes agree, else null (a soft sort preference).
export function setTuneType(seg) {
  if (!seg) return null
  const types = new Set(seg.tunes.map((t) => t.tune_type).filter(Boolean))
  return types.size === 1 ? [...types][0] : null
}

// The tune ids already in the set: demoted in the suggestions, not hidden (a set can
// repeat a tune).
export function setTuneIds(seg) {
  const ids = []
  if (seg) for (const t of seg.tunes) if (t.tune_id != null && !ids.includes(t.tune_id)) ids.push(t.tune_id)
  return ids
}

export const nextAssocKey = (anchorId, nextId) => `${anchorId}->${nextId}`

// The likely next tune: when the cursor sits at the end of a non-empty set whose last
// row is a linked tune, the tune that usually follows that one here — unless it's been
// dismissed this session or is already in the set. `seg` is cursorSegment(...).
export function likelyNext(index, seg, insertAfterId, dismissed = []) {
  if (!index) return null
  if (insertAfterId && typeof insertAfterId === 'object') return null
  if (!seg || !seg.tunes.length) return null
  const last = seg.tunes[seg.tunes.length - 1]
  if (insertAfterId != null && rid(last) !== insertAfterId) return null
  if (last.record_type === 'break' || last.tune_id == null) return null
  const nx = index.next[last.tune_id]
  if (!nx) return null
  if (dismissed.includes(nextAssocKey(last.tune_id, nx.tune_id))) return null
  if (setTuneIds(seg).includes(nx.tune_id)) return null
  return nx
}

// The suggestion stays up while the typed text is part of its name (or nothing is typed).
export function nextMatchesInput(nx, input) {
  if (!nx) return false
  const q = normName(input)
  return !q || normName(nx.name).includes(q)
}

// --- Enter ----------------------------------------------------------------------- //

// What Enter does with typed text, before any new network call:
//   {action: 'pick', tune}  a unique exact local match, or the only candidate showing
//   {action: 'submit'}      the server already said nothing matches: log it unlinked
//   {action: 'ambiguous'}   the server's answer has several and none is exact: a
//                           placeholder, with the choices showing
//   {action: 'resolve'}     not answered yet: a placeholder now, settled when the match lands
//   null                    nothing typed
// `shown` is the dropdown's state: {query, results, searching, noMatch, exact}.
export function commitStep(index, q, shown) {
  q = (q || '').trim()
  if (!q) return null
  const local = resolveLocal(index, q)
  if (local) return { action: 'pick', tune: local }
  const { query, results = [], searching, noMatch, exact } = shown || {}
  if (query === q && results.length === 1) return { action: 'pick', tune: results[0] }
  if (!searching && query === q && (results.length || noMatch)) {
    if (!results.length) return { action: 'submit' }
    if (exact) return { action: 'pick', tune: results[0] }
    return { action: 'ambiguous' }
  }
  return { action: 'resolve' }
}

// What a server match verdict ({exact_match, results}) does to a placeholder: nothing
// matched (log the text unlinked), one tune (link it), or several (let the user choose).
export function resolution(m) {
  const results = (m && m.results) || []
  if (!results.length) return { kind: 'unlinked' }
  if (m.exact_match || results.length === 1) {
    const t = results[0]
    return { kind: 'linked', tune: { tune_id: t.tune_id, name: t.name, tune_type: t.tune_type ?? null } }
  }
  return { kind: 'ambiguous', results: results.slice(0, 8) }
}

// The name matcher's answer with the notation search's added: name matches first, then
// notation-only ones (abc:true), eight at most; the verdict stays the name matcher's.
export function withNotationResults(m, abc) {
  if (!abc || !abc.length) return m
  const seen = new Set(m.results.map((r) => r.tune_id))
  const extra = abc
    .filter((t) => t.tune_id != null && !seen.has(t.tune_id))
    .map((t) => ({ tune_id: t.tune_id, name: t.name, tune_type: t.tune_type, in_session_tune: t.in_session, abc: true }))
  if (!extra.length) return m
  return { exact_match: m.exact_match, results: [...m.results, ...extra].slice(0, 8) }
}
