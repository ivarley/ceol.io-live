// Sort and filter drawers for the Tunes and Sessions lists, opened from the search row's
// filter button.
//
// Tunes: the web's /my-tunes panel (spec 052 §B1), in its order: sort (a mode and a
// direction), type, instrument (when you play two or more), when you added it, and
// where it was played. The rules are CeolLogic.MyTunesList, held to the web's fixtures.
//
// Sessions: which sessions (the web's five), plus a sort and a country, which the web's
// page doesn't have yet (SessionsRules).
//
// A session's tabs: the web's /sessions/<path> panels (SessionPage). Tunes: type, sort,
// nights I attended, and my tunebook status; Logs: logged, attended or all; People:
// members, visitors or archived.

import CeolDesign
import CeolLogic
import SwiftUI

// MARK: - Tunes

struct TunesFilterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var filters: MyTunesList.Filters
    @Binding var sort: MyTunesList.Sort
    let types: [String]
    let instruments: [MyTunesList.Instrument]

    @State private var addedDate = Date()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    sortSection
                    ChoiceChips(
                        label: tr("Type"),
                        options: [("", tr("All types"))] + types.map { ($0, SessionsL10n.typeName($0)) },
                        selection: $filters.type)
                    if instruments.count >= 2 {
                        ChoiceChips(
                            label: tr("Instrument"),
                            options: [("", tr("All my instruments"))] + instruments.map { ($0.name, SessionsL10n.instrument($0.name.capitalized)) },
                            selection: $filters.instrument)
                    }
                    addedSection
                    ChoiceChips(
                        label: tr("Played"),
                        options: [("", tr("Anywhere")), ("member", tr("At my sessions")), ("attended", tr("When I was there"))],
                        selection: $filters.rel)
                }
                .padding(20)
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Sort & filter")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Clear") {
                        filters.type = ""
                        filters.instrument = ""
                        filters.rel = ""
                        filters.addedDate = ""
                        filters.addedBefore = false
                        sort = MyTunesList.Sort()
                    }
                    .disabled(filters.activeCount == 0 && sort == MyTunesList.Sort())
                    .accessibilityIdentifier("filters.clear")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("filters.done")
                }
            }
        }
        .ceolDrawer([.medium, .large])
    }

    private var sortSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("SORT").font(.ceol(size: 12, weight: .semibold)).tracking(0.8).foregroundStyle(CeolTokens.textMuted)
            HStack(spacing: 10) {
                Menu {
                    Picker("Sort", selection: $sort.type) {
                        ForEach(MyTunesList.sortModes, id: \.id) { Text(SessionsL10n.myTunesSortLabel($0.id)).tag($0.id) }
                    }
                } label: {
                    HStack {
                        Text(SessionsL10n.myTunesSortLabel(sort.type)).font(.ceol(size: 16)).foregroundStyle(CeolTokens.textColor)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down").font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    }
                    .padding(.horizontal, 14).frame(height: 44)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                }
                .accessibilityIdentifier("filters.sort")
                Button { sort.descending.toggle() } label: {
                    Image(systemName: sort.descending ? "arrow.down" : "arrow.up")
                        .font(.system(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                        .frame(width: 44, height: 44)
                        .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(sort.descending ? Text("Sorting downward") : Text("Sorting upward"))
            }
        }
    }

    /// One date and a direction, not a range, as on the web: "added since X" or
    /// "added before X".
    private var addedSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("ADDED").font(.ceol(size: 12, weight: .semibold)).tracking(0.8).foregroundStyle(CeolTokens.textMuted)
            HStack(spacing: 10) {
                Picker("When", selection: $filters.addedBefore) {
                    Text("Since").tag(false)
                    Text("Before").tag(true)
                }
                .pickerStyle(.segmented)
                .frame(width: 150)
                .disabled(filters.addedDate.isEmpty)
                if filters.addedDate.isEmpty {
                    Button("Any time — pick a day") { filters.addedDate = Self.day.string(from: addedDate) }
                        .font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
                } else {
                    DatePicker("", selection: $addedDate, displayedComponents: .date)
                        .labelsHidden()
                        .onChange(of: addedDate) { _, d in filters.addedDate = Self.day.string(from: d) }
                    Button { filters.addedDate = "" } label: {
                        Image(systemName: "xmark.circle.fill").foregroundStyle(CeolTokens.textMuted)
                    }
                    .accessibilityLabel("Any time")
                }
            }
        }
        .onAppear { if let d = Self.day.date(from: filters.addedDate) { addedDate = d } }
    }

    static let day: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        // The day as the picker shows it, in the phone's own time zone.
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

// MARK: - Sessions

