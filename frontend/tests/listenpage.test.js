// Spec 061 stage 3: Listen on the web, Ad-hoc mode. The meter's rules (the iPhone's,
// NightRecorder.swift: sure at 100% or on a tap, let go when the listener moves on,
// "Wrong tune" and "Tune changed"), Recent Tunes Heard, and the page: what it sends,
// the tunebook box, and the one thing an "Add a tune" search opened it for.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import { Meter, candidates, bar, addRecent, loadRecent, saveRecent, RECENT_KEY, RECENT_KEEP } from '../src/listenpage/meter.js'

const tune = (tune_id, p, extra = {}) => ({ tune_id, name: `Tune ${tune_id}`, type: 'reel', p, outside: false, ...extra })
const st = (t_ms, top, extra = {}) => ({ type: 'state', status: 'listening', t_ms, top, none: 0.1, shown: top[0] ? top[0].tune_id : null, history: [], ...extra })

describe('the meter', () => {
  it('waits, then figures, and says when nothing is a tune', () => {
    const m = new Meter()
    expect(m.showing).toBe('waiting')
    m.received(st(4000, [tune(1, 0.4)]))
    expect(m.showing).toBe('figuring')
    m.received(st(8000, [tune(1, 0.1)], { none: 0.7, shown: null }))
    expect(m.showing).toBe('noTune')
  })

  it('is sure by itself at 100% of the tune it shows, and says which', () => {
    const m = new Meter()
    expect(m.received(st(4000, [tune(1, 0.99)]))).toBeNull()
    const sure = m.received(st(8000, [tune(1, 0.996)]))
    expect(sure.tune.tune_id).toBe(1)
    expect(sure.log).toBe(true)
    expect(m.showing).toBe('sure')
    expect(m.confirmedName).toBe('Tune 1')
  })

  it('is not sure by itself while the tune may have changed', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.999)], { changing: { tune_id: 1, name: 'Tune 1' } }))
    expect(m.showing).toBe('figuring')
    expect(m.wasName).toBe('Tune 1')
  })

  it('holds a sure tune for a step, then lets go when the listener moves on', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.999)]))
    // within the hold: another tune shown, still sure
    m.received(st(8000, [tune(2, 0.6), tune(1, 0.3)]))
    expect(m.showing).toBe('sure')
    m.received(st(12000, [tune(2, 0.6), tune(1, 0.3)]))
    expect(m.showing).toBe('figuring')
  })

  it('lets go when its belief drops under 80%, though still shown', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.999)]))
    m.received(st(12000, [tune(1, 0.85)]))
    expect(m.showing).toBe('sure')
    m.received(st(16000, [tune(1, 0.7)]))
    expect(m.showing).toBe('figuring')
  })

  it('a tap says this is it, with what was shown', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.5), tune(2, 0.3)]))
    expect(m.tapThis(2)).toEqual({ type: 'tap', action: 'this', tune_id: 2, shown: [1, 2] })
    expect(m.showing).toBe('sure')
    expect(m.confirmed).toBe(2)
  })

  it('"None of these" rules out every candidate', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.5), tune(2, 0.3)]))
    expect(m.tapNone()).toEqual({ type: 'tap', action: 'none', shown: [1, 2] })
  })

  it('"Wrong tune" rules it out and never names it by itself again', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.999)]))
    expect(m.wrongTune()).toEqual({ type: 'tap', action: 'none', shown: [1], why: 'wrong' })
    expect(m.showing).toBe('figuring')
    expect(m.received(st(8000, [tune(1, 0.999)]))).toBeNull()
    expect(m.showing).toBe('figuring')
  })

  it('"Tune changed" says what it was until another tune is shown', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.999)]))
    expect(m.tuneChanged()).toEqual({ type: 'tap', action: 'none', shown: [1], why: 'changed' })
    expect(m.wasName).toBe('Tune 1')
    m.received(st(8000, [tune(1, 0.5)]))
    expect(m.wasName).toBe('Tune 1')
    m.received(st(12000, [tune(3, 0.5)]))
    expect(m.wasName).toBeNull()
  })

  it('shows every strong candidate and at most two weak ones', () => {
    const rows = candidates(st(0, [tune(1, 0.5), tune(2, 0.2), tune(3, 0.04), tune(4, 0.03), tune(5, 0.01)]))
    expect(rows.map((r) => [r.tune_id, r.weak])).toEqual([[1, false], [2, false], [3, true], [4, true]])
  })

  it('draws the bar in ten cells: red, then orange, then green', () => {
    expect(bar(0)).toEqual(Array(10).fill('off'))
    expect(bar(0.73)).toEqual(['low', 'low', 'low', 'low', 'low', 'mid', 'mid', 'off', 'off', 'off'])
    expect(bar(1).slice(8)).toEqual(['high', 'high'])
  })
})

