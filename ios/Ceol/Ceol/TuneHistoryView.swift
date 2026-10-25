// The nights a tune was played: the web's tune drawer's History tab, as a screen of its
// own. The tune sheet pushes it from its play counts, so it slides in from the right and
// Back is the sheet. Its scope is a chip row, as the web's is a droplist: at the session
// the sheet was opened from (when it was), at every session you belong to (signed in),
// or at every session on Ceol. "Played at this session" lands on the first, "At sessions
// on Ceol" on the last, and from your own list (no session) only the last two are
// there. Across sessions each row names its session. "Only when I was there" starts off
// and keeps to the nights you were at. Each night opens its log at the play, as the
// web's rows link. The list is the server's 100 most recent nights, and says so when
// there were more.
//
// i18n-converted (spec 057).

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

/// Which plays: at the sheet's session, at every session you belong to, or at every
/// session on Ceol (the web's 'general' / 'member' / 'all').
enum TuneHistoryScope: String, Hashable {
    case session, mine, all
}

/// The session a sheet was opened from, for the history's "At {name}" scope.
struct TuneHistorySession: Hashable {
    let path: String
    let name: String
}

/// What a play count pushes: the scope to land on, and the sheet's session if any.
struct TuneHistoryPush: Hashable {
    let scope: TuneHistoryScope
    let session: TuneHistorySession?
}

typealias TunePlay = Components.Schemas.TuneHistory.PlayInstancesPayloadPayload

struct TuneHistoryView: View {
    @Environment(AppModel.self) private var model
    let tune: TuneRef
    /// The sheet's session, when it has one: the "At {name}" scope.
    let session: TuneHistorySession?
    /// The scope to land on (a session's own count, or the Ceol-wide one).
    let initial: TuneHistoryScope
    /// A night tapped: opens its log at this play (the sheet closes itself first).
    let openNight: (TunePlay) -> Void

    @State private var scope: TuneHistoryScope = .all
    @State private var history: LoadState<Components.Schemas.TuneHistory> = .loading
    @State private var attendedOnly = false

    var body: some View {
        Loaded(state: history, retry: load) { h in content(h) }
            .background(TuneSheet.surface)
            .navigationTitle("History")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { scope = session == nil && initial == .session ? .all : initial }
            // Both are the server's, as on the web: the list is capped at 100 nights, so
            // narrowing here could lose older nights.
            .task(id: "\(scope.rawValue)|\(attendedOnly)") { await load() }
    }

    /// The scopes on offer: the session's own only with a session, yours only signed in.
    private var scopes: [(id: TuneHistoryScope, label: String)] {
        var all: [(id: TuneHistoryScope, label: String)] = []
        if let session { all.append((.session, tr("At \(session.name)"))) }
        if !model.isGuest { all.append((.mine, tr("My sessions"))) }
        all.append((.all, tr("All sessions")))
        return all
    }

    private func load() async {
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

    @ViewBuilder private func content(_ h: Components.Schemas.TuneHistory) -> some View {
        let plays = h.playInstances
        List {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let type = tune.type { TypeChip(label: TunesWords.type(type), size: 14) }
                    Text(tune.name).font(.ceol(size: 20, weight: .semibold)).foregroundStyle(CeolTokens.textColor).lineLimit(2)
                }
                if scopes.count > 1 {
                    ChoiceChips(label: tr("Show"), options: scopes, selection: $scope)
                        .accessibilityIdentifier("history.scope")
                }
                if !model.isGuest {
                    Toggle(isOn: $attendedOnly) {
                        Text("Only when I was there").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor)
                    }
                    .tint(CeolTokens.primary)
                    .accessibilityIdentifier("history.attended")
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
            .listRowInsets(EdgeInsets())
            .listRowBackground(Color.clear)
            .listRowSeparator(.hidden)

            if plays.isEmpty {
                Text(emptyText)
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(24)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }

            ForEach(plays, id: \.sessionInstanceTuneId) { play in
                Button { openNight(play) } label: { row(play) }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("history.night")
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
                    .listRowSeparatorTint(CeolTokens.borderColor)
            }

            if h.truncated {
                Text("Showing the 100 most recent nights.")
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .refreshable { await load() }
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
        .padding(.horizontal, 16).padding(.vertical, 12)
        .contentShape(Rectangle())
    }

    private var emptyText: String {
        if attendedOnly { return tr("No nights you were at.") }
        switch scope {
        case .session: return tr("Not played here yet.")
        case .mine: return tr("Not played at your sessions yet.")
        case .all: return tr("No plays logged yet.")
        }
    }
}
