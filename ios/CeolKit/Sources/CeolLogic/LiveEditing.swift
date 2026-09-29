// Writing to a night (plan Phase 5b), the optimistic pipeline of the web logger
// (frontend/src/App.svelte: addOptimistic, endSet, splitAt, joinAt, removeTune,
// confirmRow, trySend, settleOp, undoOp). Each edit changes the log at once and returns
// the op to send; the server's answer (or its echo on the stream, whichever comes
// first) settles it, and a refusal or a failure to send rolls it back.
//
// An op's answer carries an event_id, but only the stream moves the high-water mark:
// other people's earlier events may still be on their way, and must not be skipped.

import Foundation

/// An op sent and not yet answered, with what it takes to undo it.
public struct PendingOp: Sendable, Equatable {
    public var opID: String
    public var opType: String
    /// The request body: op_id, op_type and the op's fields.
    public var body: [String: JSONValue]
    /// Optimistic rows this op added, dropped when it settles or rolls back.
    public var tempIDs: [JSONValue] = []
    /// Records as they were before this op changed them, put back on a rollback.
    public var prev: [LogRecord] = []
    /// What the op did to the log, done again over a fresh bootstrap while it's unanswered.
    var puts: [LogRecord] = []
    var drops: [JSONValue] = []
}

extension LiveLog {
    // MARK: - Edits

    /// Log a tune at the cursor: `payload` is {name} or {tune_id, name, tune_type}.
    /// Returns the ops to send, in order (a new set in a gap is a tune and then a break),
    /// and where the cursor goes next.
    public mutating func addTune(_ payload: [String: JSONValue], at cursor: Cursor, opID: String = LiveLog.newOpID())
        -> (ops: [PendingOp], cursor: Cursor)
    {
        let tempID = JSONValue.string("temp-\(opID)")
        let name = payload["name"] ?? .null
        if case .newSet(let nextFirst) = cursor {
            // A new set between two sets: the tune, then a break, both before the next set.
            let ord = ordered
            let idx = ord.firstIndex { $0.recordID == nextFirst }
            let next = idx.flatMap { ord[$0].orderPosition }
            let prevPos = idx.flatMap { $0 > 0 ? ord[$0 - 1].orderPosition : nil }
            let tunePos = FracIndex.optimisticBetween(prevPos, next)
            let breakPos = FracIndex.optimisticBetween(tunePos, next)
            let breakOpID = LiveLog.newOpID()
            let breakTemp = JSONValue.string("temp-\(breakOpID)")
            let tune = tempRecord(tempID, name: name, payload: payload, position: tunePos)
            let brkRec = tempBreak(breakTemp, position: breakPos)
            put(tune)
            put(brkRec)
            var addBody = payload
            addBody["before_record_id"] = nextFirst.json
            addBody["after_record_id"] = .null
            let add = register(opID, "add_tune", addBody, temps: [tempID], puts: [tune])
            let brk = register(
                breakOpID, "set_break", ["action": "insert", "before_record_id": nextFirst.json], temps: [breakTemp],
                puts: [brkRec])
            return ([add, brk], .after(.temp("temp-\(opID)")))
        }
        let pos = LogState.cursorPos(cursor, ordered: ordered, allRecords: records)
        let tune = tempRecord(tempID, name: name, payload: payload, position: pos.position)
        put(tune)
        var body = payload
        body["after_record_id"] = pos.afterID?.json ?? .null
        body["before_record_id"] = pos.beforeID?.json ?? .null
        let op = register(opID, "add_tune", body, temps: [tempID], puts: [tune])
        // Mid-log, the cursor follows the new tune so a burst goes in order; at the end
        // it stays at the end.
        let next: Cursor = cursor == .end ? .end : .after(.temp("temp-\(opID)"))
        return ([op], next)
    }

    /// End the open set: a break at the end (nil on an empty log). The anchor is null so
    /// the server appends when it runs the op, never a temp id.
    public mutating func endSet(opID: String = LiveLog.newOpID()) -> PendingOp? {
        guard !ordered.isEmpty else { return nil }
        let temp = JSONValue.string("temp-\(opID)")
        let brk = tempBreak(temp, position: FracIndex.generateAppend(LogState.maxPos(records)))
        put(brk)
        return register(opID, "set_break", ["action": "insert", "after_record_id": .null], temps: [temp], puts: [brk])
    }

    /// Split a set after one of its tunes.
    public mutating func split(after id: RecordID, opID: String = LiveLog.newOpID()) -> PendingOp {
        let ord = ordered
        let idx = ord.firstIndex { $0.recordID == id }
        let pos = idx.flatMap { ord[$0].orderPosition }
        let next = idx.flatMap { $0 + 1 < ord.count ? ord[$0 + 1].orderPosition : nil }
        let temp = JSONValue.string("temp-\(opID)")
        let brk = tempBreak(temp, position: FracIndex.optimisticBetween(pos, next))
        put(brk)
        return register(opID, "set_break", ["action": "insert", "after_record_id": id.json], temps: [temp], puts: [brk])
    }

