// Giving a recording a night (spec 059): one made just listening has no night, and the
// server files recordings under nights, so the recordings list offers "Attach to a
// night". Pick the session (yours first), then one of its nights, with the ones on
// the day it was recorded at the top, or add a night on that day. A festival's row
// stands for its years: the year the recording was made in is picked by itself.
//
// i18n-converted (spec 057). Session and night names are data.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

struct AttachNightSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let recording: LocalRecording
    /// Chosen: the night's id and the recording's new title.
    let onAttach: (Int, String) -> Void

    @State private var search = ""
    @State private var path: [Pick] = []

    struct Pick: Hashable {
        let path: String
        let name: String
        let festival: Bool
    }

    var body: some View {
        NavigationStack(path: $path) {
            Resourced(resource: model.sessions) { d in sessions(d) }
                .background(CeolTokens.bgColor)
                .navigationTitle("Attach to a night")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
                .navigationDestination(for: Pick.self) { pick in
                    AttachNightsList(recording: recording, pick: pick) { id, title in
                        onAttach(id, title)
                        dismiss()
                    }
                }
        }
        .preferredColorScheme(.dark)
        .task { await model.sessions.refresh(ifOlderThan: 60) }
    }

    @ViewBuilder private func sessions(_ d: SessionsPayload) -> some View {
        let today = localToday()
        let shown = d.sessions.filter {
            SessionsRules.matches($0.entry, scope: .all, status: .all, search: search, today: today)
        }
        let mine = shown.filter(\.userIsMember)
        let others = shown.filter { !$0.userIsMember }
        List {
            SearchRow(text: $search, prompt: tr("Search by name or location…"), fieldID: "attach.search",
                      filterMenu: { EmptyView() })
                .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 8, trailing: 16))
                .listRowBackground(CeolTokens.bgColor)
                .listRowSeparator(.hidden)
            if !mine.isEmpty {
                Section(header: Text("Your sessions")) { ForEach(mine, id: \.sessionId) { row($0) } }
            }
            if !others.isEmpty {
                Section(header: Text(mine.isEmpty ? "Sessions" : "Other sessions")) { ForEach(others, id: \.sessionId) { row($0) } }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
    }

    private func row(_ s: SessionsPayload.SessionsPayloadPayload) -> some View {
        NavigationLink(value: Pick(path: s.path, name: s.name, festival: s.kind == .festival)) {
            VStack(alignment: .leading, spacing: 2) {
                Text(s.name).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                if let place = s.place?.name {
                    Text(place).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                }
            }
        }
        .listRowBackground(CeolTokens.bgColor)
        .accessibilityIdentifier("attach.session")
    }
}

/// The session's nights to choose from, the day of the recording first.
struct AttachNightsList: View {
    @Environment(AppModel.self) private var model
    let recording: LocalRecording
    let pick: AttachNightSheet.Pick
    let onAttach: (Int, String) -> Void

    /// A festival: the year the recording falls in (resolved from its row).
    @State private var yearPath: String?
    @State private var resolveFailed = false
    @State private var adding = false

    private var day: String { AttachNightsList.ymd.string(from: recording.startedAt) }

    var body: some View {
        Group {
            if let sessionPath {
                Resourced(resource: model.sessionLogs(sessionPath)) { l in nights(l, sessionPath) }
                    .task { await model.sessionLogs(sessionPath).refresh(ifOlderThan: 20) }
            } else if resolveFailed {
                ContentUnavailableView {
                    Label("Couldn't load this", systemImage: "wifi.exclamationmark")
                } description: {
                    Text("Couldn't reach Ceol. Check your connection and try again.")
                } actions: {
                    Button("Retry") { Task { await resolveYear() } }.buttonStyle(.bordered)
                }
            } else {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(CeolTokens.bgColor)
        .navigationTitle(pick.name)
        .navigationBarTitleDisplayMode(.inline)
        .task { if pick.festival { await resolveYear() } }
    }

    private var sessionPath: String? { pick.festival ? yearPath : pick.path }

    @ViewBuilder private func nights(_ l: SessionLogsPayload, _ sessionPath: String) -> some View {
        let festival = l.sessionType == "festival"
        let all: [SessionDetailView.LogNight] = festival
            ? l.sortedDays.flatMap { l.instancesByDay.additionalProperties[$0] ?? [] }
            : l.sortedYears.flatMap { l.instancesByYear.additionalProperties[String($0)] ?? [] }
        let sameDay = all.filter { $0.date == day }
        let rest = all.filter { $0.date != day }
        List {
            Section {
                ForEach(sameDay, id: \.sessionInstanceId) { night in row(night, festival: festival) }
                Button { adding = true } label: {
                    Label(tr("Add a night on \(SessionsL10n.shortDate(day))"), systemImage: "plus")
                        .font(.ceol(size: 16, weight: .medium)).foregroundStyle(CeolTokens.primary)
                }
                .listRowBackground(CeolTokens.bgColor)
                .accessibilityIdentifier("attach.addNight")
            } header: {
                Text("The day it was recorded")
            }
            if !rest.isEmpty {
                Section(header: Text("Other nights")) {
                    ForEach(rest, id: \.sessionInstanceId) { night in row(night, festival: festival) }
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .sheet(isPresented: $adding) {
            AddNightView(path: sessionPath, usualVenue: nil, onAdded: { id, date in
                onAttach(id, title(date: date, room: nil, festival: festival))
            }, initialDate: recording.startedAt)
        }
    }

    private func row(_ night: SessionDetailView.LogNight, festival: Bool) -> some View {
        let room = night.locationOverride.flatMap { $0.isEmpty ? nil : $0 }
        return Button {
            onAttach(night.sessionInstanceId, title(date: night.date, room: room, festival: festival))
        } label: {
            VStack(alignment: .leading, spacing: 2) {
                Text(festival ? (room ?? pick.name) : longDay(night.date))
                    .font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                Text([festival ? SessionsL10n.shortDate(night.date) : "",
                      SessionsL10n.timeRange(start: night.startTime, end: night.endTime),
                      night.tuneCount == 1 ? tr("1 tune logged") : tr("\(night.tuneCount) tunes logged")]
                    .filter { !$0.isEmpty }.joined(separator: " · "))
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .listRowBackground(CeolTokens.bgColor)
        .accessibilityIdentifier("attach.night")
    }

    /// The recording's title, as a night is named elsewhere: "Session · Jan 27", or at
    /// a festival the room.
    private func title(date: String, room: String?, festival: Bool) -> String {
        festival ? (room ?? "\(pick.name) · \(SessionsL10n.shortDate(date))") : "\(pick.name) · \(SessionsL10n.shortDate(date))"
    }

    /// A festival's year for the recording's date, else its nearest (spec 056).
    private func resolveYear() async {
        resolveFailed = false
        do {
            let r = try await model.auth.client.resolvePath(query: .init(path: pick.path)).ok.body.json
            let years = r.years ?? []
            let year = String(day.prefix(4))
            guard let y = years.first(where: { $0.path.hasSuffix("/\(year)") }) ?? r.current.flatMap({ c in years.first { $0.path == c.path } }) ?? years.first
            else { return resolveFailed = true }
            yearPath = y.path
        } catch {
            resolveFailed = true
        }
    }

    static let ymd: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}
