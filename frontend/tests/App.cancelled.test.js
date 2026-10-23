import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from '../src/App.svelte' // static: loading it per test can outrun the hook timeout
import { render, waitFor, fireEvent } from '@testing-library/svelte'
import { sendOp, openStream } from '../src/client.js'

// A night called off (session_instance.is_cancelled). The column has always been
// honoured by every reader, but after spec 035 retired the legacy night page nothing
// could set it. The header's Cancelled row does now, through one live op, and the
// band strikes the date through so the state is visible without opening the drawer.

const bootstrapSnapshot = {
  session_id: 1,
  session_name: "B.D. Riley's",
  session_date: 'Thu · Oct 22, 2026',
  instance_date: '2026-10-22',
  instance_name: null,
  is_cancelled: false,
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
  sendOp: vi.fn(async (_c, _t, payload) => ({ success: true, is_cancelled: payload.cancelled, previous_cancelled: !payload.cancelled })),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
}))

const config = {
  sessionInstanceId: 103,
  instanceDate: '2026-10-22',
  instanceName: null,
  instanceCancelled: false,
  currentPerson: { person_id: 2, first_name: 'Ian' },
  streamingBaseUrl: 'http://stream.test/',
}

beforeEach(async () => {
  document.body.innerHTML = ''
  bootstrapSnapshot.is_cancelled = false
  vi.mocked(sendOp).mockClear()
  vi.mocked(openStream).mockClear()
})

/** Expand the header and find the Status row (the night's, not the logging status). */
async function statusRow(container) {
  await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
  await fireEvent.click(container.querySelector('.topbar-row'))
  const row = [...document.querySelectorAll('.kit-field')]
    .find((r) => r.querySelector('.kit-field-label').textContent.trim() === 'Status')
  expect(row).toBeTruthy()
  return row
}

const pick = (row, value) => fireEvent.change(row.querySelector('.hx-select'), { target: { value } })

describe('cancelling a night', () => {
  it('shows an Active night in a Status select beside a separate Logging status row', async () => {
    const { container } = render(App, { props: { config } })
    const row = await statusRow(container)
    expect(row.querySelector('.hx-select').value).toBe('active')
    expect([...row.querySelectorAll('option')].map((o) => o.textContent.trim())).toEqual(['Active', 'Cancelled'])
    const logging = [...document.querySelectorAll('.kit-field')]
      .find((r) => r.querySelector('.kit-field-label').textContent.trim() === 'Logging status')
    expect(logging.querySelector('.kit-field-value').textContent.trim()).toBe('Still logging')
    expect(container.querySelector('.session-date-cancelled')).toBeNull()
    expect(container.querySelector('.session-cancelled-badge')).toBeNull()
  })

  it('picking Cancelled sends one set_cancelled op and strikes the date through; Active sends the reverse', async () => {
    const { container } = render(App, { props: { config } })
    const row = await statusRow(container)
    await pick(row, 'cancelled')

    await waitFor(() => expect(sendOp).toHaveBeenCalledTimes(1))
    const [, opType, payload] = vi.mocked(sendOp).mock.calls[0]
    expect(opType).toBe('set_cancelled')
    expect(payload).toEqual({ cancelled: true })

    await waitFor(() => expect(container.querySelector('.session-date-cancelled')).toBeTruthy())
    expect(container.querySelector('.session-cancelled-badge').textContent.trim()).toBe('Cancelled')
    expect(row.querySelector('.hx-select').value).toBe('cancelled')

    await pick(row, 'active')
    await waitFor(() => expect(sendOp).toHaveBeenCalledTimes(2))
    expect(vi.mocked(sendOp).mock.calls[1][2]).toEqual({ cancelled: false })
    await waitFor(() => expect(container.querySelector('.session-date-cancelled')).toBeNull())
  })

  it('paints a cancelled night from the bootstrap', async () => {
    bootstrapSnapshot.is_cancelled = true
    const { container } = render(App, { props: { config } })
    const row = await statusRow(container)
    await waitFor(() => expect(row.querySelector('.hx-select').value).toBe('cancelled'))
    expect(container.querySelector('.session-date-cancelled')).toBeTruthy()
  })

  it('a rejected op springs the select back and leaves the night as it was', async () => {
    vi.mocked(sendOp).mockResolvedValueOnce({ rejected: true, reason: 'not_found', message: 'This session log no longer exists.' })
    const { container } = render(App, { props: { config } })
    const row = await statusRow(container)
    await pick(row, 'cancelled')
    await waitFor(() => expect(sendOp).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(row.querySelector('.hx-select').value).toBe('active'))
    expect(container.querySelector('.session-date-cancelled')).toBeNull()
  })

  it('signed out, the status is a plain value', async () => {
    bootstrapSnapshot.is_cancelled = true
    const { container } = render(App, { props: { config: { ...config, canEdit: false, currentPerson: null } } })
    const row = await statusRow(container)
    expect(row.querySelector('.hx-select')).toBeNull()
    expect(row.querySelector('.kit-field-value').textContent.trim()).toBe('Cancelled')
  })
})
