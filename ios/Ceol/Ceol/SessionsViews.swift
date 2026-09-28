// The Sessions tab (plan Phase 3b): the list, a session's page, and a night's log —
// the app's twins of the Svelte /sessions, /sessions/<path> and (read-only, until the
// logger in Phase 5) /sessions/<path>/<date>, from the same payloads.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import Foundation
import SwiftUI

typealias SessionsPayload = Components.Schemas.SessionsDirectory
typealias SessionDetailPayload = Components.Schemas.SessionDetail
typealias SessionLogsPayload = Components.Schemas.SessionLogs
typealias SessionPeoplePayload = Components.Schemas.SessionPeople
typealias LiveBootstrapPayload = Components.Schemas.LiveBootstrap

/// "YYYY-MM-DD" in the device's time zone.
func localToday() -> String {
    let f = DateFormatter()
    f.calendar = Calendar(identifier: .gregorian)
    f.locale = Locale(identifier: "en_US_POSIX")
    f.dateFormat = "yyyy-MM-dd"
    return f.string(from: Date())
}

/// The screens a tab's navigation stack can push.
struct SessionDestinations: ViewModifier {
    func body(content: Content) -> some View {
        content.navigationDestination(for: Route.self) { route in
            switch route {
            case .session(let path, let name): SessionDetailView(path: path, name: name)
            case .night(let id, let title): NightView(sessionInstanceID: id, title: title)
            }
        }
    }
}

// MARK: - The list

struct SessionsView: View {
    @Environment(AppModel.self) private var model
    @State private var state: LoadState<SessionsPayload> = .loading
    @State private var filter: SessionsRules.Filter = .mine
    @State private var search = ""
    @State private var decidedDefault = false

    var body: some View {
        NavigationStack {
            Loaded(state: state, retry: load) { payload in list(payload) }
                .ceolBackground()
                .navigationTitle("Sessions")
                .searchable(text: $search, prompt: "Name or place")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Menu {
                            Picker("Show", selection: $filter) {
                                ForEach(SessionsRules.Filter.allCases, id: \.self) { Text($0.label).tag($0) }
                            }
                        } label: {
                            Label(filter.label, systemImage: "line.3.horizontal.decrease.circle")
                        }
                    }
                }
                .modifier(SessionDestinations())
                .task { if state.value == nil { await load() } }
        }
    }

    private func load() async {
        do {
            let payload = try await model.auth.client.listSessions().ok.body.json
            // Not a member of anything yet: start on All Active, not an empty list.
            if !decidedDefault {
                decidedDefault = true
                if !payload.sessions.contains(where: \.userIsMember) { filter = .active }
            }
            state = .loaded(payload)
        } catch {
            if state.value == nil { state = .failed(loadFailureMessage(error)) }
        }
    }

    @ViewBuilder private func list(_ payload: SessionsPayload) -> some View {
        let today = localToday()
        let shown = payload.sessions.filter {
            SessionsRules.matches(
                .init(name: $0.name, city: $0.city, state: $0.state, country: $0.country,
                      terminationDate: $0.terminationDate, isMember: $0.userIsMember, relationship: $0.userRelationship),
                filter: filter, search: search, today: today)
        }
        List {
            Section {
                ForEach(shown, id: \.sessionId) { s in
                    NavigationLink(value: Route.session(path: s.path, name: s.name)) {
                        HStack {
                            Text(s.name)
                            Spacer()
                            if !s.activeInstances.isEmpty {
                                Text("On now").font(.caption.weight(.semibold)).foregroundStyle(CeolTokens.primary)
                            }
                            Text(SessionsRules.locationLabel(
                                city: s.city, state: s.state, country: s.country, viewerCountry: payload.viewerCountry))
                                .font(.footnote).foregroundStyle(CeolTokens.secondary)
                        }
                    }
                }
            } header: {
                Text("\(shown.count) \(filter.countNoun)")
            } footer: {
                if shown.isEmpty { Text("No sessions found.") }
            }
        }
        .refreshable { await load() }
    }
}

// MARK: - A session

struct SessionDetailView: View {
    @Environment(AppModel.self) private var model
    let path: String
    let name: String

    enum Tab: String, CaseIterable { case tunes = "Tunes", logs = "Logs", people = "People" }

    @State private var state: LoadState<SessionDetailPayload> = .loading
    @State private var tab: Tab = .tunes
    @State private var logs: LoadState<SessionLogsPayload> = .loading
    @State private var people: LoadState<SessionPeoplePayload> = .loading

