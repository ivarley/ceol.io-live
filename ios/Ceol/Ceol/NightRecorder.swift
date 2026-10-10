// Recording a night, and listening to it (spec 053; specs/changes/inprogress/
// 053 files/listen-on-the-server.md). The microphone goes two ways at once:
//
//   - to a file on the phone, which is the recording: 22,050 Hz mono 16-bit CAF in
//     Application Support/Recordings, written as it comes, so nothing is lost when the
//     network is, and a crash leaves a readable file (CAF needs no closing header);
//   - to the listening service (listen/service.py, `ceol-listen`), which says every
//     4 s what tune it thinks is playing. The wire is CeolLogic.ListenWire: numbered
//     chunks, so a reconnect resends from what the service acknowledged, and after a
//     long outage the service is told to skip (the file still has that audio).
//
// Or the phone listens for itself (ListenWhere.phone, spec 053 "Listening on the
// phone"): CeolHearing turns the audio into notes and features every 4 s, and
// CeolDeciding decides what is playing, on the phone, with no connection at all
// (PhoneDeciding). An app built without the decider's data file sends the notes and
// features to the service instead, which decides. Which one is chosen in the meter,
// and can change mid-night: the recording goes on, and listening starts again on a
// new stream.
//
// It records with the screen locked and while you use the rest of the app (the audio
// background mode), and picks up again after an interruption such as a phone call.
// The meter's taps ("this is it", "none of these") go back to the service. Every state
// the service sends and every tap also go into a meter log beside the recording
// (ListenWire.logLine), which is uploaded with it.
//
// The audio arrives on a real-time thread, so AudioCapture is nonisolated: a tap block
// made inside a main-actor type would be main-actor isolated and trap off the main
// thread under Swift 6.
//
// i18n-converted (spec 057): the messages we set are in the app's language; a refusal
// the listening service sends is shown as it comes. The meter log is not translated.

@preconcurrency import AVFoundation
import CeolDeciding
import CeolHearing
import CeolLogic
import CoreML
import Foundation
import Observation
import UIKit

/// Where a night is listened to (spec 053). Remembered for the next night.
enum ListenWhere: String, CaseIterable, Identifiable {
    case phone, server
    var id: String { rawValue }

    static let key = "ListenWhere"
    static var preferred: ListenWhere {
        get { UserDefaults.standard.string(forKey: key).flatMap(ListenWhere.init(rawValue:)) ?? .server }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: key) }
    }

    var label: String { self == .phone ? tr("This phone") : tr("Ceol's server") }
}

@Observable
final class NightRecorder {
    enum Link: Equatable {
        case connecting, live, reconnecting, unavailable(String)
    }

    let instanceID: Int
    let title: String
    let startedAt = Date()
    private(set) var elapsed: TimeInterval = 0
    /// 0...1, the microphone's level, for the bar's dot.
    private(set) var level: Double = 0
    private(set) var link: Link = .connecting
    /// What the service last said is playing.
    private(set) var state: ListenState?
    /// Seconds of audio the service hasn't acknowledged yet.
    private(set) var behind: TimeInterval = 0
    private(set) var stopped = false
    var error: String?
    /// The full-screen meter, open.
    var showingMeter = false
    /// "This is it": the name a person tapped, until the service moves on.
    private(set) var confirmed: Int?
    /// The audio time of the state on screen when "this is it" was tapped: a state from
    /// before the service heard the tap must not undo it.
    @ObservationIgnored private var confirmedAfterMs = 0

    let fileURL: URL
    /// Where the listening is done now.
    private(set) var listenWhere: ListenWhere
    /// Listening on the phone couldn't start (the models), or stopped.
    private(set) var hearingError: String?
    @ObservationIgnored private let capture: AudioCapture
    @ObservationIgnored private var streamLink: any Listening
    @ObservationIgnored private var hearing: PhoneHearing?
    @ObservationIgnored private let meterLog: MeterLog
    @ObservationIgnored private let listenURL: URL
    @ObservationIgnored private let token: String?
    @ObservationIgnored private var lastDeviceLog = Date.distantPast
    @ObservationIgnored private var ticker: Task<Void, Never>?
    @ObservationIgnored private var observers: [NSObjectProtocol] = []

    /// The recording's id in RecordingStore (its file's base name).
    let recordingID: String

