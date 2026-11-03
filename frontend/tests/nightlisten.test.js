// Spec 061 stage 4: Listen on a night's logger, Log mode. The meter's logging rules
// (the iPhone's, NightRecorder.swift): log what it is sure of at 100% when the switch
// is on, never the tune last logged twice nor any tune twice in ten minutes, leave a
// tune someone else just logged, take back its own row on "Wrong tune", and end the
// set after a stretch of no tune. Then the logger: "Listen and log", the ops it sends,
// and the strip that says it is listening.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import { Meter, latestSetEndsWith, RELOG_AFTER_MS } from '../src/listenpage/meter.js'

const tune = (tune_id, p, extra = {}) => ({ tune_id, name: `Tune ${tune_id}`, type: 'reel', p, outside: false, ...extra })
const st = (t_ms, top, extra = {}) => ({ type: 'state', status: 'listening', t_ms, top, none: 0.1, shown: top[0] ? top[0].tune_id : null, history: [], ...extra })
const quiet = (t_ms) => st(t_ms, [], { none: 0.9, shown: null })
const row = (id, tune_id) => ({ session_instance_tune_id: id, tune_id, record_type: 'tune' })
const brk = (id) => ({ session_instance_tune_id: id, record_type: 'break' })

describe('the meter in Log mode', () => {
  it('says to log a tune sure at 100%, but only shows the tune last logged as sure again', () => {
    const m = new Meter()
    expect(m.received(st(4000, [tune(1, 0.996)]), 0)).toEqual({ tune: expect.objectContaining({ tune_id: 1 }), log: true })
    m.markLogged(1, 'temp-a', 0)
    m.received(quiet(8000), 1000)
    m.received(quiet(12000), 2000)
    expect(m.showing).toBe('noTune')
    expect(m.received(st(16000, [tune(1, 0.996)]), 3000)).toEqual({ tune: expect.objectContaining({ tune_id: 1 }), log: false })
  })

  it('does not log a tune by itself twice within ten minutes', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.996)]), 0)
    m.markLogged(1, 'temp-a', 0)
    m.received(quiet(8000), 1000)
    m.received(quiet(12000), 2000)
    m.received(st(16000, [tune(2, 0.996)]), 3000)
    m.markLogged(2, 'temp-b', 3000)
    m.received(quiet(20000), 4000)
    m.received(quiet(24000), 5000)
    // tune 1 again, but not the tune logged last: not sure by itself yet
    expect(m.received(st(28000, [tune(1, 0.996)]), 6000)).toBeNull()
    expect(m.showing).toBe('figuring')
    expect(m.received(st(32000, [tune(1, 0.996)]), RELOG_AFTER_MS + 1)).toEqual({ tune: expect.objectContaining({ tune_id: 1 }), log: true })
  })

  it('"Wrong tune" forgets that it logged the tune, so the page takes the row back once', () => {
    const m = new Meter()
    m.received(st(4000, [tune(1, 0.996)]), 0)
    m.markLogged(1, 'temp-a', 0)
    expect(m.loggedRow).toBe('temp-a')
    m.wrongTune()
    expect(m.logged).toBeNull()
    expect(m.loggedRow).toBeNull()
    expect(m.loggedAt.has(1)).toBe(false)
  })

  it('can end the set after three states of no tune, when the log ends with a tune', () => {
    const m = new Meter()
    const log = [row(1, 11)]
    m.received(quiet(4000))
    m.received(quiet(8000))
    expect(m.canEndSet(log)).toBe(false)
    m.received(quiet(12000))
    expect(m.canEndSet(log)).toBe(true)
    expect(m.canEndSet([...log, brk(2)])).toBe(false)
    expect(m.canEndSet([])).toBe(false)
    m.received(st(16000, [tune(1, 0.4)]))
    expect(m.canEndSet(log)).toBe(false)
  })
})

