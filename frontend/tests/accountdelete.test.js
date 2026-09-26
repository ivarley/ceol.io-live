// Delete Account on /me (spec 054): the row, the typed-email gate, and the call.
// The deletion rules themselves are the server's (tests/integration/
// test_account_deletion_054.py); this pins what the page does around them.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import AccountSection from '../src/personpage/AccountSection.svelte'

const EMAIL = 'dora@example.com'

let fetchMock

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) })
  vi.stubGlobal('fetch', fetchMock)
  window.showMessage = vi.fn()
})

afterEach(() => {
  vi.unstubAllGlobals()
  delete window.showMessage
})

const confirmButton = () => document.body.querySelector('.kit-dialog-confirm')
const emailInput = () => document.body.querySelector('#account-delete-email')

async function openDialog() {
  const { container } = render(AccountSection, { personName: 'Dora Doomed', userEmail: EMAIL })
  await fireEvent.click(container.querySelector('#account-delete'))
  await waitFor(() => expect(emailInput()).toBeTruthy())
}

describe('Delete Account', () => {
  it('is offered on your own profile', () => {
    const { container } = render(AccountSection, { userEmail: EMAIL })
    expect(container.querySelector('#account-delete')).toBeTruthy()
  })

  it('is not offered to a system admin, whom the server would refuse', () => {
    const { container } = render(AccountSection, { isSystemAdmin: true, userEmail: EMAIL })
    expect(container.querySelector('#account-delete')).toBeNull()
  })

  it('is not offered without an account email to confirm with', () => {
    const { container } = render(AccountSection, { userEmail: '' })
    expect(container.querySelector('#account-delete')).toBeNull()
  })

  it('stays disabled until the email is typed, in any case', async () => {
    await openDialog()
    expect(confirmButton().disabled).toBe(true)
    await fireEvent.input(emailInput(), { target: { value: 'dora@example' } })
    expect(confirmButton().disabled).toBe(true)
    await fireEvent.input(emailInput(), { target: { value: ' Dora@Example.com ' } })
    expect(confirmButton().disabled).toBe(false)
  })

  it('sends what was typed, for the server to check again', async () => {
    await openDialog()
    await fireEvent.input(emailInput(), { target: { value: EMAIL } })
    await fireEvent.click(confirmButton())
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/me/delete-account')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ confirm_email: EMAIL })
  })

  it("says so when the server refuses, and doesn't pretend it worked", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ success: false, error: 'Nope', code: 'admin_account' }),
    })
    await openDialog()
    await fireEvent.input(emailInput(), { target: { value: EMAIL } })
    await fireEvent.click(confirmButton())
    await waitFor(() => expect(window.showMessage).toHaveBeenCalledWith('Nope', 'error'))
  })

  it('says nothing was deleted when the server cannot be reached', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await openDialog()
    await fireEvent.input(emailInput(), { target: { value: EMAIL } })
    await fireEvent.click(confirmButton())
    await waitFor(() =>
      expect(window.showMessage).toHaveBeenCalledWith("Couldn't reach the server, so nothing was deleted.", 'error')
    )
  })
})
