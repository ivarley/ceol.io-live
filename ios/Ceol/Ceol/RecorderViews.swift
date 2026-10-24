// The listener on screen (spec 053, 059): the certainty meter, the listening service's
// top five with ten-segment bars, where a tap on a name says "this is it" and "None of
// these" sends it looking again; and a mini bar over the tabs while it listens and
// another tab is up, like a podcast app's, so the rest of the app (the hand logger
// included) stays usable. The meter lives on the Listen tab (ListenScreen.swift); the
// model is NightRecorder.
//
// i18n-converted (spec 057). Tune names, and the night's title, are data.

import CeolAPI
import CeolDesign
import CeolLogic
import SwiftUI

/// Ten segments filled up to `p`: cells 1-5 red, 6-8 orange, 9-10 green.
struct CertaintyBar: View {
    let p: Double
    var cell: CGFloat = 12
    var height: CGFloat = 22

    var body: some View {
        let on = Int((p * 10).rounded())
        HStack(spacing: 3) {
            ForEach(1...10, id: \.self) { i in
                RoundedRectangle(cornerRadius: 3)
                    .fill(i <= on ? Self.color(i) : CeolTokens.borderColor)
                    .frame(width: cell, height: height)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("\(Int((p * 100).rounded())) percent")
    }

    static func color(_ i: Int) -> Color {
        i <= 5 ? CeolTokens.danger : i <= 8 ? CeolTokens.warning : CeolTokens.success
    }
}

extension NightRecorder {
    /// The bar's one line: what it thinks right now.
    var headline: String {
        if let error { return error }
        switch showing {
        case .waiting: return tr("Starting up…")
        case .noTune: return tr("No tune playing")
        case .figuring: return tr("Figuring out the tune…")
        case .sure(let c):
            let name = state?.top.first { $0.tuneID == c }?.name
            return name ?? tr("Tune \(c)")
        }
    }

    var linkText: String {
        switch link {
        case .connecting: tr("Connecting to the listener…")
        case .live where hearingError != nil: tr("Not listening — still recording")
        case .live: behind > 8 ? tr("Catching up, \(Int(behind)) s behind")
            : listenWhere == .phone ? tr("Listening on this phone") : tr("Listening")
        case .reconnecting: tr("Offline — still recording, will catch up")
        case .unavailable(let why): tr("Listener unavailable (\(why)) — still recording")
        }
    }

    var clock: String {
        let s = Int(elapsed)
        return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, s / 60 % 60, s % 60)
            : String(format: "%d:%02d", s / 60, s % 60)
    }
}

/// The recording dot: red, its glow following the microphone. `pulses`: every few
/// seconds a red ring leaves it, growing and fading as it goes, while recording.
struct RecordingDot: View {
    let level: Double
    var pulses = false
    var color = CeolTokens.danger
    @State private var ring = false

    var body: some View {
        Circle().fill(color).frame(width: 10, height: 10)
            .background(Circle().fill(color.opacity(0.35)).frame(width: 10 + 14 * level, height: 10 + 14 * level))
            .overlay {
                if pulses {
                    Circle().stroke(color, lineWidth: 1.5).frame(width: 10, height: 10)
                        .scaleEffect(ring ? 3 : 1).opacity(ring ? 0 : 0.8)
                }
            }
            .frame(width: 24, height: 24)
            .animation(.easeOut(duration: 0.2), value: level)
            .task(id: pulses) {
                guard pulses else { return }
                while !Task.isCancelled {
                    var still = Transaction()
                    still.disablesAnimations = true
                    withTransaction(still) { ring = false }
                    withAnimation(.easeOut(duration: 1.4)) { ring = true }
                    try? await Task.sleep(for: .seconds(3))
                }
            }
    }
}

/// The mini listener over the tabs (and over the composer while a night is logged):
/// a tap goes to the Listen tab.
struct RecorderBar: View {
    @Environment(AppModel.self) private var app
    let recorder: NightRecorder
    static let height: CGFloat = 56

    var body: some View {
        HStack(spacing: 0) {
            openButton
            if recorder.canEndSet {
                Button { recorder.endSet() } label: {
                    Text("End set").font(.ceol(size: 13, weight: .semibold))
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(CeolTokens.primaryFill, in: Capsule())
                        .foregroundStyle(.white)
                }
                .buttonStyle(.plain)
                .padding(.trailing, 12)
                .accessibilityIdentifier("recorder.endSet")
            }
        }
        .background(CeolTokens.headerBg)
        .overlay(alignment: .top) { Rectangle().fill(CeolTokens.borderColor).frame(height: 1) }
    }

