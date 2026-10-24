import AVFoundation
import CeolSession
import Foundation
import Testing
@testable import Ceol

/// The recorder's file on its way to the server (RecordingStore, AudioEncode): the CAF
/// the recorder writes becomes a FLAC the server accepts, with every sample.
struct RecordingTests {
    @Test func aRecordingIsEncodedForUploadWithEverySample() throws {
        let dir = FileManager.default.temporaryDirectory.appending(path: "rec-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let format = try #require(AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 22050, channels: 1, interleaved: true))
        let caf = dir.appending(path: "night.caf")
        let frames: AVAudioFrameCount = 22050 * 3 + 123
        do {
            let file = try AVAudioFile(forWriting: caf, settings: format.settings, commonFormat: .pcmFormatInt16, interleaved: true)
            let buffer = try #require(AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames))
            buffer.frameLength = frames
            let s = try #require(buffer.int16ChannelData?[0])
            for i in 0..<Int(frames) { s[i] = Int16(8000 * sin(Double(i) * 2 * .pi * 440 / 22050)) }
            try file.write(from: buffer)
        }
        let out = try AudioEncode.encode(caf, into: dir, name: "night")
        #expect(["flac", "wav"].contains(out.pathExtension))
        let back = try AVAudioFile(forReading: out, commonFormat: .pcmFormatInt16, interleaved: true)
        #expect(back.length == AVAudioFramePosition(frames))
        #expect(back.fileFormat.sampleRate == 22050)
        let original = try AVAudioFile(forReading: caf, commonFormat: .pcmFormatInt16, interleaved: true)
        let x = try Self.samples(original), y = try Self.samples(back)
        #expect(x.count == Int(frames) && y.count == Int(frames))
        #expect(x == y, "lossless")
        print("encoded as \(out.pathExtension): \(try FileManager.default.attributesOfItem(atPath: out.path)[.size] ?? 0) bytes against \(try FileManager.default.attributesOfItem(atPath: caf.path)[.size] ?? 0)")
    }

    /// The meter log is appended to, never replaced: a log reopened after a relaunch
    /// keeps what came before, one JSON object per line.
    @Test func theMeterLogAppendsAcrossAReopen() throws {
        let url = FileManager.default.temporaryDirectory.appending(path: "meter-\(UUID().uuidString).jsonl")
        defer { try? FileManager.default.removeItem(at: url) }
        let first = MeterLog(url: url, since: Date())
        first.write("in", #"{"type":"state","t_ms":4000}"#)
        first.close()
        let second = MeterLog(url: url, since: Date())
        second.write("out", #"{"type":"tap","action":"none","shown":[91]}"#)
        second.close()
        let lines = try String(contentsOf: url, encoding: .utf8).split(separator: "\n")
        #expect(lines.count == 2)
        let dirs = try lines.map { try #require(JSONSerialization.jsonObject(with: Data($0.utf8)) as? [String: Any])["dir"] as? String }
        #expect(dirs == ["in", "out"])
    }

    /// Every sample of a file. A compressed file can hand back fewer frames per read than
    /// asked for (FLAC: 65,536), so read until there are no more.
    static func samples(_ file: AVAudioFile) throws -> [Int16] {
        var out: [Int16] = []
        let buffer = try #require(AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: 32768))
        while file.framePosition < file.length {
            try file.read(into: buffer)
            if buffer.frameLength == 0 { break }
            let ch = try #require(buffer.int16ChannelData?[0])
            out.append(contentsOf: UnsafeBufferPointer(start: ch, count: Int(buffer.frameLength)))
        }
        return out
    }
}

/// "Upload the recording to Ceol" off: the recording is kept on the phone, says so, and
/// nothing uploads it by itself.
@MainActor
struct KeepOnPhoneTests {
    @Test func aRecordingKeptOnThePhoneSaysSo() {
        let store = RecordingStore()
        let id = "test-keep-\(UUID().uuidString)"
        store.begin(id: id, instanceID: 1, title: "A night")
        store.finish(id: id, keepOnPhone: true)
        let r = store.items.first { $0.id == id }
        #expect(r?.keepOnPhone == true)
        #expect(r?.phase == .ready)
        #expect(r?.statusText == "Kept on this phone")
        store.finish(id: id, keepOnPhone: false)
        #expect(store.items.first { $0.id == id }?.statusText == "Not uploaded yet")
        if let r = store.items.first(where: { $0.id == id }) { store.delete(r) }
    }
}

/// An upload stopped part-way (the bar's ×, or Cancel upload in the list): the
/// recording is kept on the phone, nothing retries it, and the file being prepared
/// for the server is gone.
@MainActor
struct CancelUploadTests {
    @Test func cancellingWhileTheFileIsPreparedKeepsTheRecording() async throws {
        let app = AppModel(server: URL(string: "http://127.0.0.1:9")!, store: MemoryTokenStore())
        let store = app.recordings
        store.resume(app: app)
        let id = "test-cancel-\(UUID().uuidString)"
        store.begin(id: id, instanceID: 1, title: "A night")
        // Something for the encoder to chew on: a few seconds of tone.
        let format = try #require(AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 22050, channels: 1, interleaved: true))
        let r0 = try #require(store.items.first { $0.id == id })
        do {
            let file = try AVAudioFile(forWriting: store.caf(r0), settings: format.settings, commonFormat: .pcmFormatInt16, interleaved: true)
            let frames: AVAudioFrameCount = 22050 * 5
            let buffer = try #require(AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames))
            buffer.frameLength = frames
            try file.write(from: buffer)
        }
        store.finish(id: id, keepOnPhone: true)
        defer { if let r = store.items.first(where: { $0.id == id }) { store.delete(r) } }

        let upload = Task { await store.upload(id) }
        // upload() marks the recording converting before its first await
        for _ in 0..<200 where store.items.first(where: { $0.id == id })?.phase != .converting { await Task.yield() }
        #expect(store.items.first { $0.id == id }?.phase == .converting)
        #expect(RecordingStore.cancellable(try #require(store.items.first { $0.id == id })))
        store.cancel(id)
        await upload.value

        let r = try #require(store.items.first { $0.id == id })
        #expect(r.phase == .ready)
        #expect(r.keepOnPhone == true)
        #expect(r.error == nil)
        #expect(r.uploadName == nil)
        #expect(store.progress[id] == nil)
        #expect(store.active == nil)
        #expect(!RecordingStore.cancellable(r))
        for ext in ["flac", "wav"] {
            #expect(!FileManager.default.fileExists(atPath: store.dir.appending(path: "\(id).\(ext)").path), Comment(rawValue: ext))
        }
    }

    /// The encoder stops when its task is cancelled, rather than finishing the file.
    @Test func theEncoderHonoursCancellation() async throws {
        let dir = FileManager.default.temporaryDirectory.appending(path: "rec-cancel-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let format = try #require(AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 22050, channels: 1, interleaved: true))
        let caf = dir.appending(path: "night.caf")
        do {
            let file = try AVAudioFile(forWriting: caf, settings: format.settings, commonFormat: .pcmFormatInt16, interleaved: true)
            let frames: AVAudioFrameCount = 22050 * 60
            let buffer = try #require(AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames))
            buffer.frameLength = frames
            try file.write(from: buffer)
        }
        let encode = Task.detached { try AudioEncode.encode(caf, into: dir, name: "night") }
        encode.cancel()
        await #expect(throws: CancellationError.self) { try await encode.value }
    }
}

/// A recording made just listening is given a night after the fact ("Attach to a
/// night"): named for it, ready, and left for Upload to send.
@MainActor
struct AttachNightTests {
    @Test func attachingANightReadiesTheRecording() {
        let store = RecordingStore()
        let id = "test-attach-\(UUID().uuidString)"
        store.begin(id: id, instanceID: nil, title: "Listening")
        store.finish(id: id, keepOnPhone: true)
        defer { if let r = store.items.first(where: { $0.id == id }) { store.delete(r) } }
        store.attach(id, instanceID: 42, title: "Mueller Session · Jan 27")
        let r = store.items.first { $0.id == id }
        #expect(r?.instanceID == 42)
        #expect(r?.title == "Mueller Session · Jan 27")
        #expect(r?.phase == .ready)
        #expect(r?.keepOnPhone == true, "left for Upload, not sent by itself")
    }

    /// One that failed for want of a night is ready again once it has one.
    @Test func attachingClearsAFailureForWantOfANight() {
        let store = RecordingStore()
        let id = "test-attach-failed-\(UUID().uuidString)"
        store.begin(id: id, instanceID: nil, title: "Listening")
        store.finish(id: id, keepOnPhone: false)
        defer { if let r = store.items.first(where: { $0.id == id }) { store.delete(r) } }
        store.attach(id, instanceID: 7, title: "A night")
        #expect(store.items.first { $0.id == id }?.phase == .ready)
        #expect(store.items.first { $0.id == id }?.error == nil)
    }
}

/// Hearing a recording on the phone (RecordingPlayer): ▶ plays the file, says how
/// long it is and where it has got to; ▶ again pauses; another recording takes over.
@MainActor
struct RecordingPlayerTests {
    @Test func playsPausesAndSwitches() async throws {
        let dir = FileManager.default.temporaryDirectory.appending(path: "play-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let format = try #require(AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 22050, channels: 1, interleaved: true))
        func write(_ name: String, seconds: Int) throws -> URL {
            let url = dir.appending(path: "\(name).caf")
            let file = try AVAudioFile(forWriting: url, settings: format.settings, commonFormat: .pcmFormatInt16, interleaved: true)
            let frames = AVAudioFrameCount(22050 * seconds)
            let buffer = try #require(AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames))
            buffer.frameLength = frames
            try file.write(from: buffer)
            return url
        }
        let a = try write("a", seconds: 3), b = try write("b", seconds: 5)
        let player = RecordingPlayer()
        #expect(player.current == nil)
        player.toggle("a", file: a)
        #expect(player.current == "a")
        #expect(player.playing)
        #expect(abs(player.duration - 3) < 0.1)
        player.toggle("a", file: a)
        #expect(!player.playing, "▶ again pauses")
        #expect(player.current == "a")
        player.seek(2)
        #expect(abs(player.position - 2) < 0.1)
        player.toggle("b", file: b)
        #expect(player.current == "b")
        #expect(player.playing)
        #expect(abs(player.duration - 5) < 0.1)
        player.stop()
        #expect(player.current == nil)
        #expect(!player.playing)
    }
}
