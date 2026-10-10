// The decoder (lab: bench.stream.Decoder): a causal belief over the tunes heard so far
// and "not a tune", one step at a time. A tune stays or, now and then, the music jumps
// to a tune this step proposes or to nothing; each step's aligner scores say how well
// each one fits.

import Foundation

/// The "not a tune" state.
public let notATune = -1

/// numpy's logaddexp, case for case.
@inline(__always) func logaddexp(_ x: Double, _ y: Double) -> Double {
    if x == y { return x + M_LN2 }
    let d = x - y
    if d > 0 { return x + log1p(exp(-d)) }
    if d <= 0 { return y + log1p(exp(d)) }
    return d
}

func logsumexp(_ v: [Double]) -> Double {
    var acc = v[0]
    for i in 1..<v.count { acc = logaddexp(acc, v[i]) }
    return acc
}

struct Chunk {
    var tMs: Int
    var tunes: [Int]              // in the order scored
    var scores: [Double]
    var floor: Double
    var outside: Set<Int>
    /// The second tier's tunes among those scored (popular, not the session's own).
    var partly: [Int] = []
    var nNotes: Int
    var tuneLogodds: Double
}

struct TuneDecoder {
    var lam = 40.0, tau = 0.45, pSwitch = 0.05, pNone = 0.3, nu = 0.0, kappa = 0.0, gamma = 0.0, nuPartly = 0.0
    var nSettings: (Int) -> Int = { _ in 1 }

    private(set) var ids: [Int] = [notATune]
    private var at: [Int: Int] = [notATune: 0]
    private(set) var log: [Double] = [0]

    init(lam: Double, tau: Double, pSwitch: Double, pNone: Double, nu: Double, kappa: Double, gamma: Double,
         nuPartly: Double = 0) {
        (self.lam, self.tau, self.pSwitch, self.pNone) = (lam, tau, pSwitch, pNone)
        (self.nu, self.kappa, self.gamma, self.nuPartly) = (nu, kappa, gamma, nuPartly)
    }

    mutating func reset() {
        ids = [notATune]
        at = [notATune: 0]
        log = [0]
    }

    mutating func step(_ c: Chunk) -> Int {
        let ls = Foundation.log(1 - pSwitch), lj = Foundation.log(pSwitch)
        for t in c.tunes where at[t] == nil {
            at[t] = ids.count
            ids.append(t)
            log.append(-1e9)
        }
        let n = ids.count
        var emit = [Double](repeating: lam * c.floor, count: n)
        emit[0] = lam * (tau - gamma * c.tuneLogodds / 10.0)
        var inPool = [Bool](repeating: false, count: n)
        for (t, s) in zip(c.tunes, c.scores) {
            let r = at[t]!
            emit[r] = lam * s
            inPool[r] = true
        }
        if nu != 0 { for t in c.outside { emit[at[t]!] -= lam * nu } }
        // a second-tier tune: a fraction of an outside tune's discount
        if nu != 0, nuPartly != 0 {
            for t in c.partly { if let r = at[t] { emit[r] -= lam * nu * nuPartly } }
        }
        if kappa != 0 {
            for t in c.tunes { emit[at[t]!] -= lam * kappa * Foundation.log(Double(max(1, nSettings(t)))) }
        }
        let total = logsumexp(log)
        let jumpTune = lj + Foundation.log(1 - pNone) + total - Foundation.log(Double(max(1, c.tunes.count)))
        let jumpNone = lj + Foundation.log(pNone) + total
        var new = log.map { ls + $0 }
        for i in 0..<n where inPool[i] { new[i] = logaddexp(new[i], jumpTune) }
        new[0] = logaddexp(new[0], jumpNone)
        for i in 0..<n { new[i] += emit[i] }
        let z = logsumexp(new)
        log = new.map { max($0 - z, -1e9) }
        var best = 0
        for i in 1..<n where log[i] > log[best] { best = i }
        return ids[best]
    }

    /// "This is it": all belief on that tune; listening goes on.
    mutating func confirm(_ tune: Int) {
        if at[tune] == nil {
            at[tune] = ids.count
            ids.append(tune)
            log.append(-1e9)
        }
        log = [Double](repeating: -30, count: ids.count)
        log[at[tune]!] = 0
    }

    /// "None of these": no belief left on them.
    mutating func ruleOut(_ tunes: [Int]) {
        for t in tunes { if let i = at[t] { log[i] = -1e9 } }
        let z = logsumexp(log)
        log = log.map { max($0 - z, -1e9) }
    }

    /// The `k` most believed states: (state, probability).
    func belief(_ k: Int) -> [(state: Int, p: Double)] {
        let order = log.indices.sorted { log[$0] != log[$1] ? log[$0] > log[$1] : $0 < $1 }
        return order.prefix(k).map { (ids[$0], exp(log[$0])) }
    }
}
