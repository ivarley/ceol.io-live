// String rules shared by the ports, spelled out to match JavaScript exactly.

enum JSText {
    /// JavaScript's whitespace (\s, String.prototype.trim): the Unicode set JS uses.
    static func isWhitespace(_ u: Unicode.Scalar) -> Bool { ABCQuery.isJSWhitespace(u) }

    /// String.prototype.trim.
    static func trim(_ s: String) -> String {
        let scalars = Array(s.unicodeScalars)
        guard let first = scalars.firstIndex(where: { !isWhitespace($0) }),
            let last = scalars.lastIndex(where: { !isWhitespace($0) })
        else { return "" }
        var out = String.UnicodeScalarView()
        out.append(contentsOf: scalars[first...last])
        return String(out)
    }

    /// `a < b` on JS strings: UTF-16 code-unit order, never locale-aware.
    static func less(_ a: String, _ b: String) -> Bool { a.utf16.lexicographicallyPrecedes(b.utf16) }

    /// JavaScript's String(n) for a number: integers without a fraction.
    static func string(of n: Double) -> String {
        if n.rounded() == n, abs(n) < 1e21 { return String(Int64(n)) }
        return String(n)
    }

    /// /^\d+$/ with JS's \d (ASCII digits only).
    static func isDigits(_ s: Substring) -> Bool {
        !s.isEmpty && s.unicodeScalars.allSatisfy { ("0"..."9").contains($0) }
    }
}
