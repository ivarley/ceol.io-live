// Basic Pitch (Spotify, ICASSP 2022) as the lab's BasicPitchFrontEnd runs it: its own
// Core ML model over 2 s windows, its note-making (onsets, then the "melodia trick"),
// and the loudest note in each 10 ms frame as the melody (lab/frontends/basicpitch.py).
// The note-making is basic_pitch.note_creation.output_to_notes_polyphonic, line for line.

import CoreML
import Foundation

enum BasicPitch {
    static let sr = 22050
    static let fftHop = 256
    static let windowSamples = 43844          // 2 s less a hop
    static let overlapFrames = 30
    static let framesPerWindow = 172
    static let annotationsFPS = 86            // 22050 // 256
    static let midiOffset = 21
    static let maxFreqIdx = 87
    static let onsetThreshold = 0.5, frameThreshold = 0.3
    static let minNoteFrames = 5              // round(58 ms * 86.13 frames/s)
    static let energyTolerance = 11
    static let fmin = 160.0, fmax = 1400.0

    /// The lab's Basic Pitch reads its audio back from a 16-bit WAV, which maps a sample
    /// to floor(x * 32768) of its float form: one step down for most negative ones.
    static func asWavRoundTrip(_ pcm: ArraySlice<Int16>) -> [Float] {
        pcm.map { s in
            let x = Float(s) / 32767
            let v = min(max(floor(Double(x) * 32768), -32768), 32767)
            return Float(v) / 32768
        }
    }

    /// One tracker step: audio (as 16-bit samples) -> the melody as frames.
    static func track(_ pcm: ArraySlice<Int16>, model: MLModel) throws -> Track {
        let y = asWavRoundTrip(pcm)
        let (note, onset) = try infer(y, model: model)
        let events = notes(frames: note, onsets: onset)
        return skyline(events, durationMs: 1000.0 * Double(y.count) / Double(sr))
    }

    /// basic_pitch.inference.run_inference: overlapping windows, half the overlap cut from
    /// each side, joined and trimmed to the audio's length. -> (note, onset), frames x 88.
    static func infer(_ y: [Float], model: MLModel) throws -> ([[Float]], [[Float]]) {
        let overlapLen = overlapFrames * fftHop
        let hopSize = windowSamples - overlapLen
        var audio = [Float](repeating: 0, count: overlapLen / 2)
        audio.append(contentsOf: y)
        var note = [[Float]](), onset = [[Float]]()
        let input = try MLMultiArray(shape: [1, NSNumber(value: windowSamples), 1], dataType: .float32)
        let cut = overlapFrames / 2
        var i = 0
        while i < audio.count {
            let ptr = input.dataPointer.bindMemory(to: Float.self, capacity: windowSamples)
            for k in 0..<windowSamples { ptr[k] = i + k < audio.count ? audio[i + k] : 0 }
            let out = try model.prediction(from: MLDictionaryFeatureProvider(dictionary: ["input_2": input]))
            let n = rows(out.featureValue(for: "Identity_1")!.multiArrayValue!)
            let o = rows(out.featureValue(for: "Identity_2")!.multiArrayValue!)
            note.append(contentsOf: n[cut..<(n.count - cut)])
            onset.append(contentsOf: o[cut..<(o.count - cut)])
            i += hopSize
        }
        let frames = Int(floor(Double(y.count) * (Double(annotationsFPS) / Double(sr))))
        return (Array(note.prefix(frames)), Array(onset.prefix(frames)))
    }

    /// A (1, frames, bins) output as frames of bins, whatever its strides.
    static func rows(_ a: MLMultiArray) -> [[Float]] {
        let t = a.shape[1].intValue, f = a.shape[2].intValue
        let st = a.strides.map(\.intValue)
        var out = [[Float]](repeating: [Float](repeating: 0, count: f), count: t)
        switch a.dataType {
        case .float32:
            let p = a.dataPointer.bindMemory(to: Float.self, capacity: a.count)
            for i in 0..<t { for j in 0..<f { out[i][j] = p[i * st[1] + j * st[2]] } }
        case .float16:
            let p = a.dataPointer.bindMemory(to: Float16.self, capacity: a.count)
            for i in 0..<t { for j in 0..<f { out[i][j] = Float(p[i * st[1] + j * st[2]]) } }
        default:
            for i in 0..<t { for j in 0..<f { out[i][j] = a[[0, NSNumber(value: i), NSNumber(value: j)]].floatValue } }
        }
        return out
    }

    struct Event: Equatable {
        var start: Double, end: Double, midi: Int, amplitude: Double
    }

