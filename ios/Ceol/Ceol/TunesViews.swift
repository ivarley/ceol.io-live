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
}

struct TunesView: View {
    @Environment(AppModel.self) private var model
    @State private var state: LoadState<MyTunesPayload> = .loading
    @State private var status: MyTunesRules.Status?
    @State private var type: String?
    @State private var search = ""
    @State private var catalogue: [DeepSearchResult] = []
    @State private var catalogueFailed = false
    @State private var open: TuneRef?
    @State private var failure: String?
    @FocusState private var searching: Bool

    var body: some View {
        NavigationStack {
            Loaded(state: state, retry: load) { payload in list(payload) }
                .ceolBackground()
                .navigationTitle("Tunes")
                .searchable(text: $search, prompt: "Name, notes, or notes like GED BED")
                .searchFocused($searching)
                .task(id: search) { await searchCatalogue() }
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) { typeMenu }
                }
                // The search keyboard would otherwise stay up over the sheet.
                .onChange(of: open) { _, tune in if tune != nil { searching = false } }
                .sheet(item: $open) { TuneSheet(tune: $0) { Task { await load() } } }
                .task { if state.value == nil { await load() } }
                .alert("Not saved", isPresented: Binding(get: { failure != nil }, set: { if !$0 { failure = nil } })) {
                    Button("OK") {}
                } message: {
                    Text(failure ?? "")
                }
        }
    }

    private var typeMenu: some View {
        Menu {
            Picker("Tune type", selection: $type) {
                Text("All tune types").tag(String?.none)
                ForEach(types, id: \.self) { Text($0).tag(Optional($0)) }
            }
        } label: {
            Label(type ?? "All types", systemImage: "line.3.horizontal.decrease.circle")
        }
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
        let shown = MyTunesRules.filter(payload.tunes.map(\.entry), status: status, type: type, search: search)
        // Less any you added since the search ran.
        let catalogue = catalogue.filter { byID[$0.tuneId] == nil }
        List {
            Section {
                Picker("Status", selection: $status) {
                    ForEach(MyTunesRules.Status.allCases, id: \.self) { Text($0.label).tag(Optional($0)) }
                    Text("All").tag(MyTunesRules.Status?.none)
                }
                .pickerStyle(.segmented)
                .listRowBackground(Color.clear)
            }
            Section {
                ForEach(shown, id: \.tuneID) { e in
                    let t = byID[e.tuneID]
                    Button {
                        open = TuneRef(
                            id: e.tuneID, name: e.name, type: e.type, status: e.status, heardCount: t?.heardCount,
                            notes: e.notes)
                    } label: {
                        TuneRow(name: e.name, type: e.type, status: e.status)
                    }
                    .buttonStyle(.plain)
                    .swipeActions(edge: .leading) {
                        // The web's swipe: one more hearing of a tune you want to learn.
                        if e.status == MyTunesRules.Status.wantToLearn.rawValue {
                            Button("Heard it") { Task { await heard(e.tuneID, count: (t?.heardCount ?? 0) + 1) } }
                                .tint(CeolTokens.primaryFill)
                        }
                    }
                }
            } header: {
                Text(MyTunesRules.countText(shown: shown.count, total: payload.tunes.count))
            } footer: {
                if shown.isEmpty && catalogue.isEmpty {
                    Text(search.isEmpty ? "No tunes here yet." : "None of your tunes match.")
                }
            }
            if !catalogue.isEmpty || catalogueFailed {
                Section("Not on your list") {
                    if catalogueFailed {
                        Text("Couldn't search the catalogue.").foregroundStyle(CeolTokens.secondary)
                    }
                    ForEach(catalogue, id: \.tuneId) { r in
                        Button {
                            open = TuneRef(id: r.tuneId, name: r.name, type: r.tuneType)
                        } label: {
                            TuneRow(name: r.name, type: r.tuneType, status: nil, note: r.abcOnly ? "♪ notes match" : nil)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("catalogue.row")
                    }
                }
            }
        }
        .refreshable { await load() }
    }
}

private struct TuneRow: View {
    let name: String
    let type: String?
    let status: String?
    var note: String? = nil

    var body: some View {
        HStack(spacing: 10) {
            if let status { StatusBadge(status: status) }
            VStack(alignment: .leading, spacing: 2) {
                Text(name).foregroundStyle(CeolTokens.textColor)
                if let note { Text(note).font(.caption).foregroundStyle(CeolTokens.warning) }
            }
            Spacer()
            if let type {
                Text(type).font(.caption).padding(.horizontal, 6).padding(.vertical, 2)
                    .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 3))
                    .foregroundStyle(.white)
            }
        }
        .contentShape(Rectangle())
    }
}

/// The learn-status badge, in the web's colours (want to learn blue, learning yellow,
/// learned green) and words.
struct StatusBadge: View {
    let status: String

