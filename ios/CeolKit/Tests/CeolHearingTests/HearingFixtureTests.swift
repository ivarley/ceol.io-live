// The phone's hearing against the lab's, stage by stage, on clips of real nights
// (Fixtures/*.json and *.pcm, written by `python -m lab hearing-fixtures`). Each stage
// is given the lab's own input, so a difference shows where it starts.

import CoreML
import Foundation
import Testing

@testable import CeolHearing

struct Clip {
    let name: String
    let pcm: [Int16]
    let fx: [String: Any]

    var steps: [[String: Any]] { fx["steps"] as! [[String: Any]] }

    static let names = ["r112-reel", "r143-jig", "r137-talk"]

    static func load(_ name: String) -> Clip {
        let dir = Bundle.module.url(forResource: "Fixtures", withExtension: nil)!
        let data = try! Data(contentsOf: dir.appendingPathComponent("\(name).pcm"))
        let pcm = data.withUnsafeBytes { Array($0.bindMemory(to: Int16.self)) }.map { Int16(littleEndian: $0) }
        let json = try! Data(contentsOf: dir.appendingPathComponent("\(name).json"))
        return Clip(name: name, pcm: pcm, fx: try! JSONSerialization.jsonObject(with: json) as! [String: Any])
    }

    func pcm(_ t0: Int, _ t1: Int) -> ArraySlice<Int16> {
        let a = Int(Double(t0) * 22.05), b = min(pcm.count, Int(Double(t1) * 22.05))
        return pcm[a..<b]
    }

    func audio(_ t0: Int, _ t1: Int) -> [Float] { pcm(t0, t1).map { Float($0) / 32767 } }
}

func doubles(_ x: Any?) -> [Double] { (x as? [Any] ?? []).map { ($0 as? NSNumber)?.doubleValue ?? .nan } }

func notes(_ x: Any?) -> [Note] {
    (x as? [[Int]] ?? []).map { Note($0[0], $0[1], $0[2]) }
}

/// How many of two note lists' notes are the same note at the same time.
func agreement(_ a: [Note], _ b: [Note]) -> (same: Int, of: Int) {
    let sb = Set(b)
    return (a.filter { sb.contains($0) }.count, max(a.count, b.count))
}

/// The share of frames whose pitch is within `tol` semitones (both unpitched counts too).
func pitchAgreement(_ a: [Double], _ b: [Double], tol: Double = 0.05) -> Double {
    let n = min(a.count, b.count)
    guard n > 0 else { return 1 }
    var ok = 0
    for i in 0..<n {
        let x = a[i], y = b[i]
        if !x.isFinite && !y.isFinite { ok += 1 } else if x.isFinite && y.isFinite && x > 0 && y > 0,
            abs(hzToMidi(x) - hzToMidi(y)) <= tol { ok += 1 }
    }
    return Double(ok) / Double(n)
}

// CEOL_HEARING_UNITS=ane: as the phone runs them (CPU and Neural Engine, no GPU, which
// iOS refuses an app in the background); all: anything the Mac has
let models: HearingModels = try! HearingModels(computeUnits: [
    "ane": .cpuAndNeuralEngine, "all": .all,
][ProcessInfo.processInfo.environment["CEOL_HEARING_UNITS"] ?? ""] ?? .cpuOnly)

@Suite("The phone's hearing against the lab's", .serialized)
struct HearingFixtureTests {
    @Test("yin: the same pitch in nearly every frame, the same voicing", arguments: Clip.names)
    func yin(_ name: String) {
        let clip = Clip.load(name)
        var worst = 1.0, voicedDiff = 0.0
        for step in clip.steps {
            let from = step["track_from_ms"] as! Int, t = step["t_ms"] as! Int
            let lab = (step["track"] as! [String: Any])["yin"] as! [String: Any]
            let got = Yin.track(clip.audio(from, t), sr: 22050)
            #expect(got.count == doubles(lab["f0_hz"]).count)
            worst = min(worst, pitchAgreement(got.f0, doubles(lab["f0_hz"])))
            for (a, b) in zip(got.voiced, doubles(lab["voiced"])) { voicedDiff = max(voicedDiff, abs(a - b)) }
        }
        print("yin \(name): worst step \(worst) of frames within 0.05 semitones; voicing within \(voicedDiff)")
        #expect(worst >= 0.995)
        #expect(voicedDiff < 1e-3)
    }

