// Fractional indexing — faithful JS port of fractional_indexing.py, for generating
// optimistic order_position keys client-side (so a mid-list insert renders in the
// right place before the server's authoritative position arrives). Base-62, COLLATE
// "C" byte order: 0-9 < A-Z < a-z. The server remains authoritative on settle.

const ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
const BASE = ALPHABET.length // 62
const MIDPOINT = Math.floor(BASE / 2) // 31 -> 'V'
const START = 'V'

const ci = (c) => ALPHABET.indexOf(c)
const ic = (i) => ALPHABET[i]

export function generateAppend(last) {
  if (!last) return START
  const lastChar = last[last.length - 1]
  const v = ci(lastChar)
  if (v < BASE - 1) return last.slice(0, -1) + ic(v + 1)
  return last + ic(MIDPOINT)
}

function generateBefore(after) {
  if (!after) return ic(MIDPOINT)
  const first = ci(after[0])
  if (first > 1) return ic(Math.floor(first / 2))
  if (first === 1) return ALPHABET[0] + generateBefore(after.length > 1 ? after.slice(1) : '')
  if (after.length > 1) return ALPHABET[0] + generateBefore(after.slice(1))
  return ALPHABET[0] + ic(MIDPOINT)
}

function midpoint(before, after) {
  if (after.startsWith(before) && after.length > before.length) {
    return before + generateBefore(after.slice(before.length))
  }
  const maxLen = Math.max(before.length, after.length)
  const b = before.padEnd(maxLen, ALPHABET[0])
  const a = after.padEnd(maxLen, ALPHABET[0])
  let i = 0
  while (i < maxLen && b[i] === a[i]) i++
  if (i === maxLen) throw new Error(`positions equal: ${before} ${after}`)
  const bv = ci(b[i])
  const av = ci(a[i])
  if (av - bv > 1) return b.slice(0, i) + ic(Math.floor((bv + av) / 2))
  if (before.length > i) return before + ic(MIDPOINT)
  return b.slice(0, i + 1) + ic(MIDPOINT)
}

// A key strictly between `before` and `after` (either may be null/empty for the
// start/end). Mirrors generate_position_between.
export function generateBetween(before, after) {
  if (!before && !after) return START
  if (!before) {
    const fv = ci(after[0])
    if (fv > 0) {
      const mid = Math.floor(fv / 2)
      if (mid > 0) return ic(mid)
      return '0' + ic(MIDPOINT)
    }
    if (after.length === 1) return '0' + ic(MIDPOINT)
    return '0' + generateBetween(null, after.slice(1))
  }
  if (!after) return generateAppend(before)
  if (before >= after) return generateAppend(before) // defensive; shouldn't happen
  return midpoint(before, after)
}