describe('Recent Tunes Heard', () => {
  it('is newest first, one hearing per ten minutes of the same tune, at most fifty', () => {
    let list = []
    list = addRecent(list, { tune_id: 1, heard_at: 0 })
    list = addRecent(list, { tune_id: 1, heard_at: 5 * 60 * 1000 })
    expect(list).toHaveLength(1)
    list = addRecent(list, { tune_id: 1, heard_at: 11 * 60 * 1000 })
    list = addRecent(list, { tune_id: 2, heard_at: 12 * 60 * 1000 })
    expect(list.map((x) => x.tune_id)).toEqual([2, 1, 1])
    for (let i = 0; i < 60; i++) list = addRecent(list, { tune_id: 100 + i, heard_at: i })
    expect(list).toHaveLength(RECENT_KEEP)
  })

  it('survives what the browser has stored, or a browser that stores nothing', () => {
    const store = new Map()
    const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) }
    saveRecent([{ tune_id: 3, heard_at: 1 }], storage)
    expect(loadRecent(storage)).toEqual([{ tune_id: 3, heard_at: 1 }])
    store.set(RECENT_KEY, '{nonsense')
    expect(loadRecent(storage)).toEqual([])
    store.set(RECENT_KEY, JSON.stringify([{ tune_id: 'x' }, null, { tune_id: 4 }]))
    expect(loadRecent(storage)).toEqual([{ tune_id: 4 }])
    const broken = { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('denied') } }
    expect(loadRecent(broken)).toEqual([])
    expect(() => saveRecent([{ tune_id: 1 }], broken)).not.toThrow()
  })
})

// --- the page ------------------------------------------------------------------

const links = []
vi.mock('../src/listentest/link.js', () => ({
  SAMPLE_RATE: 22050,
  ListenLink: class {
    constructor(o) {
      Object.assign(this, o)
      this.sent = []
      links.push(this)
    }
    start() {
      this.onStatus('live')
    }
    push() {}
    backlog() {
      return 0
    }
    nudge() {}
    send(m) {
      this.sent.push(m)
      return true
    }
    stop() {
      this.stopped = true
    }
  },
}))
vi.mock('../src/listentest/capture.js', () => ({
  startCapture: vi.fn(async () => ({ captured: () => 0, stop: async () => {}, sampleRate: 48000 })),
}))

const { default: App } = await import('../src/listenpage/App.svelte')
const { startCapture } = await import('../src/listentest/capture.js')

function json(body, status = 200) {
  return { ok: status < 400, status, json: async () => body }
}

