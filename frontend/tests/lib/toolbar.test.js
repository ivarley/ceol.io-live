// Toolbar: one line above a list — search, plus optional filter / sort / add —
// with the filter panel expanding directly beneath it.
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/svelte'
import { createRawSnippet } from 'svelte'
import { fireEvent } from '@testing-library/dom'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import Toolbar from '../../src/lib/Toolbar.svelte'

const filter = createRawSnippet(() => ({ render: () => '<div class="my-filters">type</div>' }))
const STYLE = (() => {
  const src = readFileSync(resolve(__dirname, '../../src/lib/Toolbar.svelte'), 'utf8')
  return src.slice(src.indexOf('<style>'))
})()

describe('Toolbar', () => {
  it('is just a search box until you ask for more', () => {
    render(Toolbar, { props: { placeholder: 'Filter tunes' } })
    expect(document.querySelector('.kit-toolbar input')).toBeTruthy()
    expect(document.querySelector('.kit-tool-filter')).toBeNull()
    expect(document.querySelector('.kit-tool-sort')).toBeNull()
    expect(document.querySelector('.kit-tool-add')).toBeNull()
    expect(document.querySelector('.kit-filter-panel')).toBeNull()
  })

  it('renders the controls it is given, in toolbar order', () => {
    render(Toolbar, { props: { filter, onSort: () => {}, onAdd: () => {} } })
    const order = [...document.querySelectorAll('.kit-toolbar > *')].map((n) =>
      n.className.replace(/\s.*/, ''),
    )
    expect(order.slice(1)).toEqual(['kit-tool-btn', 'kit-tool-btn', 'kit-tool-btn'])
    expect(document.querySelector('.kit-tool-filter')).toBeTruthy()
    expect(document.querySelector('.kit-tool-sort')).toBeTruthy()
    expect(document.querySelector('.kit-tool-add')).toBeTruthy()
  })

  describe('the filter panel belongs to the line that opened it', () => {
    it('sits directly after the toolbar in the DOM, not at the end of the page', () => {
      // The whole reason this is a component: a control at the top of the screen
      // must not open a panel at the bottom of it. (A popover is no escape
      // either — on iPhone one anchored to a control adapts into a bottom sheet.)
      render(Toolbar, { props: { filter } })
      const wrap = document.querySelector('.kit-toolbar-wrap')
      expect(wrap.children[0].className).toContain('kit-toolbar')
      expect(wrap.children[1].className).toContain('kit-filter-panel')
    })

    it('opens and closes by class, so both directions can animate', async () => {
      render(Toolbar, { props: { filter } })
      const panel = document.querySelector('.kit-filter-panel')
      const btn = document.querySelector('.kit-tool-filter')
      expect(panel.className).not.toContain('open')
      expect(btn).toHaveAttribute('aria-expanded', 'false')

      await fireEvent.click(btn)
      // the SAME node, re-classed — not a fresh one, which would animate only once
      expect(document.querySelector('.kit-filter-panel')).toBe(panel)
      expect(panel.className).toContain('open')
      expect(btn).toHaveAttribute('aria-expanded', 'true')

      await fireEvent.click(btn)
      expect(panel.className).not.toContain('open')
    })

    it('renders the host\'s own controls inside it', () => {
      render(Toolbar, { props: { filter, open: true } })
      expect(document.querySelector('.kit-filter-panel .my-filters')).toBeTruthy()
    })

    it('animates a panel of unknown height', () => {
      // grid-template-rows 0fr -> 1fr, because max-height needs a magic number
      // that either clips a tall panel or lags a short one.
      expect(STYLE).toMatch(/grid-template-rows:\s*0fr/)
      expect(STYLE).toMatch(/\.kit-filter-panel\.open\s*\{[^}]*grid-template-rows:\s*1fr/)
    })
  })

  describe('active filters are visible without opening the panel', () => {
    it('dots the button and offers Clear only when something is set', async () => {
      const onClear = vi.fn()
      const { rerender } = render(Toolbar, { props: { filter, open: true, activeCount: 0, onClear } })
      expect(document.querySelector('.kit-tool-badge')).toBeNull()
      expect(document.querySelector('.kit-filter-clear')).toBeNull()

      await rerender({ filter, open: true, activeCount: 2, onClear })
      expect(document.querySelector('.kit-tool-badge')).toBeTruthy()
      expect(document.querySelector('.kit-tool-filter').className).toContain('on')

      await fireEvent.click(document.querySelector('.kit-filter-clear'))
      expect(onClear).toHaveBeenCalled()
    })
  })

  it('marks sort only when it is not the default', async () => {
    const onSort = vi.fn()
    const { rerender } = render(Toolbar, { props: { onSort, sortActive: false } })
    expect(document.querySelector('.kit-tool-sort').className).not.toContain('on')
    await rerender({ onSort, sortActive: true })
    expect(document.querySelector('.kit-tool-sort').className).toContain('on')
    // the host opens its own menu from the button — Toolbar only reports the press
    await fireEvent.click(document.querySelector('.kit-tool-sort'))
    expect(onSort).toHaveBeenCalled()
  })

  it('points the notch at the filter button, counting what follows it', () => {
    // filter is last: 21px from the right edge
    render(Toolbar, { props: { filter } })
    expect(document.querySelector('.kit-filter-panel').getAttribute('style')).toContain('21px')

    document.body.innerHTML = ''
    // filter, then sort and add: 21 + 2 * 50
    render(Toolbar, { props: { filter, onSort: () => {}, onAdd: () => {} } })
    expect(document.querySelector('.kit-filter-panel').getAttribute('style')).toContain('121px')
  })

  it('reports settled search text through SearchField', async () => {
    const onSearch = vi.fn()
    render(Toolbar, { props: { onSearch, debounce: 0 } })
    const input = document.querySelector('.kit-toolbar input')
    await fireEvent.input(input, { target: { value: 'cooley' } })
    await fireEvent.keyDown(input, { key: 'Enter' }) // Enter flushes the debounce
    expect(onSearch).toHaveBeenCalledWith('cooley')
  })
})