    @Test("PESTO: the same pitch and confidence", arguments: Clip.names)
    func pesto(_ name: String) throws {
        let clip = Clip.load(name)
        var worst = 1.0, confDiff = 0.0
        for step in clip.steps {
            let from = step["track_from_ms"] as! Int, t = step["t_ms"] as! Int
            let lab = (step["track"] as! [String: Any])["pesto"] as! [String: Any]
            let got = try Pesto.track(clip.audio(from, t), model: models.pesto)
            #expect(got.count == doubles(lab["f0_hz"]).count)
            worst = min(worst, pitchAgreement(got.f0, doubles(lab["f0_hz"]), tol: 0.01))
            for (a, b) in zip(got.voiced, doubles(lab["voiced"])) { confDiff = max(confDiff, abs(a - b)) }
        }
        print("pesto \(name): worst step \(worst) of frames within 0.01 semitones; confidence within \(confDiff)")
        #expect(worst >= 0.999)
        #expect(confDiff < 1e-3)
    }

    @Test("Basic Pitch: the same note events and melody", arguments: Clip.names)
    func basicPitch(_ name: String) throws {
        let clip = Clip.load(name)
        var same = 0, of = 0, melody = 1.0
        for step in clip.steps {
            let from = step["track_from_ms"] as! Int, t = step["t_ms"] as! Int
            let lab = (step["track"] as! [String: Any])["basic_pitch"] as! [String: Any]
            let got = try BasicPitch.track(clip.pcm(from, t), model: models.basicPitch)
            let y = BasicPitch.asWavRoundTrip(clip.pcm(from, t))
            let (note, onset) = try BasicPitch.infer(y, model: models.basicPitch)
            let events = BasicPitch.notes(frames: note, onsets: onset)
            let labEvents = (lab["events"] as! [[Any]]).map {
                ($0[0] as! NSNumber).doubleValue.description + "/" + ($0[2] as! NSNumber).intValue.description
            }
            let mine = events.map { (($0.start * 1e6).rounded() / 1e6).description + "/" + $0.midi.description }
            same += Set(mine).intersection(labEvents).count
            of += max(mine.count, labEvents.count)
            melody = min(melody, pitchAgreement(got.f0, doubles(lab["f0_hz"]), tol: 0.01))
        }
        print("basic_pitch \(name): events \(same)/\(of) the same; melody worst step \(melody)")
        #expect(Double(same) / Double(max(of, 1)) >= 0.98)
        #expect(melody >= 0.98)
    }

    @Test("The beat, the onsets and the attacks over each 24 s span", arguments: Clip.names)
    func pulse(_ name: String) {
        let clip = Clip.load(name)
        var envDiff: Float = 0, attacksSame = 0, attacksOf = 0, periodDiff = 0.0, phaseDiff = 0.0
        var groupingSame = 0, steps = 0
        for step in clip.steps {
            let from = step["span_from_ms"] as! Int, t = step["t_ms"] as! Int
            let y = clip.audio(from, t)
            let env = Onsets.envelope(y, sr: 22050)
            let labEnv = doubles(step["onset_envelope"])
            #expect(env.count == labEnv.count)
            for (a, b) in zip(env, labEnv) { envDiff = max(envDiff, abs(a - Float(b))) }
            let att = Onsets.attackTimesMs(y, sr: 22050).map { Int($0.rounded()) }
            let labAtt = doubles(step["attacks_ms"]).map { Int($0.rounded()) }
            attacksSame += Set(att).intersection(labAtt).count
            attacksOf += max(att.count, labAtt.count)
            let p = PulseEstimate.estimate(y, sr: 22050)
            if let lab = step["pulse"] as? [String: Any], let p {
                steps += 1
                periodDiff = max(periodDiff, abs(p.periodMs - (lab["period_ms"] as! NSNumber).doubleValue))
                phaseDiff = max(phaseDiff, abs(p.phaseMs - (lab["phase_ms"] as! NSNumber).doubleValue))
                if p.grouping == lab["grouping"] as! Int { groupingSame += 1 }
            } else {
                #expect(p == nil && step["pulse"] is NSNull)
            }
        }
        print("pulse \(name): envelope within \(envDiff); attacks \(attacksSame)/\(attacksOf); period within "
              + "\(periodDiff) ms, phase within \(phaseDiff) ms; grouping \(groupingSame)/\(steps)")
        #expect(envDiff < 1e-3)
        #expect(Double(attacksSame) / Double(max(attacksOf, 1)) >= 0.98)
        #expect(periodDiff < 0.5 && phaseDiff < 2.5 && groupingSame == steps)
    }

