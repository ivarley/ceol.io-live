// The recorder on screen (spec 053): a mini bar over the tabs while a night is being
// recorded, like a podcast app's, so the rest of the app (the hand logger included)
// stays usable; tap it for the certainty meter, the listening service's top five with
// ten-segment bars, where a tap on a name says "this is it" and "None of these" sends
// it looking again. The model is NightRecorder.

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
        guard let s = state else { return "Listening…" }
        if s.notATune { return "Not a tune right now" }
        if let c = s.shownCandidate ?? s.top.first { return c.name ?? "Tune \(c.tuneID)" }
        return "Listening…"
    }

    var linkText: String {
        switch link {
        case .connecting: "Connecting to the listener…"
        case .live: behind > 8 ? "Catching up, \(Int(behind)) s behind" : "Listening"
        case .reconnecting: "Offline — still recording, will catch up"
        case .unavailable(let why): "Listener unavailable (\(why)) — still recording"
        }
    }

    var clock: String {
        let s = Int(elapsed)
        return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, s / 60 % 60, s % 60)
            : String(format: "%d:%02d", s / 60, s % 60)
    }
}

/// The recording dot: red, its glow following the microphone.
struct RecordingDot: View {
    let level: Double
    var body: some View {
        Circle().fill(CeolTokens.danger).frame(width: 10, height: 10)
            .background(Circle().fill(CeolTokens.danger.opacity(0.35)).frame(width: 10 + 14 * level, height: 10 + 14 * level))
            .frame(width: 24, height: 24)
            .animation(.easeOut(duration: 0.2), value: level)
    }
}

/// The mini recorder over the tabs (and over the composer while a night is logged).
struct RecorderBar: View {
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
        Button { recorder.showingMeter = true } label: {
            HStack(spacing: 10) {
                RecordingDot(level: recorder.level)
                VStack(alignment: .leading, spacing: 2) {
                    Text(recorder.headline).lineLimit(1)
                        .font(.ceol(size: 15, weight: .semibold))
                        .foregroundStyle(CeolTokens.textColor)
                    Text("\(recorder.clock) · \(recorder.linkText)").lineLimit(1)
                        .font(.ceol(size: 12)).monospacedDigit()
                        .foregroundStyle(CeolTokens.textMuted)
                }
                Spacer(minLength: 4)
                if let s = recorder.state, !s.notATune, let c = s.shownCandidate ?? s.top.first {
                    CertaintyBar(p: c.p, cell: 5, height: 14)
                }
                Image(systemName: "chevron.up").font(.system(size: 12)).foregroundStyle(CeolTokens.textMuted)
            }
            .padding(.horizontal, 14)
            .frame(height: Self.height)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Recording, \(recorder.headline). Show the meter.")
        .accessibilityIdentifier("recorder.bar")
    }
}

/// The certainty meter: what it thinks right now, from the last few seconds.
struct ListenMeterView: View {
    let recorder: NightRecorder
    let onStop: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var confirmingStop = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 8) {
                        RecordingDot(level: recorder.level)
                        Text(recorder.clock).font(.ceol(size: 22, weight: .semibold)).monospacedDigit()
                        Spacer()
                        if let t = recorder.state?.tuneness {
                            Text("sounds like a tune \(Int((t * 100).rounded()))%")
                                .font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                    Text(recorder.linkText).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                    if let error = recorder.error {
                        Text(error).font(.ceol(size: 14)).foregroundStyle(CeolTokens.danger)
                    }
                    candidates
                    history
                }
                .padding(16)
            }
            .background(CeolTokens.bgColor)
            .navigationTitle(recorder.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { dismiss() } label: { Image(systemName: "chevron.down") }
                        .accessibilityLabel("Hide the meter")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Stop", role: .destructive) { confirmingStop = true }
                        .accessibilityIdentifier("meter.stop")
                }
            }
            .confirmationDialog("Stop recording this night?", isPresented: $confirmingStop, titleVisibility: .visible) {
                Button("Stop recording", role: .destructive) {
                    dismiss()
                    onStop()
                }
            } message: {
                Text("The recording so far stays on this phone.")
            }
        }
        .preferredColorScheme(.dark)
    }

    /// Names under this belief are greyed, and only a couple of them shown: in practice
    /// the right one comes up to full almost at once, or in one step.
    static let lowBelief = 0.05
    static let lowShown = 2

    @ViewBuilder private var candidates: some View {
        let state = recorder.state
        if let c = recorder.confirmed {
            // "This is it": just that tune, until the service moves on.
            let candidate = state?.top.first { $0.tuneID == c }
            VStack(alignment: .leading, spacing: 10) {
                if let candidate { row(candidate, shown: true) }
                if recorder.logged == c {
                    Label("Logged to the night", systemImage: "checkmark")
                        .font(.ceol(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.success)
                }
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Listening for the tune to end or a new tune to start…")
                        .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                }
                Button("Not this one? Show the others") { recorder.unconfirm() }
                    .font(.ceol(size: 13)).buttonStyle(.borderless)
                    .accessibilityIdentifier("meter.unconfirm")
            }
        } else {
            if state?.notATune == true {
                Text("Probably not a tune right now (\(Int(((state?.none ?? 0) * 100).rounded()))%)")
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            }
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
            if state?.notATune == true {
                // nothing being played as a tune: no names to choose from
            } else if let top = state?.top, !top.isEmpty {
                let strong = top.filter { $0.p >= Self.lowBelief }
                let weak = Array(top.filter { $0.p < Self.lowBelief }.prefix(Self.lowShown))
                VStack(spacing: 8) {
                    ForEach(strong) { c in
                        Button { recorder.tapThis(c.tuneID) } label: { row(c, shown: c.tuneID == state?.shown) }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("meter.tune")
                    }
                    ForEach(weak) { c in
                        Button { recorder.tapThis(c.tuneID) } label: { row(c, shown: false).opacity(0.45) }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("meter.tune.weak")
                    }
                }
            } else if state == nil {
                Text("Waiting for the first few seconds of music.")
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted).padding(.vertical, 20)
            }
            if state?.notATune != true {
                Button { recorder.tapNone() } label: {
                    Text("None of these").font(.ceol(size: 17, weight: .semibold))
                        .frame(maxWidth: .infinity, minHeight: 50)
                }
                .buttonStyle(.bordered)
                .disabled(state?.top.isEmpty ?? true)
                .accessibilityIdentifier("meter.none")
            }
        }
    }

    private func row(_ c: ListenState.Candidate, shown: Bool) -> some View {
        let confirmed = recorder.confirmed == c.tuneID
        return HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(c.name ?? "Tune \(c.tuneID)").font(.ceol(size: 18, weight: .semibold))
                    .foregroundStyle(CeolTokens.textColor).multilineTextAlignment(.leading)
                Text([c.type, c.outside ? "new to this session" : nil, "\(Int((c.p * 100).rounded()))%"]
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
                    Text("\(Segments.formatClock(Double(s.fromMs))) · \(s.name ?? "Tune \(s.tuneID)")")
                        .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                }
            }
            .padding(.top, 8)
        }
    }
}

