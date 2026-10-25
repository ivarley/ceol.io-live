// History: the web tune drawer's History and Played With tabs, as the two halves of
// the app sheet's History tab (TunesViews.swift) — Played At (the nights) and Played
// With (the companions). Each pane says which plays it is showing and
// offers "Change…", which opens the choices the web's droplist holds: at the session
// the sheet came from, one of its nights, every session you belong to, or every session
// on Ceol (History); at this session, my sessions, while I was there, or globally (Played
// With). A night in History opens its log at the play, as the web's rows link; a tune in
// Played With pushes its own sheet. History is the server's 100 most recent nights, and
// says so when there were more.
//
// i18n-converted (spec 057).

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

typealias TunePlay = Components.Schemas.TuneHistory.PlayInstancesPayloadPayload
typealias TuneCompanion = Components.Schemas.TunePlayedWith.TunesPayloadPayload

/// The session a sheet was opened from.
struct TuneHistorySession: Hashable {
    let path: String
    let name: String
    let trackAttendance: Bool
}

/// Where in a night a tune came round.
struct PlayedPosition: Hashable {
    let sessionInstanceTuneID: Int
    let set: Int
    let position: Int
}

/// A night the tune was played at the sheet's session (the detail's played_instances).
struct PlayedNight: Hashable {
    let id: Int
    let date: String
    let startTime: String?
    let location: String?
    let positions: [PlayedPosition]

    /// "Tue, Sep 3, 2024 · The Snug · 19:30": the date, the room at a festival, and the
    /// time only where two nights would otherwise read alike (the web's label).
    func label(timeNeeded: Bool) -> String {
        var parts = [SessionsL10n.fullDate(date)]
        if let location, !location.isEmpty { parts.append(location) }
        if timeNeeded, let startTime, !startTime.isEmpty { parts.append(String(startTime.prefix(5))) }
        return parts.joined(separator: " · ")
    }
}

/// Which plays History shows: the web droplist's rows.
enum TuneHistoryScope: Hashable {
    case session
    case night(PlayedNight)
    case mine
    case all
}

/// Whose sets Played With counts: the web's scope buttons.
enum TunePlayedWithScope: Hashable {
    case session, mine, attended, all
}

/// The detail's counts, for the line over History's list.
struct TuneHistoryCounts {
    let here: Int
    let mine: Int?
    let all: Int
}

/// A play to open: its night's log, with the play highlighted.
struct TunePlayTarget {
    let instanceID: Int
    let sessionPath: String
    let sessionName: String
    let date: String
    let sessionInstanceTuneID: Int
}

/// History's second level: Played At (the nights) or Played With (the companions). A
/// small filled segment, so it reads as a switch within the tab, not another tab row.
enum HistorySub: Hashable { case playedAt, playedWith }

struct HistorySubTabs: View {
    @Binding var selection: HistorySub

