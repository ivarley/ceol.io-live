// thesession.org id parsing — a port of parseThesessionId / parseThesessionSettingId in
// frontend/src/shared/parse.js (fixtured with the logger, whose paste detection uses
// them: frontend/src/logstate.fixtures.json). The domain match is case-sensitive, and
// leading zeros are dropped, as parseInt does. One deliberate difference: a digit run
// too long for Int is nil here, where JS parseInt returns an imprecise number — an id
// that size is not a real thesession.org id either way.

import Foundation

public enum TheSession {
    /// A thesession.org tune URL or a bare numeric id -> the tune id, else nil. Mirrors
    /// the server's _parse_thesession_id.
    public static func tuneID(_ raw: String?) -> Int? {
        guard let raw else { return nil }
        let s = JSText.trim(raw)
        if let digits = digits(after: "thesession.org/tunes/", in: s) { return Int(digits) }
        return JSText.isDigits(Substring(s)) ? Int(s) : nil
    }

    /// The setting deep-link in a thesession tune URL: ?setting=N or &setting=N, else
    /// #settingN. Only meaningful alongside a URL; a bare id carries no setting.
    public static func settingID(_ raw: String?) -> Int? {
        guard let raw else { return nil }
        let s = JSText.trim(raw)
        guard s.contains("thesession.org") else { return nil }
        // /[?&]setting=(\d+)/: whichever of the two comes first in the string.
        let starts = ["?setting=", "&setting="].compactMap { matchStart($0, in: s) }
        if let start = starts.min() {
            let afterMarker = s.index(start, offsetBy: "?setting=".count)
            return Int(s[afterMarker...].prefix { ("0"..."9").contains($0) })
        }
        return digits(after: "#setting", in: s).flatMap { Int($0) }
    }

    /// The run of ASCII digits right after the FIRST occurrence of `marker` that is
    /// followed by at least one digit — what `s.match(/marker(\d+)/)` finds.
    static func digits(after marker: String, in s: String) -> Substring? {
        var searchFrom = s.startIndex
        while let r = s.range(of: marker, range: searchFrom..<s.endIndex) {
            let run = s[r.upperBound...].prefix { ("0"..."9").contains($0) }
            if !run.isEmpty { return run }
            searchFrom = r.lowerBound < s.endIndex ? s.index(after: r.lowerBound) : s.endIndex
        }
        return nil
    }

    /// Where the first `marker` followed by a digit starts.
    static func matchStart(_ marker: String, in s: String) -> String.Index? {
        var searchFrom = s.startIndex
        while let r = s.range(of: marker, range: searchFrom..<s.endIndex) {
            if let c = s[r.upperBound...].first, ("0"..."9").contains(c) { return r.lowerBound }
            searchFrom = s.index(after: r.lowerBound)
        }
        return nil
    }
}
