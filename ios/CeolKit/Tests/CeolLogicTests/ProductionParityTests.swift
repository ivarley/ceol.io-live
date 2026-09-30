// Real production nights order and split into sets exactly as the web's logstate.js does
// (opt-in: CEOL_PROD_SAMPLES, a folder from scripts/prod_parity/, with web_summary.json
// written by scripts/prod_parity/web_summary.mjs from the same files).

import Foundation
import Testing

@testable import CeolLogic

private let samples: URL? = ProcessInfo.processInfo.environment["CEOL_PROD_SAMPLES"].map { URL(fileURLWithPath: $0) }

private func nights() -> [URL] {
    guard let samples, let all = try? FileManager.default.contentsOfDirectory(at: samples, includingPropertiesForKeys: nil)
    else { return [] }
    return all.filter { $0.lastPathComponent.hasPrefix("night_") }.sorted { $0.path < $1.path }
}

@Suite("production nights match the web", .enabled(if: samples != nil))
struct ProductionParityTests {
    @Test("order, sets, set labels, and the live log's view", arguments: nights())
    func night(_ f: URL) throws {
        let b = try JSONDecoder().decode(JSONValue.self, from: Data(contentsOf: f))
        let summary = try JSONDecoder().decode(JSONValue.self, from: Data(contentsOf: samples!.appending(path: "web_summary.json")))
        let id = try #require(b["session_instance_id"]?.intValue)
        let web = try #require(summary[String(id)])
        let records = b["records"]?.arrayValue ?? []
        let ordered = LogState.computeOrdered(records)
        let segs = LogState.segmentByBreaks(ordered)
        #expect(.array(ordered.map { $0["session_instance_tune_id"] ?? .null }) == web["ordered"], "night \(id): order")
        #expect(.array(segs.map { .array($0.tunes.map { $0["session_instance_tune_id"] ?? .null }) }) == web["sets"], "night \(id): sets")
        #expect(.array(segs.map { $0.breakAfter?.json ?? .null }) == web["breakAfter"], "night \(id): breaks")
        #expect(.array(segs.map { .string(LogState.setLabel($0.tunes)) }) == web["labels"], "night \(id): labels")
        // The live log, built as the app builds it, shows the same.
        let log = LiveLog(records: records, lastEventID: b["last_event_id"]?.intValue ?? 0)
        #expect(log.ordered.map(\.recordID) == ordered.map(\.recordID), "night \(id): the live log")
        // And it survives the phone's save-and-restore (5d).
        let back = try JSONDecoder().decode(LiveLog.self, from: JSONEncoder().encode(log))
        #expect(back == log, "night \(id): saved and restored")
    }
}
