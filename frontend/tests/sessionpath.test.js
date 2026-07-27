// Client mirror of session_path.py. The rule matters because a session's path is
// its URL: a non-empty but unusable one ("/", ".", a pasted zero-width space)
// resolves to nothing in a browser, and since every admin route is keyed on the
// path, the session ends up with no screen that could repair it.
import { describe, it, expect } from 'vitest'
import { normalizeSessionPath } from '../src/shared/sessionpath.js'

// Built from code points, never typed literally - an invisible character sitting
// in a source file is invisible to review too.
const ZERO_WIDTH_SPACE = String.fromCharCode(0x200b)
const BYTE_ORDER_MARK = String.fromCharCode(0xfeff)
const NON_BREAKING_SPACE = String.fromCharCode(0x00a0)

describe('normalizeSessionPath', () => {
  it.each([
    ['austin/mueller'],
    ['mueller'],
    ['austin/mcgraths-irish-pub'],
    ['st.james'],
    ['with_underscore'],
    ['a/b/c/d'],
    ['MixedCase/Path'],
  ])('accepts %s', (value) => {
    expect(normalizeSessionPath(value)).toEqual({ path: value, error: null })
  })

  it('trims surrounding whitespace', () => {
    expect(normalizeSessionPath('  austin/mueller  ')).toEqual({
      path: 'austin/mueller',
      error: null,
    })
  })

  it.each([
    ['bare slash', '/'],
    ['dot', '.'],
    ['dot dot', '..'],
    ['hyphen only', '-'],
    ['leading slash', '/austin'],
    ['trailing slash', 'austin/'],
    ['empty segment', 'austin//mueller'],
    ['dot segment', 'austin/./mueller'],
    ['space', 'austin mueller'],
    ['query string', 'austin?x=1'],
    ['fragment', 'austin#frag'],
    ['too many segments', 'a/b/c/d/e'],
    ['zero-width space', ZERO_WIDTH_SPACE],
    ['byte order mark', BYTE_ORDER_MARK],
    ['embedded zero-width', `austin${ZERO_WIDTH_SPACE}mueller`],
    ['non-breaking space', `austin${NON_BREAKING_SPACE}mueller`],
  ])('rejects %s', (_label, value) => {
    const result = normalizeSessionPath(value)
    expect(result.path).toBeNull()
    expect(result.error).toBeTruthy()
  })

  it.each([[''], ['   '], ['\t'], [null], [undefined], [0], [false], [[]], [{}]])(
    'reports %s as required',
    (value) => {
      expect(normalizeSessionPath(value)).toEqual({ path: null, error: 'Path is required' })
    }
  )

  it('rejects a path longer than the column', () => {
    const result = normalizeSessionPath('a'.repeat(256))
    expect(result.path).toBeNull()
    expect(result.error).toContain('255')
  })

  it('rejects an overlong single segment', () => {
    const result = normalizeSessionPath(`austin/${'m'.repeat(101)}`)
    expect(result.path).toBeNull()
    expect(result.error).toContain('100')
  })
})
