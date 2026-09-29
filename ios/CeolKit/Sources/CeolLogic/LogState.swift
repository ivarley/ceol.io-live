// The live logger's pure state rules — a port of frontend/src/logstate.js: how records
// order, how they split into sets, where the insertion cursor can stand and what
// position a new row gets, how offline ops re-anchor on replay, when an add collapses
// into an existing row, and how local and server search results merge. Two clients
// that disagree on any of this show two different logs for the same session.
// Cases and the exact rules: frontend/src/logstate.fixtures.json.
//
// Records are the server's own JSON objects (session_instance_tune_id, order_position,
// record_type, deleted, tune_id, name, tune_type, and _temp on optimistic rows), kept
// as JSONValue so a record passes through with every field it arrived with. Where the
// JS branches on a value's JS type or truthiness, so does this.

import Foundation

public typealias LogRecord = JSONValue

extension JSONValue {
    /// session_instance_tune_id, as a RecordID.
    public var recordID: RecordID? { RecordID(self["session_instance_tune_id"]) }
    var orderPosition: String? { self["order_position"]?.stringValue }
    public var isBreak: Bool { self["record_type"] == .string("break") }
}

/// Where the insertion cursor stands (the JS `insertAfterId`): the end of the log,
/// after a tune, at the start of a tune's set, or a new set in the gap before a tune.
public enum Cursor: Hashable, Sendable {
    case end
    case after(RecordID)
    case before(RecordID)
    case newSet(RecordID)
}

/// One set: its tunes in order, and the break that closes it (nil for the open set).
public struct LogSegment: Sendable {
    public var tunes: [LogRecord]
    public var breakAfter: RecordID?

    public init(tunes: [LogRecord], breakAfter: RecordID?) {
        self.tunes = tunes
        self.breakAfter = breakAfter
    }
}

public enum LogState {

    // MARK: - Op timestamps

    /// Monotonic op timestamps (spec §G): queued ops replay sorted by ts, so two ops
    /// must never share one, even when the clock hasn't advanced or stepped back.
    /// The JS keeps this in module state; here it is a value the logger owns.
    public struct OpClock: Sendable, Equatable, Codable {
        public private(set) var last: Int64 = 0

        public init() {}

        /// max(now, last + 1), with `now` in milliseconds.
        public mutating func next(now: Int64) -> Int64 {
            last = max(now, last + 1)
            return last
        }
    }

    // MARK: - Ordering & segmentation

    /// Non-deleted records (tunes and breaks) by order_position, a STABLE sort in
    /// UTF-16 order. A record without a string position compares equal to anything.
    public static func computeOrdered(_ records: [LogRecord]) -> [LogRecord] {
        records.filter { !$0["deleted"].isTruthy }
            .enumerated()
            .sorted { a, b in
                let c = compare(a.element.orderPosition, b.element.orderPosition)
                return c != 0 ? c < 0 : a.offset < b.offset
            }
            .map(\.element)
    }

    static func compare(_ a: String?, _ b: String?) -> Int {
        guard let a, let b else { return 0 }
        return JSText.less(a, b) ? -1 : JSText.less(b, a) ? 1 : 0
    }

    /// Split an ordered list into sets on 'break' records. Each set remembers the break
    /// that ends it; a leading break, or one after an empty set, attaches to nothing.
    public static func segmentByBreaks(_ ordered: [LogRecord]) -> [LogSegment] {
        var out: [LogSegment] = []
        var cur: [LogRecord] = []
        for r in ordered {
            if r.isBreak {
                if !cur.isEmpty {
                    out.append(LogSegment(tunes: cur, breakAfter: r.recordID))
                    cur = []
                }
            } else {
                cur.append(r)
            }
        }
        if !cur.isEmpty { out.append(LogSegment(tunes: cur, breakAfter: nil)) }
        return out
    }

    public static func setsOf(_ segments: [LogSegment]) -> [[LogRecord]] { segments.map(\.tunes) }

    public static func tunesOf(_ ordered: [LogRecord]) -> [LogRecord] { ordered.filter { !$0.isBreak } }

    // MARK: - Set labels

    /// "Reel" -> "Reels", "Waltz" -> "Waltzes": 'es' after s, z, ch, sh or x (any case).
    /// nil and "" pass through.
    public static func pluralType(_ ty: String?) -> String? {
        guard let ty, !ty.isEmpty else { return ty }
        let lower = ty.lowercased()
        let es = ["s", "z", "ch", "sh", "x"].contains { lower.hasSuffix($0) }
        return ty + (es ? "es" : "s")
    }

