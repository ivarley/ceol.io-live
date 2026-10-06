// yin, as the lab's YinFrontEnd runs it (lab/frontends/trackers.py): librosa.yin over
// 160-1400 Hz with a trough threshold of 0.5, yin's one harmful mistake put right
// (`correctTwelfths`), and loudness relative to the span standing in for voicing.

import Accelerate
import Foundation

/// A tracker's frames: times (ms from the start of what it read), pitch (Hz, NaN where it
/// has none), and how voiced each frame is.
public struct Track: Sendable, Equatable {
    public var times: [Double]
    public var f0: [Double]
    public var voiced: [Double]

    public init(times: [Double] = [], f0: [Double] = [], voiced: [Double] = []) {
        self.times = times
        self.f0 = f0
        self.voiced = voiced
    }

    public var count: Int { times.count }
}

enum Yin {
    static let fmin = 160.0, fmax = 1400.0
    static let frameLength = 2048, hop = 256
    static let troughThreshold: Float = 0.5
    static let twelfthsRatio: Float = 3.0

    static func track(_ y: [Float], sr: Int) -> Track {
        guard y.count >= frameLength else { return Track() }
        var f0 = yin(y, sr: sr)
        f0 = correctTwelfths(y, sr: sr, f0: f0)
        let rms = rmsFrames(y)
        var ref = percentile(Array(rms.prefix(f0.count)), 90)
        if ref == 0 { ref = 1 }
        let n = f0.count
        var voiced = [Double](repeating: 0, count: n)
        for i in 0..<n {
            let r: Float = i < rms.count ? rms[i] : 0
            voiced[i] = Double(min(max(r / ref, 0), 1))
        }
        let times = (0..<n).map { Double($0) * Double(hop) * 1000.0 / Double(sr) }
        return Track(times: times, f0: f0.map(Double.init), voiced: voiced)
    }

    /// librosa.yin(y, fmin, fmax, sr, frame_length, hop_length, trough_threshold),
    /// centred with zero padding.
    static func yin(_ y: [Float], sr: Int) -> [Float] {
        let pad = frameLength / 2
        var padded = [Float](repeating: 0, count: y.count + 2 * pad)
        padded.replaceSubrange(pad..<(pad + y.count), with: y)
        let frames = 1 + (padded.count - frameLength) / hop
        let minPeriod = Int(floor(Double(sr) / fmax))
        let maxPeriod = min(Int(ceil(Double(sr) / fmin)), frameLength - 1)
        let m = maxPeriod - minPeriod + 1
        var out = [Float](repeating: 0, count: frames)
        var acf = [Float](repeating: 0, count: maxPeriod + 1)
        var cum = [Float](repeating: 0, count: maxPeriod + 1)
        var d = [Float](repeating: 0, count: maxPeriod + 1)
        var yf = [Float](repeating: 0, count: m)
        padded.withUnsafeBufferPointer { p in
            for f in 0..<frames {
                let x = p.baseAddress! + f * hop
                // autocorrelation over the frame, as librosa's (full, zero-padded) one
                for k in 0...maxPeriod {
                    var s: Float = 0
                    vDSP_dotpr(x, 1, x + k, 1, &s, vDSP_Length(frameLength - k))
                    acf[k] = s
                }
                // energy: the running sum of squares, in order, as numpy's cumsum
                var run: Float = 0
                for i in 0...maxPeriod {
                    run += x[i] * x[i]
                    cum[i] = run
                }
                d[0] = 0
                for k in 1...maxPeriod { d[k] = 2 * (acf[0] - acf[k]) - cum[k - 1] }
                // cumulative mean normalised difference
                var cm: Float = 0
                for k in 1...maxPeriod {
                    cm += d[k]
                    let mean = cm / Float(k)
                    if k >= minPeriod {
                        // numerator d[k] for k in minPeriod...maxPeriod, over the mean to k
                        yf[k - minPeriod] = d[k] / (mean + floatTiny)
                    }
                }
                _ = cm
                out[f] = Float(sr) / period(yf, minPeriod: minPeriod)
            }
        }
        return out
    }

    /// The chosen period, refined: the first trough under the threshold, else the lowest.
    private static func period(_ yf: [Float], minPeriod: Int) -> Float {
        let m = yf.count
        func trough(_ i: Int) -> Bool {
            if i == 0 { return yf[0] < yf[1] }
            if i == m - 1 { return yf[m - 1] < yf[m - 2] }
            return yf[i] < yf[i - 1] && yf[i] <= yf[i + 1]
        }
        var chosen = -1
        for i in 0..<m where trough(i) && yf[i] < troughThreshold {
            chosen = i
            break
        }
        if chosen < 0 {
            var best = 0
            for i in 1..<m where yf[i] < yf[best] { best = i }
            chosen = best
        }
        var shift: Float = 0
        if chosen > 0 && chosen < m - 1 {
            let a = yf[chosen + 1] + yf[chosen - 1] - 2 * yf[chosen]
            let b = (yf[chosen + 1] - yf[chosen - 1]) / 2
            shift = abs(b) >= abs(a) ? 0 : -b / a
        }
        return Float(minPeriod + chosen) + shift
    }

    /// librosa.feature.rms(y, frame_length, hop_length), centred with zero padding.
    static func rmsFrames(_ y: [Float]) -> [Float] {
        let pad = frameLength / 2
        var padded = [Float](repeating: 0, count: y.count + 2 * pad)
        padded.replaceSubrange(pad..<(pad + y.count), with: y)
        let frames = 1 + (padded.count - frameLength) / hop
        var out = [Float](repeating: 0, count: frames)
        padded.withUnsafeBufferPointer { p in
            for f in 0..<frames {
                var ms: Float = 0
                vDSP_measqv(p.baseAddress! + f * hop, 1, &ms, vDSP_Length(frameLength))
                out[f] = sqrt(ms)
            }
        }
        return out
    }

    /// Put back a note reported a twelfth too low: where the spectrum holds far more at
    /// 3*f0 than at f0 and 2*f0, the pitch is 3*f0 (lab: correct_twelfths).
    static func correctTwelfths(_ y: [Float], sr: Int, f0: [Float]) -> [Float] {
        let power = stftPower(y, nFFT: frameLength, hop: hop)
        let binHz = Double(sr) / Double(frameLength)
        let nyquist = Double(sr) / 2
        let bins = frameLength / 2 + 1
        var out = f0
        func energy(_ frame: Int, _ hz: Double) -> Float {
            if hz <= 0 || hz >= nyquist { return 0 }
            let b = Int((hz / binHz).roundedEven)
            let lo = max(0, b - 1), hi = min(bins, b + 2)
            guard hi > lo else { return 0 }
            var best: Float = 0
            for k in lo..<hi { best = max(best, sqrt(power[frame][k])) }
            return best
        }
        for i in 0..<min(f0.count, power.count) {
            let f = Double(f0[i])
            if !f.isFinite || f <= 0 || 3 * f >= nyquist { continue }
            let own = energy(i, f) + energy(i, 2 * f)
            let third = energy(i, 3 * f)
            if third > twelfthsRatio * (own + 1e-9) { out[i] = Float(3 * f) }
        }
        return out
    }
}
