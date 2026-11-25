// Export (the web's Me → Export my data): the chooser, the banner and bar a screen
// wears in export mode, and the round trip that fetches the file and hands it to the
// share sheet.
//
// As on the web, the screens do the choosing: the Tunes tab and a session's page keep
// their usual search and filters, and the bar at the bottom offers the rows on screen
// as JSON, CSV or PDF. The server resolves names, keys, settings and notation for the
// ids it is sent (export_routes.py). A PDF needs every tune's notation image cached, so
// the bar first asks the /check twin which settings still lack one, warms them through
// the setting-image endpoint with "Preparing notation 33 of 127" on the button, then
// asks for the file. The file is written under the temporary folder and offered to the
// share sheet (Save to Files, AirDrop, Mail), which is the phone's download.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import OpenAPIRuntime
import SwiftUI
import UIKit

// MARK: - Words

enum ExportWords {
    static func format(_ f: ExportRules.Format) -> String {
        switch f {
        case .json: tr("JSON")
        case .csv: tr("CSV")
        case .pdf: tr("PDF")
        }
    }

    /// One filter line in the file's header, in the app's language.
    static func line(_ l: ExportRules.Line) -> String {
        let dir = l.descending == true ? tr("descending") : tr("ascending")
        switch l.key {
        case .status: return tr("Status: \(TunesWords.status(l.value))")
        case .type: return tr("Type: \(TunesWords.type(l.value.capitalized))")
        case .instrument: return tr("Instrument: \(TunesWords.instrument(l.value))")
        case .tag: return tr("Tag: \(l.value)")
        case .played: return tr("Played: \(played(l.value))")
        case .addedBefore: return tr("Added before \(l.value)")
        case .addedAfter: return tr("Added after \(l.value)")
        case .search: return tr("Search: \(l.value)")
        case .sort: return tr("Sort: \(sortLabel(l.value)), \(dir)")
        case .thenBy: return tr("Then by: \(sortLabel(l.value)), \(dir)")
        case .myTunebook: return tr("My Tunebook: \(myTunebook(l.value))")
        case .nightsWith: return tr("Nights with \(l.value)")
        case .nights: return tr("Nights: \(nights(l.value))")
        }
    }

    private static func played(_ v: String) -> String {
        switch v {
        case "member": tr("At my sessions")
        case "attended": tr("When I was there")
        default: v
        }
    }

    private static func sortLabel(_ v: String) -> String {
        if let mode = SessionPage.SortMode(rawValue: v) { return SessionsL10n.label(mode) }
        return TunesWords.sortMode(v)
    }

    private static func myTunebook(_ v: String) -> String {
        let parts = v.split(separator: "/", maxSplits: 1).map(String.init)
        let status = SessionPage.MyStatus(rawValue: parts[0]).map(SessionsL10n.label) ?? parts[0]
        if parts.count == 2 { return "\(status) · \(SessionsL10n.instrument(parts[1].capitalized))" }
        return status
    }

    private static func nights(_ v: String) -> String {
        SessionPage.LogView(rawValue: v).map(SessionsL10n.label) ?? v
    }

    /// What the format note under the picker says, per kind and format.
    static func note(kind: ExportRules.Kind, format: ExportRules.Format) -> String {
        switch (kind, format) {
        case (.myTunes, .pdf): tr("Title and notation for each tune, in the setting you play")
        case (.myTunes, _): tr("Status, tags, notes and the setting you play, one row per tune")
        case (.sessionTunes, .pdf): tr("Title and notation for each tune, in the setting this session plays")
        case (.sessionTunes, _): tr("One row per tune, with the name and setting this session uses")
        case (.sessionLogs, .pdf): tr("Nights as headings, sets under them, each tune with its notation")
        case (.sessionLogs, _): tr("One row per tune: night, set, position, name used that night, key, setting")
        }
    }

    static func downloadLabel(kind: ExportRules.Kind, count: Int) -> String {
        switch kind {
        case .myTunes, .sessionTunes: count == 1 ? tr("Download 1 tune") : tr("Download \(count) tunes")
        case .sessionLogs: count == 1 ? tr("Download 1 night") : tr("Download \(count) nights")
        }
    }
}