    /// The set's shared pluralized type, "Mixed" when it spans types (compared
    /// case-sensitively), "Unknown" when no tune is matched.
    public static func setLabel(_ setTunes: [LogRecord]) -> String {
        var types: [String] = []
        for t in setTunes {
            guard let ty = t["tune_type"]?.stringValue, !ty.isEmpty, !types.contains(ty) else { continue }
            types.append(ty)
        }
        if types.isEmpty { return "Unknown" }
        if types.count > 1 { return "Mixed" }
        return pluralType(types[0])!
    }

    // MARK: - Positioning

    /// The largest order_position across ALL records, deleted and temp included; "".
    public static func maxPos(_ records: [LogRecord]) -> String {
        var m = ""
        for r in records {
            if let p = r.orderPosition, !p.isEmpty, JSText.less(m, p) { m = p }
        }
        return m
    }

    /// Server anchors and the provisional order_position for the cursor. A cursor
    /// whose anchor has vanished, or a newSet cursor, appends.
    public static func cursorPos(_ cursor: Cursor, ordered: [LogRecord], allRecords: [LogRecord])
        -> (afterID: RecordID?, beforeID: RecordID?, position: String)
    {
        let append = { (nil as RecordID?, nil as RecordID?, FracIndex.generateAppend(maxPos(allRecords))) }
        switch cursor {
        case .end, .newSet:
            return append()
        case .before(let id):
            guard let idx = ordered.firstIndex(where: { $0.recordID == id }) else { return append() }
            let x = ordered[idx].orderPosition
            let prev = idx > 0 ? ordered[idx - 1].orderPosition : nil
            return (nil, id, FracIndex.optimisticBetween(prev, x))
        case .after(let id):
            guard let idx = ordered.firstIndex(where: { $0.recordID == id }) else { return append() }
            let before = ordered[idx].orderPosition
            let after = idx + 1 < ordered.count ? ordered[idx + 1].orderPosition : nil
            return (id, nil, FracIndex.optimisticBetween(before, after))
        }
    }

    // MARK: - Anchor remapping (offline replay)

    /// Replace temp ids in an op payload with their real server ids. Unresolved
    /// anchors fall back to null (append); an unresolved record_id target means the row
    /// never persisted, so the op is skipped. A record_ids list keeps what resolves,
    /// drops what never persisted, and skips the op if nothing is left. Absent keys
    /// stay absent. Returns a copy.
    public static func remapAnchors(_ payload: [String: JSONValue], tempToReal: [String: JSONValue])
        -> (payload: [String: JSONValue], skip: Bool)
    {
        var p = payload
        func tempKey(_ v: JSONValue?) -> String? {
            if case .string(let s)? = v, s.hasPrefix("temp-") { return s }
            return nil
        }
        func fixAnchor(_ v: JSONValue) -> JSONValue {
            guard let key = tempKey(v) else { return v }
            return tempToReal[key] ?? .null
        }
        if let v = p["after_record_id"] { p["after_record_id"] = fixAnchor(v) }
        if let v = p["before_record_id"] { p["before_record_id"] = fixAnchor(v) }
        if let key = tempKey(p["record_id"]) {
            guard let real = tempToReal[key], !real.isNull else { return (p, true) }
            p["record_id"] = real
        }
        if case .array(let ids)? = p["record_ids"] {
            var kept: [JSONValue] = []
            for id in ids {
                if let key = tempKey(id) {
                    if let real = tempToReal[key], !real.isNull { kept.append(real) }
                } else {
                    kept.append(id)
                }
            }
            p["record_ids"] = .array(kept)
            if !ids.isEmpty && kept.isEmpty { return (p, true) }
        }
        return (p, false)
    }

    // MARK: - Name normalization & matching

    /// Drop a leading lowercase "the" followed by whitespace (JS /^the\s+/).
    public static func stripThe(_ s: String) -> String {
        let scalars = Array(s.unicodeScalars)
        guard scalars.count > 3, scalars[0] == "t", scalars[1] == "h", scalars[2] == "e",
            JSText.isWhitespace(scalars[3])
        else { return s }
        var i = 3
        while i < scalars.count && JSText.isWhitespace(scalars[i]) { i += 1 }
        var out = String.UnicodeScalarView()
        out.append(contentsOf: scalars[i...])
        return String(out)
    }

    /// The server matcher's normalization (normalize_quotes + unaccent + lower): smart
    /// quotes folded, NFD with combining marks (U+0300-U+036F) removed, JS trim, lower.
    /// NFD, not NFKD: a ligature survives. Keeps "the" (see stripThe).
    public static func normName(_ s: String?) -> String {
        var folded = String.UnicodeScalarView()
        for u in (s ?? "").unicodeScalars {
            switch u.value {
            case 0x2018, 0x2019, 0x201B, 0x02BC, 0x2032, 0x0060, 0x00B4: folded.append("'")
            case 0x201C, 0x201D, 0x201E, 0x2033, 0x00AB, 0x00BB: folded.append("\"")
            default: folded.append(u)
            }
        }
        var stripped = String.UnicodeScalarView()
        for u in String(folded).decomposedStringWithCanonicalMapping.unicodeScalars
        where !(0x0300...0x036F).contains(u.value) {
            stripped.append(u)
        }
        return JSText.trim(String(stripped)).lowercased()
    }

