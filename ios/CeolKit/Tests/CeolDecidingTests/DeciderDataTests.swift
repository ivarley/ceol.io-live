// Fetching a newer decider file: when one is wanted, and installing it only once it is
// the file offered and opens.

import Foundation
import Testing

@testable import CeolDeciding

@Suite("Keeping the decider's data current")
struct DeciderDataTests {
    func scratch() throws -> URL {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("decider-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    @Test("A newer file is wanted, the same or an older one not", .enabled(if: corpus != nil))
    func wanted() {
        let c = corpus!
        #expect(DeciderData.wanted(builtAt: "2026-10-12T07:16:00Z", current: nil))
        #expect(DeciderData.wanted(builtAt: "2099-01-01T00:00:00Z", current: c))
        #expect(!DeciderData.wanted(builtAt: c.builtAt, current: c))
        #expect(!DeciderData.wanted(builtAt: "2020-01-01T00:00:00Z", current: c))
    }

    @Test("Installed only when it is the file offered", .enabled(if: corpusURL != nil))
    func install() throws {
        let dir = try scratch()
        defer { try? FileManager.default.removeItem(at: dir) }
        let dest = dir.appendingPathComponent("installed/decider-v1.bin")
        let sha = try DeciderData.sha256(of: corpusURL!)
        let bytes = (try FileManager.default.attributesOfItem(atPath: corpusURL!.path)[.size] as! NSNumber).intValue

        // the wrong checksum, the wrong size: nothing installed
        let a = dir.appendingPathComponent("a.bin")
        try FileManager.default.copyItem(at: corpusURL!, to: a)
        #expect(throws: DeciderDataError.self) {
            try DeciderData.install(a, sha256: String(repeating: "0", count: 64), bytes: bytes, at: dest)
        }
        #expect(throws: DeciderDataError.self) { try DeciderData.install(a, sha256: sha, bytes: bytes + 1, at: dest) }
        #expect(!FileManager.default.fileExists(atPath: dest.path))

        // not a decider file, though it is what was offered
        let junk = dir.appendingPathComponent("junk.bin")
        try Data(repeating: 7, count: 4096).write(to: junk)
        #expect(throws: CorpusError.self) {
            try DeciderData.install(junk, sha256: try DeciderData.sha256(of: junk), bytes: 4096, at: dest)
        }

        // the real thing, then again over it (a week later)
        let got = try DeciderData.install(a, sha256: sha, bytes: bytes, at: dest)
        #expect(got.tuneCount == corpus!.tuneCount)
        let b = dir.appendingPathComponent("b.bin")
        try FileManager.default.copyItem(at: corpusURL!, to: b)
        let held = got                                  // a night still listening with the old one
        try DeciderData.install(b, sha256: sha, bytes: bytes, at: dest)
        #expect(held.name(of: held.tuneID(at: 0)) != nil)
        #expect(try DeciderData.sha256(of: dest) == sha)
    }
}
