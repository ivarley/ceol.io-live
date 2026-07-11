// Pager: inspect mode — ‹ › steppers, "N of M", disabled at the bounds.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import Pager from '../../src/lib/Pager.svelte'

describe('Pager', () => {
  it('shows 1-based "N of M"', () => {
    render(Pager, { props: { index: 1, count: 4 } })
    expect(screen.getByText('2 of 4')).toBeInTheDocument()
  })

  it('disables ‹ at the start and › at the end', async () => {
    const { rerender } = render(Pager, { props: { index: 0, count: 3 } })
    expect(screen.getByLabelText('Previous result')).toBeDisabled()
    expect(screen.getByLabelText('Next result')).toBeEnabled()
    await rerender({ index: 2 })
    expect(screen.getByLabelText('Previous result')).toBeEnabled()
    expect(screen.getByLabelText('Next result')).toBeDisabled()
  })

  it('steps its own bound index when no handlers are passed', async () => {
    render(Pager, { props: { index: 0, count: 3 } })
    await fireEvent.click(screen.getByLabelText('Next result'))
    expect(screen.getByText('2 of 3')).toBeInTheDocument()
    await fireEvent.click(screen.getByLabelText('Previous result'))
    expect(screen.getByText('1 of 3')).toBeInTheDocument()
  })

  it('delegates to onPrev/onNext when provided (no self-step)', async () => {
    const onPrev = vi.fn()
    const onNext = vi.fn()
    render(Pager, { props: { index: 1, count: 3, onPrev, onNext } })
    await fireEvent.click(screen.getByLabelText('Next result'))
    await fireEvent.click(screen.getByLabelText('Previous result'))
    expect(onNext).toHaveBeenCalledTimes(1)
    expect(onPrev).toHaveBeenCalledTimes(1)
    expect(screen.getByText('2 of 3')).toBeInTheDocument() // caller moves the index
  })

  it('does not fire past the bounds', async () => {
    const onPrev = vi.fn()
    render(Pager, { props: { index: 0, count: 3, onPrev } })
    await fireEvent.click(screen.getByLabelText('Previous result'))
    expect(onPrev).not.toHaveBeenCalled()
  })

  it('empty pager shows "0 of 0" with both ends disabled', () => {
    render(Pager, { props: { index: 0, count: 0 } })
    expect(screen.getByText('0 of 0')).toBeInTheDocument()
    expect(screen.getByLabelText('Previous result')).toBeDisabled()
    expect(screen.getByLabelText('Next result')).toBeDisabled()
  })

  it('label prop contextualizes the aria labels', () => {
    render(Pager, { props: { index: 0, count: 2, label: 'setting' } })
    expect(screen.getByLabelText('Next setting')).toBeInTheDocument()
  })
})
