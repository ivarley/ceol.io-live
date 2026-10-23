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
    /// The night's id, to open it; nil only in fixtures that carry none.
    public var sessionInstanceID: Int?
    /// Other nights of the session share the date (a festival's rooms): the night's
    /// web link is then by id, because the date URL cannot tell them apart.
    public var multipleOnDate: Bool
    /// Which day of a multi-day festival this is, counted from its first day ("Day 2");
    /// nil for a regular session.
    public var festivalDay: Int?

    public init(
        name: String, path: String?, date: String, startTime: String?, endTime: String?,
        locationName: String?, isActive: Bool, logComplete: Bool, peopleHere: Int, tunesLogged: Int,
        sessionInstanceID: Int? = nil, multipleOnDate: Bool = false, festivalDay: Int? = nil
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
        self.sessionInstanceID = sessionInstanceID
        self.multipleOnDate = multipleOnDate
        self.festivalDay = festivalDay
    }
}

/// A session's several nights on one day, folded into one Home item (a festival's rooms).
public struct HomeGroup: Sendable, Equatable {
    public var name: String
    public var path: String?
    public var date: String
    public var nights: [HomeNight]
    /// The ones on now, in the payload's order.
    public var live: [HomeNight]
    /// The rooms on now, by name: what you are choosing between.
    public var liveRooms: [String]
    public var tunesLogged: Int
    public var allFinished: Bool
    /// Which day of the festival this is; nil when the session does not say.
    public var festivalDay: Int?
}

/// One Today card or week row: a night on its own, or a day's fold of one session.
public enum HomeItem: Sendable, Equatable, Identifiable {
    case night(HomeNight)
    case group(HomeGroup)

    public var id: String {
        switch self {
        case .night(let n): return "night-\(n.sessionInstanceID.map(String.init) ?? "\(n.path ?? "")|\(n.date)")"
        case .group(let g): return "group-\(g.path ?? "")|\(g.date)"
        }
    }

    public var date: String {
        switch self {
        case .night(let n): return n.date
        case .group(let g): return g.date
        }
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

    /// The web path of a night's page: its date, or its id when several nights of the
    /// session share the date (the server's `multiple_on_date`) — the date URL would
    /// land every room of a festival on the same log. The rule frontend/src/shared/nights.js
    /// states, so a link shared from the app and one from the web are the same link.
    public static func nightPath(sessionPath: String, date: String?, id: Int?, multipleOnDate: Bool) -> String {
        if let id, multipleOnDate || date == nil || date == "" { return "/sessions/\(sessionPath)/\(id)" }
        return "/sessions/\(sessionPath)/\(date ?? "")"
    }

    /// The Today cards and the week's rows, with a session's several nights on one day
    /// folded into one item (the web's homepage/logic.js nightItems). At a festival
    /// every room is a night of the one session, so a day has a dozen at once; a dozen
    /// cards is a strip nobody can page through. The fold says "12 sessions today,
    /// 4 on now", names the rooms on now, and opens the session, where the day's list
    /// is. Items keep the payload's order; a night on its own is an item as before.
    public static func nightItems(_ nights: [HomeNight]) -> [HomeItem] {
        var order: [String] = []
        var byKey: [String: [HomeNight]] = [:]
        for n in nights {
            let key = "\(n.path ?? n.name)|\(n.date)"
            if byKey[key] == nil { order.append(key) }
            byKey[key, default: []].append(n)
        }
        return order.map { key in
            let group = byKey[key]!
            if group.count == 1 { return .night(group[0]) }
            let live = group.filter(\.isActive)
            return .group(HomeGroup(
                name: group[0].name, path: group[0].path, date: group[0].date, nights: group, live: live,
                liveRooms: live.compactMap { $0.locationName.flatMap { $0.isEmpty ? nil : $0 } },
                tunesLogged: group.reduce(0) { $0 + $1.tunesLogged },
                allFinished: group.allSatisfy(\.logComplete),
                festivalDay: group[0].festivalDay))
        }
    }

    public static func groupStatus(_ g: HomeGroup) -> Status {
        if !g.live.isEmpty { return .live }
        if g.allFinished { return .finished }
        return .upcoming
    }

    /// The fold's chip: how many are on now; else finished, or when the first starts.
    public static func groupStatusLabel(_ g: HomeGroup) -> String {
        switch groupStatus(g) {
        case .live: return "\(g.live.count) on now"
        case .finished: return "Finished"
        case .upcoming:
            let start = formatTime(g.nights.first?.startTime)
            return start.isEmpty ? "Today" : "Starts \(start)"
        }
    }

    /// "Day 2" at a multi-day festival; "" otherwise.
    public static func festivalDayLabel(_ day: Int?) -> String {
        day.map { "Day \($0)" } ?? ""
    }

    /// Which day of the festival, and how many sessions it holds.
    public static func groupSubtitle(_ g: HomeGroup) -> String {
        [festivalDayLabel(g.festivalDay), g.nights.count == 1 ? "1 session today" : "\(g.nights.count) sessions today"]
            .filter { !$0.isEmpty }.joined(separator: " · ")
    }

    /// The rooms on now by name, or, with none on, the day's tally.
    public static func groupTally(_ g: HomeGroup) -> String {
        if !g.liveRooms.isEmpty { return g.liveRooms.joined(separator: ", ") }
        if g.tunesLogged == 0 { return "No tunes logged yet" }
        return "\(g.tunesLogged) \(g.tunesLogged == 1 ? "tune" : "tunes") logged"
    }

    public static func groupWeekSubtitle(_ g: HomeGroup, today: String?) -> String {
        var parts = [festivalDayLabel(g.festivalDay), g.nights.count == 1 ? "1 session" : "\(g.nights.count) sessions"]
            .filter { !$0.isEmpty }
        if !g.live.isEmpty {
            parts.append("\(g.live.count) on now")
        } else if g.allFinished {
            parts.append("logged")
        } else if let today, g.date < today {
            parts.append("not logged")
        }
        return parts.joined(separator: " · ")
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
        if let day = n.festivalDay { parts.append(festivalDayLabel(day)) }
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
        if let day = n.festivalDay { parts.append(festivalDayLabel(day)) }
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
        public var multipleOnDate: Bool
        public init(
            sessionInstanceID: Int, name: String, path: String, date: String, lastEdit: String?,
            multipleOnDate: Bool = false
        ) {
            self.sessionInstanceID = sessionInstanceID
            self.name = name
            self.path = path
            self.date = date
            self.lastEdit = lastEdit
            self.multipleOnDate = multipleOnDate
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
                path: nightPath(sessionPath: $0.path, date: $0.date, id: $0.sessionInstanceID, multipleOnDate: $0.multipleOnDate),
                sessionPath: $0.path, sessionInstanceID: $0.sessionInstanceID)
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
