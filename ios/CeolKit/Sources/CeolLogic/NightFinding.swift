// Finding tunes in a night's log (the web logger's pull-down filter and its ★ my-list
// highlight, frontend/src/App.svelte displaySegments / rowListStatus): which sets to
// show for a search and a tunebook status, and where in a name the search sits.

import Foundation

public enum NightFinding {
    /// Where `query` sits in `name`, case and accents aside ("si bheag" finds "Sí Bheag");
    /// nil when it doesn't, or the query is blank.
    public static func match(_ name: String, _ query: String) -> Range<String.Index>? {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return nil }
        return name.range(of: q, options: [.caseInsensitive, .diacriticInsensitive])
    }

    /// Whether a record is what's being looked for: a tune whose name has the search
    /// (when there is one) and whose status under `statusOf` is `status` (when one is
    /// asked for). A break is never. With neither on, every tune is.
    public static func matches(
        _ r: LogRecord, query: String, status: String?, statusOf: (Int) -> String?
    ) -> Bool {
        guard !r.isBreak else { return false }
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if !q.isEmpty, match(r["name"]?.stringValue ?? "", q) == nil { return false }
        if let status {
            guard let id = r["tune_id"]?.intValue, statusOf(id) == status else { return false }
        }
        return true
    }

    /// The sets with a matching tune, whole: as on the web, a set is shown or not, and
    /// the other tunes in it stay for context.
    public static func filterSets(
        _ sets: [LogSegment], query: String, status: String?, statusOf: (Int) -> String?
    ) -> [LogSegment] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty || status != nil else { return sets }
        return sets.filter { $0.tunes.contains { matches($0, query: q, status: status, statusOf: statusOf) } }
    }
}
