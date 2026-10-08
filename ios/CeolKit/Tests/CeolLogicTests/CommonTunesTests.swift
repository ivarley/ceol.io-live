import Testing

@testable import CeolLogic

struct CommonTunesTests {
    let tunes = [
        CommonTunes.Tune(tuneID: 27, name: "Drowsy Maggie", type: "Reel", tunebookCount: 1800),
        CommonTunes.Tune(tuneID: 55, name: "Kesh, The", type: "Jig", tunebookCount: 1900),
        CommonTunes.Tune(tuneID: 9, name: "Banish Misfortune", type: "Jig", tunebookCount: 1800),
        CommonTunes.Tune(tuneID: 3, name: "Fear an Bháta", type: "Air", tunebookCount: 12),
    ]

    func ids(search: String = "", type: String = "", sort: CommonTunes.Sort = .init()) -> [Int] {
        CommonTunes.filter(tunes, search: search, type: type, sort: sort).map(\.tuneID)
    }

    @Test func sortsByNameThenPopularity() {
        #expect(ids() == [9, 27, 3, 55])
        #expect(ids(sort: .init(mode: .name, descending: true)) == [55, 3, 27, 9])
        // The most first; ties A to Z.
        #expect(ids(sort: .init(mode: .popular)) == [55, 9, 27, 3])
        #expect(CommonTunes.Sort(mode: .popular).descending)
    }

    @Test func searchesNamesAccentsAsideAndThesessionNumbers() {
        #expect(ids(search: "bhata") == [3])
        #expect(ids(search: "  KESH ") == [55])
        #expect(ids(search: "https://thesession.org/tunes/27") == [27])
    }

    @Test func filtersByType() {
        #expect(ids(type: "Jig") == [9, 55])
        #expect(CommonTunes.types(tunes) == ["Air", "Jig", "Reel"])
    }
}
