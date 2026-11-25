// Export (the web's Me → Export my data, export_routes.py): what the app decides on
// its own before it asks the server for the file. The server resolves names, keys,
// settings and notation for the ids it is sent, in the order sent; the app only
// chooses the ids (the screen's filtered list) and describes the filters in force.
//
// Mirrors frontend/src/lib/export.js and the two exportsummary.js files. KEEP IN
// STEP with them: a filter added to a screen is a line added here and there.

import Foundation

public enum ExportRules {
    public enum Format: String, CaseIterable, Sendable, Equatable {
        case json, csv, pdf

        public var label: String { rawValue.uppercased() }
    }

    /// Where the export bar is up: the Tunes tab, or one session's page (whose tab
    /// then decides between its tunes and its logs, as on the web).
    public enum Target: Equatable, Sendable {
        case myTunes
        case session(path: String)
    }

    /// What one bar exports; the request body's id key and the endpoint follow it.
    public enum Kind: Hashable, Sendable {
        case myTunes
        case sessionTunes(path: String)
        case sessionLogs(path: String)
    }

    /// The server caps one file at this many ids (413 beyond).
    public static let maxIDs = 5000

    /// The file name the server chose, from its Content-Disposition. The plain form is
    /// unquoted unless the name needs quoting; the RFC 5987 form wins when present.
    public static func filename(fromContentDisposition disposition: String?) -> String? {
        guard let disposition else { return nil }
        if let range = disposition.range(of: "filename*=UTF-8''", options: .caseInsensitive) {
            let rest = disposition[range.upperBound...]
            let raw = rest.split(separator: ";", maxSplits: 1).first.map(String.init) ?? ""
            if let decoded = raw.removingPercentEncoding, !decoded.isEmpty { return decoded }
        }
        guard let range = disposition.range(of: "filename=", options: .caseInsensitive) else { return nil }
        var rest = String(disposition[range.upperBound...])
        if rest.hasPrefix("\"") {
            rest.removeFirst()
            return rest.split(separator: "\"", maxSplits: 1).first.map(String.init)
        }
        let plain = rest.split(separator: ";", maxSplits: 1).first.map(String.init) ?? ""
        return plain.trimmingCharacters(in: .whitespaces).isEmpty ? nil : plain.trimmingCharacters(in: .whitespaces)
    }

    /// A safe local file name: the server's, else one built from the kind and format.
    public static func localFilename(_ serverName: String?, kind: Kind, format: Format, day: String) -> String {
        if let serverName, !serverName.isEmpty, !serverName.contains("/") { return serverName }
        let stem: String
        switch kind {
        case .myTunes: stem = "ceol-my-tunes"
        case .sessionTunes(let path): stem = "ceol-\(slug(path))-tunes"
        case .sessionLogs(let path): stem = "ceol-\(slug(path))-logs"
        }
        return "\(stem)-\(day).\(format.rawValue)"
    }

    static func slug(_ text: String) -> String {
        let lowered = text.lowercased()
        var out = ""
        var dash = false
        for ch in lowered {
            if ch.isLetter || ch.isNumber {
                out.append(ch)
                dash = false
            } else if !dash, !out.isEmpty {
                out.append("-")
                dash = true
            }
        }
        while out.hasSuffix("-") { out.removeLast() }
        return out.isEmpty ? "ceol" : out
    }

    // MARK: Filter summaries

    /// One line of the file's header: a label and its value, which the view joins in
    /// its language ("Status: Learning"). Keys name the web's lines one for one.
    public struct Line: Equatable, Sendable {
        public enum Key: Equatable, Sendable {
            case status, type, instrument, tag, played, addedBefore, addedAfter, search, sort, thenBy
            case myTunebook, nightsWith, nights
        }
        public var key: Key
        public var value: String
        /// For sort lines: whether the direction is descending.
        public var descending: Bool?
        public init(key: Key, value: String, descending: Bool? = nil) {
            self.key = key
            self.value = value
            self.descending = descending
        }
    }

    /// The Tunes tab's filters as lines, in the web's order. Values are the raw ids
    /// (status "learning", type "reel", sort "popularity"); the view puts words on them.
    public static func myTunesLines(filters: MyTunesList.Filters, sort: MyTunesList.Sort) -> [Line] {
        var lines: [Line] = []
        if !filters.status.isEmpty { lines.append(Line(key: .status, value: filters.status)) }
        if !filters.type.isEmpty { lines.append(Line(key: .type, value: filters.type)) }
        if !filters.instrument.isEmpty { lines.append(Line(key: .instrument, value: filters.instrument)) }
        if !filters.tag.isEmpty { lines.append(Line(key: .tag, value: filters.tag)) }
        if !filters.rel.isEmpty { lines.append(Line(key: .played, value: filters.rel)) }
        if !filters.addedDate.isEmpty {
            lines.append(Line(key: filters.addedBefore ? .addedBefore : .addedAfter, value: filters.addedDate))
        }
        let q = filters.search.trimmingCharacters(in: .whitespaces)
        if !q.isEmpty { lines.append(Line(key: .search, value: q)) }
        if sort.type != "alpha" || sort.descending {
            lines.append(Line(key: .sort, value: sort.type, descending: sort.descending))
        }
        if let t2 = sort.type2 { lines.append(Line(key: .thenBy, value: t2, descending: sort.descending2)) }
        return lines
    }

    /// A session's Tunes tab. `myStatusInstrument` rides along in the value as
    /// "status/instrument" when it is not "all".
    public static func sessionTunesLines(filters: SessionPage.Filters, sort: SessionPage.Sort) -> [Line] {
        var lines: [Line] = []
        if sort.mode != .session || !sort.descending {
            lines.append(Line(key: .sort, value: sort.mode.rawValue, descending: sort.descending))
        }
        if !filters.type.isEmpty { lines.append(Line(key: .type, value: filters.type)) }
        if filters.attended { lines.append(Line(key: .played, value: "attended")) }
        if filters.myStatus != .off {
            let scope = filters.myStatusInstrument == "all" ? "" : "/" + filters.myStatusInstrument
            lines.append(Line(key: .myTunebook, value: filters.myStatus.rawValue + scope))
        }
        let q = filters.search.trimmingCharacters(in: .whitespaces)
        if !q.isEmpty { lines.append(Line(key: .search, value: q)) }
        return lines
    }

    /// A session's Logs tab: which nights, or the tune they were narrowed to.
    public static func sessionLogsLines(view: SessionPage.LogView, tuneName: String?) -> [Line] {
        if let tuneName, !tuneName.isEmpty { return [Line(key: .nightsWith, value: tuneName)] }
        return [Line(key: .nights, value: view.rawValue)]
    }
}