    /// The existing tune a PURE APPEND would collapse into (the server's
    /// _find_corroboration_target): the same tune already live in the OPEN set — by
    /// tune_id when the add is linked, else by identical normName on an unlinked row.
    /// Skips temp and deleted rows. Returns that record, or nil.
    public static func openSetMergeTarget(_ payload: JSONValue, ordered: [LogRecord]) -> LogRecord? {
        let start = (ordered.lastIndex(where: \.isBreak).map { $0 + 1 }) ?? 0
        let wantID: JSONValue? = payload["tune_id"].isNullish ? nil : payload["tune_id"]
        let wantName = wantID == nil ? normName(payload["name"]?.stringValue ?? "") : nil
        for r in ordered[start...] {
            if r["record_type"] != .string("tune") || r["deleted"].isTruthy || r["_temp"].isTruthy { continue }
            if let wantID {
                if r["tune_id"] == wantID { return r }
            } else if let wantName, !wantName.isEmpty, !r["tune_id"].isTruthy,
                normName(r["name"]?.stringValue ?? "") == wantName
            {
                return r
            }
        }
        return nil
    }

    // MARK: - Search result merge

    /// Keep every shown LOCAL result in place, enriched with the server's
    /// in_session_tune and abc where the server sent them; append the server-only
    /// tunes below, each once. At most 8 rows.
    public static func mergeStable(_ localList: [JSONValue], _ serverList: [JSONValue]) -> [JSONValue] {
        var byID: [JSONValue: JSONValue] = [:]
        for r in serverList where !r["tune_id"].isNullish { byID[r["tune_id"]!] = r }
        var seen = Set(localList.compactMap { $0["tune_id"] })
        let merged: [JSONValue] = localList.map { r in
            guard let id = r["tune_id"], let s = byID[id], var o = r.objectValue else { return r }
            for key in ["in_session_tune", "abc"] {
                let value = s[key].isNullish ? r[key] : s[key]
                o[key] = value  // nil removes the key, as JSON drops `undefined`
            }
            return .object(o)
        }
        var extra: [JSONValue] = []
        for r in serverList {
            guard let id = r["tune_id"], !id.isNull, !seen.contains(id) else { continue }
            seen.insert(id)
            extra.append(r)
        }
        return Array((merged + extra).prefix(8))
    }

    // MARK: - Insertion-cursor slots (keyboard nav)

    /// Every cursor position, top to bottom, matching the seams the logger renders:
    /// each set's start, after each tune (not temp rows), the open set's end (even
    /// after a temp row — the end needs no anchor), a new set in each gap, and the
    /// closed end.
    public static func computeCursorSlots(_ segments: [LogSegment], endIsOpen: Bool, hasOrdered: Bool) -> [Cursor] {
        var slots: [Cursor] = []
        for (si, seg) in segments.enumerated() {
            guard let first = seg.tunes.first?.recordID else { continue }
            slots.append(.before(first))
            for (ti, r) in seg.tunes.enumerated() {
                let openLast = endIsOpen && si == segments.count - 1 && ti == seg.tunes.count - 1
                if openLast {
                    slots.append(.end)
                } else if !r["_temp"].isTruthy, let id = r.recordID {
                    slots.append(.after(id))
                }
            }
            if si < segments.count - 1, seg.breakAfter != nil, let next = segments[si + 1].tunes.first?.recordID {
                slots.append(.newSet(next))
            }
        }
        if hasOrdered && !endIsOpen { slots.append(.end) }
        return slots
    }

    /// The seam key a cursor resolves to: "end", "inter:<id>", "start:<id>", "after:<id>".
    public static func seamKey(for cursor: Cursor) -> String {
        switch cursor {
        case .end: return "end"
        case .newSet(let id): return "inter:\(label(id))"
        case .before(let id): return "start:\(label(id))"
        case .after(let id): return "after:\(label(id))"
        }
    }

    static func label(_ id: RecordID) -> String {
        switch id {
        case .server(let n): return String(n)
        case .temp(let s): return s
        }
    }

    public enum SeamAction: Equatable, Sendable {
        case join(breakID: RecordID)
        case split(tuneID: Int)
    }

