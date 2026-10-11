// Deep search from the logger's "Search" button (plan Phase 5c), the web's full-screen
// TuneSearch modal (frontend/src/TuneSearch.svelte): the whole catalogue by name, by
// notation, or both, with a filter button for the mode and the tune type; each card
// shows the tune's opening bars. Tapping a card opens its preview (TunePreviewPane,
// the web's TunePreview.svelte): a look before you log, with every setting to page
// through and choose; the card's ＋ logs it in one tap. On request, thesession.org too,
// where picking a tune imports it as it's logged. And the escape: log the text as typed.
//
// The same search adds a tune to a session's list (the web's add pane uses TuneSearch
// too): scoped to the session, tunes already on its list dimmed, no "as typed".
//
// i18n-converted (spec 057).

import CeolDesign
import CeolLogic
import SwiftUI
import UIKit

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

/// A result the preview can page to: the search's row, and whether it came from
/// thesession.org (an import when picked).
struct DeepSearchItem {
    let r: JSONValue
    let remote: Bool
}

struct DeepSearchSheet: View {
    let app: AppModel
    let scope: TuneSearchScope
    let initialQuery: String
    let preferType: String?
    var title = tr("Find a tune")
    /// The preview's button: what picking means here.
    var actionLabel = tr("＋ Log This Tune")
    /// Offer to log the text as typed (the logger only).
    var allowAsIs = true
    /// Close after a pick; off when the pick leads on to a next step in the same sheet.
    var closesOnPick = true
    /// The whole result picked, before `onPick` (what a next step shows of it).
    var pickedResult: ((JSONValue) -> Void)? = nil
    /// Close the panel (Cancel, a swipe to the right, or after a pick).
    let onClose: () -> Void
    /// {tune_id, name, tune_type, setting_id?, ...the result's fields}, {thesession_id, ...}, or {name}.
    let onPick: ([String: JSONValue]) -> Void

    enum Mode: String, CaseIterable { case mixed, name, abc }

    @State private var query = ""
    @State private var mode: Mode = .mixed
    @State private var type: String?
    @State private var filtersOpen = false
    @State private var results: [JSONValue] = []
    @State private var loading = false
    @State private var failed = false
    @State private var remote: [JSONValue]?
    @State private var remoteLoading = false
    @State private var remoteFailed = false
    /// The preview showing, as an index into `previewItems`.
    @State private var preview: Int?

    static let types = ["jig", "reel", "slip jig", "hornpipe", "polka", "slide", "waltz", "barndance", "strathspey", "three-two", "mazurka", "march"]

    @FocusState private var fieldFocused: Bool

    /// What the preview's ‹ › page through: the local results, then thesession.org's.
    private var previewItems: [DeepSearchItem] {
        results.map { DeepSearchItem(r: $0, remote: false) } + (remote ?? []).map { DeepSearchItem(r: $0, remote: true) }
    }

