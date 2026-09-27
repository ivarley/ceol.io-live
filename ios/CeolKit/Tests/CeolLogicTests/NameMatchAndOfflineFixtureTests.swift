import Foundation
import Testing

@testable import CeolLogic

/// A name argument as the JS reads it: String(x || '') — a string as is, a number as
/// JS prints it, anything falsy as nil.
private func name(_ v: JSONValue?) -> String? {
    switch v {
    case .string(let s)?: return s
    case .number(let n)? where n != 0: return JSText.string(of: n)
    default: return nil
    }
}

let nameMatchAdapters = ModuleAdapters(
    functions: [
        "digitRuns": { args in .array(NameMatch.digitRuns(name(args["name"])).map(JSONValue.string)) },
        "parentheticals": { args in .array(NameMatch.parentheticals(name(args["name"])).map(JSONValue.string)) },
        "normalizeName": { args in .string(NameMatch.normalizeName(name(args["name"]))) },
        "normalizeNameOrdered": { args in .string(NameMatch.normalizeNameOrdered(name(args["name"]))) },
        "diceCoefficient": { args in
            .number(NameMatch.diceCoefficient(try args.require("a", \.stringValue), try args.require("b", \.stringValue)))
        },
        "sameName": { args in .bool(NameMatch.sameName(name(args["a"]), name(args["b"]))) },
        "meaningfullyDiffers": { args in .bool(NameMatch.meaningfullyDiffers(name(args["a"]), name(args["b"]))) },
        "pickAka": { args in
            // (chain || []).map(n => n == null ? '' : String(n).trim())
            let chain: [String?] = (args["chain"]?.arrayValue ?? []).map { v in
                switch v {
                case .string(let s): return s
                case .number(let n): return JSText.string(of: n)
                default: return nil
                }
            }
            return JSONValue(NameMatch.pickAka(chain))
        },
    ],
    constants: ["DICE_THRESHOLD": .number(NameMatch.diceThreshold)]
)

let offlineAdapters = ModuleAdapters(
    functions: [
        "queueOrder": { args in
            .array(OfflineRules.queueOrder(args["all"]?.arrayValue, sessionInstanceID: args["sessionInstanceId"] ?? .null))
        },
        "normMatchQuery": { args in .string(OfflineRules.normMatchQuery(args.string("s"))) },
        "matchCacheKey": { args in
            .string(OfflineRules.matchCacheKey(
                sessionInstanceID: args["sessionInstanceId"] ?? .null, kind: try args.require("kind", \.stringValue),
                args.string("s")))
        },
        "matchCacheRows": { args in
            .array(OfflineRules.matchCacheRows(
                sessionInstanceID: args["sessionInstanceId"] ?? .null, query: args.string("q"),
                verdict: try args.require("verdict", { $0 }), now: try args.require("now", \.doubleValue)))
        },
    ],
    constants: [:]
)

@Suite("namematch.fixtures.json")
struct NameMatchFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("namematch", nameMatchAdapters) }

    @Test("case", arguments: Fixtures.cases("namematch"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, nameMatchAdapters) }

    // The calibration sets, held to the web's bars (frontend/tests/namematch.test.js).
    struct Pair: Decodable, Sendable {
        let a: String
        let b: String
        let why: String?
    }

    struct Calibration: Decodable {
        let variants: [Pair]
        let distinct: [Pair]
    }

    static let calibration = try! JSONDecoder().decode(
        Calibration.self, from: Data(contentsOf: Fixtures.url("namematch")))

    @Test("suppresses true spelling variants (every one, and at least 95%)")
    func variants() {
        let pairs = Self.calibration.variants
        let misses = pairs.filter { !NameMatch.sameName($0.a, $0.b) }
        #expect(misses.map { "\($0.a) || \($0.b)  (\($0.why ?? ""))" } == [])
        #expect(Double(pairs.count - misses.count) / Double(pairs.count) >= 0.95)
    }

    @Test("never collapses a genuinely different name")
    func distinct() {
        let collapsed = Self.calibration.distinct.filter { NameMatch.sameName($0.a, $0.b) }
        #expect(collapsed.map { "\($0.a) || \($0.b)  (\($0.why ?? ""))" } == [])
    }
}

@Suite("offline.fixtures.json")
struct OfflineFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("offline", offlineAdapters) }

    @Test("case", arguments: Fixtures.cases("offline"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, offlineAdapters) }
}
