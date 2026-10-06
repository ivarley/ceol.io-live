// Adding a session: a port of frontend/src/addsession/logic.js, held to
// frontend/src/addsession/logic.fixtures.json. What the search box's text means, the URL
// path made from the city and name, the time zone guessed from thesession.org's country
// and state, the schedule read out of thesession.org's free text, and the recurrence
// editor's summary and stored JSON. A session added from the app must get the same
// path, zone and schedule as one added from the web.
//
// The regular expressions are JavaScript's, so \d is spelled [0-9] here (NSRegularExpression's
// \d matches every script's digits) and JS's ASCII \b after an ordinal is checked by hand.

import Foundation

public enum AddSession {
    // MARK: - The search box

    public enum Input: Equatable, Sendable {
        /// A thesession.org session link or bare digits: that session.
        case id(String)
        /// Anything else: a search.
        case search(String)
    }

    public static func parseSessionInput(_ input: String?) -> Input {
        let trimmed = JSText.trim(input ?? "")
        if let m = firstMatch(#"^https?://thesession\.org/sessions/([0-9]+)(?:/.*)?$"#, in: trimmed, caseInsensitive: true) {
            return .id(m[1] ?? "")
        }
        if JSText.isDigits(Substring(trimmed)) { return .id(trimmed) }
        return .search(trimmed)
    }

    // MARK: - The path

    /// "city/session-name". Only ASCII letters, digits, whitespace and hyphens survive the
    /// lowercasing, so accented letters are dropped ("Café" -> "caf"), as on the web.
    public static func generatePath(city: String?, sessionName: String?) -> String {
        func clean(_ s: String?) -> String {
            var kept = String.UnicodeScalarView()
            for u in (s ?? "").lowercased().unicodeScalars {
                if ("a"..."z").contains(u) || ("0"..."9").contains(u) || u == "-" || JSText.isWhitespace(u) {
                    kept.append(u)
                }
            }
            // Whitespace runs -> one hyphen; hyphen runs -> one; then one off each end.
            var out = ""
            var inSpace = false
            for u in kept {
                if JSText.isWhitespace(u) {
                    if !inSpace { out.append("-") }
                    inSpace = true
                } else {
                    inSpace = false
                    out.unicodeScalars.append(u)
                }
            }
            while out.contains("--") { out = out.replacingOccurrences(of: "--", with: "-") }
            if out.hasPrefix("-") { out.removeFirst() }
            if out.hasSuffix("-") { out.removeLast() }
            return out
        }
        let c = clean(city)
        let n = clean(sessionName)
        if !c.isEmpty && !n.isEmpty { return "\(c)/\(n)" }
        return n.isEmpty ? c : n
    }

    // MARK: - The time zone

    public static func guessTimezone(country: String?, state: String?, fallback: String = "America/Chicago") -> String {
        let c = (country ?? "").lowercased()
        let s = (state ?? "").lowercased()
        if c == "ireland" { return "Europe/Dublin" }
        if ["united kingdom", "uk", "england", "scotland", "wales"].contains(c) { return "Europe/London" }
        if ["united states", "usa", "us"].contains(c) { return usStateTimezones[s] ?? fallback }
        return fallback
    }

    static let usStateTimezones: [String: String] = {
        var t: [String: String] = [:]
        let zones: [(String, [String])] = [
            ("America/New_York", [
                "connecticut", "ct", "delaware", "de", "florida", "fl", "georgia", "ga", "indiana", "in",
                "kentucky", "ky", "maine", "me", "maryland", "md", "massachusetts", "ma", "michigan", "mi",
                "new hampshire", "nh", "new jersey", "nj", "new york", "ny", "north carolina", "nc", "ohio", "oh",
                "pennsylvania", "pa", "rhode island", "ri", "south carolina", "sc", "tennessee", "tn",
                "vermont", "vt", "virginia", "va", "west virginia", "wv", "district of columbia", "dc",
                "washington dc",
            ]),
            ("America/Chicago", [
                "alabama", "al", "arkansas", "ar", "illinois", "il", "iowa", "ia", "kansas", "ks",
                "louisiana", "la", "minnesota", "mn", "mississippi", "ms", "missouri", "mo", "nebraska", "ne",
                "north dakota", "nd", "oklahoma", "ok", "south dakota", "sd", "texas", "tx", "wisconsin", "wi",
            ]),
            ("America/Phoenix", ["arizona", "az"]),
            ("America/Denver", [
                "colorado", "co", "idaho", "id", "montana", "mt", "new mexico", "nm", "utah", "ut", "wyoming", "wy",
            ]),
            ("America/Los_Angeles", ["california", "ca", "nevada", "nv", "oregon", "or", "washington", "wa"]),
            ("America/Anchorage", ["alaska", "ak"]),
            ("Pacific/Honolulu", ["hawaii", "hi"]),
        ]
        for (zone, names) in zones { for n in names { t[n] = zone } }
        return t
    }()