    private var openButton: some View {
        Button { app.openListen() } label: {
            HStack(spacing: 10) {
                ListeningDot(level: recorder.level, recording: recorder.recording)
                stateIcon.frame(width: 30)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(recorder.headline).lineLimit(1)
                            .font(.ceol(size: 15, weight: .semibold))
                            .foregroundStyle(CeolTokens.textColor)
                        if case .noTune(let none) = recorder.showing {
                            Text(verbatim: "\(Int((none * 100).rounded()))%")
                                .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                    Text("\(recorder.clock) · \(recorder.linkText)").lineLimit(1)
                        .font(.ceol(size: 12)).monospacedDigit()
                        .foregroundStyle(CeolTokens.textMuted)
                }
                Spacer(minLength: 4)
                if recorder.showing == .figuring, let s = recorder.state, let c = s.shownCandidate ?? s.top.first {
                    CertaintyBar(p: c.p, cell: 5, height: 14)
                }
                Image(systemName: "chevron.up").font(.system(size: 12)).foregroundStyle(CeolTokens.textMuted)
            }
            .padding(.horizontal, 14)
            .frame(height: Self.height)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Listening, \(recorder.headline). Show the meter.")
        .accessibilityIdentifier("recorder.bar")
    }

    /// The meter's state, as its icon: the same as the meter's own.
    @ViewBuilder private var stateIcon: some View {
        switch recorder.showing {
        case .waiting, .figuring: ProgressView().controlSize(.small)
        case .noTune: Conversation().font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted)
        case .sure: Image(systemName: "checkmark.circle.fill").font(.system(size: 20)).foregroundStyle(CeolTokens.success)
        }
    }
}

/// The listener's dot: red and pulsing while the audio is kept as a recording, green
/// while it is only listened to (spec 059).
struct ListeningDot: View {
    let level: Double
    let recording: Bool

    var body: some View {
        RecordingDot(level: level, pulses: recording, color: recording ? CeolTokens.danger : CeolTokens.success)
            .accessibilityLabel(recording ? Text("Recording") : Text("Listening"))
    }
}

/// Two people facing each other, talking in turn: each one's sound waves come into the
/// space between them, one and then the other ("No tune playing").
struct Conversation: View {
    @State private var talker = 0

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: "person.wave.2.fill")
                .symbolEffect(.variableColor.iterative, options: .repeating, isActive: talker == 0)
            Image(systemName: "person.wave.2.fill")
                .scaleEffect(x: -1, y: 1)
                .symbolEffect(.variableColor.iterative, options: .repeating, isActive: talker == 1)
        }
        .accessibilityHidden(true)
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1.8))
                talker = 1 - talker
            }
        }
    }
}

