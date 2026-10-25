// The nights a tune was played: the web's tune drawer's History tab, as a screen of its
// own. The tune sheet pushes it from its play counts ("Played at this session" gives the
// nights at that session, "At sessions on Ceol" every night on Ceol), so it slides in from
// the right and Back is the sheet. Each night opens its log at the play, as the web's
// rows link; "Only when I was there" keeps to the nights you were at (signed in). The
// list is the server's 100 most recent nights, and says so when there were more.
//
// i18n-converted (spec 057).

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

/// Which plays: at one session, or at every session on Ceol.
enum TuneHistoryScope: Hashable {
    case session(path: String, name: String)
    case all
}

typealias TunePlay = Components.Schemas.TuneHistory.PlayInstancesPayloadPayload

struct TuneHistoryView: View {
    @Environment(AppModel.self) private var model
    let tune: TuneRef
    let scope: TuneHistoryScope
    /// A night tapped: opens its log at this play (the sheet closes itself first).
    let openNight: (TunePlay) -> Void

    @State private var history: LoadState<Components.Schemas.TuneHistory> = .loading
    @State private var attendedOnly = false

    var body: some View {
        Loaded(state: history, retry: load) { h in content(h) }
            .background(TuneSheet.surface)
            .navigationTitle("History")
            .navigationBarTitleDisplayMode(.inline)
            // The filter is the server's, as on the web: the list is capped at 100
            // nights, so filtering here could lose older nights you were at.
            .task(id: attendedOnly) { await load() }
    }

    private var sessionPath: String? {
        if case .session(let path, _) = scope { return path }
        return nil
    }

    private func load() async {
        if history.value == nil { history = .loading }
        do {
            let h = try await model.auth.client.getTuneHistory(
                path: .init(tuneId: tune.id),
                query: .init(sessionPath: sessionPath, attended: attendedOnly ? true : nil)
            ).ok.body.json
            history = .loaded(h)
        } catch {
            history = .failed(loadFailureMessage(error))
        }
    }

    @ViewBuilder private func content(_ h: Components.Schemas.TuneHistory) -> some View {
        let plays = h.playInstances
        List {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 10) {
                    if let type = tune.type { TypeChip(label: TunesWords.type(type), size: 14) }
                    Text(tune.name).font(.ceol(size: 20, weight: .semibold)).foregroundStyle(CeolTokens.textColor).lineLimit(2)
                }
                Text(scopeLabel).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
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
                if case .all = scope {
                    Text(play.sessionName).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor).lineLimit(2)
                    Text("\(date) · \(position)").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                } else {
                    Text(date).font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                }
            }
            Spacer(minLength: 8)
            if play.attended {
                Image(systemName: "checkmark.circle.fill").font(.system(size: 15)).foregroundStyle(CeolTokens.primary)
                    .accessibilityLabel(Text("You were there"))
            }
            if case .session = scope {
                Text(position).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
            }
            Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.textMuted)
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .contentShape(Rectangle())
    }

    private var scopeLabel: String {
        switch scope {
        case .session(_, let name): tr("At \(name)")
        case .all: tr("At every session on Ceol")
        }
    }

    private var emptyText: String {
        if attendedOnly { return tr("No nights you were at.") }
        if case .session = scope { return tr("Not played here yet.") }
        return tr("No plays logged yet.")
    }
}
