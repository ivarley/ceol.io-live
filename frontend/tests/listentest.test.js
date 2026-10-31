// Spec 061 stage 2: the browser's side of listening on the server. The resampler
// (the mic's rate down to the service's 22050 Hz), where a chunk goes on the
// night's clock, and the link that keeps the service's copy of the night whole
// across dropped connections.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { Resampler, toInt16 } from '../src/listentest/resample.js'
import { ListenLink, frame, SAMPLE_RATE } from '../src/listentest/link.js'
import { placeChunk } from '../src/listentest/capture.js'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import App from '../src/listentest/App.svelte'

function sine(freq, rate, seconds, amp = 0.5) {
  const n = Math.round(rate * seconds)
  const out = new Float32Array(n)
  for (let i = 0; i < n; i++) out[i] = amp * Math.sin((2 * Math.PI * freq * i) / rate)
  return out
}

function rms(x, from = 0) {
  let s = 0
  for (let i = from; i < x.length; i++) s += x[i] * x[i]
  return Math.sqrt(s / (x.length - from))
}

// Frequency from upward zero crossings, away from the edges.
function frequency(x, rate) {
  let first = -1
  let last = -1
  let count = 0
  for (let i = 1000; i < x.length - 1000; i++) {
    if (x[i - 1] < 0 && x[i] >= 0) {
      if (first < 0) first = i
      else count++
      last = i
    }
  }
  return (count * rate) / (last - first)
}

function inChunks(rs, input, sizes) {
  const parts = []
  let at = 0
  let k = 0
  while (at < input.length) {
    const n = sizes[k++ % sizes.length]
    parts.push(rs.process(input.subarray(at, at + n)))
    at += n
  }
  const total = parts.reduce((a, p) => a + p.length, 0)
  const out = new Float32Array(total)
  let o = 0
  for (const p of parts) {
    out.set(p, o)
    o += p.length
  }
  return out
}

describe('Resampler', () => {
  for (const rate of [48000, 44100]) {
    it(`keeps a tune's pitch and loudness from ${rate} Hz`, () => {
      const out = new Resampler(rate, SAMPLE_RATE).process(sine(440, rate, 2))
      expect(frequency(out, SAMPLE_RATE)).toBeCloseTo(440, 0)
      expect(rms(out, 1000)).toBeCloseTo(0.5 / Math.SQRT2, 2)
      // two seconds in, about two seconds out (the filter's right side still to come)
      expect(Math.abs(out.length - 2 * SAMPLE_RATE)).toBeLessThan(100)
    })
  }

  it('keeps sound above the new Nyquist from folding back as a false pitch', () => {
    // 15 kHz at 48 kHz would alias to 7.05 kHz at 22050 Hz without the filter
    const out = new Resampler(48000, SAMPLE_RATE).process(sine(15000, 48000, 1))
    expect(rms(out, 500)).toBeLessThan(0.005)
  })

  it('gives the same samples however the input is chunked', () => {
    const input = sine(1000, 48000, 1)
    const whole = new Resampler(48000, SAMPLE_RATE).process(input)
    const chunked = inChunks(new Resampler(48000, SAMPLE_RATE), input, [128, 4096, 7, 1000])
    expect(chunked.length).toBe(whole.length)
    for (let i = 0; i < whole.length; i += 97) expect(chunked[i]).toBeCloseTo(whole[i], 6)
  })

  it('over an hour, places every sample at its exact ratio (no drift)', () => {
    const rs = new Resampler(48000, SAMPLE_RATE)
    const chunk = new Float32Array(48000)
    let out = 0
    for (let s = 0; s < 60; s++) out += rs.process(chunk).length
    // a minute of 48 kHz is exactly a minute of 22050 Hz, less the filter's lookahead
    expect(60 * SAMPLE_RATE - out).toBeGreaterThanOrEqual(0)
    expect(60 * SAMPLE_RATE - out).toBeLessThan(rs.half)
  })
})

describe('toInt16 and frame', () => {
  it('clips and scales to 16 bits', () => {
    expect(Array.from(toInt16(Float32Array.from([0, 1, -1, 2, -2, 0.5])))).toEqual([0, 32767, -32768, 32767, -32768, 16384])
  })

  it('frames a chunk as the service reads it: little-endian offset, then PCM', () => {
    const buf = frame(70000, Int16Array.from([1, -2]))
    const v = new DataView(buf)
    expect(buf.byteLength).toBe(12)
    expect(v.getBigUint64(0, true)).toBe(70000n)
    expect(v.getInt16(8, true)).toBe(1)
    expect(v.getInt16(10, true)).toBe(-2)
  })
})

