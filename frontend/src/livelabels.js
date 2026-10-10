// i18n-converted
// The live logger's fixed labels that come out of the fixture-held logic modules
// (logstate.js's pluralType / setLabel, ported to iOS and pinned by their fixtures, so
// their English outputs can't change). The components show them through these
// lookups: each a literal t() so the catalog test sees it (spec 057). Anything not
// listed shows as the module returned it.
import { t, tn, currentLang } from './lib/index.js'
import { pluralType } from './logstate.js'
import { activityText } from './people.js'
import { instanceTimeLabel } from './shared/format.js'

const PLURAL_TYPES = {
  Barndances: () => t('Barndances'),
  Hornpipes: () => t('Hornpipes'),
  Jigs: () => t('Jigs'),
  Marches: () => t('Marches'),
  Mazurkas: () => t('Mazurkas'),
  Polkas: () => t('Polkas'),
  Reels: () => t('Reels'),
  Slides: () => t('Slides'),
  'Slip Jigs': () => t('Slip Jigs'),
  Strathspeys: () => t('Strathspeys'),
  'Three-Twos': () => t('Three-Twos'),
  Waltzes: () => t('Waltzes'),
  Airs: () => t('Airs'),
  Mixed: () => t('Mixed'),
  Unknown: () => t('Unknown'),
}

/** A label logstate produced (a pluralized type, "Mixed", "Unknown") in the page's language. */
export function labelName(label) {
  if (!label) return label
  const key = Object.keys(PLURAL_TYPES).find((k) => k.toLowerCase() === String(label).toLowerCase())
  return key ? PLURAL_TYPES[key]() : label
}

/** A tune type pluralized ("Reels"), in the page's language. */
export function pluralTypeName(type) {
  return labelName(pluralType(type))
}

// The activity line ("Sarah added The Kesh"). people.js builds it in English and is
// pinned by fixtures the iOS app shares, so it stays as it is; in Irish the same
// sentence is built here from templates, verb first as Irish puts it. English is
// activityText's output unchanged.
function irishActivity(d, actor) {
  const tune = d.record?.name || (d.record?.tune_id ? `#${d.record.tune_id}` : t('a tune'))
  const person = d.person?.display_name
  const v = { actor, tune, person }
  switch (d.op_type) {
    case 'add_tune': return t('{actor} added {tune}', v)
    case 'corroborate': return t('{actor} also logged {tune}', v)
    case 'change_tune': return t('{actor} edited {tune}', v)
    case 'remove_tune': return t('{actor} removed {tune}', v)
    case 'move_tunes': return tn(d.moved_ids?.length || 0, '{actor} moved {n} tune', '{actor} moved {n} tunes', v)
    case 'remove_tunes': return tn(d.records?.length || 0, '{actor} removed {n} tune', '{actor} removed {n} tunes', v)
    case 'restore_tunes': return tn(d.records?.length || 0, '{actor} restored {n} tune', '{actor} restored {n} tunes', v)
    case 'set_break': return d.removed ? t('{actor} removed a break', v) : t('{actor} ended a set', v)
    case 'attribute_set_starter':
      return person ? t('{actor} set {person} as starting a set', v) : t('{actor} cleared a set starter', v)
    case 'set_confidence': return t('{actor} confirmed {tune}', v)
    case 'attendance_add': return person ? t('{actor} checked in {person}', v) : t('{actor} updated attendance', v)
    case 'attendance_create_person': return person ? t('{actor} added {person}', v) : t('{actor} added a player', v)
    case 'attendance_remove': return person ? t('{actor} checked out {person}', v) : t('{actor} updated attendance', v)
    case 'edit_notes': return t('{actor} edited the notes', v)
    case 'set_date': {
      const movedDate = d.previous_date != null && d.date !== d.previous_date
      const movedTimes =
        ('start_time' in d && d.start_time !== d.previous_start_time) ||
        ('end_time' in d && d.end_time !== d.previous_end_time)
      const time = instanceTimeLabel({ start_time: d.start_time, end_time: d.end_time })
      const date = d.session_date
      if (movedDate && movedTimes && date && time) return t('{actor} re-dated this log to {date}, {time}', { ...v, date, time })
      if (movedDate && date) return t('{actor} re-dated this log to {date}', { ...v, date })
      if (movedTimes) return time ? t("{actor} set this log's time to {time}", { ...v, time }) : t("{actor} cleared this log's time", v)
      return t('{actor} re-dated this log', v)
    }
    case 'set_name':
      return d.instance_name
        ? t('{actor} named this log "{name}"', { ...v, name: d.instance_name })
        : t("{actor} cleared this log's name", v)
    default: return null
  }
}

/** The activity line in the page's language, or null (people.js decides when). */
export function activityLine(d, myPersonId, viewing) {
  const english = activityText(d, myPersonId, viewing)
  if (english == null || currentLang() !== 'ga') return english
  return irishActivity(d, d.actor.name || t('Someone')) || english
}

