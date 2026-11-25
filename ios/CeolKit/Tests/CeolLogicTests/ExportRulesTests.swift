// The export rules (ExportRules.swift): file names from the server's header, and the
// filter lines a file is headed with, as the web's lib/export.js and exportsummary.js.

import Testing

@testable import CeolLogic

struct ExportRulesTests {
    @Test func filenameFromPlainAndQuotedAndEncodedForms() {
        #expect(ExportRules.filename(fromContentDisposition: "attachment; filename=ceol-my-tunes-2026-11-24.json") == "ceol-my-tunes-2026-11-24.json")
        #expect(ExportRules.filename(fromContentDisposition: "attachment; filename=\"my tunes.csv\"") == "my tunes.csv")
        #expect(ExportRules.filename(fromContentDisposition: "attachment; filename=\"a.csv\"; filename*=UTF-8''Se%C3%A1n.csv") == "Seán.csv")
        #expect(ExportRules.filename(fromContentDisposition: nil) == nil)
        #expect(ExportRules.filename(fromContentDisposition: "inline") == nil)
    }

    @Test func localFilenameFallsBackToKindAndFormat() {
        #expect(ExportRules.localFilename("served.pdf", kind: .myTunes, format: .pdf, day: "2026-11-24") == "served.pdf")
        #expect(ExportRules.localFilename(nil, kind: .myTunes, format: .json, day: "2026-11-24") == "ceol-my-tunes-2026-11-24.json")
        #expect(ExportRules.localFilename("", kind: .sessionTunes(path: "austin/mueller"), format: .csv, day: "2026-11-24") == "ceol-austin-mueller-tunes-2026-11-24.csv")
        #expect(ExportRules.localFilename("../x", kind: .sessionLogs(path: "Hill Country/2026"), format: .pdf, day: "2026-11-24") == "ceol-hill-country-2026-logs-2026-11-24.pdf")
    }

    @Test func myTunesLinesFollowTheWebsOrder() {
        var f = MyTunesList.Filters()
        f.status = "learning"
        f.type = "reel"
        f.instrument = "fiddle"
        f.tag = "pub-set"
        f.rel = "attended"
        f.addedBefore = true
        f.addedDate = "2026-01-01"
        f.search = " kesh "
        let s = MyTunesList.Sort(type: "popularity", descending: true, type2: "alpha", descending2: false)
        let keys = ExportRules.myTunesLines(filters: f, sort: s).map(\.key)
        #expect(keys == [.status, .type, .instrument, .tag, .played, .addedBefore, .search, .sort, .thenBy])
        #expect(ExportRules.myTunesLines(filters: f, sort: s)[6].value == "kesh")
        #expect(ExportRules.myTunesLines(filters: f, sort: s)[7].descending == true)
    }

    @Test func defaultMyTunesStateHasNoLines() {
        #expect(ExportRules.myTunesLines(filters: MyTunesList.Filters(), sort: MyTunesList.Sort()).isEmpty)
    }

    @Test func sessionTunesLinesSkipTheDefaultSort() {
        var f = SessionPage.Filters()
        let defaultSort = SessionPage.Sort()
        #expect(ExportRules.sessionTunesLines(filters: f, sort: defaultSort).isEmpty)
        f.attended = true
        f.myStatus = .learning
        f.myStatusInstrument = "banjo"
        let lines = ExportRules.sessionTunesLines(filters: f, sort: defaultSort)
        #expect(lines.map(\.key) == [.played, .myTunebook])
        #expect(lines[1].value == "learning/banjo")
    }

    @Test func sessionLogsLinesPreferTheTune() {
        #expect(ExportRules.sessionLogsLines(view: .attended, tuneName: nil) == [.init(key: .nights, value: "attended")])
        #expect(ExportRules.sessionLogsLines(view: .all, tuneName: "The Kesh") == [.init(key: .nightsWith, value: "The Kesh")])
    }
}
