// The Tunes tab's list: a port of frontend/src/mytunespage/logic.js (filterAndSort and
// the lines around the list), held to frontend/src/mytunespage/logic.fixtures.json. What
// a search, the filters (status, type, instrument, when added, where played) and the
// sort leave on the list, so the app and the web's /my-tunes show the same tunes.

import Foundation

public enum MyTunesList {
    /// A tune on your list, with what the filters and sorts read.
    public struct Item: Sendable {
        public var tuneID: Int
        public var name: String
        public var type: String?
        public var status: String
        public var notes: String?
        /// The day it was added, "YYYY-MM-DD" (the first ten characters of created_date).
        public var addedDay: String?
        public var tunebookCount: Int?
        public var heardCount: Int?
        public var memberPlays: Int?
        /// The older name for memberPlays, still in offline caches.
        public var sessionPlays: Int?
        public var attendedPlays: Int?
        /// Per-instrument overrides, keyed by the instrument's name on your profile.
        public var instrumentStatus: [String: String]

        public init(
            tuneID: Int, name: String, type: String?, status: String, notes: String? = nil, addedDay: String? = nil,
            tunebookCount: Int? = nil, heardCount: Int? = nil, memberPlays: Int? = nil, sessionPlays: Int? = nil,
            attendedPlays: Int? = nil, instrumentStatus: [String: String] = [:]
        ) {
            self.tuneID = tuneID
            self.name = name
            self.type = type
            self.status = status
            self.notes = notes
            self.addedDay = addedDay
            self.tunebookCount = tunebookCount
            self.heardCount = heardCount
            self.memberPlays = memberPlays
            self.sessionPlays = sessionPlays
            self.attendedPlays = attendedPlays
            self.instrumentStatus = instrumentStatus
        }

        /// Plays at your sessions (spec 033), falling back to the older count.
        public var plays: Int { memberPlays ?? sessionPlays ?? 0 }
        public var attended: Int { attendedPlays ?? 0 }
    }

    public struct Instrument: Sendable, Equatable {
        public var name: String
        /// Auto instruments follow the tune's status; manual ones are a curated list.
        public var isAuto: Bool
        public init(name: String, isAuto: Bool) {
            self.name = name
            self.isAuto = isAuto
        }
    }

    public struct Filters: Sendable, Equatable {
        public var search = ""
        public var type = ""
        public var status = ""
        public var instrument = ""
        /// "member" (played at my sessions) or "attended" (played while I was there).
        public var rel = ""
        /// Added before `addedDate` (else on or after it).
        public var addedBefore = false
        public var addedDate = ""
        public init() {}

        /// How many of the panel's filters are set (the search and status have their own
        /// controls).
        public var activeCount: Int {
            [!type.isEmpty, !instrument.isEmpty, !rel.isEmpty, !addedDate.isEmpty].filter { $0 }.count
        }
    }

    public struct Sort: Sendable, Equatable {
        public var type = "alpha"
        public var descending = false
        public var type2: String?
        public var descending2 = false
        public init(type: String = "alpha", descending: Bool = false, type2: String? = nil, descending2: Bool = false) {
            self.type = type
            self.descending = descending
            self.type2 = type2
            self.descending2 = descending2
        }
    }

    public struct Row: Sendable {
        public var item: Item
        /// Not on the filtered instrument: kept, dimmed, and sorted below the matches.
        public var dimmed: Bool
        /// Here because its notation matched, not its name.
        public var abcOnly: Bool
    }

    /// The sort modes, as the web's droplist lists them.
    public static let sortModes: [(id: String, label: String)] = [
        ("alpha", "Name (a-z)"), ("popularity", "Popularity"), ("plays", "My plays"),
        ("attended", "Plays I attended"), ("heard", "Times heard"),
    ]

    public static func sortModeLabel(_ id: String) -> String {
        sortModes.first { $0.id == id }?.label ?? sortModes[0].label
    }

    /// An instrument's status for a tune: an override wins, else an auto instrument
    /// follows the tune's status and a manual one is untracked (nil).
    public static func instrumentStatus(_ item: Item, instruments: [Instrument], name: String) -> String? {
        guard let inst = instruments.first(where: { $0.name.lowercased() == name.lowercased() }) else { return nil }
        if let over = item.instrumentStatus[inst.name] { return over }
        return inst.isAuto ? item.status : nil
    }

    /// Accent- and smart-quote-insensitive contains (the web's AccentUtils fallback).
    static func fold(_ s: String) -> String {
        var out = String.UnicodeScalarView()
        for u in s.decomposedStringWithCanonicalMapping.unicodeScalars where !(0x300...0x36F).contains(u.value) {
            out.append(u == "\u{2018}" || u == "\u{2019}" ? "'" : u)
        }
        return String(out).lowercased()
    }

    static func compare(_ type: String, _ a: Item, _ b: Item) -> Int? {
        switch type {
        case "alpha":
            switch a.name.compare(b.name, locale: Locale(identifier: "en")) {
            case .orderedAscending: return -1
            case .orderedDescending: return 1
            case .orderedSame: return 0
            }
        case "popularity": return (a.tunebookCount ?? 0) - (b.tunebookCount ?? 0)
        case "heard": return (a.heardCount ?? 0) - (b.heardCount ?? 0)
        case "plays": return a.plays - b.plays
        case "attended": return a.attended - b.attended
        default: return nil
        }
    }

