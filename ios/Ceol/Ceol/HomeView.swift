// Home (spec 052 §B2), the app's twin of the Svelte home page, from the same /api/home
// payload and the same rules (CeolLogic.HomeRules): Today, when a session is on today
// (a swipeable strip when there are several, as at a festival); This week; Learning;
// and Pick up where you left off. A night opens its session's page for now; the live
// logger arrives in Phase 5.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

typealias HomePayload = Components.Schemas.Home

/// A screen pushed onto a tab's navigation stack.
enum Route: Hashable {
    case session(path: String, name: String)
    case night(id: Int, title: String)
    /// A festival as a whole (spec 056): its slug is not a session path.
    case festival(slug: String, name: String)
}

extension HomePayload.UpcomingSessionsPayloadPayload {
    var night: HomeNight {
        HomeNight(
            name: name, path: path, date: date, startTime: startTime, endTime: endTime,
            locationName: locationName, isActive: isActive, logComplete: logCompleteDate != nil,
            peopleHere: peopleHere, tunesLogged: tunesLogged,
            sessionInstanceID: sessionInstanceId, multipleOnDate: multipleOnDate)
    }
}

struct HomeView: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        if model.isGuest { GuestHomeView() } else { signedIn }
    }

    private var signedIn: some View {
        NavigationStack {
            Resourced(resource: model.home) { home in
                content(home)
            }
            .background(CeolTokens.bgColor)
            .ceolKept(model.home)
            .ceolRootBar(tr("Home"), sharePath: "/")
            .task { await model.home.refresh(ifOlderThan: 20) }
        }
    }

    private func load() async {
        await model.home.refresh()
    }

    /// The server's "today" while the payload is today's; the phone's once it is older
    /// (kept overnight, with no signal, yesterday's nights are not tonight's).
    private var todayString: String {
        if let saved = model.home.savedAt, Calendar.current.isDateInToday(saved), let t = model.home.value?.today { return t }
        return localToday()
    }

    @ViewBuilder private func content(_ home: HomePayload) -> some View {
        let week = home.upcomingSessions
        let today = HomeRules.todaysSessions(week.map(\.night), today: todayString)
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                (Text("Welcome back, ") + Text(home.viewer?.firstName ?? tr("there")).font(.ceol(size: 26, weight: .semibold)))
                    .font(.ceol(size: 26, weight: .light, relativeTo: .title))
                    .foregroundStyle(CeolTokens.textColor)
                // The meter, with no night in mind (spec 059).
                Button { model.openListen() } label: {
                    Label { Text("What tune am I hearing right now?") } icon: { EarGlyph(size: 22) }
                        .font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.primary)
                        .frame(maxWidth: .infinity, minHeight: 50)
                        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.primary.opacity(0.6), lineWidth: 1))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("home.listen")
                if !today.isEmpty {
                    // A session's several nights on one day (a festival's rooms) are one
                    // card, which opens the session: its screen lists the rooms on now.
                    TodayStrip(items: HomeRules.nightItems(today), open: open)
                }
                VStack(alignment: .leading, spacing: 0) {
                    SectionHeading(title: tr("This week"), icon: "TabSessions")
                    if week.isEmpty {
                        Text("No sessions scheduled this week.").foregroundStyle(CeolTokens.textMuted).padding(.vertical, 16)
                    }
                    ForEach(HomeRules.nightItems(week.map(\.night))) { item in
                        switch item {
                        case .night(let n):
                            WeekRow(night: n, today: todayString) {
                                open(item)
                            } openSession: {
                                if let p = n.path { model.openSession(path: p, name: n.name) }
                            }
                        case .group(let g):
                            GroupWeekRow(group: g, today: todayString) { open(item) }
                        }
                        Rectangle().fill(CeolTokens.borderColor).frame(height: 1)
                    }
                }
                VStack(alignment: .leading, spacing: 14) {
                    SectionHeading(title: tr("Learning"), icon: "TabTunes") {
                        Button("See all") { model.openTunes(status: nil) }
                            .font(.ceol(size: 16))
                            .foregroundStyle(CeolTokens.primary)
                    }
                    HStack(spacing: 12) {
                        Button { model.openTunes(status: .learning) } label: {
                            Stat(number: home.learningCount, label: tr("Learning"))
                        }
                        .buttonStyle(.plain)
                        Button { model.openTunes(status: .wantToLearn) } label: {
                            Stat(number: home.wantToLearnCount, label: tr("To Learn"))
                        }
                        .buttonStyle(.plain)
                    }
                    if let tune = home.suggestedTune {
                        let total = home.learningCount + home.wantToLearnCount
                        (Text(total == 0 ? tr("A tune to learn: ") : tr("Another tune to learn: "))
                            + Text(tune.name).foregroundStyle(CeolTokens.primary)
                            + Text(tune.tuneType.map { " (\(tuneTypeName($0)))" } ?? "").foregroundStyle(CeolTokens.textMuted))
                            .font(.ceol(size: 15))
                            .foregroundStyle(CeolTokens.textColor)
                    }
                }
                continueSection(home)
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .refreshable { await load() }
    }

    @ViewBuilder private func continueSection(_ home: HomePayload) -> some View {
        let unfinished = HomeRules.continueItems(
            logs: home.inProgressLogs.map {
                .init(sessionInstanceID: $0.sessionInstanceId, name: $0.name, path: $0.path, date: $0.date,
                      lastEdit: $0.lastEdit, multipleOnDate: $0.multipleOnDate)
            },
            recordings: home.inProgressRecordings.map {
                .init(recordingID: $0.recordingId, label: $0.label, name: $0.name, path: $0.path,
                      lastEdit: $0.lastEdit, placed: $0.placed, tuneCount: $0.tuneCount, date: $0.date)
            },
            currentYear: home.currentYear)
        if !unfinished.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                SectionHeading(title: tr("Pick up where you left off"), icon: "IconPencil")
                ForEach(unfinished) { item in
                    let title = HomeText.continueTitle(item, home)
                    Button {
                        if let id = item.sessionInstanceID {
                            model.openNight(id: id, title: title, sessionPath: item.sessionPath, sessionName: title)
                        } else {
                            model.openSession(path: item.sessionPath, name: title)
                        }
                    } label: {
                        HStack(spacing: 14) {
                            DateBlock(weekday: HomeText.dayOfWeek(item.date), day: HomeRules.dayOfMonth(item.date))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(title).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.primary)
                                Text([HomeText.continueDetail(item, home), HomeText.editedLabel(item.lastEdit, currentYear: home.currentYear)]
                                    .filter { !$0.isEmpty }.joined(separator: " · "))
                                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                            }
                            Spacer()
                        }
                        .padding(.vertical, 12)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    Rectangle().fill(CeolTokens.borderColor).frame(height: 1)
                }
            }
        }
    }

    /// A night opens its log, as the web's week rows and View button do.
    /// A night opens its log; a day's fold opens the session, where the rooms are listed.
    private func open(_ item: HomeItem) {
        switch item {
        case .night(let night):
            // By the night's own id. Matching on name and date found the FIRST room of
            // a festival day, whichever card you tapped.
            guard let id = night.sessionInstanceID else {
                if let p = night.path { model.openSession(path: p, name: night.name) }
                return
            }
            model.openNight(
                id: id, title: "\(night.name) · \(HomeText.shortDate(night.date, currentYear: nil))",
                sessionPath: night.path, sessionName: night.name)
        case .group(let group):
            if let p = group.path { model.openSession(path: p, name: group.name) }
        }
    }
}