    var body: some View {
        Loaded(state: state, retry: load) { d in content(d) }
            .ceolBackground()
            .navigationTitle(name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                // The web's Share: a link to this page, for someone without the app too.
                ToolbarItem(placement: .topBarTrailing) {
                    ShareLink(item: model.webURL("/sessions/\(path)"), subject: Text(name)) {
                        Image(systemName: "square.and.arrow.up")
                    }
                    .accessibilityLabel("Share")
                }
            }
            .task { if state.value == nil { await load() } }
    }

    private func load() async {
        do {
            let d = try await model.auth.client.getSessionDetail(path: .init(sessionPath: path)).ok.body.json
            if d.defaultTab == .logs && state.value == nil { tab = .logs }
            state = .loaded(d)
        } catch {
            if state.value == nil { state = .failed(loadFailureMessage(error)) }
        }
    }

    private func loadLogs() async {
        do {
            logs = .loaded(try await model.auth.client.getSessionLogs(path: .init(sessionPath: path)).ok.body.json)
        } catch { logs = .failed(loadFailureMessage(error)) }
    }

    private func loadPeople() async {
        do {
            people = .loaded(try await model.auth.client.getSessionPeople(path: .init(sessionPath: path)).ok.body.json)
        } catch { people = .failed(loadFailureMessage(error)) }
    }

    @ViewBuilder private func content(_ d: SessionDetailPayload) -> some View {
        let tabs: [Tab] = d.permissions.canViewPeople ? Tab.allCases : [.tunes, .logs]
        List {
            // The one thing you came for mid-session: tonight's log.
            ForEach(d.activeInstances, id: \.sessionInstanceId) { night in
                NavigationLink(value: Route.night(id: night.sessionInstanceId, title: "\(d.session.name) · Tonight")) {
                    Label {
                        VStack(alignment: .leading) {
                            Text("On now").font(.headline)
                            Text(HomeRules.instanceTimeLabel(start: night.startTime, end: night.endTime))
                                .font(.footnote).foregroundStyle(CeolTokens.secondary)
                        }
                    } icon: {
                        Image(systemName: "dot.radiowaves.left.and.right").foregroundStyle(CeolTokens.primary)
                    }
                }
            }
            about(d.session)
            Section {
                Picker("Show", selection: $tab) {
                    ForEach(tabs, id: \.self) { t in Text(label(t, d)).tag(t) }
                }
                .pickerStyle(.segmented)
                .listRowBackground(Color.clear)
            }
            switch tab {
            case .tunes: tunes(d)
            case .logs: logsSection(d)
            case .people: peopleSection()
            }
        }
        .refreshable {
            await load()
            if tab == .logs { await loadLogs() }
            if tab == .people { await loadPeople() }
        }
    }

    private func label(_ t: Tab, _ d: SessionDetailPayload) -> String {
        switch t {
        case .tunes: return "Tunes \(d.totalTunesCount)"
        case .logs: return "Logs \(d.totalLogsCount)"
        case .people: return d.totalPeopleCount.map { "People \($0)" } ?? "People"
        }
    }

    @ViewBuilder private func about(_ s: SessionDetailPayload.SessionPayload) -> some View {
        Section {
            if let schedule = s.recurrenceReadable, !schedule.isEmpty {
                LabeledContent("When", value: schedule)
            }
            let place = [s.locationName, s.locationStreet, [s.city, s.state].compactMap { $0 }.joined(separator: ", ")]
                .compactMap { $0 }.filter { !$0.isEmpty }
            if !place.isEmpty {
                LabeledContent("Where") { Text(place.joined(separator: "\n")).multilineTextAlignment(.trailing) }
            }
            if let site = s.locationWebsite, let url = URL(string: site) {
                Link("Website", destination: url)
            }
            if let about = s.comments, !about.isEmpty {
                Text(about).font(.subheadline).foregroundStyle(CeolTokens.secondary)
            }
        }
    }

    @ViewBuilder private func tunes(_ d: SessionDetailPayload) -> some View {
        Section {
            ForEach(d.tunes, id: \.tuneId) { t in
                HStack {
                    Text(t.tuneName)
                    Spacer()
                    if let type = t.tuneType { Text(type).font(.caption).foregroundStyle(CeolTokens.secondary) }
                    Text("\(t.playCount)").font(.footnote.monospacedDigit()).foregroundStyle(CeolTokens.secondary)
                        .frame(minWidth: 24, alignment: .trailing)
                }
            }
        } footer: {
            if d.hasMoreTunes {
                Text("The \(d.tunes.count) most played of \(d.totalTunesCount). The full list comes with search in a later build.")
            }
        }
    }

