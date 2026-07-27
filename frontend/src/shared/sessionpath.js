// Validation for a session's URL path. Mirrors session_path.py — keep the two in
// lockstep. The server is the authority; this exists so the wizard and the admin
// details form can show the problem inline instead of after a round-trip.
//
// Why it's strict about more than emptiness: the path IS the session's URL, and
// values like "/" or "." or a pasted zero-width space are non-empty but resolve
// to nothing in a browser, leaving the session with no reachable admin screen.

const MAX_PATH_LENGTH = 255 // session.path is VARCHAR(255)
const MAX_SEGMENTS = 4
const MAX_SEGMENT_LENGTH = 100

const SEGMENT_ALLOWED = /^[A-Za-z0-9._~-]+$/ // RFC 3986 "unreserved"
const HAS_ALPHANUMERIC = /[A-Za-z0-9]/
// Control, format (zero-width spaces, bidi marks) and separator characters: they
// survive trim() but render as nothing. Tested by code point rather than a
// character class on purpose — invisible characters written into source, even as
// escapes, are unreviewable. Anything this misses SEGMENT_ALLOWED still rejects;
// this only buys a clearer message.
function isInvisible(codePoint) {
  return (
    codePoint <= 0x20 || // C0 controls and space
    (codePoint >= 0x7f && codePoint <= 0xa0) || // DEL, C1 controls, NBSP
    codePoint === 0xad || // soft hyphen
    codePoint === 0x34f || // combining grapheme joiner
    codePoint === 0x61c || // Arabic letter mark
    codePoint === 0x1680 || // Ogham space mark
    codePoint === 0x180e || // Mongolian vowel separator
    (codePoint >= 0x2000 && codePoint <= 0x200f) || // en/em spaces, ZWSP, bidi marks
    (codePoint >= 0x2028 && codePoint <= 0x202f) || // line/para separators, bidi embedding
    (codePoint >= 0x205f && codePoint <= 0x206f) || // medium math space, invisible operators
    codePoint === 0x3000 || // ideographic space
    codePoint === 0xfeff // zero-width no-break space / BOM
  )
}

function hasInvisible(text) {
  for (const character of text) {
    if (isInvisible(character.codePointAt(0))) return true
  }
  return false
}

/**
 * Validate a session path. Returns { path, error } — on success the trimmed
 * path and a null error, on failure a null path and a user-facing message.
 */
export function normalizeSessionPath(value) {
  if (typeof value !== 'string') return { path: null, error: 'Path is required' }

  const path = value.trim()
  if (!path) return { path: null, error: 'Path is required' }

  if (hasInvisible(path)) {
    return { path: null, error: "Path can't contain spaces or invisible characters" }
  }
  if (path.length > MAX_PATH_LENGTH) {
    return { path: null, error: `Path must be ${MAX_PATH_LENGTH} characters or fewer` }
  }
  if (path.startsWith('/') || path.endsWith('/')) {
    return { path: null, error: "Path can't start or end with a slash" }
  }

  const segments = path.split('/')
  if (segments.length > MAX_SEGMENTS) {
    return { path: null, error: `Path can have at most ${MAX_SEGMENTS} slash-separated parts` }
  }

  for (const segment of segments) {
    if (!segment) return { path: null, error: "Path can't contain an empty part (//)" }
    if (segment.length > MAX_SEGMENT_LENGTH) {
      return {
        path: null,
        error: `Each part of the path must be ${MAX_SEGMENT_LENGTH} characters or fewer`,
      }
    }
    if (!SEGMENT_ALLOWED.test(segment)) {
      return {
        path: null,
        error:
          'Path can only contain letters, numbers, hyphens, underscores, periods and slashes',
      }
    }
    // Kills "." and ".." segments, which a browser resolves away entirely.
    if (!HAS_ALPHANUMERIC.test(segment)) {
      return { path: null, error: 'Each part of the path must contain a letter or number' }
    }
  }

  return { path, error: null }
}
