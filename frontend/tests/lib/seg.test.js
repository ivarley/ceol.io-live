// Seg: controlled segmented control — host owns value; onSelect fires on EVERY
// option click (some hosts toggle-off on the active one).
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import Seg from '../../src/lib/Seg.svelte'

const options = [
  { id: 'want to learn', label: 'Want To Learn' },
  { id: 'learning', label: 'Learning' },
  { id: 'learned', label: 'Learned' },
]

describe('Seg', () => {
  it('renders options with the id attribute and marks the active one', () => {
    render(Seg, { props: { options, value: 'learning', idAttr: 'data-status', optClass: 'tunebook-status-opt' } })
    const opts = document.querySelectorAll('.kit-seg-opt')
    expect(opts).toHaveLength(3)
    expect(opts[1]).toHaveAttribute('data-status', 'learning')
    expect(opts[1].className).toContain('active')
    expect(opts[0].className).not.toContain('active')
    expect(opts[0].className).toContain('tunebook-status-opt')
  })

  it('fires onSelect on every click, INCLUDING the active option', async () => {
    const onSelect = vi.fn()
    render(Seg, { props: { options, value: 'learning', onSelect } })
    const opts = document.querySelectorAll('.kit-seg-opt')
    await fireEvent.click(opts[2])
    expect(onSelect).toHaveBeenCalledWith('learned')
    await fireEvent.click(opts[1]) // the active one — hosts may toggle-off
    expect(onSelect).toHaveBeenCalledWith('learning')
    expect(onSelect).toHaveBeenCalledTimes(2)
  })

  it('is controlled: value does not change itself on click', async () => {
    render(Seg, { props: { options, value: 'learning' } })
    const opts = document.querySelectorAll('.kit-seg-opt')
    await fireEvent.click(opts[2])
    expect(opts[1].className).toContain('active') // still the host-set value
    expect(opts[2].className).not.toContain('active')
  })

  it('marks the secondary selection and passes container attrs/skin flags', () => {
    render(Seg, {
      props: {
        options: [
          { id: 'alpha', label: 'a-z' },
          { id: 'heard', label: 'heard' },
        ],
        value: 'alpha',
        secondary: 'heard',
        idAttr: 'data-sort',
        styled: false,
        segClass: 'filter-button-group',
        role: 'group',
        'aria-label': 'Sort',
      },
    })
    const seg = document.querySelector('.kit-seg')
    expect(seg.className).toContain('filter-button-group')
    expect(seg.className).not.toContain('kit-seg--styled')
    expect(seg).toHaveAttribute('role', 'group')
    expect(seg).toHaveAttribute('aria-label', 'Sort')
    const heard = document.querySelector('[data-sort="heard"]')
    expect(heard.className).toContain('active-secondary')
  })
})
