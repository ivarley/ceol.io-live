// Tune-name matching (spec 037) — a port of frontend/src/tunesheet/namematch.js: are
// two strings the same NAME? It exists for one job, deciding whether the tune sheet's
// "aka" subtitle is worth a line ("The Silver Spear / aka Silver Spear" is noise).
// Not a judgment about whether two tunes are the same tune.
//
// The two errors are not equally bad: calling a spelling variant "different" costs a
// pointless aka line; calling a genuinely different name "same" hides that the tune
// has another name. The calibration sets in namematch.fixtures.json hold the port to
// the same bars as the web: >= 95% of variants same, 100% of distinct pairs different.
//
// After meatTokens folds a name to lowercase ASCII, every later step works on ASCII,
// so from there Swift regexes and JS regexes mean the same thing.

import Foundation

public enum NameMatch {
    /// Tuned against the labelled fixture set.
    public static let diceThreshold = 0.8
    /// Below this a "prefix" means nothing: every string starts with something short.
    static let minPrefixLength = 5

    /// Tune-type words: trailing, they are decoration ("Cooley's Reel" is "Cooley's").
    /// Multi-word types first, so the longest match wins.
    static let typeWords = [
        "slip jig", "set dance", "hop jig", "barndance", "hornpipe", "strathspey", "mazurka", "polka",
        "schottische", "hornpipes", "march", "slide", "waltz", "reel", "jig",
    ]
    static let trailingNoise = ["favourite", "favorite", "fancy", "delight"]

    // MARK: - Guards

    /// Digit runs in a name, in order, without leading zeros. Names whose numbers
    /// differ are always different.
    public static func digitRuns(_ name: String?) -> [String] {
        var runs: [String] = []
        var cur = ""
        for u in (name ?? "").unicodeScalars {
            if ("0"..."9").contains(u) {
                cur.unicodeScalars.append(u)
            } else if !cur.isEmpty {
                runs.append(cur)
                cur = ""
            }
        }
        if !cur.isEmpty { runs.append(cur) }
        // String(parseInt(d, 10)): leading zeros go, "000" is "0".
        return runs.map { run in
            let trimmed = run.drop { $0 == "0" }
            return trimmed.isEmpty ? "0" : String(trimmed)
        }
    }

    /// Bracketed asides, "The Silver Spear (Kevin's)": each ( [ { opener up to the
    /// first ) ] } closer, left to right, reduced to lowercase ASCII letters and digits,
    /// empties dropped, sorted. Names whose parentheticals differ are always different.
    public static func parentheticals(_ name: String?) -> [String] {
        let scalars = Array((name ?? "").unicodeScalars)
        let openers: Set<Unicode.Scalar> = ["(", "[", "{"]
        let closers: Set<Unicode.Scalar> = [")", "]", "}"]
        var found: [String] = []
        var i = 0
        while i < scalars.count {
            if openers.contains(scalars[i]), let j = scalars[(i + 1)...].firstIndex(where: closers.contains) {
                var kept = ""
                for u in scalars[i...j] where u.isASCII && (u.properties.isAlphabetic || ("0"..."9").contains(u)) {
                    kept.unicodeScalars.append(u)
                }
                found.append(kept.lowercased())
                i = j + 1
            } else {
                i += 1
            }
        }
        return found.filter { !$0.isEmpty }.sorted(by: JSText.less)
    }

    // MARK: - Normalization

    /// A name reduced to its "meat" tokens: lowercase, unaccented, unpunctuated,
    /// de-articled, trailing type and noise words peeled, each token de-pluralized,
    /// -y/-ie/-ey unified, spelling canonicalized.
    static func meatTokens(_ name: String?) -> [String] {
        // Lowercase, then fold diacritics BEFORE stripping punctuation, or accented
        // letters are deleted rather than folded.
        var folded = String.UnicodeScalarView()
        for u in (name ?? "").lowercased().decomposedStringWithCanonicalMapping.unicodeScalars {
            switch u.value {
            case 0x0300...0x036F: continue  // combining marks
            case 0x2019, 0x02BC, 0x0060, 0x00B4, 0x0027: continue  // apostrophes
            default: folded.append(u)
            }
        }
        // Anything but a-z 0-9 becomes one space; collapse and trim. ASCII from here on.
        var s = ""
        var pendingSpace = false
        for u in folded {
            if ("a"..."z").contains(u) || ("0"..."9").contains(u) {
                if pendingSpace && !s.isEmpty { s.append(" ") }
                pendingSpace = false
                s.unicodeScalars.append(u)
            } else {
                pendingSpace = true
            }
        }
        // Leading "the", and the trailing ", the" form (the comma is already gone).
        if s.hasPrefix("the ") { s.removeFirst(4) }
        if s.hasSuffix(" the") { s.removeLast(4) }

        // Peel trailing decoration until nothing peels; never peel down to nothing.
        var peeled = true
        while peeled {
            peeled = false
            for w in typeWords + trailingNoise {
                let suffix = " " + w
                if s.hasSuffix(suffix) && s.count > suffix.count {
                    s.removeLast(suffix.count)
                    s = s.trimmingCharacters(in: .whitespaces)
                    peeled = true
                    break
                }
            }
        }

        return s.split(separator: " ").map(String.init)
            // Trailing "s" on every token of more than two letters.
            .map { $0.count > 2 && $0.hasSuffix("s") ? String($0.dropLast()) : $0 }
            // Token-final -ey / -ie / -y all become -i (leftmost match: -ey beats -y).
            .map { t -> String in
                guard t.count > 2 else { return t }
                if t.hasSuffix("ey") || t.hasSuffix("ie") { return String(t.dropLast(2)) + "i" }
                if t.hasSuffix("y") { return String(t.dropLast()) + "i" }
                return t
            }
            .map(canonicalize)
            .filter { !$0.isEmpty }
    }

