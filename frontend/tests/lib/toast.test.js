// toast(): delegates to the site-wide window.showMessage when present;
// otherwise renders its own auto-dismissing stack.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { toast } from '../../src/lib/toast.js'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  delete window.showMessage
  document.getElementById('kit-toasts')?.remove()
  document.getElementById('kit-toasts-style')?.remove()
})

describe('toast', () => {
  it('delegates to window.showMessage when the page provides it', () => {
    window.showMessage = vi.fn()
    toast('Saved', 'success')
    expect(window.showMessage).toHaveBeenCalledWith('Saved', 'success')
    expect(document.getElementById('kit-toasts')).toBeNull() // no fallback DOM
  })

  it('falls back to its own stacked container', () => {
    toast('Boom', 'error')
    toast('FYI', 'info')
    const host = document.getElementById('kit-toasts')
    expect(host).not.toBeNull()
    const toasts = host.querySelectorAll('.kit-toast')
    expect(toasts).toHaveLength(2)
    expect(toasts[0]).toHaveClass('kit-toast-error')
    expect(toasts[0]).toHaveTextContent('Boom')
    expect(toasts[1]).toHaveClass('kit-toast-info')
  })

  it('auto-dismisses after ~3s and removes the empty host', () => {
    toast('Gone soon')
    expect(document.querySelectorAll('.kit-toast')).toHaveLength(1)
    vi.advanceTimersByTime(3100)
    expect(document.querySelectorAll('.kit-toast')).toHaveLength(0)
    expect(document.getElementById('kit-toasts')).toBeNull()
  })

  it('staggered toasts dismiss independently', () => {
    toast('first')
    vi.advanceTimersByTime(1500)
    toast('second')
    vi.advanceTimersByTime(1600) // first expires, second still up
    const remaining = document.querySelectorAll('.kit-toast')
    expect(remaining).toHaveLength(1)
    expect(remaining[0]).toHaveTextContent('second')
  })
})

describe('toastFailure', () => {
  it('network/parse failures get a human message with a next step, not raw text', async () => {
    const { toastFailure } = await import('../../src/lib/toast.js')
    window.showMessage = vi.fn()
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    toastFailure('remove the tune', new SyntaxError('Unexpected token < in JSON'))
    expect(window.showMessage).toHaveBeenCalledWith(
      "Couldn't remove the tune. Check your connection and try again.",
      'error'
    )
    expect(spy).toHaveBeenCalled()
    spy.mockRestore()
  })

  it("a ServerError's own message is shown; empty falls back", async () => {
    const { toastFailure, ServerError } = await import('../../src/lib/toast.js')
    window.showMessage = vi.fn()
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    toastFailure('save', new ServerError('Name is required'))
    expect(window.showMessage).toHaveBeenLastCalledWith('Name is required', 'error')
    toastFailure('save', new ServerError())
    expect(window.showMessage).toHaveBeenLastCalledWith("Couldn't save. Try again.", 'error')
    spy.mockRestore()
  })
})
