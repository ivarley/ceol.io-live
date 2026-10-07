// What the logger keeps on the phone (plan Phase 5d), as the web keeps it in IndexedDB
// ("ceol-live": snapshots, ops, matchcache; frontend/src/offline.js):
//
//   - Each night's last known state: the night's own fields (the bootstrap, raw), the
//     log with its unanswered changes (LiveLog is Codable, so a queued change keeps
//     everything it needs to show in place and to be undone), and the vocabulary.
//     Opening a night without a connection shows this; so does a slow load, after 800ms.
//   - Matches seen online (OfflineRules.matchCacheRows, keyed per night), so typing can
//     still link a tune offline.
//
// One file per night, one for the match cache, in Application Support. Signing out
// clears it all: it's this account's data.
//
// i18n-converted (spec 057): nothing here is shown to people.

import CeolLogic
import Foundation

struct SavedNight: Codable {
    /// The bootstrap as it came (its records are superseded by `log`).
    var night: JSONValue
    var log: LiveLog
    var knownTunes: JSONValue?
    var knownAliases: JSONValue?
    var savedAt: Date
}

enum NightStore {
    static var folder: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appending(path: "Nights", directoryHint: .isDirectory)
    }

    private static func file(_ instanceID: Int) -> URL { folder.appending(path: "\(instanceID).json") }
    private static var matchFile: URL { folder.appending(path: "matchcache.json") }

    static func load(_ instanceID: Int) -> SavedNight? {
        guard let data = try? Data(contentsOf: file(instanceID)) else { return nil }
        return try? JSONDecoder().decode(SavedNight.self, from: data)
    }

    static func save(_ night: SavedNight, _ instanceID: Int) {
        do {
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            try JSONEncoder().encode(night).write(to: file(instanceID), options: .atomic)
        } catch {
            // Best effort, as the web's snapshot is: the live log is still right.
        }
    }

    /// Everything, for signing out.
    static func clearAll() {
        try? FileManager.default.removeItem(at: folder)
        matchCache = nil
    }

    // MARK: - The match cache

    nonisolated(unsafe) private static var matchCache: [String: JSONValue]?

    private static func matches() -> [String: JSONValue] {
        if let m = matchCache { return m }
        let m = (try? Data(contentsOf: matchFile)).flatMap { try? JSONDecoder().decode([String: JSONValue].self, from: $0) } ?? [:]
        matchCache = m
        return m
    }

    /// Remember an online verdict (only one with results).
    static func putMatch(_ instanceID: Int, _ q: String, _ verdict: JSONValue) {
        guard !(verdict["results"]?.arrayValue ?? []).isEmpty else { return }
        var m = matches()
        let now = Date().timeIntervalSince1970 * 1000
        for row in OfflineRules.matchCacheRows(sessionInstanceID: JSONValue(instanceID), query: q, verdict: verdict, now: now) {
            if let key = row["key"]?.stringValue { m[key] = row }
        }
        matchCache = m
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try? JSONEncoder().encode(m).write(to: matchFile, options: .atomic)
    }

    /// Offline: the verdict for this text, else a tune by this exact name, as an exact
    /// match (the web's matchCacheGet).
    static func getMatch(_ instanceID: Int, _ q: String) -> JSONValue? {
        let m = matches()
        let id = JSONValue(instanceID)
        if let v = m[OfflineRules.matchCacheKey(sessionInstanceID: id, kind: "q", q)]?["verdict"],
            !(v["results"]?.arrayValue ?? []).isEmpty
        {
            return v
        }
        if let t = m[OfflineRules.matchCacheKey(sessionInstanceID: id, kind: "n", q)]?["tune"] {
            return ["exact_match": true, "results": [t], "fromCache": true]
        }
        return nil
    }
}
