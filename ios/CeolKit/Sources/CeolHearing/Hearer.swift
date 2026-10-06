// The hearing half of the listener, on the phone (spec 053, "Listening on the phone"):
// the lab's listen.Hearer. Every 4 s of audio it tracks the newest audio with yin,
// Basic Pitch and PESTO, makes each tracker's notes over the last 24 s (on the beat's
// grid, out-of-key notes dropped), and works out the features the music detector reads.
// What it heard goes to the listening service in place of the audio, and the service
// decides what is playing (listen/service.py, "heard" mode).

import CoreML
import Foundation

/// The two networks, compiled from the package's Models on first use.
public final class HearingModels: @unchecked Sendable {
    public let basicPitch: MLModel
    public let pesto: MLModel

    public init(computeUnits: MLComputeUnits = .all) throws {
        let config = MLModelConfiguration()
        config.computeUnits = computeUnits
        basicPitch = try MLModel(contentsOf: Self.compiled("basic_pitch"), configuration: config)
        pesto = try MLModel(contentsOf: Self.compiled("pesto"), configuration: config)
    }

    /// The model compiled once into Caches, again only when the package's copy changes.
    static func compiled(_ name: String) throws -> URL {
        guard let src = Bundle.module.url(forResource: name, withExtension: "mlpackage", subdirectory: "Models") else {
            throw CocoaError(.fileNoSuchFile)
        }
        let fm = FileManager.default
        let caches = try fm.url(for: .cachesDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            .appendingPathComponent("CeolHearing", isDirectory: true)
        try fm.createDirectory(at: caches, withIntermediateDirectories: true)
        let stamp = (try? fm.attributesOfItem(atPath: src.appendingPathComponent("Manifest.json").path)[.modificationDate]
                     as? Date)?.timeIntervalSince1970 ?? 0
        let dest = caches.appendingPathComponent("\(name)-\(Int(stamp)).mlmodelc")
        if fm.fileExists(atPath: dest.path) { return dest }
        let built = try MLModel.compileModel(at: src)
        try? fm.removeItem(at: dest)
        try fm.moveItem(at: built, to: dest)
        return dest
    }
}

/// One step's hearing: what the phone sends instead of the audio.
public struct Heard: Sendable {
    public let tMs: Int
    public let heardMs: Int
    /// Per tracker, its notes over the last 24 s.
    public let notes: [String: [Note]]
    /// The step's beat and music-detector features (lab: tuneness.audio_features).
    public let features: [String: Double?]
    /// Milliseconds each part of the step took.
    public let timing: [String: Int]

    /// The listening service's "heard" message (lab: listen.pack_heard).
    public func message() -> String {
        var feats = [String: Any]()
        for (k, v) in features {
            if let v, v.isFinite { feats[k] = k == "grouping" ? Int(v) as Any : v as Any } else { feats[k] = NSNull() }
        }
        let obj: [String: Any] = [
            "type": "heard", "t_ms": tMs, "heard_ms": heardMs,
            "notes": notes.mapValues { $0.map { [$0.t0, $0.t1, $0.midi] } },
            "features": feats,
        ]
        let data = (try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys])) ?? Data()
        return String(decoding: data, as: UTF8.self)
    }
}

public final class Hearer {
    public static let sampleRate = 22050
    public static let hopMs = 4000
    public static let poolMs = 24000
    public static let trackContextMs = 2000
    public static let trackers = ["yin", "basic_pitch", "pesto"]
    static let params: [String: NoteParams] = ["yin": .yin, "basic_pitch": .basicPitch, "pesto": .pesto]

    /// Replaceable: a phone falls back to models held to its CPU if a prediction fails.
    public var models: HearingModels
    private var samples = [Int16]()
    private var base = 0                 // the stream offset of samples[0]
    private var total = 0                // samples heard
    private let keep = 120 * 22050
    private(set) var tracks: [String: Track]
    private(set) var trackedTo = 0
    /// The next step's time (ms of audio).
    public private(set) var nextT = Hearer.hopMs

    public init(models: HearingModels) {
        self.models = models
        tracks = Dictionary(uniqueKeysWithValues: Self.trackers.map { ($0, Track()) })
    }

    public var durationMs: Int { Int(1000 * Double(total) / Double(Self.sampleRate)) }

    public func append(_ pcm: [Int16]) {
        samples.append(contentsOf: pcm)
        total += pcm.count
        if samples.count > 2 * keep {
            let drop = samples.count - keep
            samples.removeFirst(drop)
            base += drop
        }
    }

    /// The samples in [t0, t1) ms, as LiveStore.read cuts them.
    func readPCM(_ t0: Int, _ t1: Int) -> ArraySlice<Int16> {
        let a = Int(Double(t0) * Double(Self.sampleRate) / 1000), b = Int(Double(t1) * Double(Self.sampleRate) / 1000)
        let lo = max(0, a - base), hi = max(0, min(b - base, samples.count))
        return lo < hi ? samples[lo..<hi] : []
    }

    func read(_ t0: Int, _ t1: Int) -> [Float] { readPCM(t0, t1).map { Float($0) / 32767 } }

    /// Every step the audio heard so far allows, in order.
    public func readySteps() throws -> [Heard] {
        var out = [Heard]()
        while durationMs >= nextT {
            out.append(try hear(at: nextT))
            nextT += Self.hopMs
        }
        return out
    }

