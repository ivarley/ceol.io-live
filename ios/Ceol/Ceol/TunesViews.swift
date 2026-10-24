// The Tunes tab (plan Phase 3c): your list, and the tune sheet — the app's twins of
// the Svelte /my-tunes and the shared tune drawer, from the same payloads. The sheet
// edits a tune on your list (status, heard count, notes, remove) or adds one from the
// catalogue (Phase 4a); the list reloads after each change.
//
// The search field reaches the whole catalogue as on the web: your matching tunes
// first, then "Not on your list" from the server's catalogue search (name or notation).
//
// i18n-converted (spec 057): fixed text is localized; tune types, instruments, statuses
// and the list's counts are translated here (TunesWords), CeolLogic's English untouched.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI
import UIKit

typealias MyTunesPayload = Components.Schemas.MyTunes
typealias PersonTune = Components.Schemas.PersonTune
typealias DeepSearchResult = Components.Schemas.DeepSearch.ResultsPayloadPayload

extension PersonTune {
    var entry: MyTunesRules.Entry {
        .init(tuneID: tuneId, name: tuneName, type: tuneType, status: learnStatus, notes: notes)
    }
}

/// What the tune sheet opens on: a tune on your list, or one from the catalogue.
struct TuneRef: Identifiable, Hashable {
    let id: Int
    let name: String
    let type: String?
    var status: String?
    var heardCount: Int?
    var notes: String?
    var tags: [String] = []
    /// Opened from a session's page: the sheet adds that session's plays.
    var sessionPath: String? = nil
    /// Opened from one night's log: the sheet draws what was played that night, and
    /// "a different version" means that night's.
    var instanceID: Int? = nil
    /// Whether `status` is known. Opened from somewhere other than your list, the sheet
    /// reads your status from the tune's detail instead.
    var statusKnown = true
    /// A setting chosen in the search's preview: applied as yours once the tune is added.
    var settingID: Int? = nil
    /// What a session of yours calls the tune, and the key it plays: the add's fields
    /// start from these.
    var alias: String? = nil
    var key: String? = nil
}

struct TunesView: View {
    @Environment(AppModel.self) private var model
    private var state: Resource<MyTunesPayload> { model.myTunes }
    @State private var filters = MyTunesList.Filters()
    @State private var sort = MyTunesList.Sort()
    @State private var search = ""
    @State private var catalogue: [DeepSearchResult] = []
    @State private var catalogueFailed = false
    @State private var open: TuneRef?
    @State private var failure: String?
    @State private var filtering = false
    @State private var adding = false
    @FocusState private var searching: Bool

    var body: some View {
        if model.isGuest { GuestTunesView() } else { signedIn }
    }

    private var signedIn: some View {
        NavigationStack {
            Resourced(resource: state) { payload in list(payload) }
                .background(CeolTokens.bgColor)
                .ceolKept(state)
                .ceolRootBar(tr("Tunes"), sharePath: model.tunesStatus.map { "/my-tunes?status=\($0.rawValue.replacingOccurrences(of: " ", with: "+"))" } ?? "/my-tunes")
                .task(id: search) { await searchCatalogue() }
                // The search keyboard would otherwise stay up over the sheet.
                .onChange(of: open) { _, tune in if tune != nil { searching = false } }
                .sheet(item: $open) { TuneSheet(tune: $0) { Task { await load() } } }
                .sheet(isPresented: $filtering) {
                    TunesFilterSheet(filters: $filters, sort: $sort, types: types, instruments: instruments, tags: tagsUsed)
                }
                .sheet(isPresented: $adding) { AddTuneSheet { Task { await load() } } }
                // The Tunes icon, tapped while here: back to the list itself.
                .onChange(of: model.rootRequests[.tunes]) { _, _ in
                    open = nil
                    filtering = false
                    adding = false
                    searching = false
                }
                .task { await state.refresh(ifOlderThan: 20) }
                .alert("Not saved", isPresented: Binding(get: { failure != nil }, set: { if !$0 { failure = nil } })) {
                    Button("OK") {}
                } message: {
                    Text(failure ?? "")
                }
        }
    }

    private var instruments: [MyTunesList.Instrument] {
        (state.value?.instruments ?? []).map { .init(name: $0.instrument, isAuto: $0.isAuto) }
    }

    /// The tags you've given tunes: the filter's choices.
    private var tagsUsed: [String] { MyTunesList.tagsUsed((state.value?.tunes ?? []).map(\.listItem)) }

    private var types: [String] {
        Set((state.value?.tunes ?? []).compactMap(\.tuneType)).sorted()
    }

    private func heard(_ tuneID: Int, count: Int) async {
        do {
            try await model.applyTuneOp(.setHeard, tuneID: tuneID, heardCount: count)
            await load()
        } catch let f as TuneOpFailure {
            failure = f.message
        } catch {
            failure = tr("That wasn't saved. Try again.")
        }
    }

    private func load() async {
        await state.refresh()
    }

    /// The catalogue below your own matches, after a short pause in typing. Two
    /// characters at least, as the web's add pane.
    private func searchCatalogue() async {
        let q = search.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2 else {
            catalogue = []
            return
        }
        try? await Task.sleep(for: .milliseconds(300))
        guard !Task.isCancelled else { return }
        do {
            let r = try await model.auth.client.deepSearchTunes(query: .init(q: q, limit: 25)).ok.body.json
            catalogue = r.results.filter { !$0.onList }
            catalogueFailed = false
        } catch {
            if !Task.isCancelled { catalogueFailed = true }
        }
    }

