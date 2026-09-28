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
            .ceolBackground()
            .navigationTitle("Home")
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
        List {
            Section {
                Text("Welcome back, \(home.viewer?.firstName ?? "there")")
                    .font(.title3)
                    .listRowBackground(Color.clear)
            }
            if !today.isEmpty {
                Section { TodayStrip(nights: today) { open($0) } }
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
            }
            Section {
                if week.isEmpty {
                    Text("No sessions scheduled this week.").foregroundStyle(CeolTokens.secondary)
                }
                ForEach(week, id: \.sessionInstanceId) { s in
                    Button { open(s.night) } label: { WeekRow(night: s.night, today: home.today) }
                        .buttonStyle(.plain)
                }
            } header: {
                Label("This week", systemImage: "calendar")
            }
            Section {
                HStack(spacing: 12) {
                    Stat(number: home.learningCount, label: "Learning")
                    Stat(number: home.wantToLearnCount, label: "To Learn")
                }
                .listRowBackground(Color.clear)
                if let tune = home.suggestedTune {
                    let total = home.learningCount + home.wantToLearnCount
                    Text("\(total == 0 ? "A" : "Another") tune to learn: **\(tune.name)**\(tune.tuneType.map { " (\($0))" } ?? "")")
                        .font(.subheadline)
                }
            } header: {
                Label("Learning", systemImage: "music.note")
            }
            let unfinished = HomeRules.continueItems(
                logs: home.inProgressLogs.map {
                    .init(sessionInstanceID: $0.sessionInstanceId, name: $0.name, path: $0.path, date: $0.date,
                          lastEdit: $0.lastEdit)
                },
                recordings: home.inProgressRecordings.map {
                    .init(recordingID: $0.recordingId, label: $0.label, name: $0.name, path: $0.path,
                          lastEdit: $0.lastEdit, placed: $0.placed, tuneCount: $0.tuneCount)
                },
                currentYear: home.currentYear)
            if !unfinished.isEmpty {
                Section {
                    ForEach(unfinished) { item in
                        Button {
                            path.append(.session(path: item.sessionPath, name: item.title))
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.title)
                                Text([item.detail, HomeRules.editedLabel(item.lastEdit, currentYear: home.currentYear)]
                                    .filter { !$0.isEmpty }.joined(separator: " · "))
                                    .font(.footnote).foregroundStyle(CeolTokens.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                } header: {
                    Label("Pick up where you left off", systemImage: "pencil")
                }
            }
        }
        .refreshable { await load() }
    }

    private func open(_ night: HomeNight) {
        guard let p = night.path else { return }
        path.append(.session(path: p, name: night.name))
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
            TodayCard(night: nights[0], open: open).padding(.horizontal, 16)
        } else {
            TabView {
                ForEach(Array(nights.enumerated()), id: \.offset) { _, night in
                    TodayCard(night: night, open: open).padding(.horizontal, 16)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
            .frame(height: 190)
        }
    }
}

private struct TodayCard: View {
    let night: HomeNight
    let open: (HomeNight) -> Void

    var body: some View {
        let status = HomeRules.status(night)
        Button { open(night) } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Today").font(.caption.weight(.semibold)).foregroundStyle(CeolTokens.secondary)
                    Spacer()
                    Text(HomeRules.statusLabel(night))
                        .font(.caption.weight(.semibold))
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(status == .live ? CeolTokens.primaryFill : CeolTokens.headerBg, in: Capsule())
                        .foregroundStyle(status == .live ? .white : CeolTokens.textColor)
                }
                Text(night.name).font(.title3.bold()).foregroundStyle(CeolTokens.textColor)
                let sub = HomeRules.todaySubtitle(night)
                if !sub.isEmpty { Text(sub).font(.subheadline).foregroundStyle(CeolTokens.secondary) }
                Text(HomeRules.tallyLabel(night)).font(.subheadline).foregroundStyle(CeolTokens.primary)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

private struct WeekRow: View {
    let night: HomeNight
    let today: String

    var body: some View {
        HStack(spacing: 12) {
            VStack(spacing: 0) {
                Text(HomeRules.dayOfWeek(night.date)).font(.caption2).foregroundStyle(CeolTokens.secondary)
                Text(HomeRules.dayOfMonth(night.date)).font(.title3.weight(.semibold))
            }
            .frame(width: 40)
            VStack(alignment: .leading, spacing: 2) {
                Text(night.name).foregroundStyle(CeolTokens.textColor)
                let sub = HomeRules.weekSubtitle(night, today: today)
                if !sub.isEmpty { Text(sub).font(.footnote).foregroundStyle(CeolTokens.secondary) }
            }
            Spacer()
            if night.date == today {
                Text(night.isActive ? "Live" : "Today")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(night.isActive ? CeolTokens.primary : CeolTokens.secondary)
            } else if night.logComplete {
                Text("Logged").font(.caption).foregroundStyle(CeolTokens.secondary)
            }
        }
        .contentShape(Rectangle())
    }
}

private struct Stat: View {
    let number: Int
    let label: String

    var body: some View {
        VStack(spacing: 2) {
            Text("\(number)").font(.title.bold()).foregroundStyle(CeolTokens.primary)
            Text(label).font(.caption).foregroundStyle(CeolTokens.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
    }
}
