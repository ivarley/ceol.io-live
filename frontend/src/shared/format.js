// Shared display-formatting helpers (kit-adoption follow-up to spec 035). One
// tested copy replaces the per-bundle duplicates; semantics are the legacy ones.

/**
 * 24-hour "HH:MM" (or "HH:MM:SS") -> 12-hour "H:MMam/pm". Empty input -> ''.
 * e.g. "19:00" -> "7:00pm", "00:05:00" -> "12:05am".
 */
export function formatTime(timeStr) {
  if (!timeStr) return ''
  const parts = timeStr.split(':')
  let hour = parseInt(parts[0])
  const minute = parts[1]
  const period = hour >= 12 ? 'pm' : 'am'
  hour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour
  return `${hour}:${minute}${period}`
}

/** "19:00".."22:00" -> "7:00pm-10:00pm". */
export function formatTimeRange(startTime, endTime) {
  return formatTime(startTime) + '-' + formatTime(endTime)
}

/**
 * An instance's time range for display, from {start_time, end_time}.
 * A missing end_time is "still going" rather than unknown — the after-hours
 * session that runs until it stops — so it renders "9:30pm - ?" rather than
 * being dropped. No start time at all means the range says nothing: ''.
 */
export function instanceTimeLabel(instance) {
  if (!instance) return ''
  if (instance.start_time && instance.end_time) {
    return formatTimeRange(instance.start_time, instance.end_time)
  }
  if (instance.start_time) return formatTime(instance.start_time) + ' - ?'
  return ''
}