    /// basic_pitch.note_creation.model_output_to_notes with the lab's settings.
    static func notes(frames framesIn: [[Float]], onsets onsetsIn: [[Float]]) -> [Event] {
        let n = framesIn.count
        guard n > 0 else { return [] }
        let bins = framesIn[0].count
        var frames = framesIn.map { $0.map(Double.init) }
        var onsets = onsetsIn.map { $0.map(Double.init) }
        // the band
        let maxIdx = Int((hzToMidi(fmax) - Double(midiOffset)).roundedEven)
        let minIdx = Int((hzToMidi(fmin) - Double(midiOffset)).roundedEven)
        for t in 0..<n {
            for f in 0..<bins where f >= maxIdx || f < minIdx {
                frames[t][f] = 0
                onsets[t][f] = 0
            }
        }
        // onsets inferred from jumps in the frames, as well as the model's own
        var diff = [[Double]](repeating: [Double](repeating: 0, count: bins), count: n)
        var maxDiff = 0.0, maxOnset = -Double.infinity
        for t in 0..<n {
            for f in 0..<bins {
                maxOnset = max(maxOnset, onsets[t][f])
                guard t >= 2 else { continue }
                let d1 = frames[t][f] - frames[t - 1][f]
                let d2 = frames[t][f] - frames[t - 2][f]
                let d = max(0, min(d1, d2))
                diff[t][f] = d
                maxDiff = max(maxDiff, d)
            }
        }
        // With no jump anywhere numpy divides by zero and every onset becomes NaN, so
        // none is a peak; the melodia trick still runs.
        let onsetsUsable = maxDiff > 0
        if onsetsUsable {
            for t in 0..<n {
                for f in 0..<bins { onsets[t][f] = max(onsets[t][f], maxOnset * diff[t][f] / maxDiff) }
            }
        }
        var remaining = frames
        var events = [Event]()
        var starts = [(Int, Int)]()
        if onsetsUsable && n >= 3 {
            for t in 1..<(n - 1) {
                for f in 0..<bins {
                    let x = onsets[t][f]
                    if x > onsets[t - 1][f] && x > onsets[t + 1][f] && x >= onsetThreshold { starts.append((t, f)) }
                }
            }
        }
        for (start, f) in starts.reversed() {
            if start >= n - 1 { continue }
            var i = start + 1, k = 0
            while i < n - 1 && k < energyTolerance {
                if remaining[i][f] < frameThreshold { k += 1 } else { k = 0 }
                i += 1
            }
            i -= k
            if i - start <= minNoteFrames { continue }
            for r in start..<i {
                remaining[r][f] = 0
                if f < maxFreqIdx { remaining[r][f + 1] = 0 }
                if f > 0 { remaining[r][f - 1] = 0 }
            }
            events.append(Event(start: Double(start), end: Double(i), midi: f + midiOffset,
                                amplitude: mean(frames, start, i, f)))
        }
        // the melodia trick: follow what energy is left from its loudest point
        while true {
            var best = -Double.infinity, bt = 0, bf = 0
            for t in 0..<n {
                for f in 0..<bins where remaining[t][f] > best { (best, bt, bf) = (remaining[t][f], t, f) }
            }
            if !(best > frameThreshold) { break }
            let f = bf
            remaining[bt][f] = 0
            func clear(_ i: Int) {
                remaining[i][f] = 0
                if f < maxFreqIdx { remaining[i][f + 1] = 0 }
                if f > 0 { remaining[i][f - 1] = 0 }
            }
            var i = bt + 1, k = 0
            while i < n - 1 && k < energyTolerance {
                if remaining[i][f] < frameThreshold { k += 1 } else { k = 0 }
                clear(i)
                i += 1
            }
            let end = i - 1 - k
            i = bt - 1
            k = 0
            while i > 0 && k < energyTolerance {
                if remaining[i][f] < frameThreshold { k += 1 } else { k = 0 }
                clear(i)
                i -= 1
            }
            let start = i + 1 + k
            if end - start <= minNoteFrames { continue }
            events.append(Event(start: Double(start), end: Double(end), midi: f + midiOffset,
                                amplitude: mean(frames, start, end, f)))
        }
        // frame -> seconds, with Basic Pitch's own per-window offset
        let windowOffset = (Double(fftHop) / Double(sr)) * (Double(framesPerWindow) - Double(windowSamples) / Double(fftHop)) + 0.0018
        func time(_ frame: Double) -> Double {
            frame * Double(fftHop) / Double(sr) - windowOffset * floor(frame / Double(framesPerWindow))
        }
        return events.map { Event(start: time($0.start), end: time($0.end), midi: $0.midi, amplitude: $0.amplitude) }
    }

    private static func mean(_ m: [[Double]], _ a: Int, _ b: Int, _ f: Int) -> Double {
        guard b > a else { return .nan }
        var s = 0.0
        for t in a..<b { s += m[t][f] }
        return s / Double(b - a)
    }

    /// The loudest note in each 10 ms frame (lab: basicpitch.skyline).
    static func skyline(_ events: [Event], durationMs: Double, frameMs: Double = 10) -> Track {
        let n = Int(durationMs / frameMs) + 1
        var owner = [Int](repeating: -1, count: n)
        var level = [Double](repeating: 0, count: n)
        for (i, ev) in events.enumerated() {
            let a = max(0, Int(ev.start * 1000 / frameMs)), b = min(n, Int(ev.end * 1000 / frameMs))
            guard a < b else { continue }
            for k in a..<b where ev.amplitude > level[k] { (level[k], owner[k]) = (ev.amplitude, i) }
        }
        var f0 = [Double](repeating: .nan, count: n), voiced = [Double](repeating: 0, count: n)
        for k in 0..<n where owner[k] >= 0 {
            f0[k] = 440.0 * pow(2, (Double(events[owner[k]].midi) - 69) / 12)
            voiced[k] = 1
        }
        return Track(times: (0..<n).map { Double($0) * frameMs }, f0: f0, voiced: voiced)
    }
}
