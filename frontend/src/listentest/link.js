// Spec 061 stage 2: the browser's side of the listening service's WebSocket
// (the protocol is in listen/service.py's docstring). Audio goes up as chunks
// tagged with their sample offset on the night's clock; the service acknowledges
// how much it has, and every 4 s of audio answers with a "state".
//
// A dropped connection loses nothing it can help: chunks are kept until the
// service has them, a reconnect resumes the same stream_id, and the service's
// "ready" says where to resend from. Where audio is missing (kept too long and
// dropped, or never captured because the page was asleep) the link sends a
// "skip" to the next chunk's offset, so the service fills it with silence and
// its clock stays the night's.

// i18n-converted
import { t } from '../lib/i18n/index.js'

export const SAMPLE_RATE = 22050
const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000]
const MAX_BUFFERED = 1 << 20 // bytes waiting in the socket before we hold off

/** One chunk as the service takes it: 8-byte little-endian offset, then 16-bit
 * little-endian PCM. */
export function frame(offset, pcm) {
  const buf = new ArrayBuffer(8 + pcm.length * 2)
  const view = new DataView(buf)
  view.setBigUint64(0, BigInt(offset), true)
  for (let i = 0; i < pcm.length; i++) view.setInt16(8 + i * 2, pcm[i], true)
  return buf
}

export class ListenLink {
  /**
   * @param {object} o
   * @param {() => Promise<{url: string, token: string}>} o.connect where to connect, and the token
   * @param {string} o.streamId the same id on every reconnect, so the service resumes the stream
   * @param {number} [o.instanceId] the night, so the service prefers its session's tunes
   * @param {number} [o.keepSamples] most audio kept for resending (default ten minutes)
   * @param {(state: object) => void} [o.onState]
   * @param {(status: string, detail?: string) => void} [o.onStatus] connecting | live | reconnecting | refused | stopped
   * @param {(text: string) => void} [o.onEvent] a line for the page's log
   */
  constructor({
    connect,
    streamId,
    instanceId = null,
    keepSamples = 600 * SAMPLE_RATE,
    onState = () => {},
    onStatus = () => {},
    onEvent = () => {},
    WebSocketImpl = globalThis.WebSocket,
    timers = globalThis,
  }) {
    Object.assign(this, { connect, streamId, instanceId, keepSamples, onState, onStatus, onEvent })
    this.WS = WebSocketImpl
    this.timers = timers
    this.queue = [] // [{offset, pcm}] not yet acknowledged, in offset order
    this.queued = 0 // samples in the queue
    this.acked = 0 // the service has every sample before this
    this.sentEnd = 0 // on this socket, sent (or skipped) up to here
    this.ws = null
    this.ready = false
    this.stopped = false
    this.attempt = 0
    this.retryTimer = null
    this.status = 'idle'
    this.stats = { reconnects: 0, skips: 0, dropped: 0, states: 0 }
  }

  start() {
    this.open()
  }

  /** The next chunk of the night's audio, at `offset` samples. */
  push(offset, pcm) {
    if (!pcm.length) return
    this.queue.push({ offset, pcm })
    this.queued += pcm.length
    // Memory is bounded: past keepSamples the oldest goes, and a skip covers it.
    while (this.queued > this.keepSamples && this.queue.length > 1) {
      const old = this.queue.shift()
      this.queued -= old.pcm.length
      this.stats.dropped += old.pcm.length
    }
    this.flush()
  }

  /** Samples captured but not yet acknowledged. */
  backlog() {
    if (!this.queue.length) return 0
    const last = this.queue[this.queue.length - 1]
    return Math.max(0, last.offset + last.pcm.length - this.acked)
  }

  /** Reconnect now rather than at the next backoff (the network came back). */
  nudge() {
    if (this.stopped || this.ws) return
    this.timers.clearTimeout(this.retryTimer)
    this.attempt = 0
    this.open()
  }

  /** Stop: the service closes the stream and keeps nothing waiting. */
  stop() {
    this.stopped = true
    this.timers.clearTimeout(this.retryTimer)
    if (this.ws && this.ready) {
      try {
        this.ws.send(JSON.stringify({ type: 'stop' }))
      } catch {}
      // wait briefly for "done"; close regardless
      this.timers.setTimeout(() => this.close(), 3000)
    } else {
      this.close()
    }
    this.setStatus('stopped')
  }