    /// One step: track the new audio, then notes and features over what has been heard.
    public func hear(at t: Int) throws -> Heard {
        var timing = [String: Int]()
        var clock = Date()
        func lap(_ name: String) {
            let now = Date()
            timing[name] = Int(1000 * now.timeIntervalSince(clock))
            clock = now
        }
        try track(to: t, lap: lap)
        let a = max(0, t - Self.poolMs)
        let span = read(a, t)
        var pulse: Pulse?? = nil
        var attacks: [Double]? = nil
        var notes = [String: [Note]]()
        for name in Self.trackers {
            let p = Self.params[name]!
            let tr = frames(name)
            let i = searchSorted(tr.times, Double(a)), j = searchSorted(tr.times, Double(t))
            guard j - i >= 4 else {
                notes[name] = []
                continue
            }
            var ns = Notes.fromTrack(times: ArraySlice(tr.times[i..<j].map { $0 - Double(a) }), f0: tr.f0[i..<j],
                                     voiced: tr.voiced[i..<j], params: p, offsetMs: a)
            if !ns.isEmpty {
                if p.splitRepeats {
                    if pulse == nil {
                        pulse = .some(PulseEstimate.estimate(span, sr: Self.sampleRate))
                        lap("notes_pulse")
                    }
                    if let pu = pulse!, pu.periodMs > 0 {
                        if attacks == nil {
                            attacks = Onsets.attackTimesMs(span, sr: Self.sampleRate).map { $0 + Double(a) }
                            lap("notes_attacks")
                        }
                        ns = Notes.splitFusedRepeats(ns, period: pu.periodMs, phase: pu.phaseMs + Double(a),
                                                     attacks: attacks!, minSlots: p.splitMinSlots,
                                                     tolerance: p.splitTolerance)
                    }
                }
                ns = Notes.dropOutOfKey(ns)
            }
            notes[name] = ns
            lap("notes_\(name)")
        }
        let feats = features(at: t)
        lap("features")
        return Heard(tMs: t, heardMs: durationMs, notes: notes, features: feats, timing: timing)
    }

    /// lab: Hearer._track. Tracks [trackedTo - 2 s, t) and keeps the frames from trackedTo.
    func track(to t: Int, lap: (String) -> Void) throws {
        let a = max(0, trackedTo - Self.trackContextMs)
        let pcm = readPCM(a, t)
        guard pcm.count >= Self.sampleRate / 2 else { return }
        let y = pcm.map { Float($0) / 32767 }
        // every tracker first, then the frames: a failure leaves the step to be taken again
        var all = [String: Track]()
        for name in Self.trackers {
            switch name {
            case "yin": all[name] = Yin.track(y, sr: Self.sampleRate)
            case "basic_pitch": all[name] = try BasicPitch.track(pcm, model: models.basicPitch)
            default: all[name] = try Pesto.track(y, model: models.pesto)
            }
            lap("track_\(name)")
        }
        for name in Self.trackers {
            let got = all[name]!
            var tr = tracks[name]!
            for k in 0..<got.count {
                let time = got.times[k] + Double(a)
                guard time >= Double(trackedTo) else { continue }
                tr.times.append(time)
                tr.f0.append(got.f0[k])
                tr.voiced.append(got.voiced[k])
            }
            tracks[name] = tr
        }
        trackedTo = t
    }

    /// A tracker's frames, the oldest dropped once there are two minutes of them.
    func frames(_ name: String) -> Track {
        var tr = tracks[name]!
        if let first = tr.times.first, first < Double(trackedTo - 2 * 60000) {
            let from = searchSorted(tr.times, Double(trackedTo - 60000))
            tr = Track(times: Array(tr.times[from...]), f0: Array(tr.f0[from...]), voiced: Array(tr.voiced[from...]))
            tracks[name] = tr
        }
        return tr
    }

    static let pulseMs = 12000, framesMs = 6000

    /// lab: tuneness.audio_features.
    func features(at t: Int) -> [String: Double?] {
        let p = PulseEstimate.estimate(read(max(0, t - Self.pulseMs), t), sr: Self.sampleRate)
        let y = read(max(0, t - Self.framesMs), t)
        var row: [String: Double?] = [
            "pulse_strength": p?.strength, "grouping_margin": p?.groupingMargin,
            "duple": p?.duple, "triple": p?.triple,
            "period_ms": p?.periodMs, "grouping": p.map { Double($0.grouping) },
            "log_rms": nil,
        ]
        if !y.isEmpty {
            var ms: Float = 0
            for v in y { ms += v * v }
            row["log_rms"] = Double(log10(sqrt(ms / Float(y.count)) + 1e-6))
        }
        for name in Self.trackers {
            let tr = frames(name)
            let i = searchSorted(tr.times, Double(t - Self.framesMs)), j = searchSorted(tr.times, Double(t))
            var midis = [Double]()
            var ok = 0
            if j > i {
                for k in i..<j {
                    let f = tr.f0[k]
                    if f.isFinite && f > 0 && tr.voiced[k] >= 0.2 {
                        ok += 1
                        midis.append(69 + 12 * log2(f / 440))
                    }
                }
            }
            row["\(name)_voiced"] = j > i ? Double(ok) / Double(j - i) : 0
            row["\(name)_pc_entropy"] = .some(nil)
            row["\(name)_steady"] = .some(nil)
            if ok > 10 {
                var hist = [Double](repeating: 0, count: 12)
                for m in midis { hist[pymod(Int(m.roundedEven), 12)] += 1 }
                var h = 0.0
                for c in hist where c > 0 {
                    let q = c / Double(ok)
                    h -= q * log(q)
                }
                row["\(name)_pc_entropy"] = h
                var steady = 0
                for k in 1..<midis.count where abs(midis[k] - midis[k - 1]) < 0.5 { steady += 1 }
                row["\(name)_steady"] = Double(steady) / Double(midis.count - 1)
            }
        }
        return row
    }
}
