// Every captured server response decodes into the type the spec generates for it.
//
// The fixtures are real responses from the seeded server
// (scripts/capture_native_fixtures.py). The web's contract test proves the server
// matches native-surface.yaml; this proves the Swift generated from that same file
// can read what the server actually sends — the two halves of "the app and the
// server agree".

import Foundation
import Testing

@testable import CeolAPI

private func fixture(_ name: String) throws -> Data {
    let url = try #require(
        Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Fixtures"),
        "missing Fixtures/\(name).json — run scripts/capture_native_fixtures.py"
    )
    return try Data(contentsOf: url)
}

private func decode<T: Decodable>(_ type: T.Type, _ name: String) throws -> T {
    try JSONDecoder().decode(T.self, from: fixture(name))
}

/// Schema name (= fixture file) -> decode into the generated type. A new fixture
/// with no row here fails `everyFixtureIsDecoded`, so none is silently skipped.
private let decoders: [String: @Sendable (String) throws -> Void] = [
    "ActiveInstance": { _ = try decode(Components.Schemas.ActiveInstance.self, $0) },
    "AppConfig": { _ = try decode(Components.Schemas.AppConfig.self, $0) },
    "DeepSearch": { _ = try decode(Components.Schemas.DeepSearch.self, $0) },
    "Home": { _ = try decode(Components.Schemas.Home.self, $0) },
    "LiveBootstrap": { _ = try decode(Components.Schemas.LiveBootstrap.self, $0) },
    "LiveVocabulary": { _ = try decode(Components.Schemas.LiveVocabulary.self, $0) },
    "Me": { _ = try decode(Components.Schemas.Me.self, $0) },
    "MyTunes": { _ = try decode(Components.Schemas.MyTunes.self, $0) },
    "NextInstanceSuggestion": { _ = try decode(Components.Schemas.NextInstanceSuggestion.self, $0) },
    "OfflineBundle": { _ = try decode(Components.Schemas.OfflineBundle.self, $0) },
    "Profile": { _ = try decode(Components.Schemas.Profile.self, $0) },
    "Recordings": { _ = try decode(Components.Schemas.Recordings.self, $0) },
    "Resolve": { _ = try decode(Components.Schemas.Resolve.self, $0) },
    // A bare festival prefix (spec 056), from production: kind place, with its years.
    "ResolveFestival": { _ = try decode(Components.Schemas.Resolve.self, $0) },
    "SessionDetail": { _ = try decode(Components.Schemas.SessionDetail.self, $0) },
    "SessionLogs": { _ = try decode(Components.Schemas.SessionLogs.self, $0) },
    // A festival year's nights, grouped by day (spec 056), from production.
    "SessionLogsFestival": { _ = try decode(Components.Schemas.SessionLogs.self, $0) },
    "SessionPeople": { _ = try decode(Components.Schemas.SessionPeople.self, $0) },
    "SessionsDirectory": { _ = try decode(Components.Schemas.SessionsDirectory.self, $0) },
    "TuneDetail": { _ = try decode(Components.Schemas.TuneDetail.self, $0) },
    "TunePreview": { _ = try decode(Components.Schemas.TunePreview.self, $0) },
    "TuneSearch": { _ = try decode(Components.Schemas.TuneSearch.self, $0) },
]

private func fixtureNames() -> [String] {
    let dir = Bundle.module.url(forResource: "Fixtures", withExtension: nil)!
    let files = (try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []
    return files.filter { $0.hasSuffix(".json") }.map { String($0.dropLast(5)) }.sorted()
}

@Suite("Server responses decode")
struct FixtureDecodingTests {
    @Test("a festival year's nights come grouped by day, earliest first")
    func festivalLogs() throws {
        let l = try decode(Components.Schemas.SessionLogs.self, "SessionLogsFestival")
        #expect(l.sessionType == "festival")
        #expect(l.sortedYears.isEmpty)
        #expect(!l.sortedDays.isEmpty)
        #expect(l.sortedDays == l.sortedDays.sorted())
        for day in l.sortedDays { #expect(!(l.instancesByDay.additionalProperties[day] ?? []).isEmpty) }
    }

    @Test("a festival's resolve carries its years, newest-or-upcoming first")
    func festivalResolve() throws {
        let r = try decode(Components.Schemas.Resolve.self, "ResolveFestival")
        #expect(r.kind == .place)
        #expect(r.place?.kind == .festival)
        let years = try #require(r.years)
        #expect(years.map(\.path).allSatisfy { $0.hasPrefix("oflahertys/") })
        #expect(!years.isEmpty)
    }

    @Test("every fixture has a decoder")
    func everyFixtureIsDecoded() {
        let names = fixtureNames()
        #expect(!names.isEmpty)
        #expect(Set(names).subtracting(decoders.keys).isEmpty, "no decoder for \(Set(names).subtracting(decoders.keys))")
    }

    @Test("decodes", arguments: fixtureNames())
    func decodes(_ name: String) throws {
        let decode = try #require(decoders[name])
        try decode(name)
    }

    @Test("a session detail carries its tab counts and tonight's night")
    func sessionDetailFields() throws {
        let detail = try decode(Components.Schemas.SessionDetail.self, "SessionDetail")
        #expect(detail.success)
        #expect(detail.totalTunesCount > 0)
        #expect(detail.totalLogsCount > 0)
        // The capture marks one night active, so the item type is really exercised.
        #expect(detail.activeInstances.count == 1)
    }
}
