// SectionHeader: a section's title, an optional icon, and an optional "See all".
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/svelte'
import { createRawSnippet } from 'svelte'
import SectionHeader from '../../src/lib/SectionHeader.svelte'

const icon = createRawSnippet(() => ({ render: () => '<svg viewBox="0 0 24 24"></svg>' }))

describe('SectionHeader', () => {
  it('renders the title as a heading', () => {
    render(SectionHeader, { props: { title: 'This week' } })
    const h = document.querySelector('.kit-sechead-title')
    expect(h.tagName).toBe('H2')
    expect(h.textContent.trim()).toBe('This week')
  })

  it('takes the heading level from the host, so a page keeps one outline', () => {
    render(SectionHeader, { props: { title: 'Attended', level: 3 } })
    expect(document.querySelector('.kit-sechead-title').tagName).toBe('H3')
  })

  it('carries an icon when given one, and no empty slot when not', () => {
    render(SectionHeader, { props: { title: 'Learning', icon } })
    expect(document.querySelector('.kit-sechead-icon svg')).toBeTruthy()

    document.body.innerHTML = ''
    render(SectionHeader, { props: { title: 'Learning' } })
    expect(document.querySelector('.kit-sechead-icon')).toBeNull()
  })

  describe('See all', () => {
    it('renders only when there is somewhere to go', () => {
      render(SectionHeader, { props: { title: 'Attended' } })
      expect(document.querySelector('.kit-sechead-seeall')).toBeNull()

      document.body.innerHTML = ''
      // The link is what makes a section a SUMMARY: show the first few rows and
      // hand off to the full list, rather than paging a long list in place.
      render(SectionHeader, { props: { title: 'Attended', seeAllHref: '/me/attended' } })
      const a = document.querySelector('.kit-sechead-seeall')
      expect(a).toHaveAttribute('href', '/me/attended')
      expect(a.textContent.trim()).toBe('See all')
    })

    it('takes its own label', () => {
      render(SectionHeader, { props: { title: 'Logs', seeAllHref: '/logs', seeAllLabel: 'All 61 nights' } })
      expect(document.querySelector('.kit-sechead-seeall').textContent.trim()).toBe('All 61 nights')
    })
  })

  it('keeps the page skin: legacy classes and attributes pass through', () => {
    render(SectionHeader, {
      props: { title: 'This week', styled: false, headerClass: 'home-card-header', id: 'week' },
    })
    const el = document.querySelector('.kit-sechead')
    expect(el.className).toContain('home-card-header')
    expect(el.className).not.toContain('kit-sechead--styled')
    expect(el).toHaveAttribute('id', 'week')
  })
})