describe('placeChunk: the night\'s clock', () => {
  it('follows the last chunk while audio keeps up with the wall clock', () => {
    expect(placeChunk(22050, 4096, 1.2)).toBe(22050)
    // a little behind (scheduling jitter) is not a gap
    expect(placeChunk(22050, 4096, 2.5)).toBe(22050)
  })

  it('leaves a gap where the page slept', () => {
    // 10 s of audio heard, but 60 s have passed: this chunk goes at 60 s
    expect(placeChunk(10 * 22050, 4096, 60)).toBe(60 * 22050 - 4096)
  })
})

// --- the link ---------------------------------------------------------------

class FakeSocket {
  static all = []
  constructor(url) {
    this.url = url
    this.sent = []
    this.bufferedAmount = 0
    FakeSocket.all.push(this)
  }
  send(data) {
    this.sent.push(typeof data === 'string' ? JSON.parse(data) : decode(data))
  }
  close() {
    this.closed = true
  }
  // the service's side
  open() {
    this.onopen()
  }
  say(msg) {
    this.onmessage({ data: JSON.stringify(msg) })
  }
  drop(code = 1006) {
    this.onclose({ code })
  }
  audio() {
    return this.sent.filter((m) => m.type === 'audio')
  }
}

function decode(buf) {
  const v = new DataView(buf)
  return { type: 'audio', offset: Number(v.getBigUint64(0, true)), length: (buf.byteLength - 8) / 2 }
}

const pcm = (n) => new Int16Array(n)
const flush = () => new Promise((r) => setTimeout(r, 0))

describe('ListenLink', () => {
  let events
  let statuses
  let link

  beforeEach(() => {
    FakeSocket.all = []
    events = []
    statuses = []
    link = new ListenLink({
      connect: async () => ({ url: 'wss://listen.test/listen', token: 'tok' }),
      streamId: 'stream-1',
      onEvent: (e) => events.push(e),
      onStatus: (s) => statuses.push(s),
      WebSocketImpl: FakeSocket,
    })
  })

  afterEach(() => vi.useRealTimers())

  it('signs in with its start message, never the URL, and sends audio once ready', async () => {
    link.start()
    await flush()
    const ws = FakeSocket.all[0]
    expect(ws.url).toBe('wss://listen.test/listen')
    link.push(0, pcm(4096)) // before ready: kept
    ws.open()
    expect(ws.sent[0]).toEqual({ type: 'start', stream_id: 'stream-1', sample_rate: 22050, token: 'tok' })
    expect(ws.audio()).toEqual([])
    ws.say({ type: 'ready', have: 0 })
    link.push(4096, pcm(4096))
    expect(ws.audio()).toEqual([
      { type: 'audio', offset: 0, length: 4096 },
      { type: 'audio', offset: 4096, length: 4096 },
    ])
    expect(statuses).toContain('live')
  })

  it('after a drop, resends from what the service has, on the same stream', async () => {
    vi.useFakeTimers()
    link.start()
    await vi.advanceTimersByTimeAsync(0)
    let ws = FakeSocket.all[0]
    ws.open()
    ws.say({ type: 'ready', have: 0 })
    link.push(0, pcm(4096))
    link.push(4096, pcm(4096))
    ws.say({ type: 'ack', have: 4096 }) // the second chunk was lost in the drop
    ws.drop()
    link.push(8192, pcm(4096)) // heard while disconnected
    expect(statuses).toContain('reconnecting')
    await vi.advanceTimersByTimeAsync(1000)
    ws = FakeSocket.all[1]
    ws.open()
    expect(ws.sent[0].stream_id).toBe('stream-1')
    ws.say({ type: 'ready', have: 4096 })
    expect(ws.audio()).toEqual([
      { type: 'audio', offset: 4096, length: 4096 },
      { type: 'audio', offset: 8192, length: 4096 },
    ])
    expect(link.stats.reconnects).toBe(1)
  })

  it('sends a skip where audio is missing, so the clock stays the night\'s', async () => {
    link.start()
    await flush()
    const ws = FakeSocket.all[0]
    ws.open()
    ws.say({ type: 'ready', have: 0 })
    link.push(0, pcm(4096))
    link.push(22050 * 30, pcm(4096)) // the page slept for half a minute
    expect(ws.sent.slice(1)).toEqual([
      { type: 'audio', offset: 0, length: 4096 },
      { type: 'skip', to: 22050 * 30 },
      { type: 'audio', offset: 22050 * 30, length: 4096 },
    ])
  })

  it('when the service has forgotten the stream, starts it again at the right time', async () => {
    vi.useFakeTimers()
    link.start()
    await vi.advanceTimersByTimeAsync(0)
    let ws = FakeSocket.all[0]
    ws.open()
    ws.say({ type: 'ready', have: 0 })
    link.push(0, pcm(4096))
    ws.say({ type: 'ack', have: 4096 })
    ws.drop()
    link.push(4096, pcm(4096))
    await vi.advanceTimersByTimeAsync(1000)
    ws = FakeSocket.all[1]
    ws.open()
    ws.say({ type: 'ready', have: 0 }) // idle too long: a new stream
    expect(ws.sent.slice(1)).toEqual([
      { type: 'skip', to: 4096 },
      { type: 'audio', offset: 4096, length: 4096 },
    ])
  })

  it('keeps at most keepSamples, and the skip covers what it let go', async () => {
    link.keepSamples = 8192
    link.push(0, pcm(4096))
    link.push(4096, pcm(4096))
    link.push(8192, pcm(4096))
    expect(link.queued).toBe(8192)
    expect(link.stats.dropped).toBe(4096)
    link.start()
    await flush()
    const ws = FakeSocket.all[0]
    ws.open()
    ws.say({ type: 'ready', have: 0 })
    expect(ws.sent[1]).toEqual({ type: 'skip', to: 4096 })
  })

  it('stops for good when the service refuses the sign-in', async () => {
    vi.useFakeTimers()
    link.start()
    await vi.advanceTimersByTimeAsync(0)
    FakeSocket.all[0].drop(4401)
    await vi.advanceTimersByTimeAsync(60000)
    expect(FakeSocket.all.length).toBe(1)
    expect(statuses.at(-1)).toBe('refused')
  })

  it('stops for good when Ceol says this person may not listen', async () => {
    const refused = Object.assign(new Error('no'), { refused: true })
    link.connect = async () => {
      throw refused
    }
    link.start()
    await flush()
    expect(FakeSocket.all.length).toBe(0)
    expect(statuses.at(-1)).toBe('refused')
  })

  it('passes each state on, and stop tells the service', async () => {
    const states = []
    link.onState = (s) => states.push(s)
    link.start()
    await flush()
    const ws = FakeSocket.all[0]
    ws.open()
    ws.say({ type: 'ready', have: 0 })
    ws.say({ type: 'state', t_ms: 4000, shown: 7, top: [] })
    expect(states).toEqual([{ type: 'state', t_ms: 4000, shown: 7, top: [] }])
    link.stop()
    expect(ws.sent.at(-1)).toEqual({ type: 'stop' })
    ws.say({ type: 'done', have: 0 })
    expect(ws.closed).toBe(true)
  })
})

