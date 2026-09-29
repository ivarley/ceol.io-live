// Home's decisions — a port of frontend/src/homepage/logic.js (spec 052 §B2): which
// nights are today, whether one is live, what the tally and the subtitles say, and the
// "pick up where you left off" list. The Svelte Home and the SwiftUI Home make exactly
// these decisions from the same /api/home payload; HomeRulesTests pins the cases the
// web's homepage.logic.test.js pins. (adjustedCounts, which replays the web's queued
// offline edits into the counts, waits for the app's own offline queue.)
//
// Times are "HH:MM[:SS]" strings and dates "YYYY-MM-DD", as the payload carries them.

import Foundation

/// One of this week's nights, as Home reads it.
public struct HomeNight: Sendable, Equatable {
    public var name: String
    public var path: String?
    public var date: String
    public var startTime: String?
    public var endTime: String?
    public var locationName: String?
    public var isActive: Bool
    public var logComplete: Bool
    public var peopleHere: Int
    public var tunesLogged: Int

    public init(
        name: String, path: String?, date: String, startTime: String?, endTime: String?,
        locationName: String?, isActive: Bool, logComplete: Bool, peopleHere: Int, tunesLogged: Int
    ) {
        self.name = name
        self.path = path
        self.date = date
        self.startTime = startTime
        self.endTime = endTime
        self.locationName = locationName
        self.isActive = isActive
        self.logComplete = logComplete
        self.peopleHere = peopleHere
        self.tunesLogged = tunesLogged
    }
}

public enum HomeRules {
    public enum Status: Equatable, Sendable { case live, finished, upcoming }

    /// The nights happening today: a SUBSET of the week's list, never a second list,
    /// so the Today card and the week row cannot disagree about a night.
    public static func todaysSessions(_ upcoming: [HomeNight], today: String?) -> [HomeNight] {
        guard let today else { return [] }
        return upcoming.filter { $0.date == today }
    }

    /// The server's liveness flag wins (it knows the session's timezone); then a
    /// completed log; otherwise it hasn't started.
    public static func status(_ n: HomeNight) -> Status {
        if n.isActive { return .live }
        if n.logComplete { return .finished }
        return .upcoming
    }

    public static func statusLabel(_ n: HomeNight) -> String {
        switch status(n) {
        case .live: return "Live now"
        case .finished: return "Finished"
        case .upcoming:
            let start = formatTime(n.startTime)
            return start.isEmpty ? "Today" : "Starts \(start)"
        }
    }

    /// When, where, and — only while it is live — who is there.
    public static func todaySubtitle(_ n: HomeNight) -> String {
        var parts: [String] = []
        let when = instanceTimeLabel(start: n.startTime, end: n.endTime)
        if !when.isEmpty { parts.append(when) }
        if let loc = n.locationName, !loc.isEmpty { parts.append(loc) }
        if status(n) == .live && n.peopleHere > 0 {
            parts.append("\(n.peopleHere) \(n.peopleHere == 1 ? "person" : "people") here")
        }
        return parts.joined(separator: " · ")
    }

    /// "so far" only while the number can still move.
    public static func tallyLabel(_ n: HomeNight) -> String {
        if n.tunesLogged == 0 { return "No tunes logged yet" }
        let noun = n.tunesLogged == 1 ? "tune" : "tunes"
        return status(n) == .live ? "\(n.tunesLogged) \(noun) logged so far" : "\(n.tunesLogged) \(noun) logged"
    }

    /// A week row's second line: the time, where, and whether you have been yet.
    public static func weekSubtitle(_ n: HomeNight, today: String?) -> String {
        var parts: [String] = []
        let when = instanceTimeLabel(start: n.startTime, end: n.endTime)
        if !when.isEmpty { parts.append(when) }
        if let loc = n.locationName, !loc.isEmpty { parts.append(loc) }
        if n.logComplete {
            parts.append("logged")
        } else if let today, n.date < today {
            parts.append("not logged")
        }
        return parts.joined(separator: " · ")
    }

    // MARK: - Times and dates (shared/format.js)

    /// "19:00" -> "7:00pm"; nil or empty -> "".
    public static func formatTime(_ time: String?) -> String {
        guard let time, !time.isEmpty else { return "" }
        let parts = time.split(separator: ":", omittingEmptySubsequences: false)
        guard let h = Int(parts[0]), parts.count > 1 else { return "" }
        let period = h >= 12 ? "pm" : "am"
        let hour = h > 12 ? h - 12 : (h == 0 ? 12 : h)
        return "\(hour):\(parts[1])\(period)"
    }

    /// "7:00pm-10:00pm"; an open-ended night is "7:00pm - ?"; no start says nothing.
    public static func instanceTimeLabel(start: String?, end: String?) -> String {
        guard let start, !start.isEmpty else { return "" }
        if let end, !end.isEmpty { return formatTime(start) + "-" + formatTime(end) }
        return formatTime(start) + " - ?"
    }

