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
public struct PendingOp: Sendable, Equatable, Codable {
    public var opID: String
    public var opType: String
    /// When it was made (LogState.OpClock, ms): a queue replays in this order, ties by op_id.
    public var ts: Int64 = 0
    /// Couldn't be sent (no connection): saved on the device, sent when it's back.
    public var queued = false
    /// The request body: op_id, op_type and the op's fields.
    public var body: [String: JSONValue]
    /// Optimistic rows this op added, dropped when it settles or rolls back.
    public var tempIDs: [JSONValue] = []
    /// Records as they were before this op changed them, put back on a rollback.
    public var prev: [LogRecord] = []
    /// What the op did to the log, done again over a fresh bootstrap while it's unanswered.
    var puts: [LogRecord] = []
    var drops: [JSONValue] = []
    /// Rows a rollback takes away that aren't temps (a refused restore).
    var rollbackDrops: [JSONValue] = []
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

    /// Log a tune as the composer does: a plain append of a tune the open set already
    /// has (same tune, or the same unlinked name) merges into that row instead, with no
    /// new row shown (the server corroborates it); `mergedInto` says which. Otherwise
    /// addTune. `no_merge` in the payload skips the check ("Keep both").
    public mutating func logTune(_ payload: [String: JSONValue], at cursor: Cursor, opID: String = LiveLog.newOpID())
        -> (ops: [PendingOp], cursor: Cursor, mergedInto: LogRecord?)
    {
        if case .newSet = cursor {} else if payload["no_merge"] != true {
            let pos = LogState.cursorPos(cursor, ordered: ordered, allRecords: records)
            if pos.afterID == nil && pos.beforeID == nil,
                let target = LogState.openSetMergeTarget(.object(payload), ordered: ordered)
            {
                var body = payload
                body["after_record_id"] = .null
                body["before_record_id"] = .null
                return ([register(opID, "add_tune", body, temps: [])], cursor, target)
            }
        }
        let r = addTune(payload, at: cursor, opID: opID)
        return (r.ops, r.cursor, nil)
    }

    /// A placeholder row at the cursor while the server decides what the typed text
    /// names ("resolving…"). Nothing is sent; settle it with settleResolving or drop it.
    public mutating func startResolving(_ text: String, at cursor: Cursor) -> String {
        let id = "temp-resolving-\(LiveLog.newOpID())"
        let position: String
        if case .newSet(let next) = cursor {
            let ord = ordered
            let i = ord.firstIndex { $0.recordID == next }
            position = FracIndex.optimisticBetween(i.flatMap { $0 > 0 ? ord[$0 - 1].orderPosition : nil }, i.flatMap { ord[$0].orderPosition })
        } else {
            position = LogState.cursorPos(cursor, ordered: ordered, allRecords: records).position
        }
        put(.object([
            "session_instance_tune_id": .string(id), "name": .string(text), "tune_id": .null, "tune_type": .null,
            "record_type": "tune", "order_position": .string(position), "deleted": false, "_temp": true,
            "_resolving": true,
        ]))
        return id
    }

    /// Drop a placeholder (settled, or cancelled).
    public mutating func dropPlaceholder(_ id: String) { drop(.string(id)) }

