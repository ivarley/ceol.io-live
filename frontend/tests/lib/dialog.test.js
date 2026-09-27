// Dialog: one decision — confirm verb fires onConfirm, cancel/Escape fire
// onCancel, destructive styles the confirm.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import { tick } from 'svelte'
import Dialog from '../../src/lib/Dialog.svelte'

describe('Dialog', () => {
  it('renders title/description when open, nothing when closed', async () => {
    const { rerender } = render(Dialog, {
      props: { open: true, title: 'Delete session?', description: 'This cannot be undone.' },
    })
    expect(screen.getByText('Delete session?')).toBeInTheDocument()
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument()
    await rerender({ open: false })
    expect(screen.queryByText('Delete session?')).not.toBeInTheDocument()
  })

  it('confirm fires onConfirm (not onCancel) and closes', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(Dialog, {
      props: { open: true, title: 'Delete session?', confirmLabel: 'Delete session', onConfirm, onCancel },
    })
    await fireEvent.click(screen.getByText('Delete session'))
    await tick()
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCancel).not.toHaveBeenCalled()
    expect(screen.queryByText('Delete session')).not.toBeInTheDocument()
  })

  it('cancel button fires onCancel and closes', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(Dialog, { props: { open: true, title: 'Sure?', onConfirm, onCancel } })
    await fireEvent.click(screen.getByText('Cancel'))
    await tick()
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('Escape = Cancel', async () => {
    const onCancel = vi.fn()
    render(Dialog, { props: { open: true, title: 'Sure?', onCancel } })
    await fireEvent.keyDown(document, { key: 'Escape' })
    await tick()
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('destructive flags the confirm button', () => {
    render(Dialog, { props: { open: true, title: 'Delete?', confirmLabel: 'Delete tune', destructive: true } })
    const confirm = screen.getByText('Delete tune')
    expect(confirm).toHaveClass('kit-dialog-confirm')
    expect(confirm).toHaveClass('destructive')
  })

  it('non-destructive confirm has no destructive class', () => {
    render(Dialog, { props: { open: true, title: 'Save?', confirmLabel: 'Save changes' } })
    expect(screen.getByText('Save changes')).not.toHaveClass('destructive')
  })

  it('async confirm stays open and busy until the request resolves, then closes', async () => {
    let resolve
    const onConfirm = vi.fn(() => new Promise((r) => (resolve = r)))
    render(Dialog, {
      props: { open: true, title: 'Remove?', confirmLabel: 'Remove', busyLabel: 'Removing…', onConfirm },
    })
    await fireEvent.click(screen.getByText('Remove'))
    await tick()
    const busy = screen.getByText('Removing…')
    expect(busy).toBeDisabled()
    expect(screen.getByText('Cancel')).toBeDisabled()
    resolve()
    await new Promise((r) => setTimeout(r, 0))
    await tick()
    expect(screen.queryByText('Remove?')).not.toBeInTheDocument()
  })

  it('async confirm that fails (false or rejects) stays open for a retry', async () => {
    const onConfirm = vi.fn(() => Promise.resolve(false))
    const onCancel = vi.fn()
    render(Dialog, { props: { open: true, title: 'Remove?', confirmLabel: 'Remove', onConfirm, onCancel } })
    await fireEvent.click(screen.getByText('Remove'))
    await new Promise((r) => setTimeout(r, 0))
    await tick()
    expect(screen.getByText('Remove?')).toBeInTheDocument()
    expect(screen.getByText('Remove')).not.toBeDisabled()
    expect(onCancel).not.toHaveBeenCalled()
  })
})
