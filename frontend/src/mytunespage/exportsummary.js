// The filter summary that travels with a My Tunes export: one line per filter that
// is set, in the page's language, so the file says what it is a list OF. The page
// hands in its own label functions (status/type/instrument/sort wording live in
// App.svelte with the rest of the page's words); this only decides which lines exist.
//
// KEEP IN STEP with the filters in App.svelte / logic.js (filters: search, type,
// status, instrument, rel, tag, addedDate/addedDir; sort: type, dir, type2, dir2).
// A filter the page gains should gain a line here, or the export will quietly omit it.
import { t } from '../lib/i18n/index.js'

const dirWord = (dir) => (dir === 'desc' ? t('descending') : t('ascending'))

export function myTunesExportSummary(filters, sort, labels) {
  const { statusLabel = (x) => x, typeName = (x) => x, instrumentName = (x) => x, relLabel = (x) => x, sortModeLabel = (x) => x } =
    labels || {}
  const lines = []
  if (filters.status) lines.push(t('Status: {value}', { value: statusLabel(filters.status) }))
  if (filters.type) lines.push(t('Type: {value}', { value: typeName(filters.type) }))
  if (filters.instrument) lines.push(t('Instrument: {value}', { value: instrumentName(filters.instrument) }))
  if (filters.tag) lines.push(t('Tag: {value}', { value: filters.tag }))
  if (filters.rel) lines.push(t('Played: {value}', { value: relLabel(filters.rel) }))
  if (filters.addedDate) {
    lines.push(
      filters.addedDir === 'before'
        ? t('Added before {date}', { date: filters.addedDate })
        : t('Added after {date}', { date: filters.addedDate })
    )
  }
  if (filters.search) lines.push(t('Search: {value}', { value: filters.search }))
  lines.push(t('Sort: {value}, {dir}', { value: sortModeLabel(sort.type), dir: dirWord(sort.dir) }))
  if (sort.type2) lines.push(t('Then by: {value}, {dir}', { value: sortModeLabel(sort.type2), dir: dirWord(sort.dir2) }))
  return lines
}