    var body: some View {
        // No NavigationStack of its own: it's a panel over a screen that's already in one,
        // and a stack nested there pops the screen underneath.
        ZStack {
            VStack(spacing: 0) {
                header
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        if filtersOpen { filterPanel } else { filterPills }
                        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
                        if loading && results.isEmpty {
                            ProgressView().frame(maxWidth: .infinity).padding()
                        } else if failed {
                            Text("Couldn't search. Check your connection.").foregroundStyle(CeolTokens.textMuted)
                        } else if !q.isEmpty && results.isEmpty && !loading {
                            Text("No tunes found for “\(q)”.").foregroundStyle(CeolTokens.textMuted)
                        }
                        ForEach(Array(results.enumerated()), id: \.offset) { i, r in
                            card(r, remote: false, index: i)
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
                            ForEach(Array((remote ?? []).enumerated()), id: \.offset) { i, r in
                                card(r, remote: true, index: results.count + i)
                            }
                        }
                    }
                    .font(.ceol(size: 15))
                    .padding(16)
                }
                .scrollDismissesKeyboard(.interactively)
            }
            .background(CeolTokens.drawerBg)
            if let i = preview, previewItems.indices.contains(i) {
                TunePreviewPane(
                    app: app, scope: scope, items: previewItems, index: i, actionLabel: actionLabel,
                    onBack: { preview = nil }
                ) { item, data, settingID in
                    pickedResult?(item.r)
                    pick(Self.payload(item, data: data, settingID: settingID))
                }
                .background(CeolTokens.drawerBg)
                .transition(.move(edge: .trailing))
                .zIndex(1)
            }
        }
        .animation(.easeOut(duration: 0.2), value: preview)
        .task(id: "\(query)|\(mode.rawValue)|\(type ?? "")") { await search() }
        .onAppear {
            if query.isEmpty { query = initialQuery }
            // The keyboard moves from the composer to this field (the web's modal
            // autofocuses it too); the preview then sends it away.
            fieldFocused = true
        }
    }

    /// Cancel, the title, the search field, and the filter button.
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
                // The web's filter button: the search mode and the tune type, in a panel.
                let filtering = filtersOpen || type != nil || mode != .mixed
                Button { withAnimation(.easeOut(duration: 0.15)) { filtersOpen.toggle() } } label: {
                    Image(systemName: "slider.horizontal.3").font(.system(size: 17, weight: .medium))
                        .foregroundStyle(filtering ? CeolTokens.primary : CeolTokens.textMuted)
                        .frame(width: 40, height: 40)
                        .background(filtering ? CeolTokens.primary.opacity(0.16) : CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Search filters")
                .accessibilityIdentifier("deep.filters")
            }
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

    /// The filter panel: By name / By ABC (tap the one that's on to go back to both),
    /// and the tune type.
    private var filterPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                modeTab(tr("By name"), .name)
                modeTab(tr("By ABC"), .abc)
                Spacer()
            }
            Menu {
                Button("Any tune type") { type = nil }
                ForEach(Self.types, id: \.self) { t in Button(Self.typeLabel(t)) { type = t } }
            } label: {
                HStack {
                    Text(type.map(Self.typeLabel) ?? tr("Any tune type"))
                        .font(.ceol(size: 15)).foregroundStyle(type == nil ? CeolTokens.textMuted : CeolTokens.textColor)
                    Spacer()
                    Image(systemName: "chevron.up.chevron.down").font(.system(size: 12)).foregroundStyle(CeolTokens.textMuted)
                }
                .padding(.horizontal, 12).frame(height: 38)
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            }
            .accessibilityLabel("Tune type")
            .accessibilityIdentifier("deep.type")
        }
        .padding(12)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
    }

    private func modeTab(_ label: String, _ m: Mode) -> some View {
        let on = mode == m
        return Button { mode = on ? .mixed : m } label: {
            Text(label).font(.ceol(size: 14, weight: on ? .semibold : .regular))
                .foregroundStyle(on ? .white : CeolTokens.textColor)
                .padding(.horizontal, 12).frame(height: 32)
                .background(on ? CeolTokens.primaryFill : .clear, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(on ? .clear : CeolTokens.borderColor, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
        .accessibilityIdentifier(m == .name ? "deep.byName" : "deep.byAbc")
    }

    /// The filters that are on, as pills while the panel is closed; a tap clears one.
    @ViewBuilder private var filterPills: some View {
        if type != nil || mode != .mixed {
            HStack(spacing: 8) {
                if mode != .mixed {
                    pill(mode == .abc ? tr("By ABC") : tr("By name")) { mode = .mixed }
                }
                if let type {
                    pill(Self.typeLabel(type)) { self.type = nil }
                }
                Spacer()
            }
        }
    }

    private func pill(_ label: String, clear: @escaping () -> Void) -> some View {
        Button(action: clear) {
            HStack(spacing: 6) {
                Text(label).font(.ceol(size: 13, weight: .medium))
                Image(systemName: "xmark").font(.system(size: 10, weight: .bold))
            }
            .foregroundStyle(CeolTokens.primary)
            .padding(.horizontal, 10).frame(height: 28)
            .background(CeolTokens.primary.opacity(0.16), in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(tr("Clear filter \(label)"))
    }

    /// A result: its body opens the preview, its ＋ logs it at once.
    private func card(_ r: JSONValue, remote: Bool, index: Int) -> some View {
        let name = r["name"]?.stringValue ?? ""
        return HStack(spacing: 0) {
            Button {
                fieldFocused = false
                preview = index
            } label: {
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(name).font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                            .multilineTextAlignment(.leading)
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
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(tr("Preview \(name)"))
            .accessibilityIdentifier(remote ? "deep.remote" : "deep.result")
            Rectangle().fill(CeolTokens.borderColor).frame(width: 1)
            Button {
                pickedResult?(r)
                pick(Self.payload(DeepSearchItem(r: r, remote: remote), data: nil, settingID: nil))
            } label: {
                Image(systemName: "plus").font(.system(size: 20, weight: .medium))
                    .foregroundStyle(CeolTokens.primary)
                    .frame(width: 48)
                    .frame(maxHeight: .infinity)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(tr("Add \(name) without previewing"))
            .accessibilityIdentifier(remote ? "deep.remoteQuick" : "deep.quick")
        }
        .fixedSize(horizontal: false, vertical: true)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        .opacity(r["in_session"] == true && (remote || !allowAsIs) ? 0.6 : 1)
    }

    /// What a pick hands on, as the web's pickDeep / pickRemote / previewAction: the
    /// catalogue tune, or thesession.org's (imported as it's logged), with the setting
    /// chosen in the preview. A remote tune the preview found to be local already is
    /// logged as that local tune, under the name the preview fetched.
    static func payload(_ item: DeepSearchItem, data: JSONValue?, settingID: Int?) -> [String: JSONValue] {
        let r = item.r
        let name = data?["name"] ?? r["name"] ?? .null
        let type = data?["tune_type"] ?? r["tune_type"] ?? .null
        var p: [String: JSONValue]
        if item.remote && !(data != nil && data?["is_local"] != false) {
            p = ["thesession_id": r["tune_id"] ?? .null, "tune_id": r["tune_id"] ?? .null, "name": name, "tune_type": type]
        } else {
            p = ["tune_id": data?["tune_id"] ?? r["tune_id"] ?? .null, "name": name, "tune_type": type]
        }
        if let settingID { p["setting_id"] = .number(Double(settingID)) }
        return p
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
        preview = nil
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
    @State private var tried = false

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image).resizable().scaledToFit()
                    .frame(maxHeight: 56)
                    .padding(4)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
            } else if canRender && !tried {
                ProgressView().tint(.gray).frame(maxWidth: .infinity, minHeight: 44)
                    .background(Color.white.opacity(0.9), in: RoundedRectangle(cornerRadius: 6))
            } else {
                Text("♪ no notation").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
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
            tried = true
        }
    }
}

// MARK: - The preview

/// A look before you log (the web's TunePreview.svelte): the tune's name and type,
/// how often it's been played here and how common it is, its other names, every
/// setting to page through (the ones Ceol holds at once, the rest from thesession.org
/// as they arrive), the notation (opening bars; tap for the whole tune) or the ABC,
/// and the button that logs it. ‹ › at the top step through the other results. A
/// setting counts as chosen only when the pager was worked: landing on the session's
/// own setting says nothing new.
struct TunePreviewPane: View {
    let app: AppModel
    let scope: TuneSearchScope
    let items: [DeepSearchItem]
    let index: Int
    let actionLabel: String
    let onBack: () -> Void
    /// The pick: the result, the preview's data (nil when it didn't load), the chosen setting.
    let onAction: (DeepSearchItem, JSONValue?, Int?) -> Void

    struct Setting: Equatable {
        let id: Int?
        let key: String?
        let abc: String
        let incipitAbc: String
        let incipitImage: String?
        /// Only thesession.org has it (a backfilled setting, or a remote tune's).
        let remote: Bool
    }

    enum NotationMode { case notes, abc }
    enum Size { case incipit, full }

    @State private var idx = 0
    @State private var data: JSONValue?
    @State private var loading = true
    @State private var failed = false
    @State private var settings: [Setting] = []
    @State private var setIdx = 0
    @State private var touched = false
    @State private var backfilling = false
    @State private var mode: NotationMode = .notes
    @State private var size: Size = .incipit
    @State private var images: [String: UIImage] = [:]
    @State private var undrawable: Set<String> = []
    @State private var aliasesExpanded = false
    @State private var loadRun = 0

    private var item: DeepSearchItem? { items.indices.contains(idx) ? items[idx] : nil }
    private var setting: Setting? { settings.indices.contains(setIdx) ? settings[setIdx] : nil }
    /// Shown from thesession.org and not in the library: an import when logged.
    private var isRemote: Bool {
        if let data { return data["is_local"] == false }
        return item?.remote == true && item?.r["is_local"] != true
    }
    private var sessionSettingID: Int? { data?["session_setting_id"]?.intValue }
    private var chosenSettingID: Int? { touched ? setting?.id : nil }
    private var tuneID: Int? { data?["tune_id"]?.intValue ?? item?.r["tune_id"]?.intValue }

    var body: some View {
        VStack(spacing: 0) {
            head
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(data?["name"]?.stringValue ?? item?.r["name"]?.stringValue ?? "")
                            .font(.ceol(size: 22, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                        if let t = data?["tune_type"]?.stringValue ?? item?.r["tune_type"]?.stringValue {
                            TypeChip(label: t, size: 14)
                        }
                    }
                    if loading {
                        ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                    } else if failed {
                        VStack(spacing: 10) {
                            Text(item?.remote == true ? tr("Couldn’t load tune details from thesession.org.") : tr("Couldn’t load tune details."))
                                .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                            Button("Try again") { Task { await load() } }.font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
                        }
                        .frame(maxWidth: .infinity)
                    } else {
                        facts
                        aliases
                        if !settings.isEmpty { settingBar }
                        notation
                        if isRemote {
                            Text("Not in the library yet — it will be imported from thesession.org when you add it.")
                                .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                }
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
            Button { if let item { onAction(item, data, chosenSettingID) } } label: {
                Text(actionLabel).font(.ceol(size: 17, weight: .semibold))
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .foregroundStyle(.white)
                    .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 16).padding(.vertical, 10)
            .accessibilityIdentifier("preview.action")
        }
        .task { idx = index; await load() }
        .onChange(of: idx) { Task { await load() } }
        .onChange(of: setIdx) { Task { await drawCurrent() } }
        .onChange(of: size) { Task { await drawCurrent() } }
        .onChange(of: mode) { if mode == .notes { Task { await drawCurrent() } } }
    }

    /// Back to the results, where this one is, and the steppers to the others.
    private var head: some View {
        HStack(spacing: 10) {
            Button(action: onBack) {
                HStack(spacing: 4) {
                    Image(systemName: "chevron.left").font(.system(size: 15, weight: .semibold))
                    Text("Results")
                }
                .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
            }
            .accessibilityIdentifier("preview.back")
            Spacer()
            Text("\(idx + 1) of \(items.count)").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
            stepButton(-1, enabled: idx > 0, label: tr("Previous result"), id: "preview.prev") { idx -= 1 }
            stepButton(1, enabled: idx < items.count - 1, label: tr("Next result"), id: "preview.next") { idx += 1 }
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
    }

    private func stepButton(_ d: Int, enabled: Bool, label: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: d < 0 ? "chevron.left" : "chevron.right").font(.system(size: 14, weight: .semibold))
                .frame(width: 36, height: 32)
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .foregroundStyle(CeolTokens.textColor)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.35)
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
    }

    /// The two facts that decide "is this the right tune?": our history with it, and
    /// how common it is.
    private var facts: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let n = data?["played_here"]?.intValue, n > 0 {
                let dates = (data?["dates"]?.arrayValue ?? []).compactMap(\.stringValue)
                (Text(verbatim: "♪ ") + Text("Played here \(n)×") + Text(verbatim: dates.isEmpty ? "" : " — ") + Text(dates.isEmpty ? "" : tr("last: \(dates.joined(separator: ", "))")))
                    .font(.ceol(size: 14, weight: .medium)).foregroundStyle(CeolTokens.warning)
            } else {
                Text("Not played here yet").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
            }
            HStack(spacing: 10) {
                (Text(verbatim: "\(data?["tunebook_count"]?.intValue ?? 0) ").bold() + Text("tunebooks"))
                    .font(.ceol(size: 14)).foregroundStyle(CeolTokens.primary)
                if item?.r["on_list"] == true {
                    Text("★ on your list").font(.ceol(size: 13)).foregroundStyle(CeolTokens.warning)
                }
            }
        }
    }

    /// "Also known as": two lines, and More … to see the rest when it's long.
    @ViewBuilder private var aliases: some View {
        let names = (data?["aliases"]?.arrayValue ?? []).compactMap(\.stringValue)
        if !names.isEmpty {
            let joined = names.joined(separator: ", ")
            VStack(alignment: .leading, spacing: 2) {
                Text("Also known as: \(joined)").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                    .lineLimit(aliasesExpanded ? nil : 2)
                if !aliasesExpanded && joined.count > 70 {
                    Button("More …") { aliasesExpanded = true }.font(.ceol(size: 14)).foregroundStyle(CeolTokens.primary)
                }
            }
        }
    }

    /// Above the notation, so paging never moves it: ‹ Setting n of N · #id · key ›.
    private var settingBar: some View {
        HStack(spacing: 8) {
            Button { stepSetting(-1) } label: { Image(systemName: "chevron.left").frame(width: 36, height: 36) }
                .disabled(setIdx == 0).opacity(setIdx == 0 ? 0.35 : 1)
                .accessibilityLabel("Previous setting").accessibilityIdentifier("preview.prevSetting")
            VStack(spacing: 1) {
                Text("Setting \(setIdx + 1) of \(settings.count)").font(.ceol(size: 14, weight: .medium))
                HStack(spacing: 6) {
                    if let s = setting {
                        Text(verbatim: [s.id.map { "#\($0)" }, s.key].compactMap { $0 }.joined(separator: " · "))
                            .foregroundStyle(CeolTokens.textMuted)
                        if let id = s.id, id == sessionSettingID {
                            (Text(verbatim: "★ ") + Text("this session’s")).foregroundStyle(CeolTokens.warning)
                        }
                    }
                }
                .font(.ceol(size: 13))
            }
            .frame(maxWidth: .infinity)
            Button { stepSetting(1) } label: {
                Group {
                    if backfilling && setIdx >= settings.count - 1 { ProgressView() } else { Image(systemName: "chevron.right") }
                }
                .frame(width: 36, height: 36)
            }
            .disabled(setIdx >= settings.count - 1).opacity(setIdx >= settings.count - 1 ? 0.35 : 1)
            .accessibilityLabel("Next setting").accessibilityIdentifier("preview.nextSetting")
        }
        .buttonStyle(.plain)
        .foregroundStyle(CeolTokens.textColor)
        .padding(.horizontal, 4).padding(.vertical, 4)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 8))
    }

    /// The notation (or the ABC), with the notes / abc tabs and the thesession.org link
    /// under it. Tapping the notation flips opening bars ⇄ the whole tune.
    private var notation: some View {
        VStack(spacing: 8) {
            Group {
                if mode == .abc {
                    if let s = setting {
                        Button { flipSize() } label: {
                            Text(verbatim: size == .full ? s.abc : s.incipitAbc)
                                .font(.system(size: 13, design: .monospaced))
                                .foregroundStyle(.black).padding(10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                        }
                        .buttonStyle(.plain)
                    } else {
                        noNotation(tr("♪ no notation"))
                    }
                } else if let s = setting, let image = images[imageKey(s)] {
                    Button { flipSize() } label: {
                        Image(uiImage: image).resizable().scaledToFit()
                            .padding(6)
                            .frame(maxWidth: .infinity)
                            .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(size == .full ? tr("notation (full)") : tr("notation (incipit)"))
                    .accessibilityHint(size == .full ? Text("Tap to show the opening bars") : Text("Tap to show the whole tune"))
                    .accessibilityIdentifier("preview.notation")
                } else if let s = setting, !undrawable.contains(imageKey(s)) {
                    Button { flipSize() } label: {
                        HStack(spacing: 8) { ProgressView().tint(.gray); Text("rendering notation…").foregroundStyle(.gray) }
                            .font(.ceol(size: 13))
                            .frame(maxWidth: .infinity, minHeight: 80)
                            .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                } else if setting != nil {
                    noNotation(tr("♪ no notation image"))
                } else {
                    noNotation(tr("♪ no notation"))
                }
            }
            HStack(spacing: 16) {
                notationTab(tr("notes"), on: mode == .notes) { mode = .notes }
                notationTab(tr("abc"), on: mode == .abc) { mode = .abc }
                    .disabled(setting == nil).opacity(setting == nil ? 0.4 : 1)
                Spacer()
                if let tuneID {
                    let sid = setting?.id
                    let url = "https://thesession.org/tunes/\(tuneID)" + (sid.map { "?setting=\($0)#setting\($0)" } ?? "")
                    Link(destination: URL(string: url)!) { Text("thesession").font(.ceol(size: 14)) }
                        .foregroundStyle(CeolTokens.primary)
                }
            }
        }
    }

    private func noNotation(_ text: String) -> some View {
        Text(text).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            .frame(maxWidth: .infinity, minHeight: 60)
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 6))
    }

    private func notationTab(_ label: String, on: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 3) {
                Text(label).font(.ceol(size: 14, weight: on ? .semibold : .regular))
                    .foregroundStyle(on ? CeolTokens.textColor : CeolTokens.textMuted)
                Rectangle().fill(on ? CeolTokens.primary : .clear).frame(height: 2)
            }
            .fixedSize()
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
    }

    private func flipSize() {
        size = size == .incipit ? .full : .incipit
    }

    private func stepSetting(_ d: Int) {
        let n = setIdx + d
        guard settings.indices.contains(n) else { return }
        setIdx = n
        touched = true
        size = .incipit
    }

    // MARK: Loading

    /// The tune's preview: a catalogue tune's from Ceol (with this night's or session's
    /// plays and names), a thesession.org tune's from there, unless Ceol turns out to
    /// hold it after all. Then the pager lands on the session's own setting, and the
    /// rest of thesession.org's settings fill in behind.
    private func load() async {
        loadRun += 1
        let run = loadRun
        guard let item else { return }
        data = nil
        loading = true
        failed = false
        settings = []
        setIdx = 0
        touched = false
        mode = .notes
        size = .incipit
        aliasesExpanded = false
        guard let id = item.r["tune_id"]?.intValue else {
            loading = false
            failed = true
            return
        }
        do {
            var d: JSONValue
            if item.remote && item.r["is_local"] != true {
                d = try await app.getJSON("/api/tunes/thesession/\(id)/preview")
                if d["is_local"] == true, let local = d["tune_id"]?.intValue {
                    d = try await app.getJSON(DeepSearchSheet.path("/api/tunes/\(local)/preview", [scope.queryItem]))
                }
            } else {
                d = try await app.getJSON(DeepSearchSheet.path("/api/tunes/\(id)/preview", [scope.queryItem]))
            }
            guard run == loadRun else { return }
            let remoteTune = d["is_local"] == false
            data = d
            settings = Self.settings(d["settings"], remote: remoteTune)
            if let sid = d["session_setting_id"]?.intValue, let i = settings.firstIndex(where: { $0.id == sid }) {
                setIdx = i
            }
            loading = false
            await drawCurrent()
            if !remoteTune { await backfill(run: run, tuneID: d["tune_id"]?.intValue ?? id) }
        } catch {
            guard run == loadRun else { return }
            loading = false
            failed = true
        }
    }

    private static func settings(_ list: JSONValue?, remote: Bool) -> [Setting] {
        (list?.arrayValue ?? []).map {
            Setting(
                id: $0["setting_id"]?.intValue, key: $0["key"]?.stringValue, abc: $0["abc"]?.stringValue ?? "",
                incipitAbc: $0["incipit_abc"]?.stringValue ?? "", incipitImage: $0["incipit_image"]?.stringValue, remote: remote)
        }
    }

    /// Ceol usually holds only the setting an import brought; thesession.org has them
    /// all. They come in behind the first, and so do the tune's other names there.
    private func backfill(run: Int, tuneID: Int) async {
        backfilling = true
        defer { if run == loadRun { backfilling = false } }
        guard let ts = try? await app.getJSON("/api/tunes/thesession/\(tuneID)/preview?full=1"), run == loadRun else { return }
        let have = Set(settings.compactMap(\.id))
        let extra = Self.settings(ts["settings"], remote: true).filter { $0.id.map { !have.contains($0) } ?? true }
        var names = (data?["aliases"]?.arrayValue ?? []).compactMap(\.stringValue)
        for a in (ts["aliases"]?.arrayValue ?? []).compactMap(\.stringValue) where !names.contains(a) { names.append(a) }
        if var d = data?.objectValue {
            d["aliases"] = .array(names.map { .string($0) })
            data = .object(d)
        }
        guard !extra.isEmpty else { return }
        let hadNone = settings.isEmpty
        settings += extra
        if hadNone { await drawCurrent() }
    }

    // MARK: Drawing

    private func imageKey(_ s: Setting) -> String {
        "\(s.id.map(String.init) ?? "r\(setIdx)"):\(size == .full ? "full" : "incipit")"
    }

    /// The notation for the setting in view: the cached opening bars when the preview
    /// brought them, else drawn by the server (a setting Ceol holds is kept there; one
    /// only thesession.org has is drawn for this look).
    private func drawCurrent() async {
        guard mode == .notes, let s = setting else { return }
        let key = imageKey(s)
        guard images[key] == nil, !undrawable.contains(key) else { return }
        if size == .incipit, let b64 = s.incipitImage, let d = Data(base64Encoded: b64), let img = UIImage(data: d) {
            images[key] = img
            return
        }
        let kind = size == .full ? "full" : "incipit"
        var base64: String?
        if s.remote || s.id == nil {
            let body: JSONValue = .object([
                "abc": .string(s.abc), "key": s.key.map { .string($0) } ?? .null,
                "tune_type": (data?["tune_type"] ?? item?.r["tune_type"]) ?? .null, "kind": .string(kind),
            ])
            if let (status, r) = try? await app.postJSON("/api/tunes/render-abc", body: body), status == 200 {
                base64 = r["image"]?.stringValue
            }
        } else if let id = s.id {
            base64 = try? await app.getJSON("/api/tunes/settings/\(id)/image?kind=\(kind)")["image"]?.stringValue
        }
        if let base64, let d = Data(base64Encoded: base64), let img = UIImage(data: d) {
            images[key] = img
        } else {
            undrawable.insert(key)
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