    /// The night's live log, kept open while recording so "this is it" can log the tune
    /// (NightModel.logTune: the same path, ops and offline queue as logging by hand, as
    /// the person using the app). The same model as the night's screen when that is open
    /// (AppModel.openNight), so the tune shows there at once, with or without a connection.
    private var night: NightModel?
    @ObservationIgnored private weak var app: AppModel?
    /// The tune "this is it" last logged, so a second tap doesn't log it twice.
    private(set) var logged: Int?
    /// The row that logging added (nil when it merged into a row already there), so
    /// "Wrong tune" can take it back out.
    @ObservationIgnored private var loggedRow: RecordID?
    /// Tunes a person said were wrong tonight: the meter never logs them by itself again.
    @ObservationIgnored private var wrongTunes: Set<Int> = []
    /// When each tune was last logged from here: not logged by itself again for a while,
    /// so a tune said to have changed doesn't come straight back.
    @ObservationIgnored private var loggedAt: [Int: Date] = [:]
    /// A person said the tune has changed: shown as "may have changed" until the
    /// listener shows another tune (or nothing).
    private(set) var changedFrom: (tuneID: Int, name: String?)?
    /// Whether the meter logs a tune by itself at 100%: the switch on the meter,
    /// remembered for the next night (on unless turned off).
    var selfConfirms: Bool = UserDefaults.standard.object(forKey: "SelfConfirm") as? Bool ?? true {
        didSet {
            guard selfConfirms != oldValue else { return }
            UserDefaults.standard.set(selfConfirms, forKey: "SelfConfirm")
            meterLog.write("app", ListenWire.event("self_confirm", ["on": selfConfirms, "t_ms": state?.tMs ?? 0]))
        }
    }
    /// How sure the meter must be to log a tune by itself: what it shows as 100%.
    nonisolated static let selfConfirmAt = 0.995
    nonisolated static let relogAfter: TimeInterval = 600
    /// Under this, a confirmed tune is no longer claimed: the meter is figuring it out
    /// again (the listener's "may have changed" doubts at the same level).
    nonisolated static let doubtBelow = 0.8
    /// "Not a tune" this many steps running (4 s each) before the set can end. On night
    /// 143's labels: 3 steps (12 s) caught 27 of 28 set breaks and, within a set, ended
    /// only a doubtful one (20 s of talk between two tunes 7 s apart); 2 steps caught all
    /// 28 and two in-set pauses; 6 steps none in-set but only 24 of 28 breaks.
    nonisolated static let endSetAfterSteps = 3
    /// How many states running have said "not a tune".
    @ObservationIgnored private var notATuneSteps = 0

    /// What the meter shows, under "Listening on".
    enum Showing: Equatable {
        case waiting
        /// Nothing is being played as a tune: how sure, 0...1.
        case noTune(Double)
        /// A tune, not yet known for sure.
        case figuring
        /// This tune, for sure (100%, or a person said so).
        case sure(Int)
    }

    var showing: Showing {
        if let c = confirmed { return .sure(c) }
        guard let s = state else { return .waiting }
        if s.notATune { return .noTune(s.none) }
        return .figuring
    }

    init(instanceID: Int, title: String, recordingID: String, fileURL: URL, meterLogURL: URL, listenURL: URL,
         token: String?, listenWhere: ListenWhere = .preferred, app: AppModel? = nil) {
        self.instanceID = instanceID
        self.title = title
        self.app = app
        self.recordingID = recordingID
        self.fileURL = fileURL
        self.listenURL = listenURL
        self.token = token
        self.listenWhere = listenWhere
        capture = AudioCapture(fileURL: fileURL)
        let streamID = UUID().uuidString
        meterLog = MeterLog(url: meterLogURL, since: startedAt)
        meterLog.write("app", ListenWire.event("begin", [
            "instance_id": instanceID, "stream_id": streamID, "recording": recordingID,
            "started_at": ISO8601DateFormatter().string(from: startedAt), "listen": listenWhere.rawValue,
            "decide": listenWhere == .phone && PhoneDeciding.corpus != nil ? "phone" : "server",
            "self_confirm": UserDefaults.standard.object(forKey: "SelfConfirm") as? Bool ?? true,
        ]))
        streamLink = ListenLink(url: listenURL, token: token, streamID: streamID, instanceID: instanceID,
                                source: capture)
        streamLink = makeLink(streamID: streamID)
    }

    /// The stream for the chosen place: audio from the capture, or the phone's hearing,
    /// decided on the phone when it has the decider's data and on the service if not.
    private func makeLink(streamID: String) -> any Listening {
        hearing = nil
        hearingError = nil
        capture.onSamples = nil
        capture.streamsAudio = listenWhere == .server
        guard listenWhere == .phone else {
            return ListenLink(url: listenURL, token: token, streamID: streamID, instanceID: instanceID, source: capture)
        }
        let log = meterLog
        let deciding = PhoneDeciding.corpus.map { PhoneDeciding(corpus: $0, sessionTunes: KnownTunes.cached(instanceID)) }
        if let deciding {
            meterLog.write("app", ListenWire.event("decider", [
                "built_at": deciding.builtAt, "known_tunes": KnownTunes.cached(instanceID)?.count ?? 0,
            ]))
        }
        let h = PhoneHearing(
            sends: deciding == nil,
            onStep: { heard, lagMs in
                deciding?.take(heard)
                // the phone's own work, a step at a time: how long and how far behind
                log.write("app", ListenWire.event("heard", [
                    "t_ms": heard.tMs, "lag_ms": lagMs, "hear_ms": heard.timing.values.reduce(0, +),
                    "timing": heard.timing,
                ]))
            },
            onFailure: { [weak self] why, stopped in
                log.write("app", ListenWire.event(stopped ? "hearing_failed" : "hearing_fallback", ["error": why]))
                if stopped { Task { @MainActor in self?.hearingError = why } }
            })
        hearing = h
        capture.onSamples = { h.take($0) }
        return deciding ?? ListenLink(url: listenURL, token: token, streamID: streamID, instanceID: instanceID, source: h)
    }

