// The live log's reducer and the event-stream parser.

import Foundation
import Testing

@testable import CeolLogic

private func rec(_ id: Int, _ pos: String, name: String? = nil, type: String = "tune") -> JSONValue {
    ["session_instance_tune_id": JSONValue(id), "order_position": .string(pos), "record_type": .string(type),
     "name": name.map(JSONValue.string) ?? .null, "deleted": false]
}

@Suite("LiveLog")
struct LiveLogTests {
    @Test("ops change the records, in the web's Map order; replays are skipped")
    func applies() {
        var log = LiveLog(records: [rec(1, "a1", name: "Cooley's"), rec(2, "a2", name: "Kesh")], lastEventID: 10)
        do { let changed = log.apply(["op_type": "add_tune", "event_id": 11, "record": rec(3, "a3", name: "Morrison's")]); #expect(changed) }
        #expect(log.ordered.map { $0["name"]?.stringValue } == ["Cooley's", "Kesh", "Morrison's"])
        // A replay of an applied event is skipped.
        do { let changed = log.apply(["op_type": "add_tune", "event_id": 11, "record": rec(3, "a3", name: "Changed")]); #expect(!changed) }
        // A rename keeps its place; a removal drops it.
        do { let changed = log.apply(["op_type": "change_tune", "event_id": 12, "record": rec(1, "a1", name: "Cooley's Reel")]); #expect(changed) }
        #expect(log.records.first?["name"]?.stringValue == "Cooley's Reel")
        var deleted = rec(2, "a2")
        if case .object(var o) = deleted { o["deleted"] = true; deleted = .object(o) }
        do { let changed = log.apply(["op_type": "remove_tune", "event_id": 13, "record": deleted]); #expect(changed) }
        #expect(log.records.count == 2)
        #expect(log.highWater == 13)
        // Night fields.
        do { let changed = log.apply(["op_type": "mark_complete", "event_id": 14]); #expect(changed) }
        #expect(log.meta["log_complete"] == true)
        // An op with nothing for records or fields changes nothing, but moves the cursor.
        do { let changed = log.apply(["op_type": "attendance_add", "event_id": 15]); #expect(!changed) }
        #expect(log.highWater == 15)
    }
}

@Suite("SSEParser")
struct SSEParserTests {
    @Test("events, ids, comments, multi-line data, and chunks that split lines")
    func parses() {
        var p = SSEParser()
        let text = ": connected\n\nid: 7\nevent: op\ndata: {\"a\":1}\n\nevent: presence\ndata: one\ndata: two\n\nevent: ping\ndata: {}\r\n\r\nid: 9\n\n"
        let bytes = Array(text.utf8)
        var events: [SSEEvent] = []
        // In awkward chunks, including one that splits a \r\n.
        for chunk in stride(from: 0, to: bytes.count, by: 5).map({ bytes[$0..<min($0 + 5, bytes.count)] }) {
            events += p.feed(chunk)
        }
        #expect(events == [
            SSEEvent(type: "op", data: "{\"a\":1}", lastEventID: "7"),
            SSEEvent(type: "presence", data: "one\ntwo", lastEventID: "7"),
            SSEEvent(type: "ping", data: "{}", lastEventID: "7"),
        ])
        // An id with no data dispatches nothing but moves the cursor.
        #expect(p.lastEventID == "9")
    }

    @Test("a bare CR ends a line; an unnamed event is a message")
    func carriageReturns() {
        var p = SSEParser()
        #expect(p.feed(Array("data: x\r\r".utf8)) == [SSEEvent(type: "message", data: "x", lastEventID: nil)])
    }
}

@Suite("LiveLog editing")
struct LiveEditingTests {
    func names(_ log: LiveLog) -> [String] {
        log.ordered.map { $0["record_type"] == "break" ? "|" : ($0["name"]?.stringValue ?? "?") }
    }

    @Test("a tune logged at the end shows at once, and the answer settles it without moving the cursor")
    func addAndSettle() {
        var log = LiveLog(records: [rec(1, "a1", name: "Cooley's")], lastEventID: 10)
        let (ops, cursor) = log.addTune(["name": "Kesh"], at: .end, opID: "op1")
        #expect(cursor == .end)
        #expect(names(log) == ["Cooley's", "Kesh"])
        #expect(ops.count == 1)
        #expect(ops[0].body["op_type"] == "add_tune")
        #expect(ops[0].body["after_record_id"] == .null)
        #expect(log.ordered.last?["_temp"] == true)
        let err = log.settle(opID: "op1", answer: ["success": true, "op_type": "add_tune", "event_id": 12, "record": rec(5, "a2", name: "The Kesh")])
        #expect(err == nil)
        #expect(names(log) == ["Cooley's", "The Kesh"])
        #expect(log.pending.isEmpty)
        #expect(log.tempToReal["temp-op1"] == JSONValue(5))
        #expect(log.resolve(.temp("temp-op1")) == .server(5))
        // The answer doesn't move the high-water mark; event 11 (someone else's) still applies.
        #expect(log.highWater == 10)
        let changed = log.apply(["op_type": "add_tune", "event_id": 11, "record": rec(4, "a3", name: "Morrison's")])
        #expect(changed)
        // Our own echo arriving later changes nothing more.
        log.apply(["op_type": "add_tune", "event_id": 12, "op_id": "op1", "record": rec(5, "a2", name: "The Kesh")])
        #expect(names(log) == ["Cooley's", "The Kesh", "Morrison's"])
    }

    @Test("the echo on the stream can settle an op before its answer")
    func echoFirst() {
        var log = LiveLog(records: [rec(1, "a1", name: "Cooley's")], lastEventID: 10)
        _ = log.addTune(["name": "Kesh"], at: .end, opID: "op1")
        log.apply(["op_type": "add_tune", "event_id": 11, "op_id": "op1", "record": rec(5, "a2", name: "Kesh")])
        #expect(log.pending.isEmpty)
        #expect(names(log) == ["Cooley's", "Kesh"])
        #expect(log.records.count == 2)
        log.settle(opID: "op1", answer: ["success": true, "record": rec(5, "a2", name: "Kesh")])
        #expect(log.records.count == 2)
    }

    @Test("a refusal rolls the change back and says why")
    func rejected() {
        var log = LiveLog(records: [rec(1, "a1", name: "Cooley's"), rec(2, "a2", name: "Kesh")])
        let op = log.remove(.server(2), opID: "r1")
        #expect(op?.body["record_id"] == JSONValue(2))
        #expect(names(log) == ["Cooley's"])
        let err = log.settle(opID: "r1", answer: ["success": false, "rejected": true, "reason": "forbidden", "message": "Not yours."])
        #expect(err == "Not yours.")
        #expect(names(log) == ["Cooley's", "Kesh"])
        // A failed send rolls back the same way.
        _ = log.addTune(["name": "Morrison's"], at: .end, opID: "a1")
        log.rollback("a1")
        #expect(names(log) == ["Cooley's", "Kesh"])
    }

    @Test("mid-log adds follow the cursor; later ops send the real id once it's known")
    func cursorAndAnchors() {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a3", name: "C")])
        let first = log.addTune(["name": "B1"], at: .after(.server(1)), opID: "o1")
        #expect(first.ops[0].body["after_record_id"] == JSONValue(1))
        #expect(first.cursor == .after(.temp("temp-o1")))
        let second = log.addTune(["name": "B2"], at: first.cursor, opID: "o2")
        #expect(names(log) == ["A", "B1", "B2", "C"])
        #expect(second.ops[0].body["after_record_id"] == "temp-o1")
        log.settle(opID: "o1", answer: ["success": true, "record": rec(7, "a2", name: "B1")])
        #expect(log.sendableBody("o2")?["after_record_id"] == JSONValue(7))
        // Before a tune: the before anchor.
        let before = log.addTune(["name": "Z"], at: .before(.server(1)), opID: "o3")
        #expect(before.ops[0].body["before_record_id"] == JSONValue(1))
        #expect(names(log).first == "Z")
    }

    @Test("End set, Split and Join")
    func sets() {
        var empty = LiveLog(records: [])
        let none = empty.endSet()
        #expect(none == nil)
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B")])
        let end = log.endSet(opID: "e1")
        #expect(end?.body["after_record_id"] == .null)
        #expect(names(log) == ["A", "B", "|"])
        let split = log.split(after: .server(1), opID: "s1")
        #expect(split.body["after_record_id"] == JSONValue(1))
        #expect(names(log) == ["A", "|", "B", "|"])
        log.settle(opID: "s1", answer: ["success": true, "record": rec(9, "a1V", type: "break")])
        let join = log.join(breakID: .server(9), opID: "j1")
        #expect(join?.body["action"] == "remove")
        #expect(join?.body["record_id"] == JSONValue(9))
        #expect(names(log) == ["A", "B", "|"])
    }

    @Test("a new set between sets is a tune and then a break, both before the next set")
    func newSet() {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", type: "break"), rec(3, "a3", name: "C")])
        let r = log.addTune(["name": "B"], at: .newSet(.server(3)), opID: "n1")
        #expect(r.ops.count == 2)
        #expect(r.ops[0].body["before_record_id"] == JSONValue(3))
        #expect(r.ops[1].body["op_type"] == "set_break")
        #expect(r.ops[1].body["before_record_id"] == JSONValue(3))
        #expect(names(log) == ["A", "|", "B", "|", "C"])
    }

    @Test("confirming raises the confidence; a fresh bootstrap keeps changes in flight")
    func confirmAndRebase() {
        var r1 = rec(1, "a1", name: "A")
        if case .object(var o) = r1 { o["confidence"] = 40; r1 = .object(o) }
        var log = LiveLog(records: [r1, rec(2, "a2", name: "B")])
        let op = log.confirm(.server(1), opID: "c1")
        #expect(op?.body["confidence"] == 100)
        #expect(log.records.first?["confidence"] == 100)
        _ = log.remove(.server(2), opID: "r1")
        _ = log.addTune(["name": "C"], at: .end, opID: "a1")
        let fresh = LiveLog(records: [r1, rec(2, "a2", name: "B")], lastEventID: 20)
        let rebased = log.rebased(onto: fresh)
        #expect(names(rebased) == ["A", "C"])
        #expect(rebased.records.first?["confidence"] == 100)
        #expect(rebased.pending.count == 3)
        #expect(rebased.highWater == 20)
    }

    @Test("a move shows at once, keeps the block's order, and settles to the server's places")
    func move() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B"), rec(3, "a3", name: "C"), rec(4, "a4", name: "D")])
        let block = try #require(Selection.dragBlock(log.ordered, selected: [.server(3), .server(4)], grabbed: .server(3)))
        let target = Selection.DropTarget(key: "after:1", afterID: .server(1), beforeID: nil, newSet: false)
        let op = log.move(block, to: target, opID: "m1")
        #expect(op.body["op_type"] == "move_tunes")
        #expect(op.body["record_ids"] == [3, 4])
        #expect(op.body["after_record_id"] == 1)
        #expect(names(log) == ["A", "C", "D", "B"])
        // Refused: back where they were.
        log.settle(opID: "m1", answer: ["success": false, "rejected": true, "reason": "stale"])
        #expect(names(log) == ["A", "B", "C", "D"])
    }

    @Test("a move into a new set shows its breaks, and they go when it settles")
    func moveNewSet() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B"), rec(3, "a3", name: "C")])
        let block = try #require(Selection.dragBlock(log.ordered, selected: [], grabbed: .server(3)))
        let target = Selection.DropTarget(key: "top-new", afterID: nil, beforeID: .server(1), newSet: true)
        _ = log.move(block, to: target, opID: "m2")
        #expect(names(log) == ["C", "|", "A", "B"])
        log.settle(opID: "m2", answer: ["success": true, "op_type": "move_tunes",
                                         "records": [rec(3, "a0", name: "C"), rec(9, "a0V", type: "break")], "removed_break_ids": []])
        #expect(names(log) == ["C", "|", "A", "B"])
        #expect(log.records.count == 4)
    }

    @Test("a bulk remove comes back with Undo, and a refused Undo takes them away again")
    func bulkRemoveAndUndo() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B"), rec(3, "a3", name: "C")])
        let removed = log.removeMany([.server(1), .server(3)], opID: "r1")
        let (op, rows) = try #require(removed)
        #expect(op.body["record_ids"] == [1, 3])
        #expect(names(log) == ["B"])
        log.settle(opID: "r1", answer: ["success": true, "op_type": "remove_tunes", "records": []])
        let restored = log.restore(rows, opID: "u1")
        let undo = try #require(restored)
        #expect(undo.body["op_type"] == "restore_tunes")
        #expect(names(log) == ["A", "B", "C"])
        log.rollback("u1")
        #expect(names(log) == ["B"])
    }

    @Test("a set's starter goes on every tune in it, in one op")
    func starter() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B"), rec(3, "a3", type: "break"), rec(4, "a4", name: "C")])
        let set = LogState.segmentByBreaks(log.ordered)[0].tunes
        let started = log.setStarter(of: set, personID: 7, name: "Sarah O", opID: "s1")
        let op = try #require(started)
        #expect(op.body["record_id"] == 1)
        #expect(op.body["person_id"] == 7)
        #expect(log.ordered.filter { $0["started_by_name"] == "Sarah O" }.count == 2)
        log.rollback("s1")
        #expect(log.ordered.filter { $0["started_by_name"] == "Sarah O" }.isEmpty)
    }

