// The live logger's composer: a port of frontend/src/composer.js, held to
// frontend/src/composer.fixtures.json. The session's vocabulary as a match index, the
// unique exact match and the instant type-ahead over it, the set the cursor is building,
// the likely next tune, what Enter does with typed text, and what a server /match
// verdict does to a placeholder.
//
// Server match rows stay JSON (the fields /match and deep search send differ), so a row
// shown in the dropdown is exactly what the server said.

import Foundation

/// A tune the vocabulary knows.
public struct VocabTune: Sendable, Equatable, Hashable {
    public var tuneID: Int
    public var name: String
    public var tuneType: String?
    /// Found by its notation, not its name.
    public var abc = false
    /// The session's own name for it (session_tune.alias), when it has one.
    public var alias: String?
    /// As the session shows it: its alias, else the tune's name.
    public var displayName: String { alias ?? name }

    public init(tuneID: Int, name: String, tuneType: String?, abc: Bool = false) {
        self.tuneID = tuneID
        self.name = name
        self.tuneType = tuneType
        self.abc = abc
    }

    /// As the web holds it: {tune_id, name, tune_type[, abc: true]}.
    public var json: JSONValue {
        var o: [String: JSONValue] = [
            "tune_id": JSONValue(tuneID), "name": .string(name), "tune_type": tuneType.map(JSONValue.string) ?? .null,
        ]
        if abc { o["abc"] = true }
        return .object(o)
    }
}

/// The session's vocabulary, indexed for matching.
public struct VocabIndex: Sendable, Equatable {
    public struct Entry: Sendable, Equatable {
        public var tuneID: Int
        public var name: String
        public var tuneType: String?
        /// normName(name)
        public var nn: String
        public var aliases: [String]
        /// normAbc of every setting's notation.
        public var abc: String
        /// Vocabulary order: session plays first, then global popularity.
        public var idx: Int
    }

    /// normName(alias) -> tune ids
    public var alias: [String: [Int]] = [:]
    /// normName(name) and stripThe(normName(name)) -> tune ids
    public var name: [String: [Int]] = [:]
    public var byID: [Int: VocabTune] = [:]
    public var list: [Entry] = []
    /// The tune that usually follows each one here.
    public var next: [Int: VocabTune] = [:]
}

public enum Composer {
    // MARK: - The index

    /// From the vocabulary's known_tunes and known_aliases; nil when there's neither.
    public static func buildIndex(known: [JSONValue]?, aliases: [JSONValue]?) -> VocabIndex? {
        if known == nil && aliases == nil { return nil }
        var index = VocabIndex()
        func add(_ map: inout [String: [Int]], _ key: String, _ id: Int) {
            guard !key.isEmpty else { return }
            if !(map[key]?.contains(id) ?? false) { map[key, default: []].append(id) }
        }
        var at: [Int: Int] = [:]
        func ensure(_ id: Int, _ name: String, _ type: String?) -> Int {
            if let i = at[id] { return i }
            index.list.append(.init(tuneID: id, name: name, tuneType: type, nn: LogState.normName(name), aliases: [], abc: "", idx: 0))
            at[id] = index.list.count - 1
            return index.list.count - 1
        }
        for t in known ?? [] {
            guard let id = t["tune_id"]?.intValue, id != 0 else { continue }
            let name = t["name"]?.stringValue ?? ""
            let type = t["tune_type"]?.stringValue
            if let nx = t["next"], let nid = nx["tune_id"]?.intValue {
                index.next[id] = VocabTune(tuneID: nid, name: nx["name"]?.stringValue ?? "", tuneType: nx["tune_type"]?.stringValue)
            }
            index.byID[id] = VocabTune(tuneID: id, name: name, tuneType: type)
            index.byID[id]?.alias = t["alias"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 }
            let n = LogState.normName(name)
            add(&index.name, n, id)
            add(&index.name, LogState.stripThe(n), id)
            let i = ensure(id, name, type)
            if let abc = t["abc"]?.stringValue, !abc.isEmpty { index.list[i].abc = ABCQuery.normAbc(abc) }
            if let alias = t["alias"]?.stringValue, !alias.isEmpty {
                add(&index.alias, LogState.normName(alias), id)
                index.list[i].aliases.append(LogState.normName(alias))
            }
        }
        for a in aliases ?? [] {
            guard let id = a["tune_id"]?.intValue, id != 0, let alias = a["alias"]?.stringValue, !alias.isEmpty else { continue }
            add(&index.alias, LogState.normName(alias), id)
            let name = a["name"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 } ?? alias
            if index.byID[id] == nil { index.byID[id] = VocabTune(tuneID: id, name: name, tuneType: a["tune_type"]?.stringValue) }
            let i = ensure(id, name, a["tune_type"]?.stringValue)
            index.list[i].aliases.append(LogState.normName(alias))
        }
        for i in index.list.indices { index.list[i].idx = i }
        return index
    }

