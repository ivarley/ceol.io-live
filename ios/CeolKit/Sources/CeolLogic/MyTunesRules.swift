// The Tunes tab's list rules — a port of the core of frontend/src/mytunespage/logic.js
// (filterAndSort): the learn-status segments, the type filter, and the search (a tune's
// name or your notes, accent- and case-insensitive, or its thesession.org id or link).
// Notation matches come from the server's catalogue search, as on the web. The web's
// other filters (instrument, date added, played-at) and sorts arrive with editing.

import Foundation

public enum MyTunesRules {
    /// The stored learn statuses, and the page's words for them.
    public enum Status: String, CaseIterable, Sendable {
        case wantToLearn = "want to learn"
        case learning
        case learned

        public var label: String {
            switch self {
            case .wantToLearn: return "To Learn"
            case .learning: return "Learning"
            case .learned: return "Learned"
            }
        }
    }

    public struct Entry: Sendable {
        public var tuneID: Int
        public var name: String
        public var type: String?
        public var status: String?
        public var notes: String?

        public init(tuneID: Int, name: String, type: String?, status: String?, notes: String?) {
            self.tuneID = tuneID
            self.name = name
            self.type = type
            self.status = status
            self.notes = notes
        }
    }

    /// The entries that pass, sorted by name (a case- and accent-insensitive compare, as
    /// the web's localeCompare does).
    public static func filter(
        _ entries: [Entry], status: Status?, type: String?, search: String
    ) -> [Entry] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        let needle = LogState.normName(query)
        let pastedID = extractTuneID(query)
        return entries.filter { e in
            if let status, e.status != status.rawValue { return false }
            if let type, !type.isEmpty, e.type != type { return false }
            guard !query.isEmpty else { return true }
            if let pastedID, pastedID == e.tuneID { return true }
            return LogState.normName(e.name).contains(needle) || LogState.normName(e.notes).contains(needle)
        }
        .sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending }
    }

    /// A tune id typed or pasted as a bare number or a thesession.org tune link.
    public static func extractTuneID(_ s: String) -> Int? {
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty, t.allSatisfy(\.isASCII), t.allSatisfy(\.isNumber) { return Int(t) }
        guard let r = t.range(of: "thesession.org/tunes/", options: .caseInsensitive) else { return nil }
        let digits = t[r.upperBound...].prefix { $0.isASCII && $0.isNumber }
        return Int(digits)
    }

    /// "42 tunes" / "Showing 3 of 42 tunes".
    public static func countText(shown: Int, total: Int) -> String {
        shown < total ? "Showing \(shown) of \(total) tunes" : "\(total) tune\(total == 1 ? "" : "s")"
    }
}
