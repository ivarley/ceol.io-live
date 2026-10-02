// A session's three tabs, filtered as the web filters them: a port of
// frontend/src/sessionpage/logic.js (filterAndSortTunes, resultsCountLabel,
// keepInstance, matchLoggedTunes, filterPeople), and of the tunebook roll-up in
// static/js/tunebook_status.js (resolve), held to the cases in
// frontend/tests/sessionpage.logic.test.js.

import Foundation

public enum SessionPage {
    // MARK: Tunes

    /// One of the session's tunes, with what the filters and sorts read.
    public struct Tune: Sendable {
        public var tuneID: Int
        public var name: String
        public var type: String?
        public var playCount: Int
        public var tunebookCount: Int
        /// Plays on nights you checked in to (signed in only).
        public var attendedPlayCount: Int

        public init(tuneID: Int, name: String, type: String?, playCount: Int, tunebookCount: Int, attendedPlayCount: Int = 0) {
            self.tuneID = tuneID
            self.name = name
            self.type = type
            self.playCount = playCount
            self.tunebookCount = tunebookCount
            self.attendedPlayCount = attendedPlayCount
        }
    }

    /// The web's "My Tunebook" droplist: off, show (colour without filtering), or one status.
    public enum MyStatus: String, CaseIterable, Sendable {
        case off = "", all, notOnList = "not on list", wantToLearn = "want to learn", learning, learned

        public var label: String {
            switch self {
            case .off: "Off"
            case .all: "Show my status"
            case .notOnList: "Not on my list"
            case .wantToLearn: "Want to learn"
            case .learning: "Learning"
            case .learned: "Learned"
            }
        }
    }

    public struct Filters: Sendable, Equatable {
        public var search = ""
        public var type = ""
        public var attended = false
        public var myStatus = MyStatus.off
        /// "all" or one of your instruments.
        public var myStatusInstrument = "all"
        public init() {}

        /// The web's filter button counts these as one: any of them set.
        public var active: Bool { !type.isEmpty || attended || myStatus != .off }
    }

    public enum SortMode: String, CaseIterable, Sendable {
        case alpha, session, everywhere

        public var label: String {
            switch self {
            case .alpha: "A–Z"
            case .session: "Played here"
            case .everywhere: "Everywhere"
            }
        }

        /// Alpha starts ascending; the counts start with the most.
        public var defaultDescending: Bool { self != .alpha }
    }

    public struct Sort: Sendable, Equatable {
        public var mode = SortMode.session
        public var descending = true
        public init(mode: SortMode = .session, descending: Bool = true) {
            self.mode = mode
            self.descending = descending
        }
    }

    /// The tunes that pass, sorted. `status` answers your status for a tune (nil until
    /// your tunebook has loaded, when the status filter lets everything through, as the
    /// web's does).
    public static func filterAndSortTunes(_ all: [Tune], filters f: Filters, sort: Sort, status: ((Int) -> String)? = nil) -> [Tune] {
        let needle = MyTunesList.fold(JSText.trim(f.search))
        let searchedID = needle.isEmpty ? nil : MyTunesRules.extractTuneID(f.search)
        var out = all.filter { t in
            if !needle.isEmpty {
                let idMatch = searchedID != nil && t.tuneID == searchedID
                if !idMatch && !MyTunesList.fold(t.name).contains(needle) { return false }
            }
            if !f.type.isEmpty && t.type != f.type { return false }
            if f.attended && t.attendedPlayCount <= 0 { return false }
            if f.myStatus != .off && f.myStatus != .all, let status, status(t.tuneID) != f.myStatus.rawValue { return false }
            return true
        }
        let sign = sort.descending ? -1 : 1
        switch sort.mode {
        case .alpha:
            out.sort { a, b in
                let r = a.name.compare(b.name, locale: Locale(identifier: "en"))
                return sort.descending ? r == .orderedDescending : r == .orderedAscending
            }
        case .session: out.sort { ($0.playCount - $1.playCount) * sign < 0 }
        case .everywhere: out.sort { ($0.tunebookCount - $1.tunebookCount) * sign < 0 }
        }
        return out
    }

    public static func resultsCountLabel(_ filtered: Int, _ total: Int) -> String {
        if filtered < total { return "Showing \(filtered) of \(total) tunes" }
        return "\(total) tune\(total != 1 ? "s" : "")"
    }

    // MARK: Your tunebook

