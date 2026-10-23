// Where a night's page is.
//
// A night's URL is its date — /sessions/austin/mueller/2026-10-22 — because that is what
// a person would type and what reads well in a shared link. But several nights of one
// session can share a date (a festival's rooms, each a session_instance of the year),
// and then the date names none of them: the server shows the day's list instead of
// guessing. Every payload that lists nights says so per night (`multiple_on_date`), and
// the link carries the id in that case. One rule, used by Home, the directory, the
// Logs tab and the admin sheet, so a share from any of them lands on the night you
// were looking at.

/** The path of a night's page: by date, or by id when the date is shared. */
export function nightHref(sessionPath, night) {
  if (!sessionPath || !night) return null
  const part = night.multiple_on_date ? night.session_instance_id : night.date
  if (part == null || part === '') return null
  return `/sessions/${sessionPath}/${part}`
}