struct SessionsFilterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var filter: SessionsRules.Filter
    @Binding var sort: SessionsRules.Sort
    @Binding var country: String
    let countries: [String]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    ChoiceChips(
                        label: tr("Show"), options: SessionsRules.Filter.allCases.map { ($0, SessionsL10n.label($0)) }, selection: $filter)
                    ChoiceChips(label: tr("Sort"), options: SessionsRules.Sort.allCases.map { ($0, SessionsL10n.label($0)) }, selection: $sort)
                    if countries.count >= 2 {
                        ChoiceChips(label: tr("Country"), options: [("", tr("Anywhere"))] + countries.map { ($0, $0) }, selection: $country)
                    }
                }
                .padding(20)
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Sort & filter")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Clear") {
                        filter = .mine
                        sort = .name
                        country = ""
                    }
                    .accessibilityIdentifier("filters.clear")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("filters.done")
                }
            }
        }
        .ceolDrawer([.medium, .large])
    }
}

// MARK: - A session's tabs

struct SessionTunesFilterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var filters: SessionPage.Filters
    @Binding var sort: SessionPage.Sort
    let types: [String]
    let signedIn: Bool
    /// Your instruments, when you play two or more (the status can be one instrument's).
    let instruments: [String]
    /// Your tunebook failed to load, so the status filter is off.
    var tunebookFailed = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    sortSection
                    ChoiceChips(
                        label: tr("Type"),
                        options: [("", tr("All types"))] + types.map { ($0, SessionsL10n.typeName($0)) },
                        selection: $filters.type)
                    if signedIn {
                        ChoiceChips(
                            label: tr("Played"),
                            options: [(false, tr("Any night")), (true, tr("Nights I attended"))],
                            selection: $filters.attended)
                        VStack(alignment: .leading, spacing: 8) {
                            ChoiceChips(
                                label: tr("My tunebook"),
                                options: SessionPage.MyStatus.allCases.map { ($0, SessionsL10n.label($0)) },
                                selection: $filters.myStatus)
                            if tunebookFailed {
                                Text("Your tunebook didn't load, so this is off. Try again.")
                                    .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                            }
                        }
                        if filters.myStatus != .off && instruments.count >= 2 {
                            ChoiceChips(
                                label: tr("Instrument"),
                                options: [("all", tr("All instruments"))] + instruments.map { ($0, SessionsL10n.instrument($0.capitalized)) },
                                selection: $filters.myStatusInstrument)
                        }
                    }
                }
                .padding(20)
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Sort & filter")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    // As on the web: the search stays.
                    Button("Clear") {
                        filters.type = ""
                        filters.attended = false
                        filters.myStatus = .off
                        filters.myStatusInstrument = "all"
                        sort = .init()
                    }
                    .disabled(!filters.active && sort == .init())
                    .accessibilityIdentifier("filters.clear")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("filters.done")
                }
            }
        }
        .ceolDrawer([.medium, .large])
    }

    /// A droplist and a direction, as the Tunes page's drawer has them.
    private var sortSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("SORT").font(.ceol(size: 12, weight: .semibold)).tracking(0.8).foregroundStyle(CeolTokens.textMuted)
            HStack(spacing: 10) {
                Menu {
                    Picker("Sort", selection: Binding(get: { sort.mode }, set: { mode in
                        // Name starts A to Z; the counts start with the most.
                        if mode != sort.mode { sort = .init(mode: mode, descending: mode.defaultDescending) }
                    })) {
                        ForEach(SessionPage.SortMode.allCases, id: \.self) { Text(SessionsL10n.label($0)).tag($0) }
                    }
                } label: {
                    HStack {
                        Text(SessionsL10n.label(sort.mode)).font(.ceol(size: 16)).foregroundStyle(CeolTokens.textColor)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down").font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    }
                    .padding(.horizontal, 14).frame(height: 44)
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                }
                .accessibilityIdentifier("filters.sort")
                Button { sort.descending.toggle() } label: {
                    Image(systemName: sort.descending ? "arrow.down" : "arrow.up")
                        .font(.system(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                        .frame(width: 44, height: 44)
                        .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(sort.descending ? Text("Sorting downward") : Text("Sorting upward"))
                .accessibilityIdentifier("filters.direction")
            }
        }
    }
}

/// One choice for a tab: which nights, or which people.
struct SessionTabFilterSheet<ID: Hashable>: View {
    @Environment(\.dismiss) private var dismiss
    let label: String
    let options: [(id: ID, label: String)]
    @Binding var selection: ID
    let initial: ID
    /// The choices on one line, as a segmented control.
    var oneLine = false

    var body: some View {
        NavigationStack {
            ScrollView {
                Group {
                    if oneLine {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(label.uppercased()).font(.ceol(size: 12, weight: .semibold)).tracking(0.8)
                                .foregroundStyle(CeolTokens.textMuted)
                            Picker(label, selection: $selection) {
                                ForEach(options, id: \.id) { Text($0.label).tag($0.id) }
                            }
                            .pickerStyle(.segmented)
                        }
                    } else {
                        ChoiceChips(label: label, options: options, selection: $selection)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Filter")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Clear") { selection = initial }
                        .disabled(selection == initial)
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