    @Test("a paste is adds and breaks in order, each anchored on the one before")
    func paste() {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", type: "break"), rec(3, "a3", name: "C")])
        let sets: [[Selection.ClipTune]] = [[.init(tuneID: 5, name: "X"), .init(tuneID: nil, name: "Y")], [.init(tuneID: nil, name: "Z")]]
        let ops = log.paste(sets, at: .newSet(.server(3)))
        #expect(ops.map { $0.opType } == ["add_tune", "add_tune", "set_break", "add_tune", "set_break"])
        #expect(ops[0].body["before_record_id"] == 3)
        #expect(ops[0].body["tune_id"] == 5)
        #expect(ops[0].body["no_merge"] == true)
        #expect(ops[1].body["after_record_id"] == .string("temp-\(ops[0].opID)"))
        #expect(ops[2].body["after_record_id"] == .string("temp-\(ops[1].opID)"))
        #expect(ops[4].body["before_record_id"] == 3)
        #expect(names(log) == ["A", "|", "X", "Y", "|", "Z", "|", "C"])
    }

    @Test("a tune the open set already has merges into it: no new row, a plain add with no anchors")
    func mergeIntoOpenSet() {
        var r1 = rec(1, "a1", name: "The Kesh")
        if case .object(var o) = r1 { o["tune_id"] = 55; r1 = .object(o) }
        var log = LiveLog(records: [r1, rec(2, "a2", name: "Unlinked Thing")])
        let merged = log.logTune(["tune_id": 55, "name": "The Kesh"], at: .end, opID: "m1")
        #expect(merged.mergedInto?.recordID == .server(1))
        #expect(merged.ops[0].body["after_record_id"] == .null)
        #expect(log.records.count == 2)
        let byName = log.logTune(["name": "unlinked thing"], at: .end, opID: "m2")
        #expect(byName.mergedInto?.recordID == .server(2))
        // Keep both, and anywhere but the end, adds a row.
        let both = log.logTune(["tune_id": 55, "name": "The Kesh", "no_merge": true], at: .end, opID: "m3")
        #expect(both.mergedInto == nil)
        #expect(both.ops[0].body["no_merge"] == true)
        let mid = log.logTune(["tune_id": 55, "name": "The Kesh"], at: .after(.server(1)), opID: "m4")
        #expect(mid.mergedInto == nil)
        #expect(log.records.count == 4)
    }

