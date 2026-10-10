// The tunes you and someone else both know or are learning: the rules of the web's
// /me/and/<id> page (templates/common_tunes.html), so the app's screen filters and
// sorts what GET /api/my-tunes/common/<id> returns the way that page does.

import Foundation

public enum CommonTunes {
    public struct Tune: Sendable, Equatable {
        public var tuneID: Int
        public var name: String
        public var type: String?
        public var tunebookCount: Int
        public init(tuneID: Int, name: String, type: String?, tunebookCount: Int) {
            self.tuneID = tuneID
            self.name = name
            self.type = type
            self.tunebookCount = tunebookCount
        }
    }

    /// By name, or by how many tunebooks hold it on thesession.org.
    public enum SortMode: String, CaseIterable, Sendable {
        case name, popular
        public var defaultDescending: Bool { self == .popular }
    }

    public struct Sort: Equatable, Sendable {
        public var mode: SortMode
        public var descending: Bool
        public init(mode: SortMode = .name, descending: Bool? = nil) {
            self.mode = mode
            self.descending = descending ?? mode.defaultDescending
        }
    }

    /// The tunes shown. A search matches the name, accents and curly quotes aside, or a
    /// tune's thesession.org number or link; `type` "" is every type.
    public static func filter(_ tunes: [Tune], search: String, type: String, sort: Sort) -> [Tune] {
        let q = MyTunesList.fold(JSText.trim(search))
        let id = MyTunesRules.extractTuneID(search)
        let kept = tunes.filter { t in
            if !q.isEmpty && !MyTunesList.fold(t.name).contains(q) && t.tuneID != id { return false }
            if !type.isEmpty && t.type != type { return false }
            return true
        }
        let en = Locale(identifier: "en")
        func byName(_ a: Tune, _ b: Tune) -> ComparisonResult { a.name.compare(b.name, locale: en) }
        return kept.sorted { a, b in
            switch sort.mode {
            case .name:
                let c = byName(a, b)
                return sort.descending ? c == .orderedDescending : c == .orderedAscending
            case .popular:
                if a.tunebookCount != b.tunebookCount {
                    return sort.descending ? a.tunebookCount > b.tunebookCount : a.tunebookCount < b.tunebookCount
                }
                return byName(a, b) == .orderedAscending
            }
        }
    }

    /// The types among the tunes, A to Z, for the type filter.
    public static func types(_ tunes: [Tune]) -> [String] {
        Set(tunes.compactMap(\.type)).sorted()
    }
}
