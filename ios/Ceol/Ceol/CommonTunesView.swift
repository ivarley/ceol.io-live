// Common Tunes: the tunes you and someone on a session's list both know or are
// learning, the app's own screen for the web's /me/and/<id> page. Opened from their
// person sheet; filtered and sorted by CeolLogic.CommonTunes, the page's rules. A tune
// opens its sheet, where you can see it and change your own status for it.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

struct CommonTunesView: View {
    @Environment(AppModel.self) private var model
    let personID: Int
    let name: String

    @State private var tunes: LoadState<[CommonTunes.Tune]> = .loading
    @State private var search = ""
    @State private var type = ""
    @State private var sort = CommonTunes.Sort()
    @State private var filtering = false
    @State private var openTune: TuneRef?
    @FocusState private var searching: Bool

    var body: some View {
        Loaded(state: tunes, retry: load) { all in content(all) }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Tunes In Common")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $filtering) {
                CommonTunesFilterSheet(type: $type, sort: $sort, types: CommonTunes.types(tunes.value ?? []))
            }
            .sheet(item: $openTune) { TuneSheet(tune: $0) }
            .task { if tunes.value == nil { await load() } }
    }

    private func load() async {
        do {
            switch try await model.auth.client.getCommonTunes(path: .init(otherPersonId: personID)) {
            case .ok(let ok):
                tunes = .loaded(try ok.body.json.tunes.map {
                    CommonTunes.Tune(tuneID: $0.tuneId, name: $0.tuneName, type: $0.tuneType, tunebookCount: $0.tunebookCount)
                })
            case .default(_, let error):
                tunes = .failed((try? error.body.json)?.message ?? tr("Couldn't load the tunes you have in common."))
            }
        } catch {
            tunes = .failed(loadFailureMessage(error))
        }
    }

    @ViewBuilder private func content(_ all: [CommonTunes.Tune]) -> some View {
        let shown = CommonTunes.filter(all, search: search, type: type, sort: sort)
        let filterCount = (type.isEmpty ? 0 : 1) + (sort == .init() ? 0 : 1)
        List {
            VStack(alignment: .leading, spacing: 10) {
                Text("You and \(name) both know or are learning these.")
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                if !all.isEmpty {
                    SearchRow(
                        text: $search, prompt: tr("Search tunes…"), fieldID: "common.search", focused: $searching,
                        onFilter: {
                            searching = false
                            filtering = true
                        },
                        filterCount: filterCount)
                    Text(shown.count == all.count
                        ? (all.count == 1 ? tr("1 tune") : tr("\(all.count) tunes"))
                        : tr("Showing \(shown.count) of \(all.count) tunes"))
                        .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                        .accessibilityIdentifier("common.count")
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 10)
            .listRowInsets(EdgeInsets())
            .listRowBackground(Color.clear)
            .listRowSeparator(.hidden)

            if all.isEmpty {
                VStack(spacing: 6) {
                    Text("No tunes in common yet").font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                    Text("Neither of you has a tune the other has marked learned or learning.")
                        .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(24)
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
            } else if shown.isEmpty {
                Text("No tunes found matching \"\(search)\"")
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(24)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }

            ForEach(shown, id: \.tuneID) { tune in
                Button {
                    searching = false
                    openTune = TuneRef(id: tune.tuneID, name: tune.name, type: tune.type, statusKnown: false)
                } label: {
                    HStack(spacing: 10) {
                        Text(tune.name).font(.ceol(size: 18, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                            .lineLimit(1)
                        Spacer(minLength: 8)
                        // Sorted by popularity, the row says how popular.
                        if sort.mode == .popular {
                            Text("\(tune.tunebookCount)").font(.ceol(size: 14)).monospacedDigit()
                                .foregroundStyle(CeolTokens.textMuted)
                                .accessibilityLabel(Text("In \(tune.tunebookCount) tunebooks"))
                        }
                        if let t = tune.type {
                            Pill(text: SessionsL10n.typeName(t), style: .filled, color: CeolTokens.primaryFill, size: 12)
                        }
                    }
                    .padding(.horizontal, 16).padding(.vertical, 12)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("common.tune")
                .listRowInsets(EdgeInsets())
                .listRowBackground(Color.clear)
                .listRowSeparatorTint(CeolTokens.borderColor)
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .scrollDismissesKeyboard(.immediately)
        .refreshable { await load() }
    }
}

/// Type, then the order, laid out as the People drawer is.
struct CommonTunesFilterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var type: String
    @Binding var sort: CommonTunes.Sort
    let types: [String]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    SortSection(
                        options: [(CommonTunes.SortMode.name, tr("Name")), (.popular, tr("Popular"))],
                        mode: Binding(get: { sort.mode }, set: { mode in
                            if mode != sort.mode { sort = .init(mode: mode) }
                        }),
                        descending: $sort.descending)
                    if types.count >= 2 {
                        ChoiceChips(
                            label: tr("Type"),
                            options: [("", tr("All types"))] + types.map { ($0, SessionsL10n.typeName($0)) },
                            selection: $type)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Sort & filter")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Clear") {
                        type = ""
                        sort = .init()
                    }
                    .disabled(type.isEmpty && sort == .init())
                    .accessibilityIdentifier("filters.clear")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("filters.done")
                }
            }
        }
        .ceolDrawer([.medium])
    }
}