    /// Listen somewhere else from now on. The recording carries on; listening starts
    /// again on a new stream, whose times count from here (logged with the sample).
    func listen(on place: ListenWhere) {
        guard place != listenWhere, !stopped else { return }
        ListenWhere.preferred = place
        streamLink.stop()
        listenWhere = place
        state = nil
        confirmed = nil
        changedFrom = nil
        let streamID = UUID().uuidString
        capture.resetOutbox()
        meterLog.write("app", ListenWire.event("listen", [
            "listen": place.rawValue, "stream_id": streamID, "from_sample": capture.written,
            "decide": place == .phone && PhoneDeciding.corpus != nil ? "phone" : "server",
        ]))
        streamLink = makeLink(streamID: streamID)
        runLink()
    }

    /// Asks for the microphone, starts the engine, the file and the stream.
    func start() async {
        guard await AVAudioApplication.requestRecordPermission() else {
            error = tr("Ceol needs the microphone to record. Allow it in Settings.")
            stopped = true
            return
        }
        do {
            try capture.start()
        } catch {
            self.error = tr("Couldn't start recording: \(error.localizedDescription)")
            stopped = true
            return
        }
        watchInterruptions()
        // the session's own tunes, fresh if there is a signal: a phone deciding for itself
        // takes them if it has not begun yet (the night's screen usually fetched them)
        if let app, let deciding = streamLink as? PhoneDeciding {
            let id = instanceID
            Task {
                if let ids = await KnownTunes.refresh(id, app: app, timeout: 5) { deciding.useSessionTunes(ids) }
            }
        }
        if let app { night = app.openNight(instanceID) }
        runLink()
        UIDevice.current.isBatteryMonitoringEnabled = true
        ticker = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(250))
                guard let self else { return }
                self.elapsed = Date().timeIntervalSince(self.startedAt)
                self.level = self.capture.level
                self.behind = self.hearing?.behindSeconds
                    ?? Double(self.capture.unsent) / Double(ListenWire.sampleRate)
                self.logDevice()
            }
        }
    }

    private func runLink() {
        let log = meterLog
        let link = streamLink
        link.run(
            onState: { [weak self, weak link] s, text in
                // a stream stopped by a switch may still deliver a late state: not this night's
                guard link?.isRunning == true else { return }
                log.write("in", text)
                Task { @MainActor in
                    // a state from a stream left behind by a switch is not this one's
                    guard let self, let link, self.streamLink === link else { return }
                    self.received(s)
                }
            },
            onLink: { [weak self, weak link] l in
                log.write("app", ListenWire.event("link", ["link": "\(l)"]))
                Task { @MainActor in
                    guard let self, let link, self.streamLink === link else { return }
                    self.link = l
                }
            })
    }

    /// Once a minute, the phone's battery and temperature beside where it listens: what
    /// listening on the phone costs, read back from the meter log.
    private func logDevice() {
        guard Date().timeIntervalSince(lastDeviceLog) >= 60 else { return }
        lastDeviceLog = Date()
        let d = UIDevice.current
        let thermal = ["nominal", "fair", "serious", "critical"][min(3, ProcessInfo.processInfo.thermalState.rawValue)]
        meterLog.write("app", ListenWire.event("device", [
            "listen": listenWhere.rawValue, "battery": Double(d.batteryLevel),
            "charging": d.batteryState == .charging || d.batteryState == .full, "thermal": thermal,
            "low_power": ProcessInfo.processInfo.isLowPowerModeEnabled,
        ]))
    }

    func stop() {
        guard !stopped else { return }
        stopped = true
        ticker?.cancel()
        streamLink.stop()
        capture.stop()
        hearing = nil
        if let night { app?.closeNight(night) }
        night = nil
        meterLog.write("app", ListenWire.event("stop"))
        meterLog.close()
        for o in observers { NotificationCenter.default.removeObserver(o) }
        observers = []
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    func tapThis(_ tuneID: Int, auto: Bool = false) {
        confirmed = tuneID
        confirmedAfterMs = state?.tMs ?? 0
        changedFrom = nil
        send(ListenWire.tapThis(tuneID: tuneID, shown: state?.top.map(\.tuneID) ?? [], auto: auto))
        logToNight(tuneID, auto: auto)
    }

    /// The meter is sure (100%): it says "this is it" itself, as a person would, and the
    /// tune is logged. The tune last logged, sure again, is shown as sure but not logged a
    /// second time. Never a tune said to be wrong tonight, nor another one logged from
    /// here in the last ten minutes.
    private func selfConfirm(_ s: ListenState) {
        guard selfConfirms,
            let pick = Self.selfConfirmTune(s, confirmed: confirmed, wrong: wrongTunes, lastLogged: logged,
                                            loggedAt: loggedAt, now: Date())
        else { return }
        if pick.log {
            tapThis(pick.tune, auto: true)
        } else {
            confirmed = pick.tune
            confirmedAfterMs = s.tMs
            changedFrom = nil
            meterLog.write("app", ListenWire.event("sure_again", ["tune_id": pick.tune, "t_ms": s.tMs]))
        }
    }

    /// The tune to confirm by itself in this state, if any, and whether to log it.
    nonisolated static func selfConfirmTune(_ s: ListenState, confirmed: Int?, wrong: Set<Int>, lastLogged: Int?,
                                            loggedAt: [Int: Date], now: Date) -> (tune: Int, log: Bool)? {
        guard confirmed == nil, !s.notATune, !s.mayHaveChanged, let c = s.shownCandidate,
            c.p >= selfConfirmAt, !wrong.contains(c.tuneID)
        else { return nil }
        if c.tuneID == lastLogged { return (c.tuneID, false) }
        guard now.timeIntervalSince(loggedAt[c.tuneID] ?? .distantPast) >= relogAfter else { return nil }
        return (c.tuneID, true)
    }

    /// "Wrong tune": the confirmed tune isn't what's playing. Its row comes back out of the
    /// night, the listener rules it out and looks wider (as "None of these" does), and the
    /// meter won't log it by itself again tonight.
    func wrongTune() {
        guard let c = confirmed else { return }
        if logged == c, let row = loggedRow { night?.removeLogged(row) }
        if logged == c {
            logged = nil
            loggedRow = nil
            loggedAt[c] = nil
        }
        wrongTunes.insert(c)
        confirmed = nil
        send(ListenWire.tapNone(shown: [c], why: "wrong"))
        meterLog.write("app", ListenWire.event("wrong_tune", ["tune_id": c, "t_ms": state?.tMs ?? 0]))
    }

    /// "Tune changed": the confirmed tune was right and has ended. It stays logged; the
    /// listener lets go of it at once (ruled out for a while, a wider search) instead of
    /// waiting for its belief to fade, and the meter says so meanwhile.
    func tuneChanged() {
        guard let c = confirmed else { return }
        let name = state?.top.first { $0.tuneID == c }?.name
        changedFrom = (c, name)
        confirmed = nil
        send(ListenWire.tapNone(shown: [c], why: "changed"))
        meterLog.write("app", ListenWire.event("tune_changed", ["tune_id": c, "t_ms": state?.tMs ?? 0]))
    }

    /// Nothing is being played as a tune and the night's last set is still open (it has a
    /// tune, and no break after it): offer to end it.
    var canEndSet: Bool {
        guard state?.notATune == true, notATuneSteps >= Self.endSetAfterSteps,
            let last = night?.log?.ordered.last
        else { return false }
        return !last.isBreak
    }

    /// End the night's open set, as the logger's own "end the set" does. `auto`: the meter
    /// did it itself (the "by itself" switch on).
    func endSet(auto: Bool = false) {
        night?.endSet()
        meterLog.write("app", ListenWire.event("end_set", ["t_ms": state?.tMs ?? 0, "auto": auto]))
    }

    /// A tap to the service, kept in the meter log too.
    private func send(_ text: String) {
        meterLog.write("out", text)
        streamLink.send(text)
    }

    /// Add the tapped tune to the end of the night's log. A tune of the session's
    /// repertoire goes in by its id; one the whole-corpus fallback found goes in by its
    /// thesession.org id, as the composer logs a pasted thesession link. Only the id is
    /// sent; the name (as the meter shows it, received) is the row's label until the
    /// server answers.
    private func logToNight(_ tuneID: Int, auto: Bool = false) {
        guard logged != tuneID, let night, night.log != nil else { return }
        let c = state?.top.first { $0.tuneID == tuneID }
        let name: JSONValue = c?.name.map(JSONValue.string) ?? .null
        if c?.outside == true {
            loggedRow = night.logTune(["thesession_id": JSONValue(tuneID), "name": name], at: .end)
        } else {
            loggedRow = night.logTune(["tune_id": JSONValue(tuneID), "name": name], at: .end)
        }
        logged = tuneID
        loggedAt[tuneID] = Date()
        meterLog.write("app", ListenWire.event("logged", ["tune_id": tuneID, "outside": c?.outside == true, "auto": auto]))
    }

    func tapNone() {
        confirmed = nil
        send(ListenWire.tapNone(shown: state?.top.map(\.tuneID) ?? []))
    }

    func received(_ s: ListenState) {
        let vocab = night?.vocab
        state = vocab.map { v in s.named { v.byID[$0]?.displayName } } ?? s
        notATuneSteps = s.notATune ? notATuneSteps + 1 : 0
        // no longer sure (another tune, nothing playing, or its belief has dropped): the
        // meter is figuring it out again
        if let c = confirmed, s.tMs > confirmedAfterMs + 4000,
            s.shown != c || s.notATune || s.mayHaveChanged
                || (s.top.first { $0.tuneID == c }?.p ?? 0) < Self.doubtBelow
        {
            confirmed = nil
        }
        // a tune said to have changed: until the listener shows another, or nothing
        if let was = changedFrom, s.notATune || (s.shown != nil && s.shown != was.tuneID) { changedFrom = nil }
        selfConfirm(state ?? s)
        // a long enough stretch of no tune ends the set, by itself as a person would
        if selfConfirms, canEndSet { endSet(auto: true) }
    }

    /// A phone call or another app's audio stops the engine; when it ends, start again.
    /// A route change (headphones, a Bluetooth mic) changes the input's format.
    private func watchInterruptions() {
        let center = NotificationCenter.default
        observers.append(center.addObserver(forName: AVAudioSession.interruptionNotification, object: nil,
                                            queue: .main) { [weak self] note in
            let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt
            let ended = raw.flatMap(AVAudioSession.InterruptionType.init(rawValue:)) == .ended
            Task { @MainActor in
                guard let self, !self.stopped, ended else { return }
                try? self.capture.restart()
            }
        })
        observers.append(center.addObserver(forName: .AVAudioEngineConfigurationChange, object: nil,
                                            queue: .main) { [weak self] _ in
            Task { @MainActor in
                guard let self, !self.stopped else { return }
                try? self.capture.restart()
            }
        })
    }
}

