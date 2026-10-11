// The tune search (plan Phase 5c), the web's TuneSearch (frontend/src/TuneSearch.svelte)
// as one sheet for three places: the logger's "Search" (log a tune at the cursor), a
// session's "Add a tune" (its list), and your own "Add a tune" (your tunebook). The
// whole catalogue by name, by notation, or both, with a filter button for the mode and
// the tune type; each card shows the tune's opening bars. Tapping a card opens its
// preview (TunePreviewPane, the web's TunePreview.svelte): a look before you commit,
// with every setting to page through and choose; the card's ＋ commits in one tap. On
// request, thesession.org too, where picking a tune imports it as it's logged. A pasted
// thesession.org link opens that tune's preview. And the logger's escape: log the text
// as typed.
//
// i18n-converted (spec 057).

import CeolDesign
import CeolLogic
import SwiftUI
import UIKit

/// What a tune search is for, which the server reads to mark results ("played here",
/// "in this session"): a night being logged, a session's list, or your own tunebook.
enum TuneSearchScope {
    case instance(Int)
    case session(String)
    case mine

    var items: [URLQueryItem] {
        switch self {
        case .instance(let id): [.init(name: "instance", value: String(id))]
        case .session(let path): [.init(name: "session", value: path)]
        case .mine: []
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
    /// Offer thesession.org's tunes too (picking one imports it): where the pick can import.
    var allowRemote = true
    /// Close after a pick; off when the pick leads on to a next step in the same sheet.
    var closesOnPick = true
    /// Dim the tunes already on your list, and let their ＋ stand down (your tunebook).
    var dimOnList = false
    /// The tunes added from here (your tunebook): dimmed like the ones already on the list.
    var added: Binding<Set<Int>> = .constant([])
    /// The whole result picked, before `onPick` (what a next step shows of it).
    var pickedResult: ((JSONValue) -> Void)? = nil
    /// The ＋ rail, when it does something other than `onPick` (your tunebook: on the
    /// list at once, as To Learn). Returns what went wrong, or nil.
    var onQuickAdd: (([String: JSONValue]) async -> String?)? = nil
    /// The preview offers "We call this something else" and "We play this in a different
    /// key" (a session's list): the pick then carries `alias` and `key`.
    var sessionExtras = false
    /// Close the sheet (Done, a swipe down, or after a pick).
    let onClose: () -> Void
    /// The pick: {tune_id, name, tune_type, setting_id?, alias?, key?}, {thesession_id, ...},
    /// or {name}. Returns what went wrong (the sheet stays, and says so), or nil.
    let onPick: ([String: JSONValue]) async -> String?

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
    /// A pasted thesession.org link, opened: the preview pages this one tune.
    @State private var pasted: DeepSearchItem?
    /// The preview showing, as an index into `previewItems`.
    @State private var preview: Int?
    @State private var quickFailure: String?

    static let types = ["jig", "reel", "slip jig", "hornpipe", "polka", "slide", "waltz", "barndance", "strathspey", "three-two", "mazurka", "march"]

    @FocusState private var fieldFocused: Bool

    private var trimmedQuery: String { query.trimmingCharacters(in: .whitespacesAndNewlines) }
    /// A thesession.org link or tune number in the field: not a name to search for.
    private var pastedID: Int? { TheSession.tuneID(trimmedQuery) }

    /// What the preview's ‹ › page through: the local results, then thesession.org's;
    /// or the one pasted tune.
    private var previewItems: [DeepSearchItem] {
        if let pasted { return [pasted] }
        return results.map { DeepSearchItem(r: $0, remote: false) } + (remote ?? []).map { DeepSearchItem(r: $0, remote: true) }
    }

    private var filterCount: Int { (mode == .mixed ? 0 : 1) + (type == nil ? 0 : 1) }

    var body: some View {
        NavigationStack {
            ZStack {
                searchTier
                if let i = preview, previewItems.indices.contains(i) {
                    TunePreviewPane(
                        app: app, scope: scope, items: previewItems, index: i, actionLabel: actionLabel,
                        allowRemoteAction: allowRemote, extras: sessionExtras,
                        onBack: {
                            preview = nil
                            pasted = nil
                        }
                    ) { item, data, settingID, extras in
                        pickedResult?(item.r)
                        var payload = Self.payload(item, data: data, settingID: settingID)
                        payload.merge(extras) { _, new in new }
                        return await pick(payload)
                    }
                    .background(CeolTokens.drawerBg)
                    .transition(.move(edge: .trailing))
                    .zIndex(1)
                }
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: onClose).accessibilityIdentifier("deep.cancel")
                }
            }
            .animation(.easeOut(duration: 0.2), value: preview)
            .task(id: "\(query)|\(mode.rawValue)|\(type ?? "")") { await search() }
            .onAppear {
                if query.isEmpty { query = initialQuery }
                // The keyboard comes to this field (the web's modal autofocuses it too);
                // the preview then sends it away.
                fieldFocused = true
            }
        }
    }

