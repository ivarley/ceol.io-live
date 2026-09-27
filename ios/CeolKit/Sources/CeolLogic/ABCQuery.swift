// Notation (ABC) search — a port of frontend/src/shared/abcquery.js: is a typed query
// notes rather than a name, and what key does it search with? The same rules live in
// SQL (abc_search_key, schema/055), Python (database.py) and the web; this is the
// fourth copy, and if any drifts, notation search silently stops matching.
// Cases and the exact rules: frontend/src/shared/abcquery.fixtures.json.
//
// Written as explicit scans over Unicode scalars rather than Swift regexes, so the
// JavaScript semantics (the \s set, left-to-right alternation) are spelled out.

public enum ABCQuery {
    /// Blended search needs at least this many normalized characters.
    public static let minQueryLength = 3

    /// JavaScript's \s: the Unicode whitespace set JS regexes use.
    static func isJSWhitespace(_ u: Unicode.Scalar) -> Bool {
        switch u.value {
        case 0x09...0x0D, 0x20, 0xA0, 0x1680, 0x2000...0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF:
            return true
        default:
            return false
        }
    }

    /// Characters a typed melody can contain: [A-Ga-gxz0-9|^_=,'/()[\]:<>~-]
    static func isFriendly(_ u: Unicode.Scalar) -> Bool {
        switch u {
        case "A"..."G", "a"..."g", "x", "z", "0"..."9",
            "|", "^", "_", "=", ",", "'", "/", "(", ")", "[", "]", ":", "<", ">", "~", "-":
            return true
        default:
            return false
        }
    }

    /// Normalize a query, or a stored ABC body, the way abc_search_key() does:
    /// drop ornaments ({...} grace notes and "..." chord symbols, one left-to-right
    /// pass, braces not nested, an unclosed opener kept), then whitespace and '!',
    /// then lowercase.
    public static func normAbc(_ s: String?) -> String {
        let scalars = Array((s ?? "").unicodeScalars)
        var kept = String.UnicodeScalarView()
        var i = 0
        while i < scalars.count {
            let c = scalars[i]
            if c == "{" || c == "\"" {
                let close: Unicode.Scalar = c == "{" ? "}" : "\""
                if let j = scalars[(i + 1)...].firstIndex(of: close) {
                    i = j + 1
                    continue
                }
            }
            if !(isJSWhitespace(c) || c == "!") { kept.append(c) }
            i += 1
        }
        return String(kept).lowercased()
    }

    /// True when the query is plausibly notation rather than a name. Deliberately
    /// permissive: notation hits are blended below name hits.
    public static func looksLikeAbc(_ q: String?) -> Bool {
        let key = normAbc(q)
        return !key.isEmpty && key.unicodeScalars.allSatisfy(isFriendly)
    }

    /// The needle a blended notation search should use, or "" when the query doesn't
    /// qualify. `min` is inclusive, counted in UTF-16 units like JS .length.
    public static func abcNeedle(_ q: String?, min: Int = minQueryLength) -> String {
        let key = normAbc(q)
        return key.utf16.count >= min && key.unicodeScalars.allSatisfy(isFriendly) ? key : ""
    }
}