// MARK: - Pieces

/// Today's items: one card, or a paged strip when there are several — two sessions on
/// one day. A festival's rooms are one item (HomeRules.nightItems), not a page each.
private struct TodayStrip: View {
    let items: [HomeItem]
    let open: (HomeItem) -> Void

    var body: some View {
        if items.count == 1 {
            TodayCard(item: items[0], open: open)
        } else {
            TabView {
                ForEach(items) { item in
                    TodayCard(item: item, open: open).padding(.bottom, 30)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
            .frame(height: 250)
        }
    }
}

/// The web's today card: a green left edge, "TODAY" in capitals, the status pill, the
/// session, what's been logged, and a green View button into the night — or, for a
/// day's fold, how many sessions, how many on now and which rooms they are.
private struct TodayCard: View {
    let item: HomeItem
    let open: (HomeItem) -> Void

    private var status: HomeRules.Status {
        switch item {
        case .night(let n): HomeRules.status(n)
        case .group(let g): HomeRules.groupStatus(g)
        }
    }
    private var name: String {
        switch item {
        case .night(let n): n.name
        case .group(let g): g.name
        }
    }
    private var chip: String {
        switch item {
        case .night(let n): HomeText.statusLabel(n)
        case .group(let g): HomeText.groupStatusLabel(g)
        }
    }
    private var subtitle: String {
        switch item {
        case .night(let n): HomeText.todaySubtitle(n)
        case .group(let g): HomeText.groupSubtitle(g)
        }
    }
    private var tally: (text: String, bright: Bool) {
        switch item {
        case .night(let n): (HomeText.tallyLabel(n), n.tunesLogged > 0)
        case .group(let g): (HomeText.groupTally(g), !g.liveRooms.isEmpty || g.tunesLogged > 0)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("TODAY").font(.ceol(size: 13, weight: .medium)).tracking(1.2).foregroundStyle(CeolTokens.textMuted)
                Spacer()
                Pill(
                    text: chip, style: status == .live ? .filled : .outline,
                    color: status == .live ? CeolTokens.primaryFill : CeolTokens.textColor)
            }
            Text(name).font(.ceol(size: 22, weight: .semibold, relativeTo: .title2)).foregroundStyle(CeolTokens.textColor)
            if !subtitle.isEmpty { Text(subtitle).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor.opacity(0.85)) }
            Text(tally.text).font(.ceol(size: 15)).lineLimit(2)
                .foregroundStyle(tally.bright ? CeolTokens.primary : CeolTokens.textMuted)
            Button { open(item) } label: {
                Text("View").font(.ceol(size: 17, weight: .medium)).foregroundStyle(.white)
                    .padding(.horizontal, 22).padding(.vertical, 9)
                    .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)
            .padding(.top, 4)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        .overlay(alignment: .leading) {
            UnevenRoundedRectangle(topLeadingRadius: 12, bottomLeadingRadius: 12)
                .fill(CeolTokens.primary).frame(width: 4)
        }
        .contentShape(Rectangle())
        .onTapGesture { open(item) }
    }
}

/// A day's fold this week (a festival's rooms): the date block, the session's name,
/// how many sessions and how many on now. The row opens the session.
private struct GroupWeekRow: View {
    let group: HomeGroup
    let today: String
    let open: () -> Void