    // MARK: - The schedule from thesession.org

    /// A session's schedule, as the recurrence editor holds it.
    public struct Schedule: Equatable, Sendable {
        public enum Kind: String, Sendable { case weekly, monthlyNthWeekday = "monthly_nth_weekday" }
        public var kind: Kind
        public var weekday: String
        /// Weekly: every 1 or 2 weeks.
        public var everyNWeeks: Int?
        /// Monthly: which occurrences, 1-4 or -1 for the last.
        public var which: [Int]?
        public var startTime: String
        public var endTime: String
    }

    static let dayPatterns: [(String, String)] = [
        ("wednesday", "wednesday"), ("thursdays", "thursday"), ("thursday", "thursday"),
        ("saturdays", "saturday"), ("saturday", "saturday"), ("tuesdays", "tuesday"), ("tuesday", "tuesday"),
        ("sundays", "sunday"), ("sunday", "sunday"), ("mondays", "monday"), ("monday", "monday"),
        ("fridays", "friday"), ("friday", "friday"),
        ("thurs", "thursday"), ("thur", "thursday"), ("tues", "tuesday"), ("wed", "wednesday"),
        ("thu", "thursday"), ("tue", "tuesday"), ("mon", "monday"), ("fri", "friday"), ("sat", "saturday"),
        ("sun", "sunday"),
    ]

    static func findWeekday(_ s: String) -> String? {
        let lower = s.lowercased()
        return dayPatterns.first { lower.contains($0.0) }?.1
    }

    static func pad(_ n: Int) -> String { n < 10 ? "0\(n)" : String(n) }

    static func parseTime(_ s: String) -> (start: String?, end: String?) {
        let both = #"([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)\s*(?:-|to|–|until)\s*([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)"#
        let endOnly = #"([0-9]{1,2})(?::([0-9]{2}))?\s*(?:-|to|–|until)\s*([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)"#
        let single = #"(?:@|at|from|starts?|begins?)?\s*([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)"#

        if let m = firstMatch(both, in: s, caseInsensitive: true) {
            var sh = Int(m[1]!)!, eh = Int(m[4]!)!
            let sm = m[2] ?? "00", em = m[5] ?? "00"
            let sa = m[3]!.lowercased(), ea = m[6]!.lowercased()
            if sa == "pm" && sh < 12 { sh += 12 }
            if sa == "am" && sh == 12 { sh = 0 }
            if ea == "pm" && eh < 12 { eh += 12 }
            if ea == "am" && eh == 12 { eh = 0 }
            return ("\(pad(sh)):\(sm)", "\(pad(eh)):\(em)")
        }
        if let m = firstMatch(endOnly, in: s, caseInsensitive: true) {
            var sh = Int(m[1]!)!, eh = Int(m[3]!)!
            let sm = m[2] ?? "00", em = m[4] ?? "00"
            let ampm = m[5]!.lowercased()
            if ampm == "pm" {
                if eh < 12 { eh += 12 }
                if sh < 12 && sh <= eh - 12 { sh += 12 }
            } else if ampm == "am" {
                if sh == 12 { sh = 0 }
                if eh == 12 { eh = 0 }
            }
            return ("\(pad(sh)):\(sm)", "\(pad(eh)):\(em)")
        }
        if let m = firstMatch(single, in: s, caseInsensitive: true) {
            var h = Int(m[1]!)!
            let mins = m[2] ?? "00"
            let ampm = m[3]!.lowercased()
            if ampm == "pm" && h < 12 { h += 12 }
            if ampm == "am" && h == 12 { h = 0 }
            return ("\(pad(h)):\(mins)", "\(pad((h + 3) % 24)):\(mins)")
        }
        return (nil, nil)
    }

    static let nthPatterns: [(String, Int)] = [
        ("first", 1), ("1st", 1), ("second", 2), ("2nd", 2), ("third", 3), ("3rd", 3), ("fourth", 4), ("4th", 4),
        ("last", -1),
    ]

    /// The ordinal words in `s`, in the table's order. JS tests /pattern\b/: the pattern
    /// anywhere, followed by the end or a character that isn't an ASCII word character.
    static func parseNthPatterns(_ s: String) -> [Int] {
        let lower = s.lowercased()
        var which: [Int] = []
        for (pattern, value) in nthPatterns where endsAtWordBoundary(pattern, in: lower) {
            if !which.contains(value) { which.append(value) }
        }
        return which
    }

