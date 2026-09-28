// The filterAndSort cases frontend/tests/mytunespage.logic.test.js pins, for the port's subset.

import Testing

@testable import CeolLogic

private let tunes: [MyTunesRules.Entry] = [
    .init(tuneID: 1, name: "Cooley's", type: "Reel", status: "learned", notes: nil),
    .init(tuneID: 2, name: "The Kesh", type: "Jig", status: "learning", notes: "Slow at the start"),
    .init(tuneID: 3, name: "Sligo Ma\u{ED}d", type: "Reel", status: "want to learn", notes: nil),
    .init(tuneID: 4, name: "banish misfortune", type: "Jig", status: "learned", notes: nil),
]

@Suite("MyTunesRules")
struct MyTunesRulesTests {
    @Test("status and type narrow the list; it is sorted by name, case-insensitively")
    func filters() {
        #expect(MyTunesRules.filter(tunes, status: .learned, type: nil, search: "").map(\.tuneID) == [4, 1])
        #expect(MyTunesRules.filter(tunes, status: nil, type: "Jig", search: "").map(\.tuneID) == [4, 2])
        #expect(MyTunesRules.filter(tunes, status: nil, type: nil, search: "").count == 4)
    }

    @Test("search: name or notes, ignoring accents and case; or a pasted id or link")
    func search() {
        #expect(MyTunesRules.filter(tunes, status: nil, type: nil, search: "maid").map(\.tuneID) == [3])
        #expect(MyTunesRules.filter(tunes, status: nil, type: nil, search: "COOLEY\u{2019}S").map(\.tuneID) == [1])
        #expect(MyTunesRules.filter(tunes, status: nil, type: nil, search: "slow at").map(\.tuneID) == [2])
        #expect(MyTunesRules.filter(tunes, status: nil, type: nil, search: "https://thesession.org/tunes/2?setting=9").map(\.tuneID) == [2])
        #expect(MyTunesRules.filter(tunes, status: nil, type: nil, search: " 3 ").map(\.tuneID) == [3])
        #expect(MyTunesRules.filter(tunes, status: nil, type: nil, search: "galway").isEmpty)
    }

    @Test("counts")
    func counts() {
        #expect(MyTunesRules.countText(shown: 3, total: 42) == "Showing 3 of 42 tunes")
        #expect(MyTunesRules.countText(shown: 42, total: 42) == "42 tunes")
        #expect(MyTunesRules.countText(shown: 1, total: 1) == "1 tune")
    }
}
