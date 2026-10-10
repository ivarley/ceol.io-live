// The meter's "this is it" by itself (NightRecorder.selfConfirmTune): only the tune
// shown, at what the meter shows as 100%, and never one said to be wrong tonight or
// logged from here in the last ten minutes.

import CeolLogic
import Foundation
import Testing
@testable import Ceol

struct SelfConfirmTests {
    func state(p: Double, shown: Int? = 452, none: Double = 0.0, changing: Bool = false) -> ListenState {
        var obj: [String: Any] = ["type": "state", "t_ms": 60000, "status": "listening", "none": none,
                                  "top": [["tune_id": 452, "name": "Fred Finn's", "p": p, "outside": false],
                                          ["tune_id": 748, "name": "The Flax In Bloom", "p": 1 - p, "outside": false]]]
        if let shown { obj["shown"] = shown }
        if changing { obj["changing"] = ["tune_id": 452, "name": "Fred Finn's", "since_ms": 56000] }
        let data = try! JSONSerialization.data(withJSONObject: obj)
        return try! JSONDecoder().decode(ListenState.self, from: data)
    }

    func pick(_ s: ListenState, confirmed: Int? = nil, wrong: Set<Int> = [], loggedAt: [Int: Date] = [:]) -> Int? {
        NightRecorder.selfConfirmTune(s, confirmed: confirmed, wrong: wrong, loggedAt: loggedAt, now: Date())
    }

    @Test func atOneHundredPercentTheShownTuneIsConfirmed() {
        #expect(pick(state(p: 0.9999)) == 452)
        #expect(pick(state(p: 0.995)) == 452)          // shown as 100%
        #expect(pick(state(p: 0.994)) == nil)          // shown as 99%
    }

    @Test func notWhenAnythingElseSaysWait() {
        #expect(pick(state(p: 1.0), confirmed: 452) == nil)            // already confirmed
        #expect(pick(state(p: 1.0, shown: nil)) == nil)                // nothing shown
        #expect(pick(state(p: 1.0, none: 0.6)) == nil)                 // not a tune
        #expect(pick(state(p: 1.0, changing: true)) == nil)            // may have changed
        #expect(pick(state(p: 1.0), wrong: [452]) == nil)              // said to be wrong tonight
        #expect(pick(state(p: 1.0), loggedAt: [452: Date().addingTimeInterval(-60)]) == nil)
        #expect(pick(state(p: 1.0), loggedAt: [452: Date().addingTimeInterval(-601)]) == 452)
    }
}