describe('latestSetEndsWith', () => {
  it('looks at the last two tunes of the latest set, open or ended', () => {
    const log = [row(1, 11), brk(2), row(3, 12), row(4, 13), row(5, 14)]
    expect(latestSetEndsWith(14, log)).toBe(true)
    expect(latestSetEndsWith(13, log)).toBe(true)
    expect(latestSetEndsWith(12, log)).toBe(false)
    expect(latestSetEndsWith(11, log)).toBe(false)
    expect(latestSetEndsWith(14, [...log, brk(6)])).toBe(true)
    expect(latestSetEndsWith(11, [row(1, 11), brk(2)])).toBe(true)
    expect(latestSetEndsWith(11, [])).toBe(false)
  })
})

// --- NightListen, and the logger around it ------------------------------------------

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

const { default: NightListen } = await import('../src/listenpage/NightListen.svelte')

function stubStorage() {
  const store = new Map()
  vi.stubGlobal('localStorage', { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) })
  return store
}

describe('NightListen', () => {
  let onLog, onRemove, onEndSet
  beforeEach(() => {
    links.length = 0
    stubStorage()
    let n = 0
    onLog = vi.fn(() => ({ row: `temp-${++n}` }))
    onRemove = vi.fn()
    onEndSet = vi.fn()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  async function begin(props = {}) {
    const r = render(NightListen, { props: { instanceId: 90, title: 'Mueller, Sun 1 Feb', ordered: [], onLog, onRemove, onEndSet, ...props } })
    await r.component.begin()
    await waitFor(() => expect(document.querySelector('#nl-strip')).toBeTruthy())
    return r
  }
  async function hear(...states) {
    for (const s of states) {
      links[0].onState(s)
      await Promise.resolve()
    }
  }

  it('listens with the night as the hint, says it is logging, and logs a tune sure at 100%', async () => {
    await begin()
    expect(links[0].instanceId).toBe(90)
    expect(document.querySelector('#nl-logging').textContent).toContain('Logging tunes to Mueller, Sun 1 Feb')
    await hear(st(4000, [tune(7, 0.996)]))
    expect(onLog).toHaveBeenCalledWith({ tune_id: 7, name: 'Tune 7', type: 'reel' })
    await waitFor(() => expect(document.querySelector('#nl-logged')).toBeTruthy())
    expect(document.querySelector('#nl-strip').textContent).toContain('Tune 7')
  })

  it('leaves a tune someone else has just logged', async () => {
    await begin({ ordered: [row(1, 7)] })
    await hear(st(4000, [tune(7, 0.996)]))
    expect(onLog).not.toHaveBeenCalled()
    await waitFor(() => expect(document.querySelector('#nl-logged')).toBeTruthy())
  })

  it('with the switch off, shows the tune and logs it on "Log This Tune"', async () => {
    await begin()
    await fireEvent.click(document.querySelector('#nl-auto'))
    expect(localStorage.getItem('ceol.listenLogsAt100')).toBe('0')
    await hear(st(4000, [tune(7, 0.996)]))
    expect(onLog).not.toHaveBeenCalled()
    await fireEvent.click(document.querySelector('#nl-log'))
    expect(onLog).toHaveBeenCalledTimes(1)
  })

  it('a tapped candidate is logged, and "Wrong tune" takes its row back', async () => {
    await begin()
    await hear(st(4000, [tune(7, 0.6), tune(8, 0.3)]))
    await waitFor(() => expect(document.querySelectorAll('.lp-row').length).toBe(2))
    await fireEvent.click(document.querySelectorAll('.lp-row')[1])
    expect(links[0].sent.at(-1)).toMatchObject({ type: 'tap', action: 'this', tune_id: 8 })
    expect(onLog).toHaveBeenCalledWith(expect.objectContaining({ tune_id: 8 }))
    await waitFor(() => expect(document.querySelector('#lp-wrong')).toBeTruthy())
    await fireEvent.click(document.querySelector('#lp-wrong'))
    expect(onRemove).toHaveBeenCalledWith('temp-1')
    expect(links[0].sent.at(-1)).toMatchObject({ action: 'none', shown: [8], why: 'wrong' })
  })

  it('ends the set by itself after a stretch of no tune', async () => {
    await begin({ ordered: [row(1, 7)] })
    await hear(quiet(4000), quiet(8000))
    expect(onEndSet).not.toHaveBeenCalled()
    await hear(quiet(12000))
    expect(onEndSet).toHaveBeenCalledTimes(1)
  })

  it('"Stop logging" goes on listening and logs nothing more', async () => {
    const { component } = await begin()
    await fireEvent.click(document.querySelector('#nl-stop-logging'))
    const confirm = await waitFor(() => {
      const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Stop logging' && x.id !== 'nl-stop-logging')
      expect(b).toBeTruthy()
      return b
    })
    await fireEvent.click(confirm)
    await waitFor(() => expect(document.querySelector('#nl-logging')).toBeNull())
    await hear(st(4000, [tune(7, 0.996)]))
    expect(onLog).not.toHaveBeenCalled()
    expect(links[0].stopped).toBeFalsy()
    expect(document.querySelector('#nl-log-again')).toBeTruthy()
    expect(component).toBeTruthy()
  })

  it('stops logging when the log is marked complete', async () => {
    const r = await begin()
    await r.rerender({ canLog: false })
    await waitFor(() => expect(document.querySelector('#nl-logging')).toBeNull())
    await hear(st(4000, [tune(7, 0.996)]))
    expect(onLog).not.toHaveBeenCalled()
  })

  // Stage 5: recording the night on the server.
  async function beginRecording(props = {}) {
    const r = render(NightListen, { props: { instanceId: 90, title: 'Mueller, Sun 1 Feb', ordered: [], onLog, onRemove, onEndSet, canRecord: true, ...props } })
    await r.component.begin()
    return r
  }

  it('without the right to record, starts at once and asks for no recording', async () => {
    await begin()
    expect(document.querySelector('#nl-record')).toBeNull()
    expect(links[0].startFields).toEqual({})
  })

  it('someone who may record the night is asked first, with "Record this night" on', async () => {
    await beginRecording()
    expect(links.length).toBe(0)
    const box = document.querySelector('#nl-record')
    expect(box.checked).toBe(true)
    await fireEvent.click(document.querySelector('#nl-start'))
    await waitFor(() => expect(document.querySelector('#nl-strip')).toBeTruthy())
    expect(links[0].startFields).toMatchObject({ record: true, title: 'Mueller, Sun 1 Feb' })
    expect(new Date(links[0].startFields.started_at).getTime()).toBeGreaterThan(0)
    expect(document.querySelector('#nl-recording')).toBeNull() // until the service says so
    links[0].onReady({ type: 'ready', recording: true })
    await waitFor(() => expect(document.querySelector('#nl-recording')).toBeTruthy())
    expect(document.querySelector('#nl-strip').textContent).toContain('Recording')
    await fireEvent.click(document.querySelector('#nl-stop'))
    await waitFor(() => expect(document.body.textContent).toContain("The recording so far is added to this night's recordings."))
  })

  it('records nothing with the switch off', async () => {
    await beginRecording()
    await fireEvent.click(document.querySelector('#nl-record'))
    await fireEvent.click(document.querySelector('#nl-start'))
    await waitFor(() => expect(document.querySelector('#nl-strip')).toBeTruthy())
    expect(links[0].startFields).toEqual({})
  })

  it('says so when the service will not record the night, and listens anyway', async () => {
    await beginRecording()
    await fireEvent.click(document.querySelector('#nl-start'))
    await waitFor(() => expect(document.querySelector('#nl-strip')).toBeTruthy())
    links[0].onReady({ type: 'ready', recording: false, recording_error: 'not yours' })
    await waitFor(() => expect(document.querySelector('#nl-not-recording')).toBeTruthy())
    expect(document.querySelector('#nl-strip').textContent).not.toContain('Recording')
  })

  it('offers no recording once the log is marked complete', async () => {
    await beginRecording({ canLog: false })
    expect(document.querySelector('#nl-record')).toBeNull()
    await waitFor(() => expect(document.querySelector('#nl-strip')).toBeTruthy())
    expect(links[0].startFields).toEqual({})
  })

  it('says stop when the page goes, so the service files the night at once', async () => {
    await beginRecording()
    await fireEvent.click(document.querySelector('#nl-start'))
    await waitFor(() => expect(document.querySelector('#nl-strip')).toBeTruthy())
    window.dispatchEvent(new Event('pagehide'))
    await waitFor(() => expect(links[0].stopped).toBe(true))
  })
})

// --- the logger -----------------------------------------------------------------

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
const sendOp = vi.fn(async (config, opType) =>
  opType === 'add_tune'
    ? { success: true, record: { session_instance_tune_id: 50, tune_id: 9, name: 'The Roaring Barmaid', order_position: 'B', record_type: 'tune', deleted: false, tune_type: 'Reel' } }
    : { success: true },
)
vi.mock('../src/client.js', () => ({
  bootstrap: vi.fn(async () => snapshot),
  vocabulary: vi.fn(async () => ({ known_tunes: [], known_aliases: [] })),
  openStream: vi.fn(() => ({ close: () => {} })),
  livePeople: vi.fn(async () => []),
  peopleSearch: vi.fn(async () => []),
  sendOp: (...a) => sendOp(...a),
  sendTyping: vi.fn(async () => {}),
  liveMatch: vi.fn(async () => ({ exact_match: false, results: [] })),
  deepSearch: vi.fn(async () => []),
  thesessionSearch: vi.fn(async () => []),
  fetchIncipit: vi.fn(async () => null),
  tuneDetail: vi.fn(async () => ({})),
  myTunesList: vi.fn(async () => ({ tunes: [], instruments: [] })),
  myTunesOp: vi.fn(async () => ({ success: true })),
  probeServers: vi.fn(async () => ({ app: true, stream: true })),
  listenHref: () => '/listen',
}))
const { default: App } = await import('../src/App.svelte')

const config = {
  sessionInstanceId: 90,
  sessionPath: 'austin/mueller',
  instanceDate: '2026-02-01',
  currentPerson: { person_id: 2, first_name: 'Ian' },
  streamingBaseUrl: 'http://stream.test/',
  trackAttendance: true,
  trackSetStarters: true,
}

describe('the logger, for someone who may listen on the server', () => {
  beforeEach(() => {
    links.length = 0
    sendOp.mockClear()
    stubStorage()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    delete window.CEOL_LISTENS
    document.body.innerHTML = ''
  })

  it('offers "Listen and log", and logs what the meter is sure of at the end of the night', async () => {
    window.CEOL_LISTENS = true
    const { container } = render(App, { props: { config } })
    const button = await waitFor(() => {
      const b = container.querySelector('#listen-log')
      expect(b).toBeTruthy()
      return b
    })
    await fireEvent.click(button)
    await waitFor(() => expect(container.querySelector('#nl-strip')).toBeTruthy())
    expect(container.querySelector('#listen-log')).toBeNull()
    links[0].onState(st(4000, [tune(9, 0.996, { name: 'The Roaring Barmaid' })]))
    await waitFor(() => expect(sendOp).toHaveBeenCalled())
    const [, opType, payload] = sendOp.mock.calls.at(-1)
    expect(opType).toBe('add_tune')
    // by thesession.org id: the server links a tune it has, imports one it hasn't, and names the row
    expect(payload).toMatchObject({ thesession_id: 9, after_record_id: null, before_record_id: null })
    await waitFor(() => expect([...container.querySelectorAll('.tune-row .name')].map((n) => n.textContent)).toContain('The Roaring Barmaid'))
  })

  it('offers nothing to anyone else', async () => {
    const { container } = render(App, { props: { config } })
    await waitFor(() => expect(container.querySelector('.tune-row')).toBeTruthy())
    expect(container.querySelector('#listen-log')).toBeNull()
  })
})
