// Pure logic for the My Tunes page view (spec 035 Step 2) — everything here is
// data-in/data-out so it unit-tests without a DOM. Ported behavior-for-behavior
// from the legacy templates/my_tunes.html inline script.

export const STATUS_ORDER = ['want to learn', 'learning', 'learned']

// extractTuneId (thesession URL / plain number -> id) now comes from the
// shared helpers module (src/shared/) — one tested copy for every page bundle.
import { extractTuneId } from '../shared/parse.js'

// Resolve a tune's status on one instrument (by name): an explicit override wins;
// else an auto instrument follows learn_status, and a manual instrument is
// untracked (null). Delegates to the shared TunebookStatus rules when present.
export function resolveTuneInstrumentStatus(tune, instruments, instrumentName) {
  const inst = (instruments || []).find(
    (i) => i.instrument.toLowerCase() === instrumentName.toLowerCase()
  )
  if (!inst) return null
  const overrides = tune.instrument_status || {}
  if (Object.prototype.hasOwnProperty.call(overrides, inst.instrument)) {
    return overrides[inst.instrument]
  }
  return inst.is_auto ? tune.learn_status : null
}

// Spec 033 count lenses; ?? session_play_count covers stale offline caches
// (deprecated alias of the member count).
export function memberPlays(tune) {
  return tune.member_play_count ?? tune.session_play_count ?? 0
}
export function attendedPlays(tune) {
  return tune.attended_play_count ?? 0
}

// Sort comparators — single-concern, no hardcoded tiebreakers.
const sortComparators = {
  alpha: (a, b) => (a.tune_name || '').localeCompare(b.tune_name || ''),
  popularity: (a, b) => (a.tunebook_count || 0) - (b.tunebook_count || 0),
  heard: (a, b) => (a.heard_count || 0) - (b.heard_count || 0),
  plays: (a, b) => memberPlays(a) - memberPlays(b),
  attended: (a, b) => attendedPlays(a) - attendedPlays(b),
}

// Compose primary + optional secondary sort into one compare function.
export function buildSortFunction(sort) {
  const primaryCmp = sortComparators[sort.type]
  if (!primaryCmp) return null
  const primaryDir = sort.dir === 'desc' ? -1 : 1
  const secondaryCmp = sort.type2 ? sortComparators[sort.type2] : null
  const secondaryDir = sort.dir2 === 'desc' ? -1 : 1
  return (a, b) => {
    const result = primaryCmp(a, b) * primaryDir
    if (result !== 0 || !secondaryCmp) return result
    return secondaryCmp(a, b) * secondaryDir
  }
}

// Accent-insensitive contains — the shared AccentUtils global when present (the
// page always has it via base.html), with a plain fallback for unit tests.
function accentIncludes(haystack, needle) {
  if (typeof window !== 'undefined' && window.AccentUtils) {
    return window.AccentUtils.includes(haystack, needle)
  }
  const norm = (s) =>
    (s || '')
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[‘’]/g, "'")
      .toLowerCase()
  return norm(haystack).includes(norm(needle))
}

// Filter + sort the list. Returns a NEW array of the visible tunes; each carries
// `_instDimmed` when an instrument filter is active and the tune isn't on that
// instrument (kept but dimmed and sorted below the matches, never dropped).
export function filterAndSort(allTunes, filters, sort, instruments) {
  const out = []
  for (const tune of allTunes) {
    if (filters.search) {
      const tuneId = extractTuneId(filters.search)
      const nameMatch = accentIncludes(tune.tune_name || '', filters.search)
      const notesMatch = accentIncludes(tune.notes || '', filters.search)
      const tuneIdMatch = tuneId && tune.tune_id === tuneId
      if (!tuneIdMatch && !nameMatch && !notesMatch) continue
    }
    if (filters.type && tune.tune_type !== filters.type) continue

    // Relationship chips (spec 033): member = played at my sessions (R3),
    // attended = played while I was there (R4).
    if (filters.rel === 'member' && memberPlays(tune) === 0) continue
    if (filters.rel === 'attended' && attendedPlays(tune) === 0) continue

    if (filters.instrument) {
      const instStatus = resolveTuneInstrumentStatus(tune, instruments, filters.instrument)
      const dimmed = instStatus === null
      const effectiveStatus = dimmed ? tune.learn_status : instStatus
      if (filters.status && effectiveStatus !== filters.status) continue
      out.push({ ...tune, _instDimmed: dimmed })
    } else {
      if (filters.status && tune.learn_status !== filters.status) continue
      out.push(tune)
    }
  }

  const sortFn = buildSortFunction(sort)
  if (filters.instrument) {
    out.sort(
      (a, b) =>
        (a._instDimmed ? 1 : 0) - (b._instDimmed ? 1 : 0) || (sortFn ? sortFn(a, b) : 0)
    )
  } else if (sortFn) {
    out.sort(sortFn)
  }
  return out
}