    var body: some View {
        let (bg, fg): (Color, Color) =
            switch status {
            case "learning": (Color(red: 0.29, green: 0.25, blue: 0.12), Color(red: 1, green: 0.92, blue: 0.65))
            case "learned": (Color(red: 0.12, green: 0.29, blue: 0.18), Color(red: 0.76, green: 0.9, blue: 0.8))
            default: (Color(red: 0.12, green: 0.23, blue: 0.29), Color(red: 0.8, green: 0.9, blue: 1))
            }
        Text(MyTunesRules.Status(rawValue: status)?.label ?? status)
            .font(.caption.weight(.medium))
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(bg, in: Capsule())
            .foregroundStyle(fg)
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
                .ceolBackground()
                .navigationTitle(tune.name)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
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
        .presentationDetents([.large])
    }

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

    /// Your list: the status, the heard count while you want to learn it, notes, and
    /// Remove. Or, for a tune not on it, Add with a status.
    @ViewBuilder private var yourList: some View {
        if let current = status.flatMap(MyTunesRules.Status.init(rawValue:)) {
            Section {
                Picker("Status", selection: Binding(get: { current }, set: { new in Task { await setStatus(new) } })) {
                    ForEach(MyTunesRules.Status.allCases, id: \.self) { Text($0.label).tag($0) }
                }
                .pickerStyle(.segmented)
                .accessibilityIdentifier("sheet.status")
                if current == .wantToLearn {
                    Stepper(value: Binding(get: { heard }, set: { n in Task { await setHeard(n) } }), in: 0...999) {
                        LabeledContent("Heard it", value: heard == 1 ? "once" : "\(heard) times")
                    }
                    .accessibilityIdentifier("sheet.heard")
                }
                TextField("Notes", text: $notes, axis: .vertical)
                    .lineLimit(1...6)
                    .accessibilityIdentifier("sheet.notes")
                if notes != savedNotes {
                    Button("Save notes") { Task { await saveNotes() } }.disabled(busy)
                }
            } header: {
                Text("On your list")
            } footer: {
                if let failure { Text(failure).foregroundStyle(CeolTokens.danger) }
            }
        } else {
            Section {
                Menu {
                    ForEach(MyTunesRules.Status.allCases, id: \.self) { s in
                        Button(s.label) { Task { await add(s) } }
                            .accessibilityIdentifier("sheet.add.\(s.rawValue)")
                    }
                } label: {
                    // The whole row, not just the words, opens the menu.
                    Label("Add to my tunes", systemImage: "plus.circle")
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                }
                .disabled(busy)
                .accessibilityIdentifier("sheet.add")
            } footer: {
                if let failure { Text(failure).foregroundStyle(CeolTokens.danger) }
            }
        }
    }

    private func load() async {
        do {
            let d = try await model.auth.client.getTuneDetail(path: .init(tuneId: tune.id)).ok.body.json
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
        List {
            Section {
                Text([t.tuneType, t.settingKey].compactMap { $0 }.joined(separator: " · "))
                    .foregroundStyle(CeolTokens.secondary)
            }
            yourList
            Section {
                if let image = showFull ? (full ?? incipit) : incipit {
                    Image(uiImage: image)
                        .resizable().scaledToFit()
                        .background(Color.white)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                        .accessibilityLabel("Notation for \(t.tuneName)")
                } else if notationFailed {
                    Text("Couldn't draw the notation just now.").foregroundStyle(CeolTokens.secondary)
                } else if t.incipitAbc == nil && t.abc == nil {
                    Text("No notation for this tune yet.").foregroundStyle(CeolTokens.secondary)
                } else {
                    ProgressView()
                }
                if t.abc != nil {
                    Toggle("Whole tune", isOn: $showFull)
                        .onChange(of: showFull) { _, on in if on { Task { await loadFull(t) } } }
                }
            } header: {
                Text("Notation")
            }
            Section("Played") {
                LabeledContent("At sessions on Ceol", value: "\(t.globalPlayCount)")
                LabeledContent("Sessions that play it", value: "\(t.sessionCount)")
                if let books = t.tunebookCount {
                    LabeledContent("TheSession.org tunebooks", value: "\(books)")
                }
            }
            if let aliases = t.aliases, !aliases.isEmpty {
                Section("Also called") { ForEach(aliases, id: \.self) { Text($0) } }
            }
            Section {
                Link("View on TheSession.org", destination: URL(string: "https://thesession.org/tunes/\(t.tuneId)")!)
            }
            if status != nil {
                Section {
                    Button("Remove from my tunes", role: .destructive) { confirmRemove = true }
                        .disabled(busy)
                        .accessibilityIdentifier("sheet.remove")
                }
            }
        }
    }
}
