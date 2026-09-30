// The logger's typing box (plan Phase 5c), as the web composer does it
// (frontend/src/App.svelte runSearch / matchFor / commit / startResolving /
// applyResolution / commitEdit), with the decisions in CeolLogic.Composer, held to the
// web's composer.fixtures.json:
//
//   - As you type: the vocabulary's matches at once, then the server's (/match, and the
//     notation search for note-only text) 180ms after you stop, merged stably.
//   - A thesession.org number or link offers that tune instead.
//   - Enter: a unique exact match logs at once; an answered search decides; otherwise a
//     "resolving…" placeholder holds the spot until the match lands, and if several
//     tunes fit, you choose (or log the text as it is).
//   - Editing a logged tune reuses the box: pick a match to relink, or type a name.

import CeolLogic
import Foundation
import Observation

@Observable
final class LogComposerModel {
    /// A typed name waiting on the server, with its placeholder row.
    struct Resolving: Equatable {
        var text: String
        var placeholderID: String
        var cursor: Cursor
        var seq: Int
    }

    var text = "" {
        didSet { if text != oldValue { typed() } }
    }
    /// The dropdown: server rows as JSON ({tune_id, name, tune_type, in_session_tune, abc}).
    private(set) var results: [JSONValue] = []
    private(set) var resultsQuery: String?
    private(set) var searching = false
    private(set) var noMatch = false
    private(set) var lastExact = false
    /// Several tunes fit the placeholder's text: choose one.
    private(set) var ambiguous = false
    private(set) var resolving: Resolving?
    /// A thesession.org tune number or link was typed.
    private(set) var theSessionID: Int?
    /// The logged tune being edited, and its name as it was.
    private(set) var editingID: RecordID?
    private(set) var editingName = ""

    @ObservationIgnored private unowned let night: NightModel
    @ObservationIgnored private var search: Task<Void, Never>?
    @ObservationIgnored private var seq = 0
    @ObservationIgnored private var quiet = false

    init(night: NightModel) {
        self.night = night
    }

    func reset() {
        if let r = resolving { night.dropPlaceholder(r.placeholderID) }
        resolving = nil
        editingID = nil
        setText("")
        clearResults()
    }

    // MARK: - Typing

    /// Change the text without searching (clearing it, or filling it for an edit).
    private func setText(_ t: String) {
        quiet = true
        text = t
        quiet = false
    }

    private func typed() {
        night.typed(text)
        guard !quiet, resolving == nil else { return }
        ambiguous = false
        runSearch()
    }

    private func clearResults() {
        search?.cancel()
        results = []
        resultsQuery = nil
        searching = false
        noMatch = false
        ambiguous = false
        theSessionID = nil
    }

