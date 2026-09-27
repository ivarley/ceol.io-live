// Fractional indexing — a port of frontend/src/fracindex.js (itself a port of
// fractional_indexing.py), for provisional order_position keys: a mid-list insert
// renders in the right place before the server's authoritative position arrives.
// Base-62, byte order (COLLATE "C"): 0-9 < A-Z < a-z.
//
// Keys are ASCII, so they are handled as arrays of UTF-8 bytes: byte order, UTF-16
// order and code-point order all agree, and indexing is O(1). Cases and the rules a
// port must keep: frontend/src/fracindex.fixtures.json.

public enum FracIndex {
    public struct NoPosition: Error, CustomStringConvertible {
        public let description: String
    }

    static let alphabet = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz".utf8)
    static let base = alphabet.count  // 62
    static let midpoint = base / 2  // 31 -> 'V'
    static let start = "V"

    /// ALPHABET.indexOf(c): -1 for a character outside the alphabet.
    static func ci(_ c: UInt8) -> Int { alphabet.firstIndex(of: c) ?? -1 }
    static func ic(_ i: Int) -> UInt8 { alphabet[i] }

    /// A key after `last` (nil or empty: the first key).
    public static func generateAppend(_ last: String?) -> String {
        guard let last, !last.isEmpty else { return start }
        var bytes = Array(last.utf8)
        let v = ci(bytes[bytes.count - 1])
        if v < base - 1 {
            bytes[bytes.count - 1] = ic(v + 1)
            return string(bytes)
        }
        return string(bytes + [ic(midpoint)])
    }

    static func generateBefore(_ after: [UInt8]) throws -> [UInt8] {
        if after.isEmpty { return [ic(midpoint)] }
        let first = ci(after[0])
        if first > 1 { return [ic(first / 2)] }
        if first == 1 { return [alphabet[0]] + (try generateBefore(Array(after.dropFirst()))) }
        if after.count > 1 { return [alphabet[0]] + (try generateBefore(Array(after.dropFirst()))) }
        throw NoPosition(description: "no position below a key of only 0s")
    }

    static func midpoint(_ before: [UInt8], _ after: [UInt8]) throws -> [UInt8] {
        if after.starts(with: before) && after.count > before.count {
            return before + (try generateBefore(Array(after[before.count...])))
        }
        let maxLen = max(before.count, after.count)
        let b = before + Array(repeating: alphabet[0], count: maxLen - before.count)
        let a = after + Array(repeating: alphabet[0], count: maxLen - after.count)
        var i = 0
        while i < maxLen && b[i] == a[i] { i += 1 }
        if i == maxLen {
            throw NoPosition(description: "positions equal: \(string(before)) \(string(after))")
        }
        let bv = ci(b[i])
        let av = ci(a[i])
        if av - bv > 1 { return Array(b[..<i]) + [ic(floorDiv(bv + av, 2))] }
        if before.count > i { return before + [ic(midpoint)] }
        return Array(b[...i]) + [ic(midpoint)]
    }

    /// A key strictly between `before` and `after` (either nil or empty for the start
    /// or end). Throws where none exists: before >= after, or an `after` that is
    /// `before` followed only by '0's — exactly where the Python raises.
    public static func generateBetween(_ before: String?, _ after: String?) throws -> String {
        let b = before.map { Array($0.utf8) } ?? []
        let a = after.map { Array($0.utf8) } ?? []
        if b.isEmpty && a.isEmpty { return start }
        if b.isEmpty {
            let fv = ci(a[0])
            if fv > 0 {
                let mid = fv / 2
                if mid > 0 { return string([ic(mid)]) }
                return string([alphabet[0], ic(midpoint)])
            }
            if a.count == 1 { throw NoPosition(description: "no position below a key of only 0s") }
            return "0" + (try generateBetween(nil, string(Array(a.dropFirst()))))
        }
        if a.isEmpty { return generateAppend(before) }
        if !b.lexicographicallyPrecedes(a) {
            throw NoPosition(description: "invalid ordering: \(string(b)) >= \(string(a))")
        }
        return string(try midpoint(b, a))
    }

    /// generateBetween for a provisional client key: where no key lies between the
    /// neighbours, append after `before` instead of throwing. The server, which is
    /// authoritative, refuses the same request.
    public static func optimisticBetween(_ before: String?, _ after: String?) -> String {
        (try? generateBetween(before, after)) ?? generateAppend(before)
    }

    static func string(_ bytes: [UInt8]) -> String { String(decoding: bytes, as: UTF8.self) }

    /// Math.floor(x / y) for positive y.
    static func floorDiv(_ x: Int, _ y: Int) -> Int {
        let q = x / y
        return (x % y != 0 && (x < 0) != (y < 0)) ? q - 1 : q
    }
}