// MARK: - The microphone, to the file and the outbox

/// The engine, the converter to 22,050 Hz mono 16-bit, the file, and the audio the
/// service hasn't acknowledged. Everything here runs off the main thread.
nonisolated final class AudioCapture: @unchecked Sendable {
    private let engine = AVAudioEngine()
    private let fileURL: URL
    private let lock = NSLock()
    private var file: AVAudioFile?
    private var converter: AVAudioConverter?
    // Ten minutes of unsent audio, about 26 MB; older audio is still in the file.
    private var outbox = ListenOutbox(capacity: ListenWire.sampleRate * 600)
    private var _level: Double = 0
    private var _written = 0
    private var _streamsAudio = true
    private var _onSamples: (@Sendable ([Int16]) -> Void)?
    private let outFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: Double(ListenWire.sampleRate),
                                          channels: 1, interleaved: true)!

    init(fileURL: URL) { self.fileURL = fileURL }

    var level: Double { lock.withLock { _level } }
    var unsent: Int { lock.withLock { outbox.unsent } }
    /// Samples written to the file so far.
    var written: Int { lock.withLock { _written } }
    /// Whether the audio goes to the listening service (not when the phone listens).
    var streamsAudio: Bool {
        get { lock.withLock { _streamsAudio } }
        set { lock.withLock { _streamsAudio = newValue } }
    }
    /// Every converted block of samples, as it comes (the phone's hearing).
    var onSamples: (@Sendable ([Int16]) -> Void)? {
        get { lock.withLock { _onSamples } }
        set { lock.withLock { _onSamples = newValue } }
    }

    /// A new stream: nothing sent, nothing held.
    func resetOutbox() { lock.withLock { outbox = ListenOutbox(capacity: ListenWire.sampleRate * 600) } }

    func start() throws {
        let session = AVAudioSession.sharedInstance()
        // .measurement turns off the voice processing (gain control, noise suppression)
        // that would flatten a session; play-and-record lets the night's player still play.
        try session.setCategory(.playAndRecord, mode: .measurement,
                                options: [.defaultToSpeaker, .allowBluetoothA2DP, .mixWithOthers])
        try session.setActive(true)
        file = try AVAudioFile(forWriting: fileURL, settings: outFormat.settings,
                               commonFormat: .pcmFormatInt16, interleaved: true)
        try startEngine()
    }

    func restart() throws {
        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
        try AVAudioSession.sharedInstance().setActive(true)
        try startEngine()
    }

    func stop() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        lock.withLock { file = nil }      // closes it
    }

    private func startEngine() throws {
        let input = engine.inputNode
        let inFormat = input.outputFormat(forBus: 0)
        guard inFormat.sampleRate > 0, let conv = AVAudioConverter(from: inFormat, to: outFormat) else {
            throw NSError(domain: "Ceol", code: 1, userInfo: [NSLocalizedDescriptionKey: tr("No microphone input")])
        }
        converter = conv
        input.installTap(onBus: 0, bufferSize: 4096, format: inFormat) { [weak self] buffer, _ in
            self?.handle(buffer)
        }
        engine.prepare()
        try engine.start()
    }

    private func handle(_ buffer: AVAudioPCMBuffer) {
        guard let converter else { return }
        let ratio = outFormat.sampleRate / buffer.format.sampleRate
        let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 1024
        guard let out = AVAudioPCMBuffer(pcmFormat: outFormat, frameCapacity: capacity) else { return }
        let feed = ConverterFeed(buffer)
        var err: NSError?
        converter.convert(to: out, error: &err) { _, status in feed.next(status) }
        guard err == nil, out.frameLength > 0, let ch = out.int16ChannelData?[0] else { return }
        let samples = Array(UnsafeBufferPointer(start: ch, count: Int(out.frameLength)))
        var sum = 0.0
        for s in samples { let v = Double(s) / 32768; sum += v * v }
        let rms = (sum / Double(samples.count)).squareRoot()
        let hear = lock.withLock { () -> (@Sendable ([Int16]) -> Void)? in
            try? file?.write(from: out)
            _written += samples.count
            if _streamsAudio { outbox.append(samples) }
            _level = min(1, rms * 4)
            return _onSamples
        }
        hear?(samples)
    }
}