// MARK: - The banner and the bar

/// The strip at the top of a screen in export mode: what is being exported and the
/// way out. The accent wash the active tab wears, as the web's banner.
struct ExportBanner: View {
    let label: String
    let hint: String
    let onLeave: () -> Void

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.ceol(size: 14, weight: .semibold)).foregroundStyle(CeolTokens.primary)
                Text(hint).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textColor)
            }
            Spacer(minLength: 8)
            Button(tr("Leave"), action: onLeave)
                .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textColor)
                .padding(.horizontal, 9).padding(.vertical, 5)
                .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                .buttonStyle(.plain)
                .accessibilityIdentifier("export.leave")
        }
        .padding(.horizontal, 14).padding(.vertical, 9)
        .background(CeolTokens.primary.opacity(0.16))
        .overlay(alignment: .bottom) { Rectangle().fill(CeolTokens.primaryFill).frame(height: 1) }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("export.banner")
    }
}

/// The bottom of a screen in export mode: the format, what the file holds, Download
/// with the live count, Done. Sits where the tab bar was (ContentView hides it).
struct ExportBar: View {
    @Environment(AppModel.self) private var model
    /// What this bar exports right now; nil when the screen has nothing to (People).
    let kind: ExportRules.Kind?
    let ids: [Int]
    let lines: [ExportRules.Line]
    let onDone: () -> Void

    @State private var runner = ExportRunner()
    @State private var shareURL: URL?
    @State private var failure: String?

