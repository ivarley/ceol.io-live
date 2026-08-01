import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/svelte'
import { queuePut, queueAll, snapshotPut } from '../src/offline.js'

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

  // The two-pane grid reserves a 440px pane column, so main.wide may only be set when
  // the pane is actually mounted. A signed-out viewer (canEdit: false) never mounts it,
  // and used to get the column reserved and empty with the log stranded in the left half.
  it('main.wide only when the pane is really there (never for a read-only viewer)', async () => {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(3))
    expect(container.querySelector('main').classList.contains('wide')).toBe(true)

    document.body.innerHTML = ''
    const { container: ro } = render(App, { props: { config: { ...config, canEdit: false } } })
    await waitFor(() => expect(ro.querySelectorAll('.tune-row').length).toBe(3))
    expect(ro.querySelectorAll('.sidepane').length).toBe(0)
    expect(ro.querySelector('main').classList.contains('wide')).toBe(false)
  })
})

// Composer paste: commas = tunes in a set, line breaks = new sets — bulk-logged in
// order through the same op pipeline as selection-mode paste. A single plain name is
// NOT intercepted (normal paste; edit, then Enter).
describe('composer multi-tune paste', () => {
  // Each caller gets its own session instance id: unmount is not automatic (beforeEach
  // only clears the DOM), so a zombie App from an earlier test can otherwise hydrate and
  // flush this test's queued ops out of the shared fake-IndexedDB.
  async function mountInEditMode(sessionInstanceId = config.sessionInstanceId) {
    const { container } = render(App, { props: { config: { ...config, sessionInstanceId } } })
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

  // FIFO gate (§G): once an op is queued by a network failure, a LATER op minted while
  // the browser still reports online must queue behind it — never POST first, which
  // would bake the swapped order into order_position server-side. The gate also kicks
  // a flush, so the backlog drains in submit order as soon as the network cooperates.
  it('a later add never jumps the line past a queued one (flaky network)', async () => {
    const { sendOp } = await import('../src/client.js')
    sendOp.mockClear()
    let nextId = 300
    let failedOnce = false
    sendOp.mockImplementation(async (cfg, opType, payload) => {
      if (!failedOnce) { // first POST dies on a flaky network -> op goes queued
        failedOnce = true
        const e = new Error('fetch failed')
        e.networkError = true
        throw e
      }
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
    const container = await mountInEditMode(993)
    pasteInto(container.querySelector('.composer-field input'), 'Tune A, Tune B')
    await waitFor(() => expect(sendOp.mock.calls.length).toBe(3))
    const ops = sendOp.mock.calls.map((c) => [c[1], c[2].name])
    expect(ops).toEqual([
      ['add_tune', 'Tune A'], // networkError -> queued
      ['add_tune', 'Tune A'], // Tune B's gate queued it and kicked a flush: A replays first...
      ['add_tune', 'Tune B'], // ...then B, still in submit order
    ])
    // B's temp anchor resolved to A's real id on replay (order preserved, not append-scrambled)
    expect(sendOp.mock.calls[2][2].after_record_id).toBe(300)
  })
})

// Reload with a queued offline backlog (§G). openStream is mocked and never reports
// 'live' — the SSE-down case (e.g. dead sidecar) — so these pin that the queue neither
// strands nor forgets what it knew.
describe('queued ops across a reload', () => {
  it('flushes on a successful bootstrap even though SSE never goes live', async () => {
    const { sendOp } = await import('../src/client.js')
    sendOp.mockClear()
    sendOp.mockImplementation(async () => ({ success: true }))
    const inst = 991
    await queuePut({
      op_id: 'q-flush-1', op_type: 'add_tune', name: 'Maid Behind The Bar, The', ts: 1, session_instance_id: inst,
      payload: { name: 'Maid Behind The Bar, The', tune_id: 77, tune_type: 'Reel', after_record_id: null, before_record_id: null },
    })
    render(App, { props: { config: { ...config, sessionInstanceId: inst } } })
    await waitFor(() => expect(sendOp.mock.calls.length).toBe(1))
    expect(sendOp.mock.calls[0][1]).toBe('add_tune')
    expect(sendOp.mock.calls[0][3]).toBe('q-flush-1')
    await waitFor(async () => expect(await queueAll(inst)).toHaveLength(0)) // settled -> gone from IndexedDB
  })

  it('rehydrates a matched offline add as LINKED with its tune type, not "unlinked"/"Unknown"', async () => {
    const { sendOp } = await import('../src/client.js')
    sendOp.mockClear()
    sendOp.mockImplementation(async () => { // still can't reach the server -> row stays queued
      const e = new Error('offline')
      e.networkError = true
      throw e
    })
    const inst = 992
    await queuePut({
      op_id: 'q-link-1', op_type: 'add_tune', name: 'Silver Spear, The', ts: 1, session_instance_id: inst,
      payload: { name: 'Silver Spear, The', tune_id: 55, tune_type: 'Reel', after_record_id: null, before_record_id: null },
    })
    const { container } = render(App, { props: { config: { ...config, sessionInstanceId: inst } } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(4)) // 3 bootstrapped + the queued one
    const row = [...container.querySelectorAll('.tune-row')].find((r) => r.textContent.includes('Silver Spear'))
    expect(row).toBeTruthy()
    expect(row.classList.contains('unlinked')).toBe(false)
    expect(row.querySelector('.row-warn')).toBeNull() // no "⚠ unlinked" badge
    // tune_type carried through: the open set (Jig + this Reel) labels "Mixed", not "Jigs"
    const labels = [...container.querySelectorAll('.set-label')].map((b) => b.textContent.trim())
    expect(labels[labels.length - 1]).toBe('Mixed')
  })

  it('lets a queued offline add be tapped and removed before it syncs', async () => {
    const { sendOp } = await import('../src/client.js')
    sendOp.mockClear()
    sendOp.mockImplementation(async () => { // still offline: the op stays queued
      const e = new Error('offline')
      e.networkError = true
      throw e
    })
    const inst = 994
    await queuePut({
      op_id: 'q-del-1', op_type: 'add_tune', name: 'Doomed Tune', ts: 1, session_instance_id: inst,
      payload: { name: 'Doomed Tune', tune_id: null, tune_type: null, after_record_id: null, before_record_id: null },
    })
    const { container } = render(App, { props: { config: { ...config, sessionInstanceId: inst } } })
    await waitFor(() => expect(container.querySelectorAll('.tune-row').length).toBe(4))
    container.querySelector('.editbtn').click()
    await waitFor(() => expect(container.querySelector('.composer-field input')).not.toBeNull())
    let row
    await waitFor(() => { // entering edit mode reconnects (byId rebuilds); wait for the rehydrated row
      row = [...container.querySelectorAll('.tune-row')].find((r) => r.textContent.includes('Doomed Tune'))
      expect(row).toBeTruthy()
    })
    row.click() // select the queued row -> its actions panel offers Remove
    await waitFor(() => expect(container.querySelector('.row-actions .danger')).not.toBeNull())
    container.querySelector('.row-actions .danger').click()
    await waitFor(() =>
      expect([...container.querySelectorAll('.tune-row')].some((r) => r.textContent.includes('Doomed Tune'))).toBe(false)
    )
    await waitFor(async () => expect(await queueAll(inst)).toHaveLength(0)) // cancelled op left the queue
    expect(sendOp.mock.calls.every((c) => c[1] !== 'remove_tune')).toBe(true) // local cancel, no server op
  })
})

// Slow-network stale-first paint: a first bootstrap that stalls past STALE_PAINT_MS
// paints the cached snapshot provisionally (the offline render path on a timer), and
// the bootstrap that eventually lands re-applies server truth over it.
describe('slow-network stale-first paint', () => {
  const cachedSnapshot = (name) => ({
    records: [
      { session_instance_tune_id: 900, tune_id: 90, name, order_position: 'A', record_type: 'tune', deleted: false, tune_type: 'Reel' },
    ],
    last_event_id: 5, person: { person_id: 2, first_name: 'Ian' },
    session_name: 'Test Session', session_date: '2026-02-01', notes: '',
    log_complete: false, display_tz: null, known_tunes: [], known_aliases: [],
  })

  it('paints the cached snapshot while bootstrap stalls, then reconciles to server truth', async () => {
    const { bootstrap } = await import('../src/client.js')
    const inst = 995
    await snapshotPut(inst, cachedSnapshot('Cached-Only Tune'))
    let resolveBoot
    bootstrap.mockImplementation(() => new Promise((r) => { resolveBoot = r }))
    try {
      const { container } = render(App, { props: { config: { ...config, sessionInstanceId: inst } } })
      // The cached record paints after STALE_PAINT_MS, well before bootstrap answers.
      await waitFor(() => expect(container.textContent).toContain('Cached-Only Tune'), { timeout: 3000 })
      // Bootstrap lands with different truth: it wins, and the cache-only row is gone.
      resolveBoot(bootstrapSnapshot)
      await waitFor(() => expect(container.textContent).toContain('The Silver Spear'))
      expect(container.textContent).not.toContain('Cached-Only Tune')
    } finally {
      bootstrap.mockImplementation(async () => bootstrapSnapshot)
    }
  })

  it('never paints stale when bootstrap answers fast', async () => {
    const inst = 996
    await snapshotPut(inst, cachedSnapshot('Stale Tune'))
    const { container } = render(App, { props: { config: { ...config, sessionInstanceId: inst } } })
    await waitFor(() => expect(container.textContent).toContain('The Silver Spear'))
    // Wait past the stale-paint timer: the cached-only row must never show up.
    await new Promise((r) => setTimeout(r, 1100))
    expect(container.textContent).not.toContain('Stale Tune')
  })
})