    /// The field with its filter button, the filter panel or the pills, and the results.
    private var searchTier: some View {
        VStack(spacing: 0) {
            VStack(spacing: 10) {
                SearchRow(
                    text: $query, prompt: prompt, fieldID: "deep.field", focused: $fieldFocused,
                    onFilter: { withAnimation(.easeOut(duration: 0.2)) { filtersOpen.toggle() } }, filterCount: filterCount)
                if filtersOpen {
                    filterPanel.transition(.move(edge: .top).combined(with: .opacity))
                } else {
                    filterPills
                }
            }
            .padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 8)
            .clipped()
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    let q = trimmedQuery
                    if let quickFailure {
                        Text(quickFailure).font(.ceol(size: 14)).foregroundStyle(CeolTokens.danger)
                    }
                    if let id = pastedID {
                        // A link, not a name: the only thing to do with it is open that tune.
                        wide(tr("🔗 Open tune #\(id) from thesession.org"), color: CeolTokens.info, id: "deep.openPasted") {
                            openPasted(id)
                        }
                        Text("That's a thesession.org tune link — open it above to see the tune.")
                            .foregroundStyle(CeolTokens.textMuted)
                    } else if q.isEmpty {
                        Text("Search the tunes on Ceol by name, by the notes (\"GED BED\"), or paste a thesession.org link.")
                            .foregroundStyle(CeolTokens.textMuted)
                    } else if loading && results.isEmpty {
                        ProgressView().frame(maxWidth: .infinity).padding()
                    } else if failed {
                        Text("Couldn't search. Check your connection.").foregroundStyle(CeolTokens.textMuted)
                    } else if results.isEmpty && !loading {
                        Text("No tunes found for “\(q)”.").foregroundStyle(CeolTokens.textMuted)
                    }
                    ForEach(Array(results.enumerated()), id: \.offset) { i, r in
                        card(r, remote: false, index: i)
                    }
                    if !q.isEmpty && pastedID == nil {
                        if allowRemote && remote == nil && mode != .abc {
                            wide(tr("🔎 Search on thesession.org for “\(q)”"), color: CeolTokens.info, id: "deep.thesession") {
                                Task { await searchTheSession(q) }
                            }
                        }
                        if allowAsIs && mode != .abc {
                            wide(tr("＋ Log “\(q)” as typed (unlinked)"), color: CeolTokens.primary, id: "deep.asIs") {
                                Task { quickFailure = await pick(["name": .string(q)]) }
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
                .padding(.horizontal, 16).padding(.vertical, 8)
            }
            .scrollDismissesKeyboard(.interactively)
        }
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
        if filterCount > 0 {
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

    /// A result: its body opens the preview, its ＋ commits it at once (or a check, for
    /// a tune already on your list).
    private func card(_ r: JSONValue, remote: Bool, index: Int) -> some View {
        let name = r["name"]?.stringValue ?? ""
        let id = r["tune_id"]?.intValue
        let onList = dimOnList && (r["on_list"] == true || id.map { added.wrappedValue.contains($0) } == true)
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
                    if !remote, let id {
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
            if onList {
                Image(systemName: "checkmark").font(.system(size: 18, weight: .medium))
                    .foregroundStyle(CeolTokens.primary)
                    .frame(width: 48)
                    .frame(maxHeight: .infinity)
                    .accessibilityLabel("On your list")
            } else {
                Button { quickAdd(DeepSearchItem(r: r, remote: remote)) } label: {
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
        }
        .fixedSize(horizontal: false, vertical: true)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        .opacity(onList || (r["in_session"] == true && (remote || !allowAsIs)) ? 0.6 : 1)
    }

    /// The ＋ rail: the caller's quick add where there is one (your tunebook), else the pick.
    private func quickAdd(_ item: DeepSearchItem) {
        let payload = Self.payload(item, data: nil, settingID: nil)
        if let onQuickAdd {
            quickFailure = nil
            Task {
                if let problem = await onQuickAdd(payload) {
                    quickFailure = problem
                } else if let id = item.r["tune_id"]?.intValue {
                    added.wrappedValue.insert(id)
                }
            }
        } else {
            pickedResult?(item.r)
            Task { quickFailure = await pick(payload) }
        }
    }

    /// A pasted link: that tune's preview, as a thesession.org result (the preview finds
    /// out whether Ceol holds it, and loads its real name).
    private func openPasted(_ id: Int) {
        fieldFocused = false
        pasted = DeepSearchItem(r: .object(["tune_id": .number(Double(id)), "name": .string("#\(id)"), "tune_type": .null]), remote: true)
        preview = 0
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

    /// Hands the pick on; what went wrong, or nil once it is taken (and the sheet
    /// closed, where a pick closes it).
    private func pick(_ payload: [String: JSONValue]) async -> String? {
        if let problem = await onPick(payload) { return problem }
        preview = nil
        pasted = nil
        if closesOnPick { onClose() }
        return nil
    }

    private func search() async {
        let q = trimmedQuery
        remote = nil
        remoteFailed = false
        quickFailure = nil
        guard !q.isEmpty, pastedID == nil else {
            results = []
            return
        }
        try? await Task.sleep(for: .milliseconds(160))
        guard !Task.isCancelled else { return }
        loading = true
        defer { loading = false }
        var items: [URLQueryItem] = scope.items + [
            .init(name: "limit", value: "30"), .init(name: "q", value: q), .init(name: "mode", value: mode.rawValue),
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
        var items: [URLQueryItem] = scope.items + [.init(name: "q", value: q)]
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
        guard !items.isEmpty else { return p }
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

/// A look before you commit (the web's TunePreview.svelte): the tune's name and type,
/// how often it's been played here and how common it is, its other names, every
/// setting to page through (the ones Ceol holds at once, the rest from thesession.org
/// as they arrive), the notation (opening bars; tap for the whole tune) or the ABC,
/// and the button that commits it. ‹ › at the top step through the other results. A
/// setting counts as chosen only when the pager was worked: landing on the session's
/// own setting says nothing new.
struct TunePreviewPane: View {
    let app: AppModel
    let scope: TuneSearchScope
    let items: [DeepSearchItem]
    let index: Int
    let actionLabel: String
    /// Whether the button works for a tune only thesession.org has (an import): not
    /// from your tunebook, which takes catalogue tunes only.
    var allowRemoteAction = true
    /// "We call this something else" and "We play this in a different key" above the
    /// button (a session's list), handed on as `alias` and `key`.
    var extras = false
    let onBack: () -> Void
    /// The pick: the result, the preview's data (nil when it didn't load), the chosen
    /// setting, and the extras ({alias, key}, those given). What went wrong, or nil.
    let onAction: (DeepSearchItem, JSONValue?, Int?, [String: JSONValue]) async -> String?

    /// The keys the web's form offers.
    static let keys = [
        "Amajor", "Aminor", "Adorian", "Amixolydian", "Bminor", "Cmajor", "Dmajor", "Dminor",
        "Eminor", "Fmajor", "Gmajor", "Dmixolydian", "Bmixolydian", "Edorian", "Gdorian",
        "Gminor", "Ddorian", "Cdorian", "Fdorian", "Gmixolydian", "Emajor", "Bdorian", "Emixolydian",
    ]

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
    @State private var aliasOpen = false
    @State private var alias = ""
    @State private var keyOpen = false
    @State private var key = ""
    @State private var busy = false
    @State private var actionFailure: String?

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
    private var actionAllowed: Bool { allowRemoteAction || !isRemote }

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
                            Text(allowRemoteAction
                                ? tr("Not in the library yet — it will be imported from thesession.org when you add it.")
                                : tr("Not in Ceol's library yet. Log it at a session first, and it will be imported."))
                                .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                }
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
            VStack(spacing: 10) {
                if extras && !loading && !failed { extrasBlock }
                if let actionFailure {
                    Text(actionFailure).font(.ceol(size: 14)).foregroundStyle(CeolTokens.danger)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                Button { Task { await act() } } label: {
                    Text(busy ? tr("Adding…") : actionLabel).font(.ceol(size: 17, weight: .semibold))
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .foregroundStyle(.white)
                        .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
                }
                .buttonStyle(.plain)
                .disabled(loading || busy || !actionAllowed)
                .opacity(loading || busy || !actionAllowed ? 0.5 : 1)
                .accessibilityIdentifier("preview.action")
            }
            .padding(.horizontal, 16).padding(.vertical, 10)
        }
        .task { idx = index; await load() }
        .onChange(of: idx) { Task { await load() } }
        .onChange(of: setIdx) { Task { await drawCurrent() } }
        .onChange(of: size) { Task { await drawCurrent() } }
        .onChange(of: mode) { if mode == .notes { Task { await drawCurrent() } } }
    }

    private func act() async {
        guard let item, !busy else { return }
        busy = true
        actionFailure = nil
        var extra: [String: JSONValue] = [:]
        let a = alias.trimmingCharacters(in: .whitespaces)
        if aliasOpen && !a.isEmpty { extra["alias"] = .string(a) }
        if keyOpen && !key.isEmpty { extra["key"] = .string(key) }
        actionFailure = await onAction(item, data, chosenSettingID, extra)
        busy = false
    }

    /// The session's own word for the tune, and its key, when they differ from the
    /// catalogue's: a link each, opening into the field. (The setting is the pager's.)
    private var extrasBlock: some View {
        VStack(alignment: .leading, spacing: 8) {
            if aliasOpen {
                TextField("", text: $alias, prompt: Text(tr("What this session calls it")).foregroundStyle(CeolTokens.textMuted))
                    .font(.ceol(size: 16))
                    .autocorrectionDisabled()
                    .padding(.horizontal, 12).frame(height: 44)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                    .accessibilityIdentifier("preview.alias")
            } else {
                Button("We call this something else") { withAnimation(.easeOut(duration: 0.15)) { aliasOpen = true } }
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
                    .accessibilityIdentifier("preview.aliasLink")
            }
            if keyOpen {
                Menu {
                    Button("(not specified)") { key = "" }
                    ForEach(Self.keys, id: \.self) { k in Button(k) { key = k } }
                } label: {
                    HStack {
                        Text(key.isEmpty ? tr("Key the session plays it in") : key).font(.ceol(size: 16))
                            .foregroundStyle(key.isEmpty ? CeolTokens.textMuted : CeolTokens.textColor)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down").font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    }
                    .padding(.horizontal, 12).frame(height: 44)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                }
                .accessibilityIdentifier("preview.key")
            } else {
                Button("We play this in a different key") { withAnimation(.easeOut(duration: 0.15)) { keyOpen = true } }
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
                    .accessibilityIdentifier("preview.keyLink")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
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
            if items.count > 1 {
                Text("\(idx + 1) of \(items.count)").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                stepButton(-1, enabled: idx > 0, label: tr("Previous result"), id: "preview.prev") { idx -= 1 }
                stepButton(1, enabled: idx < items.count - 1, label: tr("Next result"), id: "preview.next") { idx += 1 }
            }
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
            } else if case .mine = scope {
                EmptyView()
            } else {
                Text("Not played here yet").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
            }
            HStack(spacing: 10) {
                (Text(verbatim: "\(data?["tunebook_count"]?.intValue ?? 0) ").bold() + Text("tunebooks"))
                    .font(.ceol(size: 14)).foregroundStyle(CeolTokens.primary)
                if item?.r["on_list"] == true || data?["person_tune"]?["on_list"] == true {
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
        aliasOpen = false
        alias = ""
        keyOpen = false
        key = ""
        actionFailure = nil
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
                    d = try await app.getJSON(DeepSearchSheet.path("/api/tunes/\(local)/preview", scope.items))
                }
            } else {
                d = try await app.getJSON(DeepSearchSheet.path("/api/tunes/\(id)/preview", scope.items))
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
                  onClose: onClose) { payload in
            onPick(payload)
            return nil
        }
    }
}