/// The meter's screen before it starts: what it will do (log a night's tunes, or just
/// say what is playing), where to listen (system admins: the service admits only
/// them), whether to keep a recording, and "Start Listening". Nothing is heard until
/// that is tapped; then the meter takes its place.
struct ListenStartView: View {
    /// The night whose tunes it will log; nil, just listening (spec 059).
    let logging: (instanceID: Int, title: String)?
    /// Whether to keep a recording: chosen here, on for a night.
    let onStart: (_ recording: Bool) -> Void
    @Environment(AppModel.self) private var app
    @State private var place = ListenWhere.preferred
    @State private var recording = false

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            if let logging {
                Label(tr("Logging tunes to \(logging.title)"), systemImage: "pencil.line")
                    .font(.ceol(size: 16, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                    .accessibilityIdentifier("start.logging")
            } else {
                Text("Tell me what tune is playing. Nothing is logged unless you say so.")
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            }
            if app.user?.isSystemAdmin == true {
                HStack(spacing: 10) {
                    Text("Listening on").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    Picker("Listening on", selection: $place) {
                        ForEach(ListenWhere.allCases) { Text($0.label).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("start.listenWhere")
                }
            }
            // A guest's recording could go nowhere (spec 060): no switch.
            if !app.isGuest {
                Toggle(isOn: $recording) {
                    Text("Keep a recording on this phone").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                }
                .tint(CeolTokens.primaryFill)
                .accessibilityIdentifier("start.recording")
            }
            Button {
                if app.user?.isSystemAdmin == true { ListenWhere.preferred = place }
                onStart(recording)
            } label: {
                Label { Text("Start Listening") } icon: { EarGlyph(size: 26) }
                    .font(.ceol(size: 22, weight: .semibold))
                    .frame(maxWidth: .infinity, minHeight: 72)
            }
            .buttonStyle(.borderedProminent)
            .tint(CeolTokens.primaryFill)
            .accessibilityIdentifier("start.listen")
        }
        .onAppear { recording = logging != nil }
        .onChange(of: logging?.instanceID) { _, _ in recording = logging != nil }
    }
}

/// The certainty meter: what it thinks right now, from the last few seconds. In Log
/// mode (spec 059) the tunes it is sure of go to a night, named at the top; otherwise
/// a sure tune is offered to your tunebook, to wherever this was opened from
/// (`context`), and as notation.
struct ListenMeterView: View {
    @Environment(AppModel.self) private var app
    let recorder: NightRecorder
    var context = ListenContext()
    /// The confirmed tune was tapped: "Wrong tune" or "Tune changed".
    @State private var correcting = false
    /// "Stop logging": asked to be sure.
    @State private var confirmingStopLogging = false
    /// The options, opened (folded away each time the meter opens).
    @State private var showingOptions = false
    /// The context's action ("Add To This Session's Tune List", "Log This Tune"): the
    /// tune it was done for, and what went wrong.
    @State private var acted: Int?
    @State private var actionFailure: String?
    @State private var acting = false
    /// The sure tune's full notation, loading or on screen.
    @State private var notation: NotationFetch?

    /// Everything under the toolbar (its own view so a test can draw it).
    var content: some View {
        VStack(alignment: .leading, spacing: 14) {
            logging
            HStack(spacing: 8) {
                ListeningDot(level: recorder.level, recording: recorder.recording)
                Text(recorder.clock).font(.ceol(size: 22, weight: .semibold)).monospacedDigit()
                Spacer()
                if let t = recorder.state?.tuneness {
                    Text("sounds like a tune \(Int((t * 100).rounded()))%")
                        .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
                }
            }
            Text(recorder.linkText).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            if app.user?.isSystemAdmin == true { listenWhere }
            if let error = recorder.hearingError ?? recorder.error {
                Text(error).font(.ceol(size: 14)).foregroundStyle(CeolTokens.danger)
            }
            mainState
            options
            history
        }
    }

    var body: some View {
        content
            .fullScreenCover(isPresented: Binding(get: { notation?.image != nil }, set: { if !$0 { notation = nil } })) {
                if let n = notation, let image = n.image { NotationFullScreen(image: image, name: n.name) }
            }
    }

    /// Log mode's header: the night the tunes go to, and the way out of it.
    @ViewBuilder private var logging: some View {
        if let log = recorder.logsTo {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Label(tr("Logging tunes to \(log.title)"), systemImage: "pencil.line")
                    .font(.ceol(size: 15, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                    .accessibilityIdentifier("meter.logging")
                Spacer(minLength: 0)
                Button("Stop logging") { confirmingStopLogging = true }
                    .font(.ceol(size: 14, weight: .medium)).foregroundStyle(CeolTokens.primary)
                    .accessibilityIdentifier("meter.stopLogging")
            }
            .padding(12)
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
            .confirmationDialog(
                tr("Stop logging these tunes to \(log.title) and just show them instead?"),
                isPresented: $confirmingStopLogging, titleVisibility: .visible
            ) {
                Button("Stop logging") { recorder.stopLogging() }
                    .accessibilityIdentifier("meter.stopLogging.confirm")
            }
        }
    }

    /// Where the listening is done: a choice for whoever is recording, kept for the next
    /// night. Changing it mid-night restarts the listening, never the recording.
    private var listenWhere: some View {
        HStack(spacing: 10) {
            Text("Listening on").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            Picker("Listening on", selection: Binding(get: { recorder.listenWhere }, set: { recorder.listen(on: $0) })) {
                ForEach(ListenWhere.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("meter.listenWhere")
        }
    }

    /// The options, folded away until opened: logging by itself at 100% (a night only),
    /// keeping a recording, and uploading it (a night's only). The first and last are
    /// kept for the next night.
    private var options: some View {
        DisclosureGroup(isExpanded: $showingOptions) {
            VStack(spacing: 12) {
                selfConfirmSwitch
                recordingSwitch
                if recorder.recording && recorder.isLogging { uploadSwitch }
            }
            .padding(.top, 8)
        } label: {
            Text("Options").font(.ceol(size: 14, weight: .semibold)).foregroundStyle(CeolTokens.textMuted)
        }
        .tint(CeolTokens.textMuted)
        .accessibilityIdentifier("meter.options")
    }

    /// Whether the audio is kept as a recording on the phone (spec 059).
    private var recordingSwitch: some View {
        Toggle(isOn: Binding(get: { recorder.recording }, set: { recorder.setRecording($0) })) {
            Text("Keep a recording on this phone").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
        }
        .tint(CeolTokens.primaryFill)
        .accessibilityIdentifier("meter.recording")
    }

    /// Whether the recording goes up to Ceol's server when the night stops.
    private var uploadSwitch: some View {
        Toggle(isOn: Binding(get: { recorder.uploadsRecording }, set: { recorder.uploadsRecording = $0 })) {
            Text("Upload the recording to Ceol").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
        }
        .tint(CeolTokens.primaryFill)
        .accessibilityIdentifier("meter.uploadRecording")
    }

    /// Whether a tune the meter is sure of (100%) is logged without a tap: kept for the
    /// next night. Off, and not to be had, with no night to log to.
    private var selfConfirmSwitch: some View {
        Toggle(isOn: Binding(get: { recorder.selfConfirms && recorder.isLogging }, set: { recorder.selfConfirms = $0 })) {
            Text("Log automatically at 100%").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
        }
        .tint(CeolTokens.primaryFill)
        .disabled(!recorder.isLogging)
        .accessibilityIdentifier("meter.selfConfirm")
    }

    /// Names under this belief are greyed, and only a couple of them shown: in practice
    /// the right one comes up to full almost at once, or in one step.
    static let lowBelief = 0.05
    static let lowShown = 2

    /// The meter's one main state, right under "Listening on": no tune playing, figuring
    /// out the tune (the candidates), or sure of it (just that tune).
    @ViewBuilder private var mainState: some View {
        switch recorder.showing {
        case .waiting:
            // until the listener's first answer, a step's worth of audio in
            HStack(spacing: 10) {
                ProgressView()
                Text("Starting up…").font(.ceol(size: 24, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .accessibilityIdentifier("meter.startingUp")
        case .noTune(let none):
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Conversation().font(.system(size: 26)).foregroundStyle(CeolTokens.textMuted)
                    Text("No tune playing").font(.ceol(size: 24, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                    Text(verbatim: "\(Int((none * 100).rounded()))%")
                        .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("meter.noTune")
                if recorder.canEndSet {
                    Button { recorder.endSet() } label: {
                        Label("End the set", systemImage: "stop.circle")
                            .font(.ceol(size: 17, weight: .semibold))
                            .frame(maxWidth: .infinity, minHeight: 50)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(CeolTokens.primaryFill)
                    .accessibilityIdentifier("meter.endSet")
                }
            }
        case .figuring:
            figuring
        case .sure(let c):
            sure(c)
        }
    }

    /// A tune is playing, not yet known for sure: the names with their bars, any of which
    /// can be tapped to say "this is it".
    @ViewBuilder private var figuring: some View {
        let state = recorder.state
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                ProgressView()
                Text("Figuring out the tune…").font(.ceol(size: 24, weight: .semibold))
                    .foregroundStyle(CeolTokens.textColor)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .accessibilityIdentifier("meter.figuring")
            if let was = recorder.changedFrom {
                Text("The tune may have changed (was \(was.name ?? tr("Tune \(was.tuneID)"))).")
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    .accessibilityIdentifier("meter.changing")
            } else if let was = state?.changing, state?.mayHaveChanged == true {
                Text("The tune may have changed (was \(was.name ?? tr("Tune \(was.tuneID)"))).")
                    .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    .accessibilityIdentifier("meter.changing")
            }
            if let top = state?.top, !top.isEmpty {
                let strong = top.filter { $0.p >= Self.lowBelief }
                let weak = Array(top.filter { $0.p < Self.lowBelief }.prefix(Self.lowShown))
                VStack(spacing: 8) {
                    ForEach(strong) { c in
                        Button { recorder.tapThis(c.tuneID) } label: {
                            row(c, shown: c.tuneID == state?.shown && state?.mayHaveChanged != true)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("meter.tune")
                    }
                    ForEach(weak) { c in
                        Button { recorder.tapThis(c.tuneID) } label: { row(c, shown: false).opacity(0.45) }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("meter.tune.weak")
                    }
                }
            }
            Button { recorder.tapNone() } label: {
                Text("None of these").font(.ceol(size: 17, weight: .semibold))
                    .frame(maxWidth: .infinity, minHeight: 50)
            }
            .buttonStyle(.bordered)
            .disabled(state?.top.isEmpty ?? true)
            .accessibilityIdentifier("meter.none")
        }
    }

    /// Sure of the tune (100%, or a person said so): just that tune, a green check to its
    /// left. Tapping it says it was wrong, or has ended.
    private func sure(_ c: Int) -> some View {
        let candidate = recorder.state?.top.first { $0.tuneID == c }
        let name = candidate?.name ?? tr("Tune \(c)")
        return VStack(alignment: .leading, spacing: 8) {
            Button { correcting = true } label: {
                HStack(spacing: 12) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 30)).foregroundStyle(CeolTokens.success)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(name).font(.ceol(size: 22, weight: .semibold))
                            .foregroundStyle(CeolTokens.textColor).multilineTextAlignment(.leading)
                        if let candidate {
                            Text([candidate.type.map(TunesWords.type), candidate.outside && recorder.instanceID != nil ? tr("new to this session") : nil]
                                .compactMap { $0 }.joined(separator: " · "))
                                .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 14).padding(.vertical, 14)
                .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(CeolTokens.success, lineWidth: 1))
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("meter.sure")
            .confirmationDialog(name, isPresented: $correcting, titleVisibility: .visible) {
                Button("Wrong tune", role: .destructive) { recorder.wrongTune() }
                Button("Tune changed") { recorder.tuneChanged() }
            }
            if recorder.logged == c {
                Label("Logged to the night", systemImage: "checkmark")
                    .font(.ceol(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.success)
            } else if recorder.isLogging {
                // sure, but not logged by itself (the switch off, or logged lately): by hand
                Button { recorder.tapThis(c) } label: {
                    Label("Log This Tune", systemImage: "pencil.line")
                        .font(.ceol(size: 17, weight: .semibold))
                        .frame(maxWidth: .infinity, minHeight: 50)
                }
                .buttonStyle(.borderedProminent)
                .tint(CeolTokens.primaryFill)
                .accessibilityIdentifier("meter.log")
            }
            Text("Tap the tune if it's wrong or has changed.")
                .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            if !recorder.isLogging { sureActions(c, name: name, type: candidate?.type) }
        }
    }

    /// What to do with a tune it is sure of when no night is being logged (spec 059):
    /// your tunebook, the place this was opened from, the notation.
    private func sureActions(_ c: Int, name: String, type: String?) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            TunebookBox(tune: TuneRef(id: c, name: name, type: type, statusKnown: false))
                .id(c)
            if let action = context.action, context.instanceID == nil || context.instanceID != recorder.logsTo?.instanceID {
                Button {
                    acting = true
                    actionFailure = nil
                    Task {
                        let payload: [String: JSONValue] = ["tune_id": .number(Double(c)), "name": .string(name),
                                                            "tune_type": type.map(JSONValue.string) ?? .null]
                        actionFailure = await action.run(payload)
                        if actionFailure == nil { acted = c }
                        acting = false
                    }
                } label: {
                    Label(acted == c ? action.done : action.label, systemImage: acted == c ? "checkmark" : action.icon)
                        .font(.ceol(size: 17, weight: .semibold))
                        .frame(maxWidth: .infinity, minHeight: 50)
                }
                .buttonStyle(.borderedProminent)
                .tint(CeolTokens.primaryFill)
                .disabled(acting || acted == c)
                .accessibilityIdentifier("meter.action")
                if let actionFailure { Text(actionFailure).font(.ceol(size: 13)).foregroundStyle(CeolTokens.danger) }
            }
            Button {
                notation = NotationFetch(tuneID: c, name: name)
                Task { await notation?.load(app) }
            } label: {
                Label(notation?.tuneID == c && notation?.image == nil ? tr("Loading the notation…") : tr("See the notation"),
                      systemImage: "music.note.list")
                    .font(.ceol(size: 17, weight: .semibold))
                    .frame(maxWidth: .infinity, minHeight: 50)
            }
            .buttonStyle(.bordered)
            .disabled(notation?.tuneID == c && notation?.image == nil)
            .accessibilityIdentifier("meter.notation")
            if let n = notation, n.tuneID == c, n.failed {
                Text("Couldn't draw the notation just now.").font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            }
        }
        .padding(.top, 6)
    }

    private func row(_ c: ListenState.Candidate, shown: Bool) -> some View {
        let confirmed = recorder.confirmed == c.tuneID
        return HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(c.name ?? tr("Tune \(c.tuneID)")).font(.ceol(size: 18, weight: .semibold))
                    .foregroundStyle(CeolTokens.textColor).multilineTextAlignment(.leading)
                // The names beside yours (the session's, the catalogue's), so two people
                // at one session see why their meters name the tune differently.
                let others = recorder.otherNames(for: c.tuneID)
                if !others.isEmpty {
                    (Text("Also known as") + Text(verbatim: " " + others.joined(separator: ", ")))
                        .font(.ceol(size: 12)).italic().foregroundStyle(CeolTokens.textMuted)
                        .multilineTextAlignment(.leading)
                }
                Text([c.type.map(TunesWords.type), c.outside && recorder.instanceID != nil ? tr("new to this session") : nil, "\(Int((c.p * 100).rounded()))%"]
                    .compactMap { $0 }.joined(separator: " · "))
                    .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
            }
            Spacer(minLength: 6)
            if confirmed { Image(systemName: "checkmark.circle.fill").foregroundStyle(CeolTokens.success) }
            CertaintyBar(p: c.p, cell: 11)
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(
            confirmed ? CeolTokens.success : shown ? CeolTokens.primary : CeolTokens.borderColor, lineWidth: 1))
        .contentShape(Rectangle())
    }

    @ViewBuilder private var history: some View {
        if let h = recorder.state?.history, !h.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text("Shown so far").font(.ceol(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.textMuted)
                ForEach(Array(h.reversed().enumerated()), id: \.offset) { _, s in
                    Text(verbatim: "\(Segments.formatClock(Double(s.fromMs))) · \(s.name ?? tr("Tune \(s.tuneID)"))")
                        .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                }
            }
            .padding(.top, 8)
        }
    }
}

/// A night's toolbar: listen and log its tunes (the Listen tab, in Log mode for this
/// night), or go to the meter if it is the night being logged.
struct RecordNightButton: View {
    @Environment(AppModel.self) private var app
    let instanceID: Int
    let title: String

    var body: some View {
        let loggingThis = app.recorder?.logsTo?.instanceID == instanceID
        Button {
            app.openListen(logging: loggingThis ? nil : (instanceID, title))
        } label: {
            Label { Text(loggingThis ? tr("Listening") : tr("Listen")) } icon: { EarGlyph(size: 20) }
                .foregroundStyle(loggingThis ? CeolTokens.danger : CeolTokens.textColor)
        }
        .accessibilityIdentifier("night.record")
    }
}

// MARK: - Recordings on this phone

extension LocalRecording {
    var statusText: String {
        switch phase {
        case .recording: tr("Recording")
        case .ready: keepOnPhone == true ? tr("Kept on this phone") : tr("Not uploaded yet")
        case .converting: tr("Preparing the file…")
        case .uploading: tr("Uploading…")
        case .confirming: tr("Finishing the upload…")
        case .uploaded: tr("Uploaded — open it in the segmenter")
        case .failed: error ?? tr("Upload failed")
        }
    }
}

/// While a recording goes up, a slim bar over the tabs (once the recorder's has gone).
/// Tap it for the recordings list; its × stops the upload.
struct UploadBar: View {
    let store: RecordingStore
    /// Opens the recordings list. The shell presents it (MainTabView), not the bar: the
    /// bar goes when the upload ends, and the list should not go with it.
    let openRecordings: () -> Void
    @State private var cancelling: LocalRecording?

    var body: some View {
        if let r = store.active {
            HStack(spacing: 10) {
                Button(action: openRecordings) {
                    HStack(spacing: 10) {
                        Image(systemName: "arrow.up.circle").foregroundStyle(CeolTokens.primary)
                        Text("\(r.title): \(r.statusText)").lineLimit(1).font(.ceol(size: 13))
                            .foregroundStyle(CeolTokens.textColor)
                        Spacer(minLength: 4)
                        if let p = store.progress[r.id] {
                            ProgressView(value: p).frame(width: 70).tint(CeolTokens.primary)
                        }
                    }
                    .frame(maxHeight: .infinity)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("upload.bar")
                .accessibilityHint("Opens the recordings on this phone")
                if RecordingStore.cancellable(r) {
                    Button { cancelling = r } label: {
                        Image(systemName: "xmark.circle.fill").font(.system(size: 18))
                            .foregroundStyle(CeolTokens.textMuted)
                            .frame(width: 32, height: Self.height)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Cancel upload")
                    .accessibilityIdentifier("upload.cancel")
                }
            }
            .padding(.leading, 14).padding(.trailing, 6)
            .frame(height: Self.height)
            .background(CeolTokens.headerBg)
            .overlay(alignment: .top) { Rectangle().fill(CeolTokens.borderColor).frame(height: 1) }
            .cancelUploadDialog($cancelling, store: store)
        }
    }

    static let height: CGFloat = 36
}

extension View {
    /// "Stop uploading this recording?", for the bar and the list: the recording stays
    /// on the phone (RecordingStore.cancel).
    func cancelUploadDialog(_ recording: Binding<LocalRecording?>, store: RecordingStore) -> some View {
        confirmationDialog("Stop uploading this recording?", isPresented: Binding(
            get: { recording.wrappedValue != nil }, set: { if !$0 { recording.wrappedValue = nil } }), titleVisibility: .visible
        ) {
            Button("Stop upload") {
                if let r = recording.wrappedValue { store.cancel(r.id) }
                recording.wrappedValue = nil
            }
            .accessibilityIdentifier("upload.cancel.confirm")
        } message: {
            Text("It stays on this phone, to upload again later.")
        }
    }
}

/// Every recording on this phone: its night, length, size and where its upload has got to.
struct RecordingsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var deleting: LocalRecording?
    @State private var cancelling: LocalRecording?

    var body: some View {
        let store = app.recordings
        NavigationStack {
            List {
                if store.items.isEmpty {
                    Text("Nothing recorded on this phone yet. Record a night from its page.")
                        .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                }
                ForEach(store.items) { r in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(r.title).font(.ceol(size: 16, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                        Text(details(r, store)).font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
                        Text(r.statusText).font(.ceol(size: 13))
                            .foregroundStyle(r.phase == .failed ? CeolTokens.danger : r.phase == .uploaded ? CeolTokens.success : CeolTokens.textMuted)
                        if let p = store.progress[r.id] { ProgressView(value: p).tint(CeolTokens.primary) }
                        HStack(spacing: 16) {
                            // one made just listening has no night for the server to file it under
                            if [.ready, .failed].contains(r.phase), app.recorder?.recordingID != r.id, r.instanceID != nil {
                                Button(r.phase == .failed ? tr("Retry upload") : tr("Upload")) { Task { await store.upload(r.id) } }
                                    .accessibilityIdentifier("recordings.upload")
                            }
                            if [.ready, .failed, .uploaded].contains(r.phase), app.recorder?.recordingID != r.id {
                                Button("Delete", role: .destructive) { deleting = r }
                            }
                            if RecordingStore.cancellable(r) {
                                Button("Cancel upload") { cancelling = r }
                                    .accessibilityIdentifier("recordings.cancelUpload")
                            }
                        }
                        .buttonStyle(.borderless)
                        .font(.ceol(size: 14, weight: .semibold))
                    }
                    .padding(.vertical, 4)
                    .listRowBackground(CeolTokens.headerBg)
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
            .navigationTitle("Recordings on this phone")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .confirmationDialog("Delete this recording from the phone?", isPresented: Binding(
                get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible
            ) {
                Button("Delete", role: .destructive) {
                    if let d = deleting { store.delete(d) }
                    deleting = nil
                }
            } message: {
                Text(deleting?.phase == .uploaded ? tr("It is on the server; this only frees the space here.")
                     : tr("It hasn't been uploaded: this is the only copy."))
            }
            .cancelUploadDialog($cancelling, store: store)
        }
        .preferredColorScheme(.dark)
    }

    private func details(_ r: LocalRecording, _ store: RecordingStore) -> String {
        let seconds = Int(store.duration(r))
        let length = seconds >= 3600 ? String(format: "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
            : String(format: "%d:%02d", seconds / 60, seconds % 60)
        let mb = Double(store.bytes(r)) / 1_000_000
        return "\(localizedDate(r.startedAt, Date.FormatStyle(date: .abbreviated, time: .shortened))) · \(length) · \(String(format: "%.0f MB", mb))"
    }
}
