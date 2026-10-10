// A festival as a whole (spec 056): what the web's /sessions/<festival> does. The
// sessions list shows a festival as one row whose path is the festival's slug, which is
// not a session, so this asks /api/resolve: when a year is near (the window rule's
// `current`) it opens that year in place of itself; otherwise it lists the years,
// upcoming first, as the web's picker does.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

typealias ResolvePayload = Components.Schemas.Resolve

struct FestivalView: View {
    @Environment(AppModel.self) private var model
    let slug: String
    let name: String
    @State private var state: LoadState<ResolvePayload> = .loading

    var body: some View {
        Loaded(state: state, retry: load) { r in years(r) }
            .background(CeolTokens.bgColor)
            .ceolPushedBar(name)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { ShareButton(path: "/sessions/\(slug)", subject: name) }
                    .sharedBackgroundVisibility(.hidden)
            }
            .task { if state.value == nil { await load() } }
    }

    private func years(_ r: ResolvePayload) -> some View {
        List {
            ForEach(r.years ?? [], id: \.sessionId) { y in
                NavigationLink(value: Route.session(path: y.path, name: y.name ?? "\(name) \(y.year)")) {
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text(String(y.year)).font(.ceol(size: 19, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                        if let start = y.initiationDate {
                            Text(dates(start, y.terminationDate)).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                        }
                        Spacer(minLength: 6)
                        Text(y.loggedInstances == 1 ? tr("1 session logged") : tr("\(y.loggedInstances) sessions logged"))
                            .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    }
                }
                .ceolRow()
                .accessibilityIdentifier("festival.year.\(y.year)")
            }
        }
        .ceolPlainList()
    }

    private func dates(_ start: String, _ end: String?) -> String {
        let first = SessionsL10n.shortDate(start)
        guard let end, end != start else { return first }
        return "\(first) – \(SessionsL10n.shortDate(end))"
    }

    private func load() async {
        do {
            let r = try await model.auth.client.resolvePath(query: .init(path: slug)).ok.body.json
            // A year is near: open it in this screen's place, as the web's 302 does.
            if let current = r.current?.path, let path = model.sessionsPath.lastIndex(of: .festival(slug: slug, name: name)) {
                let year = r.years?.first(where: { $0.path == current })
                model.sessionsPath[path] = .session(path: current, name: year?.name ?? name)
                return
            }
            state = .loaded(r)
        } catch {
            if state.value == nil { state = .failed(loadFailureMessage(error)) }
        }
    }
}