    @Test("Notes from the lab's frames: the same notes, on the grid and in key", arguments: Clip.names)
    func notesFromFrames(_ name: String) {
        let clip = Clip.load(name)
        var tracks = [String: Track]()
        var trackedTo = 0
        for step in clip.steps {
            let from = step["track_from_ms"] as! Int, t = step["t_ms"] as! Int
            for (tracker, v) in step["track"] as! [String: Any] {
                let lab = v as! [String: Any]
                var tr = tracks[tracker] ?? Track()
                // the fixture's times are rounded to 0.01 ms; the trackers' own are exact
                let rounded = doubles(lab["times_ms"]), f0 = doubles(lab["f0_hz"]), voiced = doubles(lab["voiced"])
                let step = tracker == "yin" ? 256 * 1000 / 22050.0 : 10.0
                let times = (0..<rounded.count).map { Double($0) * step }
                #expect(zip(times, rounded).allSatisfy { abs($0 - $1) < 0.006 })
                for k in 0..<times.count where times[k] + Double(from) >= Double(trackedTo) {
                    tr.times.append(times[k] + Double(from))
                    tr.f0.append(f0[k])
                    tr.voiced.append(voiced[k])
                }
                tracks[tracker] = tr
            }
            trackedTo = t
            let a = step["span_from_ms"] as! Int
            let pulse = step["pulse"] as? [String: Any]
            let attacks = doubles(step["attacks_ms"]).map { $0 + Double(a) }
            for (tracker, v) in step["notes"] as! [String: Any] {
                let lab = v as! [String: Any]
                let p = Hearer.params[tracker]!
                let tr = tracks[tracker]!
                let i = searchSorted(tr.times, Double(a)), j = searchSorted(tr.times, Double(t))
                let raw = j - i >= 4 ? Notes.fromTrack(times: ArraySlice(tr.times[i..<j].map { $0 - Double(a) }),
                                                       f0: tr.f0[i..<j], voiced: tr.voiced[i..<j], params: p, offsetMs: a) : []
                let labRaw = notes(lab["raw"])
                if raw != labRaw {
                    let k = (0..<min(raw.count, labRaw.count)).first { raw[$0] != labRaw[$0] } ?? min(raw.count, labRaw.count)
                    let msg = "\(name) \(tracker) at \(t): raw notes \(raw.count) against \(labRaw.count), first different "
                        + "at \(k): \(Array(raw.dropFirst(k).prefix(2))) against \(Array(labRaw.dropFirst(k).prefix(2)))"
                    Issue.record(Comment(rawValue: msg))
                }
                var gridded = raw
                if p.splitRepeats, !raw.isEmpty, let pulse {
                    gridded = Notes.splitFusedRepeats(raw, period: (pulse["period_ms"] as! NSNumber).doubleValue,
                                                      phase: (pulse["phase_ms"] as! NSNumber).doubleValue + Double(a),
                                                      attacks: attacks, minSlots: p.splitMinSlots, tolerance: p.splitTolerance)
                }
                let labGridded = notes(lab["gridded"])
                let g = agreement(gridded, labGridded)
                // the fixture's period and phase are rounded to a microsecond
                #expect(g.same >= g.of - 1, "\(name) \(tracker) at \(t): gridded \(g)")
                #expect(Notes.dropOutOfKey(labGridded) == notes(lab["final"]), "\(name) \(tracker) at \(t): key")
            }
        }
    }