  // --- internals -----------------------------------------------------------

  setStatus(status, detail) {
    this.status = status
    this.onStatus(status, detail)
  }

  close() {
    if (this.ws) {
      const ws = this.ws
      this.ws = null
      this.ready = false
      try {
        ws.close()
      } catch {}
    }
  }

  async open() {
    if (this.stopped) return
    this.setStatus(this.attempt ? 'reconnecting' : 'connecting')
    let conn
    try {
      conn = await this.connect()
    } catch (e) {
      if (e && e.refused) {
        this.setStatus('refused', e.message)
        this.stopped = true
        return
      }
      this.onEvent(t("Couldn't reach Ceol: {error}", { error: e && e.message ? e.message : String(e) }))
      return this.retry()
    }
    if (this.stopped) return
    let ws
    try {
      ws = new this.WS(conn.url)
    } catch (e) {
      this.onEvent(t("Couldn't connect to Ceol's server: {error}", { error: e.message }))
      return this.retry()
    }
    ws.binaryType = 'arraybuffer'
    this.ws = ws
    this.ready = false
    ws.onopen = () => {
      const start = { type: 'start', stream_id: this.streamId, sample_rate: SAMPLE_RATE, token: conn.token }
      if (this.instanceId) start.instance_id = this.instanceId
      ws.send(JSON.stringify(start))
    }
    ws.onmessage = (ev) => {
      if (ws !== this.ws) return
      let m
      try {
        m = JSON.parse(ev.data)
      } catch {
        return
      }
      this.receive(m)
    }
    ws.onclose = (ev) => {
      if (ws !== this.ws) return
      this.ws = null
      this.ready = false
      if (this.stopped) return
      if (ev.code === 4401) {
        this.stopped = true
        this.setStatus('refused')
        this.onEvent(t("Ceol's server refused this sign-in."))
        return
      }
      this.onEvent(t('The connection closed ({code}).', { code: ev.code }))
      this.retry()
    }
    ws.onerror = () => {} // onclose follows and decides
  }

  retry() {
    if (this.stopped) return
    const delay = BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)]
    this.attempt++
    this.setStatus('reconnecting', `${delay / 1000}s`)
    this.retryTimer = this.timers.setTimeout(() => this.open(), delay)
  }

  receive(m) {
    switch (m.type) {
      case 'ready':
        if (this.attempt) this.stats.reconnects++
        this.attempt = 0
        this.ready = true
        // Exactly what the service has, even if less than it acknowledged before
        // (it forgets a stream left idle for five minutes): flush skips the rest.
        this.acked = 0
        this.setAcked(m.have || 0)
        this.sentEnd = this.acked
        this.onEvent(t('Connected. The server has {seconds}s of audio.', { seconds: (this.acked / SAMPLE_RATE).toFixed(1) }))
        this.setStatus('live')
        this.flush()
        break
      case 'ack':
        this.setAcked(m.have || 0)
        this.flush()
        break
      case 'state':
        this.stats.states++
        this.onState(m)
        break
      case 'done':
        this.close()
        break
      case 'error':
        this.onEvent(t('The server says: {error}', { error: m.error }))
        break
    }
  }

  setAcked(have) {
    this.acked = Math.max(this.acked, have)
    while (this.queue.length) {
      const c = this.queue[0]
      if (c.offset + c.pcm.length > this.acked) break
      this.queue.shift()
      this.queued -= c.pcm.length
    }
  }

  flush() {
    const ws = this.ws
    if (!ws || !this.ready) return
    for (const c of this.queue) {
      const end = c.offset + c.pcm.length
      if (end <= this.sentEnd) continue
      if (ws.bufferedAmount > MAX_BUFFERED) return // the next ack flushes again
      if (c.offset > this.sentEnd) {
        // audio that never was, or was dropped: silence on the service's clock
        ws.send(JSON.stringify({ type: 'skip', to: c.offset }))
        this.stats.skips++
        this.onEvent(t('Sent {seconds}s of silence where audio was missing.', { seconds: ((c.offset - this.sentEnd) / SAMPLE_RATE).toFixed(1) }))
        this.sentEnd = c.offset
      }
      const from = this.sentEnd - c.offset
      ws.send(frame(this.sentEnd, from ? c.pcm.subarray(from) : c.pcm))
      this.sentEnd = end
    }
  }
}