/// What a stream to the listening service carries: the audio (AudioCapture), or what the
/// phone heard (PhoneHearing). ListenLink does the connecting and reconnecting.
nonisolated protocol ListenSource: AnyObject, Sendable {
    func startMessage(streamID: String, instanceID: Int) -> String
    /// The service's first reply -> what to send before the rest, or nil if it isn't the
    /// "ready" this stream expects.
    func ready(_ reply: ListenMessage) -> [String]?
    func acknowledged(_ message: ListenMessage)
    /// The next message to send, if there is one now.
    func next() -> URLSessionWebSocketTask.Message?
}

nonisolated extension AudioCapture: ListenSource {
    func startMessage(streamID: String, instanceID: Int) -> String { ListenWire.start(streamID: streamID, instanceID: instanceID) }

    func ready(_ reply: ListenMessage) -> [String]? {
        guard case .ready(let have) = reply else { return nil }
        let skip = lock.withLock { outbox.resume(serverHas: have) }
        return skip.map { [ListenWire.skip(to: $0)] } ?? []
    }

    func acknowledged(_ message: ListenMessage) {
        if case .ack(let have) = message { lock.withLock { outbox.acknowledge(have) } }
    }

    func next() -> URLSessionWebSocketTask.Message? {
        guard let chunk = lock.withLock({ outbox.next(max: ListenWire.sampleRate) }) else { return nil }
        return .data(ListenWire.frame(offset: chunk.offset, samples: chunk.samples))
    }
}

