// Popover: trigger click toggles the panel; Escape dismisses (bits-ui wiring).
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import { tick } from 'svelte'
import { createRawSnippet } from 'svelte'
import Popover from '../../src/lib/Popover.svelte'

const trigger = createRawSnippet(() => ({ render: () => '<span>Menu</span>' }))
const children = createRawSnippet(() => ({ render: () => '<p>Panel content</p>' }))

describe('Popover', () => {
  it('opens on trigger click and closes on a second click', async () => {
    render(Popover, { props: { trigger, children } })
    expect(screen.queryByText('Panel content')).not.toBeInTheDocument()

    await fireEvent.click(screen.getByText('Menu'))
    expect(await screen.findByText('Panel content')).toBeInTheDocument()

    await fireEvent.click(screen.getByText('Menu'))
    await tick()
    expect(screen.queryByText('Panel content')).not.toBeInTheDocument()
  })

  it('Escape dismisses', async () => {
    render(Popover, { props: { trigger, children, open: true } })
    expect(await screen.findByText('Panel content')).toBeInTheDocument()
    await fireEvent.keyDown(document, { key: 'Escape' })
    await tick()
    expect(screen.queryByText('Panel content')).not.toBeInTheDocument()
  })

  it('extends the trigger with triggerClass', () => {
    render(Popover, { props: { trigger, children, triggerClass: 'hamburger' } })
    expect(document.querySelector('.kit-popover-trigger.hamburger')).toBeTruthy()
  })
})
