// Finding your way around a night (spec 052 Phase 7), as the web logger's filter bar,
// its ★ my-list highlight and its bulk "My list" (frontend/src/App.svelte), in the
// app's own shapes:
//
//   - The night's top bar is one "⋯" menu (and Done while editing): the things you do
//     now and then. Logging starts from the capsule under the last set, where a live
//     log grows; editing, the capsule hands the night to the phone's ear instead.
//   - The search row sits under the pinned header, scrolled just out of sight until
//     the log is pulled down, with the filter button beside it (NightFilterSheet: your
//     tunebook status, and the instrument). A pill row under the header says what the
//     log is narrowed to and how much of it that is.
//   - Selecting, "By status" picks tunes by your status and "My list" (ListStatusSheet)
//     sets one on the picked tunes, through the tunebook's queue, so it works with no
//     signal (TunebookOps).
//   - Recordings (NightRecordingsSheet): the night's uploads and how far the segmenter
//     has got with each, for whoever may manage them; the work itself is on the web.
//
// i18n-converted (spec 057).

import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

/// The action under the last set: "Edit log" watching, "Listen and log" editing.
struct NightCapsule<Content: View>: View {
    let id: String
    let action: () -> Void
    @ViewBuilder let content: () -> Content

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) { content() }
                .font(.ceol(size: 16, weight: .semibold))
                .foregroundStyle(CeolTokens.primary)
                .padding(.horizontal, 18).frame(height: 44)
                .overlay(Capsule().strokeBorder(CeolTokens.primary.opacity(0.6), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }
}

/// Your status beside a tune in the log: the Tunes tab's glyph, or a hollow mark for a
/// tune not on your list; nothing for one logged as text (it can't be on a list).
struct NightStatusMark: View {
    let status: String?

    var body: some View {
        if let status, status != SessionPage.MyStatus.notOnList.rawValue {
            StatusGlyph(status: status)
        } else if status != nil {
            Text("○").font(.system(size: 13, weight: .bold)).foregroundStyle(CeolTokens.textMuted)
                .frame(width: 20)
                .accessibilityLabel("Not on my list")
        } else {
            Color.clear.frame(width: 20, height: 1).accessibilityHidden(true)
        }
    }
}

/// What the log is narrowed to: the search, the tunebook status, and "3 of 12 sets".
struct NightPills: View {
    let search: String
    let status: SessionPage.MyStatus
    let instrument: String
    /// You play two or more instruments, so the instrument is worth saying.
    let scoped: Bool
    let tunebookLoaded: Bool
    let tunebookFailed: Bool
    let shown: Int
    let total: Int
    let onClearSearch: () -> Void
    let onClearStatus: () -> Void

    var body: some View {
        let q = search.trimmingCharacters(in: .whitespacesAndNewlines)
        HStack(spacing: 8) {
            if !q.isEmpty { pill("“\(q)”", id: "night.pill.search", action: onClearSearch) }
            if status != .off { pill(statusText, id: "night.pill.status", action: onClearStatus) }
            Spacer(minLength: 4)
            if shown < total || !q.isEmpty || status != .off {
                Text(SessionsL10n.setsShown(shown, total))
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    .accessibilityIdentifier("night.shown")
            }
        }
        .padding(.horizontal, 20).padding(.vertical, 8)
        .background(CeolTokens.headerBg.opacity(0.3))
    }

    private var statusText: String {
        if tunebookFailed { return tr("Your tunebook didn't load") }
        if !tunebookLoaded { return tr("Loading your tunebook…") }
        let word = status == .all ? tr("My tunebook") : SessionsL10n.label(status)
        return scoped && instrument != "all" ? "\(word) · \(SessionsL10n.instrument(instrument.capitalized))" : word
    }

    private func pill(_ text: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Text(text).font(.ceol(size: 14, weight: .medium)).lineLimit(1)
                Image(systemName: "xmark").font(.system(size: 10, weight: .bold))
            }
            .foregroundStyle(CeolTokens.primary)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .background(CeolTokens.primary.opacity(0.14), in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(tr("\(text), clear"))
        .accessibilityIdentifier(id)
    }
}

/// The night's filter: your tunebook status (as the session Tunes tab offers it) and,
/// when you play two or more instruments, which one.
struct NightFilterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var status: SessionPage.MyStatus
    @Binding var instrument: String
    let instruments: [String]
    var tunebookFailed = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    VStack(alignment: .leading, spacing: 8) {
                        ChoiceChips(
                            label: tr("My tunebook"),
                            options: SessionPage.MyStatus.allCases.map { ($0, SessionsL10n.label($0)) },
                            selection: $status)
                        if tunebookFailed {
                            Text("Your tunebook didn't load, so this is off. Try again.")
                                .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                    if status != .off && instruments.count >= 2 {
                        ChoiceChips(
                            label: tr("Instrument"),
                            options: [("all", tr("All instruments"))] + instruments.map { ($0, SessionsL10n.instrument($0.capitalized)) },
                            selection: $instrument)
                    }
                }
                .padding(20)
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Filter")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Clear") {
                        status = .off
                        instrument = "all"
                    }
                    .disabled(status == .off && instrument == "all")
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