// MARK: - Listening on the phone

/// The phone's own hearing (CeolHearing.Hearer) on a queue of its own: every 4 s of audio
/// becomes a "heard" message, held until the service acknowledges it.
nonisolated final class PhoneHearing: ListenSource, @unchecked Sendable {
    private let queue = DispatchQueue(label: "io.ceol.hearing", qos: .userInitiated)
    private let lock = NSLock()
    private var outbox = HeardOutbox(capacity: 150)       // ten minutes of steps
    private var hearer: Hearer?                          // touched only on `queue`
    private var captured = 0                             // samples handed over
    private var lastStepT = 0
    private var failed = false
    private let onStep: @Sendable (Heard, Int) -> Void
    /// Why, and whether listening has stopped (or only moved to the CPU).
    private let onFailure: @Sendable (String, Bool) -> Void
    /// The steps go to the service (it decides); false when the phone decides itself.
    private let sends: Bool

    init(sends: Bool = true, onStep: @escaping @Sendable (Heard, Int) -> Void,
         onFailure: @escaping @Sendable (String, Bool) -> Void) {
        self.sends = sends
        self.onStep = onStep
        self.onFailure = onFailure
        // first on the queue, so every block of audio waits for the models
        queue.async { [self] in
            do {
                // the CPU and Neural Engine, not the GPU, which iOS refuses an app in the
                // background (the screen locked, which is most of a night)
                hearer = Hearer(models: try HearingModels(computeUnits: .cpuAndNeuralEngine))
            } catch {
                fail(tr("Couldn't start listening on this phone: \(error.localizedDescription)"))
            }
        }
    }

    private func fail(_ why: String) {
        lock.withLock { failed = true }
        onFailure(why, true)
    }

    /// A block of 22,050 Hz samples from the microphone.
    func take(_ samples: [Int16]) {
        lock.withLock { captured += samples.count }
        queue.async { [self] in
            guard let hearer else { return }
            hearer.append(samples)
            do {
                try steps(hearer)
            } catch {
                // once: the models held to the CPU, and the step again
                do {
                    hearer.models = try HearingModels(computeUnits: .cpuOnly)
                    onFailure("Listening on this phone moved to its CPU: \(error.localizedDescription)", false)
                    try steps(hearer)
                } catch {
                    self.hearer = nil
                    fail(tr("Listening on this phone stopped: \(error.localizedDescription)"))
                }
            }
        }
    }

    private func steps(_ hearer: Hearer) throws {
        for heard in try hearer.readySteps() {
            let lag = lock.withLock { () -> Int in
                if sends { outbox.append(t: heard.tMs, message: heard.message()) }
                lastStepT = heard.tMs
                return Int(1000 * Double(captured) / Double(Hearer.sampleRate)) - heard.tMs
            }
            onStep(heard, lag)
        }
    }

    /// How far behind the microphone the service's input is, in seconds: steps not yet
    /// heard here, and steps heard but not yet acknowledged.
    var behindSeconds: Double {
        lock.withLock {
            let heardTo = failed ? 0 : lastStepT
            let notHeard = Double(captured) / Double(Hearer.sampleRate) - Double(heardTo) / 1000
            return max(0, notHeard - Double(Hearer.hopMs) / 1000) + Double(outbox.unsent * Hearer.hopMs) / 1000
        }
    }

    func startMessage(streamID: String, instanceID: Int) -> String { ListenWire.startHeard(streamID: streamID, instanceID: instanceID) }

    func ready(_ reply: ListenMessage) -> [String]? {
        guard case .readyHeard(let t) = reply else { return nil }
        lock.withLock { outbox.resume(serverTook: t) }
        return []
    }

    func acknowledged(_ message: ListenMessage) {
        if case .heardAck(let t) = message { lock.withLock { outbox.acknowledge(t) } }
    }

    func next() -> URLSessionWebSocketTask.Message? {
        lock.withLock { outbox.next() }.map { .string($0.message) }
    }
}

