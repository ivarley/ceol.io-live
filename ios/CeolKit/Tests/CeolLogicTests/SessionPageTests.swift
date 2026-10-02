// The cases frontend/tests/sessionpage.logic.test.js pins for a session's three tabs,
// and the tunebook roll-up's rules (static/js/tunebook_status.js).

import Testing

@testable import CeolLogic

private func tune(_ id: Int, _ name: String, _ type: String, _ plays: Int, _ tunebook: Int, attended: Int = 0) -> SessionPage.Tune {
    .init(tuneID: id, name: name, type: type, playCount: plays, tunebookCount: tunebook, attendedPlayCount: attended)
}

@Suite("SessionPage")
struct SessionPageTests {
    let tunes = [
        tune(101, "Cooley's", "reel", 5, 900),
        tune(102, "Banish Misfortune", "jig", 2, 300),
        tune(103, "The Ashplant", "reel", 9, 100),
    ]

    private func ids(_ f: SessionPage.Filters, _ sort: SessionPage.Sort = .init(), status: ((Int) -> String)? = nil, in all: [SessionPage.Tune]? = nil) -> [Int] {
        SessionPage.filterAndSortTunes(all ?? tunes, filters: f, sort: sort, status: status).map(\.tuneID)
    }

    @Test("no filters: sorted by plays here, most first")
    func defaults() {
        #expect(ids(.init()) == [103, 101, 102])
    }

    @Test("the other sorts: a-z, everywhere, and the direction")
    func sorts() {
        #expect(ids(.init(), .init(mode: .alpha, descending: false)) == [102, 101, 103])
        #expect(ids(.init(), .init(mode: .alpha, descending: true)) == [103, 101, 102])
        #expect(ids(.init(), .init(mode: .everywhere, descending: true)) == [101, 102, 103])
        #expect(ids(.init(), .init(mode: .session, descending: false)) == [102, 101, 103])
    }

    @Test("search matches names, accent- and case-insensitively, and tune ids")
    func search() {
        var f = SessionPage.Filters()
        f.search = "banish"
        #expect(ids(f) == [102])
        f.search = "101"
        #expect(ids(f) == [101])
        f.search = "COOLEY’S"
        #expect(ids(f) == [101])
        f.search = "  ashpl "
        #expect(ids(f) == [103])
    }

    @Test("type narrows to one tune type")
    func type() {
        var f = SessionPage.Filters()
        f.type = "reel"
        #expect(ids(f) == [103, 101])
    }

    @Test("attended keeps only tunes with attended plays")
    func attended() {
        let all = [tune(101, "A", "reel", 5, 0, attended: 2), tune(102, "B", "reel", 2, 0), tune(103, "C", "reel", 1, 0)]
        var f = SessionPage.Filters()
        f.attended = true
        #expect(ids(f, in: all) == [101])
    }

    @Test("my status: 'show' colours without filtering; a status filters; unloaded lets all through")
    func myStatus() {
        let status: (Int) -> String = { $0 == 101 ? "learned" : "not on list" }
        var f = SessionPage.Filters()
        f.myStatus = .all
        #expect(ids(f, status: status).count == 3)
        f.myStatus = .learned
        #expect(ids(f, status: status) == [101])
        f.myStatus = .notOnList
        #expect(ids(f, status: status) == [103, 102])
        #expect(ids(f, status: nil).count == 3)
    }

    @Test("the count line")
    func countLabel() {
        #expect(SessionPage.resultsCountLabel(2, 5) == "Showing 2 of 5 tunes")
        #expect(SessionPage.resultsCountLabel(5, 5) == "5 tunes")
        #expect(SessionPage.resultsCountLabel(1, 1) == "1 tune")
    }

