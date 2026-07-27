import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor, fireEvent } from '@testing-library/svelte'
import { sendOp, openStream } from '../src/client.js'

// Spec 046: the session date is editable from the logger header. Covers the three things
// that matter — the header exposes the editor, "previous day" + Save sends one set_date op
// with the right date, and a rejected collision keeps the sheet open offering Save anyway.

const bootstrapSnapshot = {
  session_id: 1,
  session_name: 'Test Session',
  session_date: 'Sun · Feb 1, 2026',
  instance_date: '2026-02-01',
  current_person: { person_id: 2, first_name: 'Ian' },
  last_event_id: 0,
  log_complete: false,
  records: [
    { session_instance_tune_id: 1, tune_id: 11, name: 'The Silver Spear', order_position: 'A', record_type: 'tune', deleted: false, tune_type: 'Reel' },
  ],
}

vi.mock('../src/client.js', () => ({
  bootstrap: vi.fn(async () => bootstrapSnapshot),
  vocabulary: vi.fn(async () => ({ known_tunes: [], known_aliases: [] })),
  openStream: vi.fn(() => ({ close: () => {} })),
  livePeople: vi.fn(async () => []),
  peopleSearch: vi.fn(async () => []),
  sendOp: vi.fn(async () => ({ success: true, date: '2026-01-31', session_date: 'Sat · Jan 31, 2026' })),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
}))

const config = {
  sessionInstanceId: 90,
  instanceDate: '2026-02-01',
  currentPerson: { person_id: 2, first_name: 'Ian' },
  streamingBaseUrl: 'http://stream.test/',
}

let App
beforeEach(async () => {
  document.body.innerHTML = ''
  vi.mocked(sendOp).mockClear()
  vi.mocked(openStream).mockClear()
  App = (await import('../src/App.svelte')).default
})

/** Expand the header and open the date sheet; returns the sheet element. */
async function openDateSheet(container) {
  await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
  await fireEvent.click(container.querySelector('.topbar-row'))
  const rows = [...container.querySelectorAll('.hx-row')]
  const dateRow = rows.find((r) => r.querySelector('.hx-label').textContent.trim() === 'Date')
  expect(dateRow).toBeTruthy()
  await fireEvent.click(dateRow.querySelector('.hx-act'))
  // The Sheet portals to the body, not into the component's container.
  await waitFor(() => expect(document.querySelector('.dt-input')).toBeTruthy())
  return document
}

describe('session date editor (spec 046)', () => {
  it('shows the current date in the expanded header, with a way to change it', async () => {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
    await fireEvent.click(container.querySelector('.topbar-row'))
    const dateRow = [...container.querySelectorAll('.hx-row')]
      .find((r) => r.querySelector('.hx-label').textContent.trim() === 'Date')
    expect(dateRow.querySelector('.hx-val').textContent.trim()).toBe('Sun · Feb 1, 2026')
    expect(dateRow.querySelector('.hx-act').textContent.trim()).toBe('Change')
  })

  it('sends one set_date op for the previous day and re-dates the header', async () => {
    const { container } = render(App, { props: { config } })
    const doc = await openDateSheet(container)
    await fireEvent.click([...doc.querySelectorAll('.dt-step')][0]) // ‹ Previous day
    expect(doc.querySelector('.dt-input').value).toBe('2026-01-31')

    await fireEvent.click(doc.querySelector('.dt-save'))
    await waitFor(() => expect(sendOp).toHaveBeenCalledTimes(1))
    const [, opType, payload] = vi.mocked(sendOp).mock.calls[0]
    expect(opType).toBe('set_date')
    expect(payload).toMatchObject({ date: '2026-01-31', confirm: false })
    // The server's display string lands on the header, and the sheet closes.
    await waitFor(() => expect(document.querySelector('.dt-input')).toBeNull())
    expect(container.querySelector('.session-date').textContent).toContain('Sat · Jan 31, 2026')
  })

  it('re-dates from someone else\'s set_date arriving over SSE', async () => {
    // A previous test's connect() can still register a stream after its component is
    // gone, so match the call by the exact config object THIS render was given.
    const myConfig = { ...config }
    const myStream = () => vi.mocked(openStream).mock.calls.find((c) => c[0] === myConfig)
    const { container } = render(App, { props: { config: myConfig } })
    await waitFor(() => expect(myStream()).toBeTruthy())
    const { onOp } = myStream()[2]

    onOp({
      op_type: 'set_date', event_id: 7, date: '2026-01-31',
      session_date: 'Sat · Jan 31, 2026', previous_date: '2026-02-01',
      actor: { person_id: 9, name: 'Aoife' },
    })
    await waitFor(() =>
      expect(container.querySelector('.session-date').textContent).toContain('Sat · Jan 31, 2026'))
    // ...and it's attributed, like every other remote change
    expect(container.querySelector('.toast.activity').textContent).toContain('Aoife')
  })

  it('keeps the sheet open on a date collision and offers Save anyway', async () => {
    vi.mocked(sendOp).mockResolvedValueOnce({
      rejected: true, reason: 'date_conflict', message: 'This session already has a log dated Sat · Jan 31, 2026.',
    })
    const { container } = render(App, { props: { config } })
    const doc = await openDateSheet(container)
    await fireEvent.click([...doc.querySelectorAll('.dt-step')][0])
    await fireEvent.click(doc.querySelector('.dt-save'))

    await waitFor(() => expect(doc.querySelector('.dt-err')).toBeTruthy())
    expect(doc.querySelector('.dt-err').textContent).toContain('already has a log dated')
    expect(doc.querySelector('.dt-save').textContent.trim()).toBe('Save anyway')

    // Confirming re-sends the SAME date, this time with confirm set.
    await fireEvent.click(doc.querySelector('.dt-save'))
    await waitFor(() => expect(sendOp).toHaveBeenCalledTimes(2))
    expect(vi.mocked(sendOp).mock.calls[1][2]).toMatchObject({ date: '2026-01-31', confirm: true })
  })
})
