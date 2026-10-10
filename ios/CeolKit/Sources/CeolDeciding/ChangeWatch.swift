// "The tune may have changed" (lab: listen.ChangeWatch, rule "rounds"): the tune shown
// has been at full belief since it was shown, has gone round 1.8 times or more (the time
// since it was shown, over the beat heard times its eighths per round), and its belief
// falls under 0.8. A tune with no readable setting counts as having gone round once it
// has been shown 40 s. The meter then stops claiming it, until its belief is back at
// full or another tune is shown. The player's idea (2026-10-08): a tune played through
// and then doubted has almost surely changed.

import Foundation

struct ChangeWatch {
    var full = 0.99, doubt = 0.8, rounds = 1.8, heldMs = 40000.0
    /// Eighths per round of a tune, or nil (lab: analysis.form.RoundLengths).
    var roundLength: (Int) -> Double? = { _ in nil }

    private var tune: Int?
    private(set) var changing: Int?
    private(set) var changingSince: Int?
    private var since = 0, lastT = 0
    private var fullSince: Int?
    private var goneRound = 0.0
    private var period: Double?

    init(full: Double, doubt: Double, rounds: Double, heldMs: Double, roundLength: @escaping (Int) -> Double?) {
        (self.full, self.doubt, self.rounds, self.heldMs) = (full, doubt, rounds, heldMs)
        self.roundLength = roundLength
    }

    /// A beat's period folded into the range an eighth note lives in, 110-230 ms
    /// (lab: analysis.follow.eighth).
    static func eighth(_ periodMs: Double) -> Double {
        var p = periodMs
        while p > 230 { p /= 2 }
        while p < 110 { p *= 2 }
        return p
    }

    /// One state in: `belief` {tune: p} (the decoder's top eight), the tune shown (nil
    /// for none), the belief in "not a tune", the beat heard. -> the tune that may have
    /// changed, or nil.
    mutating func step(_ t: Int, belief: [Int: Double], shown: Int?, none: Double, periodMs: Double?) -> Int? {
        guard none <= 0.5, let shown else {
            tune = nil
            changing = nil
            return nil
        }
        if shown != tune {
            tune = shown
            since = t
            lastT = t
            fullSince = nil
            goneRound = 0
            period = nil
            changing = nil
        }
        if let periodMs, periodMs != 0 { period = Self.eighth(periodMs) }
        let perRound = roundLength(shown)
        if let perRound, perRound != 0, let period, period != 0 {
            goneRound += Double(t - lastT) / (period * perRound)
        }
        lastT = t
        let p = belief[shown] ?? 0
        if p >= full {
            changing = nil
            if fullSince == nil { fullSince = t }
            return nil
        }
        if changing != nil || fullSince == nil { return changing }
        let played = perRound != nil ? goneRound >= rounds : Double(t - since) >= heldMs
        if p < doubt && played {
            changing = shown
            changingSince = t
        }
        return changing
    }
}
