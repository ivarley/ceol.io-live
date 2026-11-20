// Dragging a tune in the live logger: where the list scrolls while a drag is held
// near its edge, and how fast (never over the cap, however far past the edge).
import { describe, it, expect } from 'vitest'
import { edgeZone, scrollSpeed, EDGE_ZONE, SCROLL_MIN, SCROLL_MAX } from '../src/dragscroll.js'

const rect = { top: 100, bottom: 700 }

describe('edgeZone', () => {
  it('is no edge in the middle of the list', () => {
    expect(edgeZone(400, rect)).toEqual({ edge: null, depth: 0 })
    expect(edgeZone(100 + EDGE_ZONE, rect).edge).toBeNull()
    expect(edgeZone(700 - EDGE_ZONE, rect).edge).toBeNull()
  })

  it('deepens toward the edge and stops at 1 beyond it', () => {
    expect(edgeZone(100 + EDGE_ZONE / 2, rect)).toEqual({ edge: 'top', depth: 0.5 })
    expect(edgeZone(100, rect)).toEqual({ edge: 'top', depth: 1 })
    expect(edgeZone(-500, rect)).toEqual({ edge: 'top', depth: 1 })
    expect(edgeZone(700 - EDGE_ZONE / 2, rect)).toEqual({ edge: 'bottom', depth: 0.5 })
    expect(edgeZone(2000, rect)).toEqual({ edge: 'bottom', depth: 1 })
  })

  it('leaves a middle in a short list', () => {
    const short = { top: 0, bottom: 90 }
    expect(edgeZone(45, short).edge).toBeNull()
    expect(edgeZone(10, short).edge).toBe('top')
  })
})

describe('scrollSpeed', () => {
  it('starts slow, rises toward the edge, and never passes the cap', () => {
    expect(scrollSpeed(0)).toBe(SCROLL_MIN)
    expect(scrollSpeed(0.5)).toBeLessThan((SCROLL_MIN + SCROLL_MAX) / 2)
    expect(scrollSpeed(1)).toBe(SCROLL_MAX)
    expect(scrollSpeed(40)).toBe(SCROLL_MAX)
  })
})
