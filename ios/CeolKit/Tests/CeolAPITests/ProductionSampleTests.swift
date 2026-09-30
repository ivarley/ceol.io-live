// Real production responses decode into the generated types (opt-in: set
// CEOL_PROD_SAMPLES to a folder written by scripts/prod_parity/capture.py, which reads
// production signed out and writes nothing). The committed fixtures prove the contract
// on seed data; this proves it on whatever real sessions have in them.

import Foundation
import Testing

@testable import CeolAPI

private let samples: URL? = ProcessInfo.processInfo.environment["CEOL_PROD_SAMPLES"].map { URL(fileURLWithPath: $0) }

private func files(_ prefix: String) -> [URL] {
    guard let samples, let all = try? FileManager.default.contentsOfDirectory(at: samples, includingPropertiesForKeys: nil)
    else { return [] }
    return all.filter { $0.lastPathComponent.hasPrefix(prefix) }.sorted { $0.path < $1.path }
}

@Suite("production samples decode", .enabled(if: samples != nil))
struct ProductionSampleTests {
    @Test("the sessions list") func sessions() throws {
        for f in files("sessions") { _ = try JSONDecoder().decode(Components.Schemas.SessionsDirectory.self, from: Data(contentsOf: f)) }
    }

    @Test("each session's nights", arguments: files("logs_"))
    func logs(_ f: URL) throws {
        _ = try JSONDecoder().decode(Components.Schemas.SessionLogs.self, from: Data(contentsOf: f))
    }

    @Test("each night's log", arguments: files("night_"))
    func night(_ f: URL) throws {
        _ = try JSONDecoder().decode(Components.Schemas.LiveBootstrap.self, from: Data(contentsOf: f))
    }
}
