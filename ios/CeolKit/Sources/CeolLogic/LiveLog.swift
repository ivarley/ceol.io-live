// A night's live log, as a client holds it (spec 024): the records, the night's own
// fields, and how far into the event stream it has read. Built from the bootstrap and
// kept current by the referee's ops (LogState.recordChanges / metaChanges, shared with
// the web logger), so it matches what every other client on the night shows.
//
// Records stay JSON (LogRecord) so nothing the server sent is dropped; the order they
// are held in is the web's byId Map order (a replaced record keeps its place, a new one
// goes last), which is what computeOrdered starts from.

import Foundation

public struct LiveLog: Sendable, Equatable {
    public internal(set) var records: [LogRecord] = []
    /// The night's fields that ops change: notes, instance_date, session_date,
    /// start_time, end_time, instance_name, log_complete.
    public var meta: [String: JSONValue]
    /// The last event applied: the cursor a reconnect resumes from.
    public internal(set) var highWater: Int

    /// Ops sent and not yet answered, by op_id.
    public internal(set) var pending: [String: PendingOp] = [:]
    /// Temp ids the server has answered, and the real ids they became.
    public internal(set) var tempToReal: [String: JSONValue] = [:]

    public init(records: [LogRecord], meta: [String: JSONValue] = [:], lastEventID: Int = 0) {
        self.meta = meta
        self.highWater = lastEventID
        for r in records { put(r) }
    }

    /// The records in log order.
    public var ordered: [LogRecord] { LogState.computeOrdered(records) }

    /// Apply one op from the stream (or a POST's ack). Returns whether anything changed.
    /// An op at or below the high-water mark has been applied already: a reconnect's
    /// replay can resend it, and applying it again is harmless but skipped.
    @discardableResult
    public mutating func apply(_ op: JSONValue) -> Bool {
        if let eid = op["event_id"]?.intValue {
            if eid <= highWater { return false }
            highWater = eid
        }
        // My own op, echoed before (or instead of) its POST answer: settle it here.
        if let opID = op["op_id"]?.stringValue, pending[opID] != nil { settlePending(opID, with: op) }
        let changes = LogState.recordChanges(op)
        for r in changes.puts { put(r) }
        for id in changes.drops { drop(id) }
        let patch = LogState.metaChanges(op)
        for (k, v) in patch { meta[k] = v }
        return !changes.puts.isEmpty || !changes.drops.isEmpty || !patch.isEmpty
    }

    mutating func put(_ r: LogRecord) {
        let id = r["session_instance_tune_id"]
        if let i = records.firstIndex(where: { $0["session_instance_tune_id"] == id }) {
            records[i] = r
        } else {
            records.append(r)
        }
    }

    mutating func drop(_ id: JSONValue) {
        records.removeAll { $0["session_instance_tune_id"] == id }
    }
}
