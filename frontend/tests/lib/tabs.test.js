// Tabs: ONE responsive component — bits tablist for desktop plus a <select>
// for mobile, both always in the DOM (CSS media queries pick one; jsdom can't
// exercise those, so we assert both exist and drive the switching logic).
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import { tick } from 'svelte'
import TabsFixture from './fixtures/TabsFixture.svelte'

const tabs = [
  { id: 'tunes', label: 'Tunes' },
  { id: 'stats', label: 'Stats' },
  { id: 'people', label: 'People' },
]

describe('Tabs', () => {
  it('renders BOTH the tablist and the mobile select with matching entries', () => {
    render(TabsFixture, { props: { tabs } })
    const list = document.querySelector('.kit-tabs-list')
    const select = document.querySelector('select.kit-tabs-select')
    expect(list).toBeTruthy()
    expect(select).toBeTruthy()
    expect(list.querySelectorAll('.kit-tab')).toHaveLength(3)
    expect(select.querySelectorAll('option')).toHaveLength(3)
    expect(select.querySelector('option[value="stats"]')).toHaveTextContent('Stats')
  })

  it('defaults to the first tab', () => {
    render(TabsFixture, { props: { tabs } })
    expect(screen.getByTestId('pane')).toHaveTextContent('pane:tunes')
  })

  it('select change switches the SAME pane (mobile path)', async () => {
    const onValueChange = vi.fn()
    render(TabsFixture, { props: { tabs, onValueChange } })
    const select = document.querySelector('select.kit-tabs-select')
    await fireEvent.change(select, { target: { value: 'people' } })
    await tick()
    expect(screen.getByTestId('pane')).toHaveTextContent('pane:people')
    expect(onValueChange).toHaveBeenCalledWith('people')
    // the desktop control follows: bits stamps the active trigger
    expect(screen.getByRole('tab', { name: 'People' })).toHaveAttribute('data-state', 'active')
  })

  it('tab button click switches the pane (desktop path) and the select follows', async () => {
    render(TabsFixture, { props: { tabs } })
    await fireEvent.click(screen.getByRole('tab', { name: 'Stats' }))
    await tick()
    expect(screen.getByTestId('pane')).toHaveTextContent('pane:stats')
    expect(document.querySelector('select.kit-tabs-select').value).toBe('stats')
  })

  it('honors an initial bound value', () => {
    render(TabsFixture, { props: { tabs, initial: 'stats' } })
    expect(screen.getByTestId('pane')).toHaveTextContent('pane:stats')
  })
})

describe('Tabs — skin passthrough + navigate mode (spec 035 tabs unification)', () => {
  it('stamps data-tab and an `active` class on triggers, and appends custom classes', async () => {
    render(TabsFixture, { props: { tabs, tabClass: 'tab-button', listClass: 'tab-buttons' } })
    const trigger = screen.getByRole('tab', { name: 'Tunes' })
    expect(trigger).toHaveAttribute('data-tab', 'tunes')
    expect(trigger.className).toContain('tab-button')
    expect(trigger.className).toContain('active') // first tab is active by default
    expect(document.querySelector('.kit-tabs-list').className).toContain('tab-buttons')
    await fireEvent.click(screen.getByRole('tab', { name: 'Stats' }))
    await tick()
    expect(screen.getByRole('tab', { name: 'Tunes' }).className).not.toContain('active')
    expect(screen.getByRole('tab', { name: 'Stats' }).className).toContain('active')
  })

  it('styled={false} drops the decorative root class but keeps structure', () => {
    render(TabsFixture, { props: { tabs, styled: false } })
    const root = document.querySelector('.kit-tabs')
    expect(root.className).not.toContain('kit-tabs--styled')
    expect(document.querySelector('select.kit-tabs-select')).toBeTruthy()
  })

  it('navigate mode renders real links and the select navigates', async () => {
    const hrefTabs = [
      { id: 'details', label: 'Details', href: '/admin/sessions/x' },
      { id: 'tunes', label: 'Tunes', href: '/admin/sessions/x/tunes' },
    ]
    const onNavigate = vi.fn()
    render(TabsFixture, { props: { tabs: hrefTabs, navigate: true, initial: 'details', onNavigate } })
    const links = document.querySelectorAll('a.kit-tab')
    expect(links).toHaveLength(2)
    expect(links[1]).toHaveAttribute('href', '/admin/sessions/x/tunes')
    expect(links[0]).toHaveAttribute('aria-current', 'page')
    expect(links[0].className).toContain('active')

    const select = document.querySelector('select.kit-tabs-select')
    await fireEvent.change(select, { target: { value: 'tunes' } })
    expect(onNavigate).toHaveBeenCalledWith('/admin/sessions/x/tunes')
  })
})
