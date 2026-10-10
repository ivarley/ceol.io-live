// The decider's data (spec 053, "Listening on the phone, offline"): the whole corpus's
// n-gram index, every setting's notes for the aligner, the tunes' names, and the
// configuration, in one file the lab writes (`python -m lab decider export`,
// lab/tools/decider.py, which documents the layout). Mapped, not read: the pages are
// the kernel's to drop and fetch again, so the corpus costs the app little memory.

import Foundation

public enum CorpusError: Error, CustomStringConvertible {
    case unreadable(String)
    case notADecider(String)

    public var description: String {
        switch self {
        case .unreadable(let why): "the decider's data could not be read: \(why)"
        case .notADecider(let why): "not the decider's data: \(why)"
        }
    }
}

public final class Corpus: @unchecked Sendable {
    public static let version = 2
    static let sections = ["meta", "tune_ids", "gram_count", "gram_keys", "post_off", "postings", "popular",
                           "rounds", "set_off", "seq_off", "symbols", "name_off", "names", "type_off", "types"]

    /// The file's configuration and provenance (its "meta" section).
    public let meta: [String: Any]
    /// n-gram length, and the number of tunes the corpus's idf counts.
    public let n: Int
    public let nTunes: Int
    public let tuneCount: Int
    public let gramCount: Int
    /// thesession.org's popular tunes (at least 100 tunebooks), by tune id: a session's
    /// second tier, and its first when its own are not known.
    public let popular: Set<Int>

    let tuneIDs: UnsafePointer<Int32>
    let tuneGramCount: UnsafePointer<Int32>
    let gramKeys: UnsafePointer<UInt32>
    let postOff: UnsafePointer<UInt32>
    let postings: UnsafePointer<UInt16>
    let rounds: UnsafePointer<Float32>
    let setOff: UnsafePointer<UInt32>
    let seqOff: UnsafePointer<UInt32>
    let symbols: UnsafePointer<Int8>
    private let nameOff: UnsafePointer<UInt32>
    private let names: UnsafePointer<UInt8>
    private let typeOff: UnsafePointer<UInt32>
    private let types: UnsafePointer<UInt8>

    private let base: UnsafeMutableRawPointer
    private let length: Int

    public init(contentsOf url: URL) throws {
        let fd = open(url.path, O_RDONLY)
        guard fd >= 0 else { throw CorpusError.unreadable("\(url.lastPathComponent): \(String(cString: strerror(errno)))") }
        defer { close(fd) }
        var st = stat()
        guard fstat(fd, &st) == 0, st.st_size > 16 else { throw CorpusError.unreadable("\(url.lastPathComponent): empty") }
        length = Int(st.st_size)
        guard let p = mmap(nil, length, PROT_READ, MAP_PRIVATE, fd, 0), p != MAP_FAILED else {
            throw CorpusError.unreadable("mmap: \(String(cString: strerror(errno)))")
        }
        base = p
        let raw = UnsafeRawPointer(p)
        guard length > 16, String(decoding: UnsafeRawBufferPointer(start: raw, count: 8), as: UTF8.self) == "CEOLDEC1"
        else { munmap(p, length); throw CorpusError.notADecider("no CEOLDEC1 header") }
        let version = Int(raw.loadUnaligned(fromByteOffset: 8, as: UInt32.self))
        let count = Int(raw.loadUnaligned(fromByteOffset: 12, as: UInt32.self))
        guard version == Self.version, count == Self.sections.count, 16 + 16 * count <= length else {
            munmap(p, length)
            throw CorpusError.notADecider("version \(version) with \(count) sections; this app reads version \(Self.version)")
        }
        var at = [String: (offset: Int, count: Int)]()
        for (i, name) in Self.sections.enumerated() {
            let o = Int(raw.loadUnaligned(fromByteOffset: 16 + 16 * i, as: UInt64.self))
            let c = Int(raw.loadUnaligned(fromByteOffset: 24 + 16 * i, as: UInt64.self))
            at[name] = (o, c)
        }
        let len = length
        func section<T>(_ name: String, _: T.Type) throws -> UnsafePointer<T> {
            let (o, c) = at[name]!
            guard o % MemoryLayout<T>.alignment == 0, o + c * MemoryLayout<T>.stride <= len else {
                throw CorpusError.notADecider("section \(name) out of bounds")
            }
            return raw.advanced(by: o).assumingMemoryBound(to: T.self)
        }
        do {
            let m = at["meta"]!
            guard m.offset + m.count <= len,
                let meta = try JSONSerialization.jsonObject(with: Data(bytes: raw.advanced(by: m.offset), count: m.count))
                    as? [String: Any]
            else { throw CorpusError.notADecider("meta is not an object") }
            let ids = try section("tune_ids", Int32.self)
            let pop = try section("popular", UInt16.self)
            rounds = try section("rounds", Float32.self)
            tuneGramCount = try section("gram_count", Int32.self)
            gramKeys = try section("gram_keys", UInt32.self)
            postOff = try section("post_off", UInt32.self)
            postings = try section("postings", UInt16.self)
            setOff = try section("set_off", UInt32.self)
            seqOff = try section("seq_off", UInt32.self)
            symbols = try section("symbols", Int8.self)
            nameOff = try section("name_off", UInt32.self)
            names = try section("names", UInt8.self)
            typeOff = try section("type_off", UInt32.self)
            types = try section("types", UInt8.self)
            tuneIDs = ids
            self.meta = meta
            n = meta["n"] as? Int ?? 6
            nTunes = meta["n_tunes"] as? Int ?? 0
            tuneCount = at["tune_ids"]!.count
            gramCount = at["gram_keys"]!.count
            popular = Set((0..<at["popular"]!.count).map { Int(ids[Int(pop[$0])]) })
        } catch {
            munmap(p, len)
            throw error
        }
    }

