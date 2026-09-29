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
}
