// Sheet: body-scroll locking (incl. stacked sheets), Done/Cancel conventions,
// scrim/Escape = Cancel, back chevron, center-vs-dock class.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import { tick } from 'svelte'
import { createRawSnippet } from 'svelte'
import Sheet from '../../src/lib/Sheet.svelte'

const body = createRawSnippet(() => ({ render: () => '<p>sheet body</p>' }))

beforeEach(() => {
  document.body.style.overflow = ''
})

describe('Sheet', () => {
  it('renders title and children when open, nothing when closed', async () => {
    const { rerender } = render(Sheet, { props: { open: true, title: 'Tune detail', children: body } })
    expect(screen.getByText('Tune detail')).toBeInTheDocument()
    expect(screen.getByText('sheet body')).toBeInTheDocument()
    await rerender({ open: false })
    expect(screen.queryByText('sheet body')).not.toBeInTheDocument()
  })

  it('locks body scroll while open and restores on close', async () => {
    const { rerender } = render(Sheet, { props: { open: true, children: body } })
    expect(document.body.style.overflow).toBe('hidden')
    await rerender({ open: false })
    expect(document.body.style.overflow).toBe('')
  })

  it('keeps the lock until the LAST stacked sheet closes', async () => {
    const first = render(Sheet, { props: { open: true, children: body } })
    const second = render(Sheet, { props: { open: true, children: body } })
    expect(document.body.style.overflow).toBe('hidden')
    first.unmount()
    await tick()
    expect(document.body.style.overflow).toBe('hidden') // second still open
    second.unmount()
    await tick()
    expect(document.body.style.overflow).toBe('')
  })

  it('shows Done only when onDone is passed, and commits without onCancel', async () => {
    const onDone = vi.fn()
    const onCancel = vi.fn()
    const noDone = render(Sheet, { props: { open: true, children: body } })
    expect(screen.queryByText('Done')).not.toBeInTheDocument()
    noDone.unmount()

    render(Sheet, { props: { open: true, onDone, onCancel, children: body } })
    await fireEvent.click(screen.getByText('Done'))
    await tick()
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(onCancel).not.toHaveBeenCalled()
    expect(screen.queryByText('sheet body')).not.toBeInTheDocument()
    expect(document.body.style.overflow).toBe('')
  })

  it('Cancel button abandons: onCancel once, no onDone', async () => {
    const onDone = vi.fn()
    const onCancel = vi.fn()
    render(Sheet, { props: { open: true, onDone, onCancel, children: body } })
    await fireEvent.click(screen.getByText('Cancel'))
    await tick()
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onDone).not.toHaveBeenCalled()
  })

  it('Escape (a bits-internal dismiss, same path as scrim tap) = Cancel', async () => {
    const onCancel = vi.fn()
    render(Sheet, { props: { open: true, onCancel, children: body } })
    await fireEvent.keyDown(document, { key: 'Escape' })
    await tick()
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(document.body.style.overflow).toBe('')
  })

  it('back prop swaps Cancel for a back chevron', () => {
    render(Sheet, { props: { open: true, back: 'Search', children: body } })
    expect(screen.getByText('‹ Search')).toBeInTheDocument()
    expect(screen.queryByText('Cancel')).not.toBeInTheDocument()
  })

  it('desktop prop picks the center/dock class', async () => {
    const center = render(Sheet, { props: { open: true, children: body } })
    expect(document.querySelector('.kit-sheet-center')).toBeTruthy()
    center.unmount()
    render(Sheet, { props: { open: true, desktop: 'dock', children: body } })
    expect(document.querySelector('.kit-sheet-dock')).toBeTruthy()
  })
})
