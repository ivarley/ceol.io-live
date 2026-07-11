// List: browse mode — ArrowUp/ArrowDown move the active row, Enter/click
// select, and there is deliberately no "N of M" label.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import { createRawSnippet } from 'svelte'
import List from '../../src/lib/List.svelte'

const items = [{ name: 'The Butterfly' }, { name: 'Out on the Ocean' }, { name: 'The Silver Spear' }]
const row = createRawSnippet((item) => ({ render: () => `<span>${item().name}</span>` }))

describe('List', () => {
  it('renders one option row per item via the row snippet', () => {
    render(List, { props: { items, row } })
    expect(screen.getAllByRole('option')).toHaveLength(3)
    expect(screen.getByText('Out on the Ocean')).toBeInTheDocument()
  })

  it('ArrowDown walks the active row; Enter selects it', async () => {
    const onSelect = vi.fn()
    render(List, { props: { items, row, onSelect } })
    const box = screen.getByRole('listbox')

    await fireEvent.keyDown(box, { key: 'ArrowDown' }) // none -> 0
    await fireEvent.keyDown(box, { key: 'ArrowDown' }) // 0 -> 1
    const rows = screen.getAllByRole('option')
    expect(rows[1]).toHaveAttribute('aria-selected', 'true')
    expect(rows[1]).toHaveClass('active')

    await fireEvent.keyDown(box, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith(items[1])
  })

  it('ArrowUp from nothing lands on the last row; bounds clamp', async () => {
    render(List, { props: { items, row } })
    const box = screen.getByRole('listbox')
    await fireEvent.keyDown(box, { key: 'ArrowUp' })
    expect(screen.getAllByRole('option')[2]).toHaveAttribute('aria-selected', 'true')
    await fireEvent.keyDown(box, { key: 'ArrowDown' }) // already last: stays
    expect(screen.getAllByRole('option')[2]).toHaveAttribute('aria-selected', 'true')
  })

  it('Enter with no active row selects nothing', async () => {
    const onSelect = vi.fn()
    render(List, { props: { items, row, onSelect } })
    await fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Enter' })
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('click selects the row (and makes it active)', async () => {
    const onSelect = vi.fn()
    render(List, { props: { items, row, onSelect } })
    await fireEvent.click(screen.getByText('The Silver Spear'))
    expect(onSelect).toHaveBeenCalledWith(items[2])
    expect(screen.getAllByRole('option')[2]).toHaveClass('active')
  })

  it('renders no "N of M" label — that belongs to Pager', () => {
    render(List, { props: { items, row } })
    expect(document.querySelector('.kit-list').textContent).not.toMatch(/\d+ of \d+/)
  })
})
