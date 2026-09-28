// Adding a session, held to the web's own cases: addsession/logic.fixtures.json,
// shared/sessionpath.fixtures.json and shared/parse.fixtures.json.

import Testing

@testable import CeolLogic

/// What JS's String(x) gives for the fields thesession.org's JSON may send as numbers;
/// nil for absent or null (the `?? ''` the web applies).
private func jsString(_ v: JSONValue?) -> String? {
    switch v {
    case .string(let s)?: return s
    case .number(let n)?: return JSText.string(of: n)
    case .bool(let b)?: return b ? "true" : "false"
    default: return nil
    }
}

private func scheduleJSON(_ s: AddSession.Schedule?) -> JSONValue {
    guard let s else { return .null }
    var o: [String: JSONValue] = [
        "type": .string(s.kind.rawValue), "weekday": .string(s.weekday),
        "start_time": .string(s.startTime), "end_time": .string(s.endTime),
    ]
    if let n = s.everyNWeeks { o["every_n_weeks"] = JSONValue(n) }
    if let w = s.which { o["which"] = .array(w.map { JSONValue($0) }) }
    return .object(o)
}

let addSessionAdapters = ModuleAdapters(
    functions: [
        "parseSessionInput": { args in
            switch AddSession.parseSessionInput(args.string("input")) {
            case .id(let id): return ["kind": "id", "id": .string(id)]
            case .search(let q): return ["kind": "search", "query": .string(q)]
            }
        },
        "generatePath": { args in
            .string(AddSession.generatePath(city: jsString(args["city"]), sessionName: jsString(args["sessionName"])))
        },
        "guessTimezone": { args in
            let country = args.string("country"), state = args.string("state")
            if let fallback = args.string("fallback") {
                return .string(AddSession.guessTimezone(country: country, state: state, fallback: fallback))
            }
            return .string(AddSession.guessTimezone(country: country, state: state))
        },
        "parseTheSessionRecurrence": { args in
            // text: a string, or an array of lines joined with spaces (JS Array.join).
            let text: String? =
                switch args["text"] {
                case .string(let s)?: s
                case .array(let lines)?: lines.map { jsString($0) ?? "" }.joined(separator: " ")
                default: nil
                }
            let comments = args["comments"]?.arrayValue?.map { jsString($0["content"]) ?? "" }
            return scheduleJSON(AddSession.parseTheSessionRecurrence(text: text, comments: comments))
        },
        "summarizeRecurrence": { args in
            let st = try args.require("state", \.objectValue)
            let r = AddSession.summarizeRecurrence(
                type: st["type"]?.stringValue, weekday: st["weekday"]?.stringValue,
                frequency: st["frequency"]?.intValue ?? 1,
                which: st["which"]?.arrayValue?.compactMap(\.intValue) ?? [],
                startTime: st["startTime"]?.stringValue ?? "", endTime: st["endTime"]?.stringValue ?? "")
            return ["summary": .string(r.summary), "json": r.json.map(JSONValue.string) ?? .null]
        },
    ],
    constants: [:]
)

let sessionPathAdapters = ModuleAdapters(
    functions: [
        "normalizeSessionPath": { args in
            // A non-string (a number, null) is "Path is required", as in JS.
            let r = SessionPath.normalize(args["value"]?.stringValue)
            return ["path": r.path.map(JSONValue.string) ?? .null, "error": r.error.map(JSONValue.string) ?? .null]
        }
    ],
    constants: [:]
)

let parseAdapters = ModuleAdapters(
    functions: [
        "parseThesessionSessionId": { args in
            TheSession.sessionID(jsString(args["raw"])).map { JSONValue($0) } ?? .null
        }
    ],
    constants: [:]
)

@Suite("addsession/logic.fixtures.json")
struct AddSessionFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("addsession", addSessionAdapters) }

    @Test("case", arguments: Fixtures.cases("addsession"))
    func run(_ c: FunctionCase) throws { try Fixtures.run(c, addSessionAdapters) }
}

@Suite("shared/sessionpath.fixtures.json")
struct SessionPathFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("sessionpath", sessionPathAdapters) }

    @Test("case", arguments: Fixtures.cases("sessionpath"))
    func run(_ c: FunctionCase) throws { try Fixtures.run(c, sessionPathAdapters) }
}

@Suite("shared/parse.fixtures.json")
struct ParseFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("parse", parseAdapters) }

    @Test("case", arguments: Fixtures.cases("parse"))
    func run(_ c: FunctionCase) throws { try Fixtures.run(c, parseAdapters) }
}
