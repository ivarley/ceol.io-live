// A debug build's demo of the meter (-CeolMeterDemo YES): the listener's states played
// on a timer through the real meter, with no microphone and no service, to look at its
// states and animations (spec 053). Not in release builds.

#if DEBUG
import CeolLogic
import Foundation
import SwiftUI

struct MeterDemoView: View {
    @State private var recorder: NightRecorder = {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("meter-demo")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return NightRecorder(instanceID: 0, title: "B.D. Riley's · demo", recordingID: "demo",
                             fileURL: dir.appendingPathComponent("demo.caf"),
                             meterLogURL: dir.appendingPathComponent("demo.jsonl"),
                             listenURL: URL(string: "ws://127.0.0.1:9/listen")!, token: nil, listenWhere: .phone)
    }()

    /// (seconds, belief in the first tune, the second's, "not a tune")
    static let script: [(Double, Double, Double, Double)] = [
        (1, 0.30, 0.25, 0.10), (3, 0.55, 0.30, 0.05), (5, 0.80, 0.15, 0.02), (7, 0.93, 0.05, 0.01),
        (9, 0.999, 0.001, 0.0), (15, 0.40, 0.10, 0.50), (16, 0.05, 0.02, 0.86), (19, 0.02, 0.01, 0.93),
        (22, 0.02, 0.01, 0.95), (25, 0.02, 0.01, 0.96),
    ]

    var body: some View {
        ListenMeterView(recorder: recorder, onStop: {})
            .task {
                UserDefaults.standard.set(true, forKey: "SelfConfirm")
                let start = Date()
                for (i, step) in Self.script.enumerated() {
                    // starting up for the first few seconds, as a real start is
                    let wait = 3 + step.0 - Date().timeIntervalSince(start)
                    if wait > 0 { try? await Task.sleep(for: .seconds(wait)) }
                    recorder.received(Self.state(t: 4000 * (i + 1), step.1, step.2, step.3))
                }
            }
    }

    static func state(t: Int, _ a: Double, _ b: Double, _ none: Double) -> ListenState {
        var obj: [String: Any] = [
            "type": "state", "t_ms": t, "status": "listening", "none": none, "tuneness": 1 - none,
            "top": [["tune_id": 452, "name": "Fred Finn's", "type": "reel", "p": a, "outside": false],
                    ["tune_id": 748, "name": "The Flax In Bloom", "type": "reel", "p": b, "outside": false]],
        ]
        if none <= 0.5 { obj["shown"] = 452 }
        return try! JSONDecoder().decode(ListenState.self, from: JSONSerialization.data(withJSONObject: obj))
    }
}
#endif
