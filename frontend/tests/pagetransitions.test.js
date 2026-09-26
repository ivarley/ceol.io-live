// static/js/page_transitions.js — which page-to-page navigations slide on a phone,
// and which way (spec 052 §B8 Stage 6). Only the direction rule is tested here; the
// transition itself is the browser's.
import { describe, it, expect, beforeAll } from 'vitest'

let slideDirection
beforeAll(async () => {
  await import('../../static/js/page_transitions.js')
  slideDirection = window.CeolPageTransitions.slideDirection
})

const u = (path) => `https://ceol.io${path}`

describe('slideDirection', () => {
  it('pushes into a session from the list, and pops back out', () => {
    expect(slideDirection(u('/sessions'), u('/sessions/austin/mueller'))).toBe('push')
    expect(slideDirection(u('/sessions/austin/mueller'), u('/sessions'))).toBe('pop')
  })

  it('pushes into a log from any of the session page tabs', () => {
    expect(slideDirection(u('/sessions/austin/mueller/logs'), u('/sessions/austin/mueller/2026-09-20'))).toBe('push')
    expect(slideDirection(u('/sessions/austin/mueller'), u('/sessions/austin/mueller/2026-09-20'))).toBe('push')
    expect(slideDirection(u('/sessions/austin/mueller/2026-09-20'), u('/sessions/austin/mueller/tunes'))).toBe('pop')
  })

  it('treats a trailing slash as the same path', () => {
    expect(slideDirection(u('/sessions/'), u('/sessions/austin/mueller/'))).toBe('push')
  })

  it('does not slide between tabs', () => {
    expect(slideDirection(u('/sessions'), u('/my-tunes'))).toBe(null)
    expect(slideDirection(u('/sessions/austin/mueller'), u('/me'))).toBe(null)
  })

  it('never slides to or from Home, which is a tab and not every page\'s parent', () => {
    expect(slideDirection(u('/'), u('/sessions'))).toBe(null)
    expect(slideDirection(u('/sessions/austin/mueller'), u('/'))).toBe(null)
  })

  it('does not slide between siblings, or to the same page with a new query', () => {
    expect(slideDirection(u('/sessions/austin/mueller/2026-09-20'), u('/sessions/austin/mueller/2026-09-13'))).toBe(null)
    expect(slideDirection(u('/my-tunes'), u('/my-tunes?status=learning'))).toBe(null)
  })

  it('does not mistake a shared prefix for a parent', () => {
    expect(slideDirection(u('/me'), u('/media'))).toBe(null)
  })

  it('only strips a tab suffix from a session path', () => {
    expect(slideDirection(u('/admin/logs'), u('/admin'))).toBe('pop')
  })

  it('needs both ends, on one origin', () => {
    expect(slideDirection(null, u('/sessions/x'))).toBe(null)
    expect(slideDirection('https://example.com/sessions', u('/sessions/x'))).toBe(null)
  })
})
