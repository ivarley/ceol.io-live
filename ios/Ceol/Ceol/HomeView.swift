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
}

extension HomePayload.UpcomingSessionsPayloadPayload {
    var night: HomeNight {
        HomeNight(
            name: name, path: path, date: date, startTime: startTime, endTime: endTime,
            locationName: locationName, isActive: isActive, logComplete: logCompleteDate != nil,
            peopleHere: peopleHere, tunesLogged: tunesLogged)
    }
}

struct HomeView: View {
    @Environment(AppModel.self) private var model
    @State private var state: LoadState<HomePayload> = .loading
    @State private var path: [Route] = []

    var body: some View {
        NavigationStack(path: $path) {
            Loaded(state: state, retry: load) { home in
                content(home)
            }
            .background(CeolTokens.bgColor)
            .ceolRootBar("Home")
            .modifier(SessionDestinations())
            .task { if state.value == nil { await load() } }
        }
    }

    private func load() async {
        do {
            state = .loaded(try await model.auth.client.getHome().ok.body.json)
        } catch {
            if state.value == nil { state = .failed(loadFailureMessage(error)) }
        }
    }

    @ViewBuilder private func content(_ home: HomePayload) -> some View {
        let week = home.upcomingSessions
        let today = HomeRules.todaysSessions(week.map(\.night), today: home.today)
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                (Text("Welcome back, ") + Text(home.viewer?.firstName ?? "there").font(.ceol(size: 26, weight: .semibold)))
                    .font(.ceol(size: 26, weight: .light, relativeTo: .title))
                    .foregroundStyle(CeolTokens.textColor)
                if !today.isEmpty {
                    TodayStrip(nights: today) { n in
                        openNight(n, id: week.first { $0.path == n.path && $0.date == n.date && $0.name == n.name }?.sessionInstanceId)
                    }
                }
                VStack(alignment: .leading, spacing: 0) {
                    SectionHeading(title: "This week", icon: "TabSessions")
                    if week.isEmpty {
                        Text("No sessions scheduled this week.").foregroundStyle(CeolTokens.textMuted).padding(.vertical, 16)
                    }
                    ForEach(week, id: \.sessionInstanceId) { s in
                        WeekRow(night: s.night, today: home.today) {
                            openNight(s.night, id: s.sessionInstanceId)
                        } openSession: {
                            path.append(.session(path: s.path, name: s.name))
                        }
                        Rectangle().fill(CeolTokens.borderColor).frame(height: 1)
                    }
                }
                VStack(alignment: .leading, spacing: 14) {
                    SectionHeading(title: "Learning", icon: "TabTunes") {
                        Button("See all") { model.tab = .tunes }
                            .font(.ceol(size: 16))
                            .foregroundStyle(CeolTokens.primary)
                    }
                    HStack(spacing: 12) {
                        Stat(number: home.learningCount, label: "Learning")
                        Stat(number: home.wantToLearnCount, label: "To Learn")
                    }
                    if let tune = home.suggestedTune {
                        let total = home.learningCount + home.wantToLearnCount
                        (Text("\(total == 0 ? "A" : "Another") tune to learn: ")
                            + Text(tune.name).foregroundStyle(CeolTokens.primary)
                            + Text(tune.tuneType.map { " (\($0))" } ?? "").foregroundStyle(CeolTokens.textMuted))
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
                      lastEdit: $0.lastEdit)
            },
            recordings: home.inProgressRecordings.map {
                .init(recordingID: $0.recordingId, label: $0.label, name: $0.name, path: $0.path,
                      lastEdit: $0.lastEdit, placed: $0.placed, tuneCount: $0.tuneCount, date: $0.date)
            },
            currentYear: home.currentYear)
        if !unfinished.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                SectionHeading(title: "Pick up where you left off", icon: "IconPencil")
                ForEach(unfinished) { item in
                    Button {
                        if let id = item.sessionInstanceID {
                            path.append(.night(id: id, title: item.title))
                        } else {
                            path.append(.session(path: item.sessionPath, name: item.title))
                        }
                    } label: {
                        HStack(spacing: 14) {
                            DateBlock(weekday: HomeRules.dayOfWeek(item.date), day: HomeRules.dayOfMonth(item.date))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.title).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.primary)
                                Text([item.detail, HomeRules.editedLabel(item.lastEdit, currentYear: home.currentYear)]
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
    private func openNight(_ night: HomeNight, id: Int?) {
        guard let id else {
            if let p = night.path { path.append(.session(path: p, name: night.name)) }
            return
        }
        path.append(.night(id: id, title: "\(night.name) · \(HomeRules.shortDate(night.date, currentYear: nil))"))
    }
}

// MARK: - Pieces

/// Today's nights: one card, or a paged strip when there are several — at a festival
/// the thing to see is that there are three.
private struct TodayStrip: View {
    let nights: [HomeNight]
    let open: (HomeNight) -> Void

    var body: some View {
        if nights.count == 1 {
            TodayCard(night: nights[0], open: open)
        } else {
            TabView {
                ForEach(Array(nights.enumerated()), id: \.offset) { _, night in
                    TodayCard(night: night, open: open).padding(.bottom, 30)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
            .frame(height: 250)
        }
    }
}

/// The web's today card: a green left edge, "TODAY" in capitals, the status pill, the
/// session, what's been logged, and a green View button into the night.
private struct TodayCard: View {
    let night: HomeNight
    let open: (HomeNight) -> Void

    var body: some View {
        let status = HomeRules.status(night)
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("TODAY").font(.ceol(size: 13, weight: .medium)).tracking(1.2).foregroundStyle(CeolTokens.textMuted)
                Spacer()
                Pill(
                    text: HomeRules.statusLabel(night), style: status == .live ? .filled : .outline,
                    color: status == .live ? CeolTokens.primaryFill : CeolTokens.textColor)
            }
            Text(night.name).font(.ceol(size: 22, weight: .semibold, relativeTo: .title2)).foregroundStyle(CeolTokens.textColor)
            let sub = HomeRules.todaySubtitle(night)
            if !sub.isEmpty { Text(sub).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor.opacity(0.85)) }
            Text(HomeRules.tallyLabel(night)).font(.ceol(size: 15))
                .foregroundStyle(night.tunesLogged > 0 ? CeolTokens.primary : CeolTokens.textMuted)
            Button { open(night) } label: {
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
        .onTapGesture { open(night) }
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
            DateBlock(weekday: HomeRules.dayOfWeek(night.date), day: HomeRules.dayOfMonth(night.date))
            VStack(alignment: .leading, spacing: 2) {
                Button(action: openSession) {
                    Text(night.name).font(.ceol(size: 18, weight: .medium)).foregroundStyle(CeolTokens.primary)
                        .multilineTextAlignment(.leading)
                }
                .buttonStyle(.plain)
                let sub = HomeRules.weekSubtitle(night, today: today)
                if !sub.isEmpty { Text(sub).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted).lineLimit(1) }
            }
            Spacer(minLength: 8)
            if night.date == today {
                Pill(text: night.isActive ? "Live" : "Today", color: night.isActive ? CeolTokens.primary : CeolTokens.textMuted)
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