    /// What Enter does on a seam: a between-sets seam joins the two sets on the break
    /// between them; an after-tune seam inside a set (a server id, not the set's last
    /// tune) splits there. Everything else has no action.
    public static func seamAction(for cursor: Cursor, segments: [LogSegment]) -> SeamAction? {
        switch cursor {
        case .newSet(let id):
            for i in 0..<max(0, segments.count - 1) {
                if segments[i + 1].tunes.first?.recordID == id, let br = segments[i].breakAfter {
                    return .join(breakID: br)
                }
            }
            return nil
        case .after(.server(let n)):
            for seg in segments {
                if let idx = seg.tunes.firstIndex(where: { $0.recordID == .server(n) }) {
                    return idx < seg.tunes.count - 1 ? .split(tuneID: n) : nil
                }
            }
            return nil
        default:
            return nil
        }
    }

    // MARK: - Input history (filter box and search box recall)

    /// Push a used query onto an MRU list: trimmed, any earlier copy dropped, appended
    /// as newest. Blank is ignored.
    public static func rememberInHistory(_ hist: inout [String], _ q: String?) {
        let s = JSText.trim(q ?? "")
        guard !s.isEmpty else { return }
        if let i = hist.firstIndex(of: s) { hist.remove(at: i) }  // the first copy only, as indexOf/splice
        hist.append(s)
    }

    /// Step through history (oldest to newest). `pos` nil is the live draft. dir < 0 is
    /// older (Up); otherwise newer (Down). nil when the move isn't possible; newer past
    /// the newest returns to an empty draft.
    public static func historyStep(_ hist: [String], pos: Int?, dir: Double) -> (pos: Int?, value: String)? {
        let n = hist.count
        if n == 0 { return nil }
        if dir < 0 {
            let next = pos.map { max(0, $0 - 1) } ?? n - 1
            return (next, hist[next])
        }
        guard let pos else { return nil }
        if pos >= n - 1 { return (nil, "") }
        return (pos + 1, hist[pos + 1])
    }

    // MARK: - Applying a server op (spec 024)
    //
    // Ports of logstate.js recordChanges / metaChanges: the data half of the logger's
    // applyOp, so the web and the app apply every referee op the same way.

    /// The records an op puts (insert or replace, by session_instance_tune_id) and the ids
    /// it drops, as JSON so no field is lost. Put before drop, in the order given.
    public struct RecordChanges: Sendable, Equatable {
        public var puts: [JSONValue] = []
        public var drops: [JSONValue] = []
    }

    public static func recordChanges(_ d: JSONValue?) -> RecordChanges {
        var out = RecordChanges()
        func put(_ r: JSONValue?) { if let r, !r.isNull { out.puts.append(r) } }
        guard let d else { return out }
        switch d["op_type"]?.stringValue {
        case "attribute_set_starter", "restore_tunes":
            for r in d["records"]?.arrayValue ?? [] { put(r) }
        case "add_tune", "change_tune", "set_confidence", "corroborate":
            put(d["record"])
        case "set_break":
            if d["removed"].isTruthy { out.drops.append(d["record_id"] ?? .null) } else { put(d["record"]) }
        case "remove_tune":
            if let r = d["record"], r.isTruthy {
                if r["deleted"].isTruthy { out.drops.append(r["session_instance_tune_id"] ?? .null) } else { put(r) }
            }
        case "move_tunes":
            for r in d["records"]?.arrayValue ?? [] { put(r) }
            for id in d["removed_break_ids"]?.arrayValue ?? [] { out.drops.append(id) }
        case "remove_tunes":
            for r in d["records"]?.arrayValue ?? [] { out.drops.append(r["session_instance_tune_id"] ?? .null) }
        default:
            break
        }
        return out
    }

    /// The night's own fields an op sets (notes, date and times, name, complete): only the
    /// keys it changes.
    public static func metaChanges(_ d: JSONValue?) -> [String: JSONValue] {
        guard let d else { return [:] }
        func text(_ k: String) -> JSONValue { d[k].isTruthy ? d[k]! : .string("") }
        switch d["op_type"]?.stringValue {
        case "edit_notes":
            return ["notes": text("notes")]
        case "set_date":
            var out: [String: JSONValue] = [:]
            if d["date"].isTruthy { out["instance_date"] = d["date"] }
            if d["session_date"].isTruthy { out["session_date"] = d["session_date"] }
            if d.objectValue?["start_time"] != nil { out["start_time"] = text("start_time") }
            if d.objectValue?["end_time"] != nil { out["end_time"] = text("end_time") }
            return out
        case "set_name":
            return ["instance_name": text("instance_name")]
        case "mark_complete":
            return ["log_complete": .bool(true)]
        case "mark_incomplete":
            return ["log_complete": .bool(false)]
        default:
            return [:]
        }
    }
}