    /// A unique exact known tune for the text, or nil (none, or several: the server
    /// decides those). The alias tier wins.
    public static func resolveLocal(_ index: VocabIndex?, _ q: String) -> VocabTune? {
        guard let index else { return nil }
        let qn = LogState.normName(q)
        guard !qn.isEmpty else { return nil }
        if let a = index.alias[qn] {
            return a.count == 1 ? index.byID[a[0]] : nil
        }
        var ids: [Int] = []
        for key in [qn, LogState.stripThe(qn)] {
            for id in index.name[key] ?? [] where !ids.contains(id) { ids.append(id) }
        }
        return ids.count == 1 ? index.byID[ids[0]] : nil
    }

    /// The instant type-ahead: names and aliases containing the text (2+ characters),
    /// then notation matches for note-only text. Each group: tunes already in the set
    /// last, the set's type first, then vocabulary order, then name.
    public static func resolveLocalMany(
        _ index: VocabIndex?, _ q: String, limit: Int = 8, preferType: String? = nil, inSet: [Int] = []
    ) -> [VocabTune] {
        guard let index else { return [] }
        let qn = LogState.normName(q)
        let inSetIDs = Set(inSet)
        func before(_ a: VocabIndex.Entry, _ b: VocabIndex.Entry) -> Bool {
            let ia = inSetIDs.contains(a.tuneID) ? 1 : 0
            let ib = inSetIDs.contains(b.tuneID) ? 1 : 0
            if ia != ib { return ia < ib }
            let pa = preferType != nil && a.tuneType == preferType ? 0 : 1
            let pb = preferType != nil && b.tuneType == preferType ? 0 : 1
            if pa != pb { return pa < pb }
            if a.idx != b.idx { return a.idx < b.idx }
            return JSText.less(a.nn, b.nn)
        }
        var nameHits: [VocabIndex.Entry] = []
        if qn.count >= 2 {
            nameHits = index.list.filter { $0.nn.contains(qn) || $0.aliases.contains { $0.contains(qn) } }.sorted(by: before)
        }
        var abcHits: [VocabIndex.Entry] = []
        let needle = ABCQuery.abcNeedle(q)
        if !needle.isEmpty {
            let seen = Set(nameHits.map(\.tuneID))
            abcHits = index.list.filter { !$0.abc.isEmpty && !seen.contains($0.tuneID) && $0.abc.contains(needle) }.sorted(by: before)
        }
        let out =
            nameHits.map { VocabTune(tuneID: $0.tuneID, name: $0.name, tuneType: $0.tuneType) }
            + abcHits.map { VocabTune(tuneID: $0.tuneID, name: $0.name, tuneType: $0.tuneType, abc: true) }
        return Array(out.prefix(max(0, limit)))
    }

    // MARK: - The set being built

    /// The set the cursor adds to: the open last set at the end, the anchor's set
    /// otherwise, none for a new-set gap or a closed end.
    public static func cursorSegment(_ segments: [LogSegment], endIsOpen: Bool, cursor: Cursor) -> LogSegment? {
        switch cursor {
        case .end: return endIsOpen ? segments.last : nil
        case .newSet: return nil
        case .before(let id), .after(let id): return segments.first { $0.tunes.contains { $0.recordID == id } }
        }
    }

    /// The set's type when its typed tunes agree, else nil.
    public static func setTuneType(_ seg: LogSegment?) -> String? {
        guard let seg else { return nil }
        let types = Set(seg.tunes.compactMap { $0["tune_type"]?.stringValue }.filter { !$0.isEmpty })
        return types.count == 1 ? types.first : nil
    }

    /// The tune ids already in the set, once each.
    public static func setTuneIDs(_ seg: LogSegment?) -> [Int] {
        var ids: [Int] = []
        for t in seg?.tunes ?? [] { if let id = t["tune_id"]?.intValue, !ids.contains(id) { ids.append(id) } }
        return ids
    }

