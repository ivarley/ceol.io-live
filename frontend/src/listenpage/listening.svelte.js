// i18n-converted
// Spec 061: one listening run in the browser, shared by the Listen page (Ad-hoc mode)
// and a night's logger (Log mode). It joins the stage 2 pieces, the microphone
// (../listentest/capture.js) and the link to the listening service (link.js), to the
// meter (meter.js), and holds what a page shows about them. The page decides what a
// sure tune leads to; this only says when the meter became sure (`onSure`).
import { t } from '../lib/i18n/index.js'
import { ListenLink, SAMPLE_RATE } from '../listentest/link.js'
import { startCapture } from '../listentest/capture.js'
import { Meter } from './meter.js'

async function connect() {
  const r = await fetch('/api/listen/connection', { credentials: 'same-origin' })
  const body = await r.json().catch(() => ({}))
  if (r.status === 401 || r.status === 403) {
    const e = new Error(body.message || t("You can't listen on Ceol's server."))
    e.refused = true
    throw e
  }
  if (!r.ok || !body.success) throw new Error(body.message || `HTTP ${r.status}`)
  return body
}

export class Listening {
  phase = $state('idle') // idle | starting | running
  status = $state('idle') // the link's: connecting | live | reconnecting | refused | stopped
  error = $state('')
  clockS = $state(0)
  backlogS = $state(0)
  lagS = $state(0)
  version = $state(0) // bumped whenever the meter changes

  /**
   * @param {object} o
   * @param {(pick: {tune: object, log: boolean}) => void} [o.onSure] the meter became sure by itself
   * @param {(state: object) => void} [o.onState] after every state (the meter has taken it)
   */
  constructor({ onSure = () => {}, onState = () => {} } = {}) {
    this.meter = new Meter()
    this.onSure = onSure
    this.onState = onState
    this.link = null
    this.capture = null
    this.tick = null
    this.onOnline = () => this.link && this.link.nudge()
  }

  /** Starts the microphone and the stream. `instanceId`: the night whose session's
   * tunes the listener should prefer. */
  async start({ instanceId = null } = {}) {
    if (this.phase !== 'idle') return
    this.phase = 'starting'
    this.error = ''
    this.status = 'connecting'
    const link = new ListenLink({
      connect,
      streamId: crypto.randomUUID(),
      instanceId,
      onState: (s) => this.received(s),
      onStatus: (s, detail) => {
        this.status = s
        if (s === 'refused') this.error = detail || t("You can't listen on Ceol's server.")
      },
    })
    this.link = link
    try {
      this.capture = await startCapture({ source: 'mic', onChunk: (offset, pcm) => link.push(offset, pcm) })
    } catch (e) {
      this.error =
        e && e.name === 'NotAllowedError'
          ? t('Ceol needs the microphone to listen. Allow it in your browser’s settings for this site.')
          : t("Couldn't use the microphone: {error}", { error: e.message })
      this.link = null
      this.phase = 'idle'
      this.status = 'idle'
      return
    }
    link.start()
    window.addEventListener('online', this.onOnline)
    this.tick = setInterval(() => {
      this.clockS = this.capture ? this.capture.captured() / SAMPLE_RATE : 0
      this.backlogS = this.link ? this.link.backlog() / SAMPLE_RATE : 0
    }, 500)
    this.phase = 'running'
  }

  async stop() {
    if (this.phase !== 'running') return
    this.phase = 'idle'
    clearInterval(this.tick)
    window.removeEventListener('online', this.onOnline)
    if (this.link) this.link.stop()
    this.link = null
    const capture = this.capture
    this.capture = null
    this.clockS = 0
    this.backlogS = 0
    this.meter = new Meter()
    this.status = 'idle'
    this.version++
    if (capture) await capture.stop()
  }

  received(s) {
    const pick = this.meter.received(s)
    this.lagS = (s.lag_ms || 0) / 1000
    this.version++
    if (pick) this.onSure(pick)
    this.onState(s)
  }

  /** A tap to the service (from the meter's tapThis, tapNone, wrongTune or tuneChanged). */
  send(message) {
    if (message && this.link) this.link.send(message)
    this.version++
  }

  /** What the status line says about the link. */
  get linkText() {
    if (this.status === 'connecting') return t('Connecting to the listener…')
    if (this.status === 'reconnecting') return t('Reconnecting to the listener…')
    if (this.status === 'refused') return t('Not allowed to listen')
    if (this.backlogS > 8 || this.lagS > 8) return t('Catching up, {n} s behind', { n: Math.round(Math.max(this.backlogS, this.lagS)) })
    return t('Listening')
  }
}

/** A clock: m:ss, or h:mm:ss. */
export function clock(s) {
  const total = Math.max(0, Math.floor(s))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const sec = String(total % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

// The app-wide tune sheet (base.html loads it on every page), for a tune Ceol holds.
// The listener knows every tune on thesession.org, and Ceol imports one only when
// someone adds it, so a tune it doesn't hold yet opens on thesession.org instead.
// Returns thesession.org's address when a new tab was blocked and the page is
// listening (leaving it would stop the listening), for the page to offer as a link.
export async function openTune(tuneId, { listening = false } = {}) {
  let held = true
  try {
    held = (await fetch(`/api/tunes/${tuneId}/detail`, { credentials: 'same-origin' })).status !== 404
  } catch {}
  if (held && window.TuneDetailModal) {
    window.TuneDetailModal.show({ tuneId })
    return null
  }
  const url = `https://thesession.org/tunes/${tuneId}`
  // not 'noopener', which makes open() return null even when the tab opened
  const tab = window.open(url, '_blank')
  if (tab) {
    tab.opener = null
    return null
  }
  if (listening) return url
  window.location.href = url
  return null
}