/// A night's toolbar: start recording it, or open the meter if it is the one recording.
struct RecordNightButton: View {
    @Environment(AppModel.self) private var app
    let instanceID: Int
    let title: String

    var body: some View {
        let recordingThis = app.recorder?.instanceID == instanceID
        Button {
            if recordingThis { app.recorder?.showingMeter = true } else { app.startRecording(instanceID: instanceID, title: title) }
        } label: {
            Label(recordingThis ? "Recording" : "Record", systemImage: recordingThis ? "record.circle.fill" : "record.circle")
                .foregroundStyle(recordingThis ? CeolTokens.danger : CeolTokens.textColor)
        }
        .accessibilityIdentifier("night.record")
    }
}

// MARK: - Recordings on this phone

extension LocalRecording {
    var statusText: String {
        switch phase {
        case .recording: "Recording"
        case .ready: "Not uploaded yet"
        case .converting: "Preparing the file…"
        case .uploading: "Uploading…"
        case .confirming: "Finishing the upload…"
        case .uploaded: "Uploaded — open it in the segmenter"
        case .failed: error ?? "Upload failed"
        }
    }
}

/// While a recording goes up, a slim bar over the tabs (once the recorder's has gone).
struct UploadBar: View {
    let store: RecordingStore

    var body: some View {
        if let r = store.active {
            HStack(spacing: 10) {
                Image(systemName: "arrow.up.circle").foregroundStyle(CeolTokens.primary)
                Text("\(r.title): \(r.statusText)").lineLimit(1).font(.ceol(size: 13))
                    .foregroundStyle(CeolTokens.textColor)
                Spacer(minLength: 4)
                if let p = store.progress[r.id] {
                    ProgressView(value: p).frame(width: 70).tint(CeolTokens.primary)
                }
            }
            .padding(.horizontal, 14)
            .frame(height: Self.height)
            .background(CeolTokens.headerBg)
            .overlay(alignment: .top) { Rectangle().fill(CeolTokens.borderColor).frame(height: 1) }
            .accessibilityIdentifier("upload.bar")
        }
    }

    static let height: CGFloat = 36
}

/// Every recording on this phone: its night, length, size and where its upload has got to.
struct RecordingsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var deleting: LocalRecording?

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
                            if [.ready, .failed].contains(r.phase), app.recorder?.recordingID != r.id {
                                Button(r.phase == .failed ? "Retry upload" : "Upload") { Task { await store.upload(r.id) } }
                                    .accessibilityIdentifier("recordings.upload")
                            }
                            if [.ready, .failed, .uploaded].contains(r.phase), app.recorder?.recordingID != r.id {
                                Button("Delete", role: .destructive) { deleting = r }
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
                Text(deleting?.phase == .uploaded ? "It is on the server; this only frees the space here."
                     : "It hasn't been uploaded: this is the only copy.")
            }
        }
        .preferredColorScheme(.dark)
    }

    private func details(_ r: LocalRecording, _ store: RecordingStore) -> String {
        let seconds = Int(store.duration(r))
        let length = seconds >= 3600 ? String(format: "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
            : String(format: "%d:%02d", seconds / 60, seconds % 60)
        let mb = Double(store.bytes(r)) / 1_000_000
        return "\(r.startedAt.formatted(date: .abbreviated, time: .shortened)) · \(length) · \(String(format: "%.0f MB", mb))"
    }
}
