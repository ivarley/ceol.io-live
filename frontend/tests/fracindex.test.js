import { describe, it, expect } from 'vitest'
import { generateAppend, generateBetween } from '../src/fracindex.js'

// order_position is compared byte-wise (COLLATE "C") on the server; for the ASCII
// base-62 alphabet, JS string `<` matches that byte order, so we assert with `<`.

describe('generateAppend', () => {
  it('starts at V for an empty/absent last key', () => {
    expect(generateAppend(null)).toBe('V')
    expect(generateAppend('')).toBe('V')
    expect(generateAppend(undefined)).toBe('V')
  })

  it('increments the final character', () => {
    expect(generateAppend('V')).toBe('W')
    expect(generateAppend('0')).toBe('1')
  })

  it('extends the key when the last char is the max (z)', () => {
    const next = generateAppend('z')
    expect(next).toBe('zV')
    expect('z' < next).toBe(true)
  })

  it('produces a strictly increasing sequence', () => {
    let prev = generateAppend(null)
    for (let i = 0; i < 500; i++) {
      const next = generateAppend(prev)
      expect(prev < next).toBe(true)
      prev = next
    }
  })
})

describe('generateBetween', () => {
  it('returns START when both ends are empty', () => {
    expect(generateBetween(null, null)).toBe('V')
  })

  it('append semantics when after is empty', () => {
    expect(generateBetween('V', null)).toBe(generateAppend('V'))
  })

  it('yields a key strictly between two adjacent keys', () => {
    const mid = generateBetween('V', 'W')
    expect('V' < mid).toBe(true)
    expect(mid < 'W').toBe(true)
  })

  it('inserts before the first key when before is empty', () => {
    const mid = generateBetween(null, 'V')
    expect(mid < 'V').toBe(true)
  })

  it('defensively appends (never throws) when before >= after', () => {
    // The exported API guards the degenerate case rather than throwing.
    expect(generateBetween('V', 'V')).toBe(generateAppend('V'))
    expect(generateBetween('W', 'V')).toBe(generateAppend('W'))
  })

  it('stays strictly ordered under repeated midpoint insertion', () => {
    // Repeatedly insert between the first two keys — the hardest case for a
    // fractional index (keys grow in length but must remain strictly between).
    let list = [generateBetween(null, null), generateAppend(generateBetween(null, null))]
    list = ['A', 'B'] // two well-separated anchors
    for (let i = 0; i < 200; i++) {
      const mid = generateBetween(list[0], list[1])
      expect(list[0] < mid).toBe(true)
      expect(mid < list[1]).toBe(true)
      list.splice(1, 0, mid) // insert; next iteration squeezes between [0] and [1] again
    }
    // whole list is strictly sorted and unique
    for (let i = 1; i < list.length; i++) expect(list[i - 1] < list[i]).toBe(true)
    expect(new Set(list).size).toBe(list.length)
  })
})
