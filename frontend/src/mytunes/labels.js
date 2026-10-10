// Interface words for the My Tunes area (spec 057), in the page's language.
import { t, ServerError } from '../lib/index.js'

/** A stored learn status ('want to learn') as the page's wording ("To Learn"). The
 * English matches STATUS_LABELS in mylist.js; anything unknown shows as stored. */
export function statusLabel(status) {
  if (status === 'want to learn') return t('To Learn')
  if (status === 'learning') return t('Learning')
  if (status === 'learned') return t('Learned')
  return status
}

/** What to show when a request fails: the server's (or our own) explanation when
 * there is one, else a sentence built from `what`, an already-translated phrase that
 * completes "Couldn't …" ("add the tune"). Raw error text only reaches the console. */
export function failText(e, what) {
  console.error(`Couldn't ${what}:`, e)
  if (e instanceof ServerError && e.message) return e.message
  return t("Couldn't {what}. Check your connection and try again.", { what })
}
