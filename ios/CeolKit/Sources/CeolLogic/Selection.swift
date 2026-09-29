// The live logger's selection mode (spec 029): a port of frontend/src/selection.js,
// held to frontend/src/selection.fixtures.json. Which rows a drag lifts, where they may
// land, the positions a move shows before the server answers, copy and paste, range
// select and select-all.
//
// The drop rules are where the two clients could quietly disagree: a target that is a
// no-op for the block must not be offered, and the optimistic keys must follow the
// server's rule (the destination gap is found with the moving rows left out), or the
// rows jump when the answer comes back.

import Foundation

public enum Selection {
    /// What a drag lifts: the tunes, the records they span (with any breaks between
    /// them, which travel along), and how many sets that is.
    public struct DragBlock: Sendable, Equatable {
        public var tuneIDs: [RecordID]
        public var recordIDs: [RecordID]
        public var setCount: Int
    }

    /// A place a block can land, with move_tunes' anchors. `key` extends the seam
    /// vocabulary with "top-new" and "end-new", which only a drag offers.
    public struct DropTarget: Sendable, Equatable, Hashable {
        public var key: String
        public var afterID: RecordID?
        public var beforeID: RecordID?
        public var newSet: Bool
    }

    /// A move as it shows before the server answers: new positions for the moving
    /// records, and where a new set needs a temporary break on either side.
    public struct Move: Sendable, Equatable {
        public var positions: [(RecordID, String)]
        public var tempBreakBefore: String?
        public var tempBreakAfter: String?

        public static func == (a: Move, b: Move) -> Bool {
            a.positions.map(\.0) == b.positions.map(\.0) && a.positions.map(\.1) == b.positions.map(\.1)
                && a.tempBreakBefore == b.tempBreakBefore && a.tempBreakAfter == b.tempBreakAfter
        }
    }

    // MARK: - Drag

    /// The grabbed tune plus its contiguous run of selected tunes (breaks don't
    /// interrupt a run), and the breaks inside the run's span. An unselected row drags
    /// alone. nil: not draggable (unknown, optimistic or being removed).
    public static func dragBlock(_ ordered: [LogRecord], selected: Set<RecordID>, grabbed: RecordID) -> DragBlock? {
        let tunes = ordered.filter { $0["record_type"] == "tune" }
        guard let gi = tunes.firstIndex(where: { $0.recordID == grabbed }),
            !tunes[gi]["_temp"].isTruthy, !tunes[gi]["_removing"].isTruthy
        else { return nil }
        var lo = gi
        var hi = gi
        if selected.contains(grabbed) {
            while lo > 0, let id = tunes[lo - 1].recordID, selected.contains(id) { lo -= 1 }
            while hi < tunes.count - 1, let id = tunes[hi + 1].recordID, selected.contains(id) { hi += 1 }
        }
        let tuneIDs = tunes[lo...hi].compactMap(\.recordID)
        guard let from = ordered.firstIndex(where: { $0.recordID == tuneIDs.first }),
            let to = ordered.firstIndex(where: { $0.recordID == tuneIDs.last })
        else { return nil }
        let span = ordered[from...to]
        return DragBlock(
            tuneIDs: tuneIDs, recordIDs: span.compactMap(\.recordID),
            setCount: 1 + span.filter { $0["record_type"] == "break" }.count)
    }