    @Test("tunebook roll-up: off the list, one instrument, the furthest along, one instrument's scope")
    func resolve() {
        let fiddle = MyTunesList.Instrument(name: "fiddle", isAuto: true)
        let flute = MyTunesList.Instrument(name: "flute", isAuto: false)
        let entry = SessionPage.TunebookEntry(status: "learning", instrumentStatus: ["flute": "learned"])
        #expect(SessionPage.resolveStatus(nil, instruments: [fiddle], scope: "all") == "not on list")
        #expect(SessionPage.resolveStatus(entry, instruments: [fiddle], scope: "all") == "learning")
        #expect(SessionPage.resolveStatus(entry, instruments: [fiddle, flute], scope: "all") == "learned")
        #expect(SessionPage.resolveStatus(entry, instruments: [fiddle, flute], scope: "fiddle") == "learning")
        let untracked = SessionPage.TunebookEntry(status: "learning")
        #expect(SessionPage.resolveStatus(untracked, instruments: [fiddle, flute], scope: "flute") == "not on list")
    }

    @Test("logs: logged drops empty nights, attended keeps yours, a tune filter supersedes both")
    func logs() {
        #expect(SessionPage.keepInstance(tuneCount: 5, attended: false, view: .logged, tuneInstanceIDs: nil, id: 1))
        #expect(!SessionPage.keepInstance(tuneCount: 0, attended: false, view: .logged, tuneInstanceIDs: nil, id: 2))
        #expect(SessionPage.keepInstance(tuneCount: 0, attended: false, view: .all, tuneInstanceIDs: nil, id: 2))
        #expect(SessionPage.keepInstance(tuneCount: 0, attended: true, view: .attended, tuneInstanceIDs: nil, id: 2))
        #expect(!SessionPage.keepInstance(tuneCount: 5, attended: false, view: .attended, tuneInstanceIDs: nil, id: 1))
        #expect(SessionPage.keepInstance(tuneCount: 0, attended: false, view: .logged, tuneInstanceIDs: [2], id: 2))
        #expect(!SessionPage.keepInstance(tuneCount: 5, attended: false, view: .all, tuneInstanceIDs: [2], id: 1))
        #expect(SessionPage.LogView.options(signedIn: false) == [.logged, .all])
    }

    @Test("logged-tune suggestions: none for an empty box, prefix first, then most played, capped")
    func suggestions() {
        let logged = [
            SessionPage.LoggedTune(tuneID: 1, name: "The Butterfly", logCount: 3),
            SessionPage.LoggedTune(tuneID: 2, name: "Butterfly Whirl", logCount: 9),
            SessionPage.LoggedTune(tuneID: 3, name: "Cooley's", logCount: 40),
        ]
        #expect(SessionPage.matchLoggedTunes(logged, query: "   ").isEmpty)
        #expect(SessionPage.matchLoggedTunes(logged, query: "butterfly").map(\.name) == ["Butterfly Whirl", "The Butterfly"])
        #expect(SessionPage.matchLoggedTunes(logged, query: "COOL").map(\.tuneID) == [3])
        #expect(SessionPage.matchLoggedTunes(logged, query: "butterfly", limit: 1).count == 1)
    }

    @Test("people: members, visitors, archived; a search covers everyone, by name or instrument")
    func people() {
        let people = [
            SessionPage.Person(name: "Ann Malone", instruments: ["Fiddle"], relationship: "member", archived: false),
            SessionPage.Person(name: "Bob Kelly", instruments: ["Flute"], relationship: "visitor", archived: false),
            SessionPage.Person(name: "Maura Gone", instruments: ["Harp"], relationship: "member", archived: true),
        ]
        #expect(SessionPage.filterPeople(people, view: .members, search: "") == [0])
        #expect(SessionPage.filterPeople(people, view: .visitors, search: "") == [1])
        #expect(SessionPage.filterPeople(people, view: .archived, search: "") == [2])
        #expect(SessionPage.filterPeople(people, view: .members, search: "maura") == [2])
        #expect(SessionPage.filterPeople(people, view: .members, search: "flute") == [1])
    }
}