    deinit { munmap(base, length) }

    /// When the lab built it, UTC ("YYYY-MM-DDTHH:MM:SSZ"; the lab's older files say
    /// local time without the Z). Newer files sort later.
    public var builtAt: String { meta["built_at"] as? String ?? "" }

    /// The copy the app was built with (Data/decider-v2.bin), if any.
    public static var bundled: URL? {
        Bundle.module.url(forResource: "decider-v\(version)", withExtension: "bin", subdirectory: "Data")
    }

    /// Where the app finds the file: whichever is newer of a copy fetched since
    /// (DeciderData.fetchedURL) and the one it was built with; none, and the phone
    /// decides on Ceol's server.
    public static var shipped: URL? {
        let found = [DeciderData.fetchedURL, bundled].compactMap { url -> (URL, String)? in
            guard let url, FileManager.default.fileExists(atPath: url.path),
                let c = try? Corpus(contentsOf: url) else { return nil }
            return (url, c.builtAt)
        }
        return found.max { $0.1 < $1.1 }?.0
    }

    /// The file's size: what it costs on disk, and at most what it maps.
    public var byteCount: Int { length }

    // MARK: Tunes

    /// A tune id's position in the corpus, if it is there.
    public func index(of tuneID: Int) -> Int? {
        var lo = 0, hi = tuneCount
        while lo < hi {
            let mid = (lo + hi) / 2
            if Int(tuneIDs[mid]) < tuneID { lo = mid + 1 } else { hi = mid }
        }
        return lo < tuneCount && Int(tuneIDs[lo]) == tuneID ? lo : nil
    }

    public func tuneID(at i: Int) -> Int { Int(tuneIDs[i]) }

    public func name(of tuneID: Int) -> String? { index(of: tuneID).flatMap { string(names, nameOff, $0) } }

    public func type(of tuneID: Int) -> String? { index(of: tuneID).flatMap { string(types, typeOff, $0) } }

    /// Eighths in one time through a tune as played (the median over its settings), or
    /// nil if none could be read (lab: analysis.form.RoundLengths).
    public func roundLength(of tuneID: Int) -> Double? {
        guard let i = index(of: tuneID) else { return nil }
        let v = Double(rounds[i])
        return v > 0 ? v : nil
    }

    /// How many settings the aligner holds for a tune.
    public func settingCount(of tuneID: Int) -> Int {
        guard let i = index(of: tuneID) else { return 0 }
        return Int(setOff[i + 1]) - Int(setOff[i])
    }

    private func string(_ bytes: UnsafePointer<UInt8>, _ off: UnsafePointer<UInt32>, _ i: Int) -> String? {
        let a = Int(off[i]), b = Int(off[i + 1])
        return b > a ? String(decoding: UnsafeBufferPointer(start: bytes + a, count: b - a), as: UTF8.self) : nil
    }

    // MARK: n-grams

    /// An n-gram's position in the index, if any tune has it.
    func gram(_ key: UInt32) -> Int? {
        var lo = 0, hi = gramCount
        while lo < hi {
            let mid = (lo + hi) / 2
            if gramKeys[mid] < key { lo = mid + 1 } else { hi = mid }
        }
        return lo < gramCount && gramKeys[lo] == key ? lo : nil
    }

    /// The tunes (by position) holding an n-gram.
    func tunes(holding g: Int) -> UnsafeBufferPointer<UInt16> {
        let a = Int(postOff[g]), b = Int(postOff[g + 1])
        return UnsafeBufferPointer(start: postings + a, count: b - a)
    }
}

/// A set of tunes to shortlist among, as the corpus's positions.
public struct TuneSet: Sendable {
    public let tuneIDs: Set<Int>
    /// By tune position: in the set.
    let member: [Bool]

    public init(_ tuneIDs: some Sequence<Int>, in corpus: Corpus) {
        var member = [Bool](repeating: false, count: corpus.tuneCount)
        let ids = Set(tuneIDs)
        for t in ids { if let i = corpus.index(of: t) { member[i] = true } }
        self.tuneIDs = ids
        self.member = member
    }

    public func contains(_ tuneID: Int) -> Bool { tuneIDs.contains(tuneID) }
    public var isEmpty: Bool { tuneIDs.isEmpty }
}
