// The meter's three states (NightRecorder.showing): no tune playing, figuring out the
// tune, sure of it; sure again without logging twice; and each drawn, for a look.

import CeolDesign
import CeolLogic
import CeolSession
import Foundation
import SwiftUI
import Testing
@testable import Ceol

extension OnePhoneTests {
@MainActor
struct MeterStatesTests {
    static func state(_ t: Int, p: Double, shown: Int? = 452, none: Double = 0.0) -> ListenState {
        var obj: [String: Any] = ["type": "state", "t_ms": t, "status": "listening", "none": none,
                                  "top": [["tune_id": 452, "name": "Fred Finn's", "type": "reel", "p": p, "outside": false],
                                          ["tune_id": 748, "name": "The Flax In Bloom", "type": "reel", "p": max(0, 1 - p - none),
                                           "outside": false]]]
        if let shown { obj["shown"] = shown }
        return try! JSONDecoder().decode(ListenState.self, from: try! JSONSerialization.data(withJSONObject: obj))
    }

    func recorder() -> NightRecorder {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("meter-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        UserDefaults.standard.set(true, forKey: "SelfConfirm")
        return NightRecorder(logging: (1, "A night"), recording: false, recordingID: "r", fileURL: dir.appendingPathComponent("a.caf"),
                             meterLogURL: dir.appendingPathComponent("m.jsonl"),
                             listenURL: URL(string: "ws://127.0.0.1:9/listen")!, token: nil, listenWhere: .server)
    }

    /// Just listening (spec 059): no night.
    func listener() -> NightRecorder {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("meter-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return NightRecorder(logging: nil, recording: false, recordingID: "r", fileURL: dir.appendingPathComponent("a.caf"),
                             meterLogURL: dir.appendingPathComponent("m.jsonl"),
                             listenURL: URL(string: "ws://127.0.0.1:9/listen")!, token: nil, listenWhere: .server)
    }

    /// With METER_DRAW_DIR set (xcodebuild: TEST_RUNNER_METER_DRAW_DIR), each state is
    /// drawn there as a PNG to look at.
    func draw(_ r: NightRecorder, _ name: String) {
        guard let dir = ProcessInfo.processInfo.environment["METER_DRAW_DIR"] else { return }
        let view = ListenMeterView(recorder: r).content.padding(16).frame(width: 393)
            .background(CeolTokens.bgColor).environment(\.colorScheme, .dark)
            .environment(AppModel(store: MemoryTokenStore("meter-draw")))
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        let png = renderer.uiImage?.pngData()
        #expect(png != nil, "drew nothing for \(name)")
        try? png?.write(to: URL(fileURLWithPath: dir).appendingPathComponent("meter-\(name).png"))
    }

    @Test func throughANight() {
        let r = recorder()
        #expect(r.showing == .waiting)
        r.received(Self.state(4000, p: 0.6))
        #expect(r.showing == .figuring)
        draw(r, "figuring")

        r.received(Self.state(8000, p: 0.999))
        #expect(r.showing == .sure(452))           // by itself, at 100%
        draw(r, "sure")

        r.received(Self.state(16000, p: 0.5))      // its belief has dropped
        #expect(r.showing == .figuring)
        r.received(Self.state(20000, p: 0.999))    // sure again of the same tune
        #expect(r.showing == .sure(452))

        r.received(Self.state(28000, p: 0.0, shown: nil, none: 0.83))
        #expect(r.showing == .noTune(0.83))
        draw(r, "noTune")
    }

    /// The switch is about logging: off, the meter still says it is sure at 100%.
    @Test func offTheSwitchSureAtOneHundredButNothingLogged() {
        let r = recorder()
        r.selfConfirms = false
        r.received(Self.state(4000, p: 0.999))
        #expect(r.showing == .sure(452))
        #expect(r.logged == nil)
        r.selfConfirms = true
    }

    /// Just listening (spec 059): sure at 100%, nothing to log to, the tune remembered.
    @Test func justListeningIsSureAndRemembers() {
        RecentTunes.clear()
        let r = listener()
        #expect(!r.isLogging)
        #expect(r.logsTo == nil)
        #expect(r.title == "Listening")
        r.received(Self.state(4000, p: 0.999))
        #expect(r.showing == .sure(452))
        #expect(r.logged == nil)
        #expect(RecentTunes.all.map(\.tuneID) == [452])
        // sure again of the same tune a moment later: one hearing
        r.received(Self.state(16000, p: 0.5))
        r.received(Self.state(20000, p: 0.999))
        #expect(RecentTunes.all.count == 1)
        RecentTunes.clear()
    }

    @Test func recentTunesFoldRepeatsAndKeepFifty() {
        let now = Date()
        let a = RecentTune(tuneID: 1, name: "A", type: "reel", heardAt: now)
        var list = RecentTunes.adding(a, to: [])
        list = RecentTunes.adding(RecentTune(tuneID: 1, name: "A", type: "reel", heardAt: now.addingTimeInterval(60)), to: list)
        #expect(list.count == 1)
        list = RecentTunes.adding(RecentTune(tuneID: 2, name: "B", type: nil, heardAt: now.addingTimeInterval(120)), to: list)
        #expect(list.map(\.tuneID) == [2, 1])
        list = RecentTunes.adding(RecentTune(tuneID: 1, name: "A", type: "reel", heardAt: now.addingTimeInterval(1000)), to: list)
        #expect(list.map(\.tuneID) == [1, 2, 1])
        for i in 0..<60 { list = RecentTunes.adding(RecentTune(tuneID: 100 + i, name: "T", type: nil, heardAt: now.addingTimeInterval(2000 + Double(i))), to: list) }
        #expect(list.count == RecentTunes.keep)
    }
}
}
