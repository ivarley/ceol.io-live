import AVFoundation
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
