import Testing

@testable import CeolLogic

// MARK: - JSON <-> the port's types

private func records(_ args: Args, _ name: String) throws -> [LogRecord] {
    try args.require(name, \.arrayValue)
}

private func cursor(_ v: JSONValue?) throws -> Cursor {
    guard let v, !v.isNull else { return .end }
    if case .object = v {
        if let id = RecordID(v["newSet"]), !v["newSet"].isNullish { return .newSet(id) }
        if let id = RecordID(v["before"]), !v["before"].isNullish { return .before(id) }
        throw AdapterError.badInput("cursor object with neither newSet nor before")
    }
    guard let id = RecordID(v) else { throw AdapterError.badInput("cursor") }
    return .after(id)
}

private func json(_ c: Cursor) -> JSONValue {
    switch c {
    case .end: return .null
    case .after(let id): return id.json
    case .before(let id): return ["before": id.json]
    case .newSet(let id): return ["newSet": id.json]
    }
}

private func segments(_ v: JSONValue?) throws -> [LogSegment] {
    guard let arr = v?.arrayValue else { throw AdapterError.badInput("segments") }
    return try arr.map { seg in
        guard let tunes = seg["tunes"]?.arrayValue else { throw AdapterError.badInput("segments.tunes") }
        return LogSegment(tunes: tunes, breakAfter: RecordID(seg["breakAfter"]))
    }
}

private func json(_ seg: LogSegment) -> JSONValue {
    ["tunes": .array(seg.tunes), "breakAfter": seg.breakAfter?.json ?? .null]
}

private func stringArray(_ v: JSONValue?) throws -> [String] {
    guard let arr = v?.arrayValue else { throw AdapterError.badInput("strings") }
    return try arr.map { guard let s = $0.stringValue else { throw AdapterError.badInput("strings") }; return s }
}

/// JS String(raw) for the parsers: a string as is, a number as JS prints it.
private func rawText(_ v: JSONValue?) -> String? {
    switch v {
    case .string(let s)?: return s
    case .number(let n)?: return JSText.string(of: n)
    default: return nil
    }
}

// MARK: - Adapters

let logStateAdapters = ModuleAdapters(
    functions: [
        "nextTs": { args in
            // harness "clock": a fresh counter per case; clock[i] is Date.now() at call i.
            var clock = LogState.OpClock()
            let times = try args.require("clock", \.arrayValue)
            return .array(times.map { .number(Double(clock.next(now: Int64($0.doubleValue ?? 0)))) })
        },
        "computeOrdered": { args in .array(LogState.computeOrdered(try records(args, "records"))) },
        "segmentByBreaks": { args in .array(LogState.segmentByBreaks(try records(args, "ordered")).map(json)) },
        "setsOf": { args in .array(LogState.setsOf(try segments(args["segments"])).map(JSONValue.array)) },
        "tunesOf": { args in .array(LogState.tunesOf(try records(args, "ordered"))) },
        "pluralType": { args in JSONValue(LogState.pluralType(args.string("ty"))) },
        "setLabel": { args in .string(LogState.setLabel(try records(args, "setTunes"))) },
        "maxPos": { args in .string(LogState.maxPos(try records(args, "records"))) },
        "cursorPos": { args in
            let r = LogState.cursorPos(
                try cursor(args["insertAfterId"]), ordered: try records(args, "ordered"),
                allRecords: try records(args, "allRecords"))
            return ["afterId": r.afterID?.json ?? .null, "beforeId": r.beforeID?.json ?? .null, "position": .string(r.position)]
        },
        "remapAnchors": { args in
            var table: [String: JSONValue] = [:]
            for (k, v) in try args.map("tempToReal") {
                guard let key = k.stringValue else { throw AdapterError.badInput("tempToReal") }
                table[key] = v
            }
            let r = LogState.remapAnchors(try args.require("payload", \.objectValue), tempToReal: table)
            return ["payload": .object(r.payload), "skip": .bool(r.skip)]
        },
        "stripThe": { args in .string(LogState.stripThe(try args.require("s", \.stringValue))) },
        "normName": { args in .string(LogState.normName(args.string("s"))) },
        "openSetMergeTarget": { args in
            LogState.openSetMergeTarget(try args.require("payload", { $0 }), ordered: try records(args, "ordered")) ?? .null
        },
        "mergeStable": { args in
            .array(LogState.mergeStable(try records(args, "localList"), try records(args, "serverList")))
        },
        "parseThesessionId": { args in JSONValue(TheSession.tuneID(rawText(args["raw"]))) },
        "parseThesessionSettingId": { args in JSONValue(TheSession.settingID(rawText(args["raw"]))) },
        "computeCursorSlots": { args in
            let slots = LogState.computeCursorSlots(
                try segments(args["segments"]), endIsOpen: args["endIsOpen"].isTruthy, hasOrdered: args["hasOrdered"].isTruthy)
            return .array(slots.map(json))
        },
        "seamKeyFor": { args in .string(LogState.seamKey(for: try cursor(args["s"]))) },
        "seamActionFor": { args in
            switch LogState.seamAction(for: try cursor(args["insertAfterId"]), segments: try segments(args["segments"])) {
            case nil: return .null
            case .join(let br)?: return ["type": "join", "breakId": br.json]
            case .split(let id)?: return ["type": "split", "tuneId": JSONValue(id)]
            }
        },
        "rememberInHistory": { args in
            var hist = try stringArray(args["hist"])
            LogState.rememberInHistory(&hist, args.string("q"))
            return .array(hist.map(JSONValue.string))
        },
        "historyStep": { args in
            let step = LogState.historyStep(
                try stringArray(args["hist"]), pos: args["pos"]?.intValue, dir: try args.require("dir", \.doubleValue))
            guard let step else { return .null }
            return ["pos": JSONValue(step.pos), "value": .string(step.value)]
        },
        "recordChanges": { args in
            let c = LogState.recordChanges(args["d"])
            return ["puts": .array(c.puts), "drops": .array(c.drops)]
        },
        "metaChanges": { args in .object(LogState.metaChanges(args["d"])) },
    ],
    constants: [:]
)

@Suite("logstate.fixtures.json")
struct LogStateFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("logstate", logStateAdapters) }

    @Test("case", arguments: Fixtures.cases("logstate"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, logStateAdapters) }
}
