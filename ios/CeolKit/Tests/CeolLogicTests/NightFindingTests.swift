// Finding tunes in a night (the web's pull-down filter and ★ highlight, held to
// frontend/src/App.svelte's displaySegments and rowListStatus).

import Testing

@testable import CeolLogic

private func tune(_ id: Int, _ name: String, tuneID: Int? = nil) -> LogRecord {
    ["session_instance_tune_id": JSONValue(id), "record_type": "tune", "name": .string(name),
     "tune_id": tuneID.map { JSONValue($0) } ?? .null]
}

private let breakRow: LogRecord = ["session_instance_tune_id": 99, "record_type": "break", "name": "cool break"]

@Suite("NightFinding")
struct NightFindingTests {
    let sets = [
        LogSegment(tunes: [tune(1, "Cooley's", tuneID: 11), tune(2, "The Wise Maid", tuneID: 12)], breakAfter: RecordID(JSONValue(99))),
        LogSegment(tunes: [tune(3, "Sí Bheag, Sí Mhór", tuneID: 13)], breakAfter: nil),
        LogSegment(tunes: [tune(4, "typed, not linked")], breakAfter: nil),
    ]
    let status: (Int) -> String? = { ["11": "learned", "12": "not on list", "13": "learning"][String($0)] }

    @Test("the search finds a name, case and accents aside")
    func search() {
        #expect(NightFinding.match("Cooley's", "cool") != nil)
        #expect(NightFinding.match("Sí Bheag, Sí Mhór", "si bheag") != nil)
        #expect(NightFinding.match("Cooley's", "  ") == nil)
        #expect(NightFinding.match("Cooley's", "maid") == nil)
        #expect(NightFinding.filterSets(sets, query: "maid", status: nil, statusOf: status).map(\.tunes.count) == [2])
        #expect(NightFinding.filterSets(sets, query: "SI MHOR", status: nil, statusOf: status).map(\.tunes.count) == [1])
        #expect(NightFinding.filterSets(sets, query: "", status: nil, statusOf: status).count == 3)
        #expect(NightFinding.matches(breakRow, query: "cool", status: nil, statusOf: status) == false)
    }

    @Test("a status narrows to the tunes showing it; an unlinked tune has none")
    func byStatus() {
        #expect(NightFinding.filterSets(sets, query: "", status: "not on list", statusOf: status).map(\.tunes.count) == [2])
        #expect(NightFinding.filterSets(sets, query: "", status: "learning", statusOf: status).map(\.tunes.count) == [1])
        #expect(NightFinding.filterSets(sets, query: "", status: "want to learn", statusOf: status).isEmpty)
        // Both at once: the tune must satisfy each.
        #expect(NightFinding.filterSets(sets, query: "cool", status: "not on list", statusOf: status).isEmpty)
        #expect(NightFinding.filterSets(sets, query: "cool", status: "learned", statusOf: status).count == 1)
    }
}