    var body: some View {
        @Bindable var model = model
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Picker("Format", selection: $model.exportFormat) {
                    ForEach(ExportRules.Format.allCases, id: \.self) { Text(ExportWords.format($0)).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 200)
                .accessibilityIdentifier("export.format")
                if let kind {
                    Text(ExportWords.note(kind: kind, format: model.exportFormat))
                        .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
                        .lineLimit(2).minimumScaleFactor(0.85)
                }
            }
            HStack(spacing: 8) {
                Button {
                    Task { await download() }
                } label: {
                    HStack(spacing: 8) {
                        if runner.busy { ProgressView().tint(.white) }
                        Text(runner.progress ?? kind.map { ExportWords.downloadLabel(kind: $0, count: ids.count) } ?? tr("Download"))
                            .lineLimit(1).minimumScaleFactor(0.8)
                    }
                    .font(.ceol(size: 16, weight: .semibold)).foregroundStyle(.white)
                    .frame(maxWidth: .infinity).frame(height: 44)
                    .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
                }
                .buttonStyle(.plain)
                .disabled(kind == nil || ids.isEmpty || runner.busy)
                .opacity(kind == nil || ids.isEmpty ? 0.45 : 1)
                .accessibilityIdentifier("export.download")
                Button(tr("Done"), action: onDone)
                    .font(.ceol(size: 15, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                    .padding(.horizontal, 14).frame(height: 44)
                    .background(CeolTokens.inputBg, in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("export.done")
            }
            if kind == nil {
                Text("Nothing to export on this tab. Switch to Tunes or Logs.")
                    .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
            } else if ids.isEmpty {
                Text(kind.map { if case .sessionLogs = $0 { true } else { false } } == true
                    ? tr("No nights match these filters.") : tr("No tunes match these filters."))
                    .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
            }
        }
        .padding(.horizontal, 16).padding(.top, 10).padding(.bottom, 12)
        .background(CeolTokens.headerBg)
        .overlay(alignment: .top) { Rectangle().fill(CeolTokens.borderColor).frame(height: 1) }
        .sheet(item: $shareURL) { url in
            ActivityView(items: [url])
                .presentationDetents([.medium, .large])
                .ignoresSafeArea()
        }
        .alert("Couldn't export", isPresented: Binding(get: { failure != nil }, set: { if !$0 { failure = nil } })) {
            Button("OK") {}
        } message: {
            Text(failure ?? "")
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("export.bar")
    }

    private func download() async {
        guard let kind, !ids.isEmpty else { return }
        do {
            shareURL = try await runner.run(
                model: model, kind: kind, ids: ids, format: model.exportFormat,
                filters: lines.map(ExportWords.line))
        } catch let f as ExportFailure {
            failure = f.message
        } catch {
            failure = tr("Couldn't export. Check your connection and try again.")
        }
    }
}

extension URL: @retroactive Identifiable {
    public var id: String { absoluteString }
}

/// The share sheet, with the file: Save to Files, AirDrop, Mail and the rest.
struct ActivityView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

// MARK: - The round trip

struct ExportFailure: Error {
    let message: String
}

/// Check, warm, download: one export from tap to file. Observable so the button can
/// show the warm-up's progress.
@Observable
@MainActor
final class ExportRunner {
    private(set) var busy = false
    /// "Preparing notation 33 of 127" while images are drawn; nil otherwise.
    private(set) var progress: String?

    func run(model: AppModel, kind: ExportRules.Kind, ids: [Int], format: ExportRules.Format, filters: [String]) async throws -> URL {
        busy = true
        defer {
            busy = false
            progress = nil
        }
        guard ids.count <= ExportRules.maxIDs else {
            throw ExportFailure(message: tr("That is too much for one file (\(ExportRules.maxIDs) at most). Narrow the filters."))
        }
        if format == .pdf {
            progress = tr("Preparing…")
            let missing = try await check(model: model, kind: kind, ids: ids, filters: filters)
            try await warm(model: model, settingIDs: missing)
            progress = tr("Preparing…")
        }
        return try await fetchFile(model: model, kind: kind, ids: ids, format: format, filters: filters)
    }

    /// The settings whose full notation image the server has not drawn yet.
    private func check(model: AppModel, kind: ExportRules.Kind, ids: [Int], filters: [String]) async throws -> [Int] {
        let client = model.auth.client
        do {
            switch kind {
            case .myTunes:
                return try await client.checkMyTunesExport(body: .json(.init(format: .pdf, tuneIds: ids, filters: filters)))
                    .ok.body.json.missingSettingIds
            case .sessionTunes(let path):
                return try await client.checkSessionTunesExport(
                    path: .init(sessionPath: path), body: .json(.init(format: .pdf, tuneIds: ids, filters: filters))
                ).ok.body.json.missingSettingIds
            case .sessionLogs(let path):
                return try await client.checkSessionLogsExport(
                    path: .init(sessionPath: path), body: .json(.init(format: .pdf, instanceIds: ids, filters: filters))
                ).ok.body.json.missingSettingIds
            }
        } catch let error as ClientError {
            throw ExportFailure(message: Self.envelopeMessage(error) ?? tr("Couldn't export. Check your connection and try again."))
        } catch {
            if let message = Self.undocumentedMessage(error) { throw ExportFailure(message: message) }
            throw ExportFailure(message: tr("Couldn't export. Check your connection and try again."))
        }
    }

    /// Draw the missing images, two at a time, counting them on the button. A failed
    /// image is left to the file request (which draws a few itself, or says so).
    private func warm(model: AppModel, settingIDs: [Int]) async throws {
        guard !settingIDs.isEmpty else { return }
        let client = model.auth.client
        let total = settingIDs.count
        var done = 0
        progress = tr("Preparing notation \(0) of \(total)")
        try await withThrowingTaskGroup(of: Void.self) { group in
            var iterator = settingIDs.makeIterator()
            func add() {
                guard let id = iterator.next() else { return }
                group.addTask {
                    _ = try? await client.getSettingImage(path: .init(settingId: id), query: .init(kind: .full))
                }
            }
            add()
            add()
            while try await group.next() != nil {
                done += 1
                progress = tr("Preparing notation \(done) of \(total)")
                try Task.checkCancellation()
                add()
            }
        }
    }

    /// The file itself, through URLSession (the generated client reads JSON; this is
    /// bytes with a name), written under the temporary folder.
    private func fetchFile(model: AppModel, kind: ExportRules.Kind, ids: [Int], format: ExportRules.Format, filters: [String]) async throws -> URL {
        if model.simulatedOffline { throw URLError(.notConnectedToInternet) }
        let path: String
        var body: [String: Any] = ["format": format.rawValue, "filters": filters]
        switch kind {
        case .myTunes:
            path = "/api/export/my-tunes"
            body["tune_ids"] = ids
        case .sessionTunes(let sessionPath):
            path = "/api/export/sessions/\(sessionPath)/tunes"
            body["tune_ids"] = ids
        case .sessionLogs(let sessionPath):
            path = "/api/export/sessions/\(sessionPath)/logs"
            body["instance_ids"] = ids
        }
        var request = model.authorized(URLRequest(url: model.webURL(path)))
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard http.statusCode == 200 else {
            if http.statusCode == 401 { model.signInExpired() }
            let message = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["message"] as? String
            throw ExportFailure(message: message ?? tr("Couldn't export. Check your connection and try again."))
        }
        let served = ExportRules.filename(fromContentDisposition: http.value(forHTTPHeaderField: "Content-Disposition"))
        let day = ISO8601DateFormatter.day.string(from: Date())
        let name = ExportRules.localFilename(served, kind: kind, format: format, day: day)
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("ceol-export", isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let url = folder.appendingPathComponent(name)
        try data.write(to: url, options: .atomic)
        return url
    }

    /// The server's own sentence from an error envelope the generated client decoded.
    private static func envelopeMessage(_ error: ClientError) -> String? {
        undocumentedMessage(error.underlyingError)
    }

    private static func undocumentedMessage(_ error: any Error) -> String? {
        // The generated client surfaces a documented `default` response as a thrown
        // ClientError wrapping the decoded body; the message is what the user should see.
        let text = String(describing: error)
        guard let range = text.range(of: "message: \"") else { return nil }
        let rest = text[range.upperBound...]
        return rest.split(separator: "\"", maxSplits: 1).first.map(String.init)
    }
}

extension ISO8601DateFormatter {
    /// "2026-11-24", for a file name.
    static let day: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate]
        return f
    }()
}

// MARK: - The chooser

/// Me → Export my data: the web's /export. Pick My Tunes, a session's tunes or a
/// session's logs; the screen itself opens in export mode.
struct ExportChooserView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    /// The sessions to offer, observable so the pushed picker sees them arrive (a
    /// pushed destination keeps the state it was built with).
    @State private var options = ExportOptionsStore()
    @State private var picking: ExportRules.Kind?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Pick what to export. The next page has the usual filters; set them, then choose a format.")
                        .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                    choice(title: tr("My Tunes"), detail: tr("Your tune list, with status, tags, notes and the setting you play."), id: "export.myTunes") {
                        start(.myTunes)
                    }
                    choice(title: tr("Session Tunes"), detail: tr("Everything a session plays, with its names and settings."), id: "export.sessionTunes") {
                        picking = .sessionTunes(path: "")
                    }
                    choice(title: tr("Session Logs"), detail: tr("Nights at a session, set by set."), id: "export.sessionLogs") {
                        picking = .sessionLogs(path: "")
                    }
                    Text("The two session pickers list your sessions first, then any session on Ceol.")
                        .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
                }
                .padding(20)
            }
            .background(CeolTokens.bgColor)
            .navigationTitle(tr("Export"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
            // The picker is pushed, not a second sheet: a pick then closes one sheet (this
            // one), which is the only dismissal SwiftUI does reliably.
            .navigationDestination(item: $picking) { kind in
                ExportSessionPicker(kind: kind, options: options) { path in
                    switch kind {
                    case .sessionTunes: start(.sessionTunes(path: path))
                    case .sessionLogs: start(.sessionLogs(path: path))
                    case .myTunes: break
                    }
                }
            }
            .task { await loadOptions() }
        }
    }

    private func choice(title: String, detail: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(title).font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                    Spacer()
                    Image(systemName: "chevron.right").foregroundStyle(CeolTokens.primary)
                }
                Text(detail).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                    .multilineTextAlignment(.leading)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }

    /// Open the screen in export mode: the Tunes tab, or the session's page in the
    /// Sessions tab (where sessions live), with its own tab chosen.
    private func start(_ kind: ExportRules.Kind) {
        dismiss()
        switch kind {
        case .myTunes:
            model.exporting = .myTunes
            model.tab = .tunes
        case .sessionTunes(let path), .sessionLogs(let path):
            let name = options.state?.value?.all.first { $0.path == path }?.name
                ?? options.state?.value?.mine.first { $0.path == path }?.name ?? path
            model.exporting = .session(path: path)
            model.exportTab = (kind == .sessionLogs(path: path)) ? "logs" : "tunes"
            model.tab = .sessions
            model.sessionsPath = [.session(path: path, name: name)]
        }
    }

    private func loadOptions() async {
        options.state = .loading
        do {
            let r = try await model.auth.client.getExportOptions().ok.body.json
            options.state = .loaded(ExportOptions(
                mine: r.mySessions.map { .init(path: $0.path, name: $0.name, place: $0.place) },
                all: r.allSessions.map { .init(path: $0.path, name: $0.name, place: $0.place) }))
        } catch {
            options.state = .failed(loadFailureMessage(error))
        }
    }
}

