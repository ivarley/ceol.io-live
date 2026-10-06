// Frames to notes, notes back on the beat's grid, and notes out of key dropped: the lab's
// segmentation.notes_from_pitch, grid.regrid_notes and key.drop_out_of_key.

import Foundation

public struct Note: Sendable, Equatable, Hashable {
    public var t0: Int
    public var t1: Int
    public var midi: Int

    public init(_ t0: Int, _ t1: Int, _ midi: Int) {
        self.t0 = t0
        self.t1 = t1
        self.midi = midi
    }
}

/// How one tracker's frames become notes (the lab's front-end defaults).
public struct NoteParams: Sendable {
    var minNoteMs: Double
    var medianFrames: Int
    var minVoiced: Double
    /// A tracker with no band of its own (PESTO) has yin's applied afterwards.
    var band: (Double, Double)?
    /// Split fused repeats where something was struck on a grid line.
    var splitRepeats: Bool
    var splitMinSlots = 1.6
    var splitTolerance = 0.12

    static let yin = NoteParams(minNoteMs: 60, medianFrames: 5, minVoiced: 0.2, band: nil, splitRepeats: true)
    static let pesto = NoteParams(minNoteMs: 60, medianFrames: 5, minVoiced: 0.0, band: (160, 1400), splitRepeats: true)
    static let basicPitch = NoteParams(minNoteMs: 30, medianFrames: 1, minVoiced: 0.5, band: nil, splitRepeats: false)
}

enum Notes {
    static let pitchClassBase = 60

    /// lab: FrontEnd.notes_from_track (and BandedFrontEnd's band first), folded to one
    /// octave, then offset by `offsetMs`.
    static func fromTrack(times: ArraySlice<Double>, f0: ArraySlice<Double>, voiced: ArraySlice<Double>,
                          params p: NoteParams, offsetMs: Int) -> [Note] {
        let n = times.count
        guard n > 0 else { return [] }
        let t = Array(times), v = Array(voiced)
        var f = Array(f0)
        if let (lo, hi) = p.band {
            for i in 0..<n where !(f[i] >= lo && f[i] <= hi) { f[i] = .nan }
        }
        var midi = [Double](repeating: .nan, count: n)
        var any = false
        for i in 0..<n where v[i] >= p.minVoiced {
            any = true
            if f[i].isFinite && f[i] > 0 {
                let m = hzToMidi(f[i]).roundedEven
                midi[i] = Double(pitchClassBase) + (m - 12 * floor(m / 12))
            }
        }
        guard any else { return [] }
        // median filter over the pitched frames only, edges repeated
        let idx = (0..<n).filter { midi[$0].isFinite }
        var smoothed = midi
        if p.medianFrames > 1 && !idx.isEmpty {
            let vals = idx.map { midi[$0] }
            let k = p.medianFrames, half = k / 2
            for (j, i) in idx.enumerated() {
                var w = [Double]()
                for o in (j - half)...(j - half + k - 1) { w.append(vals[min(max(o, 0), vals.count - 1)]) }
                w.sort()
                smoothed[i] = k % 2 == 1 ? w[k / 2] : (w[k / 2 - 1] + w[k / 2]) / 2
            }
        }
        var notes = [Note]()
        var current: Double? = nil
        var start = 0
        for i in 0...n {
            let value: Double = i < n ? smoothed[i] : .nan
            if let c = current, !value.isFinite || value != c {
                let t0 = t[start]
                let span = i < n ? t[i] - t0 : t[n - 1] - t0
                if span >= p.minNoteMs {
                    notes.append(Note(Int(t0) + offsetMs, Int(t0 + span) + offsetMs, Int(c)))
                }
                current = nil
            }
            if value.isFinite && current == nil {
                current = value
                start = i
            }
        }
        return notes
    }

    // MARK: The grid (lab: frontends/grid.py)

    static let minPiece = 0.25

    static func gridLines(_ t0: Double, _ t1: Double, period: Double, phase: Double) -> [Double] {
        guard period > 0 else { return [] }
        let first = Int(ceil((t0 - phase) / period)), last = Int(floor((t1 - phase) / period))
        guard first <= last else { return [] }
        return (first...last).map { phase + Double($0) * period }.filter { t0 < $0 && $0 < t1 }
    }

    /// Cut a long note at interior grid lines where an attack sits near the line.
    static func splitFusedRepeats(_ notes: [Note], period: Double, phase: Double, attacks: [Double],
                                  minSlots: Double, tolerance: Double) -> [Note] {
        guard period > 0, !notes.isEmpty else { return notes }
        let a = attacks.sorted()
        let window = tolerance * period
        var out = [Note]()
        for note in notes {
            let t0 = Double(note.t0), t1 = Double(note.t1)
            if t1 - t0 < minSlots * period {
                out.append(note)
                continue
            }
            let guardMs = minPiece * period
            var cuts = [Double]()
            for line in gridLines(t0, t1, period: period, phase: phase) {
                if line - t0 < guardMs || t1 - line < guardMs { continue }
                if !a.isEmpty {
                    let i = searchSorted(a, line)
                    let near = [i - 1, i].filter { $0 >= 0 && $0 < a.count }.map { a[$0] }
                    if near.contains(where: { abs($0 - line) <= window }) { cuts.append(line) }
                }
            }
            if cuts.isEmpty {
                out.append(note)
                continue
            }
            let edges = [t0] + cuts + [t1]
            for (x, y) in zip(edges, edges.dropFirst()) {
                let rx = Int(x.roundedEven), ry = Int(y.roundedEven)
                if ry - rx <= 0 { continue }
                out.append(Note(rx, ry, note.midi))
            }
        }
        return out
    }

    // MARK: The key (lab: analysis/key.py, "pair")

    static let major = [0, 2, 4, 5, 7, 9, 11]

    static func rootForSharps(_ sharps: Int) -> Int { pymod(7 * sharps, 12) }

    /// The eight pitch classes of two neighbouring key signatures holding the most note
    /// time, or nil with fewer than `minNotes` notes.
    static func modalPair(_ notes: [Note], minNotes: Int = 30) -> Set<Int>? {
        guard notes.count >= minNotes else { return nil }
        var mass = [Double](repeating: 0, count: 12)
        for n in notes { mass[pymod(n.midi, 12)] += max(1.0, Double(n.t1 - n.t0)) }
        var best: (Double, Set<Int>)? = nil
        for sharps in -5...7 {
            let pcs = Set(major.map { pymod(rootForSharps(sharps) + $0, 12) })
                .union(major.map { pymod(rootForSharps(sharps + 1) + $0, 12) })
            let held = pcs.reduce(0.0) { $0 + mass[$1] }
            if best == nil || held > best!.0 { best = (held, pcs) }
        }
        return best?.1
    }

    static func dropOutOfKey(_ notes: [Note]) -> [Note] {
        guard let pcs = modalPair(notes) else { return notes }
        return notes.filter { pcs.contains(pymod($0.midi, 12)) }
    }
}
