import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/svelte'

// Spec 039: a session can opt out of the members list, attendance, and set starters.
// The header's expanded panel is one of the three places that has to honour it, and it
// had no coverage — the old assertions named classes the panel no longer uses, so they
// would have passed no matter what the panel rendered.
//
// What must hold with the flags OFF, for a SIGNED-IN logger:
//   - no attendance row and no Manage button (people)
//   - no set-starter pills on the sets (people)
//   - Date / Tunes / Notes / Status are untouched — they are not people facts, and
//     re-dating in particular must never be gated by a people preference.

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
    { session_instance_tune_id: 1, tune_id: 11, name: 'The Silver Spear', order_position: 'A', record_type: 'tune', deleted: false, tune_type: 'Reel', started_by_name: 'Aoife K', started_by_person_id: 5 },
  ],
}

const livePeople = vi.fn(async () => [
  { person_id: 5, display_name: 'Aoife Kelly', attending: true },
])

vi.mock('../src/client.js', () => ({
  bootstrap: vi.fn(async () => snapshot),
  vocabulary: vi.fn(async () => ({ known_tunes: [], known_aliases: [] })),
  openStream: vi.fn(() => ({ close: () => {} })),
  livePeople: (...a) => livePeople(...a),
  peopleSearch: vi.fn(async () => []),
  sendOp: vi.fn(async () => ({ success: true })),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
  myTunesList: vi.fn(async () => ({ tunes: [] })),
  myTunesOp: vi.fn(async () => ({ success: true })),
  probeServers: vi.fn(async () => ({ app: true, stream: true })),
}))

const config = (over = {}) => ({
  sessionInstanceId: 90,
  sessionPath: 'austin/mueller',
  instanceDate: '2026-02-01',
  currentPerson: { person_id: 2, first_name: 'Ian' },
  streamingBaseUrl: 'http://stream.test/',
  trackAttendance: true,
  trackSetStarters: true,
  ...over,
})

/** Expand the header and read back what the panel offers. */
async function panel(container) {
  await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(1))
  container.querySelector('.topbar-row').click()
  await waitFor(() => expect(container.querySelectorAll('.hx-row').length).toBeGreaterThan(0))
  return {
    labels: [...container.querySelectorAll('.hx-row .hx-label')].map((l) => l.textContent.trim()),
    actions: [...container.querySelectorAll('.hx-act')].map((b) => b.textContent.trim()),
    starterPills: container.querySelectorAll('.starter-pill').length,
  }
}

let App
beforeEach(async () => {
  document.body.innerHTML = ''
  livePeople.mockClear()
  App = (await import('../src/App.svelte')).default
})

describe('header honours the per-session people flags (spec 039)', () => {
  it('shows attendance and starters when both flags are on', async () => {
    const { container } = render(App, { props: { config: config() } })
    const p = await panel(container)
    // "Attended", past tense — the fixture instance date is in the past.
    expect(p.labels).toContain('Attended')
    expect(p.actions).toContain('Manage')
  })

  it('drops the attendance row and Manage when track_attendance is off', async () => {
    const { container } = render(App, { props: { config: config({ trackAttendance: false, trackSetStarters: false }) } })
    const p = await panel(container)
    expect(p.labels).not.toContain('Attending')
    expect(p.labels).not.toContain('Attended')
    expect(p.actions).not.toContain('Manage')
    expect(p.starterPills).toBe(0)
    // ...and the non-people rows are all still there, editable
    expect(p.labels).toEqual(expect.arrayContaining(['Date', 'Tunes', 'Notes', 'Status']))
    expect(p.actions).toContain('Change')
    expect(p.actions).toContain('Mark complete')
    expect(container.querySelector('.hn-area')).toBeTruthy()
  })

  it('never asks the server for people when both flags are off', async () => {
    render(App, { props: { config: config({ trackAttendance: false, trackSetStarters: false }) } })
    await waitFor(() => expect(document.querySelectorAll('.tune-row').length).toBe(1))
    expect(livePeople).not.toHaveBeenCalled()
  })
})