    static func endsAtWordBoundary(_ pattern: String, in s: String) -> Bool {
        var from = s.startIndex
        while let r = s.range(of: pattern, range: from..<s.endIndex) {
            guard let next = s[r.upperBound...].unicodeScalars.first else { return true }
            let word = ("a"..."z").contains(next) || ("A"..."Z").contains(next) || ("0"..."9").contains(next) || next == "_"
            if !word { return true }
            from = s.index(after: r.lowerBound)
        }
        return false
    }

    static func isBiWeekly(_ s: String) -> Bool {
        let lower = s.lowercased()
        return lower.contains("every other") || lower.contains("bi-weekly") || lower.contains("biweekly")
    }

    /// thesession.org's schedule text (its lines joined with spaces) plus its comments,
    /// most recent first, as a schedule; nil when no weekday can be found.
    public static func parseTheSessionRecurrence(text: String?, comments: [String]?) -> Schedule? {
        let scheduleText = text ?? ""
        var weekday = findWeekday(scheduleText)
        var time = parseTime(scheduleText)
        var which = parseNthPatterns(scheduleText)
        var biWeekly = isBiWeekly(scheduleText)

        if let comments, !comments.isEmpty {
            for content in comments {
                guard let commentWeekday = findWeekday(content) else { continue }
                if weekday == nil { weekday = commentWeekday }
                if commentWeekday == weekday || findWeekday(scheduleText) == nil {
                    if time.start == nil { time = parseTime(content) }
                    if which.isEmpty { which = parseNthPatterns(content) }
                    if !biWeekly { biWeekly = isBiWeekly(content) }
                }
                break
            }
            if time.start == nil, let t = comments.lazy.map(parseTime).first(where: { $0.start != nil }) {
                time = t
            }
            if which.isEmpty, let w = comments.lazy.map(parseNthPatterns).first(where: { !$0.isEmpty }) {
                which = w
            }
        }

        guard let weekday else { return nil }
        let start = time.start ?? "19:00"
        let end = time.end ?? "22:00"
        if !which.isEmpty {
            return Schedule(kind: .monthlyNthWeekday, weekday: weekday, everyNWeeks: nil, which: which, startTime: start, endTime: end)
        }
        return Schedule(kind: .weekly, weekday: weekday, everyNWeeks: biWeekly ? 2 : 1, which: nil, startTime: start, endTime: end)
    }

    // MARK: - The recurrence editor

    static let ordinals: [Int: String] = [1: "1st", 2: "2nd", 3: "3rd", 4: "4th", -1: "last"]

    /// "8pm", "7:30pm", "12am".
    static func formatTimeOfDay(_ time: String) -> String {
        let parts = time.split(separator: ":", omittingEmptySubsequences: false).map(String.init)
        var h = Int(parts[0]) ?? 0
        let mins = parts.count > 1 ? parts[1] : ""
        let ampm = h >= 12 ? "pm" : "am"
        h = h % 12 == 0 ? 12 : h % 12
        return mins == "00" ? "\(h)\(ampm)" : "\(h):\(mins)\(ampm)"
    }

    /// The editor's summary line, and the recurrence JSON the API stores (nil while the
    /// state is incomplete). The JSON's key order is JSON.stringify's, as the web sends it.
    public static func summarizeRecurrence(
        type: String?, weekday: String?, frequency: Int = 1, which: [Int] = [], startTime: String, endTime: String
    ) -> (summary: String, json: String?) {
        guard let type, !type.isEmpty else { return ("No schedule set", nil) }
        guard let weekday, !weekday.isEmpty else { return ("Select a day...", nil) }
        let day = weekday.prefix(1).uppercased() + weekday.dropFirst()
        var fields: [(String, String)] = [
            ("type", quoted(type)), ("weekday", quoted(weekday)),
            ("start_time", quoted(startTime)), ("end_time", quoted(endTime)),
        ]
        var summary = ""
        if type == "weekly" {
            fields.append(("every_n_weeks", String(frequency)))
            switch frequency {
            case 1: summary = "\(day)s"
            case 2: summary = "Every other \(day)"
            default: summary = "Every \(frequency) weeks on \(day)"
            }
        } else if type == "monthly_nth_weekday" {
            if which.isEmpty { return ("Select which occurrences...", nil) }
            fields.append(("which", "[" + which.map(String.init).joined(separator: ",") + "]"))
            summary = which.map { ordinals[$0] ?? "" }.joined(separator: " & ") + " \(day)"
        }
        summary += " from \(formatTimeOfDay(startTime))-\(formatTimeOfDay(endTime))"
        let schedule = "{" + fields.map { "\(quoted($0.0)):\($0.1)" }.joined(separator: ",") + "}"
        return (summary, "{\"schedules\":[\(schedule)]}")
    }

