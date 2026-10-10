// A tune swiped from the night's log offers Undo, as a bulk delete does
// (NightModel.removeWithUndo); a row the server hasn't answered for yet goes without.

import CeolLogic
import CeolSession
import Foundation
import Testing
@testable import Ceol

@MainActor
struct SwipeUndoTests {
    func row(_ id: JSONValue, _ pos: String, _ name: String) -> JSONValue {
        ["session_instance_tune_id": id, "order_position": .string(pos), "record_type": "tune", "name": .string(name),
         "tune_id": .null, "deleted": false]
    }

    @Test func aSwipedTuneCanBeUndone() async throws {
        let instance = 987_654
        var temp = row("temp-x", "a3", "Fred Finn's")
        if case .object(var o) = temp { o["_temp"] = true; temp = .object(o) }
        let log = LiveLog(records: [row(1, "a1", "Drowsy Maggie"), row(2, "a2", "The Kesh"), temp], lastEventID: 5)
        NightStore.save(SavedNight(night: ["session_name": "A session"], log: log, savedAt: Date()), instance)
        defer { NightStore.clearAll() }

        let app = AppModel(server: URL(string: "http://127.0.0.1:9")!, store: MemoryTokenStore())
        app.simulatedOffline = true
        let night = app.openNight(instance)
        defer { app.closeNight(night) }
        for _ in 0..<50 where night.log == nil { try await Task.sleep(for: .milliseconds(100)) }
        let names = { night.log?.ordered.compactMap { $0["name"]?.stringValue } ?? [] }
        #expect(names() == ["Drowsy Maggie", "The Kesh", "Fred Finn's"])

        night.removeWithUndo(.server(2))
        #expect(names() == ["Drowsy Maggie", "Fred Finn's"])
        #expect(night.undoable?.count == 1)

        night.undoDelete()
        #expect(names() == ["Drowsy Maggie", "The Kesh", "Fred Finn's"])
        #expect(night.undoable == nil)

        // not yet answered: no id to restore by, so no Undo
        night.removeWithUndo(.temp("temp-x"))
        #expect(names() == ["Drowsy Maggie", "The Kesh"])
        #expect(night.undoable == nil)
    }
}
