// Spec 061 stage 2: the browser's audio, at whatever rate its AudioContext runs
// (44.1 or 48 kHz on a phone), down to the 22050 Hz the listening service takes
// (listen/service.py). A streaming windowed-sinc resampler: each output sample is
// the input low-passed just under the new Nyquist (so nothing above it folds back
// as a false pitch) and read at its fractional position. The rates' ratio is
// rational (48000 / 22050 = 320 / 147), so the filter is one table per phase,
// built once.

function gcd(a, b) {
  while (b) [a, b] = [b, a % b]
  return a
}

function sinc(x) {
  if (x === 0) return 1
  const px = Math.PI * x
  return Math.sin(px) / px
}

// Blackman, over |x| <= 1.
function blackman(x) {
  if (Math.abs(x) >= 1) return 0
  const u = (x + 1) / 2
  return 0.42 - 0.5 * Math.cos(2 * Math.PI * u) + 0.08 * Math.cos(4 * Math.PI * u)
}

export class Resampler {
  /**
   * @param {number} inRate  the input's sample rate (an integer, as AudioContext gives)
   * @param {number} outRate the output's (22050 for the service)
   * @param {number} zeroCrossings filter length: the sinc's zero crossings on each side
   */
  constructor(inRate, outRate, zeroCrossings = 12) {
    inRate = Math.round(inRate)
    outRate = Math.round(outRate)
    const g = gcd(inRate, outRate)
    this.L = inRate / g // input samples per M output samples
    this.M = outRate / g // phases
    if (this.M > 8192) throw new Error(`can't resample ${inRate} Hz to ${outRate} Hz`)
    // the cutoff, in cycles per input sample: 90% of the lower Nyquist
    const f = (0.45 * Math.min(inRate, outRate)) / inRate
    this.half = Math.ceil(zeroCrossings / (2 * f))
    const width = 2 * this.half
    this.table = []
    for (let p = 0; p < this.M; p++) {
      const frac = p / this.M
      const w = new Float32Array(width)
      let sum = 0
      for (let j = 0; j < width; j++) {
        const x = j - this.half + 1 - frac // tap j reads input i0 + j - half + 1
        w[j] = 2 * f * sinc(2 * f * x) * blackman(x / this.half)
        sum += w[j]
      }
      for (let j = 0; j < width; j++) w[j] /= sum // unity gain at DC, every phase
      this.table.push(w)
    }
    // Input kept for the filter's left side, starting at absolute input index
    // histStart. It begins as silence before the first sample.
    this.hist = new Float32Array(this.half)
    this.histStart = -this.half
    this.n = 0 // the next output sample
  }

  /** Feed the next input; returns the output samples it completes (often a few
   * fewer than in/out of the ratio, the rest once the filter's right side arrives). */
  process(input) {
    const buf = new Float32Array(this.hist.length + input.length)
    buf.set(this.hist)
    buf.set(input, this.hist.length)
    const end = this.histStart + buf.length // one past the last input sample
    const out = []
    const width = 2 * this.half
    for (;;) {
      const acc = this.n * this.L
      const i0 = Math.floor(acc / this.M)
      if (i0 + this.half > end) break // the right side hasn't arrived
      const w = this.table[acc % this.M]
      const base = i0 - this.half + 1 - this.histStart
      let y = 0
      for (let j = 0; j < width; j++) y += w[j] * buf[base + j]
      out.push(y)
      this.n++
    }
    const nextI0 = Math.floor((this.n * this.L) / this.M)
    const keepFrom = Math.max(this.histStart, nextI0 - this.half + 1)
    this.hist = buf.slice(keepFrom - this.histStart)
    this.histStart = keepFrom
    return Float32Array.from(out)
  }
}

/** Float samples (-1..1) as the 16-bit little-endian PCM the service takes. */
export function toInt16(samples) {
  const out = new Int16Array(samples.length)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    out[i] = s < 0 ? Math.round(s * 32768) : Math.round(s * 32767)
  }
  return out
}
