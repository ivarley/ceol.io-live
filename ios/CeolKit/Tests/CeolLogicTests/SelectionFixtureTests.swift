import Testing

@testable import CeolLogic

private func ids(_ v: JSONValue?) throws -> [RecordID] {
    guard let arr = v?.arrayValue else { throw AdapterError.badInput("ids") }
    return try arr.map { guard let id = RecordID($0) else { throw AdapterError.badInput("id") }; return id }
}

private func json(_ ids: [RecordID]) -> JSONValue { .array(ids.map(\.json)) }

private func json(_ t: Selection.DropTarget) -> JSONValue {
    ["key": .string(t.key), "after_record_id": t.afterID?.json ?? .null, "before_record_id": t.beforeID?.json ?? .null,
     "new_set": .bool(t.newSet)]
}

private func clip(_ t: Selection.ClipTune, withType: Bool) -> JSONValue {
    var o: [String: JSONValue] = ["tune_id": t.tuneID.map { JSONValue($0) } ?? .null, "name": .string(t.name)]
    if withType { o["tune_type"] = t.tuneType.map(JSONValue.string) ?? .null }
    return .object(o)
}

private func clipSets(_ v: JSONValue?) -> [[Selection.ClipTune]] {
    (v?.arrayValue ?? []).map { set in
        (set.arrayValue ?? []).map {
            Selection.ClipTune(tuneID: $0["tune_id"]?.intValue, name: $0["name"]?.stringValue ?? "",
                               tuneType: $0["tune_type"]?.stringValue)
        }
    }
}

let selectionAdapters = ModuleAdapters(
    functions: [
        "dragBlock": { args in
            guard let grabbed = RecordID(args["grabbedId"]) else { throw AdapterError.badInput("grabbedId") }
            guard let b = Selection.dragBlock(try args.require("ordered", \.arrayValue),
                                              selected: Set(try ids(args["selectedIds"])), grabbed: grabbed)
            else { return .null }
            return ["tuneIds": json(b.tuneIDs), "recordIds": json(b.recordIDs), "setCount": JSONValue(b.setCount)]
        },
        "dropTargets": { args in
            .array(Selection.dropTargets(
                try args.require("ordered", \.arrayValue), segments: try segments(args["segments"]),
                endIsOpen: args["endIsOpen"].isTruthy, block: try ids(args["blockRecordIds"])).map(json))
        },
        "optimisticMove": { args in
            let t = args["target"]
            let target = Selection.DropTarget(
                key: "", afterID: RecordID(t?["after_record_id"]), beforeID: RecordID(t?["before_record_id"]),
                newSet: t?["new_set"].isTruthy ?? false)
            let m = Selection.optimisticMove(
                try args.require("ordered", \.arrayValue), allRecords: try args.require("allRecords", \.arrayValue),
                block: try ids(args["blockRecordIds"]), target: target)
            return [
                "positions": .array(m.positions.map { .array([$0.0.json, .string($0.1)]) }),
                "tempBreakKeys": ["before": m.tempBreakBefore.map(JSONValue.string) ?? .null,
                                  "after": m.tempBreakAfter.map(JSONValue.string) ?? .null],
            ]
        },
        "serializeClipboard": { args in
            guard let c = Selection.serializeClipboard(try segments(args["segments"]), selected: Set(try ids(args["selectedIds"])))
            else { return .null }
            return ["text": .string(c.text), "rich": .array(c.rich.map { .array($0.map { clip($0, withType: true) }) })]
        },
        "parseClipboard": { args in
            let last = args["lastCopy"].flatMap { v -> Selection.Copy? in
                guard let text = v["text"]?.stringValue else { return nil }
                return Selection.Copy(text: text, rich: clipSets(v["rich"]))
            }
            guard let p = Selection.parseClipboard(args.string("text"), lastCopy: last) else { return .null }
            let typed = p.kind == .internal
            return ["kind": .string(p.kind.rawValue), "sets": .array(p.sets.map { .array($0.map { clip($0, withType: typed) }) })]
        },
        "rangeBetween": { args in
            guard let target = RecordID(args["targetId"]) else { throw AdapterError.badInput("targetId") }
            return json(Selection.rangeBetween(try args.require("ordered", \.arrayValue), anchor: RecordID(args["anchorId"]), target: target))
        },
        "selectableIds": { args in
            json(Selection.selectableIDs(try segments(args["segments"]), filter: args.string("filterText")))
        },
    ],
    constants: [:]
)

@Suite("selection.fixtures.json")
struct SelectionFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("selection", selectionAdapters) }

    @Test("case", arguments: Fixtures.cases("selection"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, selectionAdapters) }
}
