// Export mode (the profile's "Export my data"): the pages you already use, with an
// export bar at the bottom. The mode is one URL flag, `export=1`, kept beside the
// page's own filter params so the filters a person set are the ones that go into the
// file. Nothing here knows which page it is on; the page says what it is exporting
// (ids in display order, a human summary of the filters) and this module runs the
// server round trip and hands the browser the file.
//
// The server contract (export_routes.py):
//   POST <url> {format, <ids>, filters}            -> the file (attachment)
//   POST <url> {format:'pdf', <ids>, check:true}   -> {missing_setting_ids, total}
// A PDF embeds each tune's notation image; a setting whose image was never rendered
// is rendered on first request by GET /api/tunes/settings/<id>/image?kind=full, so
// a big export warms those first (showing progress) rather than making one request
// that times out on the fiftieth tune.

export const EXPORT_PARAM = 'export'
export const EXPORT_EVENT = 'ceol-export-mode'

/** Is the page in export mode right now (`?export=1`)? */
export function isExportMode(search = typeof window !== 'undefined' ? window.location.search : '') {
  return new URLSearchParams(search).get(EXPORT_PARAM) === '1'
}

/** The current URL with the export flag removed and every other param kept. */
export function urlWithoutExport(loc = window.location) {
  const params = new URLSearchParams(loc.search)
  params.delete(EXPORT_PARAM)
  const q = params.toString()
  return loc.pathname + (q ? '?' + q : '') + (loc.hash || '')
}

/** Leave export mode: drop the flag, keep the filters, and tell the page. */
export function leaveExportMode() {
  window.history.replaceState({}, '', urlWithoutExport())
  window.dispatchEvent(new Event(EXPORT_EVENT))
}

/** Keep the flag on a URLSearchParams a page is about to write to the address bar. */
export function withExportParam(params, on = isExportMode()) {
  if (on) params.set(EXPORT_PARAM, '1')
  else params.delete(EXPORT_PARAM)
  return params
}

/**
 * Subscribe to the mode changing under the page: Back/Forward, or leaveExportMode().
 * Returns the unsubscribe function, for an $effect's cleanup.
 */
export function onExportModeChange(fn) {
  const handler = () => fn(isExportMode())
  window.addEventListener('popstate', handler)
  window.addEventListener(EXPORT_EVENT, handler)
  return () => {
    window.removeEventListener('popstate', handler)
    window.removeEventListener(EXPORT_EVENT, handler)
  }
}

export const FORMATS = ['json', 'csv', 'pdf']

/** Pull the server's filename out of Content-Disposition, RFC 5987 form first. */
export function filenameFrom(disposition) {
  if (!disposition) return null
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  if (star) {
    try {
      return decodeURIComponent(star[1])
    } catch {
      /* fall through */
    }
  }
  // Flask quotes the plain form only when the name needs it, so accept both.
  const plain = /filename=(?:"([^"]+)"|([^;\s]+))/i.exec(disposition)
  return plain ? plain[1] || plain[2] : null
}

/** Hand a blob to the browser as a download. */
export function triggerDownload(blob, filename, doc = document) {
  const url = URL.createObjectURL(blob)
  const a = doc.createElement('a')
  a.href = url
  a.download = filename
  doc.body.appendChild(a)
  a.click()
  a.remove()
  // Firefox needs the object URL to outlive the click; revoking immediately
  // cancels the save it just started.
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}

/** The error envelope's wording, else nothing (the caller has a fallback). */
async function serverMessage(res) {
  try {
    const d = await res.json()
    return d?.message || d?.error || null
  } catch {
    return null
  }
}

export class ExportError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function post(fetchFn, url, body) {
  return fetchFn(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/**
 * Warm the full-notation images the PDF will embed. Two at a time: the renderer is
 * one Node process, and the point is progress, not speed. A failure on one setting
 * is not fatal here; the server renders or skips it when it builds the file.
 */
export async function warmNotation(ids, { fetchFn = fetch, onProgress = () => {}, concurrency = 2 } = {}) {
  const total = ids.length
  let done = 0
  let next = 0
  onProgress({ done, total })
  const worker = async () => {
    while (next < ids.length) {
      const id = ids[next++]
      try {
        await fetchFn(`/api/tunes/settings/${id}/image?kind=full`, { credentials: 'same-origin' })
      } catch {
        /* the server will try again while building the file */
      }
      done++
      onProgress({ done, total })
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, ids.length) }, worker))
}

/**
 * Run one export: check (PDF only) → warm → fetch the file → download it.
 * `body` carries the page's ids and filter summary; `format` is added here.
 * `onProgress` gets {done,total} while warming and null when that is over.
 * Resolves to the filename; throws ExportError with the server's wording.
 */
export async function runExport({ url, body, format, onProgress = () => {}, fetchFn = fetch, fallbackName = 'ceol-export' }) {
  if (!FORMATS.includes(format)) throw new ExportError(`Unknown format ${format}`, 0)
  if (format === 'pdf') {
    const check = await post(fetchFn, url, { ...body, format, check: true })
    if (!check.ok) throw new ExportError(await serverMessage(check), check.status)
    const d = await check.json()
    const missing = Array.isArray(d.missing_setting_ids) ? d.missing_setting_ids : []
    if (missing.length) await warmNotation(missing, { fetchFn, onProgress })
    onProgress(null)
  }
  const res = await post(fetchFn, url, { ...body, format })
  if (!res.ok) throw new ExportError(await serverMessage(res), res.status)
  const blob = await res.blob()
  const filename = filenameFrom(res.headers.get('Content-Disposition')) || `${fallbackName}.${format}`
  triggerDownload(blob, filename)
  return filename
}