    var body: some View {
        HStack(spacing: 4) {
            segment(.playedAt, tr("Played At"), id: "history.playedAt")
            segment(.playedWith, tr("Played With"), id: "history.playedWith")
        }
        .padding(4)
        .background(CeolTokens.bgColor, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
    }

    private func segment(_ sub: HistorySub, _ label: String, id: String) -> some View {
        let on = selection == sub
        return Button {
            withAnimation(.easeOut(duration: 0.15)) { selection = sub }
        } label: {
            Text(label).font(.ceol(size: 14, weight: on ? .semibold : .medium))
                .foregroundStyle(on ? .white : CeolTokens.textMuted)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 7)
                .background(on ? CeolTokens.primaryFill : .clear, in: RoundedRectangle(cornerRadius: 7))
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
        .accessibilityAddTraits(on ? .isSelected : [])
    }
}

/// "At Mueller Session   Change…": what a pane shows, and the way to another choice.
struct ScopeLine: View {
    let label: String
    let canChange: Bool
    let id: String
    let onChange: () -> Void

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(label).font(.ceol(size: 16, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                .accessibilityIdentifier("\(id).label")
            Spacer(minLength: 8)
            if canChange {
                Button("Change…") { onChange() }
                    .font(.ceol(size: 15, weight: .medium)).foregroundStyle(CeolTokens.primary)
                    .accessibilityIdentifier(id)
            }
        }
    }
}

/// The choices behind "Change…", one to a row, the current one ticked. Picking one
/// closes the sheet.
struct ScopeChoiceSheet<ID: Hashable>: View {
    @Environment(\.dismiss) private var dismiss
    let title: String
    let options: [(id: ID, label: String)]
    @Binding var selection: ID

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 0) {
                    ForEach(options, id: \.id) { opt in
                        let on = opt.id == selection
                        Button {
                            selection = opt.id
                            dismiss()
                        } label: {
                            HStack(spacing: 10) {
                                Text(opt.label).font(.ceol(size: 17, weight: on ? .semibold : .regular))
                                    .foregroundStyle(on ? CeolTokens.primary : CeolTokens.textColor)
                                    .multilineTextAlignment(.leading)
                                Spacer(minLength: 8)
                                if on {
                                    Image(systemName: "checkmark").font(.system(size: 15, weight: .semibold)).foregroundStyle(CeolTokens.primary)
                                }
                            }
                            .padding(.horizontal, 20).padding(.vertical, 14)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("scope.option")
                        .accessibilityAddTraits(on ? .isSelected : [])
                        Hairline().padding(.leading, 20)
                    }
                }
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.accessibilityIdentifier("scope.done") } }
        }
        .ceolDrawer([.medium, .large])
    }
}

// MARK: - History

struct TuneHistoryPane: View {
    @Environment(AppModel.self) private var model
    let tune: TuneRef
    let session: TuneHistorySession?
    /// The nights at the sheet's session, each a scope of its own.
    let nights: [PlayedNight]
    let counts: TuneHistoryCounts
    @Binding var scope: TuneHistoryScope
    /// The night the sheet was opened from, with its own setting (nil: the session's),
    /// when the viewer may change it (a member): that night's scope shows the row.
    var ownNight: (id: Int, setting: Int?, change: () -> Void)? = nil
    let openNight: (TunePlayTarget) -> Void

