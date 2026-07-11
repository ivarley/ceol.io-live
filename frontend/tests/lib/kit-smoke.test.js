// Import smoke test: every export in src/lib/index.js compiles under the real
// svelte plugin and mounts with minimal props — the kit isn't imported by a
// page entry yet, so this is what keeps it honest until Step 2 wires it in.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/svelte'
import * as kit from '../../src/lib/index.js'

const COMPONENTS = {
  Sheet: { open: false },
  Dialog: { open: false },
  Popover: {},
  Card: {},
  Chip: { label: 'x' },
  Tabs: { tabs: [{ id: 'a', label: 'A' }] },
  List: { items: [] },
  Pager: { index: 0, count: 0 },
  SearchField: {},
}

describe('kit exports', () => {
  it('exports exactly the documented surface', () => {
    expect(Object.keys(kit).sort()).toEqual([...Object.keys(COMPONENTS), 'toast'].sort())
  })

  for (const [name, props] of Object.entries(COMPONENTS)) {
    it(`${name} mounts with minimal props`, () => {
      const { container, unmount } = render(kit[name], { props })
      expect(container).toBeTruthy()
      unmount()
    })
  }

  it('toast is a callable function', () => {
    expect(typeof kit.toast).toBe('function')
  })
})
