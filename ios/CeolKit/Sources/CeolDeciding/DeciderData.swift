// Keeping the decider's data current (spec 053, "Listening on the phone, offline").
// The file is rebuilt every week from thesession.org's dump and published
// (services/decider_data_service.py); GET /api/listen/decider-data offers the newest in
// this format with a short-lived link. The app fetches it when it has a connection and
// installs it here, in Application Support, only once it is whole, is the file offered
// (its SHA-256) and opens as a decider file. A night already listening keeps the file it
// started with: the old one stays mapped until that night lets it go.

import CryptoKit
import Foundation

public enum DeciderDataError: Error, CustomStringConvertible {
    case wrongSize(Int, Int)
    case wrongChecksum

    public var description: String {
        switch self {
        case .wrongSize(let got, let want): "the download is \(got) bytes, not \(want)"
        case .wrongChecksum: "the download is not the file offered (SHA-256)"
        }
    }
}

public enum DeciderData {
    /// Where a fetched file goes.
    public static var fetchedURL: URL? {
        try? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil,
                                     create: false)
            .appendingPathComponent("CeolDeciding/decider-v\(Corpus.version).bin")
    }

    /// Whether a file offered as built at `builtAt` is worth fetching: there is no file
    /// here, or it is newer than the one there is.
    public static func wanted(builtAt offered: String, current: Corpus?) -> Bool {
        guard let current else { return true }
        return offered > current.builtAt
    }

    /// Check a downloaded file against what was offered, then put it in place of any
    /// earlier one. Returns it opened.
    @discardableResult
    public static func install(_ downloaded: URL, sha256: String, bytes: Int?, at dest: URL? = nil) throws -> Corpus {
        let fm = FileManager.default
        if let bytes {
            let size = (try fm.attributesOfItem(atPath: downloaded.path)[.size] as? NSNumber)?.intValue ?? -1
            guard size == bytes else { throw DeciderDataError.wrongSize(size, bytes) }
        }
        guard try Self.sha256(of: downloaded) == sha256.lowercased() else { throw DeciderDataError.wrongChecksum }
        _ = try Corpus(contentsOf: downloaded)          // a decider file this app reads
        guard let dest = dest ?? fetchedURL else { throw CocoaError(.fileNoSuchFile) }
        try fm.createDirectory(at: dest.deletingLastPathComponent(), withIntermediateDirectories: true)
        if fm.fileExists(atPath: dest.path) {
            _ = try fm.replaceItemAt(dest, withItemAt: downloaded)
        } else {
            try fm.moveItem(at: downloaded, to: dest)
        }
        var url = dest
        var values = URLResourceValues()
        values.isExcludedFromBackup = true             // fetched again if lost
        try? url.setResourceValues(values)
        return try Corpus(contentsOf: dest)
    }

    static func sha256(of url: URL) throws -> String {
        let h = try FileHandle(forReadingFrom: url)
        defer { try? h.close() }
        var hasher = SHA256()
        while let chunk = try h.read(upToCount: 1 << 20), !chunk.isEmpty { hasher.update(data: chunk) }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}
