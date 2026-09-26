// Tabs: ONE control at every width — a bits tablist that scrolls sideways on a
// phone when the tabs do not fit.
//
// It used to render a second control alongside it, a <select> that took over under
// 768px. That is retired (spec 052 §B3): no iOS idiom turns a tab bar into a
// dropdown, so a page navigated by one could not be ported, only redesigned. The
// tests that drove the select are gone with it; what is left drives the tabs.
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
  it('renders one tab per entry, and no second control beside them', () => {
    render(TabsFixture, { props: { tabs } })
    const list = document.querySelector('.kit-tabs-list')
    expect(list).toBeTruthy()
    expect(list.querySelectorAll('.kit-tab')).toHaveLength(3)
    // The mobile <select> is retired; nothing should render one.
    expect(document.querySelector('select.kit-tabs-select')).toBeNull()
  })

  it('defaults to the first tab', () => {
    render(TabsFixture, { props: { tabs } })
    expect(screen.getByTestId('pane')).toHaveTextContent('pane:tunes')
  })

  it('a tab click switches the pane and reports the change', async () => {
    const onValueChange = vi.fn()
    render(TabsFixture, { props: { tabs, onValueChange } })
    await fireEvent.click(screen.getByRole('tab', { name: 'People' }))
    await tick()
    expect(screen.getByTestId('pane')).toHaveTextContent('pane:people')
    expect(onValueChange).toHaveBeenCalledWith('people')
    expect(screen.getByRole('tab', { name: 'People' })).toHaveAttribute('data-state', 'active')
  })

  it('honors an initial bound value', () => {
    render(TabsFixture, { props: { tabs, initial: 'stats' } })
    expect(screen.getByTestId('pane')).toHaveTextContent('pane:stats')
  })
})

describe('Tabs — many tabs still render as tabs', () => {
  // The case the <select> existed for. Six tabs do not fit a phone; they scroll,
  // which is a thing both platforms do, rather than turning into another control.
  const sixTabs = ['a', 'b', 'c', 'd', 'e', 'f'].map((id) => ({ id, label: id.toUpperCase() }))

  it('renders six tabs and no dropdown', () => {
    render(TabsFixture, { props: { tabs: sixTabs } })
    expect(document.querySelectorAll('.kit-tab')).toHaveLength(6)
    expect(document.querySelector('select')).toBeNull()
  })

  it('has no mobile-select class left to scope a rule with', () => {
    render(TabsFixture, { props: { tabs: sixTabs } })
    expect(document.querySelector('.kit-tabs').className).not.toContain('mselect')
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
    expect(document.querySelector('.kit-tabs-list')).toBeTruthy()
  })

  it('navigate mode renders real links', async () => {
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
    // Navigation is the browser following the href; there is no longer a second
    // control that has to be taught to navigate on its behalf.
    expect(onNavigate).not.toHaveBeenCalled()
  })
})
