// i18n-converted
// The sentences normalizeSessionPath (./sessionpath.js) returns, in the page's
// language (spec 057). sessionpath.js is held to fixtures shared with the iOS app,
// so its English stays as it is; a component showing one of its errors passes it
// through here. An error not in the list (a newer sentence) shows as sent.
import { t } from '../lib/i18n/index.js'

const SENTENCES = {
  'Path is required': () => t('Path is required'),
  "Path can't contain spaces or invisible characters": () => t("Path can't contain spaces or invisible characters"),
  'Path must be 255 characters or fewer': () => t('Path must be 255 characters or fewer'),
  "Path can't start or end with a slash": () => t("Path can't start or end with a slash"),
  'Path must have exactly two parts, a place and a name, like austin/mueller': () =>
    t('Path must have exactly two parts, a place and a name, like austin/mueller'),
  "Path can't contain an empty part (//)": () => t("Path can't contain an empty part (//)"),
  'Each part of the path must be 100 characters or fewer': () => t('Each part of the path must be 100 characters or fewer'),
  'Path can only contain letters, numbers, hyphens, underscores, periods and slashes': () =>
    t('Path can only contain letters, numbers, hyphens, underscores, periods and slashes'),
  'Each part of the path must contain a letter or number': () => t('Each part of the path must contain a letter or number'),
}

/** normalizeSessionPath's `error` in the page's language. */
export function sessionPathErrorText(error) {
  return error && SENTENCES[error] ? SENTENCES[error]() : error
}
