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
    @State private var sort: SessionsRules.Sort = .name
    @State private var country = ""
    @State private var filtering = false
    @State private var adding = false

    var body: some View {
        @Bindable var model = model
        NavigationStack(path: $model.sessionsPath) {
            Loaded(state: state, retry: load) { payload in list(payload) }
                .background(CeolTokens.bgColor)
                .ceolRootBar("Sessions", sharePath: "/sessions")
                .modifier(SessionDestinations())
                .sheet(isPresented: $filtering) {
                    SessionsFilterSheet(
                        filter: $filter, sort: $sort, country: $country,
                        // Only countries with sessions under the other choices, so none is empty.
                        countries: SessionsRules.countries((state.value?.sessions ?? []).map(\.entry).filter {
                            SessionsRules.matches($0, filter: filter, search: search, today: localToday())
                        }))
                }
                .sheet(isPresented: $adding) {
                    AddSessionView { path, name in
                        model.sessionsPath.append(.session(path: path, name: name))
                        Task { await load() }
                    }
                }
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
        let passing = payload.sessions.filter {
            SessionsRules.matches($0.entry, filter: filter, search: search, today: today)
                && SessionsRules.inCountry($0.entry, country)
        }
        let shown = SessionsRules.sorted(passing.map(\.entry), by: sort) { !passing[$0].activeInstances.isEmpty }
            .map { passing[$0] }
        List {
            VStack(alignment: .leading, spacing: 8) {
                SearchRow(
                    text: $search, prompt: "Search by name or location…", fieldID: "sessions.search",
                    onAdd: { adding = true }, addID: "sessions.add", addLabel: "Add a session",
                    onFilter: { filtering = true },
                    filterCount: (filter != .mine ? 1 : 0) + (sort != .name ? 1 : 0) + (country.isEmpty ? 0 : 1))
                Text("\(shown.count) \(filter.countNoun)").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            }
            .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 8, trailing: 16))
            .listRowBackground(CeolTokens.bgColor)
            .listRowSeparator(.hidden)
            ForEach(shown, id: \.sessionId) { s in
                ZStack {
                    NavigationLink(value: Route.session(path: s.path, name: s.name)) { EmptyView() }.opacity(0)
                    HStack(spacing: 10) {
                        Text(s.name).font(.ceol(size: 19, weight: .medium)).foregroundStyle(CeolTokens.textColor).lineLimit(1)
                        Spacer(minLength: 6)
                        if let night = s.activeInstances.first {
                            // As on the web: straight into tonight's log.
                            Button {
                                model.sessionsPath.append(.session(path: s.path, name: s.name))
                                model.sessionsPath.append(.night(id: night.sessionInstanceId, title: "\(s.name) · Tonight"))
                            } label: {
                                Pill(text: "On Now", style: .filled, color: CeolTokens.primaryFill)
                            }
                            .buttonStyle(.borderless)
                            .accessibilityLabel("\(s.name) is on now: open tonight's log")
                        }
                        Text(SessionsRules.locationLabel(
                            city: s.city, state: s.state, country: s.country, viewerCountry: payload.viewerCountry))
                            .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted).lineLimit(1)
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityAddTraits(.isButton)
                .ceolRow()
            }
            VStack(spacing: 4) {
                if shown.isEmpty { Text("No sessions found.").foregroundStyle(CeolTokens.textMuted) }
                (Text("Don't see your session?\n")
                    + Text("Search all sessions").foregroundStyle(CeolTokens.primary)
                    + Text(" or ")
                    + Text("add it!").foregroundStyle(CeolTokens.primary))
                    .font(.ceol(size: 17))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(CeolTokens.textMuted)
                    .onTapGesture {
                        if filter == .all { adding = true } else { filter = .all }
                    }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 24)
            .listRowBackground(CeolTokens.bgColor)
            .listRowSeparator(.hidden)
        }
        .ceolPlainList()
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
    @State private var addingNight = false
    @State private var editingRole = false
    @State private var aboutOpen = false
    /// The session's details, folded under its band until tapped (as on the web).
    @State private var infoOpen = false
    @State private var openTune: TuneRef?
    @State private var newNight: NewNight?

    /// A night just added, to go straight to.
    struct NewNight: Identifiable, Hashable {
        let id: Int
        let title: String
    }

    var body: some View {
        Loaded(state: state, retry: load) { d in content(d) }
            .background(CeolTokens.bgColor)
            .ceolPushedBar(name)
            .toolbar {
                // The web's Share: a link to this page, for someone without the app too.
                ToolbarItem(placement: .topBarTrailing) { ShareButton(path: "/sessions/\(path)/\(tab.rawValue.lowercased())", subject: name) }
                    .sharedBackgroundVisibility(.hidden)
            }
            .navigationDestination(item: $newNight) { NightView(sessionInstanceID: $0.id, title: $0.title) }
            .sheet(isPresented: $editingRole) {
                if let p = state.value?.permissions, let relationship = p.relationship {
                    RoleSheet(path: path, relationship: relationship, isAdmin: p.isSessionAdmin) {
                        await load()
                        people = .loading
                    }
                }
            }
            .sheet(item: $openTune) { TuneSheet(tune: $0) }
            .sheet(isPresented: $addingNight) {
                AddNightView(path: path, usualVenue: state.value?.session.locationName) { id, date in
                    logs = .loading
                    newNight = NewNight(id: id, title: "\(name) · \(HomeRules.shortDate(date, currentYear: nil))")
                    Task { await load() }
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
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // The session's band, in the style of a night's header: its name and a
                // chevron. The details fold away under it so the tabs sit right below
                // the name; a tap opens them. The web's session page is the same.
                Button { withAnimation(.easeOut(duration: 0.2)) { infoOpen.toggle() } } label: {
                    HStack(spacing: 10) {
                        Text(d.session.name).font(.ceol(size: 24, weight: .semibold, relativeTo: .title2))
                            .foregroundStyle(CeolTokens.textColor)
                            .multilineTextAlignment(.leading)
                        Spacer(minLength: 8)
                        Image(systemName: "chevron.right").font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(CeolTokens.textMuted)
                            .rotationEffect(.degrees(infoOpen ? 90 : 0))
                    }
                    .padding(.horizontal, 14).padding(.vertical, 12)
                    .background(Color(red: 0.11, green: 0.114, blue: 0.133), in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Color(red: 0.204, green: 0.208, blue: 0.239), lineWidth: 1))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("session.band")
                .accessibilityValue(infoOpen ? "details shown" : "details hidden")
                .accessibilityHint("Shows the session's details")
                .padding(.horizontal, 20)
                if infoOpen {
                    about(d)
                        .padding(.horizontal, 20)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }
                // The one thing you came for mid-session: tonight's log.
                ForEach(d.activeInstances, id: \.sessionInstanceId) { night in
                    NavigationLink(value: Route.night(id: night.sessionInstanceId, title: "\(d.session.name) · Tonight")) {
                        HStack(spacing: 12) {
                            Image(systemName: "dot.radiowaves.left.and.right").foregroundStyle(CeolTokens.primary)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("On now").font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                                Text(HomeRules.instanceTimeLabel(start: night.startTime, end: night.endTime))
                                    .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                            }
                            Spacer()
                            Image(systemName: "chevron.right").foregroundStyle(CeolTokens.textMuted)
                        }
                        .padding(14)
                        .background(CeolTokens.primaryFill.opacity(0.25), in: RoundedRectangle(cornerRadius: 8))
                        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.primaryFill, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .padding(.horizontal, 20)
                }
                JoinPrompt(path: path, permissions: d.permissions) {
                    await load()
                    people = .loading
                }
                .padding(.horizontal, 20)
                VStack(spacing: 0) {
                    UnderlineTabs(items: tabs.map { ($0, $0.rawValue, count($0, d)) }, selection: $tab)
                    switch tab {
                    case .tunes: tunes(d)
                    case .logs: logsSection(d)
                    case .people: peopleSection()
                    }
                }
            }
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .refreshable {
            await load()
            if tab == .logs { await loadLogs() }
            if tab == .people { await loadPeople() }
        }
    }

    private func count(_ t: Tab, _ d: SessionDetailPayload) -> Int? {
        switch t {
        case .tunes: d.totalTunesCount
        case .logs: d.totalLogsCount
        case .people: d.totalPeopleCount
        }
    }

    /// The web's info card: your role, then Location, Schedule and About with bold
    /// labels, the about text folded to two lines with "more".
    @ViewBuilder private func about(_ d: SessionDetailPayload) -> some View {
        let s = d.session
        VStack(alignment: .leading, spacing: 10) {
            if let relationship = d.permissions.relationship {
                Button { editingRole = true } label: {
                    Pill(
                        text: d.permissions.isSessionAdmin ? "Admin" : relationship == "visitor" ? "Visitor" : "Member",
                        style: .filled,
                        color: relationship == "visitor" && !d.permissions.isSessionAdmin
                            ? Color(red: 0.55, green: 0.45, blue: 0.15) : CeolTokens.primaryFill,
                        size: 15)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("session.role")
                .accessibilityLabel("You're \(d.permissions.isSessionAdmin ? "Admin" : relationship == "visitor" ? "Visitor" : "Member")")
            }
            if let venue = s.locationName, !venue.isEmpty {
                labelled("Location", venue)
            }
            let place = [s.locationStreet, s.city, s.state, s.country].compactMap { $0 }.filter { !$0.isEmpty }
            if !place.isEmpty || s.locationWebsite != nil {
                HStack(spacing: 6) {
                    if !place.isEmpty { Text(place.joined(separator: ", ")).foregroundStyle(CeolTokens.textColor) }
                    if let site = s.locationWebsite, let url = URL(string: site) {
                        if !place.isEmpty { Text("•").foregroundStyle(CeolTokens.textMuted) }
                        Link("Web", destination: url).foregroundStyle(CeolTokens.primary)
                    }
                }
                .font(.ceol(size: 16))
            }
            if let schedule = s.recurrenceReadable, !schedule.isEmpty {
                labelled("Schedule", schedule)
            }
            if let about = s.comments, !about.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    labelled("About this session", about).lineLimit(aboutOpen ? nil : 2)
                    Button(aboutOpen ? "less" : "more …") { aboutOpen.toggle() }
                        .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                }
            }
            if d.permissions.relationship != nil && !d.permissions.isConfirmed && d.session.showPeopleList {
                Text("A session admin can confirm you to show you who else plays here.")
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
    }

    private func labelled(_ label: String, _ value: String) -> Text {
        (Text("\(label): ").font(.ceol(size: 16, weight: .semibold)) + Text(value).font(.ceol(size: 16)))
            .foregroundStyle(CeolTokens.textColor)
    }

    @ViewBuilder private func tunes(_ d: SessionDetailPayload) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(d.totalTunesCount == 1 ? "1 tune" : "\(d.totalTunesCount) tunes")
                .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                .padding(.horizontal, 16).padding(.vertical, 10)
            Hairline()
            ForEach(d.tunes, id: \.tuneId) { t in
                Button {
                    openTune = TuneRef(id: t.tuneId, name: t.tuneName, type: t.tuneType, sessionPath: path, statusKnown: false)
                } label: {
                    HStack(spacing: 8) {
                        Text(t.tuneName).font(.ceol(size: 19, weight: .medium)).foregroundStyle(CeolTokens.textColor).lineLimit(1)
                        Spacer(minLength: 6)
                        if let type = t.tuneType { TypeChip(label: type, size: 15) }
                        CountBox(count: t.playCount)
                    }
                    .padding(.horizontal, 16).padding(.vertical, 12)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("session.tune")
                Hairline()
            }
            if d.hasMoreTunes {
                Text("The \(d.tunes.count) most played of \(d.totalTunesCount).")
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    .padding(16)
            }
        }
    }

    @ViewBuilder private func logsSection(_ d: SessionDetailPayload) -> some View {
        switch logs {
        case .loading:
            ProgressView().padding(24).task { await loadLogs() }
        case .failed(let message):
            VStack(spacing: 8) {
                Text(message).foregroundStyle(CeolTokens.textMuted)
                Button("Retry") { Task { await loadLogs() } }
            }
            .padding(24)
        case .loaded(let l):
            VStack(alignment: .leading, spacing: 0) {
                if d.permissions.isLoggedIn {
                    Button { addingNight = true } label: {
                        Label("Add a night", systemImage: "plus").font(.ceol(size: 17, weight: .medium))
                            .foregroundStyle(CeolTokens.primary)
                            .frame(maxWidth: .infinity, minHeight: 46)
                            .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("session.addNight")
                    .padding(16)
                }
                ForEach(l.sortedYears, id: \.self) { year in
                    let nights = l.instancesByYear.additionalProperties[String(year)] ?? []
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text(String(year)).font(.ceol(size: 24, weight: .semibold, relativeTo: .title2))
                            .foregroundStyle(CeolTokens.textColor)
                        Text(nights.count == 1 ? "1 log" : "\(nights.count) logs").font(.ceol(size: 16))
                            .foregroundStyle(CeolTokens.textMuted)
                    }
                    .padding(.horizontal, 16).padding(.top, 14).padding(.bottom, 8)
                    Hairline()
                    ForEach(nights, id: \.sessionInstanceId) { night in
                        NavigationLink(value: Route.night(id: night.sessionInstanceId, title: "\(d.session.name) · \(HomeRules.shortDate(night.date, currentYear: nil))")) {
                            HStack(spacing: 14) {
                                DateBlock(weekday: HomeRules.dayOfWeek(night.date), day: HomeRules.dayOfMonth(night.date),
                                          color: CeolTokens.textMuted)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(longDay(night.date)).font(.ceol(size: 18, weight: .medium))
                                        .foregroundStyle(CeolTokens.primary)
                                    Text([HomeRules.instanceTimeLabel(start: night.startTime, end: night.endTime),
                                          night.tuneCount == 1 ? "1 tune logged" : "\(night.tuneCount) tunes logged"]
                                        .filter { !$0.isEmpty }.joined(separator: " · "))
                                        .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                                }
                                Spacer()
                            }
                            .padding(.horizontal, 16).padding(.vertical, 12)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("\(longDay(night.date)), \(night.tuneCount) tunes")
                        Hairline()
                    }
                }
            }
        }
    }

    @ViewBuilder private func peopleSection() -> some View {
        switch people {
        case .loading:
            ProgressView().padding(24).task { await loadPeople() }
        case .failed(let message):
            VStack(spacing: 8) {
                Text(message).foregroundStyle(CeolTokens.textMuted)
                Button("Retry") { Task { await loadPeople() } }
            }
            .padding(24)
        case .loaded(let p):
            // Members first, as the web's People tab opens (visitors and archived after).
            let members = p.people.filter { $0.relationship != "visitor" && $0.archived != true }
            let others = p.people.filter { $0.relationship == "visitor" || $0.archived == true }
            VStack(alignment: .leading, spacing: 0) {
                peopleGroup("Members", members)
                if !others.isEmpty { peopleGroup("Visitors and archived", others) }
            }
        }
    }

    @ViewBuilder private func peopleGroup(_ title: String, _ people: [SessionPeoplePayload.PeoplePayloadPayload]) -> some View {
        Text(title.uppercased()).font(.ceol(size: 12, weight: .semibold)).tracking(0.8)
            .foregroundStyle(CeolTokens.textMuted)
            .padding(.horizontal, 16).padding(.top, 16).padding(.bottom, 6)
        Hairline()
        ForEach(people, id: \.personId) { person in
            PersonRow(person: person).padding(.horizontal, 16).padding(.vertical, 10)
            Hairline()
        }
    }
}

/// "Tuesday, Jan 27" from "2026-01-27".
func longDay(_ date: String) -> String {
    let parse = DateFormatter()
    parse.locale = Locale(identifier: "en_US_POSIX")
    parse.dateFormat = "yyyy-MM-dd"
    guard let d = parse.date(from: date) else { return date }
    let out = DateFormatter()
    out.locale = Locale(identifier: "en_US_POSIX")
    out.dateFormat = "EEEE, MMM d"
    return out.string(from: d)
}

private struct PersonRow: View {
    let person: SessionPeoplePayload.PeoplePayloadPayload

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(person.displayName).font(.ceol(size: 18, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                if !person.instruments.isEmpty {
                    Text(person.instruments.joined(separator: ", ")).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                }
            }
            Spacer()
            if person.isAdmin { Pill(text: "Admin", style: .filled, color: CeolTokens.primaryFill, size: 12) }
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
            .background(CeolTokens.bgColor)
            .ceolPushedBar(title)
            .toolbar {
                if let b = state.value {
                    // A night's page is its date, or its id when it has none.
                    ToolbarItem(placement: .topBarTrailing) {
                        ShareButton(
                            path: "/sessions/\(b.sessionPath)/\(b.instanceDate ?? String(sessionInstanceID))",
                            subject: "\(b.sessionName), \(b.sessionDate)")
                    }
                    .sharedBackgroundVisibility(.hidden)
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
        let tuneCount = sets.reduce(0) { $0 + $1.tunes.count }
        // As the web logger: starters only where the session tracks them, which needs
        // attendance too (spec 039). An older server doesn't say: on, as the web's default.
        let trackStarters = (b.trackSetStarters ?? true) && (b.trackAttendance ?? true)
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                // The web's night header: the session, the date and a tally, the notes.
                VStack(alignment: .leading, spacing: 4) {
                    Text(b.sessionName).font(.ceol(size: 24, weight: .semibold, relativeTo: .title2))
                        .foregroundStyle(CeolTokens.textColor)
                    Text([b.sessionDate, tuneCount == 0 ? nil : "\(tuneCount) tune\(tuneCount == 1 ? "" : "s") in \(sets.count) set\(sets.count == 1 ? "" : "s")"]
                        .compactMap { $0 }.joined(separator: " · "))
                        .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    if let notes = b.notes, !notes.isEmpty {
                        Text(notes).font(.ceolItalic(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    }
                }
                .padding(.horizontal, 20).padding(.vertical, 14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(CeolTokens.headerBg.opacity(0.5))
                VStack(spacing: 12) {
                    if sets.isEmpty {
                        Text("No tunes logged yet.").font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                            .frame(maxWidth: .infinity).padding(.vertical, 32)
                    }
                    ForEach(Array(sets.enumerated()), id: \.offset) { i, set in
                        SetCard(label: LogState.setLabel(set.tunes), starter: trackStarters ? setStarter(set.tunes) : nil) {
                            ForEach(Array(set.tunes.enumerated()), id: \.offset) { _, t in
                                Text(t["name"]?.stringValue ?? "Unknown tune")
                                    .font(.ceol(size: 19))
                                    .foregroundStyle(CeolTokens.textColor)
                                    .padding(.vertical, 9)
                            }
                        }
                        .accessibilityElement(children: .contain)
                        .accessibilityLabel("Set \(i + 1) · \(LogState.setLabel(set.tunes))")
                    }
                    if b.logComplete {
                        Text("✓ This session has been fully logged").font(.ceol(size: 16, weight: .medium))
                            .foregroundStyle(CeolTokens.textMuted).padding(.top, 12)
                    }
                }
                .padding(.horizontal, 20).padding(.top, 12).padding(.bottom, 24)
            }
        }
        .refreshable { await load() }
    }
}

/// A set's starter: the first of its tunes that names one (the web logger's
/// setStarterName).
func setStarter(_ tunes: [JSONValue]) -> String? {
    tunes.lazy.compactMap { $0["started_by_name"]?.stringValue }.first
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

extension SessionsPayload.SessionsPayloadPayload {
    var entry: SessionsRules.Entry {
        .init(name: name, city: city, state: state, country: country, terminationDate: terminationDate,
              isMember: userIsMember, relationship: userRelationship)
    }
}
