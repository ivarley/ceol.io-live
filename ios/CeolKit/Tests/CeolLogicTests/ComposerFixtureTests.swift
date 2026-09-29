import Testing

@testable import CeolLogic

private func tune(_ v: JSONValue) -> VocabTune? {
    guard let id = v["tune_id"]?.intValue else { return nil }
    return VocabTune(tuneID: id, name: v["name"]?.stringValue ?? "", tuneType: v["tune_type"]?.stringValue, abc: v["abc"] == true)
}

private func ids(_ m: [String: [Int]]) -> JSONValue { .object(m.mapValues { .array($0.map { JSONValue($0) }) }) }

private func json(_ index: VocabIndex?) -> JSONValue {
    guard let index else { return .null }
    return [
        "alias": ids(index.alias), "name": ids(index.name),
        "byId": .object(Dictionary(uniqueKeysWithValues: index.byID.map { (String($0.key), $0.value.json) })),
        "list": .array(index.list.map {
            ["tune_id": JSONValue($0.tuneID), "name": .string($0.name), "tune_type": $0.tuneType.map(JSONValue.string) ?? .null,
             "nn": .string($0.nn), "aliases": .array($0.aliases.map(JSONValue.string)), "abc": .string($0.abc),
             "idx": JSONValue($0.idx)]
        }),
        "next": .object(Dictionary(uniqueKeysWithValues: index.next.map { (String($0.key), $0.value.json) })),
    ]
}

private func index(_ v: JSONValue?) -> VocabIndex? {
    guard let v, !v.isNull else { return nil }
    func idMap(_ m: JSONValue?) -> [String: [Int]] {
        guard case .object(let o)? = m else { return [:] }
        return o.mapValues { ($0.arrayValue ?? []).compactMap(\.intValue) }
    }
    func tuneMap(_ m: JSONValue?) -> [Int: VocabTune] {
        guard case .object(let o)? = m else { return [:] }
        var out: [Int: VocabTune] = [:]
        for (k, t) in o { if let id = Int(k), let t = tune(t) { out[id] = t } }
        return out
    }
    var i = VocabIndex()
    i.alias = idMap(v["alias"])
    i.name = idMap(v["name"])
    i.byID = tuneMap(v["byId"])
    i.next = tuneMap(v["next"])
    i.list = (v["list"]?.arrayValue ?? []).map {
        .init(tuneID: $0["tune_id"]?.intValue ?? 0, name: $0["name"]?.stringValue ?? "", tuneType: $0["tune_type"]?.stringValue,
              nn: $0["nn"]?.stringValue ?? "", aliases: ($0["aliases"]?.arrayValue ?? []).compactMap(\.stringValue),
              abc: $0["abc"]?.stringValue ?? "", idx: $0["idx"]?.intValue ?? 0)
    }
    return i
}

private func cursor(_ v: JSONValue?) throws -> Cursor {
    guard let v, !v.isNull else { return .end }
    if case .object = v {
        if let id = RecordID(v["newSet"]) { return .newSet(id) }
        if let id = RecordID(v["before"]) { return .before(id) }
        throw AdapterError.badInput("cursor")
    }
    guard let id = RecordID(v) else { throw AdapterError.badInput("cursor") }
    return .after(id)
}

private func segment(_ v: JSONValue?) -> LogSegment? {
    guard let v, !v.isNull else { return nil }
    return LogSegment(tunes: v["tunes"]?.arrayValue ?? [], breakAfter: RecordID(v["breakAfter"]))
}

private func json(_ seg: LogSegment?) -> JSONValue {
    guard let seg else { return .null }
    return ["tunes": .array(seg.tunes), "breakAfter": seg.breakAfter?.json ?? .null]
}

let composerAdapters = ModuleAdapters(
    functions: [
        "buildVocabIndex": { args in json(Composer.buildIndex(known: args["known"]?.arrayValue, aliases: args["aliases"]?.arrayValue)) },
        "resolveLocal": { args in Composer.resolveLocal(index(args["index"]), args.string("q") ?? "")?.json ?? .null },
        "resolveLocalMany": { args in
            .array(Composer.resolveLocalMany(
                index(args["index"]), args.string("q") ?? "", limit: args["limit"]?.intValue ?? 8,
                preferType: args.string("preferType"), inSet: (args["inSetIds"]?.arrayValue ?? []).compactMap(\.intValue)
            ).map(\.json))
        },
        "cursorSegment": { args in
            json(Composer.cursorSegment(try segments(args["segments"]), endIsOpen: args["endIsOpen"].isTruthy, cursor: try cursor(args["insertAfterId"])))
        },
        "setTuneType": { args in Composer.setTuneType(segment(args["seg"])).map(JSONValue.string) ?? .null },
        "setTuneIds": { args in .array(Composer.setTuneIDs(segment(args["seg"])).map { JSONValue($0) }) },
        "nextAssocKey": { args in
            .string(Composer.nextAssocKey(try args.require("anchorId", \.intValue), try args.require("nextId", \.intValue)))
        },
        "likelyNext": { args in
            Composer.likelyNext(
                index(args["index"]), seg: segment(args["seg"]), cursor: try cursor(args["insertAfterId"]),
                dismissed: (args["dismissed"]?.arrayValue ?? []).compactMap(\.stringValue))?.json ?? .null
        },
        "nextMatchesInput": { args in .bool(Composer.nextMatchesInput(args["nx"].flatMap(tune), args.string("input") ?? "")) },
        "commitStep": { args in
            let s = args["shown"]
            let shown = Composer.Shown(
                query: s?["query"]?.stringValue, results: s?["results"]?.arrayValue ?? [], searching: s?["searching"].isTruthy ?? false,
                noMatch: s?["noMatch"].isTruthy ?? false, exact: s?["exact"].isTruthy ?? false)
            switch Composer.commitStep(index(args["index"]), args.string("q") ?? "", shown: shown) {
            case nil: return .null
            case .pick(let t)?: return ["action": "pick", "tune": t]
            case .submit?: return ["action": "submit"]
            case .ambiguous?: return ["action": "ambiguous"]
            case .resolve?: return ["action": "resolve"]
            }
        },
        "resolution": { args in
            switch Composer.resolution(args["m"]) {
            case .unlinked: return ["kind": "unlinked"]
            case .linked(let t): return ["kind": "linked", "tune": t.json]
            case .ambiguous(let rs): return ["kind": "ambiguous", "results": .array(rs)]
            }
        },
        "withNotationResults": { args in
            Composer.withNotationResults(try args.require("m") { $0 }, abc: args["abc"]?.arrayValue ?? [])
        },
    ],
    constants: [:]
)

@Suite("composer.fixtures.json")
struct ComposerFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("composer", composerAdapters) }

    @Test("case", arguments: Fixtures.cases("composer"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, composerAdapters) }
}
