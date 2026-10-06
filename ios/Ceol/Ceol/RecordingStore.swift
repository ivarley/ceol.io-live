// Recordings kept on the phone, and their way to the server (spec 053; the web's upload
// is spec 050's, and this takes the same path):
//
//   1. NightRecorder writes the night to a CAF file; a small JSON beside it says which
//      night, when it started, and where it has got to, so a crash or a quit leaves the
//      two together and the upload can be picked up later.
//   2. On Stop the CAF becomes a FLAC (lossless, about half the size; WAV if the
//      encoder isn't there), POST /api/recordings/upload-url signs a direct S3 upload,
//      and a background URLSession PUTs the file, so it carries on with the screen
//      locked or the app in the background.
//   3. POST /api/recordings confirms it and starts the server's ingest (waveform,
//      playback proxy); from there the night opens in the segmenter like any upload.
//   4. The meter log (what the listening service showed, and the taps; NightRecorder's
//      MeterLog) goes up to PUT /api/recordings/<id>/listen-log, which keeps it beside
//      the audio. If that fails it is tried again the next time the app starts.
//
// An upload that failed (offline at the pub, say) is tried again by itself whenever the
// phone gets a connection and when the app starts, at most every ten minutes each:
// whichever way the night was listened to, its recording reaches the server.
//
// The CAF stays until the upload is confirmed; Delete removes a recording by hand.

import AVFoundation
import CeolLogic
import Foundation
import Network
import Observation

struct LocalRecording: Codable, Identifiable, Equatable {
    enum Phase: String, Codable {
        case recording, ready, converting, uploading, confirming, uploaded, failed
    }

    /// The file's base name.
    let id: String
    let instanceID: Int
    let title: String
    let startedAt: Date
    var endedAt: Date?
    var phase: Phase
    var storageKey: String?
    var recordingID: Int?
    var error: String?
    var uploadName: String?
    /// The meter log has reached the server.
    var meterLogSent: Bool?
}

@Observable
final class RecordingStore {
    private(set) var items: [LocalRecording] = []
    /// 0...1 per recording while its file goes up.
    private(set) var progress: [String: Double] = [:]

    @ObservationIgnored let dir: URL
    @ObservationIgnored private var uploads: UploadSession?
    @ObservationIgnored private weak var app: AppModel?
    @ObservationIgnored private var monitor: NWPathMonitor?
    @ObservationIgnored private var lastTried: [String: Date] = [:]
    static let retryEvery: TimeInterval = 600

