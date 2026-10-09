import Foundation
import Testing

@testable import CeolLogic

@Suite("The listening service's wire")
struct ListenWireTests {
    @Test("The start names the night, so the service can prefer its session's tunes")
    func startNamesTheNight() {
        let with = ListenWire.start(streamID: "s", instanceID: 42)
        #expect(with.contains(#""instance_id":42"#) && with.contains(#""stream_id":"s""#))
        #expect(!ListenWire.start(streamID: "s").contains("instance_id"))
    }

    @Test("A frame is the offset as a little-endian UInt64, then 16-bit little-endian samples")
    func frame() {
        let data = ListenWire.frame(offset: 0x0102, samples: [1, -2][...])
        #expect(Array(data) == [0x02, 0x01, 0, 0, 0, 0, 0, 0, 0x01, 0x00, 0xFE, 0xFF])
    }

    @Test("Chunks go out in order, and an acknowledgement frees what the server holds")
    func sendAndAcknowledge() {
        var box = ListenOutbox(capacity: 100)
        box.append(Array(0..<30).map(Int16.init))
        let a = box.next(max: 20)
        #expect(a?.offset == 0 && a?.samples.count == 20)
        let b = box.next(max: 20)
        #expect(b?.offset == 20 && Array(b!.samples) == Array(20..<30).map(Int16.init))
        #expect(box.next(max: 20) == nil)
        box.acknowledge(25)
        #expect(box.start == 25 && box.end == 30)
    }

    @Test("After a reconnect it resends from what the server holds")
    func resume() {
        var box = ListenOutbox(capacity: 100)
        box.append(Array(repeating: 1, count: 50))
        _ = box.next(max: 50)
        #expect(box.resume(serverHas: 30) == nil)
        #expect(box.next(max: 100)?.offset == 30)
    }

    @Test("Audio past the outbox's capacity is dropped, and a server behind it is told to skip")
    func skipAfterALongOutage() {
        var box = ListenOutbox(capacity: 40)
        box.append(Array(repeating: 1, count: 100))   // the oldest 60 are gone
        #expect(box.start == 60 && box.end == 100)
        #expect(box.resume(serverHas: 10) == 60)
        let c = box.next(max: 100)
        #expect(c?.offset == 60 && c?.samples.count == 40)
    }

    @Test("The service's messages decode by type, the state with its candidates")
    func messages() {
        #expect(ListenMessage.decode(#"{"type":"ready","stream_id":"x","have":44100}"#) == .ready(have: 44100))
        #expect(ListenMessage.decode(#"{"type":"ack","have":22050}"#) == .ack(have: 22050))
        let text = #"""
            {"type":"state","status":"listening","t_ms":16000,"top":[{"tune_id":91,"name":"Roaring Barmaid, The",
             "type":"jig","p":0.62,"outside":false},{"tune_id":514,"name":"Down The Broom","type":"reel","p":0.3}],
             "none":0.01,"tuneness":0.981,"shown":91,"notes":101,"wide":false,"compute_ms":248,"lag_ms":0,
             "history":[{"tune_id":91,"name":"Roaring Barmaid, The","from_ms":16000}],"heard_ms":16500}
            """#
        guard case .state(let s) = ListenMessage.decode(text) else {
            Issue.record("not a state")
            return
        }
        #expect(s.tMs == 16000 && s.top.count == 2 && s.shown == 91)
        #expect(s.shownCandidate?.name == "Roaring Barmaid, The")
        #expect(s.top[1].outside == false && !s.notATune && s.history.first?.fromMs == 16000)
    }

    @Test("A state says when the tune shown may have changed; an older service's says nothing")
    func changing() throws {
        let text = #"""
            {"type":"state","t_ms":52000,"top":[{"tune_id":91,"name":"Roaring Barmaid, The","p":0.9},
             {"tune_id":514,"name":"Down The Broom","p":0.08}],"none":0.02,"shown":91,
             "changing":{"tune_id":91,"name":"Roaring Barmaid, The","since_ms":48000}}
            """#
        guard case .state(let s) = ListenMessage.decode(text) else {
            Issue.record("not a state")
            return
        }
        #expect(s.changing == ListenState.Changing(tuneID: 91, name: "Roaring Barmaid, The", sinceMs: 48000))
        #expect(s.mayHaveChanged)
        #expect(s.named { $0 == 91 ? "The Roaring Barmaid" : nil }.changing?.name == "The Roaring Barmaid")
        guard case .state(let old) = ListenMessage.decode(#"{"type":"state","t_ms":4000,"top":[],"none":0.1,"changing":null}"#) else {
            Issue.record("not a state")
            return
        }
        #expect(old.changing == nil && !old.mayHaveChanged)
    }

    @Test("The meter shows a tune as the session does; the dump's name only for one it doesn't know")
    func named() throws {
        let text = #"""
            {"type":"state","t_ms":8000,"top":[{"tune_id":91,"name":"Roaring Barmaid, The","p":0.6},
             {"tune_id":7,"name":"The Rose In The Heather","p":0.2},{"tune_id":514,"name":"Down The Broom","p":0.1}],
             "none":0.1,"shown":91,"history":[{"tune_id":91,"name":"Roaring Barmaid, The","from_ms":4000}]}
            """#
        guard case .state(let s) = ListenMessage.decode(text) else {
            Issue.record("not a state")
            return
        }
        let vocab = try #require(Composer.buildIndex(
            known: [["tune_id": 91, "name": "The Roaring Barmaid", "alias": ""],
                    ["tune_id": 7, "name": "The Rose In The Heather", "alias": "Rosie"]],
            aliases: nil))
        let n = s.named { vocab.byID[$0]?.displayName }
        #expect(n.top.map(\.name) == ["The Roaring Barmaid", "Rosie", "Down The Broom"])
        #expect(n.history.first?.name == "The Roaring Barmaid")
        #expect(n.shown == 91 && n.top[0].p == 0.6)
    }

    @Test("A tap names the tune and what was on screen")
    func taps() {
        #expect(ListenWire.tapThis(tuneID: 91, shown: [91, 514]) == #"{"action":"this","shown":[91,514],"tune_id":91,"type":"tap"}"#)
        #expect(ListenWire.tapNone(shown: [91]) == #"{"action":"none","shown":[91],"type":"tap"}"#)
    }

    @Test("A meter-log line wraps the message as it came, on one line, with when and which way")
    func meterLog() throws {
        let line = ListenWire.logLine(atMs: 4210, dir: "in", message: "{\"type\":\"state\",\n \"t_ms\":4000}")
        #expect(line.hasSuffix("\n") && line.dropLast().contains("\n") == false)
        let obj = try #require(JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any])
        #expect(obj["at_ms"] as? Int == 4210 && obj["dir"] as? String == "in")
        #expect((obj["msg"] as? [String: Any])?["t_ms"] as? Int == 4000)
        #expect(ListenWire.event("end_set") == #"{"type":"end_set"}"#)
        #expect(ListenWire.event("logged", ["tune_id": 91]) == #"{"tune_id":91,"type":"logged"}"#)
    }
}