    /// A JSON string literal, escaped as JSON.stringify escapes it.
    static func quoted(_ s: String) -> String {
        var out = "\""
        for u in s.unicodeScalars {
            switch u {
            case "\"": out += "\\\""
            case "\\": out += "\\\\"
            case "\n": out += "\\n"
            case "\r": out += "\\r"
            case "\t": out += "\\t"
            case "\u{08}": out += "\\b"
            case "\u{0C}": out += "\\f"
            default:
                if u.value < 0x20 {
                    out += String(format: "\\u%04x", u.value)
                } else {
                    out.unicodeScalars.append(u)
                }
            }
        }
        return out + "\""
    }

    // MARK: -

    /// The capture groups of the first match (index 0 is the whole match), nil for a group
    /// that took no part — what JS's String.match gives.
    static func firstMatch(_ pattern: String, in s: String, caseInsensitive: Bool = false) -> [String?]? {
        let re = try! NSRegularExpression(pattern: pattern, options: caseInsensitive ? [.caseInsensitive] : [])
        let ns = s as NSString
        guard let m = re.firstMatch(in: s, range: NSRange(location: 0, length: ns.length)) else { return nil }
        return (0..<m.numberOfRanges).map { i in
            let r = m.range(at: i)
            return r.location == NSNotFound ? nil : ns.substring(with: r)
        }
    }
}

// MARK: - A session's path

/// A port of frontend/src/shared/sessionpath.js (and so of the server's session_path.py),
/// held to frontend/src/shared/sessionpath.fixtures.json. The server is the authority;
/// this shows the problem in the form before the round trip.
public enum SessionPath {
    static let maxLength = 255
    static let pathSegments = 2 // {place}/{name-or-year}, spec 055
    static let maxSegmentLength = 100

    /// The trimmed path, or the sentence to show.
    public static func normalize(_ value: String?) -> (path: String?, error: String?) {
        guard let value else { return (nil, "Path is required") }
        let path = JSText.trim(value)
        if path.isEmpty { return (nil, "Path is required") }
        if path.unicodeScalars.contains(where: { isInvisible($0.value) }) {
            return (nil, "Path can't contain spaces or invisible characters")
        }
        // JS lengths are UTF-16 code units.
        if path.utf16.count > maxLength { return (nil, "Path must be \(maxLength) characters or fewer") }
        if path.hasPrefix("/") || path.hasSuffix("/") { return (nil, "Path can't start or end with a slash") }
        let segments = path.split(separator: "/", omittingEmptySubsequences: false)
        if segments.count != pathSegments {
            return (nil, "Path must have exactly two parts, a place and a name, like austin/mueller")
        }
        for segment in segments {
            if segment.isEmpty { return (nil, "Path can't contain an empty part (//)") }
            if segment.utf16.count > maxSegmentLength {
                return (nil, "Each part of the path must be \(maxSegmentLength) characters or fewer")
            }
            let allowed = segment.unicodeScalars.allSatisfy {
                ("A"..."Z").contains($0) || ("a"..."z").contains($0) || ("0"..."9").contains($0) || "._~-".unicodeScalars.contains($0)
            }
            if !allowed {
                return (nil, "Path can only contain letters, numbers, hyphens, underscores, periods and slashes")
            }
            let hasAlphanumeric = segment.unicodeScalars.contains {
                ("A"..."Z").contains($0) || ("a"..."z").contains($0) || ("0"..."9").contains($0)
            }
            if !hasAlphanumeric { return (nil, "Each part of the path must contain a letter or number") }
        }
        return (path, nil)
    }

    static func isInvisible(_ c: UInt32) -> Bool {
        c <= 0x20 || (0x7f...0xa0).contains(c) || c == 0xad || c == 0x34f || c == 0x61c || c == 0x1680
            || c == 0x180e || (0x2000...0x200f).contains(c) || (0x2028...0x202f).contains(c)
            || (0x205f...0x206f).contains(c) || c == 0x3000 || c == 0xfeff
    }
}

extension TheSession {
    /// A thesession.org session link or bare digits -> the session id, else nil. Mirrors
    /// the server's _parse_thesession_session_id.
    public static func sessionID(_ raw: String?) -> Int? {
        guard let raw else { return nil }
        let s = JSText.trim(raw)
        if let digits = digits(after: "thesession.org/sessions/", in: s) { return Int(digits) }
        return JSText.isDigits(Substring(s)) ? Int(s) : nil
    }
}
