// Chip: pill states, click handling, and the ×-dismiss convention.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import Chip from '../../src/lib/Chip.svelte'

describe('Chip', () => {
  it('renders the label in a plain (non-button) pill by default', () => {
    render(Chip, { props: { label: 'Fiddle' } })
    expect(screen.getByText('Fiddle')).toBeInTheDocument()
    expect(document.querySelector('.kit-chip button.kit-chip-body')).toBeNull()
  })

  it('active and variant map to classes', () => {
    render(Chip, { props: { label: 'Reels', active: true, variant: 'primary' } })
    const chip = document.querySelector('.kit-chip')
    expect(chip).toHaveClass('active')
    expect(chip).toHaveClass('kit-chip-primary')
  })

  it('onclick makes the body a button and fires', async () => {
    const onclick = vi.fn()
    render(Chip, { props: { label: 'Jigs', onclick } })
    const btn = screen.getByRole('button', { name: 'Jigs' })
    await fireEvent.click(btn)
    expect(onclick).toHaveBeenCalledTimes(1)
  })

  it('dismissible shows the one × glyph (U+00D7, .kit-x) and fires onDismiss', async () => {
    const onDismiss = vi.fn()
    render(Chip, { props: { label: 'Polka', dismissible: true, onDismiss } })
    const x = screen.getByRole('button', { name: 'Remove Polka' })
    expect(x).toHaveClass('kit-x')
    expect(x.textContent).toBe('×')
    await fireEvent.click(x)
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('dismiss does not trigger the chip onclick (sibling, not nested)', async () => {
    const onclick = vi.fn()
    const onDismiss = vi.fn()
    render(Chip, { props: { label: 'Slide', onclick, dismissible: true, onDismiss } })
    await fireEvent.click(screen.getByRole('button', { name: 'Remove Slide' }))
    expect(onDismiss).toHaveBeenCalledTimes(1)
    expect(onclick).not.toHaveBeenCalled()
  })
})

describe('Chip — skin passthrough (spec 035 chip unification)', () => {
  it('chipClass/xClass land on wrapper and dismiss button; styled={false} drops the skin', async () => {
    const onDismiss = vi.fn()
    render(Chip, {
      props: { label: 'Reel', dismissible: true, onDismiss, styled: false, chipClass: 'filter-pill', xClass: 'filter-pill-x', title: 'a pill' },
    })
    const chip = document.querySelector('.kit-chip')
    expect(chip.className).toContain('filter-pill')
    expect(chip.className).not.toContain('kit-chip--styled')
    expect(chip).toHaveAttribute('title', 'a pill')
    const x = document.querySelector('.kit-x')
    expect(x.className).toContain('filter-pill-x')
    expect(x.textContent).toBe('\u00d7') // the ONE sanctioned close glyph
    await fireEvent.click(x)
    expect(onDismiss).toHaveBeenCalled()
  })
})