/// Hands the converter one buffer, then says there is no more for now. The converter
/// calls it synchronously, inside convert().
nonisolated private final class ConverterFeed: @unchecked Sendable {
    private let buffer: AVAudioPCMBuffer
    private var fed = false

    init(_ buffer: AVAudioPCMBuffer) { self.buffer = buffer }

    func next(_ status: UnsafeMutablePointer<AVAudioConverterInputStatus>) -> AVAudioBuffer? {
        if fed {
            status.pointee = .noDataNow
            return nil
        }
        fed = true
        status.pointee = .haveData
        return buffer
    }
}

// MARK: - Deciding on the phone

/// Where the states come from and the taps go: the listening service (ListenLink), or
/// the phone itself (PhoneDeciding).
nonisolated protocol Listening: AnyObject, Sendable {
    var isRunning: Bool { get }
    func run(onState: @escaping @Sendable (ListenState, String) -> Void,
             onLink: @escaping @Sendable (NightRecorder.Link) -> Void)
    /// A tap, as ListenWire writes it for the service.
    func send(_ text: String)
    func stop()
}

/// The service's deciding, done on the phone (CeolDeciding, spec 053 "Listening on the
/// phone, offline"): each step the phone heard goes to the decider on a queue of its
/// own, and its state comes back as the service's "state" message would, so the meter
/// and its log cannot tell the difference. No network at all.
nonisolated final class PhoneDeciding: Listening, @unchecked Sendable {
    /// The decider's data as it is now (the newest of the copy built in and one fetched
    /// since, DeciderRefresher), mapped afresh for each stream: a night keeps the file it
    /// started with, and a newer one fetched meanwhile is the next night's. Nil if the
    /// app has none.
    static var corpus: Corpus? { Corpus.shipped.flatMap { try? Corpus(contentsOf: $0) } }

    private let queue = DispatchQueue(label: "io.ceol.deciding", qos: .userInitiated)
    private let lock = NSLock()
    private var running = true
    private var onState: (@Sendable (ListenState, String) -> Void)?
    private let corpus: Corpus
    private var decider: Decider?                    // touched only on `queue`
    private var stepped = false                      // touched only on `queue`

    /// When the corpus this stream decides from was built.
    var builtAt: String { corpus.builtAt }

    /// `sessionTunes`: the tunes the session logged before the night (KnownTunes); nil,
    /// and the popular tunes stand in.
    init(corpus: Corpus, sessionTunes: [Int]?) {
        self.corpus = corpus
        queue.async { [self] in decider = Decider(corpus: corpus, sessionTunes: sessionTunes) }
    }

    /// The session's tunes arrived after the stream began: taken if nothing has been
    /// decided yet, so a night is decided one way throughout.
    func useSessionTunes(_ ids: [Int]) {
        queue.async { [self] in
            guard !stepped else { return }
            decider = Decider(corpus: corpus, sessionTunes: ids)
        }
    }

    var isRunning: Bool { lock.withLock { running } }

    func run(onState: @escaping @Sendable (ListenState, String) -> Void,
             onLink: @escaping @Sendable (NightRecorder.Link) -> Void) {
        lock.withLock { self.onState = onState }
        onLink(.live)
    }

    /// One step of the phone's hearing.
    func take(_ heard: Heard) {
        queue.async { [self] in
            guard let decider, let onState = lock.withLock({ running ? self.onState : nil }) else { return }
            stepped = true
            let notes = heard.notes.mapValues { $0.map { HeardNote($0.t0, $0.t1, $0.midi) } }
            decider.step(tMs: heard.tMs, notes: notes, features: heard.features, heardMs: heard.heardMs)
            let text = decider.stateMessage()
            if case .state(let s) = ListenMessage.decode(text) { onState(s, text) }
        }
    }

    func send(_ text: String) {
        guard let obj = try? JSONSerialization.jsonObject(with: Data(text.utf8)) as? [String: Any],
            obj["type"] as? String == "tap"
        else { return }
        let shown = (obj["shown"] as? [NSNumber] ?? []).map(\.intValue)
        let tune = (obj["tune_id"] as? NSNumber)?.intValue
        queue.async { [self] in
            switch obj["action"] as? String {
            case "this": if let tune { decider?.tapThis(tune) }
            case "none": decider?.tapNone(shown: shown)
            default: break
            }
        }
    }

    func stop() { lock.withLock { running = false } }
}

