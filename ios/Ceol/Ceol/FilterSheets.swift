// Sort and filter drawers for the Tunes and Sessions lists, opened from the search row's
// filter button.
//
// Tunes: the web's /my-tunes panel (spec 052 §B1), in its order: sort (a mode and a
// direction), type, instrument (when you play two or more), when you added it, and
// where it was played. The rules are CeolLogic.MyTunesList, held to the web's fixtures.
//
// Sessions: which sessions (the web's five), plus a sort and a country, which the web's
// page doesn't have yet (SessionsRules).

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
                        label: "Type",
                        options: [("", "All types")] + types.map { ($0, $0.capitalized) },
                        selection: $filters.type)
                    if instruments.count >= 2 {
                        ChoiceChips(
                            label: "Instrument",
                            options: [("", "All my instruments")] + instruments.map { ($0.name, $0.name.capitalized) },
                            selection: $filters.instrument)
                    }
                    addedSection
                    ChoiceChips(
                        label: "Played",
                        options: [("", "Anywhere"), ("member", "At my sessions"), ("attended", "When I was there")],
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
                        ForEach(MyTunesList.sortModes, id: \.id) { Text($0.label).tag($0.id) }
                    }
                } label: {
                    HStack {
                        Text(MyTunesList.sortModeLabel(sort.type)).font(.ceol(size: 16)).foregroundStyle(CeolTokens.textColor)
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
                .accessibilityLabel(sort.descending ? "Sorting downward" : "Sorting upward")
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
                        label: "Show", options: SessionsRules.Filter.allCases.map { ($0, $0.label) }, selection: $filter)
                    ChoiceChips(label: "Sort", options: SessionsRules.Sort.allCases.map { ($0, $0.label) }, selection: $sort)
                    if countries.count >= 2 {
                        ChoiceChips(label: "Country", options: [("", "Anywhere")] + countries.map { ($0, $0) }, selection: $country)
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
