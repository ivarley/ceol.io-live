// The beat and where notes are struck: the lab's analysis/pulse.py (estimate_pulse,
// attack_times_ms) on librosa's onset strength and peak picker.

import Accelerate
import Foundation

public struct Pulse: Sendable, Equatable {
    public var periodMs: Double
    public var phaseMs: Double
    public var grouping: Int
    public var beatMs: Double
    public var duple: Double
    public var triple: Double
    public var groupingMargin: Double
    public var strength: Double
}

enum Onsets {
    static let hop = 256, nFFT = 2048, nMels = 128

    /// librosa.filters.mel(sr, n_fft, n_mels=128, fmin=0, fmax=sr/2), Slaney's scale and
    /// area normalisation.
    static func melFilters(sr: Int) -> [[Float]] {
        let fSp = 200.0 / 3, minLogHz = 1000.0, minLogMel = 1000.0 / fSp, logstep = log(6.4) / 27
        func hzToMel(_ f: Double) -> Double { f >= minLogHz ? minLogMel + log(f / minLogHz) / logstep : f / fSp }
        func melToHz(_ m: Double) -> Double { m >= minLogMel ? minLogHz * exp(logstep * (m - minLogMel)) : fSp * m }
        let bins = nFFT / 2 + 1
        let fft = (0..<bins).map { Double(sr) / 2 * Double($0) / Double(bins - 1) }
        let lo = hzToMel(0), hi = hzToMel(Double(sr) / 2)
        let melF = (0..<(nMels + 2)).map { melToHz(lo + (hi - lo) * Double($0) / Double(nMels + 1)) }
        var w = [[Float]](repeating: [Float](repeating: 0, count: bins), count: nMels)
        for i in 0..<nMels {
            let d0 = melF[i + 1] - melF[i], d1 = melF[i + 2] - melF[i + 1]
            let enorm = 2.0 / (melF[i + 2] - melF[i])
            for k in 0..<bins {
                let lower = -(melF[i] - fft[k]) / d0
                let upper = (melF[i + 2] - fft[k]) / d1
                w[i][k] = Float(max(0, min(lower, upper)) * enorm)
            }
        }
        return w
    }

    private static let filters = melFilters(sr: 22050)

    /// librosa.onset.onset_strength(y, sr, hop_length=256): the mean rise in log-mel
    /// power from one frame to the next. Empty for under eight hops of audio.
    static func envelope(_ y: [Float], sr: Int) -> [Float] {
        guard y.count >= hop * 8 else { return [] }
        let power = stftPower(y, nFFT: nFFT, hop: hop)
        let n = power.count
        let bins = nFFT / 2 + 1
        let w = sr == 22050 ? filters : melFilters(sr: sr)
        // log-mel power, floored at 1e-10 and at 80 dB under the loudest
        var db = [[Float]](repeating: [Float](repeating: 0, count: nMels), count: n)
        var top = -Float.infinity
        for f in 0..<n {
            power[f].withUnsafeBufferPointer { p in
                for m in 0..<nMels {
                    var s: Float = 0
                    vDSP_dotpr(w[m], 1, p.baseAddress!, 1, &s, vDSP_Length(bins))
                    let v = 10 * log10(max(1e-10, s))
                    db[f][m] = v
                    top = max(top, v)
                }
            }
        }
        let floor = top - 80
        var out = [Float](repeating: 0, count: n)
        let lead = 1 + nFFT / (2 * hop)
        guard n > lead else { return out }
        for f in 1..<(n - lead + 1) {
            var s: Float = 0
            for m in 0..<nMels {
                s += max(0, max(db[f][m], floor) - max(db[f - 1][m], floor))
            }
            out[f - 1 + lead] = s / Float(nMels)
        }
        return out
    }

    /// lab: attack_times_ms -> librosa.onset.onset_detect(delta=0.06), in ms from the
    /// start of `y`.
    static func attackTimesMs(_ y: [Float], sr: Int) -> [Double] {
        let env = envelope(y, sr: sr)
        guard env.count >= 4 else { return [] }
        return peaks(env, sr: sr, delta: 0.06).map { Double($0) * Double(hop) * 1000 / Double(sr) }
    }

    /// librosa's onset peak picker, the envelope normalised to 0...1 first.
    static func peaks(_ envelope: [Float], sr: Int, delta: Float) -> [Int] {
        let lo = envelope.min() ?? 0
        var x = envelope.map { $0 - lo }
        let hi = x.max() ?? 0
        x = x.map { $0 / (hi + floatTiny) }
        guard x.contains(where: { $0 != 0 }), x.allSatisfy({ $0.isFinite }) else { return [] }
        let per = Double(sr) / Double(hop)
        let preMax = Int(ceil((0.03 * per).rounded(.down))), postMax = 1
        let preAvg = Int(ceil((0.10 * per).rounded(.down))), postAvg = Int((0.10 * per).rounded(.down)) + 1
        let wait = Int(ceil((0.03 * per).rounded(.down)))
        let n = x.count
        func mean(_ a: Int, _ b: Int) -> Float {
            var s: Float = 0
            for i in a..<b { s += x[i] }
            return s / Float(b - a)
        }
        var out = [Int]()
        var first = x[0] >= x[0..<min(postMax, n)].max()!
        first = first && x[0] >= mean(0, min(postAvg, n)) + delta
        if first { out.append(0) }
        var i = first ? wait + 1 : 1
        while i < n {
            let maxn = x[max(0, i - preMax)..<min(i + postMax, n)].max()!
            if x[i] != maxn {
                i += 1
                continue
            }
            if !(x[i] >= mean(max(0, i - preAvg), min(i + postAvg, n)) + delta) {
                i += 1
                continue
            }
            out.append(i)
            i += wait + 1
        }
        return out
    }
}