    @ViewBuilder private func logsSection(_ d: SessionDetailPayload) -> some View {
        switch logs {
        case .loading:
            ProgressView().task { await loadLogs() }
        case .failed(let message):
            Section {
                Text(message)
                Button("Retry") { Task { await loadLogs() } }
            }
        case .loaded(let l):
            ForEach(l.sortedYears, id: \.self) { year in
                Section(String(year)) {
                    ForEach(l.instancesByYear.additionalProperties[String(year)] ?? [], id: \.sessionInstanceId) { night in
                        NavigationLink(value: Route.night(id: night.sessionInstanceId, title: "\(d.session.name) · \(HomeRules.shortDate(night.date, currentYear: nil))")) {
                            HStack {
                                Text(HomeRules.shortDate(night.date, currentYear: nil))
                                Spacer()
                                Text(night.tuneCount == 1 ? "1 tune" : "\(night.tuneCount) tunes")
                                    .font(.footnote).foregroundStyle(CeolTokens.secondary)
                            }
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder private func peopleSection() -> some View {
        switch people {
        case .loading:
            ProgressView().task { await loadPeople() }
        case .failed(let message):
            Section {
                Text(message)
                Button("Retry") { Task { await loadPeople() } }
            }
        case .loaded(let p):
            // Members first, as the web's People tab opens (visitors and archived after).
            let members = p.people.filter { $0.relationship != "visitor" && $0.archived != true }
            let others = p.people.filter { $0.relationship == "visitor" || $0.archived == true }
            Section("Members") { ForEach(members, id: \.personId) { PersonRow(person: $0) } }
            if !others.isEmpty {
                Section("Visitors and archived") { ForEach(others, id: \.personId) { PersonRow(person: $0) } }
            }
        }
    }
}

private struct PersonRow: View {
    let person: SessionPeoplePayload.PeoplePayloadPayload

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(person.displayName)
                if person.isAdmin { Text("Admin").font(.caption).foregroundStyle(CeolTokens.primary) }
            }
            if !person.instruments.isEmpty {
                Text(person.instruments.joined(separator: ", ")).font(.footnote).foregroundStyle(CeolTokens.secondary)
            }
        }
    }
}

// MARK: - A night

/// A night's log, read-only: its tunes in sets. Ordered and split by the same rules
/// the live logger uses (CeolLogic.LogState, ported from the web in Phase 1).
struct NightView: View {
    @Environment(AppModel.self) private var model
    let sessionInstanceID: Int
    let title: String
    @State private var state: LoadState<LiveBootstrapPayload> = .loading

    var body: some View {
        Loaded(state: state, retry: load) { b in content(b) }
            .ceolBackground()
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if let b = state.value {
                    ToolbarItem(placement: .topBarTrailing) {
                        // A night's page is its date, or its id when it has none.
                        ShareLink(
                            item: model.webURL("/sessions/\(b.sessionPath)/\(b.instanceDate ?? String(sessionInstanceID))"),
                            subject: Text("\(b.sessionName), \(b.sessionDate)")
                        ) {
                            Image(systemName: "square.and.arrow.up")
                        }
                        .accessibilityLabel("Share")
                    }
                }
            }
            .task { if state.value == nil { await load() } }
    }

    private func load() async {
        do {
            state = .loaded(
                try await model.auth.client.getLiveBootstrap(path: .init(sessionInstanceId: sessionInstanceID)).ok.body.json)
        } catch {
            if state.value == nil { state = .failed(loadFailureMessage(error)) }
        }
    }

    @ViewBuilder private func content(_ b: LiveBootstrapPayload) -> some View {
        let records = b.records.compactMap { JSONValue(encoding: $0) }
        let sets = LogState.segmentByBreaks(LogState.computeOrdered(records))
        List {
            Section {
                Text(b.sessionDate).foregroundStyle(CeolTokens.secondary)
                if let notes = b.notes, !notes.isEmpty { Text(notes).font(.subheadline) }
            }
            if sets.isEmpty {
                Section { Text("No tunes logged yet.").foregroundStyle(CeolTokens.secondary) }
            }
            ForEach(Array(sets.enumerated()), id: \.offset) { i, set in
                Section("Set \(i + 1) · \(LogState.setLabel(set.tunes))") {
                    ForEach(Array(set.tunes.enumerated()), id: \.offset) { _, t in
                        Text(t["name"]?.stringValue ?? "Unknown tune")
                    }
                }
            }
        }
        .refreshable { await load() }
    }
}

extension JSONValue {
    /// Any Encodable value as JSON (a generated record, for the ported logic).
    init?<T: Encodable>(encoding value: T) {
        guard let data = try? JSONEncoder().encode(value),
            let json = try? JSONDecoder().decode(JSONValue.self, from: data)
        else { return nil }
        self = json
    }
}
