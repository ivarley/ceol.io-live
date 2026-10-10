// The n-gram shortlist (lab: corpus.index.Index.lookup, bench.retrieval.fuse,
// frontends.segmentation.intervals_from_notes): what was heard as semitone steps, every
// run of six as a vote for the tunes that hold it, weighted by how rare it is.

import Foundation

/// A note as the hearing sends it: start and end in ms of audio, a whole MIDI pitch.
public struct HeardNote: Sendable, Equatable {
    public let t0: Int
    public let t1: Int
    public let midi: Int
    public init(_ t0: Int, _ t1: Int, _ midi: Int) { self.t0 = t0; self.t1 = t1; self.midi = midi }
}

/// One tune in a ranking.
struct Ranked {
    let tune: Int          // position in the corpus
    let score: Double
    let coverage: Double
    let hits: Int
}

/// Semitone steps between notes, folded so an octave error costs nothing; nil where a
/// gap of more than 1.5 s breaks the phrase.
func intervals(_ notes: [HeardNote], maxGapMs: Int = 1500) -> [Int?] {
    guard notes.count > 1 else { return [] }
    var out = [Int?]()
    out.reserveCapacity(notes.count - 1)
    for i in 1..<notes.count {
        let prev = notes[i - 1], next = notes[i]
        if next.t0 - prev.t1 > maxGapMs {
            out.append(nil)
        } else {
            out.append(fold(next.midi - prev.midi))
        }
    }
    return out
}

/// An interval in [-6, 5] (lab: abc_pitch.fold_interval).
func fold(_ d: Int) -> Int {
    let m = (d + 6) % 12
    return (m < 0 ? m + 12 : m) - 6
}

/// Python's round(x, digits): the decimal nearest the double's exact value, ties to
/// even. The quick way is right unless x sits within a hair of a half.
func pyRound(_ x: Double, _ digits: Int) -> Double {
    let scale = pow(10.0, Double(digits))
    let y = x * scale
    let frac = abs(y - y.rounded(.down))
    if abs(frac - 0.5) > 1e-6, y.isFinite, abs(y) < 1e15 { return y.rounded(.toNearestOrAwayFromZero) / scale }
    return Double(String(format: "%.\(digits)f", x)) ?? x
}

final class Lookup {
    let corpus: Corpus
    // scratch, by tune position; cleared after each lookup
    private var scores: [Double]
    private var hits: [Int32]
    private var distinct: [Int32]
    private var touched: [Int] = []

    init(_ corpus: Corpus) {
        self.corpus = corpus
        scores = .init(repeating: 0, count: corpus.tuneCount)
        hits = .init(repeating: 0, count: corpus.tuneCount)
        distinct = .init(repeating: 0, count: corpus.tuneCount)
    }

    /// The n-gram keys of a run of intervals, each once, in the order first met, with
    /// how many times it occurs (Counter's order).
    private func grams(_ steps: [Int?]) -> [(key: UInt32, mult: Int)] {
        let n = corpus.n
        var out = [(key: UInt32, mult: Int)]()
        var at = [UInt32: Int]()
        var run = [Int]()
        for v in steps {
            guard let v else { run.removeAll(keepingCapacity: true); continue }
            run.append(v)
            if run.count >= n {
                var key: UInt32 = 0, place: UInt32 = 1
                for x in run[(run.count - n)...] {
                    key &+= UInt32(x + 6) &* place
                    place &*= 12
                }
                if let i = at[key] { out[i].mult += 1 } else { at[key] = out.count; out.append((key, 1)) }
            }
        }
        return out
    }

    /// The `top` tunes for what was heard, over the whole corpus or only a repertoire's
    /// tunes (with that repertoire's idf).
    func lookup(_ steps: [Int?], top: Int, within rep: Repertoire? = nil) -> [Ranked] {
        let grams = grams(steps)
        if grams.isEmpty { return [] }
        let nTunes = Double(rep?.size ?? corpus.nTunes)
        var totalIDF = 0.0
        for (key, mult) in grams {
            guard let g = corpus.gram(key) else { continue }      // df 0: idf 0, adds nothing
            let list = corpus.tunes(holding: g)
            let df = rep.map { Int($0.df[g]) } ?? list.count
            if df == 0 { continue }
            let w = log(nTunes / Double(df))
            totalIDF += w * Double(mult)
            if w <= 0 { continue }
            let wm = w * Double(mult)
            for t16 in list {
                let t = Int(t16)
                if let rep, !rep.member[t] { continue }
                if hits[t] == 0 { touched.append(t) }
                scores[t] += wm
                hits[t] += Int32(mult)
                distinct[t] += 1
            }
        }
        defer {
            for t in touched { scores[t] = 0; hits[t] = 0; distinct[t] = 0 }
            touched.removeAll(keepingCapacity: true)
        }
        if touched.isEmpty { return [] }
        let denom = totalIDF == 0 ? 1.0 : totalIDF
        var out = touched.map { t in
            Ranked(tune: t, score: scores[t] / denom,
                   coverage: Double(distinct[t]) / Double(max(1, Int(corpus.tuneGramCount[t]))),
                   hits: Int(hits[t]))
        }
        let rounded = Dictionary(uniqueKeysWithValues: out.map { ($0.tune, pyRound($0.score, 6)) })
        out.sort { a, b in
            let ra = rounded[a.tune]!, rb = rounded[b.tune]!
            if ra != rb { return ra > rb }
            if a.coverage != b.coverage { return a.coverage > b.coverage }
            if a.hits != b.hits { return a.hits > b.hits }
            return a.tune < b.tune        // positions follow tune ids
        }
        return Array(out.prefix(top))
    }
}

/// Rankings from several trackers as one (lab: retrieval.fuse, method "sum"): each
/// tracker's scores as shares of its own total, summed.
func fuse(_ rankings: [[Ranked]]) -> [Ranked] {
    if rankings.count == 1 { return rankings[0] }
    var order = [Int]()
    var merged = [Int: Double]()
    var first = [Int: Ranked]()
    for ranked in rankings {
        var total = 0.0
        for r in ranked { total += max(0, r.score) }
        if total == 0 { total = 1 }
        for r in ranked {
            if merged[r.tune] == nil { order.append(r.tune); first[r.tune] = r; merged[r.tune] = 0 }
            merged[r.tune]! += max(0, r.score) / total
        }
    }
    let at = Dictionary(uniqueKeysWithValues: order.enumerated().map { ($1, $0) })
    return order.sorted { a, b in
        let x = merged[a]!, y = merged[b]!
        return x != y ? x > y : at[a]! < at[b]!       // Python's sort is stable
    }.map { t in
        let r = first[t]!
        return Ranked(tune: t, score: merged[t]!, coverage: r.coverage, hits: r.hits)
    }
}
