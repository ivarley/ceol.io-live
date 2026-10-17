// The Listen tab (spec 059): the meter's home. Before anything is heard, the start
// screen (ListenStartView); then the meter (ListenMeterView), in Log mode when a
// night's tunes are being logged, else just saying what is playing, with Recent Tunes
// Heard under it. The same screen is presented over a tune search (the "Listen To
// What's Playing Now" button under its empty field), with the search's own pick as
// what a sure tune can be added to or logged to.
//
// i18n-converted (spec 057). Tune names, and a night's title, are data.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI
import UIKit

/// Where the listen screen was opened from: what it offers a tune it is sure of
/// (nothing more than your tunebook, from the tab or Home).
struct ListenContext {
    /// A night's search: no "Log This Tune" while the meter logs to that very night.
    var instanceID: Int? = nil
    var action: ListenAction? = nil
}

/// "Add To This Session's Tune List", "Log This Tune": the search's pick, as a button
/// under the sure tune. `run` takes {tune_id, name, tune_type} and says what went wrong.
struct ListenAction {
    let label: String
    /// The button once it has been done ("Added", "Logged").
    let done: String
    let icon: String
    let run: ([String: JSONValue]) async -> String?
}

/// The listen screen slid up over the app (AppModel.presentedListen).
struct ListenPresentation: Identifiable {
    let id = UUID()
}

/// The listen screen over something else: a search sheet, or the tab view (a night's
/// Listen button, Home's, the mini bar). A chevron closes it.
struct ListenCover: View {
    var context = ListenContext()
    @State private var showingRecent = false

    var body: some View {
        ListenScreen(context: context, presented: true, showingRecent: $showingRecent)
    }
}

/// The ear, as the tab bar draws it: the one glyph for listening everywhere.
struct EarGlyph: View {
    var size: CGFloat = 20

    var body: some View {
        Image("TabListen").renderingMode(.template).resizable().scaledToFit().frame(width: size, height: size)
    }
}

/// The tab's root.
struct ListenTab: View {
    @Environment(AppModel.self) private var app
    @State private var showingRecent = false

    var body: some View {
        ListenScreen(showingRecent: $showingRecent)
            .onChange(of: app.rootRequests[.listen]) { _, _ in showingRecent = false }
    }
}

/// The listen screen: the start screen or the meter, the Stop in its toolbar, and
/// Recent Tunes Heard. `presented`: over a search sheet (a chevron closes it), else
/// the tab's root (the wordmark).
struct ListenScreen: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var context = ListenContext()
    var presented = false
    @Binding var showingRecent: Bool
    @State private var confirmingStop = false

    init(context: ListenContext = ListenContext(), presented: Bool = false, showingRecent: Binding<Bool>) {
        self.context = context
        self.presented = presented
        _showingRecent = showingRecent
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let recorder = app.recorder {
                        ListenMeterView(recorder: recorder, context: context)
                        if !recorder.isLogging { recentLink }
                    } else {
                        ListenStartView(logging: app.pendingLog) { recording in
                            app.startListening(logging: app.pendingLog, recording: recording)
                        }
                        recentLink
                    }
                }
                .padding(16)
            }
            .background(CeolTokens.bgColor)
            .modifier(CeolTopBar(title: app.recorder?.title ?? tr("Listen"), root: !presented) {
                HStack(spacing: 14) { stopButton; PageMenu(path: nil) }
            })
            .toolbar {
                if presented {
                    ToolbarItem(placement: .topBarLeading) {
                        Button { dismiss() } label: { Image(systemName: "chevron.down") }
                            .accessibilityLabel("Close")
                            .accessibilityIdentifier("listen.close")
                    }
                }
            }
            .confirmationDialog(
                app.recorder?.isLogging == true ? tr("Stop listening to this night?") : tr("Stop listening?"),
                isPresented: $confirmingStop, titleVisibility: .visible
            ) {
                Button("Stop listening", role: .destructive) { app.stopListening() }
                    .accessibilityIdentifier("meter.stop.confirm")
            } message: {
                if app.recorder?.recording == true { Text("The recording so far stays on this phone.") }
            }
            .sheet(isPresented: $showingRecent) { RecentTunesView() }
        }
        .preferredColorScheme(.dark)
    }

    @ViewBuilder private var stopButton: some View {
        if app.recorder != nil {
            Button("Stop", role: .destructive) { confirmingStop = true }
                .accessibilityIdentifier("meter.stop")
        }
    }

    private var recentLink: some View {
        Button { showingRecent = true } label: {
            Label("Recent Tunes Heard", systemImage: "clock.arrow.circlepath")
                .font(.ceol(size: 16, weight: .medium)).foregroundStyle(CeolTokens.primary)
                .frame(maxWidth: .infinity, minHeight: 44)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("listen.recent")
    }
}

