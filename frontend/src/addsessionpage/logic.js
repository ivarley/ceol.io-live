// Pure logic for the add-session wizard (spec 035 final migration) — ported
// behavior-for-behavior from the inline script in the legacy
// templates/add_session.html so it's unit-testable.

/**
 * Classify the wizard's one input box: a thesession.org session URL or a bare
 * numeric ID resolves to that session; anything else is a search query.
 */
export function parseSessionInput(input) {
  const trimmed = (input || '').trim()
  const urlMatch = trimmed.match(/^https?:\/\/thesession\.org\/sessions\/(\d+)(?:\/.*)?$/i)
  if (urlMatch) return { kind: 'id', id: urlMatch[1] }
  if (/^\d+$/.test(trimmed)) return { kind: 'id', id: trimmed }
  return { kind: 'search', query: trimmed }
}

/**
 * Generate the URL slug ("city/session-name") from the city and session name.
 */
export function generatePath(city, sessionName) {
  const clean = (s) =>
    (s || '')
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '') // Remove special characters
      .replace(/\s+/g, '-') // Replace spaces with hyphens
      .replace(/-+/g, '-') // Replace multiple hyphens with single
      .replace(/^-|-$/g, '') // Remove leading/trailing hyphens
  const cleanCity = clean(city)
  const cleanSessionName = clean(sessionName)
  if (cleanCity && cleanSessionName) return `${cleanCity}/${cleanSessionName}`
  return cleanSessionName || cleanCity
}

// US state -> primary timezone (split states use their primary zone).
const US_STATE_TIMEZONES = {
  // Eastern Time
  connecticut: 'America/New_York', ct: 'America/New_York',
  delaware: 'America/New_York', de: 'America/New_York',
  florida: 'America/New_York', fl: 'America/New_York',
  georgia: 'America/New_York', ga: 'America/New_York',
  indiana: 'America/New_York', in: 'America/New_York',
  kentucky: 'America/New_York', ky: 'America/New_York',
  maine: 'America/New_York', me: 'America/New_York',
  maryland: 'America/New_York', md: 'America/New_York',
  massachusetts: 'America/New_York', ma: 'America/New_York',
  michigan: 'America/New_York', mi: 'America/New_York',
  'new hampshire': 'America/New_York', nh: 'America/New_York',
  'new jersey': 'America/New_York', nj: 'America/New_York',
  'new york': 'America/New_York', ny: 'America/New_York',
  'north carolina': 'America/New_York', nc: 'America/New_York',
  ohio: 'America/New_York', oh: 'America/New_York',
  pennsylvania: 'America/New_York', pa: 'America/New_York',
  'rhode island': 'America/New_York', ri: 'America/New_York',
  'south carolina': 'America/New_York', sc: 'America/New_York',
  tennessee: 'America/New_York', tn: 'America/New_York',
  vermont: 'America/New_York', vt: 'America/New_York',
  virginia: 'America/New_York', va: 'America/New_York',
  'west virginia': 'America/New_York', wv: 'America/New_York',
  'district of columbia': 'America/New_York', dc: 'America/New_York',
  'washington dc': 'America/New_York',
  // Central Time
  alabama: 'America/Chicago', al: 'America/Chicago',
  arkansas: 'America/Chicago', ar: 'America/Chicago',
  illinois: 'America/Chicago', il: 'America/Chicago',
  iowa: 'America/Chicago', ia: 'America/Chicago',
  kansas: 'America/Chicago', ks: 'America/Chicago',
  louisiana: 'America/Chicago', la: 'America/Chicago',
  minnesota: 'America/Chicago', mn: 'America/Chicago',
  mississippi: 'America/Chicago', ms: 'America/Chicago',
  missouri: 'America/Chicago', mo: 'America/Chicago',
  nebraska: 'America/Chicago', ne: 'America/Chicago',
  'north dakota': 'America/Chicago', nd: 'America/Chicago',
  oklahoma: 'America/Chicago', ok: 'America/Chicago',
  'south dakota': 'America/Chicago', sd: 'America/Chicago',
  texas: 'America/Chicago', tx: 'America/Chicago',
  wisconsin: 'America/Chicago', wi: 'America/Chicago',
  // Mountain Time (Arizona has no DST)
  arizona: 'America/Phoenix', az: 'America/Phoenix',
  colorado: 'America/Denver', co: 'America/Denver',
  idaho: 'America/Denver', id: 'America/Denver',
  montana: 'America/Denver', mt: 'America/Denver',
  'new mexico': 'America/Denver', nm: 'America/Denver',
  utah: 'America/Denver', ut: 'America/Denver',
  wyoming: 'America/Denver', wy: 'America/Denver',
  // Pacific Time
  california: 'America/Los_Angeles', ca: 'America/Los_Angeles',
  nevada: 'America/Los_Angeles', nv: 'America/Los_Angeles',
  oregon: 'America/Los_Angeles', or: 'America/Los_Angeles',
  washington: 'America/Los_Angeles', wa: 'America/Los_Angeles',
  // Alaska & Hawaii
  alaska: 'America/Anchorage', ak: 'America/Anchorage',
  hawaii: 'Pacific/Honolulu', hi: 'Pacific/Honolulu',
}