    /// Changes made with no signal, waiting to be sent; and any the server refused.
    @ViewBuilder private var queueNotice: some View {
        let n = model.tuneQueue.count
        if n > 0 {
            Text(n == 1 ? tr("1 change waiting to be sent") : tr("\(n) changes waiting to be sent"))
                .font(.ceol(size: 13)).foregroundStyle(CeolTokens.warning)
                .accessibilityIdentifier("tunes.waiting")
        }
        if !model.tuneQueue.refused.isEmpty {
            HStack(alignment: .top, spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(model.tuneQueue.refused, id: \.self) { r in
                        Text("Couldn't save \(r)").font(.ceol(size: 13)).foregroundStyle(CeolTokens.warning)
                    }
                }
                Spacer()
                Button("Dismiss") { model.tuneQueue.refused = [] }.font(.ceol(size: 13)).foregroundStyle(CeolTokens.primary)
            }
            .accessibilityIdentifier("tunes.refused")
        }
    }

    @ViewBuilder private func list(_ payload: MyTunesPayload) -> some View {
        let byID = Dictionary(payload.tunes.map { ($0.tuneId, $0) }, uniquingKeysWith: { a, _ in a })
        var f = filters
        let _ = { f.search = search; f.status = model.tunesStatus?.rawValue ?? "" }()
        let rows = MyTunesList.filterAndSort(payload.tunes.map(\.listItem), filters: f, sort: sort, instruments: instruments)
        let firstDimmed = rows.firstIndex { $0.dimmed }
        // Less any you added since the search ran.
        let catalogue = catalogue.filter { byID[$0.tuneId] == nil }
        List {
            VStack(alignment: .leading, spacing: 10) {
                // The web's toolbar: search (your list, then the catalogue below it),
                // sort and filter, and + to add a tune.
                SearchRow(
                    text: $search, prompt: tr("Search"), fieldID: "tunes.search",
                    onAdd: { adding = true }, addID: "tunes.add", addLabel: tr("Add a tune"),
                    focused: $searching,
                    onFilter: { filtering = true },
                    filterCount: filters.activeCount + (sort == MyTunesList.Sort() ? 0 : 1))
                Picker("Status", selection: Binding(get: { model.tunesStatus }, set: { model.tunesStatus = $0 })) {
                    ForEach(MyTunesRules.Status.allCases, id: \.self) { Text(TunesWords.status($0.rawValue)).tag(Optional($0)) }
                    Text("All").tag(MyTunesRules.Status?.none)
                }
                .pickerStyle(.segmented)
                HStack {
                    Text(TunesWords.resultsCount(rows, total: payload.tunes.count, filters: f))
                    if sort.type != "alpha" || sort.descending {
                        Text("· \(TunesWords.sortMode(sort.type)) \(sort.descending ? "↓" : "↑")")
                    }
                }
                .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                queueNotice
            }
            .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 6, trailing: 16))
            .listRowBackground(CeolTokens.bgColor)
            .listRowSeparator(.hidden)
            ForEach(Array(rows.enumerated()), id: \.element.item.tuneID) { i, row in
                let e = row.item
                let t = byID[e.tuneID]
                if i == firstDimmed {
                    // The web's heading between the tunes on the instrument and the rest.
                    Text("Not on \(TunesWords.instrument(filters.instrument))").font(.ceol(size: 13, weight: .semibold)).textCase(.uppercase)
                        .tracking(0.8).foregroundStyle(CeolTokens.textMuted)
                        .listRowInsets(EdgeInsets(top: 18, leading: 16, bottom: 4, trailing: 16))
                        .listRowBackground(CeolTokens.bgColor)
                }
                Button {
                    open = TuneRef(
                        id: e.tuneID, name: e.name, type: e.type, status: e.status, heardCount: t?.heardCount,
                        notes: e.notes, tags: t?.tags ?? [])
                } label: {
                    TuneRow(
                        name: e.name, type: MyTunesList.typeBadgeLabel(e, sortType: sort.type), status: e.status,
                        note: row.abcOnly
                            ? tr("♪ notes match")
                            : row.matchedTags.isEmpty ? nil : tr("tagged \(row.matchedTags.joined(separator: " "))"),
                        typeIsCount: sort.type != "alpha")
                }
                .accessibilityIdentifier("tunes.row")
                .buttonStyle(.plain)
                .opacity(row.dimmed ? 0.45 : 1)
                .ceolRow()
                .swipeActions(edge: .leading) {
                    // The web's swipe: one more hearing of a tune you want to learn.
                    if e.status == MyTunesRules.Status.wantToLearn.rawValue {
                        Button("Heard it") { Task { await heard(e.tuneID, count: (t?.heardCount ?? 0) + 1) } }
                            .tint(CeolTokens.primaryFill)
                    }
                }
            }
            if rows.isEmpty && catalogue.isEmpty {
                Text(payload.tunes.isEmpty ? tr("No tunes here yet.") : TunesWords.noResults(f))
                    .font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                    .listRowBackground(CeolTokens.bgColor).listRowSeparator(.hidden)
            }
            if !catalogue.isEmpty || catalogueFailed {
                Text("Not on your list").font(.ceol(size: 13, weight: .semibold)).textCase(.uppercase).tracking(0.8)
                    .foregroundStyle(CeolTokens.textMuted)
                    .listRowInsets(EdgeInsets(top: 22, leading: 16, bottom: 6, trailing: 16))
                    .listRowBackground(CeolTokens.bgColor)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityLabel("Not on your list")
                if catalogueFailed {
                    Text("Couldn't search the catalogue.").foregroundStyle(CeolTokens.textMuted).ceolRow()
                }
                ForEach(catalogue, id: \.tuneId) { r in
                    Button {
                        open = TuneRef(id: r.tuneId, name: r.name, type: r.tuneType)
                    } label: {
                        TuneRow(name: r.name, type: r.tuneType, status: nil, note: r.abcOnly ? tr("♪ notes match") : nil)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("catalogue.row")
                    .ceolRow()
                }
            }
        }
        .ceolPlainList()
        .refreshable { await load() }
    }
}

extension PersonTune {
    /// What the list's filters and sorts read (MyTunesList, the web's rules).
    var listItem: MyTunesList.Item {
        var overrides: [String: String] = [:]
        for (k, v) in instrumentStatus.additionalProperties { overrides[k] = v }
        return MyTunesList.Item(
            tuneID: tuneId, name: tuneName, type: tuneType, status: learnStatus, notes: notes,
            addedDay: String(createdDate.prefix(10)), tunebookCount: tunebookCount,
            heardCount: heardCount, memberPlays: memberPlayCount, sessionPlays: sessionPlayCount,
            attendedPlays: attendedPlayCount, instrumentStatus: overrides, tags: tags)
    }
}

/// A tune in a list, as the web's phone row: the status glyph, the name, the type chip.
private struct TuneRow: View {
    let name: String
    let type: String?
    let status: String?
    var note: String? = nil
    /// Under a count sort the chip shows the count, not the type (the web's badge).
    var typeIsCount = false

    var body: some View {
        HStack(spacing: 10) {
            if let status { StatusGlyph(status: status) }
            VStack(alignment: .leading, spacing: 2) {
                Text(name).font(.ceol(size: 19, weight: .medium)).foregroundStyle(CeolTokens.textColor).lineLimit(1)
                if let note { Text(note).font(.ceol(size: 12)).foregroundStyle(CeolTokens.warning) }
            }
            Spacer(minLength: 6)
            if typeIsCount, let type {
                CountBox(count: Int(type) ?? 0)
            } else if let type, !type.isEmpty {
                TypeChip(label: TunesWords.type(type), size: 15)
            }
        }
        .padding(.vertical, 3)
        .contentShape(Rectangle())
    }
}

// MARK: - The tune sheet