    @Test("a tune named by id is sent as the id alone; its name only labels the row")
    func sentByID() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "Kesh")])
        let byID = log.logTune(["tune_id": 1566, "name": "Holly Bush, The"], at: .end, opID: "i1")
        #expect(byID.ops[0].body["tune_id"] == 1566)
        #expect(byID.ops[0].body["name"] == nil)
        #expect(byID.ops[0].label == "Holly Bush, The")
        #expect(names(log) == ["Kesh", "Holly Bush, The"])
        let imported = log.logTune(["thesession_id": 7080, "name": "#7080"], at: .end, opID: "i2")
        #expect(imported.ops[0].body["name"] == nil)
        // A typed name goes as typed: the server matches it.
        let typed = log.logTune(["name": "Some Reel"], at: .end, opID: "i3")
        #expect(typed.ops[0].body["name"] == "Some Reel")
        // A relink sends the id alone; a rename (unlink with a name) keeps its name.
        let relinked = log.changeTune(.server(1), ["tune_id": 9, "name": "Kesh, The"], patch: ["tune_id": 9], opID: "c1")
        let relink = try #require(relinked)
        #expect(relink.body["name"] == nil)
        log.settle(opID: "c1", answer: ["success": false, "rejected": true, "reason": "invalid"])
        let renamed = log.changeTune(.server(1), ["name": "A2", "unlink": true], patch: ["name": "A2"], opID: "c2")
        let rename = try #require(renamed)
        #expect(rename.body["name"] == "A2")
    }

    @Test("a placeholder sits at the cursor until it's dropped")
    func placeholder() {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B")])
        let id = log.startResolving("kesh", at: .after(.server(1)))
        #expect(names(log) == ["A", "kesh", "B"])
        #expect(log.pending.isEmpty)
        log.dropPlaceholder(id)
        #expect(names(log) == ["A", "B"])
    }

    @Test("editing a tune: shown at once, one change_tune op, rolled back on a refusal")
    func changeTune() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "Kesh")])
        let changed = log.changeTune(.server(1), ["tune_id": 9, "name": "The Kesh"], patch: ["tune_id": 9, "name": "The Kesh"], opID: "c1")
        let op = try #require(changed)
        #expect(op.body["op_type"] == "change_tune")
        #expect(op.body["record_id"] == 1)
        #expect(names(log) == ["The Kesh"])
        log.settle(opID: "c1", answer: ["success": false, "rejected": true, "reason": "invalid"])
        #expect(names(log) == ["Kesh"])
    }

    @Test("a queued change says so on its row, keeps its order, and survives being saved and restored")
    func queuedAndSaved() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "A")], lastEventID: 7)
        _ = log.addTune(["name": "B"], at: .end, opID: "b")
        _ = log.addTune(["name": "C"], at: .end, opID: "c")
        #expect(log.sendOrder == ["b", "c"])
        #expect(log.pending["b"]!.ts < log.pending["c"]!.ts)
        log.markQueued("b")
        log.markQueued("c")
        #expect(log.queuedCount == 2)
        #expect(log.ordered.filter { $0["_status"] == "queued" }.count == 2)
        // Saved to disk and read back: the queue, its rows and the cursor into the stream.
        let data = try JSONEncoder().encode(log)
        let back = try JSONDecoder().decode(LiveLog.self, from: data)
        #expect(back == log)
        // Laid over a fresh load, the queued rows stay where they were, still marked.
        let fresh = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a0", name: "Z")], lastEventID: 9)
        let rebased = back.rebased(onto: fresh)
        #expect(names(rebased) == ["Z", "A", "B", "C"])
        #expect(rebased.ordered.filter { $0["_status"] == "queued" }.count == 2)
        #expect(rebased.sendOrder == ["b", "c"])
    }

    @Test("ops made in the same millisecond still have an order")
    func sameMillisecond() {
        var log = LiveLog(records: [])
        for i in 0..<20 { _ = log.addTune(["name": .string("T\(i)")], at: .end, opID: String(format: "op%02d", i)) }
        #expect(log.sendOrder == (0..<20).map { String(format: "op%02d", $0) })
    }

    @Test("a row someone else removed stays removed: not brought back by a rebase or an undo")
    func removedElsewhereStaysRemoved() throws {
        var log = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B")], lastEventID: 1)
        _ = log.changeTune(.server(1), ["name": "A2", "unlink": true], patch: ["name": "A2"], opID: "c1")
        log.markQueued("c1")
        // Back online: the fresh log no longer has row 1.
        var rebased = log.rebased(onto: LiveLog(records: [rec(2, "a2", name: "B")], lastEventID: 5))
        #expect(names(rebased) == ["B"])
        // The change is refused; undoing it doesn't resurrect the row.
        rebased.settle(opID: "c1", answer: ["success": false, "rejected": true, "reason": "target_deleted"])
        #expect(names(rebased) == ["B"])
        // Live, too: the removal arrives on the stream while a change is pending.
        var live = LiveLog(records: [rec(1, "a1", name: "A"), rec(2, "a2", name: "B")], lastEventID: 1)
        _ = live.changeTune(.server(1), ["name": "A2", "unlink": true], patch: ["name": "A2"], opID: "c2")
        var gone = rec(1, "a1", name: "A2")
        if case .object(var o) = gone { o["deleted"] = true; gone = .object(o) }
        live.apply(["op_type": "remove_tune", "event_id": 2, "record": gone])
        live.rollback("c2")
        #expect(names(live) == ["B"])
        // But undoing a removal still brings the row back.
        let removed = live.remove(.server(2), opID: "r1")
        _ = try #require(removed)
        live.rollback("r1")
        #expect(names(live) == ["B"])
    }
}