    private func runSearch() {
        let q = text.trimmingCharacters(in: .whitespacesAndNewlines)
        search?.cancel()
        if let id = TheSession.tuneID(q) {
            clearResults()
            theSessionID = id
            return
        }
        theSessionID = nil
        guard q.count >= 2 else {
            clearResults()
            return
        }
        let seg = night.cursorSegment
        let local = Composer.resolveLocalMany(
            night.vocab, q, limit: 8, preferType: Composer.setTuneType(seg), inSet: Composer.setTuneIDs(seg)
        ).map(\.json)
        results = local
        resultsQuery = q
        searching = true
        noMatch = false
        seq += 1
        let mine = seq
        search = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(180))
            guard let self, !Task.isCancelled else { return }
            let m = await self.matchFor(q)
            guard !Task.isCancelled, self.seq == mine else { return }
            self.results = LogState.mergeStable(local, m["results"]?.arrayValue ?? [])
            self.lastExact = m["exact_match"] == true
            self.noMatch = self.results.isEmpty
            self.searching = false
        }
    }

    /// The server's verdict for the text: /match (rows renamed to the web's shape), with
    /// the notation search's tunes added for note-only text. A failure is "no match".
    func matchFor(_ q: String) async -> JSONValue {
        let prefer = Composer.setTuneType(night.cursorSegment)
        var items: [URLQueryItem] = [.init(name: "q", value: q), .init(name: "limit", value: "8")]
        if let prefer { items.append(.init(name: "prefer_type", value: prefer)) }
        async let abc: [JSONValue] = ABCQuery.looksLikeAbc(q) ? notationSearch(q, prefer: prefer) : []
        var m: JSONValue = ["exact_match": false, "results": []]
        let answer = try? await night.app.getJSON(path("/api/live/instances/\(night.instanceID)/match", items))
        if let r = answer {
            let rows: [JSONValue] = (r["results"]?.arrayValue ?? []).map { t in
                var o: [String: JSONValue] = ["tune_id": t["tune_id"] ?? .null, "name": t["tune_name"] ?? .null,
                                              "tune_type": t["tune_type"] ?? .null]
                if let v = t["in_session_tune"] { o["in_session_tune"] = v }
                return .object(o)
            }
            m = ["exact_match": r["exact_match"] ?? false, "results": .array(rows)]
        }
        if !(m["results"]?.arrayValue ?? []).isEmpty {
            // Remembered, so the same text can still link a tune offline.
            NightStore.putMatch(night.instanceID, q, m)
        } else if answer == nil || night.status == .offline, let cached = NightStore.getMatch(night.instanceID, q) {
            // Offline (an online empty answer is the real answer): what we saw before.
            return cached
        }
        return Composer.withNotationResults(m, abc: await abc)
    }

    private func notationSearch(_ q: String, prefer: String?) async -> [JSONValue] {
        var items: [URLQueryItem] = [
            .init(name: "instance", value: String(night.instanceID)), .init(name: "q", value: q),
            .init(name: "limit", value: "8"), .init(name: "mode", value: "abc"),
        ]
        if let prefer { items.append(.init(name: "prefer_type", value: prefer)) }
        return (try? await night.app.getJSON(path("/api/tunes/deep-search", items)))?["results"]?.arrayValue ?? []
    }

    private func path(_ p: String, _ items: [URLQueryItem]) -> String {
        var c = URLComponents()
        c.path = p
        c.queryItems = items
        return c.string ?? p
    }

    // MARK: - Enter

    func commit() async {
        if editingID != nil {
            await commitEdit()
            return
        }
        if resolving != nil {
            // Enter on a placeholder with choices showing takes the top one.
            if ambiguous, let top = results.first { settle(with: top) }
            return
        }
        if let id = theSessionID {
            logTheSession(id)
            return
        }
        let q = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let shown = Composer.Shown(query: resultsQuery, results: results, searching: searching, noMatch: noMatch, exact: lastExact)
        switch Composer.commitStep(night.vocab, q, shown: shown) {
        case nil: return
        case .pick(let t)?: pick(t)
        case .submit?:
            setText("")
            clearResults()
            night.logTune(["name": .string(q)])
        case .ambiguous?:
            startResolving(q)
            apply(["exact_match": .bool(lastExact), "results": .array(results)])
        case .resolve?:
            startResolving(q)
            guard let r = resolving else { return }
            let m = await matchFor(q)
            guard resolving?.seq == r.seq else { return }  // settled or cancelled meanwhile
            apply(m)
        }
    }

    /// A row from the dropdown (or the likely-next suggestion).
    func pick(_ t: JSONValue) {
        if let id = editingID {
            relink(id, to: t)
            return
        }
        if resolving != nil {
            settle(with: t)
            return
        }
        setText("")
        clearResults()
        night.logTune(payload(t))
    }

    func logTheSession(_ id: Int) {
        setText("")
        clearResults()
        night.logTune(["thesession_id": JSONValue(id), "name": .string("#\(id)")])
    }

    private func payload(_ t: JSONValue) -> [String: JSONValue] {
        ["tune_id": t["tune_id"] ?? .null, "name": t["name"] ?? .null, "tune_type": t["tune_type"] ?? .null]
    }

    // MARK: - The placeholder

    private func startResolving(_ q: String) {
        guard let id = night.startPlaceholder(q, at: night.cursor) else { return }
        seq += 1
        search?.cancel()
        resolving = Resolving(text: q, placeholderID: id, cursor: night.cursor, seq: seq)
        night.stopTyping()
        setText("")
        searching = false
    }

    private func apply(_ m: JSONValue) {
        guard let r = resolving else { return }
        switch Composer.resolution(m) {
        case .unlinked: settle(payload: ["name": .string(r.text)])
        case .linked(let t): settle(payload: payload(t.json))
        case .ambiguous(let rows):
            results = rows
            resultsQuery = r.text
            noMatch = false
            ambiguous = true
        }
    }

    private func settle(with t: JSONValue) { settle(payload: payload(t)) }

    private func settle(payload: [String: JSONValue]) {
        guard let r = resolving else { return }
        night.dropPlaceholder(r.placeholderID)
        resolving = nil
        clearResults()
        night.logTune(payload, at: r.cursor)
    }

    /// "Log it as typed": the placeholder becomes an unlinked row.
    func logAsIs() {
        guard let r = resolving else { return }
        settle(payload: ["name": .string(r.text)])
    }

    /// Give up on the placeholder; `returnText` puts the text back in the box.
    func cancelResolving(returnText: Bool) {
        guard let r = resolving else { return }
        night.dropPlaceholder(r.placeholderID)
        resolving = nil
        clearResults()
        if returnText {
            text = r.text
        }
    }

    // MARK: - Editing a logged tune

    func startEdit(_ record: LogRecord) {
        guard let id = record.recordID, !record["_temp"].isTruthy else { return }
        if resolving != nil { cancelResolving(returnText: false) }
        editingID = id
        editingName = record["name"]?.stringValue ?? ""
        night.selected = nil
        text = editingName
    }

    func cancelEdit() {
        editingID = nil
        editingName = ""
        setText("")
        clearResults()
    }

    /// Save: the top match if one fits the text (relink), else rename to the text.
    private func commitEdit() async {
        guard let id = editingID else { return }
        let q = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else {
            cancelEdit()
            return
        }
        if resultsQuery == q, let top = results.first {
            relink(id, to: top)
            return
        }
        let m = await matchFor(q)
        if let top = m["results"]?.arrayValue?.first {
            relink(id, to: top)
            return
        }
        cancelEdit()
        night.changeTune(id, ["name": .string(q), "unlink": true], patch: ["name": .string(q), "tune_id": .null, "tune_type": .null])
    }

    /// A deep-search pick while editing: relink to it (a thesession.org pick carries its
    /// thesession_id, and the server finds or imports the tune).
    func relink(to pick: [String: JSONValue]) {
        guard let id = editingID else { return }
        relink(id, to: .object(pick))
    }

    private func relink(_ id: RecordID, to t: JSONValue) {
        cancelEdit()
        var payload: [String: JSONValue] = ["tune_id": t["tune_id"] ?? .null, "name": t["name"] ?? .null]
        if let ts = t["thesession_id"], !ts.isNull { payload["thesession_id"] = ts }
        night.changeTune(
            id, payload,
            patch: ["tune_id": t["tune_id"] ?? .null, "name": t["name"] ?? .null, "tune_type": t["tune_type"] ?? .null,
                    "confidence": 100])
    }

    /// Keep the name, drop the link to the catalogue.
    func unlink() {
        guard let id = editingID else { return }
        cancelEdit()
        night.changeTune(id, ["unlink": true], patch: ["tune_id": .null, "tune_type": .null])
    }
}