/**
 * Guess a timezone from thesession.org's country/state strings; `fallback`
 * (the payload's default_timezone) covers everything unrecognized.
 */
export function guessTimezone(country, state, fallback = 'America/Chicago') {
  const c = (country || '').toLowerCase()
  const s = (state || '').toLowerCase()
  if (c === 'ireland') return 'Europe/Dublin'
  if (['united kingdom', 'uk', 'england', 'scotland', 'wales'].includes(c)) return 'Europe/London'
  if (['united states', 'usa', 'us'].includes(c)) return US_STATE_TIMEZONES[s] || fallback
  return fallback
}

// Day patterns to look for (longer patterns first to avoid substring issues).
const DAY_PATTERNS = [
  ['wednesday', 'wednesday'],
  ['thursdays', 'thursday'],
  ['thursday', 'thursday'],
  ['saturdays', 'saturday'],
  ['saturday', 'saturday'],
  ['tuesdays', 'tuesday'],
  ['tuesday', 'tuesday'],
  ['sundays', 'sunday'],
  ['sunday', 'sunday'],
  ['mondays', 'monday'],
  ['monday', 'monday'],
  ['fridays', 'friday'],
  ['friday', 'friday'],
  // Abbreviations (check after full names)
  ['thurs', 'thursday'],
  ['thur', 'thursday'],
  ['tues', 'tuesday'],
  ['wed', 'wednesday'],
  ['thu', 'thursday'],
  ['tue', 'tuesday'],
  ['mon', 'monday'],
  ['fri', 'friday'],
  ['sat', 'saturday'],
  ['sun', 'sunday'],
]

function findWeekday(str) {
  const lower = (str || '').toLowerCase()
  for (const [pattern, day] of DAY_PATTERNS) {
    if (lower.indexOf(pattern) !== -1) return day
  }
  return null
}

function parseTime(str) {
  // Match patterns like "8pm", "7:30pm", "2:00-4:00 pm", "7pm to 9pm", "from 8pm", "@ 8pm".
  // Range with am/pm after each time ("7pm to 9pm", "7:00pm - 9:00pm"):
  const timeRangeWithBothAmPm =
    /(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*(?:-|to|–|until)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)/i
  // Range with am/pm only at the end ("7 to 9pm", "2:00-4:00 pm"):
  const timeRangeEndAmPm =
    /(\d{1,2})(?::(\d{2}))?\s*(?:-|to|–|until)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)/i
  const singleTimePattern = /(?:@|at|from|starts?|begins?)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)/i

  let startTime = null
  let endTime = null

  let rangeMatch = str.match(timeRangeWithBothAmPm)
  if (rangeMatch) {
    let startHours = parseInt(rangeMatch[1])
    const startMins = rangeMatch[2] || '00'
    const startAmPm = rangeMatch[3]?.toLowerCase()
    let endHours = parseInt(rangeMatch[4])
    const endMins = rangeMatch[5] || '00'
    const endAmPm = rangeMatch[6]?.toLowerCase()

    if (startAmPm === 'pm' && startHours < 12) startHours += 12
    if (startAmPm === 'am' && startHours === 12) startHours = 0
    if (endAmPm === 'pm' && endHours < 12) endHours += 12
    if (endAmPm === 'am' && endHours === 12) endHours = 0

    startTime = `${startHours.toString().padStart(2, '0')}:${startMins}`
    endTime = `${endHours.toString().padStart(2, '0')}:${endMins}`
  } else {
    rangeMatch = str.match(timeRangeEndAmPm)
    if (rangeMatch) {
      let startHours = parseInt(rangeMatch[1])
      const startMins = rangeMatch[2] || '00'
      let endHours = parseInt(rangeMatch[3])
      const endMins = rangeMatch[4] || '00'
      const ampm = rangeMatch[5]?.toLowerCase()

      // Apply am/pm to both times intelligently
      if (ampm === 'pm') {
        if (endHours < 12) endHours += 12
        // If start is less than end and end is PM, start is probably PM too
        if (startHours < 12 && startHours <= endHours - 12) startHours += 12
      } else if (ampm === 'am') {
        if (startHours === 12) startHours = 0
        if (endHours === 12) endHours = 0
      }

      startTime = `${startHours.toString().padStart(2, '0')}:${startMins}`
      endTime = `${endHours.toString().padStart(2, '0')}:${endMins}`
    } else {
      const singleMatch = str.match(singleTimePattern)
      if (singleMatch) {
        let hours = parseInt(singleMatch[1])
        const mins = singleMatch[2] || '00'
        const ampm = singleMatch[3]?.toLowerCase()

        if (ampm === 'pm' && hours < 12) hours += 12
        if (ampm === 'am' && hours === 12) hours = 0

        startTime = `${hours.toString().padStart(2, '0')}:${mins}`
        // Estimate end time as 3 hours after start
        const endHours = (hours + 3) % 24
        endTime = `${endHours.toString().padStart(2, '0')}:${mins}`
      }
    }
  }

  return { startTime, endTime }
}

