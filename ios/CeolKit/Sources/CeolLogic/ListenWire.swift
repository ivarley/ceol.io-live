// The listening service's wire (listen/service.py, spec 053): what the app sends while
// it records a night, and what comes back. No audio code here, so it is tested on the
// Mac (CeolLogicTests/ListenWireTests).
//
//   app -> {"type":"start","stream_id":…,"sample_rate":22050}   (again after a reconnect)
//   srv -> {"type":"ready","have":N}          N: the samples it already holds
//   app -> binary: UInt64 little-endian sample offset, then 16-bit little-endian PCM
//   srv -> {"type":"ack","have":N}            contiguous samples held
//   srv -> {"type":"state",…}                 every 4 s of audio: what it thinks is playing
//   app -> {"type":"tap","action":"this"|"none",…}, {"type":"skip","to":N}, {"type":"stop"}
//
// The phone's own file is the recording; the stream is for the meter. So the outbox
// holds only the last few minutes of unacknowledged audio, and after a longer outage the
// app says "skip" and the server fills the gap with silence, keeping its clock the
// recording's.

import Foundation

public enum ListenWire {
    public static let sampleRate = 22050

    /// One binary message: where the first sample sits in the stream, then the samples.
    public static func frame(offset: Int, samples: ArraySlice<Int16>) -> Data {
        var data = Data(capacity: 8 + samples.count * 2)
        withUnsafeBytes(of: UInt64(offset).littleEndian) { data.append(contentsOf: $0) }
        for s in samples { withUnsafeBytes(of: s.littleEndian) { data.append(contentsOf: $0) } }
        return data
    }

    /// Start (or resume) a stream. With the night, the service prefers the tunes its
    /// session has logged before (spec 053, the tiers), asking the web app with this
    /// device's token.
    public static func start(streamID: String, instanceID: Int? = nil) -> String {
        var object: [String: Any] = ["type": "start", "stream_id": streamID, "sample_rate": sampleRate]
        if let instanceID { object["instance_id"] = instanceID }
        return json(object)
    }

    public static func skip(to offset: Int) -> String { json(["type": "skip", "to": offset]) }

    public static func stop() -> String { json(["type": "stop"]) }

    /// "This is it": the tune a person says is playing.
    public static func tapThis(tuneID: Int, shown: [Int]) -> String {
        json(["type": "tap", "action": "this", "tune_id": tuneID, "shown": shown])
    }

    /// "None of these": rules the shown names out for a while and widens the search.
    public static func tapNone(shown: [Int]) -> String {
        json(["type": "tap", "action": "none", "shown": shown])
    }

    // MARK: The meter log
    //
    // Beside each recording the phone keeps what the meter showed: one JSON object per
    // line, {"at_ms":…,"dir":"in"|"out"|"app","msg":{…}}. "in" is a message from the
    // service exactly as it came (each state carries its own t_ms, the audio time it is
    // about); "out" is a tap as it was sent; "app" is the phone's own doing (the night it
    // began, a tune logged, a set ended, the link). at_ms is wall-clock time since the
    // recording began, so the lag between audio and screen can be read back. Uploaded with
    // the recording (PUT /api/recordings/<id>/listen-log).

    /// One line of the meter log, newline included. `message` is a JSON object's text.
    public static func logLine(atMs: Int, dir: String, message: String) -> String {
        let flat = message.replacingOccurrences(of: "\n", with: " ").replacingOccurrences(of: "\r", with: " ")
        return "{\"at_ms\":\(atMs),\"dir\":\"\(dir)\",\"msg\":\(flat)}\n"
    }

    /// An "app" event for the meter log: its type and fields.
    public static func event(_ type: String, _ fields: [String: Any] = [:]) -> String {
        var object = fields
        object["type"] = type
        return json(object)
    }

    private static func json(_ object: [String: Any]) -> String {
        let data = (try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])) ?? Data()
        return String(decoding: data, as: UTF8.self)
    }
}

/// Audio not yet acknowledged by the service, by its offset in the stream. Holds at most
/// `capacity` samples: older audio is dropped (the phone's file still has it), and a
/// reconnect that finds the server behind what is held says skip.
public struct ListenOutbox: Sendable {
    /// The offset of the first sample held.
    public private(set) var start = 0
    /// The next offset to send.
    public private(set) var sent = 0
    public let capacity: Int
    private var samples: [Int16] = []
    private var head = 0          // samples[head] is the sample at `start`

    public init(capacity: Int) { self.capacity = capacity }

    /// One past the newest sample held.
    public var end: Int { start + (samples.count - head) }
    public var unsent: Int { end - sent }

    public mutating func append(_ more: [Int16]) {
        samples.append(contentsOf: more)
        let over = (samples.count - head) - capacity
        if over > 0 { drop(over) }
    }

    /// The server holds everything before `have`.
    public mutating func acknowledge(_ have: Int) {
        if have > start { drop(min(have, end) - start) }
    }

