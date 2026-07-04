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
  thesessionSearch: vi.fn(async () => []),
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

  // spec 028: ≥900px mounts the persistent side pane (jsdom's default innerWidth is 1024);
  // below 900px the pane must not mount at all (mobile layout byte-for-byte unchanged).
  it('mounts the side pane when wide, not when narrow', async () => {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(3))
    expect(container.querySelectorAll('.sidepane').length).toBe(1)
    expect(container.querySelector('.sidepane .deep-field')).not.toBeNull()

    const realWidth = window.innerWidth
    Object.defineProperty(window, 'innerWidth', { value: 500, configurable: true, writable: true })
    try {
      document.body.innerHTML = ''
      const { container: narrow } = render(App, { props: { config } })
      await waitFor(() => expect(narrow.querySelectorAll('.tune-row').length).toBe(3))
      expect(narrow.querySelectorAll('.sidepane').length).toBe(0)
    } finally {
      Object.defineProperty(window, 'innerWidth', { value: realWidth, configurable: true, writable: true })
    }
  })
})

// Composer paste: commas = tunes in a set, line breaks = new sets — bulk-logged in
// order through the same op pipeline as selection-mode paste. A single plain name is
// NOT intercepted (normal paste; edit, then Enter).
describe('composer multi-tune paste', () => {
  async function mountInEditMode() {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(3))
    container.querySelector('.editbtn').click()
    await waitFor(() => expect(container.querySelector('.composer-field input')).not.toBeNull())
    return container
  }

  function pasteInto(input, text) {
    const ev = new Event('paste', { bubbles: true, cancelable: true })
    ev.clipboardData = { getData: () => text }
    input.dispatchEvent(ev)
    return ev
  }

  it('pastes lines/commas as ordered add_tune + set_break ops', async () => {
    const { sendOp } = await import('../src/client.js')
    sendOp.mockClear()
    // echo a real record per op so temp→real anchor remapping is observable
    let nextId = 100
    sendOp.mockImplementation(async (cfg, opType, payload) => {
      const id = nextId++
      return {
        success: true,
        record: {
          session_instance_tune_id: id, tune_id: payload.tune_id ?? null, tune_type: null,
          name: payload.name ?? null, order_position: `Z${id}`, deleted: false,
          record_type: opType === 'set_break' ? 'break' : 'tune',
        },
      }
    })
    const container = await mountInEditMode()
    const ev = pasteInto(container.querySelector('.composer-field input'), 'Tune A, Tune B\nTune C')
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(sendOp.mock.calls.length).toBe(4))
    const ops = sendOp.mock.calls.map((c) => [c[1], c[2].name ?? null, c[2].after_record_id ?? null])
    expect(ops).toEqual([
      ['add_tune', 'Tune A', null],   // pure append at the end
      ['add_tune', 'Tune B', 100],    // same set: chained after Tune A
      ['set_break', null, 101],       // line break -> new set after Tune B
      ['add_tune', 'Tune C', 102],    // first tune of the new set, after the break
    ])
    // pasted duplicates must always add, never corroborate-collapse
    for (const c of sendOp.mock.calls) if (c[1] === 'add_tune') expect(c[2].no_merge).toBe(true)
  })

  it('leaves a single plain name to the default paste', async () => {
    const { sendOp } = await import('../src/client.js')
    sendOp.mockClear()
    const container = await mountInEditMode()
    const ev = pasteInto(container.querySelector('.composer-field input'), 'The Lonesome Boatman')
    expect(ev.defaultPrevented).toBe(false)
    expect(sendOp).not.toHaveBeenCalled()
  })
})
