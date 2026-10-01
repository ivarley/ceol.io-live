import Foundation
import Testing

@testable import CeolLogic

@Suite("The listening service's wire")
struct ListenWireTests {
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

    @Test("A tap names the tune and what was on screen")
    func taps() {
        #expect(ListenWire.tapThis(tuneID: 91, shown: [91, 514]) == #"{"action":"this","shown":[91,514],"tune_id":91,"type":"tap"}"#)
        #expect(ListenWire.tapNone(shown: [91]) == #"{"action":"none","shown":[91],"type":"tap"}"#)
    }
}