/// The last tunes the meter was sure of (RecentTunes), newest first; each opens its
/// sheet, where it can go on your list (no session or night to add it to from here).
struct RecentTunesView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var tunes = RecentTunes.all
    @State private var open: TuneRef?

    var body: some View {
        NavigationStack {
            List {
                if tunes.isEmpty {
                    Text("Nothing heard yet. Tunes the meter is sure of will be listed here.")
                        .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                        .listRowBackground(CeolTokens.drawerBg)
                }
                ForEach(tunes) { t in
                    Button {
                        open = TuneRef(id: t.tuneID, name: t.name, type: t.type, statusKnown: false)
                    } label: {
                        HStack(spacing: 10) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(t.name).font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                                Text(Self.when(t.heardAt)).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                            }
                            Spacer(minLength: 6)
                            if let type = t.type { TypeChip(label: TunesWords.type(type), size: 13) }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .listRowBackground(CeolTokens.drawerBg)
                    .accessibilityIdentifier("recent.tune")
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.drawerBg)
            .navigationTitle("Recent Tunes Heard")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
                if !tunes.isEmpty {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("Clear") {
                            RecentTunes.clear()
                            tunes = []
                        }
                        .accessibilityIdentifier("recent.clear")
                    }
                }
            }
            .sheet(item: $open) { TuneSheet(tune: $0) }
        }
        .ceolDrawer()
    }

    /// "Today, 21:14" / "Fri 10 Oct, 21:14", in the app's language.
    static func when(_ date: Date) -> String {
        if Calendar.current.isDateInToday(date) {
            return tr("Today, \(localizedDate(date, .init(time: .shortened)))")
        }
        return localizedDate(date, .init(date: .abbreviated, time: .shortened))
    }
}

/// A sure tune's whole notation, fetched for the full screen: the setting the tune's
/// detail draws, as the tune sheet draws it.
@Observable
final class NotationFetch {
    let tuneID: Int
    let name: String
    private(set) var image: UIImage?
    private(set) var failed = false

    init(tuneID: Int, name: String) {
        self.tuneID = tuneID
        self.name = name
    }

    func load(_ app: AppModel) async {
        let client = app.auth.client
        if let d = try? await client.getTuneDetail(path: .init(tuneId: tuneID), query: .init()).ok.body.json.sessionTune {
            if let b64 = d.image, let data = Data(base64Encoded: b64), let img = UIImage(data: data) {
                image = img
                return
            }
            if let setting = d.settingOverride ?? d.settingId,
               let r = try? await client.getSettingImage(path: .init(settingId: setting), query: .init(kind: .full)).ok.body.json,
               let data = Data(base64Encoded: r.image ?? ""), let img = UIImage(data: data)
            {
                image = img
                return
            }
        }
        if let r = try? await client.getTuneIncipitImage(path: .init(tuneId: tuneID)).ok.body.json,
           let data = Data(base64Encoded: r.image ?? ""), let img = UIImage(data: data)
        {
            image = img
            return
        }
        failed = true
    }
}