    /// Join two sets: remove the break between them.
    public mutating func join(breakID: RecordID, opID: String = LiveLog.newOpID()) -> PendingOp? {
        guard let brk = records.first(where: { $0.recordID == breakID }) else { return nil }
        drop(breakID.json)
        var op = register(opID, "set_break", ["action": "remove", "record_id": breakID.json], temps: [], drops: [breakID.json])
        op.prev = [brk]
        pending[opID] = op
        return op
    }

    /// Remove a tune.
    public mutating func remove(_ id: RecordID, opID: String = LiveLog.newOpID()) -> PendingOp? {
        guard let r = records.first(where: { $0.recordID == id }) else { return nil }
        drop(id.json)
        var op = register(opID, "remove_tune", ["record_id": id.json], temps: [], drops: [id.json])
        op.prev = [r]
        pending[opID] = op
        return op
    }

    /// Confirm a low-confidence tune.
    public mutating func confirm(_ id: RecordID, opID: String = LiveLog.newOpID()) -> PendingOp? {
        guard let r = records.first(where: { $0.recordID == id }), case .object(var o) = r else { return nil }
        o["confidence"] = 100
        put(.object(o))
        var op = register(
            opID, "set_confidence", ["record_id": id.json, "confidence": 100], temps: [], puts: [.object(o)])
        op.prev = [r]
        pending[opID] = op
        return op
    }

    // MARK: - Sending and settling

    /// The body to POST for a pending op, with any temp anchors swapped for the real ids
    /// the server has since given them; nil when the op's record never reached the server
    /// (nothing to send).
    public func sendableBody(_ opID: String) -> [String: JSONValue]? {
        guard let op = pending[opID] else { return nil }
        let r = LogState.remapAnchors(op.body, tempToReal: tempToReal)
        return r.skip ? nil : r.payload
    }

    /// The POST's answer. A success settles the op and applies what it did; a refusal
    /// rolls it back and returns the server's reason.
    @discardableResult
    public mutating func settle(opID: String, answer: JSONValue) -> String? {
        if answer["success"]?.boolValue == false || answer["rejected"].isTruthy {
            rollback(opID)
            return answer["message"]?.stringValue ?? answer["reason"]?.stringValue ?? "That change wasn't accepted."
        }
        var answer = answer
        if answer["op_type"] == nil, case .object(var o) = answer, let type = pending[opID]?.opType {
            o["op_type"] = .string(type)
            answer = .object(o)
        }
        settlePending(opID, with: answer)
        let changes = LogState.recordChanges(answer)
        for r in changes.puts { put(r) }
        for id in changes.drops { drop(id) }
        for (k, v) in LogState.metaChanges(answer) { meta[k] = v }
        return nil
    }

    /// Undo an op's optimistic change (a refusal, or it couldn't be sent).
    public mutating func rollback(_ opID: String) {
        guard let op = pending.removeValue(forKey: opID) else { return }
        for t in op.tempIDs { drop(t) }
        for r in op.prev { put(r) }
    }

    /// The log from a fresh bootstrap, with this log's unanswered ops laid over it again,
    /// so a reconnect doesn't make a change in flight vanish and reappear.
    public func rebased(onto fresh: LiveLog) -> LiveLog {
        var out = fresh
        out.pending = pending
        out.tempToReal = tempToReal
        for op in pending.values {
            for r in op.puts { out.put(r) }
            for id in op.drops { out.drop(id) }
        }
        return out
    }

    /// Where a temp id stands now: its real id once answered.
    public func resolve(_ id: RecordID) -> RecordID {
        if case .temp(let s) = id, let real = tempToReal[s], let r = RecordID(real) { return r }
        return id
    }

    // MARK: -

    public static func newOpID() -> String { UUID().uuidString.lowercased() }

    mutating func settlePending(_ opID: String, with answer: JSONValue) {
        guard let op = pending.removeValue(forKey: opID) else { return }
        for t in op.tempIDs { drop(t) }
        if let temp = op.tempIDs.first?.stringValue, let real = answer["record"]?["session_instance_tune_id"] {
            tempToReal[temp] = real
        }
    }

    private mutating func register(
        _ opID: String, _ type: String, _ fields: [String: JSONValue], temps: [JSONValue], puts: [LogRecord] = [],
        drops: [JSONValue] = []
    ) -> PendingOp {
        var body = fields
        body["op_id"] = .string(opID)
        body["op_type"] = .string(type)
        let op = PendingOp(opID: opID, opType: type, body: body, tempIDs: temps, puts: puts, drops: drops)
        pending[opID] = op
        return op
    }

    private func tempRecord(_ id: JSONValue, name: JSONValue, payload: [String: JSONValue], position: String) -> LogRecord {
        .object([
            "session_instance_tune_id": id, "name": name, "tune_id": payload["tune_id"] ?? .null,
            "tune_type": payload["tune_type"] ?? .null, "record_type": "tune", "order_position": .string(position),
            "deleted": false, "_temp": true, "_status": "sending",
        ])
    }

    private func tempBreak(_ id: JSONValue, position: String) -> LogRecord {
        .object([
            "session_instance_tune_id": id, "record_type": "break", "order_position": .string(position),
            "deleted": false, "_temp": true,
        ])
    }
}