// The "no tunes found" message, mirroring the legacy wording exactly.
export function noResultsMessage(filters) {
  const searchedTuneId = filters.search ? extractTuneId(filters.search) : null
  if (searchedTuneId) return `No tune with ID ${searchedTuneId} found`
  const parts = []
  if (filters.type) {
    parts.push(filters.type.charAt(0).toUpperCase() + filters.type.slice(1) + 's')
  } else {
    parts.push('tunes')
  }
  if (filters.search) parts.push(`containing '${filters.search}'`)
  if (filters.status) {
    const statusLabels = { learned: 'Learned', learning: 'Learning', 'want to learn': 'Want To Learn' }
    parts.push(`in '${statusLabels[filters.status] || filters.status}' status`)
  }
  let message = 'No ' + parts[0]
  if (parts.length > 1) message += ' ' + parts.slice(1).join(' ')
  return message + ' found'
}

// The results-count line ("42 tunes" / "Showing 3 of 42 tunes" / on-instrument form).
export function resultsCountText(filtered, total, filters) {
  const n = filtered.length
  if (filters.instrument) {
    const onInstrument = filtered.filter((t) => !t._instDimmed).length
    return `${onInstrument} of ${n} tune${n !== 1 ? 's' : ''} on ${filters.instrument}`
  }
  if (n < total) return `Showing ${n} of ${total} tunes`
  return `${total} tune${total !== 1 ? 's' : ''}`
}

// What the card's type badge shows: the numeric count under count-based sorts,
// the tune type otherwise.
export function typeBadgeLabel(tune, sortType) {
  if (sortType === 'popularity') return String(tune.tunebook_count || 0)
  if (sortType === 'heard') return String(tune.heard_count || 0)
  if (sortType === 'plays') return String(memberPlays(tune))
  if (sortType === 'attended') return String(attendedPlays(tune))
  return tune.tune_type || ''
}

// What the badge's number means under each count sort — the tooltip that keeps
// the badge from silently swapping meaning with the active sort.
export function typeBadgeTitle(sortType) {
  if (sortType === 'popularity') return 'TheSession.org tunebooks'
  if (sortType === 'heard') return 'Times heard'
  if (sortType === 'plays') return 'Times logged at my sessions'
  if (sortType === 'attended') return 'Times logged while I was there'
  return ''
}

// --- URL state (filters + sort mirrored via replaceState) --------------------

export function stateFromParams(params) {
  const filters = {
    search: params.get('search') || '',
    type: params.get('type') || '',
    status: params.get('status') || '',
    instrument: params.get('instrument') || '',
    rel: params.get('rel') || '',
  }
  const sort = {
    type: params.get('sortType') || 'alpha',
    dir: params.get('sortDir') || 'asc',
    type2: params.get('sortType2') || null,
    dir2: params.get('sortDir2') || null,
  }
  return { filters, sort }
}

export function paramsFromState(filters, sort) {
  const params = new URLSearchParams()
  if (filters.search) params.set('search', filters.search)
  if (filters.type) params.set('type', filters.type)
  if (filters.status) params.set('status', filters.status)
  if (filters.instrument) params.set('instrument', filters.instrument)
  if (filters.rel) params.set('rel', filters.rel)
  if (sort.type !== 'alpha' || sort.dir !== 'asc') {
    params.set('sortType', sort.type)
    params.set('sortDir', sort.dir)
  }
  if (sort.type2) {
    params.set('sortType2', sort.type2)
    params.set('sortDir2', sort.dir2)
  }
  return params
}

// --- offline overlay ----------------------------------------------------------

