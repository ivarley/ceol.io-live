import Testing

@testable import CeolLogic

let abcQueryAdapters = ModuleAdapters(
    functions: [
        "normAbc": { args in .string(ABCQuery.normAbc(args.string("s"))) },
        "looksLikeAbc": { args in .bool(ABCQuery.looksLikeAbc(args.string("q"))) },
        "abcNeedle": { args in
            if let min = args["min"]?.intValue {
                return .string(ABCQuery.abcNeedle(args.string("q"), min: min))
            }
            return .string(ABCQuery.abcNeedle(args.string("q")))
        },
    ],
    constants: ["ABC_MIN_QUERY_LEN": JSONValue(ABCQuery.minQueryLength)]
)

// MARK: - segments

private func resolvedJSON(_ r: Segments.Resolved) -> JSONValue {
    [
        "startMs": .number(r.startMs),
        "endMs": r.endMs.map(JSONValue.number) ?? .null,
        "explicitEnd": .bool(r.explicitEnd),
        "gapAfterMs": .number(r.gapAfterMs),
    ]
}

private func resolved(_ json: JSONValue) throws -> Segments.Resolved {
    guard let start = json["startMs"]?.doubleValue else { throw AdapterError.badInput("resolved") }
    return Segments.Resolved(
        startMs: start,
        endMs: json["endMs"]?.doubleValue,
        explicitEnd: json["explicitEnd"]?.boolValue ?? false,
        gapAfterMs: json["gapAfterMs"]?.doubleValue ?? 0
    )
}

let segmentsAdapters = ModuleAdapters(
    functions: [
        "formatClock": { args in
            .string(Segments.formatClock(args["ms"]?.doubleValue, millis: args["opts"]?["millis"]?.isTruthy ?? false))
        },
        "resolveSegments": { args in
            let tunes = try args.require("tunes", \.arrayValue)
            // A tune is placed when `segment` is present and not null.
            let marks: [Segments.Mark] = try tunes.compactMap { t in
                guard let seg = t["segment"], !seg.isNull else { return nil }
                guard let id = RecordID(t["session_instance_tune_id"]), let start = seg["start_ms"]?.doubleValue else {
                    throw AdapterError.badInput("tunes")
                }
                return Segments.Mark(id: id, startMs: start, endMs: seg["end_ms"]?.doubleValue)
            }
            let out = Segments.resolveSegments(marks, durationMs: args["durationMs"]?.doubleValue)
            return .array(out.map { .array([$0.id.json, resolvedJSON($0.segment)]) })
        },
        "playbackStep": { args in
            let queue = try args.require("queue", \.arrayValue).map { v -> RecordID in
                guard let id = RecordID(v) else { throw AdapterError.badInput("queue") }
                return id
            }
            var table: [RecordID: Segments.Resolved] = [:]
            for (k, v) in try args.map("resolved") {
                guard let id = RecordID(k) else { throw AdapterError.badInput("resolved") }
                table[id] = try resolved(v)
            }
            // `opts.x ?? default`: absent or null takes the default.
            var opts = Segments.PlaybackOptions()
            let o = args["opts"]
            if let v = o?["leadMs"]?.doubleValue { opts.leadMs = v }
            if let v = o?["contiguousMs"]?.doubleValue { opts.contiguousMs = v }
            if let v = o?["repeatOne"]?.boolValue { opts.repeatOne = v }
            if let v = o?["autoContinue"]?.boolValue { opts.autoContinue = v }
            let step = Segments.playbackStep(
                queue: queue, idx: try args.require("idx", \.intValue),
                nowMs: try args.require("nowMs", \.doubleValue), resolved: table, options: opts)
            return [
                "idx": JSONValue(step.idx),
                "seekMs": step.seekMs.map(JSONValue.number) ?? .null,
                "done": .bool(step.done),
            ]
        },
    ],
    constants: [
        "HANDOVER_LEAD_MS": .number(Segments.handoverLeadMs),
        "CONTIGUOUS_MS": .number(Segments.contiguousMs),
    ]
)

@Suite("abcquery.fixtures.json")
struct ABCQueryFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("abcquery", abcQueryAdapters) }

    @Test("case", arguments: Fixtures.cases("abcquery"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, abcQueryAdapters) }
}

@Suite("segments.fixtures.json")
struct SegmentsFixtureTests {
    @Test("covers every function") func coverage() { Fixtures.checkCoverage("segments", segmentsAdapters) }

    @Test("case", arguments: Fixtures.cases("segments"))
    func run(_ fc: FunctionCase) throws { try Fixtures.run(fc, segmentsAdapters) }
}
