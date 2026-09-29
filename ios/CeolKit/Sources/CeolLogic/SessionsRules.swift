// The sessions list's rules — a port of frontend/src/sessionsdir (logic.js and the
// filter in App.svelte): the five filters, the search, and where a session is.
//
// One deliberate difference: the web's search folds smart quotes and case; this also
// strips accents, on both sides (LogState.normName), so "maid" finds "Maíd".

import Foundation

public enum SessionsRules {
    /// The filters, in the web's order. Signed-out viewers get the last three.
    public enum Filter: String, CaseIterable, Sendable {
        case mine, visited, active, all, inactive

        public var label: String {
            switch self {
            case .mine: return "My Sessions"
            case .visited: return "Visited"
            case .active: return "All Active"
            case .all: return "All"
            case .inactive: return "Inactive"
            }
        }

        /// "3 sessions in your list".
        public var countNoun: String {
            switch self {
            case .mine: return "sessions in your list"
            case .visited: return "sessions you've visited"
            case .active: return "active sessions"
            case .all: return "sessions"
            case .inactive: return "inactive sessions"
            }
        }
    }

    public struct Entry: Sendable {
        public var name: String
        public var city: String?
        public var state: String?
        public var country: String?
        /// "YYYY-MM-DD" once the session has stopped (or will stop).
        public var terminationDate: String?
        public var isMember: Bool
        public var relationship: String?

        public init(
            name: String, city: String?, state: String?, country: String?, terminationDate: String?,
            isMember: Bool, relationship: String?
        ) {
            self.name = name
            self.city = city
            self.state = state
            self.country = country
            self.terminationDate = terminationDate
            self.isMember = isMember
            self.relationship = relationship
        }
    }

    /// Does a session pass the filter and the search? `today` is the viewer's local
    /// "YYYY-MM-DD": a session is active until its termination date arrives.
    public static func matches(_ e: Entry, filter: Filter, search: String, today: String) -> Bool {
        let passes: Bool =
            switch filter {
            case .mine: e.isMember
            case .visited: e.relationship == "visitor"
            case .active: e.terminationDate.map { $0 > today } ?? true
            case .all: true
            case .inactive: e.terminationDate.map { $0 <= today } ?? false
            }
        guard passes else { return false }
        let term = LogState.normName(search)
        guard !term.isEmpty else { return true }
        let place = [e.city, e.state, e.country].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", ")
        return LogState.normName(e.name).contains(term) || LogState.normName(place).contains(term)
    }

    /// Where a session is: "Austin, TX" to someone in the USA, "Galway, Ireland" to that
    /// same person. With no viewer country known, nothing is dropped.
    public static func locationLabel(city: String?, state: String?, country: String?, viewerCountry: String?) -> String {
        func norm(_ s: String?) -> String { (s ?? "").trimmingCharacters(in: .whitespaces).lowercased() }
        let mine = norm(viewerCountry)
        let same = !mine.isEmpty && norm(country) == mine
        let parts = [city, state, same ? nil : country].compactMap { $0 }.filter { !$0.isEmpty }
        return parts.isEmpty ? "Unknown" : parts.joined(separator: ", ")
    }

    // MARK: - The app's sort and country filter
    //
    // The web's Sessions page has only the five filters above. The app's drawer adds a
    // sort and a country, which a traveller wants and a long list needs.

    public enum Sort: String, CaseIterable, Sendable {
        case name, place, onNow

        public var label: String {
            switch self {
            case .name: return "Name"
            case .place: return "Place"
            case .onNow: return "On now first"
            }
        }
    }

    /// The countries in the list, most sessions first, then by name ("USA", "Ireland").
    public static func countries(_ entries: [Entry]) -> [String] {
        var counts: [String: (label: String, n: Int)] = [:]
        for e in entries {
            guard let c = e.country?.trimmingCharacters(in: .whitespaces), !c.isEmpty else { continue }
            let key = c.lowercased()
            counts[key] = (counts[key]?.label ?? c, (counts[key]?.n ?? 0) + 1)
        }
        return counts.values.sorted { $0.n != $1.n ? $0.n > $1.n : $0.label.localizedCaseInsensitiveCompare($1.label) == .orderedAscending }
            .map(\.label)
    }

    /// Whether a session is in `country` (case-insensitive; nil or empty is any).
    public static func inCountry(_ e: Entry, _ country: String?) -> Bool {
        guard let country, !country.isEmpty else { return true }
        return e.country?.trimmingCharacters(in: .whitespaces).lowercased() == country.lowercased()
    }

    /// Indices of `entries` in sort order. Name: case-insensitive. Place: country, state,
    /// city, then name. On now first: sessions on now (`onNow`), then by name. Ties keep
    /// the list's order.
    public static func sorted(_ entries: [Entry], by sort: Sort, onNow: (Int) -> Bool = { _ in false }) -> [Int] {
        func cmp(_ a: String?, _ b: String?) -> ComparisonResult {
            (a ?? "").localizedCaseInsensitiveCompare(b ?? "")
        }
        return entries.indices.sorted { i, j in
            let a = entries[i], b = entries[j]
            switch sort {
            case .name:
                return cmp(a.name, b.name) == .orderedAscending
            case .place:
                for (x, y) in [(a.country, b.country), (a.state, b.state), (a.city, b.city), (a.name, b.name)] {
                    let r = cmp(x, y)
                    if r != .orderedSame { return r == .orderedAscending }
                }
                return false
            case .onNow:
                if onNow(i) != onNow(j) { return onNow(i) }
                return cmp(a.name, b.name) == .orderedAscending
            }
        }
    }
}
