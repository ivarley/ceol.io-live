import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor, fireEvent } from '@testing-library/svelte'
import { sendOp, openStream, bootstrap } from '../src/client.js'

// Spec 047: a log's own name (session_instance.location_override) is editable from the
// logger header. It exists for festivals, where several sessions share a date and the
// date therefore names none of them — but it's the same field a regular session uses for
// a night at a different venue, so the row is not festival-gated.

const bootstrapSnapshot = {
  session_id: 1,
  session_name: 'Hill Country Trad Fest',
  session_date: 'Sat · Jun 6, 2026',
  instance_date: '2026-06-06',
  instance_name: null, // unnamed to start — the case the row exists to fix
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
  sendOp: vi.fn(async () => ({ success: true, instance_name: 'Advanced Session @ Jim Bowie', previous_name: null })),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
}))

const config = {
  sessionInstanceId: 103,
  instanceDate: '2026-06-06',
  instanceName: null,
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

/** Expand the header and find the Name row. */
async function nameRow(container) {
  await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
  await fireEvent.click(container.querySelector('.topbar-row'))
  const row = [...container.querySelectorAll('.hx-row')]
    .find((r) => r.querySelector('.hx-label').textContent.trim() === 'Name')
  expect(row).toBeTruthy()
  return row
}

/** Open the name sheet; it portals to the body, not into the container. */
async function openNameSheet(container) {
  const row = await nameRow(container)
  await fireEvent.click(row.querySelector('.hx-act'))
  await waitFor(() => expect(document.querySelector('.dt-input[type="text"]')).toBeTruthy())
  return document.querySelector('.dt-input[type="text"]')
}

describe('log name editor (spec 047)', () => {
  it('offers to name an unnamed log', async () => {
    const { container } = render(App, { props: { config } })
    const row = await nameRow(container)
    expect(row.querySelector('.hx-val').textContent.trim()).toBe('The usual')
    expect(row.querySelector('.hx-act').textContent.trim()).toBe('Name it')
    // Nothing to show in the collapsed header while it's unnamed.
    expect(container.querySelector('.session-instance-name')).toBeNull()
  })

  it('sends one set_name op and shows the name in the collapsed header', async () => {
    const { container } = render(App, { props: { config } })
    const input = await openNameSheet(container)
    await fireEvent.input(input, { target: { value: 'Advanced Session @ Jim Bowie' } })
    await fireEvent.click(document.querySelector('.dt-save'))

    await waitFor(() => expect(sendOp).toHaveBeenCalledTimes(1))
    const [, opType, payload] = vi.mocked(sendOp).mock.calls[0]
    expect(opType).toBe('set_name')
    expect(payload).toEqual({ name: 'Advanced Session @ Jim Bowie' })

    await waitFor(() =>
      expect(container.querySelector('.session-instance-name')?.textContent).toBe('Advanced Session @ Jim Bowie'))
  })

  it('clears the name when the field is emptied', async () => {
    // Bootstrap is server truth for the name, so this log has to arrive already named —
    // seeding config alone would be overwritten by the bootstrap's null.
    vi.mocked(bootstrap).mockResolvedValueOnce({
      ...bootstrapSnapshot, instance_name: 'Advanced Session @ Jim Bowie',
    })
    vi.mocked(sendOp).mockResolvedValueOnce({
      success: true, instance_name: null, previous_name: 'Advanced Session @ Jim Bowie',
    })
    const named = { ...config, instanceName: 'Advanced Session @ Jim Bowie' }
    const { container } = render(App, { props: { config: named } })
    const input = await openNameSheet(container)
    expect(input.value).toBe('Advanced Session @ Jim Bowie')

    await fireEvent.input(input, { target: { value: '   ' } })
    // Blanking is a real edit, so the commit stays live — and says so.
    expect(document.querySelector('.dt-save').textContent.trim()).toBe('Clear name')
    await fireEvent.click(document.querySelector('.dt-save'))

    await waitFor(() => expect(sendOp).toHaveBeenCalledTimes(1))
    expect(vi.mocked(sendOp).mock.calls[0][2]).toEqual({ name: '' })
    await waitFor(() => expect(container.querySelector('.session-instance-name')).toBeNull())
  })

  it('renames from someone else\'s set_name arriving over SSE', async () => {
    // A previous test's connect() can still register a stream after its component is
    // gone, so match the call by the exact config object THIS render was given.
    const myConfig = { ...config }
    const myStream = () => vi.mocked(openStream).mock.calls.find((c) => c[0] === myConfig)
    const { container } = render(App, { props: { config: myConfig } })
    await waitFor(() => expect(myStream()).toBeTruthy())
    const { onOp } = myStream()[2]

    onOp({
      op_type: 'set_name', event_id: 7,
      instance_name: 'After-Hours Session @ Hotel', previous_name: null,
      actor: { person_id: 9, name: 'Aoife' },
    })
    await waitFor(() =>
      expect(container.querySelector('.session-instance-name')?.textContent).toBe('After-Hours Session @ Hotel'))
    expect(container.querySelector('.toast.activity').textContent).toContain('Aoife')
  })
})