    @State private var history: LoadState<Components.Schemas.TuneHistory> = .loading
    @State private var attendedOnly = false
    @State private var choosing = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            ScopeLine(label: label(scope), canChange: options.count > 1, id: "history.change") { choosing = true }
            if showAttendedFilter {
                Toggle(isOn: $attendedOnly) {
                    Text("Only when I was there").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor)
                }
                .tint(CeolTokens.primary)
                .accessibilityIdentifier("history.attended")
            }
            if let line = summaryLine {
                Text(line).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                    .accessibilityIdentifier("history.summary")
            }
            if case .night(let night) = scope {
                nightContent(night)
            } else {
                Loaded(state: history, retry: load) { h in list(h) }
            }
        }
        // Both are the server's, as on the web: the list is capped at 100 nights, so
        // narrowing here could lose older nights.
        .task(id: requestKey) { await load() }
        .sheet(isPresented: $choosing) { ScopeChoiceSheet(title: tr("Show"), options: options, selection: $scope) }
    }

    /// The scopes on offer, in the web's order: the session's own, each of its nights,
    /// then (signed in) yours, then every session.
    private var options: [(id: TuneHistoryScope, label: String)] {
        var all: [(id: TuneHistoryScope, label: String)] = []
        if let session {
            all.append((.session, tr("At \(session.name)")))
            // Which nights would still read alike with the date and the room shown?
            // Those get their time too.
            var alike: [String: Int] = [:]
            for n in nights { alike["\(n.date)|\(n.location ?? "")", default: 0] += 1 }
            for n in nights {
                all.append((.night(n), tr("… on \(n.label(timeNeeded: alike["\(n.date)|\(n.location ?? "")", default: 0] > 1))")))
            }
        }
        if !model.isGuest { all.append((.mine, tr("All my sessions"))) }
        all.append((.all, tr("All sessions")))
        return all
    }

    private func label(_ s: TuneHistoryScope) -> String {
        switch s {
        case .session: tr("At \(session?.name ?? tr("this session"))")
        case .night(let n): tr("On \(n.label(timeNeeded: false))")
        case .mine: tr("All my sessions")
        case .all: tr("All sessions")
        }
    }

    /// "While I was there" filters any scope but one night (one night is where you were
    /// or weren't), and a session that doesn't track attendance has nothing to filter.
    private var showAttendedFilter: Bool {
        guard !model.isGuest else { return false }
        switch scope {
        case .night: return false
        case .session: return session?.trackAttendance != false
        case .mine, .all: return true
        }
    }

    /// The count over the list; it steps aside when the filter is on (the counts don't
    /// know about it) and on one night (the list IS the answer).
    private var summaryLine: String? {
        guard !attendedOnly else { return nil }
        switch scope {
        case .session: return tr("Played \(counts.here) times at this session")
        case .mine: return counts.mine.map { tr("Played \($0) times at my sessions") }
        case .all: return tr("Played \(counts.all) times at all sessions")
        case .night: return nil
        }
    }

    private var requestKey: String {
        switch scope {
        case .session: "session|\(attendedOnly)"
        case .night(let n): "night|\(n.id)"
        case .mine: "mine|\(attendedOnly)"
        case .all: "all|\(attendedOnly)"
        }
    }

    private func load() async {
        if case .night = scope { return }
        if history.value == nil { history = .loading }
        do {
            let h = try await model.auth.client.getTuneHistory(
                path: .init(tuneId: tune.id),
                query: .init(
                    sessionPath: scope == .session ? session?.path : nil,
                    scope: scope == .mine ? .member : nil,
                    attended: attendedOnly ? true : nil)
            ).ok.body.json
            history = .loaded(h)
        } catch {
            history = .failed(loadFailureMessage(error))
        }
    }

    @ViewBuilder private func list(_ h: Components.Schemas.TuneHistory) -> some View {
        let plays = h.playInstances
        VStack(spacing: 0) {
            if plays.isEmpty {
                Text(emptyText)
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            }
            ForEach(plays, id: \.sessionInstanceTuneId) { play in
                Button {
                    openNight(TunePlayTarget(
                        instanceID: play.sessionInstanceId, sessionPath: play.sessionPath, sessionName: play.sessionName,
                        date: play.date ?? "", sessionInstanceTuneID: play.sessionInstanceTuneId))
                } label: { row(play) }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("history.night")
                Hairline()
            }
            if h.truncated {
                Text("Showing the 100 most recent nights.")
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
        }
    }

    /// One play: the date, where in the night it came round, and a mark on the nights you
    /// were at. Across sessions the session's name takes the first line (festival years
    /// run long), with the date and the place in the night under it.
    @ViewBuilder private func row(_ play: TunePlay) -> some View {
        let date = play.date.map(SessionsL10n.fullDate) ?? ""
        let position = tr("Set \(play.setNumber), Tune \(play.positionInSet)")
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                if scope == .session {
                    Text(date).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                } else {
                    Text(play.sessionName).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor).lineLimit(2)
                    Text("\(date) · \(position)").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                }
            }
            Spacer(minLength: 8)
            if play.attended {
                Image(systemName: "checkmark.circle.fill").font(.system(size: 15)).foregroundStyle(CeolTokens.primary)
                    .accessibilityLabel(Text("You were there"))
            }
            if scope == .session {
                Text(position).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
            }
            Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.textMuted)
        }
        .padding(.vertical, 12)
        .contentShape(Rectangle())
    }

    /// One night: where the tune came round ("Set 2, Tune 1", each opening the log
    /// there), and the night's own setting when you may change it.
    @ViewBuilder private func nightContent(_ night: PlayedNight) -> some View {
        VStack(spacing: 0) {
            if night.positions.isEmpty {
                Text("Not played that night.")
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            }
            ForEach(night.positions, id: \.sessionInstanceTuneID) { p in
                Button {
                    guard let session else { return }
                    openNight(TunePlayTarget(
                        instanceID: night.id, sessionPath: session.path, sessionName: session.name,
                        date: night.date, sessionInstanceTuneID: p.sessionInstanceTuneID))
                } label: {
                    HStack(spacing: 10) {
                        Text("Set \(p.set), Tune \(p.position)").font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                        Spacer(minLength: 8)
                        Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.textMuted)
                    }
                    .padding(.vertical, 12)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("history.position")
                Hairline()
            }
            if let ownNight, ownNight.id == night.id {
                HStack(spacing: 10) {
                    Text("We played setting:").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    Text(ownNight.setting.map { "#\($0)" } ?? tr("(the session's)")).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor)
                    Spacer(minLength: 8)
                    Button("Change Setting") { ownNight.change() }
                        .font(.ceol(size: 15, weight: .medium)).foregroundStyle(CeolTokens.primary)
                        .accessibilityIdentifier("history.nightSetting")
                }
                .padding(.top, 12)
            }
        }
    }

    private var emptyText: String {
        if attendedOnly { return tr("No nights you were at.") }
        switch scope {
        case .session: return tr("Not played here yet.")
        case .mine: return tr("Not played at your sessions yet.")
        case .all, .night: return tr("No plays logged yet.")
        }
    }
}

