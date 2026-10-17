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

    func pick(_ s: ListenState, confirmed: Int? = nil, wrong: Set<Int> = [], lastLogged: Int? = nil,
              loggedAt: [Int: Date] = [:]) -> Int? {
        NightRecorder.selfConfirmTune(s, confirmed: confirmed, wrong: wrong, lastLogged: lastLogged, loggedAt: loggedAt,
                                      now: Date())?.tune
    }

    @Test func theTuneLastLoggedIsSureAgainButNotLoggedTwice() {
        let again = NightRecorder.selfConfirmTune(state(p: 1.0), confirmed: nil, wrong: [], lastLogged: 452,
                                                  loggedAt: [452: Date()], now: Date())
        #expect(again?.tune == 452 && again?.log == false)
        let fresh = NightRecorder.selfConfirmTune(state(p: 1.0), confirmed: nil, wrong: [], lastLogged: 748,
                                                  loggedAt: [:], now: Date())
        #expect(fresh?.tune == 452 && fresh?.log == true)
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

// Two phones listening at one session: a tune the other phone has already logged as the
// latest set's last or second-to-last tune isn't logged again (NightRecorder.latestSetEndsWith).
struct AlreadyLoggedTests {
    func tune(_ id: Int?, _ pos: String) -> LogRecord {
        .object(["session_instance_tune_id": .string("r\(pos)"), "record_type": "tune", "order_position": .string(pos),
                 "tune_id": id.map { JSONValue($0) } ?? .null, "deleted": false])
    }

    func brk(_ pos: String) -> LogRecord {
        .object(["session_instance_tune_id": .string("b\(pos)"), "record_type": "break", "order_position": .string(pos),
                 "deleted": false])
    }

    @Test func theLastOrSecondToLastTuneOfTheOpenSet() {
        let log = [tune(100, "a0"), tune(452, "a1"), tune(748, "a2")]
        #expect(NightRecorder.latestSetEndsWith(748, log))
        #expect(NightRecorder.latestSetEndsWith(452, log))
        #expect(!NightRecorder.latestSetEndsWith(100, log))   // third from the end: played again
        #expect(!NightRecorder.latestSetEndsWith(999, log))
    }

    @Test func aSetJustEndedIsStillTheLatest() {
        let log = [tune(452, "a0"), tune(748, "a1"), brk("a2")]
        #expect(NightRecorder.latestSetEndsWith(748, log))
        #expect(NightRecorder.latestSetEndsWith(452, log))
    }

    @Test func onlyTheLatestSet() {
        let log = [tune(452, "a0"), brk("a1"), tune(748, "a2")]
        #expect(!NightRecorder.latestSetEndsWith(452, log))
        #expect(NightRecorder.latestSetEndsWith(748, log))
        #expect(!NightRecorder.latestSetEndsWith(452, []))
    }

    @Test func aRowStillOnItsWayHasNoTuneYet() {
        let log = [tune(452, "a0"), tune(nil, "a1"), tune(nil, "a2")]
        #expect(!NightRecorder.latestSetEndsWith(452, log))
    }
}
