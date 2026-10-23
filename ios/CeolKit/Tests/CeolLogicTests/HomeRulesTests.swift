// The cases frontend/tests/homepage.logic.test.js pins, for the Swift port.

import Foundation
import Testing

@testable import CeolLogic

private func night(
    date: String = "2026-09-22", start: String? = "19:00:00", end: String? = "22:00:00",
    location: String? = "BD Riley's", active: Bool = false, complete: Bool = false,
    people: Int = 0, tunes: Int = 0, id: Int? = nil, path: String = "austin/mueller",
    name: String = "Mueller Session", several: Bool = false, day: Int? = nil
) -> HomeNight {
    HomeNight(
        name: name, path: path, date: date, startTime: start, endTime: end,
        locationName: location, isActive: active, logComplete: complete, peopleHere: people, tunesLogged: tunes,
        sessionInstanceID: id, multipleOnDate: several, festivalDay: day)
}

/// A room of a festival day: one of several nights of the one session on the date.
private func room(
    _ id: Int, start: String = "10:00:00", location: String? = "Room A", active: Bool = false,
    complete: Bool = false, tunes: Int = 0, date: String = "2026-10-22", day: Int? = nil
) -> HomeNight {
    night(
        date: date, start: start, end: nil, location: location, active: active, complete: complete, tunes: tunes,
        id: id, path: "oflahertys/2026", name: "O'Flaherty's 2026", several: true, day: day)
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

    @Test("a night's web path is its date, or its id when the session has several nights that day")
    func nightPath() {
        #expect(HomeRules.nightPath(sessionPath: "austin/mueller", date: "2026-09-22", id: 120, multipleOnDate: false)
            == "/sessions/austin/mueller/2026-09-22")
        #expect(HomeRules.nightPath(sessionPath: "oflahertys/2026", date: "2026-10-22", id: 7, multipleOnDate: true)
            == "/sessions/oflahertys/2026/7")
        // No date at all: the id is all there is.
        #expect(HomeRules.nightPath(sessionPath: "austin/mueller", date: nil, id: 120, multipleOnDate: false)
            == "/sessions/austin/mueller/120")
        let logs = HomeRules.continueItems(
            logs: [.init(sessionInstanceID: 7, name: "O'Flaherty's 2026", path: "oflahertys/2026", date: "2026-10-22",
                         lastEdit: nil, multipleOnDate: true)],
            recordings: [], currentYear: 2026)
        #expect(logs[0].path == "/sessions/oflahertys/2026/7")
    }

    @Test("a session's several nights on one day fold into one item; a night alone stays one")
    func fold() {
        let items = HomeRules.nightItems([
            night(date: "2026-10-22", id: 1),
            room(10, location: "Room A", active: true, tunes: 4),
            room(11, location: "Room B", active: true),
            room(12, start: "14:00:00", location: "Room C", tunes: 2),
        ])
        #expect(items.count == 2)
        guard case .night(let alone) = items[0], case .group(let g) = items[1] else {
            Issue.record("expected a night then a group"); return
        }
        #expect(alone.sessionInstanceID == 1)
        #expect(g.name == "O'Flaherty's 2026")
        #expect(g.nights.count == 3)
        #expect(g.live.map(\.sessionInstanceID) == [10, 11])
        #expect(HomeRules.groupStatusLabel(g) == "2 on now")
        #expect(HomeRules.groupSubtitle(g) == "3 sessions today")
        #expect(HomeRules.groupTally(g) == "Room A, Room B")
        #expect(HomeRules.groupWeekSubtitle(g, today: "2026-10-22") == "3 sessions · 2 on now")
        #expect(items[0].id != items[1].id)

        // Different sessions, or different days of one session, do not fold.
        let apart = HomeRules.nightItems([room(1), room(2, date: "2026-10-23"), night(date: "2026-10-22", id: 3)])
        #expect(apart.count == 3)
    }

    @Test("a fold with none on now says when the first starts, then that it is finished")
    func foldStatus() {
        guard case .group(let upcoming) = HomeRules.nightItems([room(1, start: "19:00:00"), room(2, start: "21:00:00")])[0]
        else { Issue.record("expected a group"); return }
        #expect(HomeRules.groupStatusLabel(upcoming) == "Starts 7:00pm")
        #expect(HomeRules.groupTally(upcoming) == "No tunes logged yet")
        guard case .group(let done) = HomeRules.nightItems([room(1, complete: true, tunes: 3), room(2, complete: true, tunes: 5)])[0]
        else { Issue.record("expected a group"); return }
        #expect(HomeRules.groupStatusLabel(done) == "Finished")
        #expect(HomeRules.groupTally(done) == "8 tunes logged")
        #expect(HomeRules.groupWeekSubtitle(done, today: "2026-10-23") == "2 sessions · logged")
        guard case .group(let missed) = HomeRules.nightItems([room(1), room(2)])[0] else { Issue.record("expected a group"); return }
        #expect(HomeRules.groupWeekSubtitle(missed, today: "2026-10-23") == "2 sessions · not logged")
    }

    @Test("a multi-day festival's items say which day it is")
    func festivalDay() {
        guard case .group(let g) = HomeRules.nightItems([room(1, day: 2), room(2, day: 2)])[0]
        else { Issue.record("expected a group"); return }
        #expect(HomeRules.groupSubtitle(g) == "Day 2 · 2 sessions today")
        #expect(HomeRules.groupWeekSubtitle(g, today: "2026-10-24") == "Day 2 · 2 sessions · not logged")
        // A festival day with one session, and a regular session, which has no day.
        #expect(HomeRules.weekSubtitle(room(3, day: 1), today: "2026-10-22") == "10:00am - ? · Room A · Day 1")
        #expect(HomeRules.todaySubtitle(room(3, day: 1)) == "10:00am - ? · Room A · Day 1")
        #expect(HomeRules.weekSubtitle(night(), today: "2026-09-22") == "7:00pm-10:00pm · BD Riley's")
        #expect(HomeRules.festivalDayLabel(nil) == "")
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