// MARK: - Played With

struct TunePlayedWithPane: View {
    @Environment(AppModel.self) private var model
    let tune: TuneRef
    let session: TuneHistorySession?

    @State private var scope: TunePlayedWithScope
    @State private var tunes: LoadState<[TuneCompanion]> = .loading
    @State private var choosing = false

    init(tune: TuneRef, session: TuneHistorySession?) {
        self.tune = tune
        self.session = session
        // At the sheet's session; from your own list, everywhere.
        _scope = State(initialValue: session != nil ? .session : .all)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            ScopeLine(label: label(scope), canChange: options.count > 1, id: "playedwith.change") { choosing = true }
            Loaded(state: tunes, retry: load) { all in list(all) }
        }
        .task(id: scope) { await load() }
        .sheet(isPresented: $choosing) { ScopeChoiceSheet(title: tr("Show"), options: options, selection: $scope) }
    }

    private var options: [(id: TunePlayedWithScope, label: String)] {
        var all: [(id: TunePlayedWithScope, label: String)] = []
        if session != nil { all.append((.session, tr("At this session"))) }
        if !model.isGuest {
            all.append((.mine, tr("At my sessions")))
            all.append((.attended, tr("While I was there")))
        }
        all.append((.all, tr("Globally")))
        return all
    }

    private func label(_ s: TunePlayedWithScope) -> String {
        switch s {
        case .session: tr("At \(session?.name ?? tr("this session"))")
        case .mine: tr("At my sessions")
        case .attended: tr("While I was there")
        case .all: tr("Globally")
        }
    }

    private func load() async {
        if tunes.value == nil { tunes = .loading }
        do {
            let r = try await model.auth.client.getTunePlayedWith(
                path: .init(tuneId: tune.id),
                query: .init(
                    sessionPath: scope == .session ? session?.path : nil,
                    scope: scope == .mine ? .member : scope == .attended ? .attended : nil)
            ).ok.body.json
            tunes = .loaded(r.tunes)
        } catch {
            tunes = .failed(loadFailureMessage(error))
        }
    }

    @ViewBuilder private func list(_ all: [TuneCompanion]) -> some View {
        VStack(spacing: 0) {
            if all.isEmpty {
                Text(scope == .session
                    ? tr("This tune has not been played in a set with any other tune at this session yet.")
                    : tr("This tune has not been played in a set with any other tune yet."))
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            }
            ForEach(all, id: \.tuneId) { t in
                // The companion's own sheet, over this one (the web swaps the drawer's tune).
                NavigationLink(value: TuneRef(id: t.tuneId, name: t.name, type: t.tuneType, sessionPath: session?.path, statusKnown: false)) {
                    HStack(spacing: 10) {
                        Text(t.name).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor).lineLimit(2)
                        Spacer(minLength: 8)
                        if let type = t.tuneType { TypeChip(label: TunesWords.type(type), size: 13) }
                        Text("\(t.count)").font(.ceol(size: 15)).monospacedDigit().foregroundStyle(CeolTokens.textMuted)
                            .accessibilityLabel(Text("\(t.count) times together"))
                        Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.textMuted)
                    }
                    .padding(.vertical, 12)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("playedwith.row")
                Hairline()
            }
        }
    }
}
