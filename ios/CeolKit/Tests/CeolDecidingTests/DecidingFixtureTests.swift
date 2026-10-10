// The phone's deciding against the lab's, step by step, on stretches of real nights
// (Fixtures/*.json, written by `python -m lab decider fixtures`): the heard messages
// the lab's hearing made, the taps a person made between steps, and at each step what
// the lab's listener did with them: the shortlist, the tunes aligned and their scores,
// tune-ness, the decoder's belief and the state the service would send.
//
// The corpus file is not in the repo (16 MB, rebuilt with the corpus): CEOL_DECIDER_DATA
// names it, else LAB_DATA_DIR/index/decider-v1.bin, else this worktree's lab/data, else
// the copy the app ships (Sources/CeolDeciding/Data). The tests are skipped without it.

import Foundation
import Testing

@testable import CeolDeciding
import CeolHearing

let corpusURL: URL? = {
    let env = ProcessInfo.processInfo.environment
    var candidates = [String]()
    if let p = env["CEOL_DECIDER_DATA"] { candidates.append(p) }
    if let d = env["LAB_DATA_DIR"] { candidates.append("\(d)/index/decider-v1.bin") }
    let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../../../../lab/data")
    candidates.append(root.appendingPathComponent("index/decider-v1.bin").standardized.path)
    if let shipped = Corpus.shipped { candidates.append(shipped.path) }
    return candidates.first { FileManager.default.fileExists(atPath: $0) }.map(URL.init(fileURLWithPath:))
}()

let corpus: Corpus? = corpusURL.flatMap { try? Corpus(contentsOf: $0) }

struct DecideClip {
    let name: String
    let fx: [String: Any]
    var steps: [[String: Any]] { fx["steps"] as! [[String: Any]] }
    var taps: [[String: Any]] { fx["taps"] as! [[String: Any]] }

    static let names = ["r112-reel", "r137-talk", "r143-jig"]

    static func load(_ name: String) -> DecideClip {
        let dir = Bundle.module.url(forResource: "Fixtures", withExtension: nil)!
        let json = try! Data(contentsOf: dir.appendingPathComponent("\(name).json"))
        return DecideClip(name: name, fx: try! JSONSerialization.jsonObject(with: json) as! [String: Any])
    }

    func message(_ step: [String: Any]) -> String {
        String(decoding: try! JSONSerialization.data(withJSONObject: step["heard"]!), as: UTF8.self)
    }
}

func ints(_ x: Any?) -> [Int] { (x as? [NSNumber] ?? []).map(\.intValue) }

