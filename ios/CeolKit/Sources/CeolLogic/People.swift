// Who's there, in the live logger: a port of frontend/src/people.js, held to
// frontend/src/people.fixtures.json. The loggers' colours and initials, whose colour a
// logged tune carries, who else is typing, and the attendance picker's groups.

import Foundation

public enum People {
    /// Player colours by the persisted per-session index (#rrggbb). No yellow: that's
    /// the insertion point's.
    public static let palette = ["#4f9dff", "#46d27a", "#ef8b3d", "#e0594b", "#b07cff", "#3fd0c9", "#ff8fab", "#9ab0c0"]

    public static func color(_ seq: Int) -> String {
        palette[((seq % palette.count) + palette.count) % palette.count]
    }

    /// "Sarah O'Connor" -> "SO"; one word -> its first two letters; nothing -> "?".
    public static func initials(_ name: String?) -> String {
        let words = JSText.trim(name ?? "").split(whereSeparator: { $0.unicodeScalars.allSatisfy { JSText.isWhitespace($0) } })
            .filter { !$0.isEmpty }
        guard let first = words.first else { return "?" }
        if words.count == 1 { return String(utf16Prefix(first, 2)).uppercased() }
        return (String(utf16Prefix(first, 1)) + String(utf16Prefix(words.last!, 1))).uppercased()
    }

    /// JS slice(0, n) on UTF-16 units, kept whole where a character is one unit.
    private static func utf16Prefix(_ s: Substring, _ n: Int) -> Substring {
        var units = 0
        var end = s.startIndex
        for c in s {
            units += c.utf16.count
            if units > n { break }
            end = s.index(after: end)
        }
        return s[s.startIndex..<end]
    }

    /// A row's logger colour index: only someone else's rows; the saved colour, else the
    /// live roster's for that person.
    public static func loggerColorIndex(_ r: JSONValue, me: Int?, roster: [JSONValue] = []) -> Int? {
        let by = r["logged_by_person_id"]?.intValue
        if let by, let me, by == me { return nil }
        if let c = r["logged_by_color"]?.intValue { return c }
        if let by, let p = roster.first(where: { $0["person_id"]?.intValue == by }) { return p["arrival_seq"]?.intValue }
        return nil
    }

    /// Everyone typing but me.
    public static func othersTyping(_ typers: [JSONValue]?, me: Int?) -> [JSONValue] {
        (typers ?? []).filter { $0["person_id"]?.intValue != me }
    }

    public struct Tiers: Sendable, Equatable {
        public var here: [JSONValue]
        public var roster: [JSONValue]
        public var archived: [JSONValue]
    }

    /// Checked in (even if archived), then not checked in, then the archived, who show
    /// only when the query finds them.
    public static func pickerTiers(_ people: [JSONValue]?, query: String?) -> Tiers {
        let q = JSText.trim(query ?? "").lowercased()
        let visible = (people ?? []).filter { p in
            let matches = q.isEmpty || (p["display_name"]?.stringValue ?? "").lowercased().contains(q)
            return matches && (!p["archived"].isTruthy || !q.isEmpty || p["attending"].isTruthy)
        }
        let away = visible.filter { !$0["attending"].isTruthy }
        return Tiers(
            here: visible.filter { $0["attending"].isTruthy },
            roster: away.filter { !$0["archived"].isTruthy },
            archived: away.filter { $0["archived"].isTruthy })
    }

    /// "Mary Kate Quinn" -> ("Mary", "Kate Quinn").
    public static func splitName(_ query: String?) -> (first: String, last: String) {
        let parts = JSText.trim(query ?? "").split(whereSeparator: { $0.unicodeScalars.allSatisfy { JSText.isWhitespace($0) } }).map(String.init)
        return (parts.first ?? "", parts.dropFirst().joined(separator: " "))
    }

    // MARK: - Someone else's change, said in a line

    public static let maxActivity = 3

    /// What the actor did: "added The Kesh", "ended a set"; nil for an op not worth a line.
    public static func remoteLabel(_ d: JSONValue) -> String? {
        let rec = d["record"]
        let n = rec?["name"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 }
            ?? (rec?["tune_id"].isTruthy == true ? "#\(rec?["tune_id"]?.intValue.map(String.init) ?? "")" : "a tune")
        func count(_ key: String) -> Int { d[key]?.arrayValue?.count ?? 0 }
        func plural(_ c: Int) -> String { "\(c) tune\(c == 1 ? "" : "s")" }
        let person = d["person"]?["display_name"]?.stringValue
        let hasPerson = d["person"].isTruthy
        switch d["op_type"]?.stringValue {
        case "add_tune": return "added \(n)"
        case "corroborate": return "also logged \(n)"
        case "change_tune": return "edited \(n)"
        case "remove_tune": return "removed \(n)"
        case "move_tunes": return "moved \(plural(count("moved_ids")))"
        case "remove_tunes": return "removed \(plural(count("records")))"
        case "restore_tunes": return "restored \(plural(count("records")))"
        case "set_break": return d["removed"].isTruthy ? "removed a break" : "ended a set"
        case "attribute_set_starter": return hasPerson ? "set \(person ?? "") as starting a set" : "cleared a set starter"
        case "set_confidence": return "confirmed \(n)"
        case "attendance_add": return hasPerson ? "checked in \(person ?? "")" : "updated attendance"
        case "attendance_create_person": return hasPerson ? "added \(person ?? "")" : "added a player"
        case "attendance_remove": return hasPerson ? "checked out \(person ?? "")" : "updated attendance"
        case "edit_notes": return "edited the notes"
        case "set_date":
            // Say which of the two edits actually happened.
            let movedDate = !d["previous_date"].isNullish && d["date"] != d["previous_date"]
            let movedTimes =
                (d["start_time"] != nil && d["start_time"] != d["previous_start_time"])
                || (d["end_time"] != nil && d["end_time"] != d["previous_end_time"])
            let when = HomeRules.instanceTimeLabel(start: d["start_time"]?.stringValue, end: d["end_time"]?.stringValue)
            let date = d["session_date"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 }
            if movedDate && movedTimes, let date { return "re-dated this log to \(date)\(when.isEmpty ? "" : ", \(when)")" }
            if movedDate { return date.map { "re-dated this log to \($0)" } ?? "re-dated this log" }
            if movedTimes { return when.isEmpty ? "cleared this log's time" : "set this log's time to \(when)" }
            return "re-dated this log"
        case "set_name":
            if let name = d["instance_name"]?.stringValue, !name.isEmpty { return "named this log \"\(name)\"" }
            return "cleared this log's name"
        default: return nil
        }
    }

    /// The whole line, or nil. My own changes are skipped while I edit; watching, every
    /// change shows (even mine, from another window).
    public static func activityText(_ d: JSONValue, me: Int?, viewing: Bool) -> String? {
        guard let actor = d["actor"], let who = actor["person_id"]?.intValue else { return nil }
        if !viewing && who == me { return nil }
        guard let label = remoteLabel(d) else { return nil }
        let name = actor["name"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 } ?? "Someone"
        return "\(name) \(label)"
    }
}