// Overlay not-yet-synced offline ops (queued in MyTunesOffline) onto the server
// tune list so an offline add/edit/remove shows immediately, before it syncs.
// Queued adds synthesize person_tune_id 'pending-<tune_id>' rows; queued removes
// drop the row; every touched row gets pending_sync (renders the badge).
export function applyPendingOps(serverTunes, ops) {
  if (!ops || !ops.length) return serverTunes
  const byId = {}
  const out = serverTunes.slice()
  out.forEach((t) => {
    byId[t.tune_id] = t
  })
  const touch = (t, patch) => {
    const copy = { ...t, ...patch, pending_sync: true }
    byId[copy.tune_id] = copy
    out[out.indexOf(t)] = copy
    return copy
  }
  ops
    .slice()
    .sort((a, b) => a.ts - b.ts)
    .forEach((op) => {
      const t = byId[op.tune_id]
      if (op.type === 'add') {
        if (!t) {
          const added = {
            tune_id: op.tune_id,
            tune_name: op.name || 'Tune #' + op.tune_id,
            tune_type: op.tune_type || null,
            learn_status: op.learn_status || 'want to learn',
            heard_count: 0,
            notes: null,
            person_tune_id: 'pending-' + op.tune_id,
            tunebook_count: op.tunebook_count || 0,
            pending_sync: true,
          }
          byId[op.tune_id] = added
          out.push(added)
        } else {
          touch(t, {})
        }
      } else if (op.type === 'remove') {
        if (t) touch(t, { _removed: true })
      } else if (op.type === 'set_status' && t) {
        touch(t, { learn_status: op.learn_status })
      } else if (op.type === 'set_heard' && t) {
        touch(t, { heard_count: op.heard_count })
      } else if (op.type === 'set_notes' && t) {
        touch(t, { notes: op.notes })
      } else if (op.type === 'set_instrument_status' && t) {
        const over = { ...(t.instrument_status || {}) }
        if (op.status === null || op.status === undefined) delete over[op.instrument]
        else over[op.instrument] = op.status
        touch(t, { instrument_status: over })
      }
    })
  return out.filter((t) => !t._removed)
}

// Promise flavor used by the page: read the queue, overlay, and never let a
// bundle/queue failure blank the list (rule 6 of the offline contract).
export function overlayPendingOps(serverTunes) {
  if (typeof window === 'undefined' || !window.MyTunesOffline || !window.MyTunesOffline.pending) {
    return Promise.resolve(serverTunes)
  }
  return window.MyTunesOffline.pending()
    .then((ops) => applyPendingOps(serverTunes, ops))
    .catch(() => serverTunes)
}

// --- writes (optimistic; offline-queued via the shared op-queue) ---------------

// Submit one op through window.MyTunesOffline when present (queues offline,
// resolves {queued:true}), else a plain POST. Rejects on a server rejection.
export function submitOp(op) {
  if (typeof window !== 'undefined' && window.MyTunesOffline) {
    return window.MyTunesOffline.submit(op)
  }
  return fetch('/api/my-tunes/ops', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(op),
  })
    .then((r) => r.json())
    .then((d) => {
      if (!d.success) throw new Error(d.error || 'op failed')
      return { online: true, data: d }
    })
}

// Next status in the tap-to-cycle order.
export function nextStatus(current) {
  return STATUS_ORDER[(STATUS_ORDER.indexOf(current) + 1) % STATUS_ORDER.length]
}

// Per-instrument cycle result: what the overrides map and the op status become.
// An auto instrument set back to the tune's overall status stores NO override
// (snap-back) — matches the modal's semantics.
export function cycleInstrumentOverride(tune, inst, next) {
  const updated = { ...(tune.instrument_status || {}) }
  if (inst.is_auto && next === tune.learn_status) delete updated[inst.instrument]
  else updated[inst.instrument] = next
  return updated
}

// Fetch the full list from the API, following pagination past the 2000-row page
// cap (the legacy page silently truncated at 2000 — this is the fix).
export async function fetchAllTunes(sortParam) {
  let instruments = null
  const tunes = []
  for (let page = 1; ; page++) {
    const res = await fetch(
      `/api/my-tunes?per_page=2000&page=${page}&sort=${encodeURIComponent(sortParam)}`,
      { headers: { Accept: 'application/json' }, credentials: 'same-origin' }
    )
    if (!res.ok) throw new Error('my-tunes failed: ' + res.status)
    const j = await res.json()
    if (page === 1) instruments = j.instruments || []
    tunes.push(...(j.tunes || []))
    if (!j.pagination || !j.pagination.has_next) break
  }
  return { tunes, instruments }
}