    /// After a (re)connect, the server holds `have` samples: send from there, or, if that
    /// audio is no longer held, from the oldest held, and return where to skip to.
    public mutating func resume(serverHas have: Int) -> Int? {
        acknowledge(have)
        if have < start {
            sent = start
            return start
        }
        sent = max(have, start)
        return nil
    }

    /// The next chunk to send, of at most `max` samples.
    public mutating func next(max: Int) -> (offset: Int, samples: ArraySlice<Int16>)? {
        guard sent < end else { return nil }
        if sent < start { sent = start }
        let from = head + (sent - start)
        let to = Swift.min(samples.count, from + max)
        let chunk = (offset: sent, samples: samples[from..<to])
        sent += to - from
        return chunk
    }

    private mutating func drop(_ n: Int) {
        guard n > 0 else { return }
        head += n
        start += n
        if sent < start { sent = start }
        // compact now and then rather than on every drop
        if head > 1 << 16, head > samples.count / 2 {
            samples.removeFirst(head)
            head = 0
        }
    }
}

/// What the service thinks is playing (its "state" message).
public struct ListenState: Decodable, Sendable, Equatable {
    public struct Candidate: Decodable, Sendable, Equatable, Identifiable {
        public let tuneID: Int
        public internal(set) var name: String?
        public let type: String?
        /// The decoder's belief, 0...1.
        public let p: Double
        /// Not in the session's repertoire: from the whole-corpus fallback.
        public let outside: Bool
        public var id: Int { tuneID }

        enum CodingKeys: String, CodingKey { case tuneID = "tune_id", name, type, p, outside }

        public init(from decoder: any Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            tuneID = try c.decode(Int.self, forKey: .tuneID)
            name = try c.decodeIfPresent(String.self, forKey: .name)
            type = try c.decodeIfPresent(String.self, forKey: .type)
            p = try c.decode(Double.self, forKey: .p)
            outside = try c.decodeIfPresent(Bool.self, forKey: .outside) ?? false
        }
    }

    public struct Shown: Decodable, Sendable, Equatable {
        public let tuneID: Int
        public internal(set) var name: String?
        public let fromMs: Int
        enum CodingKeys: String, CodingKey { case tuneID = "tune_id", name, fromMs = "from_ms" }
    }

    /// ms of audio this state is about.
    public let tMs: Int
    public internal(set) var top: [Candidate]
    /// Belief that nothing is being played as a tune.
    public let none: Double
    /// 0...1: how much the last seconds sound like a tune at all.
    public let tuneness: Double?
    /// The tune the decoder would display, if any.
    public let shown: Int?
    public internal(set) var history: [Shown]
    public let status: String
    public let computeMs: Int?

    enum CodingKeys: String, CodingKey {
        case tMs = "t_ms", top, none, tuneness, shown, history, status, computeMs = "compute_ms"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        tMs = try c.decodeIfPresent(Int.self, forKey: .tMs) ?? 0
        top = try c.decodeIfPresent([Candidate].self, forKey: .top) ?? []
        none = try c.decodeIfPresent(Double.self, forKey: .none) ?? 1
        tuneness = try c.decodeIfPresent(Double.self, forKey: .tuneness)
        shown = try c.decodeIfPresent(Int.self, forKey: .shown)
        history = try c.decodeIfPresent([Shown].self, forKey: .history) ?? []
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? ""
        computeMs = try c.decodeIfPresent(Int.self, forKey: .computeMs)
    }

    /// The same state with the names this device knows put in: the service's are from
    /// thesession.org's data dump, and a tune the session knows shows as the session
    /// shows it (its alias, else its name), as the night's log does.
    public func named(by name: (Int) -> String?) -> ListenState {
        var s = self
        for i in s.top.indices { s.top[i].name = name(s.top[i].tuneID) ?? s.top[i].name }
        for i in s.history.indices { s.history[i].name = name(s.history[i].tuneID) ?? s.history[i].name }
        return s
    }

    /// The candidate on display, if the decoder is showing one.
    public var shownCandidate: Candidate? { top.first { $0.tuneID == shown } }
    /// It is more sure that nothing is being played as a tune than that anything is.
    public var notATune: Bool { none > 0.5 }
}

/// A message from the service, by its "type".
public enum ListenMessage: Sendable, Equatable {
    case ready(have: Int)
    case ack(have: Int)
    case state(ListenState)
    case done(have: Int)
    case error(String)
    case other

    public static func decode(_ text: String) -> ListenMessage {
        let data = Data(text.utf8)
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let type = obj["type"] as? String
        else { return .other }
        let have = (obj["have"] as? NSNumber)?.intValue ?? 0
        switch type {
        case "ready": return .ready(have: have)
        case "ack": return .ack(have: have)
        case "done": return .done(have: have)
        case "error": return .error(obj["error"] as? String ?? "error")
        case "state":
            if let s = try? JSONDecoder().decode(ListenState.self, from: data) { return .state(s) }
            return .other
        default: return .other
        }
    }
}