// --- the page ---------------------------------------------------------------

describe('the listen test page', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('first paint: the microphone chosen, ready to start, nothing heard yet', () => {
    const { container } = render(App)
    expect(container.querySelector('#lt-mic').checked).toBe(true)
    expect(container.querySelector('#lt-start').disabled).toBe(false)
    expect(container.querySelector('#lt-connection').textContent.trim()).toBe('Not listening')
    expect(container.querySelector('#lt-now').textContent).toContain('The first answer comes after a few seconds of audio.')
  })

  it('a recording file must be chosen before it can start', async () => {
    const { container } = render(App)
    await fireEvent.click(container.querySelector('#lt-file'))
    expect(container.querySelector('#lt-file-input')).not.toBeNull()
    expect(container.querySelector('#lt-start').disabled).toBe(true)
  })

  it('says so when the microphone cannot be used, and does not connect', async () => {
    class Ctx {
      sampleRate = 48000
      state = 'running'
      audioWorklet = { addModule: async () => {} }
      createGain() {
        return { gain: {}, connect: (x) => x }
      }
      get destination() {
        return {}
      }
    }
    class Node {
      constructor() {
        this.port = {}
      }
      connect(x) {
        return x
      }
    }
    const fetchSpy = vi.fn()
    vi.stubGlobal('AudioContext', Ctx)
    vi.stubGlobal('AudioWorkletNode', Node)
    vi.stubGlobal('fetch', fetchSpy)
    URL.createObjectURL = () => 'blob:x'
    URL.revokeObjectURL = () => {}
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: async () => { throw new Error('Permission denied') } },
    })
    const { container } = render(App)
    await fireEvent.click(container.querySelector('#lt-start'))
    await waitFor(() => expect(container.querySelector('#lt-log').textContent).toContain("Couldn't use the microphone: Permission denied"))
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(container.querySelector('#lt-start')).not.toBeNull()
  })
})