    /// The compare the sort asks for, or nil for an unknown mode (input order stands).
    static func sortFunction(_ sort: Sort) -> ((Item, Item) -> Int)? {
        guard compare(sort.type, Item(tuneID: 0, name: "", type: nil, status: ""), Item(tuneID: 0, name: "", type: nil, status: "")) != nil
        else { return nil }
        return { a, b in
            let r = (compare(sort.type, a, b) ?? 0) * (sort.descending ? -1 : 1)
            guard r == 0, let t2 = sort.type2 else { return r }
            return (compare(t2, a, b) ?? 0) * (sort.descending2 ? -1 : 1)
        }
    }

    /// The tunes that pass, sorted. `abcIDs`: tunes whose notation matched a note-shaped
    /// search (the server's answer); nil is name-only matching.
    public static func filterAndSort(
        _ all: [Item], filters f: Filters, sort: Sort, instruments: [Instrument], abcIDs: Set<Int>? = nil
    ) -> [Row] {
        var out: [Row] = []
        let needle = fold(f.search)
        let searchedID = f.search.isEmpty ? nil : MyTunesRules.extractTuneID(f.search)
        for item in all {
            var abcOnly = false
            if !f.search.isEmpty {
                let idMatch = searchedID != nil && item.tuneID == searchedID
                let nameMatch = fold(item.name).contains(needle)
                let notesMatch = fold(item.notes ?? "").contains(needle)
                let abcMatch = abcIDs?.contains(item.tuneID) ?? false
                if !idMatch && !nameMatch && !notesMatch && !abcMatch { continue }
                abcOnly = abcMatch && !idMatch && !nameMatch && !notesMatch
            }
            if !f.type.isEmpty && item.type != f.type { continue }
            if !f.addedDate.isEmpty {
                guard let added = item.addedDay, !added.isEmpty else { continue }
                if f.addedBefore ? added >= f.addedDate : added < f.addedDate { continue }
            }
            if f.rel == "member" && item.plays == 0 { continue }
            if f.rel == "attended" && item.attended == 0 { continue }
            if !f.instrument.isEmpty {
                let inst = instrumentStatus(item, instruments: instruments, name: f.instrument)
                let dimmed = inst == nil
                if !f.status.isEmpty && (inst ?? item.status) != f.status { continue }
                out.append(Row(item: item, dimmed: dimmed, abcOnly: abcOnly))
            } else {
                if !f.status.isEmpty && item.status != f.status { continue }
                out.append(Row(item: item, dimmed: false, abcOnly: abcOnly))
            }
        }
        let cmp = sortFunction(sort)
        if !f.instrument.isEmpty {
            // Swift's sort is stable, as Array.prototype.sort is.
            out.sort { a, b in
                if a.dimmed != b.dimmed { return !a.dimmed }
                return (cmp?(a.item, b.item) ?? 0) < 0
            }
        } else if let cmp {
            out.sort { cmp($0.item, $1.item) < 0 }
        }
        return out
    }

    static let statusLabels = ["want to learn": "To Learn", "learning": "Learning", "learned": "Learned"]

    public static func noResultsMessage(_ f: Filters) -> String {
        if !f.search.isEmpty, let id = MyTunesRules.extractTuneID(f.search) { return "No tune with ID \(id) found" }
        var parts = [f.type.isEmpty ? "tunes" : f.type.prefix(1).uppercased() + f.type.dropFirst() + "s"]
        if !f.search.isEmpty { parts.append("containing '\(f.search)'") }
        if !f.status.isEmpty { parts.append("in '\(statusLabels[f.status] ?? f.status)' status") }
        var message = "No " + parts[0]
        if parts.count > 1 { message += " " + parts.dropFirst().joined(separator: " ") }
        return message + " found"
    }

    public static func resultsCountText(_ rows: [Row], total: Int, filters: Filters) -> String {
        let n = rows.count
        if !filters.instrument.isEmpty {
            let on = rows.filter { !$0.dimmed }.count
            return "\(on) of \(n) tune\(n != 1 ? "s" : "") on \(filters.instrument)"
        }
        if n < total { return "Showing \(n) of \(total) tunes" }
        return "\(total) tune\(total != 1 ? "s" : "")"
    }

    /// The chip beside a tune: its type, or the count the list is sorted by.
    public static func typeBadgeLabel(_ item: Item, sortType: String) -> String {
        switch sortType {
        case "popularity": String(item.tunebookCount ?? 0)
        case "heard": String(item.heardCount ?? 0)
        case "plays": String(item.plays)
        case "attended": String(item.attended)
        default: item.type ?? ""
        }
    }

    public static func typeBadgeTitle(_ sortType: String) -> String {
        switch sortType {
        case "popularity": "TheSession.org tunebooks"
        case "heard": "Times heard"
        case "plays": "Times logged at my sessions"
        case "attended": "Times logged while I was there"
        default: ""
        }
    }
}
