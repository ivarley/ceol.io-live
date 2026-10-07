// Deep search from the logger's "Search" button (plan Phase 5c), the web's full-screen
// TuneSearch modal (frontend/src/TuneSearch.svelte): the whole catalogue by name, by
// notation, or both, with a type filter; each card shows the tune's opening bars. On
// request, thesession.org too, where picking a tune imports it as it's logged. And the
// escape: log the text as typed.
//
// The same search adds a tune to a session's list (the web's add pane uses TuneSearch
// too): scoped to the session, tunes already on its list dimmed, no "as typed".

import CeolDesign
import CeolLogic
import SwiftUI

/// What a tune search is for, which the server reads to mark results ("played here",
/// "in this session"): a night being logged, or a session's list.
enum TuneSearchScope {
    case instance(Int)
    case session(String)

    var queryItem: URLQueryItem {
        switch self {
        case .instance(let id): .init(name: "instance", value: String(id))
        case .session(let path): .init(name: "session", value: path)
        }
    }
}

struct DeepSearchSheet: View {
    let app: AppModel
    let scope: TuneSearchScope
    let initialQuery: String
    let preferType: String?
    var title = tr("Find a tune")
    /// Offer to log the text as typed (the logger only).
    var allowAsIs = true
    /// Close after a pick; off when the pick leads on to a next step in the same sheet.
    var closesOnPick = true
    /// The whole result picked, before `onPick` (what a next step shows of it).
    var pickedResult: ((JSONValue) -> Void)? = nil
    /// Close the panel (Cancel, a swipe to the right, or after a pick).
    let onClose: () -> Void
    /// {tune_id, name, tune_type, ...the result's fields}, {thesession_id, ...}, or {name}.
    let onPick: ([String: JSONValue]) -> Void

    enum Mode: String, CaseIterable { case mixed, name, abc }

    @State private var query = ""
    @State private var mode: Mode = .mixed
    @State private var type: String?
    @State private var results: [JSONValue] = []
    @State private var loading = false
    @State private var failed = false
    @State private var remote: [JSONValue]?
    @State private var remoteLoading = false
    @State private var remoteFailed = false

    static let types = ["jig", "reel", "slip jig", "hornpipe", "polka", "slide", "waltz", "barndance", "strathspey", "three-two", "mazurka", "march"]

    @FocusState private var fieldFocused: Bool