describe('the Listen page', () => {
  let fetchSpy
  let localStorage
  beforeEach(() => {
    links.length = 0
    const store = new Map()
    localStorage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) }
    vi.stubGlobal('localStorage', localStorage)
    fetchSpy = vi.fn(async (url, opts = {}) => {
      if (url.startsWith('/api/tunes/')) return json({ success: true, session_tune: { person_tune_status: { on_list: false } } })
      if (url === '/api/my-tunes') return json({ success: true, person_tune: { learn_status: JSON.parse(opts.body).learn_status, heard_count: 1 } })
      if (url.startsWith('/api/live/instances/')) return json({ success: true })
      return json({ success: false }, 404)
    })
    vi.stubGlobal('fetch', fetchSpy)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  async function startAndHear(payload, ...states) {
    const r = render(App, { props: { payload } })
    await fireEvent.click(r.container.querySelector('#lp-start'))
    await waitFor(() => expect(r.container.querySelector('#lp-stop')).toBeTruthy())
    for (const s of states) {
      links[0].onState(s)
      await Promise.resolve()
    }
    return r
  }

  it('first paints ready to start, with nothing heard yet', () => {
    const { container } = render(App, { props: { payload: { context: null } } })
    expect(container.querySelector('#lp-start').textContent).toContain('Start Listening')
    expect(container.querySelector('#lp-back')).toBeNull()
    expect(container.querySelector('#lp-recent').textContent).toContain('Nothing heard yet')
  })

  it('says so when the microphone is refused', async () => {
    startCapture.mockImplementationOnce(async () => {
      const e = new Error('denied')
      e.name = 'NotAllowedError'
      throw e
    })
    const { container } = render(App, { props: { payload: {} } })
    await fireEvent.click(container.querySelector('#lp-start'))
    await waitFor(() => expect(container.querySelector('#lp-error').textContent).toContain('Ceol needs the microphone'))
    expect(container.querySelector('#lp-start')).toBeTruthy()
  })

  it('shows the candidates and sends a tap when one is chosen', async () => {
    const { container } = await startAndHear({}, st(4000, [tune(1, 0.6), tune(2, 0.3)]))
    await waitFor(() => expect(container.querySelectorAll('.lp-row')).toHaveLength(2))
    await fireEvent.click(container.querySelectorAll('.lp-row')[1])
    expect(links[0].sent).toEqual([{ type: 'tap', action: 'this', tune_id: 2, shown: [1, 2] }])
    await waitFor(() => expect(container.querySelector('#lp-sure-name').textContent).toBe('Tune 2'))
    // into Recent Tunes Heard, here and in the browser
    expect(container.querySelector('#lp-recent').textContent).toContain('Tune 2')
    expect(JSON.parse(localStorage.getItem(RECENT_KEY))[0].tune_id).toBe(2)
  })

  it('when sure, offers the tune to your list and adds it as you choose', async () => {
    const { container } = await startAndHear({}, st(4000, [tune(7, 0.999)]))
    await waitFor(() => expect(container.querySelector('#lp-tunebook').textContent).toContain('Add this tune to your list as'))
    const learning = [...container.querySelectorAll('.lp-seg button')].find((b) => b.textContent === 'Learning')
    await fireEvent.click(learning)
    await waitFor(() => expect(container.querySelector('#lp-tunebook').textContent).toContain('This tune is on your list as'))
    const add = fetchSpy.mock.calls.find(([url]) => url === '/api/my-tunes')
    expect(JSON.parse(add[1].body)).toEqual({ thesession_id: 7, learn_status: 'learning' })
    // no context: nothing else to offer
    expect(container.querySelector('#lp-action')).toBeNull()
  })

  it('"Wrong tune" goes back to figuring and tells the listener', async () => {
    const { container } = await startAndHear({}, st(4000, [tune(7, 0.999)]))
    await waitFor(() => expect(container.querySelector('#lp-wrong')).toBeTruthy())
    await fireEvent.click(container.querySelector('#lp-wrong'))
    expect(links[0].sent).toEqual([{ type: 'tap', action: 'none', shown: [7], why: 'wrong' }])
    await waitFor(() => expect(container.querySelector('#lp-meter').dataset.showing).toBe('figuring'))
  })

  it('from a night, logs the sure tune to it, and goes back there', async () => {
    const payload = { context: { kind: 'night', instance_id: 5, session_name: 'The Mueller', date: '2026-10-30', back: '/live/instances/5' } }
    const { container } = await startAndHear(payload, st(4000, [tune(7, 0.999)]))
    expect(links[0].instanceId).toBe(5)
    expect(container.querySelector('#lp-back').getAttribute('href')).toBe('/live/instances/5')
    await waitFor(() => expect(container.querySelector('#lp-action').textContent).toContain('Log This Tune'))
    await fireEvent.click(container.querySelector('#lp-action'))
    await waitFor(() => expect(container.querySelector('#lp-action').textContent).toContain('Logged'))
    const [url, opts] = fetchSpy.mock.calls.find(([u]) => u.startsWith('/api/live/instances/'))
    expect(url).toBe('/api/live/instances/5/ops')
    expect(JSON.parse(opts.body)).toMatchObject({ op_type: 'add_tune', tune_id: 7, name: 'Tune 7' })
  })

  it("from a session, adds the sure tune to its list; already there counts as done", async () => {
    fetchSpy.mockImplementation(async (url) => {
      if (url.startsWith('/api/tunes/')) return json({ success: true, session_tune: { person_tune_status: { on_list: false } } })
      if (url === '/api/sessions/austin/mueller/tunes') return json({ success: false, error: 'already' }, 409)
      return json({}, 404)
    })
    const payload = { context: { kind: 'session', session_path: 'austin/mueller', session_name: 'The Mueller', back: '/sessions/austin/mueller' } }
    const { container } = await startAndHear(payload, st(4000, [tune(7, 0.999)]))
    await fireEvent.click(container.querySelector('#lp-action'))
    await waitFor(() => expect(container.querySelector('#lp-action').textContent).toContain("Added to this session's tune list"))
    const [, opts] = fetchSpy.mock.calls.find(([u]) => u === '/api/sessions/austin/mueller/tunes')
    expect(JSON.parse(opts.body)).toEqual({ thesession_id: 7 })
  })

  it('Stop ends the stream and keeps what was heard', async () => {
    const { container } = await startAndHear({}, st(4000, [tune(7, 0.999)]))
    await fireEvent.click(container.querySelector('#lp-stop'))
    await waitFor(() => expect(container.querySelector('#lp-start')).toBeTruthy())
    expect(links[0].stopped).toBe(true)
    expect(container.querySelector('#lp-recent').textContent).toContain('Tune 7')
  })
})

