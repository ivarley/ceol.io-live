// The Swift twin of frontend/tests/fixtures.test.js: it reads the SAME fixture files,
// in place in frontend/src (found from this file's own path — these tests run on the
// Mac, in the repo), and holds the ported logic to them. The web's runner and this one follow the same rules, so a case
// means the same thing on both sides:
//
//   functions.<name>.params    argument names in call order. An input key that is
//                              ABSENT means the argument was not passed (its default
//                              applies) — `args["x"] == nil` here, never `.null`.
//   functions.<name>.mapParams params that are a JS Map, written as [[key, value], ...]
//   functions.<name>.returns   "map": the result is a Map, compared as [[key, value], ...]
//   functions.<name>.harness   "clock": see nextTs
//   cases                      [{ name, input, expected }] or [{ name, input, throws: true }]
//   constants                  exported values, compared exactly
//   _not_fixtured              exports with no cases, and why
//
// Results are compared as JSON values, which is what a JSON round trip of the JS
// result gives. Each module's adapters (FixtureAdapters+<Module>.swift) turn a case's
// JSON input into Swift arguments and the Swift result back into JSON.

import Foundation
import Testing

@testable import CeolLogic

struct FixtureFile: Decodable, Sendable {
    let functions: [String: FunctionSpec]
    let constants: [String: JSONValue]?
    let notFixtured: [String: String]?

    enum CodingKeys: String, CodingKey {
        case functions, constants
        case notFixtured = "_not_fixtured"
    }
}

struct FunctionSpec: Decodable, Sendable {
    let params: [String]?
    let mapParams: [String]?
    let returns: String?
    let harness: String?
    let cases: [FixtureCase]
}

struct FixtureCase: Decodable, Sendable, CustomTestStringConvertible {
    let name: String
    let input: [String: JSONValue]
    let expected: JSONValue?
    let `throws`: Bool?
    let note: String?

    var testDescription: String { name }
}

/// A case's arguments, by parameter name. nil = not passed.
struct Args: Sendable {
    let values: [String: JSONValue]
    subscript(_ name: String) -> JSONValue? { values[name] }
}

typealias Adapter = @Sendable (Args) throws -> JSONValue

/// One module's port, as the runner sees it.
struct ModuleAdapters: Sendable {
    let functions: [String: Adapter]
    let constants: [String: JSONValue]
}

enum Fixtures {
    /// Module name -> its fixture file, relative to frontend/src.
    static let paths = [
        "fracindex": "fracindex.fixtures.json",
        "logstate": "logstate.fixtures.json",
        "offline": "offline.fixtures.json",
        "abcquery": "shared/abcquery.fixtures.json",
        "segments": "shared/segments.fixtures.json",
        "namematch": "tunesheet/namematch.fixtures.json",
        "addsession": "addsession/logic.fixtures.json",
        "sessionpath": "shared/sessionpath.fixtures.json",
        "parse": "shared/parse.fixtures.json",
    ]

    /// frontend/src, from ios/CeolKit/Tests/CeolLogicTests/FixtureRunner.swift.
    static let frontendSrc = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()  // CeolLogicTests
        .deletingLastPathComponent()  // Tests
        .deletingLastPathComponent()  // CeolKit
        .deletingLastPathComponent()  // ios
        .deletingLastPathComponent()  // repo root
        .appendingPathComponent("frontend/src")

    static func url(_ module: String) -> URL { frontendSrc.appendingPathComponent(paths[module]!) }

    static func load(_ module: String) -> FixtureFile {
        try! JSONDecoder().decode(FixtureFile.self, from: Data(contentsOf: url(module)))
    }

    /// Every (function, case) in a module's file, for a parameterized test.
    static func cases(_ module: String) -> [FunctionCase] {
        let file = load(module)
        return file.functions.keys.sorted().flatMap { fn in
            file.functions[fn]!.cases.map { FunctionCase(function: fn, spec: file.functions[fn]!, testCase: $0) }
        }
    }

    /// Run one case against the module's adapters.
    static func run(_ fc: FunctionCase, _ adapters: ModuleAdapters) throws {
        let adapter = try #require(adapters.functions[fc.function], "no Swift port of \(fc.function)")
        let args = Args(values: fc.testCase.input)
        if fc.testCase.throws == true {
            #expect(throws: (any Error).self, "\(fc.function): \(fc.testCase.name) must refuse") {
                _ = try adapter(args)
            }
            return
        }
        let actual = try adapter(args)
        #expect(
            actual == (fc.testCase.expected ?? .null),
            "\(fc.function): \(fc.testCase.name)\(fc.testCase.note.map { " — \($0)" } ?? "")"
        )
    }

    /// The guard, as in the web runner: every function in the file has a Swift port,
    /// every constant matches, and the port adds nothing the file doesn't know about.
    static func checkCoverage(_ module: String, _ adapters: ModuleAdapters) {
        let file = load(module)
        let missing = Set(file.functions.keys).subtracting(adapters.functions.keys)
        #expect(missing.isEmpty, "\(module): no Swift port of \(missing.sorted())")
        let stale = Set(adapters.functions.keys).subtracting(file.functions.keys)
        #expect(stale.isEmpty, "\(module): adapters for functions the fixtures don't have: \(stale.sorted())")
        for (name, value) in file.constants ?? [:] {
            #expect(adapters.constants[name] == value, "\(module): constant \(name)")
        }
        let extraConstants = Set(adapters.constants.keys).subtracting((file.constants ?? [:]).keys)
        #expect(extraConstants.isEmpty, "\(module): constants the fixtures don't pin: \(extraConstants.sorted())")
    }
}

struct FunctionCase: Sendable, CustomTestStringConvertible {
    let function: String
    let spec: FunctionSpec
    let testCase: FixtureCase
    var testDescription: String { "\(function): \(testCase.name)" }
}

// MARK: - Conversions shared by the adapters

enum AdapterError: Error {
    case badInput(String)
}

extension Args {
    /// A string argument; nil when absent or null (JS `undefined`/`null`).
    func string(_ name: String) -> String? { self[name]?.stringValue }

    func require<T>(_ name: String, _ get: (JSONValue) -> T?) throws -> T {
        guard let v = self[name], let t = get(v) else { throw AdapterError.badInput(name) }
        return t
    }

    /// A Map param written as [[key, value], ...].
    func map(_ name: String) throws -> [(JSONValue, JSONValue)] {
        guard let pairs = self[name]?.arrayValue else { throw AdapterError.badInput(name) }
        return try pairs.map { pair in
            guard let kv = pair.arrayValue, kv.count == 2 else { throw AdapterError.badInput(name) }
            return (kv[0], kv[1])
        }
    }
}