    var body: some View {
        // No NavigationStack of its own: it's a panel over a screen that's already in one,
        // and a stack nested there pops the screen underneath.
        VStack(spacing: 0) {
            header
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    filters
                    let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
                    if loading && results.isEmpty {
                        ProgressView().frame(maxWidth: .infinity).padding()
                    } else if failed {
                        Text("Couldn't search. Check your connection.").foregroundStyle(CeolTokens.textMuted)
                    } else if !q.isEmpty && results.isEmpty && !loading {
                        Text("No tunes found for “\(q)”.").foregroundStyle(CeolTokens.textMuted)
                    }
                    ForEach(Array(results.enumerated()), id: \.offset) { _, r in
                        card(r, remote: false)
                    }
                    if !q.isEmpty {
                        if remote == nil && mode != .abc {
                            wide(tr("🔎 Search on thesession.org for “\(q)”"), color: CeolTokens.info, id: "deep.thesession") {
                                Task { await searchTheSession(q) }
                            }
                        }
                        if allowAsIs && mode != .abc {
                            wide(tr("＋ Log “\(q)” as typed (unlinked)"), color: CeolTokens.primary, id: "deep.asIs") {
                                pick(["name": .string(q)])
                            }
                        }
                    }
                    if remoteLoading || remote != nil || remoteFailed {
                        Text("FROM THESESSION.ORG").font(.ceol(size: 12, weight: .semibold)).tracking(0.8)
                            .foregroundStyle(CeolTokens.textMuted).padding(.top, 8)
                        if remoteLoading {
                            ProgressView().frame(maxWidth: .infinity)
                        } else if remoteFailed {
                            Text("Couldn't search thesession.org.").foregroundStyle(CeolTokens.textMuted)
                        } else if remote?.isEmpty == true {
                            Text("No new tunes on thesession.org for “\(q)”.").foregroundStyle(CeolTokens.textMuted)
                        }
                        ForEach(Array((remote ?? []).enumerated()), id: \.offset) { _, r in card(r, remote: true) }
                    }
                }
                .font(.ceol(size: 15))
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
        }
        .background(CeolTokens.drawerBg)
        .task(id: "\(query)|\(mode.rawValue)|\(type ?? "")") { await search() }
        .onAppear { if query.isEmpty { query = initialQuery } }
    }

    /// Cancel, the title, and the search field.
    private var header: some View {
        VStack(spacing: 10) {
            ZStack {
                Text(title).font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                HStack {
                    Button("Cancel", action: onClose)
                        .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
                        .accessibilityIdentifier("deep.cancel")
                    Spacer()
                }
            }
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").foregroundStyle(CeolTokens.textMuted)
                TextField("", text: $query, prompt: Text(prompt).foregroundStyle(CeolTokens.textMuted))
                    .font(.ceol(size: 16)).foregroundStyle(CeolTokens.textColor)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .focused($fieldFocused)
                    .submitLabel(.search)
                    .accessibilityIdentifier("deep.field")
                if !query.isEmpty {
                    Button { query = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(CeolTokens.textMuted) }
                        .buttonStyle(.plain).accessibilityLabel("Clear search")
                }
            }
            .padding(.horizontal, 12).frame(height: 40)
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
        }
        .padding(.horizontal, 16).padding(.top, 10).padding(.bottom, 8)
        .background(CeolTokens.drawerBg)
    }

    private var prompt: String {
        switch mode {
        case .abc: tr("Search by notes, e.g. GED or EBBA…")
        case .name: tr("Search by name…")
        case .mixed: tr("Search by name or notes…")
        }
    }

    private var filters: some View {
        HStack(spacing: 8) {
            Picker("Search", selection: $mode) {
                Text("Both").tag(Mode.mixed)
                Text("By name").tag(Mode.name)
                Text("By ABC").tag(Mode.abc)
            }
            .pickerStyle(.segmented)
            Menu {
                Button("Any type") { type = nil }
                ForEach(Self.types, id: \.self) { t in Button(Self.typeLabel(t)) { type = t } }
            } label: {
                Text(type.map(Self.typeLabel) ?? tr("Any type"))
                    .font(.ceol(size: 14)).foregroundStyle(type == nil ? CeolTokens.textMuted : CeolTokens.primary)
                    .padding(.horizontal, 10).frame(height: 32)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            }
            .accessibilityIdentifier("deep.type")
        }
    }

    private func card(_ r: JSONValue, remote: Bool) -> some View {
        let payload: [String: JSONValue] =
            remote
            ? ["thesession_id": r["tune_id"] ?? .null, "tune_id": r["tune_id"] ?? .null, "name": r["name"] ?? .null,
               "tune_type": r["tune_type"] ?? .null]
            : ["tune_id": r["tune_id"] ?? .null, "name": r["name"] ?? .null, "tune_type": r["tune_type"] ?? .null]
        return Button {
            pickedResult?(r)
            pick(payload)
        } label: {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(r["name"]?.stringValue ?? "").font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                    Spacer()
                    if let t = r["tune_type"]?.stringValue { TypeChip(label: t) }
                }
                if !remote, let id = r["tune_id"]?.intValue {
                    DeepIncipit(app: app, tuneID: id, base64: r["incipit_image"]?.stringValue, canRender: r["can_render"] == true)
                }
                let badges = [
                    r["abc_only"] == true ? tr("♪ notation") : nil, r["on_list"] == true ? tr("★ on your list") : nil,
                    r["in_session"] == true ? tr("in this session") : nil,
                    r["played_here"]?.intValue.flatMap { $0 > 0 ? tr("played here \($0)×") : nil },
                    remote
                        ? (r["alias"]?.stringValue).map { tr("aka \($0)") }
                        : Self.tunebooks(r["tunebook_count"]?.intValue ?? 0),
                ].compactMap { $0 }
                if !badges.isEmpty {
                    Text(badges.joined(separator: " · ")).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            .opacity(r["in_session"] == true && (remote || !allowAsIs) ? 0.6 : 1)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(remote ? "deep.remote" : "deep.result")
    }

    /// "Reels" in the type menu: LogState's plural, capitalized, in the app's language.
    private static func typeLabel(_ t: String) -> String {
        let plural = LogState.pluralType(t)?.capitalized ?? t
        return logLabelName(plural)
    }

    /// "12 tunebooks" (English has always said "1 tunebooks" too); Irish has its plural forms.
    private static func tunebooks(_ n: Int) -> String { tr("\(n) tunebooks") }

    private func wide(_ title: String, color: Color, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(.ceol(size: 15, weight: .semibold)).foregroundStyle(color)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(color.opacity(0.5), style: StrokeStyle(lineWidth: 1, dash: [4, 3])))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }

    private func pick(_ payload: [String: JSONValue]) {
        onPick(payload)
        if closesOnPick { onClose() }
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        remote = nil
        remoteFailed = false
        guard !q.isEmpty else {
            results = []
            return
        }
        try? await Task.sleep(for: .milliseconds(160))
        guard !Task.isCancelled else { return }
        loading = true
        defer { loading = false }
        var items: [URLQueryItem] = [
            scope.queryItem, .init(name: "limit", value: "30"),
            .init(name: "q", value: q), .init(name: "mode", value: mode.rawValue),
        ]
        if let type { items.append(.init(name: "type", value: type)) }
        if let preferType { items.append(.init(name: "prefer_type", value: preferType)) }
        do {
            let r = try await app.getJSON(Self.path("/api/tunes/deep-search", items))
            guard !Task.isCancelled else { return }
            results = r["results"]?.arrayValue ?? []
            failed = false
        } catch {
            if !Task.isCancelled { failed = true }
        }
    }

    private func searchTheSession(_ q: String) async {
        remoteLoading = true
        defer { remoteLoading = false }
        var items: [URLQueryItem] = [scope.queryItem, .init(name: "q", value: q)]
        if let type { items.append(.init(name: "type", value: type)) }
        do {
            let r = try await app.getJSON(Self.path("/api/tunes/thesession-search", items))
            // Only tunes the local list doesn't already show.
            let local = Set(results.compactMap { $0["tune_id"]?.intValue })
            var seen = Set<Int>()
            remote = (r["results"]?.arrayValue ?? []).filter { t in
                guard let id = t["tune_id"]?.intValue else { return false }
                return !local.contains(id) && seen.insert(id).inserted
            }
            remoteFailed = false
        } catch {
            remoteFailed = true
        }
    }

    static func path(_ p: String, _ items: [URLQueryItem]) -> String {
        var c = URLComponents()
        c.path = p
        c.queryItems = items
        return c.string ?? p
    }
}

/// A search card's opening bars: the cached image, or rendered on demand.
struct DeepIncipit: View {
    let app: AppModel
    let tuneID: Int
    let base64: String?
    let canRender: Bool
    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image).resizable().scaledToFit()
                    .frame(maxHeight: 56)
                    .padding(4)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
            }
        }
        .task(id: tuneID) {
            if let base64, let data = Data(base64Encoded: base64) {
                image = UIImage(data: data)
            } else if canRender,
                let r = try? await app.getJSON("/api/tunes/\(tuneID)/incipit-image"),
                let s = r["image"]?.stringValue, let data = Data(base64Encoded: s)
            {
                image = UIImage(data: data)
            }
        }
    }
}

extension DeepSearchSheet {
    /// The logger's search: scoped to the night.
    init(
        model: NightModel, initialQuery: String, preferType: String?, onClose: @escaping () -> Void,
        onPick: @escaping ([String: JSONValue]) -> Void
    ) {
        self.init(app: model.app, scope: .instance(model.instanceID), initialQuery: initialQuery, preferType: preferType,
                  onClose: onClose, onPick: onPick)
    }
}