@Observable
final class ExportOptionsStore {
    var state: LoadState<ExportOptions>?
}

struct ExportOptions {
    struct Session: Hashable {
        let path: String
        let name: String
        let place: String?
    }
    let mine: [Session]
    let all: [Session]
}

/// Which session: yours first, then every session on Ceol, searchable.
struct ExportSessionPicker: View {
    let kind: ExportRules.Kind
    let options: ExportOptionsStore
    let onPick: (String) -> Void
    @State private var query = ""
    @FocusState private var searching: Bool

    var body: some View {
        Group {
            switch options.state {
            case .loaded(let o): list(o)
            case .failed(let message): ContentUnavailableView(message, systemImage: "wifi.exclamationmark")
            default: ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(CeolTokens.bgColor)
        .navigationTitle(kind.isLogs ? tr("Which session’s logs?") : tr("Which session’s tunes?"))
        .navigationBarTitleDisplayMode(.inline)
    }

    private func matches(_ s: ExportOptions.Session) -> Bool {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return q.isEmpty || s.name.lowercased().contains(q) || (s.place ?? "").lowercased().contains(q) || s.path.contains(q)
    }

    @ViewBuilder private func list(_ o: ExportOptions) -> some View {
        let mine = o.mine.filter(matches)
        let minePaths = Set(o.mine.map(\.path))
        let rest = o.all.filter { !minePaths.contains($0.path) && matches($0) }
        List {
            SearchRow(text: $query, prompt: tr("Find a session"), fieldID: "export.sessionSearch", focused: $searching)
                .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 6, trailing: 16))
                .listRowBackground(CeolTokens.bgColor).listRowSeparator(.hidden)
            if !mine.isEmpty {
                section(tr("Your sessions"), mine)
            }
            if !rest.isEmpty {
                section(tr("All sessions"), rest)
            }
            if mine.isEmpty && rest.isEmpty {
                Text("No session matches “\(query)”.").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    .listRowBackground(CeolTokens.bgColor).listRowSeparator(.hidden)
            }
        }
        .ceolPlainList()
    }

    @ViewBuilder private func section(_ title: String, _ sessions: [ExportOptions.Session]) -> some View {
        Text(title).font(.ceol(size: 13, weight: .semibold)).textCase(.uppercase).tracking(0.8)
            .foregroundStyle(CeolTokens.textMuted)
            .listRowInsets(EdgeInsets(top: 14, leading: 16, bottom: 4, trailing: 16))
            .listRowBackground(CeolTokens.bgColor).listRowSeparator(.hidden)
        ForEach(sessions, id: \.path) { s in
            Button { onPick(s.path) } label: {
                HStack {
                    Text(s.name).font(.ceol(size: 16)).foregroundStyle(CeolTokens.textColor)
                    Spacer()
                    if let place = s.place { Text(place).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted) }
                }
                .frame(maxWidth: .infinity)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .ceolRow()
            .accessibilityIdentifier("export.session")
        }
    }
}

extension ExportRules.Kind: @retroactive Identifiable {
    var isLogs: Bool { if case .sessionLogs = self { true } else { false } }
    public var id: String {
        switch self {
        case .myTunes: "my-tunes"
        case .sessionTunes(let path): "tunes:\(path)"
        case .sessionLogs(let path): "logs:\(path)"
        }
    }
}
