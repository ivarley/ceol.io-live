// The numerical pieces the hearing shares: a real FFT, the short-time spectrum librosa
// takes, and the few numpy behaviours the lab's code leans on (round half to even, a
// left search in sorted times, linear percentiles). Each is written to give what the lab
// gives, because the fixtures hold the stages to the lab's numbers.

import Accelerate
import Foundation

/// The true DFT of real input of a power-of-two length: bins 0...n/2.
final class RealFFT {
    let n: Int
    private let log2n: vDSP_Length
    private let setup: FFTSetup
    private var re: [Float]
    private var im: [Float]

    init(n: Int) {
        precondition(n > 1 && n & (n - 1) == 0, "power of two")
        self.n = n
        log2n = vDSP_Length(log2(Double(n)))
        setup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2))!
        re = [Float](repeating: 0, count: n / 2)
        im = [Float](repeating: 0, count: n / 2)
    }

    deinit { vDSP_destroy_fftsetup(setup) }

    /// Power |X_k|^2 of `x` (zero-padded to n) for k in 0...n/2, into `out`.
    func power(_ x: UnsafePointer<Float>, count: Int, into out: UnsafeMutablePointer<Float>) {
        var buffer = [Float](repeating: 0, count: n)
        buffer.withUnsafeMutableBufferPointer { b in
            b.baseAddress!.update(from: x, count: min(count, n))
        }
        re.withUnsafeMutableBufferPointer { rp in
            im.withUnsafeMutableBufferPointer { ip in
                var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                buffer.withUnsafeBufferPointer { b in
                    b.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: n / 2) {
                        vDSP_ctoz($0, 2, &split, 1, vDSP_Length(n / 2))
                    }
                }
                vDSP_fft_zrip(setup, &split, 1, log2n, FFTDirection(FFT_FORWARD))
                // zrip gives twice the DFT, with bin n/2's real part in imagp[0]
                let dc = rp[0] / 2, nyquist = ip[0] / 2
                out[0] = dc * dc
                out[n / 2] = nyquist * nyquist
                for k in 1..<(n / 2) {
                    let a = rp[k] / 2, b = ip[k] / 2
                    out[k] = a * a + b * b
                }
            }
        }
    }
}

/// scipy's periodic Hann window (librosa's default for a spectrum).
func hann(_ n: Int) -> [Float] {
    (0..<n).map { Float(0.5 - 0.5 * cos(2.0 * Double.pi * Double($0) / Double(n))) }
}

/// librosa.stft(y, n_fft, hop, center=True, pad_mode="constant") as power, frame-major:
/// frames x (n_fft/2 + 1).
func stftPower(_ y: [Float], nFFT: Int = 2048, hop: Int = 256) -> [[Float]] {
    let pad = nFFT / 2
    var padded = [Float](repeating: 0, count: y.count + 2 * pad)
    padded.replaceSubrange(pad..<(pad + y.count), with: y)
    let frames = 1 + (padded.count - nFFT) / hop
    guard frames > 0 else { return [] }
    let window = hann(nFFT)
    let fft = RealFFT(n: nFFT)
    var out = [[Float]](repeating: [Float](repeating: 0, count: nFFT / 2 + 1), count: frames)
    var windowed = [Float](repeating: 0, count: nFFT)
    padded.withUnsafeBufferPointer { p in
        for f in 0..<frames {
            vDSP_vmul(p.baseAddress! + f * hop, 1, window, 1, &windowed, 1, vDSP_Length(nFFT))
            out[f].withUnsafeMutableBufferPointer { o in
                fft.power(windowed, count: nFFT, into: o.baseAddress!)
            }
        }
    }
    return out
}

extension Double {
    /// numpy's round: half to even.
    var roundedEven: Double { rounded(.toNearestOrEven) }
}

/// numpy.searchsorted(sorted, x, side="left").
func searchSorted(_ sorted: [Double], _ x: Double) -> Int {
    var lo = 0, hi = sorted.count
    while lo < hi {
        let mid = (lo + hi) / 2
        if sorted[mid] < x { lo = mid + 1 } else { hi = mid }
    }
    return lo
}

/// numpy.percentile with its default linear interpolation.
func percentile(_ x: [Float], _ q: Double) -> Float {
    guard !x.isEmpty else { return 0 }
    let s = x.sorted()
    let pos = q / 100 * Double(s.count - 1)
    let lo = Int(pos.rounded(.down)), hi = min(lo + 1, s.count - 1)
    let frac = Float(pos - Double(lo))
    return s[lo] + (s[hi] - s[lo]) * frac
}

/// Python's % for a positive modulus: never negative.
func pymod(_ a: Int, _ m: Int) -> Int { ((a % m) + m) % m }

/// librosa.hz_to_midi.
func hzToMidi(_ hz: Double) -> Double { 12 * (log2(hz) - log2(440.0)) + 69 }

/// The smallest normal Float, numpy's `tiny` for float32.
let floatTiny = Float.leastNormalMagnitude