    @Test("End to end: what the phone hears is what the lab hears", arguments: Clip.names)
    func endToEnd(_ name: String) throws {
        let clip = Clip.load(name)
        let hearer = Hearer(models: models)
        var heard = [Heard]()
        for i in stride(from: 0, to: clip.pcm.count, by: 22050) {
            hearer.append(Array(clip.pcm[i..<min(i + 22050, clip.pcm.count)]))
            heard.append(contentsOf: try hearer.readySteps())
        }
        #expect(heard.count == clip.steps.count)
        var same = [String: Int](), of = [String: Int](), featDiff = [String: Double]()
        for (h, step) in zip(heard, clip.steps) {
            let lab = step["heard"] as! [String: Any]
            #expect(h.tMs == lab["t_ms"] as! Int)
            for tracker in Hearer.trackers {
                let g = agreement(h.notes[tracker]!, notes((lab["notes"] as! [String: Any])[tracker]))
                same[tracker, default: 0] += g.same
                of[tracker, default: 0] += g.of
            }
            for (k, v) in lab["features"] as! [String: Any] {
                let mine = h.features[k] ?? nil
                if let n = v as? NSNumber, let mine {
                    featDiff[k] = max(featDiff[k] ?? 0, abs(mine - n.doubleValue))
                } else {
                    #expect((v is NSNull) == (mine == nil), "\(name) at \(h.tMs): \(k) \(v) against \(String(describing: mine))")
                }
            }
        }
        var parts = [String: [Int]]()
        for h in heard.dropFirst(2) { for (k, v) in h.timing { parts[k, default: []].append(v) } }
        print("time a step \(name) (ms, median): " + parts.sorted { $0.key < $1.key }
              .map { "\($0.key) \($0.value.sorted()[$0.value.count / 2])" }.joined(separator: ", "))
        let summary = Hearer.trackers.map { "\($0) \(same[$0]!)/\(of[$0]!)" }.joined(separator: ", ")
        print("end to end \(name): notes the same: \(summary); features, largest difference: "
              + featDiff.sorted { $0.key < $1.key }.map { "\($0.key) \(String(format: "%.2g", $0.value))" }.joined(separator: ", "))
        for tracker in Hearer.trackers {
            #expect(Double(same[tracker]!) / Double(max(of[tracker]!, 1)) >= 0.97, "\(tracker)")
        }
    }
}

/// Against a running listening service (CEOL_LISTEN_URL=ws://localhost:8440/listen): the
/// phone's "heard" messages are taken, and come back as states naming the tune.
@Suite("Heard mode against the listening service")
struct HeardServiceTests {
    @Test("A clip heard here is decided there", .enabled(if: ProcessInfo.processInfo.environment["CEOL_LISTEN_URL"] != nil))
    func againstService() async throws {
        let clip = Clip.load("r112-reel")
        let hearer = Hearer(models: models)
        hearer.append(clip.pcm)
        let heard = try hearer.readySteps()
        let url = URL(string: ProcessInfo.processInfo.environment["CEOL_LISTEN_URL"]!)!
        let ws = URLSession.shared.webSocketTask(with: url)
        ws.resume()
        let sid = UUID().uuidString
        try await ws.send(.string(#"{"type":"start","stream_id":"\#(sid)","mode":"heard"}"#))
        guard case .string(let ready) = try await ws.receive() else { Issue.record("no ready"); return }
        #expect(ready.contains(#""mode": "heard""#) || ready.contains(#""mode":"heard""#))
        var states = [[String: Any]]()
        for h in heard {
            try await ws.send(.string(h.message()))
            while true {
                guard case .string(let text) = try await ws.receive() else { continue }
                let m = try JSONSerialization.jsonObject(with: Data(text.utf8)) as! [String: Any]
                if m["type"] as? String == "state" { states.append(m) }
                if m["type"] as? String == "ack" { break }
            }
        }
        ws.cancel(with: .normalClosure, reason: nil)
        #expect(states.count == heard.count)
        let last = states.last!
        let top = (last["top"] as! [[String: Any]]).first
        print("service on the phone's notes: \(states.count) states, last shows \(top?["name"] ?? "-") "
              + "\(top?["p"] ?? 0), status \(last["status"] ?? "")")
        #expect((last["status"] as? String) == "listening")
    }
}
