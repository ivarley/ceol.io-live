// The cases frontend/tests/sessionsdir.logic.test.js pins, and the filter's rules.

import Testing

@testable import CeolLogic

private func entry(
    _ name: String = "Mueller Session", city: String? = "Austin", state: String? = "TX", country: String? = "USA",
    ends: String? = nil, member: Bool = false, relationship: String? = nil
) -> SessionsRules.Entry {
    .init(name: name, city: city, state: state, country: country, terminationDate: ends, isMember: member,
          relationship: relationship)
}

@Suite("SessionsRules")
struct SessionsRulesTests {
    @Test("the viewer's own country is dropped, another's kept")
    func location() {
        #expect(SessionsRules.locationLabel(city: "Austin", state: "TX", country: "USA", viewerCountry: "usa ") == "Austin, TX")
        #expect(SessionsRules.locationLabel(city: "Galway", state: nil, country: "Ireland", viewerCountry: "USA") == "Galway, Ireland")
        #expect(SessionsRules.locationLabel(city: "Austin", state: "TX", country: "USA", viewerCountry: nil) == "Austin, TX, USA")
        #expect(SessionsRules.locationLabel(city: nil, state: nil, country: nil, viewerCountry: "USA") == "Unknown")
    }

    @Test("filters: membership, visitors, and active until the end date arrives")
    func filters() {
        let today = "2026-09-28"
        #expect(SessionsRules.matches(entry(member: true), filter: .mine, search: "", today: today))
        #expect(!SessionsRules.matches(entry(relationship: "visitor"), filter: .mine, search: "", today: today))
        #expect(SessionsRules.matches(entry(relationship: "visitor"), filter: .visited, search: "", today: today))
        #expect(SessionsRules.matches(entry(), filter: .active, search: "", today: today))
        #expect(SessionsRules.matches(entry(ends: "2026-10-01"), filter: .active, search: "", today: today))
        #expect(!SessionsRules.matches(entry(ends: "2026-09-28"), filter: .active, search: "", today: today))
        #expect(SessionsRules.matches(entry(ends: "2026-09-28"), filter: .inactive, search: "", today: today))
        #expect(!SessionsRules.matches(entry(), filter: .inactive, search: "", today: today))
        #expect(SessionsRules.matches(entry(ends: "2020-01-01"), filter: .all, search: "", today: today))
    }

    @Test("search: the name or the place, smart quotes folded")
    func search() {
        let today = "2026-09-28"
        #expect(SessionsRules.matches(entry("O'Flaherty's"), filter: .all, search: "o\u{2019}flah", today: today))
        #expect(SessionsRules.matches(entry(), filter: .all, search: "austin", today: today))
        #expect(!SessionsRules.matches(entry(), filter: .all, search: "galway", today: today))
        #expect(SessionsRules.matches(entry("Sligo Ma\u{ED}d"), filter: .all, search: "maid", today: today))
        #expect(SessionsRules.matches(entry("Sligo Maid"), filter: .all, search: "ma\u{ED}d", today: today))
    }
}