describe('listenHref', () => {
  it('carries the search scope and the page to come back to', async () => {
    const { listenHref } = await vi.importActual('../src/client.js')
    expect(listenHref({ searchScope: {} })).toBe('/listen')
    expect(listenHref({ searchScope: { session: 'austin/mueller' } }, '/sessions/austin/mueller')).toBe(
      '/listen?session=austin%2Fmueller&back=%2Fsessions%2Faustin%2Fmueller'
    )
    expect(listenHref({ sessionInstanceId: 5 }, '/live/instances/5')).toBe('/listen?instance=5&back=%2Flive%2Finstances%2F5')
  })
})

describe('opening a tune', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    delete window.TuneDetailModal
    document.body.innerHTML = ''
  })

  function withRecent(tuneId) {
    const store = new Map([[RECENT_KEY, JSON.stringify([{ tune_id: tuneId, name: 'Tune', heard_at: Date.now() }])]])
    vi.stubGlobal('localStorage', { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) })
  }

  it('opens the tune sheet for a tune Ceol holds', async () => {
    withRecent(5)
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })))
    const show = vi.fn()
    window.TuneDetailModal = { show }
    const { container } = render(App, { props: { payload: {} } })
    await fireEvent.click(container.querySelector('.lp-recent-row'))
    await waitFor(() => expect(show).toHaveBeenCalledWith({ tuneId: 5 }))
  })

  it("opens thesession.org for one it doesn't hold yet", async () => {
    withRecent(6)
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) })))
    const tab = { opener: 'me' }
    const open = vi.fn(() => tab)
    vi.stubGlobal('open', open)
    window.TuneDetailModal = { show: vi.fn() }
    const { container } = render(App, { props: { payload: {} } })
    await fireEvent.click(container.querySelector('.lp-recent-row'))
    await waitFor(() => expect(open).toHaveBeenCalledWith('https://thesession.org/tunes/6', '_blank'))
    expect(tab.opener).toBeNull()
    expect(window.TuneDetailModal.show).not.toHaveBeenCalled()
  })
})
