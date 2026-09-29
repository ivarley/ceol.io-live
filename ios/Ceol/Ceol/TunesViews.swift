// The Tunes tab (plan Phase 3c): your list, and the tune sheet — the app's twins of
// the Svelte /my-tunes and the shared tune drawer, from the same payloads. The sheet
// edits a tune on your list (status, heard count, notes, remove) or adds one from the
// catalogue (Phase 4a); the list reloads after each change.
//
// The search field reaches the whole catalogue as on the web: your matching tunes
// first, then "Not on your list" from the server's catalogue search (name or notation).

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
    /// Opened from a session's page: the sheet adds that session's plays.
    var sessionPath: String? = nil
    /// Whether `status` is known. Opened from somewhere other than your list, the sheet
    /// reads your status from the tune's detail instead.
    var statusKnown = true
}

struct TunesView: View {
    @Environment(AppModel.self) private var model
    @State private var state: LoadState<MyTunesPayload> = .loading
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
        NavigationStack {
            Loaded(state: state, retry: load) { payload in list(payload) }
                .background(CeolTokens.bgColor)
                .ceolRootBar("Tunes", sharePath: model.tunesStatus.map { "/my-tunes?status=\($0.rawValue.replacingOccurrences(of: " ", with: "+"))" } ?? "/my-tunes")
                .task(id: search) { await searchCatalogue() }
                // The search keyboard would otherwise stay up over the sheet.
                .onChange(of: open) { _, tune in if tune != nil { searching = false } }
                .sheet(item: $open) { TuneSheet(tune: $0) { Task { await load() } } }
                .sheet(isPresented: $filtering) {
                    TunesFilterSheet(filters: $filters, sort: $sort, types: types, instruments: instruments)
                }
                .sheet(isPresented: $adding) { AddTuneSheet { Task { await load() } } }
                .task { if state.value == nil { await load() } }
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
            failure = "That wasn't saved. Try again."
        }
    }

    private func load() async {
        do {
            state = .loaded(try await model.auth.client.getMyTunes().ok.body.json)
        } catch {
            if state.value == nil { state = .failed(loadFailureMessage(error)) }
        }
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
                    text: $search, prompt: "Search", fieldID: "tunes.search",
                    onAdd: { adding = true }, addID: "tunes.add", addLabel: "Add a tune",
                    focused: $searching,
                    onFilter: { filtering = true },
                    filterCount: filters.activeCount + (sort == MyTunesList.Sort() ? 0 : 1))
                Picker("Status", selection: Binding(get: { model.tunesStatus }, set: { model.tunesStatus = $0 })) {
                    ForEach(MyTunesRules.Status.allCases, id: \.self) { Text($0.label).tag(Optional($0)) }
                    Text("All").tag(MyTunesRules.Status?.none)
                }
                .pickerStyle(.segmented)
                HStack {
                    Text(MyTunesList.resultsCountText(rows, total: payload.tunes.count, filters: f))
                    if sort.type != "alpha" || sort.descending {
                        Text("· \(MyTunesList.sortModeLabel(sort.type)) \(sort.descending ? "↓" : "↑")")
                    }
                }
                .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            }
            .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 6, trailing: 16))
            .listRowBackground(CeolTokens.bgColor)
            .listRowSeparator(.hidden)
            ForEach(Array(rows.enumerated()), id: \.element.item.tuneID) { i, row in
                let e = row.item
                let t = byID[e.tuneID]
                if i == firstDimmed {
                    // The web's heading between the tunes on the instrument and the rest.
                    Text("Not on \(filters.instrument)").font(.ceol(size: 13, weight: .semibold)).textCase(.uppercase)
                        .tracking(0.8).foregroundStyle(CeolTokens.textMuted)
                        .listRowInsets(EdgeInsets(top: 18, leading: 16, bottom: 4, trailing: 16))
                        .listRowBackground(CeolTokens.bgColor)
                }
                Button {
                    open = TuneRef(
                        id: e.tuneID, name: e.name, type: e.type, status: e.status, heardCount: t?.heardCount,
                        notes: e.notes)
                } label: {
                    TuneRow(
                        name: e.name, type: MyTunesList.typeBadgeLabel(e, sortType: sort.type), status: e.status,
                        note: row.abcOnly ? "♪ notes match" : nil, typeIsCount: sort.type != "alpha")
                }
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
                Text(payload.tunes.isEmpty ? "No tunes here yet." : MyTunesList.noResultsMessage(f))
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
                        TuneRow(name: r.name, type: r.tuneType, status: nil, note: r.abcOnly ? "♪ notes match" : nil)
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
            attendedPlays: attendedPlayCount, instrumentStatus: overrides)
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
                TypeChip(label: type, size: 15)
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
    @State private var busy = false
    @State private var failure: String?
    @State private var confirmRemove = false
    @State private var detail: LoadState<Components.Schemas.TuneDetail> = .loading
    @State private var incipit: UIImage?
    @State private var full: UIImage?
    @State private var showFull = false
    @State private var notationFailed = false

    var body: some View {
        NavigationStack {
            Loaded(state: detail, retry: load) { d in content(d.sessionTune) }
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
                    await load()
                }
                .confirmationDialog("Remove \(tune.name) from your tunes?", isPresented: $confirmRemove, titleVisibility: .visible) {
                    Button("Remove", role: .destructive) {
                        Task { if await save(.remove) { dismiss() } }
                    }
                } message: {
                    Text("Its status, notes and heard count go with it.")
                }
        }
        .ceolDrawer()
    }

    static let surface = CeolTokens.drawerBg

    /// Saves one op; true when the server took it.
    @discardableResult
    private func save(_ type: TuneOp._TypePayload, status s: LearnStatus? = nil, heard h: Int? = nil, notes n: String? = nil) async -> Bool {
        busy = true
        failure = nil
        defer { busy = false }
        do {
            try await model.applyTuneOp(type, tuneID: tune.id, learnStatus: s, heardCount: h, notes: n)
            onChanged()
            return true
        } catch let f as TuneOpFailure {
            failure = f.message
        } catch {
            failure = "That wasn't saved. Try again."
        }
        return false
    }

    private func setStatus(_ new: MyTunesRules.Status) async {
        let old = status
        status = new.rawValue
        if !(await save(.setStatus, status: LearnStatus(stored: new.rawValue))) { status = old }
    }

    private func add(_ new: MyTunesRules.Status) async {
        if await save(.add, status: LearnStatus(stored: new.rawValue)) {
            status = new.rawValue
            heard = 1  // an add is itself a hearing, as on the web
        }
    }

    private func setHeard(_ count: Int) async {
        let old = heard
        heard = count
        if !(await save(.setHeard, heard: count)) { heard = old }
    }

    private func saveNotes() async {
        let trimmed = notes.trimmingCharacters(in: .whitespacesAndNewlines)
        if await save(.setNotes, notes: trimmed.isEmpty ? nil : trimmed) {
            notes = trimmed
            savedNotes = trimmed
        }
    }

    /// Your list, in the web's green panel: "This tune is on your list as" and the three
    /// statuses as buttons, the heard count while you want to learn it; or, for a tune
    /// not on it, the three ways to add it.
    @ViewBuilder private var yourList: some View {
        let current = status.flatMap(MyTunesRules.Status.init(rawValue:))
        VStack(spacing: 14) {
            Text(current == nil ? "Add this tune to your list as" : "This tune is on your list as")
                .font(.ceol(size: 17)).foregroundStyle(CeolTokens.textColor)
                .frame(maxWidth: .infinity, alignment: .leading)
            HStack(spacing: 0) {
                ForEach(MyTunesRules.Status.allCases, id: \.self) { s in
                    let on = s == current
                    Button {
                        Task { if current == nil { await add(s) } else if !on { await setStatus(s) } }
                    } label: {
                        Text(s.label).font(.ceol(size: 16, weight: on ? .semibold : .medium))
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
            if current == .wantToLearn {
                Stepper(value: Binding(get: { heard }, set: { n in Task { await setHeard(n) } }), in: 0...999) {
                    Text("Heard it \(heard == 1 ? "once" : "\(heard) times")").font(.ceol(size: 16)).foregroundStyle(.white)
                }
                .accessibilityIdentifier("sheet.heard")
            }
            if let failure { Text(failure).font(.ceol(size: 13)).foregroundStyle(.white) }
        }
        .padding(16)
        // On your list: the web's green panel (the tune drawer's "My List" box). Not yet
        // on it: a plain outlined box, so green means "yours".
        .background(current == nil ? Color.clear : Color(red: 0.13, green: 0.29, blue: 0.19), in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(current == nil ? CeolTokens.borderColor : .clear, lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("sheet.status")
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
        }
    }

    private func load() async {
        do {
            let d = try await model.auth.client.getTuneDetail(
                path: .init(tuneId: tune.id), query: .init(session: tune.sessionPath)
            ).ok.body.json
            if !tune.statusKnown, let mine = JSONValue(encoding: d.sessionTune.personTuneStatus),
                mine["on_list"]?.boolValue == true
            {
                status = mine["learn_status"]?.stringValue
                heard = mine["heard_count"]?.intValue ?? 0
                notes = mine["notes"]?.stringValue ?? ""
                savedNotes = notes
            }
            detail = .loaded(d)
            await loadNotation(d.sessionTune)
        } catch {
            detail = .failed(loadFailureMessage(error))
        }
    }

    private func loadNotation(_ t: Components.Schemas.TuneDetail.SessionTunePayload) async {
        if let img = decode(t.incipitImage) {
            incipit = img
        } else if let r = try? await model.auth.client.getTuneIncipitImage(path: .init(tuneId: tune.id)).ok.body.json {
            incipit = decode(r.image)
        }
        notationFailed = incipit == nil && t.incipitAbc != nil
    }

    private func loadFull(_ t: Components.Schemas.TuneDetail.SessionTunePayload) async {
        guard full == nil else { return }
        if let img = decode(t.image) {
            full = img
        } else if let setting = t.settingId,
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
                    if let type = t.tuneType { TypeChip(label: type, size: 16) }
                    Text(t.tuneName).font(.ceol(size: 26, weight: .semibold, relativeTo: .title)).foregroundStyle(CeolTokens.textColor)
                }
                notation(t)
                yourList
                VStack(spacing: 0) {
                    if tune.sessionPath != nil {
                        stat("Played at this session", t.timesPlayed)
                        Hairline()
                    }
                    stat("At sessions on Ceol", t.globalPlayCount)
                    Hairline()
                    stat("Sessions that play it", t.sessionCount)
                    if let books = t.tunebookCount {
                        Hairline()
                        stat("TheSession.org tunebooks", books)
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
                    Link("TheSession.org", destination: URL(string: "https://thesession.org/tunes/\(t.tuneId)")!)
                        .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
                    Spacer()
                    if status != nil {
                        Button("Remove From My Tunes") { confirmRemove = true }
                            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                            .disabled(busy)
                            .accessibilityIdentifier("sheet.remove")
                    }
                }
            }
            .padding(20)
        }
    }

    private func stat(_ label: String, _ value: Int) -> some View {
        HStack { Text(label); Spacer(); Text("\(value)").foregroundStyle(CeolTokens.textMuted) }
            .font(.ceol(size: 16)).padding(.vertical, 12)
    }

    /// The notation card: white, the opening bars or the whole tune, and the switch
    /// between them underneath, as the web's notes tab.
    @ViewBuilder private func notation(_ t: Components.Schemas.TuneDetail.SessionTunePayload) -> some View {
        VStack(spacing: 10) {
            if let image = showFull ? (full ?? incipit) : incipit {
                Image(uiImage: image)
                    .resizable().scaledToFit()
                    .padding(6)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                    .accessibilityLabel("Notation for \(t.tuneName)")
            } else if notationFailed {
                Text("Couldn't draw the notation just now.").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            } else if t.incipitAbc == nil && t.abc == nil {
                Text("No notation for this tune yet.").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            } else {
                ProgressView().frame(height: 80)
            }
            if t.abc != nil {
                HStack(spacing: 22) {
                    notationTab("Opening bars", on: !showFull) { showFull = false }
                    notationTab("Whole tune", on: showFull) {
                        showFull = true
                        Task { await loadFull(t) }
                    }
                    Spacer()
                }
            }
        }
        .padding(12)
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
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

// MARK: - Adding a tune

/// The web's add pane (mytunes/AddTuneApp.svelte), as a drawer: search the catalogue by
/// name, notes ("GED BED") or a pasted thesession.org link; tap a tune to see it and add
/// it with a status; or + on a row adds it at once as To Learn, as the web's + rail does.
struct AddTuneSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let onChanged: () -> Void

    @State private var query = ""
    @State private var results: [DeepSearchResult] = []
    @State private var searched = false
    @State private var failed = false
    @State private var added: Set<Int> = []
    @State private var open: TuneRef?
    @State private var failure: String?
    @FocusState private var focused: Bool

    var body: some View {
        NavigationStack {
            List {
                SearchRow(text: $query, prompt: "Tune name, notes, or a link", fieldID: "addTune.query", focused: $focused)
                    .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 10, trailing: 16))
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
                if let failure {
                    Text(failure).font(.ceol(size: 14)).foregroundStyle(CeolTokens.danger)
                        .listRowBackground(Color.clear).listRowSeparator(.hidden)
                }
                if failed {
                    Text("Couldn't search the catalogue. Check your connection.").font(.ceol(size: 15))
                        .foregroundStyle(CeolTokens.textMuted).listRowBackground(Color.clear)
                } else if searched && results.isEmpty {
                    Text("No tunes found.").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                        .listRowBackground(Color.clear)
                } else if !searched {
                    Text("Search the tunes on Ceol by name, by the notes (\"GED BED\"), or paste a thesession.org link.")
                        .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                        .listRowBackground(Color.clear).listRowSeparator(.hidden)
                }
                ForEach(results, id: \.tuneId) { r in
                    let onList = r.onList || added.contains(r.tuneId)
                    HStack(spacing: 10) {
                        Button {
                            open = TuneRef(id: r.tuneId, name: r.name, type: r.tuneType, statusKnown: false)
                        } label: {
                            TuneRow(name: r.name, type: r.tuneType, status: nil, note: r.abcOnly ? "♪ notes match" : nil)
                        }
                        .buttonStyle(.plain)
                        // Already yours: dimmed, and still opens.
                        .opacity(onList ? 0.45 : 1)
                        .accessibilityIdentifier("addTune.row")
                        if onList {
                            Image(systemName: "checkmark").foregroundStyle(CeolTokens.primary).frame(width: 36)
                                .accessibilityLabel("On your list")
                        } else {
                            Button { Task { await quickAdd(r) } } label: {
                                Image(systemName: "plus").font(.system(size: 17, weight: .medium))
                                    .foregroundStyle(CeolTokens.primary).frame(width: 36, height: 36)
                                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Add \(r.name) as To Learn")
                            .accessibilityIdentifier("addTune.quickAdd")
                        }
                    }
                    .listRowBackground(Color.clear)
                    .listRowSeparatorTint(CeolTokens.borderColor)
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(CeolTokens.drawerBg)
            .navigationTitle("Add a tune")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .task(id: query) { await search() }
            .onAppear { focused = true }
            .sheet(item: $open) { tune in
                TuneSheet(tune: tune) {
                    added.insert(tune.id)
                    onChanged()
                }
            }
        }
        .ceolDrawer()
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2 else {
            results = []
            searched = false
            return
        }
        try? await Task.sleep(for: .milliseconds(300))
        guard !Task.isCancelled else { return }
        do {
            results = try await model.auth.client.deepSearchTunes(query: .init(q: q, limit: 40)).ok.body.json.results
            failed = false
            searched = true
        } catch {
            if !Task.isCancelled { failed = true }
        }
    }

    /// + : on the list at once, as To Learn (the web's + rail).
    private func quickAdd(_ r: DeepSearchResult) async {
        failure = nil
        do {
            try await model.applyTuneOp(.add, tuneID: r.tuneId, learnStatus: .wantToLearn)
            added.insert(r.tuneId)
            onChanged()
        } catch let f as TuneOpFailure {
            failure = f.message
        } catch {
            failure = "That wasn't saved. Try again."
        }
    }
}
