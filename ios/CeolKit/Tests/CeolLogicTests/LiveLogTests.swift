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
