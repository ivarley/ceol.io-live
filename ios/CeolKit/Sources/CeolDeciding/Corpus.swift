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
    public static let version = 1
    static let sections = ["meta", "tune_ids", "gram_count", "gram_keys", "post_off", "postings", "repertoire",
                           "set_off", "seq_off", "symbols", "name_off", "names", "type_off", "types"]

    /// The file's configuration and provenance (its "meta" section).
    public let meta: [String: Any]
    /// n-gram length, and the number of tunes the corpus's idf counts.
    public let n: Int
    public let nTunes: Int
    public let tuneCount: Int
    public let gramCount: Int
    /// The default session's tunes, by tune id (the lab's repertoire index).
    public let defaultRepertoire: [Int]

    let tuneIDs: UnsafePointer<Int32>
    let tuneGramCount: UnsafePointer<Int32>
    let gramKeys: UnsafePointer<UInt32>
    let postOff: UnsafePointer<UInt32>
    let postings: UnsafePointer<UInt16>
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
            let rep = try section("repertoire", UInt16.self)
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
            defaultRepertoire = (0..<at["repertoire"]!.count).map { Int(ids[Int(rep[$0])]) }
        } catch {
            munmap(p, len)
            throw error
        }
    }

    deinit { munmap(base, length) }

    /// Where the app finds the file: a copy fetched since (Application Support/CeolDeciding),
    /// else the one it was built with (Data/decider-v1.bin), else none, and the phone
    /// decides on Ceol's server.
    public static var shipped: URL? {
        let name = "decider-v\(version).bin"
        let fm = FileManager.default
        if let support = try? fm.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil,
                                     create: false) {
            let fetched = support.appendingPathComponent("CeolDeciding/\(name)")
            if fm.fileExists(atPath: fetched.path) { return fetched }
        }
        return Bundle.module.url(forResource: name, withExtension: nil, subdirectory: "Data")
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

/// A session's tunes: the lab's repertoire index, as a restriction of the whole
/// corpus's. Its idf counts only these tunes, as an index built from them would.
public struct Repertoire: Sendable {
    public let tuneIDs: Set<Int>
    /// The tunes the idf divides by (the repertoire index's `n_tunes`).
    let size: Int
    /// By tune position: in the repertoire.
    let member: [Bool]
    /// By n-gram: how many of these tunes hold it.
    let df: [UInt16]

    public init(_ tuneIDs: some Sequence<Int>, in corpus: Corpus) {
        var member = [Bool](repeating: false, count: corpus.tuneCount)
        var ids = Set<Int>()
        for t in tuneIDs {
            ids.insert(t)
            if let i = corpus.index(of: t) { member[i] = true }
        }
        var df = [UInt16](repeating: 0, count: corpus.gramCount)
        for g in 0..<corpus.gramCount {
            var c = 0
            for t in corpus.tunes(holding: g) where member[Int(t)] { c += 1 }
            df[g] = UInt16(clamping: c)
        }
        self.tuneIDs = ids
        self.size = ids.count
        self.member = member
        self.df = df
    }
}