function parseNthPatterns(str) {
  const lower = (str || '').toLowerCase()
  const nthMap = {
    first: 1, '1st': 1,
    second: 2, '2nd': 2,
    third: 3, '3rd': 3,
    fourth: 4, '4th': 4,
    last: -1,
  }
  const which = []
  for (const [pattern, value] of Object.entries(nthMap)) {
    // Look for "every first", "first and third", "1st sunday", etc.
    const regex = new RegExp(`(every\\s+)?${pattern}\\b`, 'i')
    if (regex.test(lower)) {
      if (!which.includes(value)) which.push(value)
    }
  }
  return which
}

function isBiWeekly(str) {
  const lower = (str || '').toLowerCase()
  return lower.includes('every other') || lower.includes('bi-weekly') || lower.includes('biweekly')
}

/**
 * Parse thesession.org schedule text (plus its comments, most recent first)
 * into our schedule shape, or null when no weekday can be found. Common inputs:
 * "Every Tuesday @ 8pm", "Weekly on Thursdays", "First and third Mondays".
 */
export function parseTheSessionRecurrence(text, comments) {
  let scheduleText = ''
  if (text) {
    if (Array.isArray(text)) scheduleText = text.join(' ')
    else if (typeof text === 'string') scheduleText = text
  }

  let weekday = findWeekday(scheduleText)
  let timeInfo = parseTime(scheduleText)
  let which = parseNthPatterns(scheduleText)
  let biWeekly = isBiWeekly(scheduleText)

  if (comments && Array.isArray(comments) && comments.length > 0) {
    // First pass: the most recent comment that mentions a weekday wins.
    for (const comment of comments) {
      const content = comment.content || ''
      const commentWeekday = findWeekday(content)
      if (commentWeekday) {
        if (!weekday) weekday = commentWeekday
        // Only use this comment's details if its weekday matches (or the
        // schedule field had none).
        if (commentWeekday === weekday || !findWeekday(scheduleText)) {
          if (!timeInfo.startTime) timeInfo = parseTime(content)
          if (which.length === 0) which = parseNthPatterns(content)
          if (!biWeekly) biWeekly = isBiWeekly(content)
        }
        break
      }
    }
    // Second pass: still no time — take it from any comment.
    if (!timeInfo.startTime) {
      for (const comment of comments) {
        const commentTimeInfo = parseTime(comment.content || '')
        if (commentTimeInfo.startTime) {
          timeInfo = commentTimeInfo
          break
        }
      }
    }
    // Third pass: still no nth patterns — take them from any comment.
    if (which.length === 0) {
      for (const comment of comments) {
        const commentWhich = parseNthPatterns(comment.content || '')
        if (commentWhich.length > 0) {
          which = commentWhich
          break
        }
      }
    }
  }

  if (!weekday) return null

  const startTime = timeInfo.startTime || '19:00'
  const endTime = timeInfo.endTime || '22:00'

  if (which.length > 0) {
    return {
      type: 'monthly_nth_weekday',
      weekday,
      which,
      start_time: startTime,
      end_time: endTime,
    }
  }
  return {
    type: 'weekly',
    weekday,
    every_n_weeks: biWeekly ? 2 : 1,
    start_time: startTime,
    end_time: endTime,
  }
}

const ORDINALS = { 1: '1st', 2: '2nd', 3: '3rd', 4: '4th', '-1': 'last' }

function formatTimeOfDay(time) {
  const [hours, mins] = time.split(':')
  let h = parseInt(hours)
  const ampm = h >= 12 ? 'pm' : 'am'
  h = h % 12 || 12
  return mins === '00' ? `${h}${ampm}` : `${h}:${mins}${ampm}`
}

/**
 * Turn the recurrence editor's state into its summary line + the recurrence
 * JSON the API stores ({schedules:[…]} or null while the state is incomplete).
 */
export function summarizeRecurrence({ type, weekday, frequency = 1, which = [], startTime, endTime }) {
  if (!type) return { summary: 'No schedule set', json: null }
  if (!weekday) return { summary: 'Select a day...', json: null }

  const dayCapitalized = weekday.charAt(0).toUpperCase() + weekday.slice(1)
  const schedule = { type, weekday, start_time: startTime, end_time: endTime }
  let summary = ''

  if (type === 'weekly') {
    schedule.every_n_weeks = frequency
    if (frequency === 1) summary = `${dayCapitalized}s`
    else if (frequency === 2) summary = `Every other ${dayCapitalized}`
    else summary = `Every ${frequency} weeks on ${dayCapitalized}`
  } else if (type === 'monthly_nth_weekday') {
    if (which.length === 0) return { summary: 'Select which occurrences...', json: null }
    schedule.which = which
    summary = `${which.map((n) => ORDINALS[n]).join(' & ')} ${dayCapitalized}`
  }

  summary += ` from ${formatTimeOfDay(startTime)}-${formatTimeOfDay(endTime)}`
  return { summary, json: JSON.stringify({ schedules: [schedule] }) }
}
