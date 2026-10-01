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
// It records with the screen locked and while you use the rest of the app (the audio
// background mode), and picks up again after an interruption such as a phone call.
// The meter's taps ("this is it", "none of these") go back to the service.
//
// The audio arrives on a real-time thread, so AudioCapture is nonisolated: a tap block
// made inside a main-actor type would be main-actor isolated and trap off the main
// thread under Swift 6.

@preconcurrency import AVFoundation
import CeolLogic
import Foundation
import Observation

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

    let fileURL: URL
    @ObservationIgnored private let capture: AudioCapture
    @ObservationIgnored private let streamLink: ListenLink
    @ObservationIgnored private var ticker: Task<Void, Never>?
    @ObservationIgnored private var observers: [NSObjectProtocol] = []

    init(instanceID: Int, title: String, listenURL: URL, token: String?) throws {
        self.instanceID = instanceID
        self.title = title
        let dir = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                              appropriateFor: nil, create: true).appending(path: "Recordings")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        fileURL = dir.appending(path: "night-\(instanceID)-\(stamp).caf")
        capture = AudioCapture(fileURL: fileURL)
        streamLink = ListenLink(url: listenURL, token: token, streamID: UUID().uuidString, capture: capture)
    }

    /// Asks for the microphone, starts the engine, the file and the stream.
    func start() async {
        guard await AVAudioApplication.requestRecordPermission() else {
            error = "Ceol needs the microphone to record. Allow it in Settings."
            stopped = true
            return
        }
        do {
            try capture.start()
        } catch {
            self.error = "Couldn't start recording: \(error.localizedDescription)"
            stopped = true
            return
        }
        watchInterruptions()
        streamLink.run(
            onState: { [weak self] s in Task { @MainActor in self?.received(s) } },
            onLink: { [weak self] l in Task { @MainActor in self?.link = l } })
        ticker = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(250))
                guard let self else { return }
                self.elapsed = Date().timeIntervalSince(self.startedAt)
                self.level = self.capture.level
                self.behind = Double(self.capture.unsent) / Double(ListenWire.sampleRate)
            }
        }
    }

    func stop() {
        guard !stopped else { return }
        stopped = true
        ticker?.cancel()
        streamLink.stop()
        capture.stop()
        for o in observers { NotificationCenter.default.removeObserver(o) }
        observers = []
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    func tapThis(_ tuneID: Int) {
        confirmed = tuneID
        streamLink.send(ListenWire.tapThis(tuneID: tuneID, shown: state?.top.map(\.tuneID) ?? []))
    }

    func tapNone() {
        confirmed = nil
        streamLink.send(ListenWire.tapNone(shown: state?.top.map(\.tuneID) ?? []))
    }

    private func received(_ s: ListenState) {
        state = s
        if let c = confirmed, s.shown != c { confirmed = nil }
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
    private let outFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: Double(ListenWire.sampleRate),
                                          channels: 1, interleaved: true)!

    init(fileURL: URL) { self.fileURL = fileURL }

    var level: Double { lock.withLock { _level } }
    var unsent: Int { lock.withLock { outbox.unsent } }

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
            throw NSError(domain: "Ceol", code: 1, userInfo: [NSLocalizedDescriptionKey: "No microphone input"])
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
        lock.withLock {
            try? file?.write(from: out)
            outbox.append(samples)
            _level = min(1, rms * 4)
        }
    }

    // The link's side of the outbox.
    func resume(serverHas have: Int) -> Int? { lock.withLock { outbox.resume(serverHas: have) } }
    func acknowledge(_ have: Int) { lock.withLock { outbox.acknowledge(have) } }
    func next(max: Int) -> (offset: Int, samples: ArraySlice<Int16>)? { lock.withLock { outbox.next(max: max) } }
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

// MARK: - The stream to the service

/// One WebSocket to the listening service at a time, reconnecting until stopped.
nonisolated final class ListenLink: @unchecked Sendable {
    private let url: URL
    private let token: String?
    private let streamID: String
    private let capture: AudioCapture
    private let lock = NSLock()
    private var task: URLSessionWebSocketTask?
    private var running = true
    private var runner: Task<Void, Never>?

    init(url: URL, token: String?, streamID: String, capture: AudioCapture) {
        self.url = url
        self.token = token
        self.streamID = streamID
        self.capture = capture
    }

    func run(onState: @escaping @Sendable (ListenState) -> Void, onLink: @escaping @Sendable (NightRecorder.Link) -> Void) {
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

    private var isRunning: Bool { lock.withLock { running } }

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
    private func session(onState: @escaping @Sendable (ListenState) -> Void,
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
            try await ws.send(.string(ListenWire.start(streamID: streamID)))
            // the first reply says how much it holds
            guard case .string(let first) = try await ws.receive() else { return nil }
            switch ListenMessage.decode(first) {
            case .ready(let have):
                if let skip = capture.resume(serverHas: have) {
                    try await ws.send(.string(ListenWire.skip(to: skip)))
                }
            case .error(let e): return e
            default: return nil
            }
        } catch {
            if ws.closeCode.rawValue == 4401 { return "Not allowed to listen" }
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
                        case .ack(let have): self.capture.acknowledge(have)
                        case .state(let s): onState(s)
                        default: break
                        }
                    }
                }
            }
            group.addTask { [self] in
                while self.isRunning, !Task.isCancelled {
                    var sentAny = false
                    while let chunk = self.capture.next(max: ListenWire.sampleRate) {
                        do {
                            try await ws.send(.data(ListenWire.frame(offset: chunk.offset, samples: chunk.samples)))
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