/// The bulk "My list": the status to put on the picked tunes, and on which instrument.
struct ListStatusSheet: View {
    @Environment(\.dismiss) private var dismiss
    let count: Int
    let instruments: [String]
    let loaded: Bool
    let failed: Bool
    let onApply: (String, String) -> Void
    @State private var status = "learned"
    @State private var scope = "all"

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    ChoiceChips(
                        label: tr("Status"),
                        options: [("want to learn", tr("Want to learn")), ("learning", tr("Learning")), ("learned", tr("Learned"))],
                        selection: $status)
                    if instruments.count >= 2 {
                        ChoiceChips(
                            label: tr("Instrument"),
                            options: [("all", tr("All instruments"))] + instruments.map { ($0, SessionsL10n.instrument($0.capitalized)) },
                            selection: $scope)
                    }
                    if failed {
                        Text("Your tunebook didn't load. Check your connection and try again.")
                            .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                    } else if !loaded {
                        HStack(spacing: 8) {
                            ProgressView().controlSize(.small)
                            Text("Loading your tunebook…").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                    Button {
                        onApply(status, scope)
                        dismiss()
                    } label: {
                        Text(count == 1 ? tr("Apply to 1 tune") : tr("Apply to \(count) tunes"))
                            .font(.ceol(size: 16, weight: .semibold))
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity).frame(height: 46)
                            .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                    .disabled(!loaded || count == 0)
                    .opacity(loaded && count > 0 ? 1 : 0.5)
                    .accessibilityIdentifier("mylist.apply")
                }
                .padding(20)
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("My list")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
        }
        .ceolDrawer([.medium, .large])
    }
}

/// The night's recordings and where the segmenter has got with each, as the web's
/// Recordings dialog lists them; the segmenter itself opens on the web, signed in.
struct NightRecordingsSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let instanceID: Int
    @State private var recordings: [JSONValue]?
    @State private var tuneCount = 0
    @State private var failure: String?
    @State private var page: WebPage?
    @State private var opening: Int?

    var body: some View {
        NavigationStack {
            Group {
                if let recordings {
                    if recordings.isEmpty {
                        ContentUnavailableView {
                            Label("No recordings yet", systemImage: "waveform")
                        } description: {
                            Text("Record a night from here with Listen, or upload one on the web.")
                        }
                    } else {
                        List {
                            ForEach(Array(recordings.enumerated()), id: \.offset) { _, r in row(r) }
                            Section {
                                Text("Uploading, retrying and deleting a recording are done on the web.")
                                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                            }
                        }
                        .listStyle(.insetGrouped)
                        .scrollContentBackground(.hidden)
                    }
                } else if let failure {
                    ContentUnavailableView {
                        Label("Couldn't load this", systemImage: "wifi.exclamationmark")
                    } description: {
                        Text(failure)
                    } actions: {
                        Button("Retry") { Task { await load() } }.buttonStyle(.bordered)
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .background(CeolTokens.drawerBg)
            .navigationTitle("Recordings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.accessibilityIdentifier("recordings.done") }
            }
            .sheet(item: $page) { SafariView(url: $0.url).ignoresSafeArea() }
        }
        .ceolDrawer([.large])
        .task { await load() }
    }

    @ViewBuilder private func row(_ r: JSONValue) -> some View {
        let id = r["recording_id"]?.intValue ?? 0
        let status = r["status"]?.stringValue ?? ""
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(r["label"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 } ?? tr("Untitled recording"))
                    .font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                Spacer()
                if let ms = r["duration_ms"]?.intValue {
                    Text(Self.clock(ms)).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                }
            }
            if let started = r["started_at"]?.stringValue, let date = ISO8601DateFormatter().date(from: started) {
                Text(date.formatted(date: .abbreviated, time: .shortened)).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
            }
            Text(statusLine(r, status)).font(.ceol(size: 14))
                .foregroundStyle(status == "failed" ? CeolTokens.errorText : CeolTokens.textMuted)
            if status == "ready" {
                Button {
                    Task { await open(id) }
                } label: {
                    HStack(spacing: 6) {
                        if opening == id { ProgressView().controlSize(.small) }
                        Text("Open in the segmenter")
                    }
                    .font(.ceol(size: 15, weight: .semibold)).foregroundStyle(CeolTokens.primary)
                }
                .buttonStyle(.plain)
                .disabled(opening != nil)
                .padding(.top, 2)
            }
        }
        .padding(.vertical, 4)
        .listRowBackground(CeolTokens.headerBg.opacity(0.4))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("recording.row")
    }

    private func statusLine(_ r: JSONValue, _ status: String) -> String {
        switch status {
        case "ready":
            let placed = r["segment_count"]?.intValue ?? 0
            var line = tr("\(placed) of \(tuneCount) tunes placed")
            if r["segmenting_complete"]?.boolValue == true { line += " — " + tr("rest isn't in this audio") }
            return line
        case "failed":
            return tr("Processing failed — \(r["status_detail"]?.stringValue ?? tr("no detail recorded"))")
        default:
            return r["status_detail"]?.stringValue ?? tr("Processing…")
        }
    }

    /// "1:02:33" or "4:07".
    static func clock(_ ms: Int) -> String {
        let s = ms / 1000
        return s >= 3600
            ? String(format: "%d:%02d:%02d", s / 3600, s / 60 % 60, s % 60)
            : String(format: "%d:%02d", s / 60, s % 60)
    }

    private func load() async {
        failure = nil
        do {
            let v = try await app.getJSON("/api/session-instances/\(instanceID)/recordings")
            recordings = v["recordings"]?.arrayValue ?? []
            tuneCount = v["tune_count"]?.intValue ?? 0
        } catch {
            failure = loadFailureMessage(error)
        }
    }

    /// The segmenter, signed in, through the one-time handoff link (as Admin opens).
    private func open(_ id: Int) async {
        opening = id
        defer { opening = nil }
        do {
            page = WebPage(url: try await app.auth.webSession(next: "/admin/recordings/\(id)/segment"))
        } catch let f as AuthFailure {
            failure = f.message
        } catch {
            failure = tr("Couldn't reach Ceol. Check your connection and try again.")
        }
    }
}
