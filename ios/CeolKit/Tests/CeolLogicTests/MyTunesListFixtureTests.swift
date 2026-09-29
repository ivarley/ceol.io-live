// The Tunes tab's list rules, held to frontend/src/mytunespage/logic.fixtures.json.

import Testing

@testable import CeolLogic

private func item(_ t: JSONValue) -> MyTunesList.Item {
    var overrides: [String: String] = [:]
    for (k, v) in t["instrument_status"]?.objectValue ?? [:] { if let s = v.stringValue { overrides[k] = s } }
    return MyTunesList.Item(
        tuneID: t["tune_id"]?.intValue ?? 0, name: t["tune_name"]?.stringValue ?? "", type: t["tune_type"]?.stringValue,
        status: t["learn_status"]?.stringValue ?? "", notes: t["notes"]?.stringValue,
        addedDay: t["created_date"]?.stringValue.map { String($0.prefix(10)) },
        tunebookCount: t["tunebook_count"]?.intValue, heardCount: t["heard_count"]?.intValue,
        memberPlays: t["member_play_count"]?.intValue, sessionPlays: t["session_play_count"]?.intValue,
        attendedPlays: t["attended_play_count"]?.intValue, instrumentStatus: overrides)
}

private func filters(_ f: JSONValue?) -> MyTunesList.Filters {
    var out = MyTunesList.Filters()
    out.search = f?["search"]?.stringValue ?? ""
    out.type = f?["type"]?.stringValue ?? ""
    out.status = f?["status"]?.stringValue ?? ""
    out.instrument = f?["instrument"]?.stringValue ?? ""
    out.rel = f?["rel"]?.stringValue ?? ""
    out.addedBefore = f?["addedDir"]?.stringValue == "before"
    out.addedDate = f?["addedDate"]?.stringValue ?? ""
    return out
}

private func instruments(_ v: JSONValue?) -> [MyTunesList.Instrument] {
    (v?.arrayValue ?? []).map { .init(name: $0["instrument"]?.stringValue ?? "", isAuto: $0["is_auto"]?.boolValue ?? false) }
}

let myTunesAdapters = ModuleAdapters(
    functions: [
        "filterAndSort": { args in
            let all = try args.require("allTunes", \.arrayValue)
            let s = args["sort"]
            let sort = MyTunesList.Sort(
                type: s?["type"]?.stringValue ?? "alpha", descending: s?["dir"]?.stringValue == "desc",
                type2: s?["type2"]?.stringValue, descending2: s?["dir2"]?.stringValue == "desc")
            let rows = MyTunesList.filterAndSort(
                all.map(item), filters: filters(args["filters"]), sort: sort, instruments: instruments(args["instruments"]))
            // The web returns the tune objects themselves (copies, with the flags added).
            let byID = Dictionary(all.map { ($0["tune_id"]?.intValue ?? 0, $0) }, uniquingKeysWith: { a, _ in a })
            return .array(rows.map { row in
                var o = byID[row.item.tuneID]?.objectValue ?? [:]
                if !filters(args["filters"]).instrument.isEmpty {
                    o["_instDimmed"] = .bool(row.dimmed)
                    o["_abcOnly"] = .bool(row.abcOnly)
                }
                return .object(o)
            })
        },
        "resultsCountText": { args in
            let filtered = try args.require("filtered", \.arrayValue)
            let rows = filtered.map {
                MyTunesList.Row(item: .init(tuneID: 0, name: "", type: nil, status: ""), dimmed: $0["_instDimmed"]?.boolValue ?? false, abcOnly: false)
            }
            return .string(MyTunesList.resultsCountText(rows, total: args["total"]?.intValue ?? 0, filters: filters(args["filters"])))
        },
        "noResultsMessage": { args in .string(MyTunesList.noResultsMessage(filters(args["filters"]))) },
        "typeBadgeLabel": { args in
            .string(MyTunesList.typeBadgeLabel(item(try args.require("tune") { $0 }), sortType: args.string("sortType") ?? ""))
        },
        "typeBadgeTitle": { args in .string(MyTunesList.typeBadgeTitle(args.string("sortType") ?? "")) },
        "sortModeLabel": { args in .string(MyTunesList.sortModeLabel(args.string("id") ?? "")) },
        "memberPlays": { args in JSONValue(item(try args.require("tune") { $0 }).plays) },
        "attendedPlays": { args in JSONValue(item(try args.require("tune") { $0 }).attended) },
        "resolveTuneInstrumentStatus": { args in
            MyTunesList.instrumentStatus(
                item(try args.require("tune") { $0 }), instruments: instruments(args["instruments"]),
                name: args.string("instrumentName") ?? ""
            ).map(JSONValue.string) ?? .null
        },
    ],
    constants: [
        "SORT_MODES": .array(MyTunesList.sortModes.map { ["id": .string($0.id), "label": .string($0.label)] })
    ]
)

@Suite("mytunespage/logic.fixtures.json")
struct MyTunesListFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("mytunes", myTunesAdapters) }

    @Test("case", arguments: Fixtures.cases("mytunes"))
    func run(_ c: FunctionCase) throws { try Fixtures.run(c, myTunesAdapters) }
}