@Suite("The phone's deciding against the lab's", .serialized, .enabled(if: corpus != nil, "no decider-v1.bin"))
struct DecidingFixtureTests {
    @Test("Every step: the same shortlist, the same scores, the same state", arguments: DecideClip.names)
    func steps(_ name: String) throws {
        let clip = DecideClip.load(name)
        let decider = Decider(corpus: corpus!)
        var poolSame = 0, tunesSame = 0, shownSame = 0, worstScore = 0.0, worstLogodds = 0.0, worstP = 0.0
        for (i, step) in clip.steps.enumerated() {
            let got = try #require(decider.step(message: clip.message(step)))
            let last = try #require(decider.last)
            let lab = step["state"] as! [String: Any]

            if last.pool == ints(step["pool"]) { poolSame += 1 } else if poolSame == i {
                let want = ints(step["pool"])
                Issue.record("\(name) step \(i): pool differs first at \((0..<min(last.pool.count, want.count)).first { last.pool[$0] != want[$0] } ?? min(last.pool.count, want.count)) (\(last.pool.count) against \(want.count))")
            }
            if last.tunes == ints(step["tunes"]) { tunesSame += 1 }
            let want = (step["scores"] as! [String: NSNumber])
            #expect(Set(last.scores.keys.map(String.init)) == Set(want.keys), "\(name) step \(i): the tunes scored")
            for (k, v) in want {
                if let s = last.scores[Int(k)!] { worstScore = max(worstScore, abs(s - v.doubleValue)) }
            }
            worstLogodds = max(worstLogodds, abs(last.tuneLogodds - (step["tune_logodds"] as! NSNumber).doubleValue))
            #expect(last.nNotes == step["n_notes"] as! Int)

            let shown = got["shown"] as? Int, labShown = lab["shown"] as? Int
            if shown == labShown { shownSame += 1 } else {
                Issue.record("\(name) step \(i): shows \(String(describing: shown)), the lab \(String(describing: labShown))")
            }
            // the names worth showing (p >= 0.0001); below that their order is a tie's
            let mine = (got["top"] as! [[String: Any]]).filter { ($0["p"] as! Double) > 0 }
            let theirs = (lab["top"] as! [[String: Any]]).filter { ($0["p"] as! NSNumber).doubleValue > 0 }
            #expect(mine.map { $0["tune_id"] as! Int } == theirs.map { $0["tune_id"] as! Int }, "\(name) step \(i): top")
            for (a, b) in zip(mine, theirs) {
                worstP = max(worstP, abs((a["p"] as! Double) - (b["p"] as! NSNumber).doubleValue))
                #expect((a["outside"] as! Bool) == (b["outside"] as! Bool))
            }
            worstP = max(worstP, abs((got["none"] as! Double) - (lab["none"] as! NSNumber).doubleValue))
            #expect(abs((got["tuneness"] as! Double) - (lab["tuneness"] as! NSNumber).doubleValue) <= 0.001)
            #expect((got["history"] as! [[String: Any]]).map { $0["tune_id"] as! Int }
                    == (lab["history"] as! [[String: Any]]).map { ($0["tune_id"] as! NSNumber).intValue })
            #expect(got["wide"] as? Bool == lab["wide"] as? Bool)

            for tap in clip.taps where (tap["after"] as! Int) == i {
                if tap["action"] as! String == "this" { decider.tapThis(tap["tune_id"] as! Int) }
                else { decider.tapNone(shown: ints(tap["shown"])) }
            }
        }
        let n = clip.steps.count
        print("\(name): pool \(poolSame)/\(n), aligned \(tunesSame)/\(n), shown \(shownSame)/\(n); "
              + "worst score \(worstScore), tune-ness log-odds \(worstLogodds), belief \(worstP)")
        #expect(poolSame == n)
        #expect(tunesSame == n)
        #expect(worstScore <= 1e-9)
        #expect(worstLogodds <= 1e-9)
        #expect(worstP <= 1e-4 + 1e-12)
    }

    @Test("How fast, on this machine: loading, a session's repertoire, a step")
    func speed() throws {
        let t0 = Date()
        let c = try Corpus(contentsOf: corpusURL!)
        let load = Date().timeIntervalSince(t0)
        let t1 = Date()
        let decider = Decider(corpus: c)
        let rep = Date().timeIntervalSince(t1)
        var times = [Double]()
        for name in DecideClip.names {
            let clip = DecideClip.load(name)
            for step in clip.steps {
                let s = Date()
                decider.step(message: clip.message(step))
                times.append(1000 * Date().timeIntervalSince(s))
            }
        }
        times.sort()
        print(String(format: "corpus %.1f MB mapped in %.1f ms; repertoire %.1f ms; a step: median %.1f ms, "
                     + "90th %.1f, worst %.1f (%d steps)", Double(c.byteCount) / 1e6, 1000 * load, 1000 * rep,
                     times[times.count / 2], times[times.count * 9 / 10], times.last!, times.count))
    }
}

/// Heard and decided on the phone end to end: CeolHearing's clip of night 112 (the
/// hearing fixtures' r112-reel, the same 30 s the deciding fixture starts with) through
/// Swift's hearing, then Swift's deciding, against the lab's states.
@Suite("Heard and decided in Swift", .enabled(if: corpus != nil, "no decider-v1.bin"))
struct EndToEndTests {
    @Test("A clip of a reel: every state the lab's")
    func reel() throws {
        let dir = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .appendingPathComponent("../CeolHearingTests/Fixtures").standardized
        let data = try Data(contentsOf: dir.appendingPathComponent("r112-reel.pcm"))
        let pcm = data.withUnsafeBytes { Array($0.bindMemory(to: Int16.self)) }.map { Int16(littleEndian: $0) }
        let hearer = Hearer(models: try HearingModels(computeUnits: .cpuOnly))
        let decider = Decider(corpus: corpus!)
        let lab = DecideClip.load("r112-reel").steps
        var i = 0
        for start in stride(from: 0, to: pcm.count, by: 22050) {
            hearer.append(Array(pcm[start..<min(pcm.count, start + 22050)]))
            for heard in try hearer.readySteps() {
                let notes = heard.notes.mapValues { $0.map { HeardNote($0.t0, $0.t1, $0.midi) } }
                let got = decider.step(tMs: heard.tMs, notes: notes, features: heard.features, heardMs: heard.heardMs)
                let want = lab[i]["state"] as! [String: Any]
                #expect(got["shown"] as? Int == want["shown"] as? Int, "step \(i)")
                #expect(abs((got["none"] as! Double) - (want["none"] as! NSNumber).doubleValue) <= 1e-3, "step \(i)")
                print("  \(heard.tMs / 1000) s: \(corpus!.name(of: got["shown"] as? Int ?? -1) ?? "not a tune")")
                i += 1
            }
        }
        #expect(i == 7)
    }
}