    public static func nextAssocKey(_ anchor: Int, _ next: Int) -> String { "\(anchor)->\(next)" }

    /// The likely next tune: at the end of a non-empty set whose last row is a linked
    /// tune, the one that usually follows it here, unless dismissed or already in the set.
    public static func likelyNext(_ index: VocabIndex?, seg: LogSegment?, cursor: Cursor, dismissed: [String] = [])
        -> VocabTune?
    {
        guard let index, let seg, let last = seg.tunes.last else { return nil }
        switch cursor {
        case .before, .newSet: return nil
        case .after(let id): if last.recordID != id { return nil }
        case .end: break
        }
        guard !last.isBreak, let tid = last["tune_id"]?.intValue, let nx = index.next[tid] else { return nil }
        if dismissed.contains(nextAssocKey(tid, nx.tuneID)) { return nil }
        if setTuneIDs(seg).contains(nx.tuneID) { return nil }
        return nx
    }

    /// The suggestion stays up while the typed text is part of its name.
    public static func nextMatchesInput(_ nx: VocabTune?, _ input: String) -> Bool {
        guard let nx else { return false }
        let q = LogState.normName(input)
        return q.isEmpty || LogState.normName(nx.name).contains(q)
    }

    // MARK: - Enter

    /// The dropdown as it stands.
    public struct Shown: Sendable {
        public var query: String?
        public var results: [JSONValue]
        public var searching: Bool
        public var noMatch: Bool
        public var exact: Bool
        public init(query: String? = nil, results: [JSONValue] = [], searching: Bool = false, noMatch: Bool = false, exact: Bool = false) {
            self.query = query
            self.results = results
            self.searching = searching
            self.noMatch = noMatch
            self.exact = exact
        }
    }

    public enum Step: Sendable, Equatable {
        /// Log this tune now.
        case pick(JSONValue)
        /// Nothing matches: log the text unlinked.
        case submit
        /// Several match and none exactly: a placeholder, with the choices showing.
        case ambiguous
        /// Not answered yet: a placeholder now, settled when the match lands.
        case resolve
    }

    /// What Enter does with the text, before any new network call; nil for nothing typed.
    public static func commitStep(_ index: VocabIndex?, _ q: String, shown: Shown) -> Step? {
        let q = JSText.trim(q)
        guard !q.isEmpty else { return nil }
        if let local = resolveLocal(index, q) { return .pick(local.json) }
        if shown.query == q && shown.results.count == 1 { return .pick(shown.results[0]) }
        if !shown.searching && shown.query == q && (!shown.results.isEmpty || shown.noMatch) {
            if shown.results.isEmpty { return .submit }
            if shown.exact { return .pick(shown.results[0]) }
            return .ambiguous
        }
        return .resolve
    }

    public enum Resolution: Sendable, Equatable {
        case unlinked
        case linked(VocabTune)
        case ambiguous([JSONValue])
    }

    /// What a match verdict ({exact_match, results}) does to a placeholder.
    public static func resolution(_ m: JSONValue?) -> Resolution {
        let results = m?["results"]?.arrayValue ?? []
        guard let t = results.first else { return .unlinked }
        if m?["exact_match"].isTruthy == true || results.count == 1 {
            return .linked(
                VocabTune(tuneID: t["tune_id"]?.intValue ?? 0, name: t["name"]?.stringValue ?? "", tuneType: t["tune_type"]?.stringValue))
        }
        return .ambiguous(Array(results.prefix(8)))
    }

    /// The name matches with the notation search's added after them (abc: true), eight
    /// at most; the verdict stays the name matcher's.
    public static func withNotationResults(_ m: JSONValue, abc: [JSONValue]) -> JSONValue {
        let results = m["results"]?.arrayValue ?? []
        let seen = Set(results.compactMap { $0["tune_id"]?.intValue })
        let extra: [JSONValue] = abc.compactMap { t in
            guard let id = t["tune_id"]?.intValue, !seen.contains(id) else { return nil }
            var o: [String: JSONValue] = ["tune_id": JSONValue(id), "abc": true]
            if let v = t["name"] { o["name"] = v }
            if let v = t["tune_type"] { o["tune_type"] = v }
            if let v = t["in_session"] { o["in_session_tune"] = v }
            return .object(o)
        }
        guard !extra.isEmpty else { return m }
        return ["exact_match": m["exact_match"] ?? false, "results": .array(Array((results + extra).prefix(8)))]
    }
}
