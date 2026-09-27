import Testing

@testable import CeolLogic

let fracIndexAdapters = ModuleAdapters(
    functions: [
        "generateAppend": { args in .string(FracIndex.generateAppend(args.string("last"))) },
        "generateBetween": { args in .string(try FracIndex.generateBetween(args.string("before"), args.string("after"))) },
        "optimisticBetween": { args in .string(FracIndex.optimisticBetween(args.string("before"), args.string("after"))) },
    ],
    constants: [:]
)

@Suite("fracindex.fixtures.json")
struct FracIndexFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("fracindex", fracIndexAdapters) }

    @Test("case", arguments: Fixtures.cases("fracindex"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, fracIndexAdapters) }
}