    /// Every place the block may land, top to bottom, leaving out the ones that would
    /// change nothing.
    public static func dropTargets(
        _ ordered: [LogRecord], segments: [LogSegment], endIsOpen: Bool, block blockIDs: [RecordID]
    ) -> [DropTarget] {
        let block = Set(blockIDs)
        var idx: [RecordID: Int] = [:]
        for (i, r) in ordered.enumerated() { if let id = r.recordID, idx[id] == nil { idx[id] = i } }
        func neighborInBlock(_ id: RecordID, _ dir: Int) -> Bool {
            guard let i = idx[id], ordered.indices.contains(i + dir), let nb = ordered[i + dir].recordID else { return false }
            return block.contains(nb)
        }
        // Is the block a whole set (or run of sets)? The record above it is a break or
        // the start of the log.
        let fi = ordered.firstIndex { $0.recordID.map(block.contains) ?? false } ?? -1
        let startsAtSetBoundary = fi <= 0 || ordered[fi - 1]["record_type"] == "break"

        var out: [DropTarget] = []
        func add(_ key: String, _ after: RecordID?, _ before: RecordID?, _ newSet: Bool) {
            out.append(DropTarget(key: key, afterID: after, beforeID: before, newSet: newSet))
        }
        guard let firstTune = segments.first?.tunes.first?.recordID else { return out }
        if !block.contains(firstTune) { add("top-new", nil, firstTune, true) }

        for (si, seg) in segments.enumerated() {
            guard let segFirst = seg.tunes.first?.recordID else { continue }
            if !block.contains(segFirst) && !neighborInBlock(segFirst, -1) {
                add("start:\(key(segFirst))", nil, segFirst, false)
            }
            for (ti, r) in seg.tunes.enumerated() {
                if r["_temp"].isTruthy { continue }
                guard let id = r.recordID else { continue }
                if endIsOpen && si == segments.count - 1 && ti == seg.tunes.count - 1 {
                    // The open end: weld onto the open set, or land as a set below it.
                    if !block.contains(id) {
                        add("end", nil, nil, false)
                        if !blockEndsLog(ordered, block) || !startsAtSetBoundary { add("end-new", nil, nil, true) }
                    }
                    continue
                }
                if !block.contains(id) && !neighborInBlock(id, 1) { add("after:\(key(id))", id, nil, false) }
            }
            if si < segments.count - 1, seg.breakAfter != nil, let nextFirst = segments[si + 1].tunes.first?.recordID {
                // A no-op: the block is exactly the set(s) ending right above this gap.
                let lastAbove = seg.tunes.last?.recordID
                let noop = lastAbove.map(block.contains) == true && startsAtSetBoundary
                if !block.contains(nextFirst) && !noop { add("inter:\(key(nextFirst))", nil, nextFirst, true) }
            }
        }
        if !endIsOpen {
            // A closed end: landing there starts a new set.
            if let last = ordered.last?.recordID, block.contains(last) {} else { add("end", nil, nil, true) }
        }
        return out
    }

    static func blockEndsLog(_ ordered: [LogRecord], _ block: Set<RecordID>) -> Bool {
        guard let last = ordered.last(where: { $0["record_type"] == "tune" })?.recordID else { return false }
        return block.contains(last)
    }

    /// A seam key's id part, as JS prints it.
    static func key(_ id: RecordID) -> String {
        switch id {
        case .server(let n): String(n)
        case .temp(let s): s
        }
    }

    // MARK: - Optimistic move

    /// The server's key assignment, previewed: the destination gap found with the
    /// moving rows left out, keys handed out in the block's order.
    public static func optimisticMove(
        _ ordered: [LogRecord], allRecords: [LogRecord], block blockIDs: [RecordID], target: DropTarget
    ) -> Move {
        let block = Set(blockIDs)
        let inBlock = { (r: LogRecord) in r.recordID.map(block.contains) ?? false }
        let rest = ordered.filter { !inBlock($0) }
        var predPos: String?
        var succPos: String?
        var predRec: LogRecord?
        var succRec: LogRecord?
        if let before = target.beforeID, let i = rest.firstIndex(where: { $0.recordID == before }) {
            succRec = rest[i]
            succPos = rest[i]["order_position"]?.stringValue
            predRec = i > 0 ? rest[i - 1] : nil
            predPos = predRec?["order_position"]?.stringValue
        } else if let after = target.afterID, let i = rest.firstIndex(where: { $0.recordID == after }) {
            predRec = rest[i]
            predPos = rest[i]["order_position"]?.stringValue
            succRec = i + 1 < rest.count ? rest[i + 1] : nil
            succPos = succRec?["order_position"]?.stringValue
        } else {
            // Append: after everything else ever placed (temp and deleted rows too).
            for r in allRecords where !inBlock(r) {
                if let p = r["order_position"]?.stringValue, !p.isEmpty, predPos.map({ JSText.less($0, p) }) ?? true {
                    predPos = p
                }
            }
            predRec = rest.last
        }
        let needBefore = target.newSet && predRec?["record_type"] == "tune"
        let needAfter = target.newSet && succRec?["record_type"] == "tune"
        var move = Move(positions: [], tempBreakBefore: nil, tempBreakAfter: nil)
        var prev = predPos
        if needBefore {
            prev = FracIndex.optimisticBetween(prev, succPos)
            move.tempBreakBefore = prev
        }
        for r in ordered where inBlock(r) {
            let p = FracIndex.optimisticBetween(prev, succPos)
            prev = p
            if let id = r.recordID { move.positions.append((id, p)) }
        }
        if needAfter { move.tempBreakAfter = FracIndex.optimisticBetween(prev, succPos) }
        return move
    }

    // MARK: - Clipboard

    /// A tune on the clipboard. The rich form (our own copy) keeps the link and type.
    public struct ClipTune: Sendable, Equatable {
        public var tuneID: Int?
        public var name: String
        public var tuneType: String?
        public init(tuneID: Int?, name: String, tuneType: String? = nil) {
            self.tuneID = tuneID
            self.name = name
            self.tuneType = tuneType
        }
    }