    /// One tune on your list: its status, and per-instrument overrides.
    public struct TunebookEntry: Sendable {
        public var status: String
        public var instrumentStatus: [String: String]
        public init(status: String, instrumentStatus: [String: String] = [:]) {
            self.status = status
            self.instrumentStatus = instrumentStatus
        }
    }

    static let statusRank = ["want to learn": 1, "learning": 2, "learned": 3]

    /// Your status for a tune under `scope` ("all" or an instrument name): "not on list"
    /// with no entry; at two or more instruments "all" is the furthest along of them.
    public static func resolveStatus(_ entry: TunebookEntry?, instruments: [MyTunesList.Instrument], scope: String) -> String {
        guard let entry else { return MyStatus.notOnList.rawValue }
        // An override wins; else an auto instrument follows the tune's status and a
        // manual one is untracked.
        func one(_ inst: MyTunesList.Instrument) -> String? {
            entry.instrumentStatus[inst.name] ?? (inst.isAuto ? entry.status : nil)
        }
        if scope != "all" && instruments.count >= 2, let inst = instruments.first(where: { $0.name == scope }) {
            return one(inst) ?? MyStatus.notOnList.rawValue
        }
        if instruments.count < 2 { return entry.status }
        var best: String?
        for inst in instruments {
            if let st = one(inst), best == nil || (statusRank[st] ?? 0) > (statusRank[best!] ?? 0) { best = st }
        }
        return best ?? entry.status
    }

    // MARK: Logs

    public enum LogView: String, CaseIterable, Sendable {
        case logged, attended, all

        public var label: String { rawValue.capitalized }

        /// "Attended" means nothing signed out.
        public static func options(signedIn: Bool) -> [LogView] { signedIn ? [.logged, .attended, .all] : [.logged, .all] }
    }

    /// Whether a night stays on the list. A tune filter supersedes the view: every
    /// night a tune was played is a logged one.
    public static func keepInstance(tuneCount: Int, attended: Bool, view: LogView, tuneInstanceIDs: Set<Int>?, id: Int) -> Bool {
        if let tuneInstanceIDs { return tuneInstanceIDs.contains(id) }
        switch view {
        case .logged: return tuneCount > 0
        case .attended: return attended
        case .all: return true
        }
    }

    public struct LoggedTune: Sendable, Equatable {
        public var tuneID: Int
        public var name: String
        public var logCount: Int
        public init(tuneID: Int, name: String, logCount: Int) {
            self.tuneID = tuneID
            self.name = name
            self.logCount = logCount
        }
    }

    /// The tune search's suggestions: names containing the query, those starting with
    /// it first, then the most played here, then by name.
    public static func matchLoggedTunes(_ tunes: [LoggedTune], query: String, limit: Int = 8) -> [LoggedTune] {
        let q = MyTunesList.fold(JSText.trim(query))
        guard !q.isEmpty else { return [] }
        let matches = tunes.filter { MyTunesList.fold($0.name).contains(q) }
        return Array(matches.sorted { a, b in
            let ap = MyTunesList.fold(a.name).hasPrefix(q), bp = MyTunesList.fold(b.name).hasPrefix(q)
            if ap != bp { return ap }
            if a.logCount != b.logCount { return a.logCount > b.logCount }
            return a.name.compare(b.name, locale: Locale(identifier: "en")) == .orderedAscending
        }.prefix(limit))
    }

    // MARK: People

    public enum PeopleView: String, CaseIterable, Sendable {
        case members, visitors, archived
        public var label: String { rawValue.capitalized }
    }

    public struct Person: Sendable {
        public var name: String
        public var instruments: [String]
        public var relationship: String?
        public var archived: Bool
        public init(name: String, instruments: [String], relationship: String?, archived: Bool) {
            self.name = name
            self.instruments = instruments
            self.relationship = relationship
            self.archived = archived
        }
    }

    /// The indices of the people shown. Archived is its own view across members and
    /// visitors; a search covers everyone, archived included, so nobody hidden is
    /// unfindable (which is how duplicate people get made).
    public static func filterPeople(_ people: [Person], view: PeopleView, search: String) -> [Int] {
        let q = JSText.trim(search).lowercased()
        return people.indices.filter { i in
            let p = people[i]
            if !q.isEmpty {
                return p.name.lowercased().contains(q) || p.instruments.joined(separator: " ").lowercased().contains(q)
            }
            switch view {
            case .archived: return p.archived
            case .visitors: return p.relationship == "visitor" && !p.archived
            case .members: return p.relationship != "visitor" && !p.archived
            }
        }
    }
}