    init() {
        let base = (try? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                                  appropriateFor: nil, create: true)) ?? FileManager.default.temporaryDirectory
        dir = base.appending(path: "Recordings")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        load()
    }

    func caf(_ r: LocalRecording) -> URL { dir.appending(path: "\(r.id).caf") }
    private func json(_ id: String) -> URL { dir.appending(path: "\(id).json") }
    /// What the meter showed while this was recorded (ListenWire.logLine).
    func meterLog(_ id: String) -> URL { dir.appending(path: "\(id).states.jsonl") }
    private func encoded(_ r: LocalRecording) -> URL? { r.uploadName.map { dir.appending(path: $0) } }

    var active: LocalRecording? { items.first { [.converting, .uploading, .confirming].contains($0.phase) } }

    /// Hours, minutes, seconds of a recording on disk.
    func duration(_ r: LocalRecording) -> TimeInterval {
        guard let f = try? AVAudioFile(forReading: caf(r)) else { return 0 }
        return Double(f.length) / f.fileFormat.sampleRate
    }

    func bytes(_ r: LocalRecording) -> Int {
        ((try? FileManager.default.attributesOfItem(atPath: caf(r).path))?[.size] as? Int) ?? 0
    }

    // MARK: - Keeping track

    /// A recording has begun: its JSON, beside the CAF the recorder writes.
    func begin(id: String, instanceID: Int, title: String) {
        save(LocalRecording(id: id, instanceID: instanceID, title: title, startedAt: Date(), phase: .recording))
    }

    func finish(id: String) {
        guard var r = items.first(where: { $0.id == id }) else { return }
        r.endedAt = Date()
        r.phase = .ready
        save(r)
    }

    func delete(_ r: LocalRecording) {
        for url in [caf(r), json(r.id), meterLog(r.id)] + [encoded(r)].compactMap({ $0 }) { try? FileManager.default.removeItem(at: url) }
        items.removeAll { $0.id == r.id }
    }

    private func save(_ r: LocalRecording) {
        if let i = items.firstIndex(where: { $0.id == r.id }) { items[i] = r } else { items.insert(r, at: 0) }
        if let data = try? JSONEncoder.iso.encode(r) { try? data.write(to: json(r.id), options: .atomic) }
    }

    private func load() {
        let files = (try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? []
        items = files.filter { $0.pathExtension == "json" }
            .compactMap { try? JSONDecoder.iso.decode(LocalRecording.self, from: Data(contentsOf: $0)) }
            .map { r in
                // Recording when the app went away: it isn't any more, and what's on disk is the night.
                var r = r
                if r.phase == .recording { r.phase = .ready }
                return r
            }
            .sorted { $0.startedAt > $1.startedAt }
    }

    // MARK: - Uploading

    /// Resume anything left half-way when the app last went away.
    func resume(app: AppModel) {
        self.app = app
        uploadSession()
        for r in items where r.phase == .uploading || r.phase == .confirming || r.phase == .converting {
            if r.phase == .confirming || (r.phase == .uploading && r.storageKey != nil) {
                Task { await confirm(r.id) }
            } else {
                Task { await upload(r.id) }
            }
        }
        for r in items where r.phase == .uploaded && r.meterLogSent != true {
            Task { await sendMeterLog(r.id) }
        }
        watchNetwork()
    }

    /// Whenever there is a connection (and at once, if there is one now), try again
    /// what didn't go up.
    private func watchNetwork() {
        guard monitor == nil else { return }
        let m = NWPathMonitor()
        m.pathUpdateHandler = { [weak self] path in
            guard path.status == .satisfied else { return }
            Task { @MainActor in self?.retryWaiting() }
        }
        m.start(queue: DispatchQueue(label: "io.ceol.recordings.network"))
        monitor = m
    }

    /// Recordings not uploaded (a failure, or a stop the app never got to upload),
    /// each at most every ten minutes.
    func retryWaiting() {
        guard let app, !app.simulatedOffline else { return }
        let now = Date()
        for r in items where r.phase == .failed || r.phase == .ready {
            if let t = lastTried[r.id], now.timeIntervalSince(t) < Self.retryEvery { continue }
            lastTried[r.id] = now
            Task { await upload(r.id) }
        }
    }

    func upload(_ id: String) async {
        guard var r = items.first(where: { $0.id == id }), let app else { return }
        lastTried[id] = Date()
        r.error = nil
        r.phase = .converting
        save(r)
        // 1. FLAC (or WAV), off the main thread
        let source = caf(r)
        let dir = self.dir
        let encodedURL: URL
        do {
            encodedURL = try await Task.detached { try AudioEncode.encode(source, into: dir, name: id) }.value
        } catch {
            return fail(id, "Couldn't prepare the file: \(error.localizedDescription)")
        }
        r.uploadName = encodedURL.lastPathComponent
        // 2. a signed upload
        let (status, body) = (try? await app.postJSON(
            "/api/recordings/upload-url",
            body: ["session_instance_id": .number(Double(r.instanceID)), "filename": .string(encodedURL.lastPathComponent)]))
            ?? (0, .null)
        guard status == 200, let put = body["upload_url"]?.stringValue.flatMap(URL.init(string:)),
            let key = body["storage_key"]?.stringValue, let type = body["content_type"]?.stringValue
        else {
            return fail(id, body["error"]?.stringValue ?? (status == 0 ? "Offline — try again later" : "The server refused the upload (\(status))"))
        }
        r.storageKey = key
        r.phase = .uploading
        save(r)
        progress[id] = 0
        // 3. the PUT, in the background session
        var request = URLRequest(url: put)
        request.httpMethod = "PUT"
        request.setValue(type, forHTTPHeaderField: "Content-Type")
        uploadSession().put(request, file: encodedURL, id: id)
    }

    /// The file is in S3: tell the server, which starts its ingest.
    func confirm(_ id: String) async {
        guard var r = items.first(where: { $0.id == id }), let key = r.storageKey, let app else { return }
        r.phase = .confirming
        save(r)
        progress[id] = nil
        var body: [String: JSONValue] = [
            "session_instance_id": .number(Double(r.instanceID)),
            "storage_key": .string(key),
            "label": .string("\(r.title) (Ceol app)"),
            "started_at": .string(ISO8601DateFormatter().string(from: r.startedAt)),
        ]
        let seconds = duration(r)
        if seconds > 0 { body["duration_ms"] = .number((seconds * 1000).rounded()) }
        let (status, reply) = (try? await app.postJSON("/api/recordings", body: .object(body))) ?? (0, .null)
        guard status == 201, let recordingID = reply["recording_id"]?.intValue else {
            if status == 400, reply["error"]?.stringValue?.contains("didn't finish") == true {
                // the object isn't there after all: upload again
                return await upload(id)
            }
            return fail(id, reply["error"]?.stringValue ?? (status == 0 ? "Offline — will finish later" : "The server said \(status)"))
        }
        r.recordingID = recordingID
        r.phase = .uploaded
        save(r)
        if let e = encoded(r) { try? FileManager.default.removeItem(at: e) }
        await sendMeterLog(id)
    }

    /// The meter log to the server, once the recording has its id there. A failure is
    /// left for the next start (resume); the recording itself is already safe.
    func sendMeterLog(_ id: String) async {
        guard var r = items.first(where: { $0.id == id }), let recordingID = r.recordingID, let app,
            !app.simulatedOffline,
            let data = try? Data(contentsOf: meterLog(id)), !data.isEmpty
        else { return }
        var request = app.authorized(URLRequest(url: app.webURL("/api/recordings/\(recordingID)/listen-log")))
        request.httpMethod = "PUT"
        request.timeoutInterval = 60
        request.setValue("application/x-ndjson", forHTTPHeaderField: "Content-Type")
        guard let (_, response) = try? await URLSession.shared.upload(for: request, from: data),
            (response as? HTTPURLResponse)?.statusCode == 200
        else { return }
        r.meterLogSent = true
        save(r)
    }

    fileprivate func uploaded(_ id: String, error: String?) {
        if let error { return fail(id, error) }
        Task { await confirm(id) }
    }

    fileprivate func progressed(_ id: String, _ p: Double) { progress[id] = p }

    private func fail(_ id: String, _ message: String) {
        guard var r = items.first(where: { $0.id == id }) else { return }
        r.phase = .failed
        r.error = message
        progress[id] = nil
        save(r)
    }

    @discardableResult
    private func uploadSession() -> UploadSession {
        if let uploads { return uploads }
        let s = UploadSession(
            onProgress: { [weak self] id, p in Task { @MainActor in self?.progressed(id, p) } },
            onDone: { [weak self] id, err in Task { @MainActor in self?.uploaded(id, error: err) } })
        uploads = s
        return s
    }
}