    public struct Copy: Sendable, Equatable {
        /// Lines are sets, commas are tunes (the old pill logger's format).
        public var text: String
        public var rich: [[ClipTune]]
    }

    public enum PasteKind: String, Sendable { case `internal`, json, text }

    /// The selected tunes by set, in log order; nil when nothing is selected.
    public static func serializeClipboard(_ segments: [LogSegment], selected: Set<RecordID>) -> Copy? {
        var rich: [[ClipTune]] = []
        for seg in segments {
            let picked = seg.tunes.filter { $0.recordID.map(selected.contains) ?? false }
            guard !picked.isEmpty else { continue }
            rich.append(picked.map { t in
                let id = t["tune_id"]?.intValue
                let name = t["name"]?.stringValue ?? ""
                return ClipTune(
                    tuneID: id, name: !name.isEmpty ? name : (t["tune_id"].isTruthy ? "#\(id.map(String.init) ?? "")" : ""),
                    tuneType: t["tune_type"]?.stringValue)
            })
        }
        guard !rich.isEmpty else { return nil }
        return Copy(text: rich.map { $0.map(\.name).joined(separator: ", ") }.joined(separator: "\n"), rich: rich)
    }

    /// Clipboard text to a paste: our own last copy (links kept), the old logger's JSON
    /// pills, or plain text by lines and commas. nil: nothing to paste.
    public static func parseClipboard(_ text: String?, lastCopy: Copy?) -> (kind: PasteKind, sets: [[ClipTune]])? {
        let raw = JSText.trim(text ?? "")
        guard !raw.isEmpty else { return nil }
        if let lastCopy, text == lastCopy.text { return (.internal, lastCopy.rich) }
        if let parsed = try? JSONDecoder().decode(JSONValue.self, from: Data(raw.utf8)),
            let arr = parsed.arrayValue, let first = arr.first
        {
            func pill(_ p: JSONValue) -> ClipTune {
                let id = [p["tuneId"], p["tune_id"]].first { !$0.isNullish } ?? nil
                let name = [p["tuneName"], p["name"]].first { !$0.isNullish } ?? nil
                return ClipTune(tuneID: id?.intValue, name: name?.stringValue ?? "")
            }
            var sets: [[ClipTune]]?
            if first.arrayValue != nil {
                let inner = arr.map(\.arrayValue)
                if inner.allSatisfy({ $0 != nil }) { sets = inner.map { $0!.map(pill) } }
            } else {
                sets = [arr.map(pill)]
            }
            if let sets {
                let clean = sets.map { $0.filter { !$0.name.isEmpty || $0.tuneID != nil } }.filter { !$0.isEmpty }
                if !clean.isEmpty { return (.json, clean) }
            }
        }
        let sets = raw.split(separator: "\n", omittingEmptySubsequences: false)
            .map { line in
                line.split(separator: ",", omittingEmptySubsequences: false)
                    .map { JSText.trim(String($0)) }.filter { !$0.isEmpty }
                    .map { ClipTune(tuneID: nil, name: $0) }
            }
            .filter { !$0.isEmpty }
        return sets.isEmpty ? nil : (.text, sets)
    }

    // MARK: - Range and select-all

    /// The tunes between two, inclusive, either way, across breaks. A vanished anchor
    /// gives just the target; a vanished target, nothing.
    public static func rangeBetween(_ ordered: [LogRecord], anchor: RecordID?, target: RecordID) -> [RecordID] {
        let tunes = ordered.filter { $0["record_type"] == "tune" }
        guard let b = tunes.firstIndex(where: { $0.recordID == target }) else { return [] }
        guard let anchor, let a = tunes.firstIndex(where: { $0.recordID == anchor }) else { return [target] }
        return tunes[min(a, b)...max(a, b)].compactMap(\.recordID)
    }

    /// "Select all": every settled tune, or with a filter only the matching tunes (not
    /// their sets, or a bulk remove would take too much).
    public static func selectableIDs(_ segments: [LogSegment], filter: String? = nil) -> [RecordID] {
        let q = JSText.trim(filter ?? "")
        var out: [RecordID] = []
        for seg in segments {
            for t in seg.tunes where !t["_temp"].isTruthy && !t["_removing"].isTruthy {
                if q.isEmpty || LogState.normName(t["name"]?.stringValue ?? "").contains(LogState.normName(q)),
                    let id = t.recordID
                {
                    out.append(id)
                }
            }
        }
        return out
    }
}
