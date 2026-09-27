// The live logger's offline rules — a port of the pure parts of frontend/src/offline.js
// (spec 024 §G). The web keeps the op queue and the match cache in IndexedDB; a native
// store replaces that plumbing, but what it stores, and in what order ops replay,
// must agree with the web. Cases and the exact rules: frontend/src/offline.fixtures.json.
//
// Queued ops and cache rows are JSON, as they are on the web and on the wire.

public enum OfflineRules {
    /// Queued ops for ONE instance, oldest first: only ops whose session_instance_id
    /// is STRICTLY equal to the instance (1 and "1" differ), a stable sort by ts. The
    /// input is the store's contents in op_id order, so a ts tie replays in op_id order
    /// — a native store must hand them over in that order too.
    public static func queueOrder(_ all: [JSONValue]?, sessionInstanceID: JSONValue) -> [JSONValue] {
        (all ?? []).filter { $0["session_instance_id"] == sessionInstanceID }
            .enumerated()
            .sorted { a, b in
                let ta = a.element["ts"]?.doubleValue, tb = b.element["ts"]?.doubleValue
                if let ta, let tb, ta != tb { return ta < tb }
                return a.offset < b.offset
            }
            .map(\.element)
    }

    /// The cache key's normalizer: normName, then one leading "the " dropped, so "The
    /// Silver Spear" and "Silver Spear" share an entry.
    public static func normMatchQuery(_ s: String?) -> String { LogState.stripThe(LogState.normName(s)) }

    /// `<instance>|q|<query>` for a whole verdict, `<instance>|n|<name>` for one tune.
    /// The instance id is written as JS would: 12 and "12" give the same key.
    public static func matchCacheKey(sessionInstanceID: JSONValue, kind: String, _ s: String?) -> String {
        let id: String
        switch sessionInstanceID {
        case .number(let n): id = JSText.string(of: n)
        case .string(let str): id = str
        default: id = "null"
        }
        return "\(id)|\(kind)|\(normMatchQuery(s))"
    }

    /// The rows one verdict writes: the verdict under its query, then each linked,
    /// named result (truthy tune_id, non-empty name) under its own name. `now` is the
    /// caller's clock in milliseconds.
    public static func matchCacheRows(
        sessionInstanceID: JSONValue, query q: String?, verdict: JSONValue, now: Double
    ) -> [JSONValue] {
        var rows: [JSONValue] = [
            ["key": .string(matchCacheKey(sessionInstanceID: sessionInstanceID, kind: "q", q)), "verdict": verdict, "ts": .number(now)]
        ]
        for t in verdict["results"]?.arrayValue ?? [] {
            guard t["tune_id"].isTruthy, t["name"].isTruthy, let name = t["name"]?.stringValue else { continue }
            rows.append([
                "key": .string(matchCacheKey(sessionInstanceID: sessionInstanceID, kind: "n", name)),
                "tune": ["tune_id": t["tune_id"]!, "name": .string(name), "tune_type": t["tune_type"] ?? .null],
                "ts": .number(now),
            ])
        }
        return rows
    }
}