    var body: some View {
        HStack(spacing: 14) {
            DateBlock(weekday: HomeText.dayOfWeek(group.date), day: HomeRules.dayOfMonth(group.date))
            VStack(alignment: .leading, spacing: 2) {
                Text(group.name).font(.ceol(size: 18, weight: .medium)).foregroundStyle(CeolTokens.primary)
                    .multilineTextAlignment(.leading)
                let sub = HomeText.groupWeekSubtitle(group, today: today)
                if !sub.isEmpty { Text(sub).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted).lineLimit(1) }
            }
            Spacer(minLength: 8)
            if group.date == today {
                let live = !group.live.isEmpty
                Pill(text: live ? tr("Live") : tr("Today"), color: live ? CeolTokens.primary : CeolTokens.textMuted)
            } else if group.allFinished {
                Text("Logged").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            }
        }
        .padding(.vertical, 12)
        .contentShape(Rectangle())
        .onTapGesture(perform: open)
    }
}

/// A night this week: the date block, the session's name in green (opens the session),
/// what and where, and a Today / Live pill. The rest of the row opens the night.
private struct WeekRow: View {
    let night: HomeNight
    let today: String
    let openNight: () -> Void
    let openSession: () -> Void

    var body: some View {
        HStack(spacing: 14) {
            DateBlock(weekday: HomeText.dayOfWeek(night.date), day: HomeRules.dayOfMonth(night.date))
            VStack(alignment: .leading, spacing: 2) {
                Button(action: openSession) {
                    Text(night.name).font(.ceol(size: 18, weight: .medium)).foregroundStyle(CeolTokens.primary)
                        .multilineTextAlignment(.leading)
                }
                .buttonStyle(.plain)
                let sub = HomeText.weekSubtitle(night, today: today)
                if !sub.isEmpty { Text(sub).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted).lineLimit(1) }
            }
            Spacer(minLength: 8)
            if night.date == today {
                Pill(text: night.isActive ? tr("Live") : tr("Today"), color: night.isActive ? CeolTokens.primary : CeolTokens.textMuted)
            } else if night.logComplete {
                Text("Logged").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            }
        }
        .padding(.vertical, 12)
        .contentShape(Rectangle())
        .onTapGesture(perform: openNight)
    }
}

