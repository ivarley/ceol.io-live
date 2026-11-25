// The filter summaries that travel with a session export: one line per filter that
// is set, in the page's language. Two builders, one per tab that can export.
//
// KEEP IN STEP with the filters in TunesTab.svelte / logic.js (filters: search, type,
// mystatus, attended; sort: type, dir; myStatusInstrument) and in LogsTab.svelte
// (viewMode: logged | attended | all; the tune filter). A filter a tab gains should
// gain a line here, or the export will quietly omit it.
import { t } from '../lib/i18n/index.js'

const dirWord = (dir) => (dir === 'desc' ? t('descending') : t('ascending'))

export function sessionTunesExportSummary(filters, sort, myStatusInstrument, labels) {
  const { sortLabel = (x) => x, typeName = (x) => x, statusWord = (x) => x, instrumentName = (x) => x } = labels || {}
  const lines = []
  if (filters.type) lines.push(t('Type: {value}', { value: typeName(filters.type) }))
  if (filters.attended) lines.push(t('Nights I attended'))
  if (filters.mystatus) {
    lines.push(t('My Tunebook: {value}', { value: statusWord(filters.mystatus) }))
    if (myStatusInstrument && myStatusInstrument !== 'all')
      lines.push(t('Instrument: {value}', { value: instrumentName(myStatusInstrument) }))
  }
  if (filters.search) lines.push(t('Search: {value}', { value: filters.search }))
  lines.push(t('Sort: {value}, {dir}', { value: sortLabel(sort.type), dir: dirWord(sort.dir) }))
  return lines
}

export function sessionLogsExportSummary(viewMode, selectedTune, labels) {
  const { viewLabel = (x) => x } = labels || {}
  const lines = []
  // A tune filter supersedes the Logged/Attended/All toggle (logic.js keepInstance),
  // so the summary names the one that is actually in force.
  if (selectedTune) lines.push(t('Nights with {name}', { name: selectedTune.name }))
  else lines.push(t('Nights: {value}', { value: viewLabel(viewMode) }))
  return lines
}
