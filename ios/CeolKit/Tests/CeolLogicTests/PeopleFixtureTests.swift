import Testing

@testable import CeolLogic

let peopleAdapters = ModuleAdapters(
    functions: [
        "colorFor": { args in .string(People.color(try args.require("seq", \.intValue))) },
        "initials": { args in .string(People.initials(args.string("name"))) },
        "loggerColorIdx": { args in
            People.loggerColorIndex(args["r"] ?? .null, me: args["myPersonId"]?.intValue, roster: args["roster"]?.arrayValue ?? [])
                .map { JSONValue($0) } ?? .null
        },
        "othersTyping": { args in .array(People.othersTyping(args["typers"]?.arrayValue, me: args["myPersonId"]?.intValue)) },
        "pickerTiers": { args in
            let t = People.pickerTiers(args["people"]?.arrayValue, query: args.string("query"))
            return ["here": .array(t.here), "roster": .array(t.roster), "archived": .array(t.archived)]
        },
        "remoteLabel": { args in People.remoteLabel(args["d"] ?? .null).map(JSONValue.string) ?? .null },
        "activityText": { args in
            People.activityText(args["d"] ?? .null, me: args["myPersonId"]?.intValue, viewing: args["viewing"].isTruthy)
                .map(JSONValue.string) ?? .null
        },
        "splitName": { args in
            let n = People.splitName(args.string("query"))
            return ["first": .string(n.first), "last": .string(n.last)]
        },
    ],
    constants: ["PALETTE": .array(People.palette.map(JSONValue.string)), "MAX_ACTIVITY": JSONValue(People.maxActivity)]
)

@Suite("people.fixtures.json")
struct PeopleFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("people", peopleAdapters) }

    @Test("case", arguments: Fixtures.cases("people"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, peopleAdapters) }
}