/// A tune's sheet: name and type, your status (and heard count and notes) or Add, the
/// notation (opening bars, or the whole tune), and how much it gets played. Notation is
/// rendered by the server, as on the web. `onChanged` runs after each saved edit.
struct TuneSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let tune: TuneRef
    var onChanged: () -> Void = {}

    @State private var status: String?
    @State private var heard = 0
    @State private var notes = ""
    @State private var savedNotes = ""
    @State private var tags: [String] = []
    @State private var busy = false
    @State private var failure: String?
    @State private var confirmRemove = false
    @State private var detail: LoadState<Components.Schemas.TuneDetail> = .loading
    @State private var incipit: UIImage?
    @State private var full: UIImage?
    @State private var showFull = false
    /// The ABC instead of the staff (the notes / abc tabs under it).
    @State private var abcMode = false
    /// What's showing, over the whole screen (the arrows under the staff).
    @State private var fullScreen = false
    /// The copy button's tick, for a moment after copying.
    @State private var copied = false
    /// The first time you tap through to the whole tune: a word about learning by ear.
    @State private var showNotationNotice = false
    @State private var notationNoticeDone = false
    @State private var notationFailed = false
    @State private var chooser: SettingLayer?

    var body: some View {
        NavigationStack {
            Group {
                if case .failed(let message) = detail, tune.statusKnown {
                    // No signal, but your status came with the list: that much still
                    // works (a change waits to be sent); the notation needs a connection.
                    keptContent(message)
                } else {
                    Loaded(state: detail, retry: load) { d in content(d.sessionTune) }
                }
            }
                .background(Self.surface)
                .navigationTitle(tune.name)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .principal) { Color.clear.frame(width: 1, height: 1) }
                    ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
                }
                // Share, with this drawer up, is this tune: its page at the session it was
                // opened from, else its thesession.org page (Ceol has no public page for a
                // tune on its own).
                .onAppear {
                    model.shareOverride = ShareTarget(
                        url: tune.sessionPath.map { model.webURL("/sessions/\($0)/tunes/\(tune.id)") }
                            ?? URL(string: "https://thesession.org/tunes/\(tune.id)")!,
                        title: tune.name)
                }
                .onDisappear { model.shareOverride = nil }
                .task {
                    status = tune.status
                    heard = tune.heardCount ?? 0
                    notes = tune.notes ?? ""
                    savedNotes = notes
                    tags = tune.tags
                    await load()
                }
                .confirmationDialog("Remove \(tune.name) from your tunes?", isPresented: $confirmRemove, titleVisibility: .visible) {
                    Button("Remove", role: .destructive) {
                        Task { if await save(.remove) { dismiss() } }
                    }
                } message: {
                    Text("Its status, notes and heard count go with it.")
                }
                .fullScreenCover(isPresented: $fullScreen) {
                    if let image = showFull ? (full ?? incipit) : incipit { NotationFullScreen(image: image, name: tune.name) }
                }
                .sheet(item: $chooser) { layer in
                    if let t = detail.value?.sessionTune {
                        SettingChooser(
                            tuneID: tune.id, tuneName: t.tuneName, tuneType: t.tuneType,
                            heading: layer.heading(sessionName: sessionName(t)),
                            current: settingInUse(layer, t)
                        ) { await saveSetting($0, for: layer) }
                    }
                }
        }
        .ceolDrawer()
    }

    static let surface = CeolTokens.drawerBg

    /// Saves one op; true when the server took it.
    @discardableResult
    private func save(
        _ type: TuneOp._TypePayload, status s: LearnStatus? = nil, heard h: Int? = nil, notes n: String? = nil,
        tags: [String]? = nil, nameAlias: String? = nil, key: String? = nil
    ) async -> Bool {
        busy = true
        failure = nil
        defer { busy = false }
        do {
            try await model.applyTuneOp(
                type, tuneID: tune.id, learnStatus: s, heardCount: h, notes: n, tags: tags, nameAlias: nameAlias, key: key,
                name: tune.name, tuneType: tune.type)
            onChanged()
            return true
        } catch let f as TuneOpFailure {
            failure = f.message
        } catch {
            failure = tr("That wasn't saved. Try again.")
        }
        return false
    }

    private func saveNotes() async {
        let trimmed = notes.trimmingCharacters(in: .whitespacesAndNewlines)
        if await save(.setNotes, notes: trimmed.isEmpty ? nil : trimmed) {
            notes = trimmed
            savedNotes = trimmed
        }
    }

    /// Your tags, saved as they change (the web's field saves as you leave it): shown
    /// at once, put back if the save is refused.
    private func saveTags(_ new: [String]) async {
        let before = tags
        tags = new
        if !(await save(.setTags, tags: new)) { tags = before }
    }

    /// Your list (TunebookPanel), and your notes and tags under it once the tune is on it.
    @ViewBuilder private var yourList: some View {
        let current = status.flatMap(MyTunesRules.Status.init(rawValue:))
        TunebookPanel(tune: tune, status: $status, heard: $heard, onAdded: {
            // the setting chosen in a search's preview is yours now too
            if let s = tune.settingID, await saveSetting(s, for: .mine) == nil {
                incipit = nil
                full = nil
            }
        }, onChanged: onChanged)
        if current != nil {
            VStack(alignment: .trailing, spacing: 6) {
                TextField("", text: $notes, prompt: Text("Notes").foregroundStyle(CeolTokens.textMuted), axis: .vertical)
                    .font(.ceol(size: 17))
                    .lineLimit(3...8)
                    .padding(12)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                    .accessibilityIdentifier("sheet.notes")
                if notes != savedNotes {
                    Button("Save notes") { Task { await saveNotes() } }
                        .font(.ceol(size: 15, weight: .medium)).foregroundStyle(CeolTokens.primary).disabled(busy)
                }
            }
            TagsEditor(tags: tags, busy: busy) { new in Task { await saveTags(new) } }
        }
    }

    private func load() async {
        do {
            let d = try await model.auth.client.getTuneDetail(
                path: .init(tuneId: tune.id),
                query: .init(session: tune.sessionPath, instance: tune.instanceID.map(String.init))
            ).ok.body.json
            if !tune.statusKnown, let mine = JSONValue(encoding: d.sessionTune.personTuneStatus),
                mine["on_list"]?.boolValue == true
            {
                status = mine["learn_status"]?.stringValue
                heard = mine["heard_count"]?.intValue ?? 0
                notes = mine["notes"]?.stringValue ?? ""
                savedNotes = notes
                tags = (mine["tags"]?.arrayValue ?? []).compactMap(\.stringValue)
            }
            detail = .loaded(d)
            await loadNotation(d.sessionTune)
        } catch {
            detail = .failed(loadFailureMessage(error))
        }
    }

    /// The setting the staff draws: a night's own, else the one under it.
    private func drawnSetting(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> Int? {
        t.settingOverride ?? t.settingId
    }

    private func loadNotation(_ t: Components.Schemas.TuneDetail.SessionTunePayload) async {
        if let img = decode(t.incipitImage) {
            incipit = img
        } else if let setting = drawnSetting(t),
            let r = try? await model.auth.client.getSettingImage(path: .init(settingId: setting), query: .init(kind: .incipit)).ok.body.json
        {
            incipit = decode(r.image)
        } else if let r = try? await model.auth.client.getTuneIncipitImage(path: .init(tuneId: tune.id)).ok.body.json {
            incipit = decode(r.image)
        }
        notationFailed = incipit == nil && t.incipitAbc != nil
    }

    private func loadFull(_ t: Components.Schemas.TuneDetail.SessionTunePayload) async {
        guard full == nil else { return }
        if let img = decode(t.image) {
            full = img
        } else if let setting = drawnSetting(t),
            let r = try? await model.auth.client.getSettingImage(path: .init(settingId: setting), query: .init(kind: .full)).ok.body.json
        {
            full = decode(r.image)
        }
    }

    private func decode(_ base64: String?) -> UIImage? {
        guard let base64, let data = Data(base64Encoded: base64) else { return nil }
        return UIImage(data: data)
    }

    @ViewBuilder private func content(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                // The web's header: the type chip beside the name, the key under it.
                HStack(spacing: 12) {
                    if let type = t.tuneType { TypeChip(label: TunesWords.type(type), size: 16) }
                    Text(t.tuneName).font(.ceol(size: 26, weight: .semibold, relativeTo: .title)).foregroundStyle(CeolTokens.textColor)
                }
                notation(t)
                if let layer = settingLayer(t) {
                    HStack(spacing: 10) {
                        Text(layer.prompt).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                        Spacer(minLength: 0)
                        Button { chooser = layer } label: {
                            Text("Change Setting").font(.ceol(size: 15, weight: .medium))
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.primary, lineWidth: 1))
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(CeolTokens.primary)
                        .accessibilityIdentifier("sheet.changeSetting")
                    }
                }
                yourList
                VStack(spacing: 0) {
                    if tune.sessionPath != nil {
                        stat(tr("Played at this session"), t.timesPlayed)
                        Hairline()
                    }
                    stat(tr("At sessions on Ceol"), t.globalPlayCount)
                    Hairline()
                    stat(tr("Sessions that play it"), t.sessionCount)
                    if let books = t.tunebookCount {
                        Hairline()
                        stat(tr("TheSession.org tunebooks"), books)
                    }
                    if let key = t.settingKey {
                        Hairline()
                        HStack { Text("Key"); Spacer(); Text(key).foregroundStyle(CeolTokens.textMuted) }
                            .font(.ceol(size: 16)).padding(.vertical, 12)
                    }
                }
                .padding(.horizontal, 16)
                .background(CeolTokens.bgColor, in: RoundedRectangle(cornerRadius: 10))
                if let aliases = t.aliases, !aliases.isEmpty {
                    (Text("Also called: ").font(.ceol(size: 15, weight: .semibold)) + Text(aliases.joined(separator: ", ")).font(.ceol(size: 15)))
                        .foregroundStyle(CeolTokens.textMuted)
                }
                HStack {
                    Spacer()
                    if status != nil {
                        Button("Remove From My Tunes") { confirmRemove = true }
                            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.danger)
                            .disabled(busy)
                            .accessibilityIdentifier("sheet.remove")
                    }
                }
            }
            .padding(20)
        }
    }

    /// The sheet with no connection, for a tune from your list: its name, your status
    /// and notes, and why the rest is missing.
    @ViewBuilder private func keptContent(_ message: String) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 12) {
                    if let type = tune.type { TypeChip(label: TunesWords.type(type), size: 16) }
                    Text(tune.name).font(.ceol(size: 26, weight: .semibold, relativeTo: .title)).foregroundStyle(CeolTokens.textColor)
                }
                HStack(spacing: 10) {
                    Image(systemName: "wifi.exclamationmark").foregroundStyle(CeolTokens.textMuted)
                    Text(message).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    Spacer(minLength: 0)
                    Button("Retry") { Task { await load() } }.font(.ceol(size: 15, weight: .medium)).foregroundStyle(CeolTokens.primary)
                }
                .padding(12)
                .background(CeolTokens.bgColor, in: RoundedRectangle(cornerRadius: 10))
                .accessibilityIdentifier("sheet.offline")
                yourList
                HStack {
                    Spacer()
                    if status != nil {
                        Button("Remove From My Tunes") { confirmRemove = true }
                            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.danger)
                            .disabled(busy)
                            .accessibilityIdentifier("sheet.remove")
                    }
                }
            }
            .padding(20)
        }
    }

    // MARK: Which version

    /// Which layer "a different version" means here, or nil when this viewer can't change
    /// it: on your list, yours; at a session, the session's (its admins); on one night,
    /// that night's (its members, and only for a tune played that night). As the web.
    private func settingLayer(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> SettingLayer? {
        guard let path = tune.sessionPath else { return status != nil ? .mine : nil }
        guard let scope = JSONValue(encoding: t.sessionScope) else { return nil }
        if let night = tune.instanceID {
            let played = scope["played_instances"]?.arrayValue?
                .contains { $0["session_instance_id"]?.intValue == night } ?? false
            return played && scope["can_edit_instance"]?.boolValue == true ? .night(path: path, instanceID: night) : nil
        }
        return scope["can_edit_session"]?.boolValue == true ? .session(path: path) : nil
    }

    private func sessionName(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> String {
        JSONValue(encoding: t.sessionScope)?["session_name"]?.stringValue ?? tr("this session")
    }

    /// The setting a layer uses now. A night with no setting of its own played the session's.
    private func settingInUse(_ layer: SettingLayer, _ t: Components.Schemas.TuneDetail.SessionTunePayload) -> Int? {
        switch layer {
        case .mine: return JSONValue(encoding: t.personTuneStatus)?["setting_id"]?.intValue ?? t.settingId
        case .session: return t.settingId
        case .night: return t.settingOverride ?? t.settingId
        }
    }

    /// Writes the pick to its layer (the server imports a setting only thesession.org
    /// has), then redraws the sheet. nil when saved, else what to say.
    private func saveSetting(_ settingID: Int, for layer: SettingLayer) async -> String? {
        let refused: String?
        do {
            switch layer {
            case .mine:
                do {
                    try await model.applyTuneOp(.setSetting, tuneID: tune.id, settingID: settingID)
                    refused = nil
                } catch let f as TuneOpFailure {
                    refused = f.message
                }
            case .session(let path):
                switch try await model.auth.client.updateSessionTune(
                    path: .init(sessionPath: path, tuneId: tune.id), body: .json(.init(settingId: settingID)))
                {
                case .ok: refused = nil
                case .default(_, let e): refused = (try? e.body.json)?.message ?? tr("That wasn't saved. Try again.")
                }
            case .night(let path, let night):
                switch try await model.auth.client.updateSessionInstanceTune(
                    path: .init(sessionPath: path, dateOrId: String(night), tuneId: tune.id),
                    body: .json(.init(settingOverride: settingID)))
                {
                case .ok: refused = nil
                case .default(_, let e): refused = (try? e.body.json)?.message ?? tr("That wasn't saved. Try again.")
                }
            }
        } catch {
            return tr("Couldn't reach Ceol, so that wasn't saved. Check your connection and try again.")
        }
        if let refused { return refused }
        incipit = nil
        full = nil
        showFull = false
        await load()
        onChanged()
        return nil
    }

    private func stat(_ label: String, _ value: Int) -> some View {
        HStack { Text(label); Spacer(); Text("\(value)").foregroundStyle(CeolTokens.textMuted) }
            .font(.ceol(size: 16)).padding(.vertical, 12)
    }
}

/// The web's green panel, "your list" (the tune drawer's My List box): "This tune is on
/// your list as" and the three statuses as buttons, the heard count while you want to
/// learn it; or, for a tune not on it, the three ways to add it, with your own name and
/// key. The tune sheet's, and the listen screen's for a tune the meter is sure of
/// (spec 059). `loadsStatus`: read your status from the tune's detail first (the sheet
/// reads it itself).
struct TunebookPanel: View {
    @Environment(AppModel.self) private var model
    let tune: TuneRef
    @Binding var status: String?
    @Binding var heard: Int
    var loadsStatus = false
    /// After an add was saved: the sheet applies a setting chosen in a search.
    var onAdded: () async -> Void = {}
    var onChanged: () -> Void = {}

    @State private var busy = false
    @State private var loading = false
    @State private var failure: String?
    /// Adding: what you call it and the key you play it in, when they differ from the
    /// catalogue's; a link each, opening into its field.
    @State private var aliasOpen = false
    @State private var alias = ""
    @State private var keyOpen = false
    @State private var key = ""

    var body: some View {
        // A guest has no list to add to (spec 060).
        if model.isGuest {
            SignInPrompt(text: tr("Sign in to add this to your tunes"), id: "sheet.signIn")
        } else {
            panel
        }
    }

    private var panel: some View {
        let current = status.flatMap(MyTunesRules.Status.init(rawValue:))
        return VStack(spacing: 14) {
            if loading {
                ProgressView().frame(maxWidth: .infinity)
            } else {
                Text(current == nil ? tr("Add this tune to your list as") : tr("This tune is on your list as"))
                    .font(.ceol(size: 17)).foregroundStyle(CeolTokens.textColor)
                    .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 0) {
                    ForEach(MyTunesRules.Status.allCases, id: \.self) { s in
                        let on = s == current
                        Button {
                            Task { if current == nil { await add(s) } else if !on { await setStatus(s) } }
                        } label: {
                            Text(TunesWords.status(s.rawValue)).font(.ceol(size: 16, weight: on ? .semibold : .medium))
                                .foregroundStyle(current == nil ? CeolTokens.primary : .white)
                                .frame(maxWidth: .infinity, minHeight: 42)
                                .background(on ? CeolTokens.primaryFill : .clear)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .disabled(busy)
                        .accessibilityIdentifier(current == nil ? "sheet.add.\(s.rawValue)" : "sheet.status.\(s.rawValue)")
                        .accessibilityAddTraits(on ? .isSelected : [])
                        if s != MyTunesRules.Status.allCases.last {
                            Rectangle().fill(current == nil ? CeolTokens.borderColor : .white.opacity(0.5)).frame(width: 1)
                        }
                    }
                }
                .fixedSize(horizontal: false, vertical: true)
                .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(
                    current == nil ? CeolTokens.borderColor : .white.opacity(0.6), lineWidth: 1))
                .clipShape(RoundedRectangle(cornerRadius: 6))
                if current == nil { addExtras }
                if current == .wantToLearn {
                    Stepper(value: Binding(get: { heard }, set: { n in Task { await setHeard(n) } }), in: 0...999) {
                        (heard == 1 ? Text("Heard it once") : Text("Heard it \(heard) times")).font(.ceol(size: 16)).foregroundStyle(.white)
                    }
                    .accessibilityIdentifier("sheet.heard")
                }
                if let failure { Text(failure).font(.ceol(size: 13)).foregroundStyle(.white) }
            }
        }
        .padding(16)
        // On your list: the web's green panel (the tune drawer's "My List" box). Not yet
        // on it: a plain outlined box, so green means "yours".
        .background(current == nil ? Color.clear : Color(red: 0.13, green: 0.29, blue: 0.19), in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(current == nil ? CeolTokens.borderColor : .clear, lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("sheet.status")
        .onAppear {
            if let a = tune.alias { alias = a; aliasOpen = true }
            if let k = tune.key { key = k; keyOpen = true }
        }
        .task(id: tune.id) { if loadsStatus { await loadStatus() } }
    }

    /// Your status for the tune, from its detail (the listen screen knows only its id).
    private func loadStatus() async {
        loading = true
        defer { loading = false }
        guard let d = try? await model.auth.client.getTuneDetail(path: .init(tuneId: tune.id), query: .init()).ok.body.json,
            let mine = JSONValue(encoding: d.sessionTune.personTuneStatus)
        else { return }
        if mine["on_list"]?.boolValue == true {
            status = mine["learn_status"]?.stringValue
            heard = mine["heard_count"]?.intValue ?? 0
        } else {
            status = nil
        }
    }

    /// Saves one op; true when the server took it.
    private func save(_ type: TuneOp._TypePayload, status s: LearnStatus? = nil, heard h: Int? = nil,
                      nameAlias: String? = nil, key: String? = nil) async -> Bool {
        busy = true
        failure = nil
        defer { busy = false }
        do {
            try await model.applyTuneOp(
                type, tuneID: tune.id, learnStatus: s, heardCount: h, nameAlias: nameAlias, key: key,
                name: tune.name, tuneType: tune.type)
            onChanged()
            return true
        } catch let f as TuneOpFailure {
            failure = f.message
        } catch {
            failure = tr("That wasn't saved. Try again.")
        }
        return false
    }

    private func setStatus(_ new: MyTunesRules.Status) async {
        let old = status
        status = new.rawValue
        if !(await save(.setStatus, status: LearnStatus(stored: new.rawValue))) { status = old }
    }

    private func add(_ new: MyTunesRules.Status) async {
        let a = alias.trimmingCharacters(in: .whitespaces)
        if await save(.add, status: LearnStatus(stored: new.rawValue), nameAlias: aliasOpen && !a.isEmpty ? a : nil,
                      key: keyOpen && !key.isEmpty ? key : nil) {
            status = new.rawValue
            heard = 1  // an add is itself a hearing, as on the web
            await onAdded()
        }
    }

    private func setHeard(_ count: Int) async {
        let old = heard
        heard = count
        if !(await save(.setHeard, heard: count)) { heard = old }
    }

    /// Before the add: "I call this something else" and "I play this in a different
    /// key", each opening into its field, as the web's add form.
    private var addExtras: some View {
        VStack(alignment: .leading, spacing: 8) {
            if aliasOpen {
                TextField("", text: $alias, prompt: Text(tr("What I call it")).foregroundStyle(CeolTokens.textMuted))
                    .font(.ceol(size: 16)).foregroundStyle(CeolTokens.textColor)
                    .autocorrectionDisabled()
                    .padding(.horizontal, 12).frame(height: 44)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                    .accessibilityIdentifier("sheet.add.alias")
            } else {
                Button("I call this something else") { withAnimation(.easeOut(duration: 0.15)) { aliasOpen = true } }
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
                    .accessibilityIdentifier("sheet.add.aliasLink")
            }
            if keyOpen {
                Menu {
                    Button("(not specified)") { key = "" }
                    ForEach(TunePreviewPane.keys, id: \.self) { k in Button(k) { key = k } }
                } label: {
                    HStack {
                        Text(key.isEmpty ? tr("Key I play it in") : key).font(.ceol(size: 16))
                            .foregroundStyle(key.isEmpty ? CeolTokens.textMuted : CeolTokens.textColor)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down").font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    }
                    .padding(.horizontal, 12).frame(height: 44)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                }
                .accessibilityIdentifier("sheet.add.key")
            } else {
                Button("I play this in a different key") { withAnimation(.easeOut(duration: 0.15)) { keyOpen = true } }
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
                    .accessibilityIdentifier("sheet.add.keyLink")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// TunebookPanel with its own status: for a tune known only by its id (the listen screen).
struct TunebookBox: View {
    let tune: TuneRef
    @State private var status: String?
    @State private var heard = 0

    var body: some View {
        TunebookPanel(tune: tune, status: $status, heard: $heard, loadsStatus: true)
    }
}

extension TuneSheet {
    /// The notation card, as the web's tune drawer: the staff (or the ABC) on white,
    /// tapped to flip opening bars ⇄ the whole tune; under it the notes / abc tabs on the
    /// left and, on the right, "open in" (thesession.org, abc-tools) and full screen.
    @ViewBuilder private func notation(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> some View {
        VStack(spacing: 10) {
            Group {
                if abcMode, let text = showFull ? t.abc : (t.incipitAbc ?? t.abc) {
                    Button { flipSize(t) } label: {
                        Text(verbatim: text).font(.system(size: 13, design: .monospaced))
                            .foregroundStyle(.black).padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Notation for \(t.tuneName)")
                    .accessibilityHint(showFull ? Text("Tap to show the opening bars") : Text("Tap to show the whole tune"))
                    .accessibilityIdentifier("sheet.notation")
                } else if !abcMode, let image = showFull ? (full ?? incipit) : incipit {
                    Button { flipSize(t) } label: {
                        Image(uiImage: image)
                            .resizable().scaledToFit()
                            .padding(6)
                            .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Notation for \(t.tuneName)")
                    .accessibilityHint(showFull ? Text("Tap to show the opening bars") : Text("Tap to show the whole tune"))
                    .accessibilityIdentifier("sheet.notation")
                } else if notationFailed {
                    Text("Couldn't draw the notation just now.").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                } else if t.incipitAbc == nil && t.abc == nil {
                    Text("No notation for this tune yet.").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                } else {
                    ProgressView().frame(height: 80)
                }
            }
            HStack(spacing: 16) {
                notationTab(tr("notes"), on: !abcMode) { abcMode = false }
                notationTab(tr("abc"), on: abcMode) { abcMode = true }
                    .disabled(t.abc == nil && t.incipitAbc == nil)
                    .opacity(t.abc == nil && t.incipitAbc == nil ? 0.4 : 1)
                Spacer()
                // Copy what's showing: the staff as an image, or the ABC as text.
                if let copy = copyable(t) {
                    Button {
                        switch copy {
                        case .image(let image): UIPasteboard.general.image = image
                        case .text(let text): UIPasteboard.general.string = text
                        }
                        copied = true
                        Task {
                            try? await Task.sleep(for: .seconds(1.5))
                            copied = false
                        }
                    } label: {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc").font(.system(size: 17))
                            .foregroundStyle(CeolTokens.primary)
                            .frame(width: 36, height: 32).contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(copied ? "Copied" : "Copy")
                    .accessibilityIdentifier("sheet.copy")
                }
                // Full screen, once the whole tune is up (the opening bars fit as they are).
                if showFull && !abcMode && full != nil {
                    Button { fullScreen = true } label: {
                        Image(systemName: "arrow.up.left.and.arrow.down.right").font(.system(size: 17))
                            .foregroundStyle(CeolTokens.primary)
                            .frame(width: 36, height: 32).contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Full screen")
                    .accessibilityIdentifier("sheet.fullScreen")
                }
                // Where else to see it: a menu, so more can join thesession.org and abc-tools.
                Menu {
                    // Names, not words to translate.
                    Link(destination: Self.theSessionURL(t)) { Label { Text(verbatim: "thesession.org") } icon: { Image(systemName: "safari") } }
                    if let url = Self.abcToolsURL(t) {
                        Link(destination: url) { Label { Text(verbatim: "abc-tools") } icon: { Image(systemName: "music.note") } }
                    }
                } label: {
                    Image(systemName: "arrow.up.right.square").font(.system(size: 18))
                        .foregroundStyle(CeolTokens.primary)
                        .frame(width: 36, height: 32).contentShape(Rectangle())
                }
                .accessibilityLabel("Open in…")
                .accessibilityIdentifier("sheet.openIn")
            }
        }
        .padding(12)
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        .alert("Hi! You found a secret feature!", isPresented: $showNotationNotice) {
            Button("OK, Got It!") {
                notationNoticeDone = true
                Self.markNotationNoticeSeen(for: model.user?.personId)
            }
        } message: {
            Text("You can tap the opening bars to see the whole tune setting.\n\nBUT! Please remember that traditional Irish music is best learned by listening, not reading. It's OK to use the notation as a reference, in a pinch, but it's always better to learn with your ears.")
        }
    }

    private enum Copyable { case image(UIImage), text(String) }

    /// What the copy button copies: whatever the card is showing.
    private func copyable(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> Copyable? {
        if abcMode { return (showFull ? t.abc : (t.incipitAbc ?? t.abc)).map(Copyable.text) }
        return (showFull ? (full ?? incipit) : incipit).map(Copyable.image)
    }

    /// Opening bars ⇄ the whole tune, fetched the first time it is asked for. The first
    /// time through to the whole tune, a word about learning by ear (once per person).
    private func flipSize(_ t: Components.Schemas.TuneDetail.SessionTunePayload) {
        showFull.toggle()
        if showFull && !abcMode { Task { await loadFull(t) } }
        if showFull && !notationNoticeDone && !Self.notationNoticeSeen(for: model.user?.personId) { showNotationNotice = true }
    }

    private static func notationNoticeKey(for personID: Int?) -> String { "CeolNotationNoticeSeen.\(personID ?? 0)" }
    private static func notationNoticeSeen(for personID: Int?) -> Bool {
        UserDefaults.standard.bool(forKey: notationNoticeKey(for: personID))
    }
    private static func markNotationNoticeSeen(for personID: Int?) {
        UserDefaults.standard.set(true, forKey: notationNoticeKey(for: personID))
    }

    /// The tune on thesession.org, at the setting drawn (a night's own, else the session's).
    static func theSessionURL(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> URL {
        let base = "https://thesession.org/tunes/\(t.tuneId)"
        if let setting = t.settingOverride ?? t.settingId { return URL(string: "\(base)#setting\(setting)")! }
        return URL(string: base)!
    }

    /// The tune in michaeleskin.com's abc-tools, the ABC in the link as the web builds it
    /// (tunesheet/logic.js abcToolsUrl): the same header, compressed the same way.
    static func abcToolsURL(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> URL? {
        guard let abc = t.abc ?? t.incipitAbc, !abc.isEmpty else { return nil }
        let body = abc.replacingOccurrences(of: "!", with: "\n")
        let type = t.tuneType ?? ""
        let meter = Self.meter(for: type)
        let formatted = "X: 1\nT: \(t.tuneName)\nR: \(type)" + (meter.map { "\nM: \($0)" } ?? "")
            + "\nL: 1/8\nK: \(t.settingKey ?? "")\n\(body)"
        let compressed = LZString.compressToEncodedURIComponent(formatted)
        let name = t.tuneName.addingPercentEncoding(withAllowedCharacters: Self.uriComponentAllowed) ?? ""
        return URL(string: "https://michaeleskin.com/abctools/abctools.html?lzw=\(compressed)&format=noten&ssp=45&name=\(name)&play=1")
    }

    /// JavaScript's encodeURIComponent leaves these alone.
    private static let uriComponentAllowed: CharacterSet = {
        var set = CharacterSet.alphanumerics
        set.insert(charactersIn: "-_.!~*'()")
        return set
    }()

    /// The time signature for a tune type, as the web's abc-tools header has it.
    private static func meter(for tuneType: String) -> String? {
        switch tuneType.lowercased() {
        case "polka": return "2/4"
        case "barndance", "hornpipe", "reel", "march": return "4/4"
        case "waltz", "mazurka": return "3/4"
        case "hop jig": return "9/8"
        case "jig", "set dance": return "6/8"
        case "slide": return "12/8"
        default: return nil
        }
    }

    private func notationTab(_ label: String, on: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Text(label).font(.ceol(size: 15, weight: on ? .semibold : .regular))
                    .foregroundStyle(on ? CeolTokens.textColor : CeolTokens.textMuted)
                Rectangle().fill(on ? CeolTokens.primary : .clear).frame(height: 2)
            }
            .fixedSize()
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
    }
}

/// The whole tune over the whole screen, on white as the notation card: as wide as the
/// screen whichever way the phone is held (turn it on its side for a wider staff), and
/// scrolling down when it is taller. Pinch to zoom in (to four times) and pan about;
/// a double tap zooms in on that spot and back out. A tap anywhere puts it away.
struct NotationFullScreen: View {
    @Environment(\.dismiss) private var dismiss
    let image: UIImage
    let name: String

    var body: some View {
        ZoomableNotation(image: image, name: name) { dismiss() }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.white)
            .overlay(alignment: .topTrailing) {
                Button { dismiss() } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Color.black.opacity(0.45))
                        .padding(12)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Close")
            }
            .ignoresSafeArea(edges: .bottom)
    }
}

/// The notation in a UIScrollView, which is what gives pinch-to-zoom its native feel
/// (the bounce at the ends, the momentum, zooming about the fingers) as Photos has it.
struct ZoomableNotation: UIViewRepresentable {
    let image: UIImage
    let name: String
    let onTap: () -> Void

    func makeUIView(context: Context) -> NotationScrollView {
        let v = NotationScrollView(image: image)
        v.imageView.accessibilityLabel = tr("Notation for \(name)")
        v.onTap = onTap
        return v
    }

    func updateUIView(_ v: NotationScrollView, context: Context) {
        v.onTap = onTap
        if v.imageView.image !== image {
            v.imageView.image = image
            v.refit()
        }
    }
}

final class NotationScrollView: UIScrollView, UIScrollViewDelegate {
    let imageView: UIImageView
    var onTap: () -> Void = {}
    /// The width the image was last fitted to: a change (the phone turned) refits it.
    private var fittedWidth: CGFloat = 0

    init(image: UIImage) {
        imageView = UIImageView(image: image)
        super.init(frame: .zero)
        delegate = self
        minimumZoomScale = 1
        maximumZoomScale = 4
        bouncesZoom = true
        showsHorizontalScrollIndicator = false
        contentInsetAdjustmentBehavior = .never
        contentInset = UIEdgeInsets(top: 12, left: 0, bottom: 12, right: 0)
        backgroundColor = .white
        imageView.isAccessibilityElement = true
        imageView.accessibilityTraits = .image
        addSubview(imageView)
        let double = UITapGestureRecognizer(target: self, action: #selector(doubleTapped))
        double.numberOfTapsRequired = 2
        addGestureRecognizer(double)
        let single = UITapGestureRecognizer(target: self, action: #selector(tapped))
        single.require(toFail: double)
        addGestureRecognizer(single)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { nil }

    override func layoutSubviews() {
        super.layoutSubviews()
        if bounds.width != fittedWidth { refit() }
    }

    /// The image as wide as the view at 1×, its height to match; zoomed out again.
    func refit() {
        let w = bounds.width
        guard w > 0, let img = imageView.image, img.size.width > 0 else { return }
        fittedWidth = w
        zoomScale = 1
        imageView.frame = CGRect(x: 0, y: 0, width: w, height: w * img.size.height / img.size.width)
        contentSize = imageView.frame.size
        contentOffset = CGPoint(x: 0, y: -contentInset.top)
        imageView.accessibilityValue = "100%"
    }

    func viewForZooming(in scrollView: UIScrollView) -> UIView? { imageView }

    /// How far in, for VoiceOver (and the UI test): "250%".
    func scrollViewDidZoom(_ scrollView: UIScrollView) {
        imageView.accessibilityValue = "\(Int((zoomScale * 100).rounded()))%"
    }

    @objc private func tapped() { onTap() }

    /// Zoomed in: back to the whole width. Else 2.5× about the tapped spot.
    @objc private func doubleTapped(_ g: UITapGestureRecognizer) {
        if zoomScale > 1.01 {
            setZoomScale(1, animated: true)
            return
        }
        let scale: CGFloat = 2.5
        let p = g.location(in: imageView)
        let size = CGSize(width: bounds.width / scale, height: bounds.height / scale)
        zoom(to: CGRect(x: p.x - size.width / 2, y: p.y - size.height / 2, width: size.width, height: size.height), animated: true)
    }
}

// MARK: - Adding a tune

/// The web's add pane (mytunes/AddTuneApp.svelte), as a drawer: the shared tune search
/// (DeepSearchSheet) over the catalogue, tunes already yours dimmed; a card's preview
/// leads to the tune's sheet, where it is added with a status; + on a card adds it at
/// once as To Learn, as the web's + rail does.
struct AddTuneSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let onChanged: () -> Void

    @State private var added: Set<Int> = []
    @State private var open: TuneRef?

    var body: some View {
        DeepSearchSheet(
            app: model, scope: .mine, initialQuery: "", preferType: nil,
            title: tr("Add a tune"), actionLabel: tr("Add to my tunes"), allowAsIs: false, allowRemote: false,
            closesOnPick: false, dimOnList: true, added: $added,
            onQuickAdd: { await quickAdd($0) },
            onClose: { dismiss() }
        ) { payload in
            guard let id = payload["tune_id"]?.intValue else { return tr("That tune isn't in Ceol's library yet.") }
            open = TuneRef(
                id: id, name: payload["name"]?.stringValue ?? "", type: payload["tune_type"]?.stringValue,
                statusKnown: false, settingID: payload["setting_id"]?.intValue,
                alias: payload["alias"]?.stringValue, key: payload["key"]?.stringValue)
            return nil
        }
        .sheet(item: $open) { tune in
            TuneSheet(tune: tune) {
                added.insert(tune.id)
                onChanged()
            }
        }
        .ceolDrawer(interactive: false)
    }

    /// + : on the list at once, as To Learn (the web's + rail), with what a session of
    /// yours already says about it. What went wrong, or nil.
    private func quickAdd(_ payload: [String: JSONValue]) async -> String? {
        guard let id = payload["tune_id"]?.intValue else { return tr("That tune isn't in Ceol's library yet.") }
        do {
            try await model.applyTuneOp(
                .add, tuneID: id, learnStatus: .wantToLearn,
                nameAlias: payload["alias"]?.stringValue, key: payload["key"]?.stringValue,
                name: payload["name"]?.stringValue, tuneType: payload["tune_type"]?.stringValue)
            if let sid = payload["setting_id"]?.intValue {
                try await model.applyTuneOp(.setSetting, tuneID: id, settingID: sid)
            }
            onChanged()
            return nil
        } catch let f as TuneOpFailure {
            return f.message
        } catch {
            return tr("That wasn't saved. Try again.")
        }
    }
}

// MARK: - The list's words, in the app's language

/// Tune types, instruments and statuses are interface words: Irish here, English as the
/// server sends them. CeolLogic's built sentences stay its English; in Irish they are
/// built again here from the same parts.
enum TunesWords {
    static func type(_ t: String) -> String {
        guard AppLanguage.code == "ga" else { return t }
        switch t.lowercased() {
        case "reel": return tr("Reel")
        case "jig": return tr("Jig")
        case "slip jig": return tr("Slip Jig")
        case "hornpipe": return tr("Hornpipe")
        case "polka": return tr("Polka")
        case "slide": return tr("Slide")
        case "waltz": return tr("Waltz")
        case "barndance": return tr("Barndance")
        case "march": return tr("March")
        case "mazurka": return tr("Mazurka")
        case "strathspey": return tr("Strathspey")
        case "three-two": return tr("Three-Two")
        case "air", "slow air": return tr("Air")
        default: return t
        }
    }

    static func instrument(_ name: String) -> String {
        guard AppLanguage.code == "ga" else { return name }
        switch name.lowercased() {
        case "fiddle": return tr("Fiddle")
        case "whistle", "tin whistle": return tr("Whistle")
        case "flute": return tr("Flute")
        case "uilleann pipes": return tr("Uilleann Pipes")
        case "concertina": return tr("Concertina")
        case "button accordion": return tr("Button Accordion")
        case "banjo": return tr("Banjo")
        case "guitar": return tr("Guitar")
        case "bouzouki": return tr("Bouzouki")
        case "bodhrán", "bodhran": return tr("Bodhrán")
        case "harp": return tr("Harp")
        case "low whistle": return tr("Low Whistle")
        case "mandolin": return tr("Mandolin")
        case "piano": return tr("Piano")
        case "piano accordion": return tr("Piano Accordion")
        default: return name
        }
    }

    /// A stored status ("want to learn", "learning", "learned").
    static func status(_ stored: String) -> String {
        switch stored {
        case "learned": tr("Learned")
        case "learning": tr("Learning")
        case "want to learn": tr("To Learn")
        default: stored
        }
    }

    static func sortMode(_ id: String) -> String {
        guard AppLanguage.code == "ga" else { return MyTunesList.sortModeLabel(id) }
        switch id {
        case "popularity": return tr("Popularity")
        case "plays": return tr("My plays")
        case "attended": return tr("Plays I attended")
        case "heard": return tr("Times heard")
        default: return tr("Name (a-z)")
        }
    }

    private static func tunes(_ n: Int) -> String { n == 1 ? tr("1 tune") : tr("\(n) tunes") }

    /// MyTunesList.resultsCountText, in Irish when the app is.
    static func resultsCount(_ rows: [MyTunesList.Row], total: Int, filters: MyTunesList.Filters) -> String {
        guard AppLanguage.code == "ga" else { return MyTunesList.resultsCountText(rows, total: total, filters: filters) }
        let n = rows.count
        if !filters.instrument.isEmpty {
            let on = rows.filter { !$0.dimmed }.count
            return tr("\(on) of \(tunes(n)) on \(instrument(filters.instrument))")
        }
        if n < total { return tr("Showing \(n) of \(total) tunes") }
        return tunes(total)
    }

    /// MyTunesList.noResultsMessage, in Irish when the app is.
    static func noResults(_ f: MyTunesList.Filters) -> String {
        guard AppLanguage.code == "ga" else { return MyTunesList.noResultsMessage(f) }
        if !f.search.isEmpty, let id = MyTunesRules.extractTuneID(f.search) { return tr("No tune with ID \(String(id)) found") }
        var parts: [String] = []
        if !f.search.isEmpty { parts.append(tr("containing '\(f.search)'")) }
        if !f.status.isEmpty { parts.append(tr("in '\(status(f.status))' status")) }
        let rest = parts.joined(separator: " ")
        switch (f.type.isEmpty, rest.isEmpty) {
        case (true, true): return tr("No tunes found")
        case (true, false): return tr("No tunes \(rest) found")
        case (false, true): return tr("No tunes of type \(type(f.type)) found")
        case (false, false): return tr("No tunes of type \(type(f.type)) \(rest) found")
        }
    }
}

/// Whose setting the chooser changes: yours, a session's, or one night's.
enum SettingLayer: Identifiable, Hashable {
    case mine
    case session(path: String)
    case night(path: String, instanceID: Int)

    var id: Self { self }

    /// The line under the staff, beside Change Setting.
    var prompt: String {
        switch self {
        case .mine: tr("I play a different version")
        case .session: tr("We play a different version")
        case .night: tr("We played a different version on this night")
        }
    }

    func heading(sessionName: String) -> String {
        switch self {
        case .mine: tr("Which version do you play?")
        case .session: tr("Which version does \(sessionName) play?")
        case .night: tr("Which version was played that night?")
        }
    }
}

/// Your tags for a tune (spec 042), as the web's tag field: a chip with an ✕ for each,
/// and a field that adds one on return, spelt as the server keeps it (lower case,
/// hyphenated). The Tunes tab's filter offers every tag you've used.
struct TagsEditor: View {
    let tags: [String]
    let busy: Bool
    let onChange: ([String]) -> Void
    @State private var draft = ""

    var body: some View {
        FlowLayout(spacing: 8) {
            ForEach(tags, id: \.self) { tag in
                HStack(spacing: 5) {
                    Text(tag).font(.ceol(size: 14, weight: .medium)).lineLimit(1)
                    Button { onChange(tags.filter { $0 != tag }) } label: {
                        Image(systemName: "xmark").font(.system(size: 10, weight: .bold))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(tr("Remove tag \(tag)"))
                }
                .foregroundStyle(CeolTokens.primary)
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(CeolTokens.primary.opacity(0.14), in: Capsule())
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("sheet.tag.\(tag)")
            }
            TextField("", text: $draft, prompt: Text("Add a tag").foregroundStyle(CeolTokens.textMuted))
                .font(.ceol(size: 15))
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .onSubmit(add)
                .padding(.horizontal, 10)
                .frame(minWidth: 110).frame(height: 32)
                .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                .accessibilityIdentifier("sheet.tagInput")
        }
        .disabled(busy)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("sheet.tags")
    }

    private func add() {
        let tag = MyTunesList.normalizeTag(draft)
        draft = ""
        guard !tag.isEmpty, !tags.contains(tag) else { return }
        onChange(tags + [tag])
    }
}

// MARK: - A guest's Tunes (spec 060)

typealias TopTunesPayload = Components.Schemas.TopTunes

/// The Tunes tab for a guest: no list of your own, so the most common tunes (the web's
/// public Tunes page), and the search reaches the whole catalogue by name.
struct GuestTunesView: View {
    @Environment(AppModel.self) private var model
    private var state: Resource<TopTunesPayload> { model.topTunes }
    @State private var search = ""
    @State private var results: [Components.Schemas.TuneSearch.TunesPayloadPayload]?
    @State private var searchFailed = false
    @State private var open: TuneRef?
    @FocusState private var searching: Bool

    var body: some View {
        NavigationStack {
            Resourced(resource: state) { payload in list(payload) }
                .background(CeolTokens.bgColor)
                .ceolKept(state)
                .ceolRootBar(tr("Tunes"), sharePath: "/tunes")
                .task(id: search) { await searchCatalogue() }
                .onChange(of: open) { _, tune in if tune != nil { searching = false } }
                .sheet(item: $open) { TuneSheet(tune: $0) }
                .onChange(of: model.rootRequests[.tunes]) { _, _ in
                    open = nil
                    searching = false
                }
                .task { await state.refresh(ifOlderThan: 60 * 60) }
        }
    }

    /// The catalogue's name search, after a short pause in typing; two characters at least.
    private func searchCatalogue() async {
        let q = search.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2 else {
            results = nil
            return
        }
        try? await Task.sleep(for: .milliseconds(300))
        guard !Task.isCancelled else { return }
        do {
            results = try await model.auth.client.searchTunes(query: .init(q: q)).ok.body.json.tunes
            searchFailed = false
        } catch {
            if !Task.isCancelled { searchFailed = true }
        }
    }

    @ViewBuilder private func list(_ payload: TopTunesPayload) -> some View {
        List {
            VStack(alignment: .leading, spacing: 10) {
                SignInPrompt(text: tr("Sign in to keep your own list of tunes"), id: "tunes.signIn")
                SearchRow(text: $search, prompt: tr("Search"), fieldID: "tunes.search", focused: $searching)
                Text(results == nil ? tr("The most common tunes, by how many players have them in a tunebook on thesession.org.") : tr("Tunes on Ceol"))
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            }
            .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 6, trailing: 16))
            .listRowBackground(CeolTokens.bgColor)
            .listRowSeparator(.hidden)
            if let results {
                if searchFailed {
                    Text("Couldn't search the catalogue.").foregroundStyle(CeolTokens.textMuted).ceolRow()
                } else if results.isEmpty {
                    Text("No tunes match.").font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                        .listRowBackground(CeolTokens.bgColor).listRowSeparator(.hidden)
                }
                ForEach(results, id: \.tuneId) { r in
                    row(id: r.tuneId, name: r.name, type: r.tuneType, note: r.abcOnly ? tr("♪ notes match") : nil)
                }
            } else {
                ForEach(payload.tunes, id: \.tuneId) { t in
                    row(id: t.tuneId, name: t.name, type: t.tuneType, note: nil)
                }
            }
        }
        .ceolPlainList()
        .refreshable { await state.refresh() }
    }

    private func row(id: Int, name: String, type: String?, note: String?) -> some View {
        Button {
            open = TuneRef(id: id, name: name, type: type)
        } label: {
            TuneRow(name: name, type: type, status: nil, note: note)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("tunes.row")
        .ceolRow()
    }
}
