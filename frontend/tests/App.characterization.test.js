import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/svelte'

// Characterization test: mounts the REAL App with client.js mocked, and pins the
// observable behavior the logstate.js extraction must preserve — that a bootstrap of
// records renders in the right order, grouped into the right sets. If the extraction
// (computeOrdered / segmentByBreaks / setLabel) ever drifts, this fails at the DOM.
//
// offline.js is left real (fake-indexeddb backs it in tests/setup.js); only the
// network surface (client.js) is stubbed so onMount's connect() resolves deterministically.

const bootstrapSnapshot = {
  session_id: 1,
  session_name: 'Test Session',
  session_date: '2026-02-01',
  current_person: { person_id: 2, first_name: 'Ian' },
  last_event_id: 0,
  log_complete: false,
  records: [
    { session_instance_tune_id: 1, tune_id: 11, name: 'The Silver Spear', order_position: 'A', record_type: 'tune', deleted: false, tune_type: 'Reel' },
    { session_instance_tune_id: 2, tune_id: 12, name: "Cooley's", order_position: 'B', record_type: 'tune', deleted: false, tune_type: 'Reel' },
    { session_instance_tune_id: 3, name: null, order_position: 'C', record_type: 'break', deleted: false },
    { session_instance_tune_id: 4, tune_id: 13, name: 'Out on the Ocean', order_position: 'D', record_type: 'tune', deleted: false, tune_type: 'Jig' },
  ],
}

vi.mock('../src/client.js', () => ({
  bootstrap: vi.fn(async () => bootstrapSnapshot),
  vocabulary: vi.fn(async () => ({ known_tunes: [], known_aliases: [] })),
  openStream: vi.fn(() => ({ close: () => {} })),
  livePeople: vi.fn(async () => []),
  peopleSearch: vi.fn(async () => []),
  sendOp: vi.fn(async () => ({ success: true })),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
}))

const config = { sessionInstanceId: 90, currentPerson: { person_id: 2, first_name: 'Ian' }, streamingBaseUrl: 'http://stream.test/' }

let App
beforeEach(async () => {
  document.body.innerHTML = ''
  App = (await import('../src/App.svelte')).default
})

describe('App renders bootstrapped records (extraction guard)', () => {
  it('renders tune names in order_position order', async () => {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row .name').length).toBe(3))
    const names = [...container.querySelectorAll('.tune-row .name')].map((n) => n.textContent.trim())
    expect(names).toEqual(['The Silver Spear', "Cooley's", 'Out on the Ocean'])
  })

  it('groups tunes into sets split on the break record', async () => {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelectorAll('.set').length).toBe(2))
    const sets = container.querySelectorAll('.set')
    // set 1 has two tunes, set 2 has one (the break separates them)
    expect(sets[0].querySelectorAll('.tune-row').length).toBe(2)
    expect(sets[1].querySelectorAll('.tune-row').length).toBe(1)
  })

  it('labels the sets by tune type via setLabel', async () => {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelectorAll('.set-label').length).toBe(2))
    const labels = [...container.querySelectorAll('.set-label')].map((b) => b.textContent.trim())
    expect(labels).toEqual(['Reels', 'Jigs'])
  })
})
