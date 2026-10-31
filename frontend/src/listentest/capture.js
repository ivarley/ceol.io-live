// Spec 061 stage 2: what the browser hears, as 22050 Hz chunks on the night's
// clock. The source is the microphone, or a recording file played through the
// same path (for a desktop with nobody playing, and for tests of the pipeline).
//
// The night's clock is the wall clock from the moment listening started, not the
// count of samples heard: when the page sleeps (a phone's screen goes off, Chrome
// on Android freezes a hidden tab) no audio arrives, and the next chunk is placed
// where the wall clock says, leaving a gap the link sends as a skip.
//
// Everything the browser does that matters to whether this works on a phone
// (page hidden or shown, the audio context suspended, the microphone muted, the
// wake lock lost) is reported through onEvent, for the page's log.

// i18n-converted
import { t } from '../lib/i18n/index.js'
import { Resampler, toInt16 } from './resample.js'
import { SAMPLE_RATE } from './link.js'

const GAP_S = 2 // a shortfall against the wall clock longer than this is a gap

// The AudioContext's states, as words.
function audioState(state) {
  return (
    {
      running: t('running'),
      suspended: t('suspended'),
      interrupted: t('interrupted'),
      closed: t('closed'),
    }[state] || state
  )
}

// Copies each 128-sample render quantum out to the page, in batches.
const WORKLET = `
class Tap extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(4096); this.n = 0 }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (ch) {
      for (let i = 0; i < ch.length; i++) {
        this.buf[this.n++] = ch[i]
        if (this.n === this.buf.length) { this.port.postMessage(this.buf); this.buf = new Float32Array(4096); this.n = 0 }
      }
    }
    return true
  }
}
registerProcessor('ceol-tap', Tap)
`

/** Where the next chunk goes on the night's clock: after the last one, unless
 * the wall clock has run more than GAP_S ahead of the audio (the page slept). */
export function placeChunk(captured, length, elapsedS, sampleRate = SAMPLE_RATE) {
  const due = Math.round(elapsedS * sampleRate) - length
  return due - captured > GAP_S * sampleRate ? due : captured
}

/**
 * Start hearing.
 * @param {object} o
 * @param {'mic'|File} o.source
 * @param {(offset: number, pcm: Int16Array) => void} o.onChunk
 * @param {(level: number) => void} [o.onLevel] the last chunk's RMS
 * @param {(text: string) => void} [o.onEvent]
 * @param {() => void} [o.onEnded] a file source played to its end
 * @returns {Promise<{stop: () => Promise<void>, captured: () => number, sampleRate: number}>}
 */
