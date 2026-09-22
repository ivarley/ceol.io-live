// Row: lead / (title + subtitle) / trailing, with the trailing slot hard against
// the right margin whatever else the row carries.
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/svelte'
import { createRawSnippet } from 'svelte'
import { fireEvent } from '@testing-library/dom'
import Row from '../../src/lib/Row.svelte'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// jsdom does not apply a Svelte component's scoped <style>, so getComputedStyle
// cannot see this component's layout. The structural guarantees are asserted
// against the DOM below; the two CSS facts the whole component turns on are
// asserted against its source, which is crude but honest — and cheaper than the
// alternative, which is finding out in a browser six screens later.
// The <style> block only: the doc comment above it NAMES grid-template-columns
// while explaining why this component does not use one, and that mention must
// not trip the assertion below.
const SOURCE = readFileSync(resolve(__dirname, '../../src/lib/Row.svelte'), 'utf8')
const STYLE = SOURCE.slice(SOURCE.indexOf('<style>'))

describe('Row', () => {
  it('renders a title and subtitle, and omits the subtitle when empty', () => {
    render(Row, { props: { title: "Cooley's", subtitle: 'Reel · Edor' } })
    expect(document.querySelector('.kit-row-title').textContent.trim()).toBe("Cooley's")
    expect(document.querySelector('.kit-row-sub').textContent.trim()).toBe('Reel · Edor')

    document.body.innerHTML = ''
    render(Row, { props: { title: 'The Kesh' } })
    expect(document.querySelector('.kit-row-sub')).toBeNull()
  })

  // THE regression this component exists for. The prototype's first cut was a
  // 3-column grid whose empty lead was display:none; hiding a grid child removes
  // it from the grid, so the body auto-placed into column 1 and the trailing slot
  // into the stretchy middle column — the status chip landed beside the text
  // instead of at the right edge. Rows WITH a lead looked right, which is what
  // made it read as a styling whim rather than a bug.
  describe('the trailing slot stays at the right margin', () => {
    it('is the last child, and pushed right, when there is no lead', () => {
      render(Row, {
        props: {
          title: "Cooley's",
          trailing: createRawSnippet(() => ({ render: () => '<span class="chip">Know it</span>' })),
        },
      })
      const row = document.querySelector('.kit-row')
      // No lead ELEMENT at all when no lead snippet — not an empty one hidden
      // with display:none, which is precisely what broke the grid version.
      expect(row.querySelector('.kit-row-lead')).toBeNull()
      expect(row.lastElementChild.className).toContain('kit-row-trail')
    })

    it('is still the last child when there IS a lead', () => {
      render(Row, {
        props: {
          title: 'September 16',
          lead: createRawSnippet(() => ({ render: () => '<span class="date">16</span>' })),
          trailing: createRawSnippet(() => ({ render: () => '<span class="chip">Open</span>' })),
        },
      })
      const row = document.querySelector('.kit-row')
      expect(row.firstElementChild.className).toContain('kit-row-lead')
      expect(row.lastElementChild.className).toContain('kit-row-trail')
    })
  })

  describe('the two CSS facts the component turns on', () => {
    it('lays the row out with flex, never a grid whose columns a missing child can steal', () => {
      expect(STYLE).toMatch(/\.kit-row\s*\{[^}]*display:\s*flex/)
      expect(STYLE).not.toMatch(/grid-template-columns/)
      // margin-left:auto is what holds the trailing slot at the right margin
      expect(STYLE).toMatch(/\.kit-row-trail\s*\{[^}]*margin-left:\s*auto/)
    })

    it('gives the body min-width:0 so a long title ellipsizes instead of widening the row', () => {
      // Without this a long tune name sets the row's width, pushes the trailing
      // slot past the right edge, and the whole page scrolls sideways — the
      // regression e2e/mobile/*.mobile.spec.ts measures in a real browser.
      expect(STYLE).toMatch(/\.kit-row-body\s*\{[^}]*min-width:\s*0/)
      expect(STYLE).toMatch(/text-overflow:\s*ellipsis/)
    })
  })

  it('lets a page supply the whole body when it has its own layout', () => {
    // The session People row lays name / badges / instruments out INLINE on desktop
    // and stacked on a phone — a shape title+subtitle cannot express. The `body`
    // snippet hands that back to the page while Row keeps the three-slot frame.
    render(Row, {
      props: {
        title: 'ignored when body is given',
        subtitle: 'also ignored',
        body: createRawSnippet(() => ({ render: () => '<div class="person-info">Sarah</div>' })),
        trailing: createRawSnippet(() => ({ render: () => '<span class="count">12</span>' })),
      },
    })
    const row = document.querySelector('.kit-row')
    expect(row.querySelector('.kit-row-body .person-info')).toBeTruthy()
    expect(row.querySelector('.kit-row-title')).toBeNull() // not both
    expect(row.querySelector('.kit-row-sub')).toBeNull()
    expect(row.lastElementChild.className).toContain('kit-row-trail') // still right
  })

  describe('semantics follow behaviour', () => {
    it('is a real button when it does something', async () => {
      const onclick = vi.fn()
      render(Row, { props: { title: "Cooley's", onclick } })
      const row = document.querySelector('.kit-row')
      expect(row.tagName).toBe('BUTTON')
      expect(row).toHaveAttribute('type', 'button') // never submits a surrounding form
      await fireEvent.click(row)
      expect(onclick).toHaveBeenCalled()
    })

    it('is a real anchor when it navigates', () => {
      render(Row, { props: { title: 'Mueller Session', href: '/sessions/austin/mueller' } })
      const row = document.querySelector('.kit-row')
      expect(row.tagName).toBe('A')
      expect(row).toHaveAttribute('href', '/sessions/austin/mueller')
    })

    it('is a plain div when it is only text', () => {
      render(Row, { props: { title: 'Fiddle' } })
      expect(document.querySelector('.kit-row').tagName).toBe('DIV')
    })
  })

  it('keeps the page skin: legacy classes and ids pass through', () => {
    render(Row, {
      props: { title: "Cooley's", styled: false, rowClass: 'tune-row', id: 'tune-1', 'data-tune-id': 1 },
    })
    const row = document.querySelector('.kit-row')
    expect(row.className).toContain('tune-row')
    expect(row.className).not.toContain('kit-row--styled') // structure only
    expect(row).toHaveAttribute('id', 'tune-1')
    expect(row).toHaveAttribute('data-tune-id', '1')
  })
})