    /// Change a logged tune (change_tune): relink {tune_id, name}, unlink {unlink: true},
    /// or rename {name, unlink: true}. `patch` is how the row shows it until the answer.
    public mutating func changeTune(
        _ id: RecordID, _ payload: [String: JSONValue], patch: [String: JSONValue], opID: String = LiveLog.newOpID()
    ) -> PendingOp? {
        guard let r = records.first(where: { $0.recordID == id }), case .object(var o) = r, !r["_temp"].isTruthy else { return nil }
        for (k, v) in patch { o[k] = v }
        put(.object(o))
        var op = register(opID, "change_tune", payload.merging(["record_id": id.json]) { a, _ in a }, temps: [], puts: [.object(o)])
        op.prev = [r]
        pending[opID] = op
        return op
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

    /// Move a block (Selection.dragBlock) to a drop target: one move_tunes op. The rows
    /// take their new places at once, with a temporary break where a new set needs one.
    public mutating func move(
        _ block: Selection.DragBlock, to target: Selection.DropTarget, opID: String = LiveLog.newOpID()
    ) -> PendingOp {
        let ord = ordered
        let plan = Selection.optimisticMove(ord, allRecords: records, block: block.recordIDs, target: target)
        var prev: [LogRecord] = []
        var puts: [LogRecord] = []
        for (id, key) in plan.positions {
            guard let r = records.first(where: { $0.recordID == id }), case .object(var o) = r else { continue }
            prev.append(r)
            o["order_position"] = .string(key)
            puts.append(.object(o))
            put(.object(o))
        }
        var temps: [JSONValue] = []
        for (side, key) in [("before", plan.tempBreakBefore), ("after", plan.tempBreakAfter)] {
            guard let key else { continue }
            let t = JSONValue.string("temp-\(opID)-\(side)")
            let brk = tempBreak(t, position: key)
            put(brk)
            puts.append(brk)
            temps.append(t)
        }
        var op = register(
            opID, "move_tunes",
            [
                "record_ids": .array(block.tuneIDs.map(\.json)), "after_record_id": target.afterID?.json ?? .null,
                "before_record_id": target.beforeID?.json ?? .null, "new_set": .bool(target.newSet),
            ],
            temps: temps, puts: puts)
        op.prev = prev
        pending[opID] = op
        return op
    }

    /// Remove several tunes in one op (remove_tunes). nil when none of them is a
    /// settled row. Returns the removed records too, for an Undo.
    public mutating func removeMany(_ ids: [RecordID], opID: String = LiveLog.newOpID()) -> (PendingOp, [LogRecord])? {
        let rows = ids.compactMap { id in
            records.first { $0.recordID == id && !$0["_temp"].isTruthy && !$0.isBreak }
        }
        guard !rows.isEmpty else { return nil }
        for r in rows { if let id = r.recordID { drop(id.json) } }
        let removed = rows.compactMap(\.recordID)
        var op = register(
            opID, "remove_tunes", ["record_ids": .array(removed.map(\.json))], temps: [], drops: removed.map(\.json))
        op.prev = rows
        pending[opID] = op
        return (op, rows)
    }

    /// Undo a bulk remove: the rows come back at once, and restore_tunes brings them
    /// back for everyone.
    public mutating func restore(_ rows: [LogRecord], opID: String = LiveLog.newOpID()) -> PendingOp? {
        let back: [LogRecord] = rows.compactMap { r in
            guard case .object(var o) = r else { return nil }
            o["deleted"] = false
            return .object(o)
        }
        guard !back.isEmpty else { return nil }
        for r in back { put(r) }
        var op = register(
            opID, "restore_tunes", ["record_ids": .array(back.compactMap { $0.recordID?.json })], temps: [], puts: back)
        // A refused restore takes them away again.
        op.rollbackDrops = back.compactMap { $0.recordID?.json }
        pending[opID] = op
        return op
    }

    /// Set (or clear) who started a set: every tune in it, one op on its first tune.
    /// `name` is how the set shows it ("Sarah O").
    public mutating func setStarter(
        of setTunes: [LogRecord], personID: Int?, name: String?, opID: String = LiveLog.newOpID()
    ) -> PendingOp? {
        guard let first = setTunes.first?.recordID else { return nil }
        var prev: [LogRecord] = []
        var puts: [LogRecord] = []
        for t in setTunes {
            guard let id = t.recordID, let r = records.first(where: { $0.recordID == id }), case .object(var o) = r else { continue }
            prev.append(r)
            o["started_by_person_id"] = personID.map { JSONValue($0) } ?? .null
            o["started_by_name"] = name.map(JSONValue.string) ?? .null
            puts.append(.object(o))
            put(.object(o))
        }
        var op = register(
            opID, "attribute_set_starter", ["record_id": first.json, "person_id": personID.map { JSONValue($0) } ?? .null],
            temps: [], puts: puts)
        op.prev = prev
        pending[opID] = op
        return op
    }

    /// Paste sets of tunes at the cursor (the web's pasteSets): adds in order, a break
    /// between sets, each anchored on the row before it, so to everyone else it looks like
    /// fast logging. no_merge: a pasted duplicate is always a new row. At a new-set gap
    /// the block is closed off from the set below.
    public mutating func paste(_ sets: [[Selection.ClipTune]], at cursor: Cursor) -> [PendingOp] {
        let ord = ordered
        var afterAnchor: RecordID?
        var beforeAnchor: RecordID?
        var prevPos: String?
        var succPos: String?
        var newSetTarget: RecordID?
        func bounds(before id: RecordID) {
            let i = ord.firstIndex { $0.recordID == id }
            succPos = i.flatMap { ord[$0].orderPosition }
            prevPos = i.flatMap { $0 > 0 ? ord[$0 - 1].orderPosition : nil }
        }
        if case .newSet(let next) = cursor {
            newSetTarget = next
            beforeAnchor = next
            bounds(before: next)
        } else {
            let p = LogState.cursorPos(cursor, ordered: ord, allRecords: records)
            afterAnchor = p.afterID
            beforeAnchor = p.beforeID
            if let b = beforeAnchor {
                bounds(before: b)
            } else if let a = afterAnchor {
                let i = ord.firstIndex { $0.recordID == a }
                prevPos = i.flatMap { ord[$0].orderPosition }
                succPos = i.flatMap { $0 + 1 < ord.count ? ord[$0 + 1].orderPosition : nil }
            } else {
                prevPos = LogState.maxPos(records)
            }
        }
        var ops: [PendingOp] = []
        var prevTemp: JSONValue?
        func addBreak(_ fields: [String: JSONValue]) {
            let opID = LiveLog.newOpID()
            let t = JSONValue.string("temp-\(opID)")
            let key = FracIndex.optimisticBetween(prevPos, succPos)
            let brk = tempBreak(t, position: key)
            put(brk)
            ops.append(register(opID, "set_break", fields.merging(["action": "insert"]) { a, _ in a }, temps: [t], puts: [brk]))
            prevPos = key
            prevTemp = t
        }
        for (si, set) in sets.enumerated() {
            if si > 0 { addBreak(["after_record_id": prevTemp ?? .null]) }
            for t in set {
                let opID = LiveLog.newOpID()
                let temp = JSONValue.string("temp-\(opID)")
                let key = FracIndex.optimisticBetween(prevPos, succPos)
                let payload: [String: JSONValue] = [
                    "tune_id": t.tuneID.map { JSONValue($0) } ?? .null, "name": .string(t.name),
                    "tune_type": t.tuneType.map(JSONValue.string) ?? .null,
                ]
                let row = tempRecord(temp, name: .string(t.name), payload: payload, position: key)
                put(row)
                var body = payload
                body.removeValue(forKey: "tune_type")
                body["no_merge"] = true
                body["after_record_id"] = prevTemp ?? afterAnchor?.json ?? .null
                body["before_record_id"] = prevTemp != nil || afterAnchor != nil ? .null : beforeAnchor?.json ?? .null
                ops.append(register(opID, "add_tune", body, temps: [temp], puts: [row]))
                prevTemp = temp
                prevPos = key
            }
        }
        if let next = newSetTarget, prevTemp != nil { addBreak(["before_record_id": next.json]) }
        return ops
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
        for id in op.rollbackDrops { drop(id) }
        // Put back what the op changed, but only rows still here (or rows the op itself
        // took away): one someone else removed meanwhile stays removed.
        let removedByOp = Set(op.drops)
        for r in op.prev {
            let id = r["session_instance_tune_id"] ?? .null
            if removedByOp.contains(id) || records.contains(where: { $0["session_instance_tune_id"] == id }) { put(r) }
        }
    }

    /// The log from a fresh bootstrap, with this log's unanswered ops laid over it again,
    /// so a reconnect doesn't make a change in flight vanish and reappear.
    public func rebased(onto fresh: LiveLog) -> LiveLog {
        var out = fresh
        out.pending = pending
        out.tempToReal = tempToReal
        out.clock = clock
        // In the order they were made; a change to a row the fresh log no longer has
        // (someone removed it) isn't laid back over it.
        let here = Set(fresh.records.compactMap { $0["session_instance_tune_id"] })
        for id in sendOrder {
            guard let op = pending[id] else { continue }
            for r in op.puts {
                let rid = r["session_instance_tune_id"] ?? .null
                if r["_temp"].isTruthy || here.contains(rid) { out.put(r) }
            }
            for id in op.drops { out.drop(id) }
        }
        return out
    }

    /// The unanswered ops in the order they must be sent: by ts, then op_id.
    public var sendOrder: [String] {
        pending.values.sorted { $0.ts != $1.ts ? $0.ts < $1.ts : $0.opID < $1.opID }.map(\.opID)
    }

    /// No connection: the op waits on the device. Its rows say so (the web's "offline").
    public mutating func markQueued(_ opID: String) {
        guard var op = pending[opID], !op.queued else { return }
        op.queued = true
        let temps = Set(op.tempIDs)
        func mark(_ r: LogRecord) -> LogRecord {
            guard temps.contains(r["session_instance_tune_id"] ?? .null), case .object(var o) = r else { return r }
            o["_status"] = "queued"
            return .object(o)
        }
        op.puts = op.puts.map(mark)
        pending[opID] = op
        for r in op.puts where temps.contains(r["session_instance_tune_id"] ?? .null) { put(r) }
    }

    /// Queued ops, oldest first.
    public var queuedCount: Int { pending.values.filter(\.queued).count }

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
        let ts = clock.next(now: Int64(Date().timeIntervalSince1970 * 1000))
        let op = PendingOp(opID: opID, opType: type, ts: ts, body: body, tempIDs: temps, puts: puts, drops: drops)
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
