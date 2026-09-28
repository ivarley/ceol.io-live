// The cases frontend/tests/homepage.logic.test.js pins, for the Swift port.

import Foundation
import Testing

@testable import CeolLogic

private func night(
    date: String = "2026-09-22", start: String? = "19:00:00", end: String? = "22:00:00",
    location: String? = "BD Riley's", active: Bool = false, complete: Bool = false,
    people: Int = 0, tunes: Int = 0
) -> HomeNight {
    HomeNight(
        name: "Mueller Session", path: "austin/mueller", date: date, startTime: start, endTime: end,
        locationName: location, isActive: active, logComplete: complete, peopleHere: people, tunesLogged: tunes)
}

@Suite("HomeRules")
struct HomeRulesTests {
    @Test("today is a subset of the week, and keeps every night on the day")
    func today() {
        let week = [night(date: "2026-09-21"), night(), night(date: "2026-09-23")]
        #expect(HomeRules.todaysSessions(week, today: "2026-09-22") == [week[1]])
        #expect(HomeRules.todaysSessions([night()], today: nil).isEmpty)
        let festival = [night(), night(), night()]
        #expect(HomeRules.todaysSessions(festival, today: "2026-09-22").count == 3)
    }

    @Test("liveness: the server flag, then a completed log")
    func status() {
        #expect(HomeRules.status(night(active: true)) == .live)
        #expect(HomeRules.statusLabel(night(active: true)) == "Live now")
        #expect(HomeRules.status(night(complete: true)) == .finished)
        #expect(HomeRules.statusLabel(night(complete: true)) == "Finished")
        #expect(HomeRules.status(night(active: true, complete: true)) == .live)
        #expect(HomeRules.statusLabel(night()) == "Starts 7:00pm")
        #expect(HomeRules.statusLabel(night(start: nil)) == "Today")
    }

    @Test("the subtitle counts the room only while live, and drops what it doesn't have")
    func subtitle() {
        #expect(HomeRules.todaySubtitle(night(active: true, people: 4)) == "7:00pm-10:00pm · BD Riley's · 4 people here")
        #expect(HomeRules.todaySubtitle(night(complete: true)) == "7:00pm-10:00pm · BD Riley's")
        #expect(HomeRules.todaySubtitle(night(active: true, people: 1)).contains("1 person here"))
        #expect(HomeRules.todaySubtitle(night(start: nil, end: nil, location: nil)) == "")
        #expect(HomeRules.todaySubtitle(night(end: nil)).contains("7:00pm - ?"))
    }

    @Test("the tally says so far only while the number can move")
    func tally() {
        #expect(HomeRules.tallyLabel(night(active: true, tunes: 18)) == "18 tunes logged so far")
        #expect(HomeRules.tallyLabel(night(complete: true, tunes: 18)) == "18 tunes logged")
        #expect(HomeRules.tallyLabel(night()) == "No tunes logged yet")
        #expect(HomeRules.tallyLabel(night(tunes: 1)) == "1 tune logged")
    }

    @Test("a week row marks a past night never logged, and not a future one")
    func week() {
        #expect(HomeRules.weekSubtitle(night(date: "2026-09-21"), today: "2026-09-22").contains("not logged"))
        #expect(!HomeRules.weekSubtitle(night(date: "2026-09-23"), today: "2026-09-22").contains("not logged"))
        let logged = HomeRules.weekSubtitle(night(date: "2026-09-21", complete: true), today: "2026-09-22")
        #expect(logged.hasSuffix("logged") && !logged.contains("not logged"))
    }

    @Test("times: 12-hour, midnight and noon")
    func times() {
        #expect(HomeRules.formatTime("19:00:00") == "7:00pm")
        #expect(HomeRules.formatTime("00:30") == "12:30am")
        #expect(HomeRules.formatTime("12:15:00") == "12:15pm")
        #expect(HomeRules.formatTime(nil) == "")
    }

    @Test("pick up where you left off: one list, newest edit first, keyed apart")
    func continueItems() {
        let items = HomeRules.continueItems(
            logs: [.init(sessionInstanceID: 7, name: "Mueller Session", path: "austin/mueller", date: "2026-09-16",
                         lastEdit: "2026-09-20T10:00:00Z")],
            recordings: [.init(recordingID: 7, label: nil, name: "Mueller Session", path: "austin/mueller",
                               lastEdit: "2026-09-21T10:00:00Z", placed: 4, tuneCount: 11)],
            currentYear: 2026)
        #expect(items.map(\.kind) == [.recording, .log])
        #expect(Set(items.map(\.id)).count == 2)
        #expect(items[1].path == "/sessions/austin/mueller/2026-09-16")
        #expect(items[0].path == "/admin/recordings/7/segment")
        #expect(items[0].detail == "4 of 11 tunes placed")
        #expect(items[0].title == "Place tunes on Mueller Session")
        #expect(HomeRules.continueItems(logs: [], recordings: [], currentYear: 2026).isEmpty)
    }

    @Test("edited: minutes and hours, then a date, the year only when not this one")
    func edited() {
        let now = ISO8601DateFormatter().date(from: "2026-09-22T12:00:00Z")!
        #expect(HomeRules.editedLabel("2026-09-22T11:58:00Z", currentYear: 2026, now: now) == "2 minutes ago")
        #expect(HomeRules.editedLabel("2026-09-22T09:00:00Z", currentYear: 2026, now: now) == "3 hours ago")
        #expect(HomeRules.editedLabel("2026-09-16T12:00:00Z", currentYear: 2026, now: now).contains("Sep 16"))
        #expect(HomeRules.editedLabel("2025-09-16T12:00:00Z", currentYear: 2026, now: now).contains("2025"))
        #expect(HomeRules.editedLabel(nil, currentYear: 2026, now: now) == "")
        #expect(HomeRules.editedLabel("not a date", currentYear: 2026, now: now) == "")
    }
}
