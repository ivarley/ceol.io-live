// Server-sent events, parsed from raw bytes (the WHATWG EventSource rules the web's
// EventSource applies): lines end in \n, \r\n or \r; "field: value" with one leading
// space dropped; data lines joined with \n; a blank line dispatches; ":" lines are
// comments; an event with no data isn't dispatched. Fed chunk by chunk, since a chunk
// can end mid-line. (URLSession's line reader can't be used: it drops the blank lines
// that end each event.)

import Foundation

public struct SSEEvent: Equatable, Sendable {
    /// The event's type ("op", "presence", "typing", "ping"); "message" when unnamed.
    public var type: String
    public var data: String
    /// The stream's last event id once this event is dispatched (what a reconnect sends).
    public var lastEventID: String?

    public init(type: String, data: String, lastEventID: String?) {
        self.type = type
        self.data = data
        self.lastEventID = lastEventID
    }
}

public struct SSEParser: Sendable {
    private var line: [UInt8] = []
    private var afterCR = false
    private var data: [String] = []
    private var type = ""
    public private(set) var lastEventID: String?

    public init(lastEventID: String? = nil) {
        self.lastEventID = lastEventID
    }

    /// Feed bytes; returns the events they complete.
    public mutating func feed<S: Sequence>(_ bytes: S) -> [SSEEvent] where S.Element == UInt8 {
        var out: [SSEEvent] = []
        for b in bytes {
            if afterCR {
                afterCR = false
                if b == 0x0A { continue }  // the \n of a \r\n
            }
            if b == 0x0D || b == 0x0A {
                afterCR = b == 0x0D
                if let e = endLine() { out.append(e) }
            } else {
                line.append(b)
            }
        }
        return out
    }

    private mutating func endLine() -> SSEEvent? {
        let text = String(decoding: line, as: UTF8.self)
        line.removeAll(keepingCapacity: true)
        if text.isEmpty { return dispatch() }
        if text.hasPrefix(":") { return nil }
        let field: Substring
        var value: Substring
        if let colon = text.firstIndex(of: ":") {
            field = text[..<colon]
            value = text[text.index(after: colon)...]
            if value.hasPrefix(" ") { value = value.dropFirst() }
        } else {
            field = Substring(text)
            value = ""
        }
        switch field {
        case "data": data.append(String(value))
        case "event": type = String(value)
        case "id" where !value.contains("\0"): lastEventID = String(value)
        default: break  // retry, and anything unknown
        }
        return nil
    }

    private mutating func dispatch() -> SSEEvent? {
        defer {
            data.removeAll()
            type = ""
        }
        guard !data.isEmpty else { return nil }
        return SSEEvent(type: type.isEmpty ? "message" : type, data: data.joined(separator: "\n"), lastEventID: lastEventID)
    }
}