/// The meter's "Wrong tune" takes back the row "this is it" logged: by its temporary id
/// before the server answers (the removal queues behind the add), by the server's after.
@Suite("Taking back a logged tune")
struct TakeBackTests {
    private func tune(_ id: Int, _ pos: String, tuneID: Int, name: String) -> JSONValue {
        ["session_instance_tune_id": JSONValue(id), "order_position": .string(pos), "record_type": "tune",
         "name": .string(name), "tune_id": JSONValue(tuneID), "deleted": false]
    }

    @Test("a new row: removed by its temporary id, or by the server's once answered")
    func newRow() throws {
        var log = LiveLog(records: [tune(1, "a1", tuneID: 27, name: "Drowsy Maggie")], lastEventID: 5)
        let r = log.logTune(["tune_id": 452, "name": "Fred Finn's"], at: .end, opID: "op1")
        #expect(r.mergedInto == nil)
        let temp = RecordID.temp("temp-op1")
        #expect(log.ordered.contains { $0.recordID == temp })

        // before an answer: the removal names the temporary row, and is sent with the real id
        var early = log
        let removed = early.remove(early.resolve(temp))
        let op = try #require(removed)
        #expect(!early.ordered.contains { $0.recordID == temp })
        #expect(op.body["record_id"] == .string("temp-op1"))
        let sent = LogState.remapAnchors(op.body, tempToReal: ["temp-op1": 77])
        #expect(sent.payload["record_id"] == 77 && !sent.skip)

        // after an answer: the temporary id leads to the server's row
        log.settlePending("op1", with: ["record": tune(77, "a2", tuneID: 452, name: "Fred Finn's")])
        _ = log.apply(["op_type": "add_tune", "event_id": 6, "record": tune(77, "a2", tuneID: 452, name: "Fred Finn's")])
        #expect(log.resolve(temp) == .server(77))
        let target = log.resolve(temp)
        let gone = log.remove(target)
        #expect(gone != nil)
        #expect(!log.ordered.contains { $0["tune_id"] == 452 })
    }

    @Test("a tune the open set already has merges: no row of its own to take back")
    func merged() {
        var log = LiveLog(records: [tune(1, "a1", tuneID: 452, name: "Fred Finn's")], lastEventID: 5)
        let r = log.logTune(["tune_id": 452, "name": "Fred Finn's"], at: .end, opID: "op2")
        #expect(r.mergedInto != nil)
        #expect(!log.ordered.contains { $0.recordID == .temp("temp-op2") })
    }
}