    /// Spelling canonicalizations, identical on both sides of a comparison. Minimal by
    /// policy: each entry exists because a labelled pair fails without it.
    static func canonicalize(_ t: String) -> String {
        var x = t
        x = x.replacing(/conn(?:aught|aght|acht)/, with: "connacht")
        x = x.replacing("connachtmann", with: "connachtman")
        x = x.replacing("our", with: "or")
        x = x.replacing("ise", with: "ize")
        x = x.replacing(/([bcdfgklmnprstz])\1/) { String($0.output.1) }
        return x
    }

    /// The prefix form: word order kept.
    public static func normalizeNameOrdered(_ name: String?) -> String { meatTokens(name).joined() }

    /// The similarity form: tokens sorted, so word order carries no identity.
    public static func normalizeName(_ name: String?) -> String {
        meatTokens(name).sorted(by: JSText.less).joined()
    }

    /// Dice coefficient over character bigrams (UTF-16 units, as the JS slices them):
    /// 1 is identical, 0 nothing in common.
    public static func diceCoefficient(_ a: String, _ b: String) -> Double {
        if a == b { return 1 }
        let ua = Array(a.utf16)
        let ub = Array(b.utf16)
        if ua.count < 2 || ub.count < 2 { return 0 }
        var bigrams: [UInt32: Int] = [:]
        for i in 0..<(ua.count - 1) {
            bigrams[UInt32(ua[i]) << 16 | UInt32(ua[i + 1]), default: 0] += 1
        }
        var hits = 0
        for i in 0..<(ub.count - 1) {
            let g = UInt32(ub[i]) << 16 | UInt32(ub[i + 1])
            if let n = bigrams[g], n > 0 {
                bigrams[g] = n - 1
                hits += 1
            }
        }
        return Double(2 * hits) / Double(ua.count - 1 + (ub.count - 1))
    }

    // MARK: - The decisions

    /// Are these the same name? Equal after normalization, or one a prefix of the
    /// other (word order kept), or close by bigram overlap — always overridden by the
    /// two guards: differing numbers or differing parentheticals are different names.
    public static func sameName(_ a: String?, _ b: String?) -> Bool {
        let rawA = JSText.trim(a ?? "")
        let rawB = JSText.trim(b ?? "")
        if rawA.isEmpty || rawB.isEmpty { return false }
        if rawA == rawB { return true }

        if digitRuns(rawA) != digitRuns(rawB) { return false }
        if parentheticals(rawA) != parentheticals(rawB) { return false }

        let na = normalizeName(rawA)
        let nb = normalizeName(rawB)
        if na.isEmpty || nb.isEmpty { return rawA.lowercased() == rawB.lowercased() }
        if na == nb { return true }

        let oa = normalizeNameOrdered(rawA)
        let ob = normalizeNameOrdered(rawB)
        let (shortO, longO) = oa.utf16.count <= ob.utf16.count ? (oa, ob) : (ob, oa)
        if shortO.utf16.count >= minPrefixLength && longO.hasPrefix(shortO) { return true }

        return diceCoefficient(na, nb) >= diceThreshold
    }

    /// The inverse, named for how the tune sheet reads.
    public static func meaningfullyDiffers(_ a: String?, _ b: String?) -> Bool { !sameName(a, b) }

    /// The aka line: walking down the name chain (most personal first, nil for layers
    /// that don't apply), the first name that meaningfully differs from the title —
    /// the first non-empty entry. Exactly one, or nil.
    public static func pickAka(_ chain: [String?]) -> String? {
        let names = chain.map { $0.map(JSText.trim) ?? "" }
        guard let titleIdx = names.firstIndex(where: { !$0.isEmpty }) else { return nil }
        let title = names[titleIdx]
        for candidate in names[(titleIdx + 1)...] where !candidate.isEmpty && meaningfullyDiffers(title, candidate) {
            return candidate
        }
        return nil
    }
}