// MARK: - The stream to the service

/// One WebSocket to the listening service at a time, reconnecting until stopped.
nonisolated final class ListenLink: Listening, @unchecked Sendable {
    private let url: URL
    private let token: String?
    private let streamID: String
    private let instanceID: Int
    private let source: any ListenSource
    private let lock = NSLock()
    private var task: URLSessionWebSocketTask?
    private var running = true
    private var runner: Task<Void, Never>?

    init(url: URL, token: String?, streamID: String, instanceID: Int, source: any ListenSource) {
        self.url = url
        self.token = token
        self.streamID = streamID
        self.instanceID = instanceID
        self.source = source
    }

    func run(onState: @escaping @Sendable (ListenState, String) -> Void, onLink: @escaping @Sendable (NightRecorder.Link) -> Void) {
        runner = Task.detached { [self] in
            var delay: Double = 1
            while self.isRunning {
                onLink(.connecting)
                let refused = await self.session(onState: onState, onLink: onLink)
                guard self.isRunning else { break }
                if let refused {
                    onLink(.unavailable(refused))
                } else {
                    onLink(.reconnecting)
                }
                try? await Task.sleep(for: .seconds(delay))
                delay = min(delay * 2, 30)
            }
        }
    }

    var isRunning: Bool { lock.withLock { running } }

    func stop() {
        let t = lock.withLock { () -> URLSessionWebSocketTask? in
            running = false
            return task
        }
        t?.send(.string(ListenWire.stop())) { _ in }
        Task.detached {
            try? await Task.sleep(for: .seconds(1))
            t?.cancel(with: .goingAway, reason: nil)
        }
        runner?.cancel()
    }

    func send(_ text: String) {
        lock.withLock { task }?.send(.string(text)) { _ in }
    }

    /// One connection, until it drops: start, then send what's unsent while reading the
    /// service's messages. Returns a reason when the service refused us (no point
    /// hammering it), nil when the connection just dropped.
    private func session(onState: @escaping @Sendable (ListenState, String) -> Void,
                         onLink: @escaping @Sendable (NightRecorder.Link) -> Void) async -> String? {
        var request = URLRequest(url: url)
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let ws = URLSession.shared.webSocketTask(with: request)
        ws.maximumMessageSize = 1 << 20
        lock.withLock { task = ws }
        ws.resume()
        defer {
            ws.cancel(with: .normalClosure, reason: nil)
            lock.withLock { if task === ws { task = nil } }
        }
        do {
            try await ws.send(.string(source.startMessage(streamID: streamID, instanceID: instanceID)))
            // the first reply says how much it holds
            guard case .string(let first) = try await ws.receive() else { return nil }
            let reply = ListenMessage.decode(first)
            if case .error(let e) = reply { return e }
            guard let answers = source.ready(reply) else { return nil }
            for a in answers { try await ws.send(.string(a)) }
        } catch {
            if ws.closeCode.rawValue == 4401 { return tr("Not allowed to listen") }
            return nil
        }
        onLink(.live)
        // Read and send side by side; whichever fails first ends the connection.
        return await withTaskGroup(of: Void.self) { group in
            group.addTask { [self] in
                while self.isRunning, !Task.isCancelled {
                    guard let msg = try? await ws.receive() else { return }
                    if case .string(let text) = msg {
                        switch ListenMessage.decode(text) {
                        case .state(let s): onState(s, text)
                        case let m: self.source.acknowledged(m)
                        }
                    }
                }
            }
            group.addTask { [self] in
                while self.isRunning, !Task.isCancelled {
                    var sentAny = false
                    while let message = self.source.next() {
                        do {
                            try await ws.send(message)
                        } catch { return }
                        sentAny = true
                    }
                    if !sentAny { try? await Task.sleep(for: .milliseconds(250)) }
                }
            }
            await group.next()
            // the reader waits in receive() until the socket goes; end it here, or the
            // group would wait for it forever
            ws.cancel(with: .normalClosure, reason: nil)
            group.cancelAll()
            return nil
        }
    }
}

/// The meter log beside a recording (ListenWire.logLine), appended as things happen so a
/// crash keeps what came before. Written from the socket's thread and the main actor.
nonisolated final class MeterLog: @unchecked Sendable {
    private let lock = NSLock()
    private var handle: FileHandle?
    private let since: Date

    init(url: URL, since: Date) {
        self.since = since
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        handle = try? FileHandle(forWritingTo: url)
        _ = try? handle?.seekToEnd()
    }

    func write(_ dir: String, _ message: String) {
        let ms = Int(Date().timeIntervalSince(since) * 1000)
        let line = ListenWire.logLine(atMs: ms, dir: dir, message: message)
        lock.withLock { try? handle?.write(contentsOf: Data(line.utf8)) }
    }

    func close() {
        lock.withLock {
            try? handle?.close()
            handle = nil
        }
    }
}