export async function startCapture({ source, onChunk, onLevel = () => {}, onEvent = () => {}, onEnded = () => {} }) {
  const ctx = new AudioContext()
  const resampler = new Resampler(ctx.sampleRate, SAMPLE_RATE)
  onEvent(t('Hearing at {rate} Hz, sending at {sent} Hz.', { rate: ctx.sampleRate, sent: SAMPLE_RATE }))
  const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }))
  await ctx.audioWorklet.addModule(url)
  URL.revokeObjectURL(url)
  const tap = new AudioWorkletNode(ctx, 'ceol-tap', { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1, channelCountMode: 'explicit' })
  // The tap must reach the destination to be pulled; silently.
  const mute = ctx.createGain()
  mute.gain.value = 0
  tap.connect(mute).connect(ctx.destination)

  let stream = null
  let player = null
  if (source === 'mic') {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
    })
    const track = stream.getAudioTracks()[0]
    const settings = track.getSettings ? track.getSettings() : {}
    onEvent(t('Microphone: {name}, {rate} Hz.', { name: track.label || '?', rate: settings.sampleRate || '?' }))
    track.onmute = () => onEvent(t('The browser muted the microphone.'))
    track.onunmute = () => onEvent(t('The microphone is back.'))
    track.onended = () => onEvent(t('The microphone stopped.'))
    ctx.createMediaStreamSource(stream).connect(tap)
  } else {
    const audio = await ctx.decodeAudioData(await source.arrayBuffer())
    onEvent(t('File: {name}, {seconds}s.', { name: source.name, seconds: audio.duration.toFixed(0) }))
    player = ctx.createBufferSource()
    player.buffer = audio
    player.connect(tap)
    player.connect(ctx.destination) // you hear what it hears
    player.onended = () => onEnded()
    player.start()
  }
  // A browser starts audio only after a tap on the page. Start's own tap counts
  // (the context was made before the first await), but if it is held back anyway,
  // say so and start on the next tap rather than wait for ever.
  if (ctx.state !== 'running') {
    await Promise.race([ctx.resume(), new Promise((r) => setTimeout(r, 1500))])
    if (ctx.state !== 'running') {
      onEvent(t('The browser is holding the audio back. Tap the page to let it start.'))
      const onTap = () =>
        ctx.resume().then(() => {
          if (ctx.state === 'running') document.removeEventListener('pointerdown', onTap)
        })
      document.addEventListener('pointerdown', onTap)
    }
  }

  let started = null // performance.now() of the first sample
  let captured = 0
  tap.port.onmessage = (ev) => {
    const now = performance.now()
    const out = resampler.process(ev.data)
    if (!out.length) return
    if (started === null) started = now - (out.length / SAMPLE_RATE) * 1000
    const at = placeChunk(captured, out.length, (now - started) / 1000)
    if (at > captured) onEvent(t('No audio for {seconds}s. Was the page asleep?', { seconds: ((at - captured) / SAMPLE_RATE).toFixed(1) }))
    let sum = 0
    for (let i = 0; i < out.length; i++) sum += out[i] * out[i]
    onLevel(Math.sqrt(sum / out.length))
    onChunk(at, toInt16(out))
    captured = at + out.length
  }

  // --- staying awake, and saying when we don't --------------------------------
  let wakeLock = null
  async function lockScreen() {
    if (!('wakeLock' in navigator)) {
      onEvent(t("This browser can't keep the screen on. Keep it on yourself."))
      return
    }
    try {
      wakeLock = await navigator.wakeLock.request('screen')
      onEvent(t('The screen stays on.'))
      wakeLock.addEventListener('release', () => onEvent(t('The screen may turn off again.')))
    } catch (e) {
      onEvent(t("Couldn't keep the screen on: {error}", { error: e.message }))
    }
  }
  const onVisibility = () => {
    onEvent(
      document.visibilityState === 'visible'
        ? t('Page shown. Audio is {state}.', { state: audioState(ctx.state) })
        : t('Page hidden. Audio is {state}.', { state: audioState(ctx.state) })
    )
    if (document.visibilityState === 'visible') {
      if (ctx.state === 'suspended' || ctx.state === 'interrupted') ctx.resume()
      if (!wakeLock || wakeLock.released) lockScreen()
    }
  }
  const onFreeze = () => onEvent(t('The browser froze the page.'))
  const onResume = () => onEvent(t('The browser woke the page.'))
  ctx.onstatechange = () => onEvent(t('Audio is {state}.', { state: audioState(ctx.state) }))
  document.addEventListener('visibilitychange', onVisibility)
  document.addEventListener('freeze', onFreeze)
  document.addEventListener('resume', onResume)
  await lockScreen()

  return {
    sampleRate: ctx.sampleRate,
    captured: () => captured,
    async stop() {
      document.removeEventListener('visibilitychange', onVisibility)
      document.removeEventListener('freeze', onFreeze)
      document.removeEventListener('resume', onResume)
      tap.port.onmessage = null
      if (player) {
        player.onended = null
        try {
          player.stop()
        } catch {}
      }
      if (stream) stream.getTracks().forEach((t) => t.stop())
      if (wakeLock && !wakeLock.released) await wakeLock.release().catch(() => {})
      await ctx.close().catch(() => {})
    },
  }
}
