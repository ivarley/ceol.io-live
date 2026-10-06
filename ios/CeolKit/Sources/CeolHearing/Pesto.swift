// PESTO (Riou et al., ISMIR 2023) as the lab's PestoFrontEnd runs it: the network as a
// Core ML model (`python -m lab coreml`: its spectrum taken as magnitudes, any length from
// 0.5 to 30 s), then PESTO's roll and argmax-local weighted average to a pitch per 10 ms.

import CoreML
import Foundation

enum Pesto {
    static let binsPerSemitone = 3
    /// round(model.shift * bins_per_semitone) for mir-1k_g7.
    static let shiftBins = 20

    static func track(_ y: [Float], model: MLModel) throws -> Track {
        let input = try MLMultiArray(shape: [1, NSNumber(value: y.count)], dataType: .float32)
        let p = input.dataPointer.bindMemory(to: Float.self, capacity: y.count)
        for i in 0..<y.count { p[i] = y[i] }
        let out = try model.prediction(from: MLDictionaryFeatureProvider(dictionary: ["audio": input]))
        let act = out.featureValue(for: "activations")!.multiArrayValue!
        let conf = out.featureValue(for: "confidence")!.multiArrayValue!
        let frames = act.shape[0].intValue, bins = act.shape[act.shape.count - 1].intValue
        let rows = BasicPitch.rows(reshaped(act, frames, bins))
        var f0 = [Double](repeating: .nan, count: frames), voiced = [Double](repeating: 0, count: frames)
        let c = flat(conf)
        for t in 0..<frames {
            let semitones = pitch(rows[t])
            f0[t] = 440.0 * pow(2, (Double(semitones) - 69) / 12)
            voiced[t] = Double(c[t])
        }
        return Track(times: (0..<frames).map { Double($0) * 10 }, f0: f0, voiced: voiced)
    }

    /// The roll, then the argmax-local weighted average (pesto.utils.reduce_activations,
    /// "alwa"), in fractional MIDI semitones.
    static func pitch(_ raw: [Float]) -> Float {
        let n = raw.count
        let a = (0..<n).map { raw[($0 + shiftBins) % n] }
        var center = 0
        for i in 1..<n where a[i] > a[center] { center = i }
        var num: Float = 0, den: Float = 0
        for w in (1 - binsPerSemitone)...(binsPerSemitone - 1) {
            let i = min(max(center + w, 0), n - 1)
            num += a[i] * (Float(i) / Float(binsPerSemitone))
            den += a[i]
        }
        return num / den
    }

    private static func reshaped(_ a: MLMultiArray, _ frames: Int, _ bins: Int) -> MLMultiArray {
        if a.shape.count == 3 { return a }
        // (frames, bins) -> (1, frames, bins) for `rows`
        let r = try! MLMultiArray(shape: [1, NSNumber(value: frames), NSNumber(value: bins)], dataType: .float32)
        let src = flat(a)
        let p = r.dataPointer.bindMemory(to: Float.self, capacity: frames * bins)
        for i in 0..<(frames * bins) { p[i] = src[i] }
        return r
    }

    /// Every value in order, whatever the array's strides (row-major over its shape).
    static func flat(_ a: MLMultiArray) -> [Float] {
        let shape = a.shape.map(\.intValue), st = a.strides.map(\.intValue)
        let count = shape.reduce(1, *)
        var out = [Float](repeating: 0, count: count)
        var idx = [Int](repeating: 0, count: shape.count)
        for o in 0..<count {
            var off = 0
            for d in 0..<shape.count { off += idx[d] * st[d] }
            switch a.dataType {
            case .float16: out[o] = Float(a.dataPointer.bindMemory(to: Float16.self, capacity: a.count)[off])
            default: out[o] = a.dataPointer.bindMemory(to: Float.self, capacity: a.count)[off]
            }
            var d = shape.count - 1
            while d >= 0 {
                idx[d] += 1
                if idx[d] < shape[d] { break }
                idx[d] = 0
                d -= 1
            }
        }
        return out
    }
}
