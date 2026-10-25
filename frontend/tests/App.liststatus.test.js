import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import App from '../src/App.svelte' // static: loading it per test can outrun the hook timeout
import { render, waitFor } from '@testing-library/svelte'

// The my-list highlight mode (★) colors every logged tune by MY learn status from a
// list fetched once per page. The tune sheet saves statuses on tap, with no Save
// button, so the log behind it only stays right if the sheet's onStatusChange is
// mirrored into that list — this pins that mirroring.

const snapshot = {
  session_id: 1,
  session_name: 'Test Session',
  session_date: 'Sun · Feb 1, 2026',
  instance_date: '2026-02-01',
  current_person: { person_id: 2, first_name: 'Ian' },
  can_edit: true,
  last_event_id: 0,
  log_complete: false,
  records: [
    { session_instance_tune_id: 1, tune_id: 11, name: 'The Silver Spear', order_position: 'A', record_type: 'tune', deleted: false, tune_type: 'Reel' },
  ],
}

vi.mock('../src/client.js', () => ({
  bootstrap: vi.fn(async () => snapshot),
  vocabulary: vi.fn(async () => ({ known_tunes: [], known_aliases: [] })),
  openStream: vi.fn(() => ({ close: () => {} })),
  livePeople: vi.fn(async () => []),
  peopleSearch: vi.fn(async () => []),
  sendOp: vi.fn(async () => ({ success: true })),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
  myTunesList: vi.fn(async () => ({ tunes: [], instruments: [] })),
  myTunesOp: vi.fn(async () => ({ success: true })),
  probeServers: vi.fn(async () => ({ app: true, stream: true })),
}))

const config = {
  sessionInstanceId: 90,
  sessionPath: 'austin/mueller',
  instanceDate: '2026-02-01',
  currentPerson: { person_id: 2, first_name: 'Ian' },
  streamingBaseUrl: 'http://stream.test/',
  trackAttendance: true,
  trackSetStarters: true,
}

beforeEach(() => {
  document.body.innerHTML = ''
  window.TuneDetailModal = { show: vi.fn(), close: vi.fn() }
})
afterEach(() => {
  delete window.TuneDetailModal
})

describe('my-list highlight mode follows the tune sheet', () => {
  it('a status changed in the sheet re-colors the row behind it at once', async () => {
    const { container } = render(App, { props: { config } })
    const row = () => container.querySelector('.tune-row[data-sit="1"]')
    await waitFor(() => expect(row()).toBeTruthy())

    container.querySelector('.listmode-btn').click()
    await waitFor(() => expect(row().classList.contains('ls-not-on-list')).toBe(true))

    row().click() // view mode: a tap opens the sheet
    await waitFor(() => expect(window.TuneDetailModal.show).toHaveBeenCalled())
    const cfg = window.TuneDetailModal.show.mock.calls.at(-1)[0]
    expect(cfg.tuneId).toBe(11)
    expect(typeof cfg.onStatusChange).toBe('function')

    cfg.onStatusChange({ tune_id: 11, learn_status: 'learning', instrument_status: {}, on_list: true, person_tune_id: 9 })
    await waitFor(() => expect(row().classList.contains('ls-learning')).toBe(true))

    // Removed from the list in the sheet: back to "not on list".
    cfg.onStatusChange({ tune_id: 11, learn_status: null, instrument_status: {}, on_list: false, person_tune_id: null })
    await waitFor(() => expect(row().classList.contains('ls-not-on-list')).toBe(true))
  })
})