    static func localDate(_ ymd: String) -> Date? {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: ymd)
    }

    static func format(_ date: Date, _ template: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US")
        f.timeZone = .current
        f.setLocalizedDateFormatFromTemplate(template)
        return f.string(from: date)
    }

    /// "Tue" over "22", for a row's date block.
    public static func dayOfWeek(_ ymd: String) -> String { localDate(ymd).map { format($0, "EEE") } ?? "" }
    public static func dayOfMonth(_ ymd: String) -> String {
        localDate(ymd).map { String(Calendar.current.component(.day, from: $0)) } ?? ""
    }

    /// "Sep 16", with the year only when it isn't the current one.
    public static func shortDate(_ ymd: String, currentYear: Int?) -> String {
        guard let d = localDate(ymd) else { return "" }
        let year = Calendar.current.component(.year, from: d)
        return format(d, currentYear != nil && year != currentYear ? "MMM d yyyy" : "MMM d")
    }

    /// "2 hours ago" for a recent edit; a date once that stops being useful.
    public static func editedLabel(_ iso: String?, currentYear: Int?, now: Date = Date()) -> String {
        guard let iso, let then = parseISO(iso) else { return "" }
        let mins = Int(now.timeIntervalSince(then) / 60)
        if mins < 1 { return "just now" }
        if mins < 60 { return "\(mins) minute\(mins == 1 ? "" : "s") ago" }
        let hours = mins / 60
        if hours < 24 { return "\(hours) hour\(hours == 1 ? "" : "s") ago" }
        let year = Calendar.current.component(.year, from: then)
        return format(then, currentYear != nil && year != currentYear ? "MMM d yyyy" : "MMM d")
    }

    static func parseISO(_ s: String) -> Date? {
        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return withFraction.date(from: s) ?? ISO8601DateFormatter().date(from: s)
    }

    // MARK: - Pick up where you left off

    public struct ContinueItem: Equatable, Sendable, Identifiable {
        public enum Kind: Equatable, Sendable { case log, recording }
        public var kind: Kind
        /// Unique across both kinds (their id spaces overlap).
        public var id: String
        public var title: String
        /// The night's date, for the row's date block.
        public var date: String
        public var detail: String
        public var lastEdit: String?
        /// The web path it opens: a night's log, or the recording segmenter.
        public var path: String
        public var sessionPath: String
        /// The night a log item opens in the app; nil for a recording.
        public var sessionInstanceID: Int? = nil
    }

    public struct UnfinishedLog: Sendable {
        public var sessionInstanceID: Int, name: String, path: String, date: String, lastEdit: String?
        public init(sessionInstanceID: Int, name: String, path: String, date: String, lastEdit: String?) {
            self.sessionInstanceID = sessionInstanceID
            self.name = name
            self.path = path
            self.date = date
            self.lastEdit = lastEdit
        }
    }

    public struct UnfinishedRecording: Sendable {
        public var recordingID: Int, label: String?, name: String, path: String, lastEdit: String?, placed: Int, tuneCount: Int
        public var date: String = ""
        public init(
            recordingID: Int, label: String?, name: String, path: String, lastEdit: String?, placed: Int, tuneCount: Int,
            date: String = ""
        ) {
            self.date = date
            self.recordingID = recordingID
            self.label = label
            self.name = name
            self.path = path
            self.lastEdit = lastEdit
            self.placed = placed
            self.tuneCount = tuneCount
        }
    }

    /// The unfinished logs and half-placed recordings as ONE list, newest edit first.
    public static func continueItems(
        logs: [UnfinishedLog], recordings: [UnfinishedRecording], currentYear: Int?
    ) -> [ContinueItem] {
        let l = logs.map {
            ContinueItem(
                kind: .log, id: "log-\($0.sessionInstanceID)", title: "Finish logging \($0.name)", date: $0.date,
                detail: shortDate($0.date, currentYear: currentYear), lastEdit: $0.lastEdit,
                path: "/sessions/\($0.path)/\($0.date)", sessionPath: $0.path, sessionInstanceID: $0.sessionInstanceID)
        }
        let r = recordings.map {
            ContinueItem(
                kind: .recording, id: "rec-\($0.recordingID)",
                title: "Place tunes on \(($0.label?.isEmpty == false ? $0.label : nil) ?? $0.name)", date: $0.date,
                detail: "\($0.placed) of \($0.tuneCount) tunes placed", lastEdit: $0.lastEdit,
                path: "/admin/recordings/\($0.recordingID)/segment", sessionPath: $0.path)
        }
        func t(_ s: String?) -> Double { s.flatMap(parseISO)?.timeIntervalSince1970 ?? 0 }
        return (l + r).enumerated()
            .sorted { t($0.element.lastEdit) != t($1.element.lastEdit) ? t($0.element.lastEdit) > t($1.element.lastEdit) : $0.offset < $1.offset }
            .map(\.element)
    }
}