extension JSONEncoder {
    static var iso: JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        return e
    }
}

extension JSONDecoder {
    static var iso: JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }
}

// MARK: - The file, re-encoded for the server

nonisolated enum AudioEncode {
    /// The CAF as FLAC (lossless, about half the size), or WAV if this phone's encoder
    /// refuses: both are types the server takes.
    static func encode(_ source: URL, into dir: URL, name: String) throws -> URL {
        let input = try AVAudioFile(forReading: source, commonFormat: .pcmFormatInt16, interleaved: true)
        let format = input.processingFormat
        let flac = dir.appending(path: "\(name).flac")
        let wav = dir.appending(path: "\(name).wav")
        for url in [flac, wav] { try? FileManager.default.removeItem(at: url) }
        let out: AVAudioFile
        let url: URL
        do {
            out = try AVAudioFile(forWriting: flac,
                                  settings: [AVFormatIDKey: kAudioFormatFLAC, AVSampleRateKey: format.sampleRate,
                                             AVNumberOfChannelsKey: format.channelCount],
                                  commonFormat: .pcmFormatInt16, interleaved: true)
            url = flac
        } catch {
            out = try AVAudioFile(forWriting: wav, settings: format.settings, commonFormat: .pcmFormatInt16, interleaved: true)
            url = wav
        }
        let chunk: AVAudioFrameCount = 22050 * 30
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: chunk) else { throw CocoaError(.fileWriteUnknown) }
        while input.framePosition < input.length {
            try input.read(into: buffer, frameCount: min(chunk, AVAudioFrameCount(input.length - input.framePosition)))
            if buffer.frameLength == 0 { break }
            try out.write(from: buffer)
        }
        return url
    }
}

// MARK: - The background upload

/// One background URLSession for every recording's PUT, so an upload carries on with
/// the app in the background and reports back when it is next running.
nonisolated final class UploadSession: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    static let identifier = "io.ceol.Ceol.recording-upload"
    /// Set by the app delegate when the system wakes the app for this session.
    nonisolated(unsafe) static var systemCompletion: (() -> Void)?

    private var session: URLSession!
    private let onProgress: @Sendable (String, Double) -> Void
    private let onDone: @Sendable (String, String?) -> Void

    init(onProgress: @escaping @Sendable (String, Double) -> Void, onDone: @escaping @Sendable (String, String?) -> Void) {
        self.onProgress = onProgress
        self.onDone = onDone
        super.init()
        let config = URLSessionConfiguration.background(withIdentifier: Self.identifier)
        config.sessionSendsLaunchEvents = true
        config.isDiscretionary = false
        session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }

    func put(_ request: URLRequest, file: URL, id: String) {
        let task = session.uploadTask(with: request, fromFile: file)
        task.taskDescription = id
        task.resume()
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didSendBodyData _: Int64,
                    totalBytesSent sent: Int64, totalBytesExpectedToSend total: Int64) {
        guard let id = task.taskDescription, total > 0 else { return }
        onProgress(id, Double(sent) / Double(total))
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let id = task.taskDescription else { return }
        let status = (task.response as? HTTPURLResponse)?.statusCode ?? 0
        if let error {
            onDone(id, "Upload stopped: \(error.localizedDescription)")
        } else if !(200..<300).contains(status) {
            onDone(id, "S3 refused the upload (\(status))")
        } else {
            onDone(id, nil)
        }
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        DispatchQueue.main.async {
            UploadSession.systemCompletion?()
            UploadSession.systemCompletion = nil
        }
    }
}