private struct Stat: View {
    let number: Int
    let label: String

    var body: some View {
        VStack(spacing: 2) {
            Text("\(number)").font(.ceol(size: 28, weight: .semibold, relativeTo: .title)).foregroundStyle(CeolTokens.primary)
            Text(label.uppercased()).font(.ceol(size: 11, weight: .medium, relativeTo: .caption2)).tracking(0.8)
                .foregroundStyle(CeolTokens.textMuted)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(CeolTokens.bgColor, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
    }
}

// MARK: - Home's words in Irish (spec 057)

/// HomeRules' sentences, as Home shows them. English is exactly what HomeRules returns
/// (held to the web's fixtures); in Irish the same decisions are put in Irish words,
/// times on the 24-hour clock and dates in Irish.
enum HomeText {
    private static var irish: Bool { AppLanguage.code == "ga" }

    static func statusLabel(_ n: HomeNight) -> String {
        guard irish else { return HomeRules.statusLabel(n) }
        switch HomeRules.status(n) {
        case .live: return tr("Live now")
        case .finished: return tr("Finished")
        case .upcoming:
            let start = time(n.startTime)
            return start.isEmpty ? tr("Today") : tr("Starts \(start)")
        }
    }

    static func todaySubtitle(_ n: HomeNight) -> String {
        guard irish else { return HomeRules.todaySubtitle(n) }
        var parts: [String] = []
        let when = timeRange(start: n.startTime, end: n.endTime)
        if !when.isEmpty { parts.append(when) }
        if let loc = n.locationName, !loc.isEmpty { parts.append(loc) }
        if HomeRules.status(n) == .live && n.peopleHere > 0 {
            parts.append(n.peopleHere == 1 ? tr("1 person here") : tr("\(n.peopleHere) people here"))
        }
        return parts.joined(separator: " · ")
    }

    static func tallyLabel(_ n: HomeNight) -> String {
        guard irish else { return HomeRules.tallyLabel(n) }
        let count = n.tunesLogged
        if count == 0 { return tr("No tunes logged yet") }
        if HomeRules.status(n) == .live {
            return count == 1 ? tr("1 tune logged so far") : tr("\(count) tunes logged so far")
        }
        return count == 1 ? tr("1 tune logged") : tr("\(count) tunes logged")
    }

    static func weekSubtitle(_ n: HomeNight, today: String?) -> String {
        guard irish else { return HomeRules.weekSubtitle(n, today: today) }
        var parts: [String] = []
        let when = timeRange(start: n.startTime, end: n.endTime)
        if !when.isEmpty { parts.append(when) }
        if let loc = n.locationName, !loc.isEmpty { parts.append(loc) }
        if n.logComplete {
            parts.append(tr("logged"))
        } else if let today, n.date < today {
            parts.append(tr("not logged"))
        }
        return parts.joined(separator: " · ")
    }

    // A day's fold (HomeRules.nightItems): the same decisions, in Irish words.

    static func groupStatusLabel(_ g: HomeGroup) -> String {
        guard irish else { return HomeRules.groupStatusLabel(g) }
        switch HomeRules.groupStatus(g) {
        case .live: return tr("\(g.live.count) on now")
        case .finished: return tr("Finished")
        case .upcoming:
            let start = time(g.nights.first?.startTime)
            return start.isEmpty ? tr("Today") : tr("Starts \(start)")
        }
    }

    static func groupSubtitle(_ g: HomeGroup) -> String {
        guard irish else { return HomeRules.groupSubtitle(g) }
        return tr("\(g.nights.count) sessions today")
    }

    static func groupTally(_ g: HomeGroup) -> String {
        guard irish else { return HomeRules.groupTally(g) }
        if !g.liveRooms.isEmpty { return g.liveRooms.joined(separator: ", ") }
        if g.tunesLogged == 0 { return tr("No tunes logged yet") }
        return g.tunesLogged == 1 ? tr("1 tune logged") : tr("\(g.tunesLogged) tunes logged")
    }

    static func groupWeekSubtitle(_ g: HomeGroup, today: String?) -> String {
        guard irish else { return HomeRules.groupWeekSubtitle(g, today: today) }
        var parts = [tr("\(g.nights.count) sessions")]
        if !g.live.isEmpty {
            parts.append(tr("\(g.live.count) on now"))
        } else if g.allFinished {
            parts.append(tr("logged"))
        } else if let today, g.date < today {
            parts.append(tr("not logged"))
        }
        return parts.joined(separator: " · ")
    }

    static func dayOfWeek(_ ymd: String) -> String {
        guard irish else { return HomeRules.dayOfWeek(ymd) }
        return day(ymd).map { format($0, "EEE") } ?? ""
    }

    static func shortDate(_ ymd: String, currentYear: Int?) -> String {
        guard irish else { return HomeRules.shortDate(ymd, currentYear: currentYear) }
        guard let d = day(ymd) else { return "" }
        let year = Calendar.current.component(.year, from: d)
        return format(d, currentYear != nil && year != currentYear ? "d MMM yyyy" : "d MMM")
    }

    static func editedLabel(_ iso: String?, currentYear: Int?, now: Date = Date()) -> String {
        guard irish else { return HomeRules.editedLabel(iso, currentYear: currentYear, now: now) }
        guard let iso, let then = ISO8601DateFormatter.flexible(iso) else { return "" }
        let mins = Int(now.timeIntervalSince(then) / 60)
        if mins < 1 { return tr("just now") }
        if mins < 60 { return mins == 1 ? tr("1 minute ago") : tr("\(mins) minutes ago") }
        let hours = mins / 60
        if hours < 24 { return hours == 1 ? tr("1 hour ago") : tr("\(hours) hours ago") }
        let year = Calendar.current.component(.year, from: then)
        return format(then, currentYear != nil && year != currentYear ? "d MMM yyyy" : "d MMM")
    }

    /// "Finish logging …" / "Place tunes on …", from the payload the item was made from.
    static func continueTitle(_ item: HomeRules.ContinueItem, _ home: HomePayload) -> String {
        guard irish else { return item.title }
        switch item.kind {
        case .log:
            guard let log = home.inProgressLogs.first(where: { $0.sessionInstanceId == item.sessionInstanceID })
            else { return item.title }
            return tr("Finish logging \(log.name)")
        case .recording:
            guard let rec = recording(item, home) else { return item.title }
            return tr("Place tunes on \((rec.label?.isEmpty == false ? rec.label : nil) ?? rec.name)")
        }
    }

    static func continueDetail(_ item: HomeRules.ContinueItem, _ home: HomePayload) -> String {
        guard irish else { return item.detail }
        switch item.kind {
        case .log:
            return shortDate(item.date, currentYear: home.currentYear)
        case .recording:
            guard let rec = recording(item, home) else { return item.detail }
            let placed = rec.tuneCount == 1 ? tr("1 tune placed") : tr("\(rec.tuneCount) tunes placed")
            return tr("\(rec.placed) of \(placed)")
        }
    }

    private static func recording(_ item: HomeRules.ContinueItem, _ home: HomePayload)
        -> (label: String?, name: String, placed: Int, tuneCount: Int)?
    {
        home.inProgressRecordings.first { "rec-\($0.recordingId)" == item.id }
            .map { (label: $0.label, name: $0.name, placed: $0.placed, tuneCount: $0.tuneCount) }
    }

    /// "19:00" from "19:00:00".
    private static func time(_ t: String?) -> String {
        guard let t, !t.isEmpty else { return "" }
        let parts = t.split(separator: ":", omittingEmptySubsequences: false)
        guard let h = Int(parts[0]), parts.count > 1 else { return "" }
        return String(format: "%02d:%@", h, String(parts[1]))
    }

    private static func timeRange(start: String?, end: String?) -> String {
        guard let start, !start.isEmpty else { return "" }
        if let end, !end.isEmpty { return time(start) + "-" + time(end) }
        return time(start) + " - ?"
    }

    /// A "YYYY-MM-DD" as that day here (parsed with en_US_POSIX, as HomeRules does).
    private static func day(_ ymd: String) -> Date? {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: ymd)
    }

    private static func format(_ date: Date, _ template: String) -> String {
        let f = DateFormatter()
        f.locale = AppLanguage.locale
        f.timeZone = .current
        f.setLocalizedDateFormatFromTemplate(template)
        return f.string(from: date)
    }
}