enum PulseEstimate {
    static let minBeatS = 0.26, maxBeatS = 0.62
    static let dupleWindow = (0.44, 0.57)
    static let tripleWindows = [(0.28, 0.41), (0.59, 0.72)]
    static let halvingRatio: Float = 0.80

    /// lab: estimate_pulse. nil when there is nothing periodic to find.
    static func estimate(_ y: [Float], sr: Int) -> Pulse? {
        let onset = Onsets.envelope(y, sr: sr)
        guard onset.count >= 64 else { return nil }
        let ac = autocorrelation(onset)
        let fps = Double(sr) / Double(Onsets.hop)
        guard ac.count >= Int(1.2 * fps) else { return nil }
        var (strength, beatS) = strongestPeak(ac, minBeatS, maxBeatS, fps)
        guard beatS > 0 else { return nil }
        // step down an octave while half the period is still a plausible beat
        while true {
            let half = beatS / 2
            if half < minBeatS { break }
            let (hs, hsS) = strongestPeak(ac, half * 0.94, half * 1.06, fps)
            if hs < halvingRatio * strength { break }
            (strength, beatS) = (hs, hsS)
        }
        let duple = strongestPeak(ac, dupleWindow.0 * beatS, dupleWindow.1 * beatS, fps).0
        let thirds = tripleWindows.map { strongestPeak(ac, $0.0 * beatS, $0.1 * beatS, fps).0 }
        let triple = (Double(thirds[0]) + Double(thirds[1])) / 2
        let grouping = triple > Double(duple) ? 3 : 2
        let periodS = beatS / Double(grouping)
        let phaseS = phase(onset, periodFrames: beatS * fps, fps: fps) / fps
        let winner = max(Double(duple), triple), loser = min(Double(duple), triple)
        return Pulse(periodMs: periodS * 1000, phaseMs: phaseS * 1000, grouping: grouping, beatMs: beatS * 1000,
                     duple: Double(duple), triple: triple, groupingMargin: min(max(winner - max(loser, 0), 0), 1),
                     strength: Double(strength))
    }

    static func autocorrelation(_ onset: [Float]) -> [Float] {
        var mean: Float = 0
        vDSP_meanv(onset, 1, &mean, vDSP_Length(onset.count))
        let x = onset.map { $0 - mean }
        var denom: Float = 0
        vDSP_dotpr(x, 1, x, 1, &denom, vDSP_Length(x.count))
        if denom == 0 { denom = 1 }
        var ac = [Float](repeating: 0, count: x.count)
        x.withUnsafeBufferPointer { p in
            for k in 0..<x.count {
                var s: Float = 0
                vDSP_dotpr(p.baseAddress!, 1, p.baseAddress! + k, 1, &s, vDSP_Length(x.count - k))
                ac[k] = s / denom
            }
        }
        return ac
    }

    /// (height, period in seconds) of the tallest peak in a lag window.
    static func strongestPeak(_ ac: [Float], _ loS: Double, _ hiS: Double, _ fps: Double) -> (Float, Double) {
        let lo = max(2, Int(loS * fps)), hi = min(ac.count - 1, Int(hiS * fps))
        guard hi > lo else { return (0, 0) }
        var best: (Float, Int)? = nil
        for i in lo..<hi where ac[i] >= ac[i - 1] && ac[i] >= ac[i + 1] {
            // Python's max over (height, lag): the taller, and on a tie the longer lag
            if best == nil || ac[i] > best!.0 || (ac[i] == best!.0 && i > best!.1) { best = (ac[i], i) }
        }
        guard let (height, lag) = best else {
            return (ac[lo..<hi].max()!, Double(lo + hi) / 2 / fps)
        }
        return (height, refine(ac, lag) / fps)
    }

    static func refine(_ ac: [Float], _ lag: Int) -> Double {
        if lag <= 0 || lag + 1 >= ac.count { return Double(lag) }
        let a = ac[lag - 1], b = ac[lag], c = ac[lag + 1]
        let denom = a - 2 * b + c
        if abs(denom) < 1e-12 { return Double(lag) }
        return Double(lag) + Double(min(max(0.5 * (a - c) / denom, -0.5), 0.5))
    }

    /// Where the grid starts: the offset whose pulse train best fits the onsets.
    static func phase(_ onset: [Float], periodFrames: Double, fps: Double, resolutionS: Double = 0.002) -> Double {
        let period = max(2.0, periodFrames)
        let steps = Int(min(max((period / max(1e-6, resolutionS * fps)).roundedEven, 24), 512))
        let n = onset.count
        let count = Int(ceil(Double(n) / period))
        let positions = (0..<count).map { Double($0) * period }
        var bestOffset = 0.0, bestScore = -Double.infinity
        let step = period / Double(steps)
        for s in 0..<steps {
            let offset = Double(s) * step
            var sum: Float = 0
            var m = 0
            for p in positions {
                let i = Int((p + offset).roundedEven)
                if i < n {
                    sum += onset[i]
                    m += 1
                }
            }
            guard m > 0 else { continue }
            let score = Double(sum) / Double(m)
            if score > bestScore { (bestOffset, bestScore) = (offset, score) }
        }
        return bestOffset
    }
}
