// Where each export choice leads. The export happens ON the page that already has
// the filters (My Tunes, a session's Tunes or Logs tab), in its export mode: the
// `export=1` flag. Session tabs are path segments (/sessions/<path>/tunes), so the
// links are built here rather than typed in the markup. Pure, so Vitest can pin them.

export const MY_TUNES_EXPORT = '/my-tunes?export=1'

export function sessionExportHref(path, tab) {
  if (!path) return null
  const clean = String(path).replace(/^\/+|\/+$/g, '')
  return `/sessions/${clean}/${tab}?export=1`
}

/** Your sessions first, then everyone else's, with no session listed twice. */
export function pickerSections(mySessions = [], allSessions = []) {
  const mine = (mySessions || []).filter((s) => s && s.path)
  const seen = new Set(mine.map((s) => s.path))
  const rest = (allSessions || []).filter((s) => s && s.path && !seen.has(s.path))
  return { mine, rest }
}

/** Case-insensitive match on the name, then the place. */
export function matchSessions(sessions, query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return sessions
  return sessions.filter((s) => `${s.name || ''} ${s.place || ''}`.toLowerCase().includes(q))
}
