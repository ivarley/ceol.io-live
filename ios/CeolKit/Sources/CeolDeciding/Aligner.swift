// The aligner (lab: bench.retrieval.Aligner on the "notes" reading, in each setting's
// written key; analysis.align): the newest notes as pitch classes, cut into pieces of
// 24, each finding its best place anywhere in a setting written twice over
// (Smith-Waterman: match +2, mismatch and gap -1). A tune scores its best setting, as
// a share of what the notes could score, averaged over the trackers.
//
// Every value is a whole number until the last division, so integer arithmetic here
// gives the lab's floats exactly.

import Foundation

struct Aligner {
    let corpus: Corpus
    var chunk = 24

    /// One tracker's notes as a query: pitch classes, a repeated one once.
    static func query(_ notes: [HeardNote]) -> [Int8] {
        var out = [Int8]()
        for n in notes {
            let pc = Int8(((n.midi % 12) + 12) % 12)
            if out.last != pc { out.append(pc) }
        }
        return out
    }

    /// {tune id: score} for every tune, the queries one per tracker that heard notes.
    func scores(_ tuneIDs: [Int], _ queries: [[Int8]]) -> [Double] {
        let pieces = queries.map { q -> [ArraySlice<Int8>] in
            stride(from: 0, to: q.count, by: chunk).compactMap { s in
                let p = q[s..<min(q.count, s + chunk)]
                return p.count >= chunk / 4 ? p : nil       // every symbol is known here
            }
        }
        let known = queries.map(\.count)
        var out = [Double](repeating: 0, count: tuneIDs.count)
        let positions = tuneIDs.map { corpus.index(of: $0) }
        out.withUnsafeMutableBufferPointer { res in
            let res = res
            DispatchQueue.concurrentPerform(iterations: tuneIDs.count) { k in
                guard let i = positions[k] else { return }
                let a = Int(corpus.setOff[i]), b = Int(corpus.setOff[i + 1])
                if a == b { return }
                var total = 0.0
                for (qi, ps) in pieces.enumerated() {
                    var best = 0.0
                    for s in a..<b {
                        let from = Int(corpus.seqOff[s]), to = Int(corpus.seqOff[s + 1])
                        let target = UnsafeBufferPointer(start: corpus.symbols + from, count: to - from)
                        var sum = 0
                        for p in ps { sum += Self.localAlign(p, target) }
                        let v = target.isEmpty ? 0 : Double(sum) / Double(2 * known[qi])
                        if v > best { best = v }
                    }
                    total += best
                }
                res[k] = total / Double(queries.count)
            }
        }
        return out
    }

    /// Best local alignment of q against t written twice over (lab: align.local_align).
    static func localAlign(_ q: ArraySlice<Int8>, _ t: UnsafeBufferPointer<Int8>) -> Int {
        let m = t.count
        let w = 2 * m
        if m == 0 { return 0 }
        var prev = [Int32](repeating: 0, count: w + 1)
        var cur = [Int32](repeating: 0, count: w + 1)
        var best: Int32 = 0
        prev.withUnsafeMutableBufferPointer { prev in
            cur.withUnsafeMutableBufferPointer { cur in
                var p = prev, c = cur
                for qi in q {
                    c[0] = 0
                    for j in 1...w {
                        let tj = t[j <= m ? j - 1 : j - 1 - m]
                        let s: Int32 = (qi < 0 || tj < 0) ? 0 : (qi == tj ? 2 : -1)
                        var v = p[j - 1] + s
                        let up = p[j] - 1
                        if up > v { v = up }
                        let left = c[j - 1] - 1
                        if left > v { v = left }
                        if v < 0 { v = 0 }
                        c[j] = v
                        if v > best { best = v }
                    }
                    swap(&p, &c)
                }
            }
        }
        return Int(best)
    }
}
