//
//  CeolUITests.swift
//  CeolUITests
//
//  Created by Ian Varley on 6/29/26.
//

import XCTest

/// Sign-in, driven through the real app against a development server (plan Phase 2).
///
/// These talk to a server, so they run only when given one — never production:
///
///     make ios-ui-test          # starts nothing; expects the app on http://127.0.0.1:5031
///
/// which passes CEOL_TEST_SERVER (and, for the emailed-link test, CEOL_TEST_LOGIN_TOKEN,
/// a magic-link token it writes into the local database) through to this process.
/// Uses the seeded password account, so nothing is emailed.
final class CeolUITests: XCTestCase {
    private var server: String!

    override func setUpWithError() throws {
        continueAfterFailure = false
        guard let s = ProcessInfo.processInfo.environment["CEOL_TEST_SERVER"], !s.isEmpty else {
            throw XCTSkip("No CEOL_TEST_SERVER: sign-in UI tests need a development server (make ios-ui-test).")
        }
        server = s
    }

    private func launch(openURL: String? = nil, reset: Bool = true, extra: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-CeolServerURL", server, "-CeolResetSession", reset ? "YES" : "NO"] + extra
        if let openURL { app.launchArguments += ["-CeolOpenURL", openURL] }
        app.launch()
        return app
    }

    /// Sign in with the seeded password account (nothing is emailed).
    private func signIn(_ app: XCUIApplication) {
        let email = app.textFields["signin.email"]
        XCTAssertTrue(email.waitForExistence(timeout: 15))
        email.tap()
        email.typeText("ian@ceol.io")
        app.buttons["signin.continue"].tap()
        let password = app.secureTextFields["signin.password"]
        XCTAssertTrue(password.waitForExistence(timeout: 10))
        password.tap()
        password.typeText("password123")
        app.buttons["signin.submit"].tap()
        XCTAssertTrue(app.buttons["tab.me"].firstMatch.waitForExistence(timeout: 10))
    }

    private func snapshot(_ name: String) {
        let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }

    /// Phase 3: the read-only screens, walked the way a person would.
    @MainActor
    func testBrowsingASessionToANight() throws {
        let app = launch()
        signIn(app)
        XCTAssertTrue(app.staticTexts["Welcome back, Ian"].waitForExistence(timeout: 10))
        snapshot("home")

        app.buttons["tab.sessions"].firstMatch.tap()
        let mueller = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch
        XCTAssertTrue(mueller.waitForExistence(timeout: 10))
        snapshot("sessions")
        mueller.tap()

        XCTAssertTrue(app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Tunes'")).firstMatch.waitForExistence(timeout: 10))
        snapshot("session")
        // A tune on the session's list opens its sheet, with this session's plays.
        let tune = app.buttons["session.tune"].firstMatch
        XCTAssertTrue(tune.waitForExistence(timeout: 10))
        tune.tap()
        XCTAssertTrue(app.staticTexts["Played at this session"].waitForExistence(timeout: 10))
        snapshot("session tune")
        app.buttons["Done"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Played at this session"].waitForNonExistence(timeout: 5))
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        // The first night with tunes in it (the newest may have none yet).
        let night = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[1-9][0-9]* tunes.*'")).firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        snapshot("logs")
        night.tap()
        XCTAssertTrue(app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Set 1'")).firstMatch.waitForExistence(timeout: 10))
        snapshot("night")
    }

    /// Phase 3c: the Tunes tab, a tune's sheet, and the catalogue below your matches.
    @MainActor
    func testBrowsingTunes() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.tunes"].firstMatch.tap()
        let cooleys = app.buttons.containing(NSPredicate(format: "label CONTAINS \"Cooley's\"")).firstMatch
        XCTAssertTrue(cooleys.waitForExistence(timeout: 10))
        snapshot("tunes")
        cooleys.tap()
        XCTAssertTrue(app.images["Notation for Cooley's"].waitForExistence(timeout: 20))
        snapshot("sheet")
        app.buttons["Done"].tap()
        XCTAssertTrue(app.images["Notation for Cooley's"].waitForNonExistence(timeout: 5))

        // The sort and filter drawer.
        app.buttons["tunes.search.filter"].tap()
        XCTAssertTrue(app.buttons["filters.done"].waitForExistence(timeout: 5))
        snapshot("tunes filter")
        app.buttons["filters.done"].tap()
        let search = app.textFields["tunes.search"]
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
        search.typeText("maid")
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label ==[c] %@", "Not on your list")).firstMatch.waitForExistence(timeout: 10))
        snapshot("search")
    }

    /// Phase 4a: add a catalogue tune, change it, and remove it again (so the seed
    /// data ends as it began).
    @MainActor
    func testEditingATune() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.tunes"].firstMatch.tap()
        let search = app.textFields["tunes.search"]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
        search.typeText("maid")
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label ==[c] %@", "Not on your list")).firstMatch.waitForExistence(timeout: 10))
        let row = app.buttons.matching(identifier: "catalogue.row").firstMatch
        let name = row.staticTexts.firstMatch.label
        row.tap()

        let toLearn = app.buttons["sheet.add.want to learn"]
        XCTAssertTrue(toLearn.waitForExistence(timeout: 10))
        toLearn.tap()
        let learnSelected = app.buttons["sheet.status.want to learn"]
        XCTAssertTrue(learnSelected.waitForExistence(timeout: 10))
        XCTAssertTrue(learnSelected.isSelected)
        // The stepper reads its label and value as one: "Heard it, once".
        let heard = app.steppers["sheet.heard"]
        XCTAssertTrue(heard.descendants(matching: .any).containing(NSPredicate(format: "label CONTAINS 'once'")).firstMatch.exists
            || heard.label.contains("once"), heard.debugDescription)
        heard.buttons.element(boundBy: 1).tap()
        let twice = app.descendants(matching: .any).containing(NSPredicate(format: "label CONTAINS '2 times'")).firstMatch
        XCTAssertTrue(twice.waitForExistence(timeout: 5) || heard.label.contains("2 times"), heard.debugDescription)
        app.buttons["sheet.status.learning"].tap()
        XCTAssertTrue(app.steppers["sheet.heard"].waitForNonExistence(timeout: 5))
        snapshot("edited")

        app.swipeUp()
        app.buttons["sheet.remove"].tap()
        let confirm = app.buttons.matching(NSPredicate(format: "label == 'Remove' AND identifier != 'sheet.remove'")).firstMatch
        XCTAssertTrue(confirm.waitForExistence(timeout: 5))
        confirm.tap()
        XCTAssertTrue(app.buttons["sheet.remove"].waitForNonExistence(timeout: 10))
        // Back in the catalogue, not on the list.
        XCTAssertTrue(
            app.buttons.matching(identifier: "catalogue.row").containing(NSPredicate(format: "label == %@", name)).firstMatch
                .waitForExistence(timeout: 10))
    }

    /// Phase 4b: Admin opens the web in a Safari view, already signed in.
    @MainActor
    func testAdminOpensTheWebSignedIn() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.me"].firstMatch.tap()
        let admin = app.buttons["me.admin"]
        XCTAssertTrue(admin.waitForExistence(timeout: 10))
        // Below the Account rows now: scroll it clear of the tab bar first.
        app.swipeUp()
        admin.tap()
        // The web's own page, not its login form.
        let web = app.webViews.firstMatch
        XCTAssertTrue(web.waitForExistence(timeout: 20))
        let people = web.links.containing(NSPredicate(format: "label CONTAINS 'People'")).firstMatch
        XCTAssertTrue(people.waitForExistence(timeout: 20), app.debugDescription)
        XCTAssertFalse(web.secureTextFields.firstMatch.exists, "landed on the login form")
        // The app's tab bar is the navigation; the web leaves its own out here.
        XCTAssertFalse(web.links["Sessions"].exists && web.links["Me"].exists, "the web's tab bar is showing")
        snapshot("admin")
        app.buttons["Done"].firstMatch.tap()
        XCTAssertTrue(admin.waitForExistence(timeout: 10))
    }

    /// Phase 4c: join a session you don't belong to, change your role, add a night,
    /// and leave again. The night stays (nights aren't yours to delete); the seed is
    /// refreshed by the next test-DB reseed.
    @MainActor
    func testJoiningASessionAndAddingANight() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.sessions"].firstMatch.tap()
        let filter = app.buttons["sessions.search.filter"].firstMatch
        XCTAssertTrue(filter.waitForExistence(timeout: 10))
        filter.tap()
        let allActive = app.buttons["All Active"].firstMatch
        XCTAssertTrue(allActive.waitForExistence(timeout: 5))
        allActive.tap()
        app.buttons["filters.done"].tap()
        let boston = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Boston Celtic Session'")).firstMatch
        XCTAssertTrue(boston.waitForExistence(timeout: 10))
        boston.tap()
        // The session's details (and the role pill) fold under its band: open them.
        let band = app.buttons["session.band"]
        XCTAssertTrue(band.waitForExistence(timeout: 10))
        band.tap()

        let join = app.buttons["session.join"]
        let role = app.buttons["session.role"]
        // A run that failed partway may have left us a member: leave first.
        if role.waitForExistence(timeout: 5) {
            role.tap()
            app.buttons["role.leave"].tap()
            app.buttons.matching(NSPredicate(format: "label == 'Leave' AND identifier != 'role.leave'")).firstMatch.tap()
        }
        XCTAssertTrue(join.waitForExistence(timeout: 10))
        join.tap()
        let visiting = app.buttons["Just visiting"]
        XCTAssertTrue(visiting.waitForExistence(timeout: 5))
        visiting.tap()
        XCTAssertTrue(role.waitForExistence(timeout: 10))
        XCTAssertTrue(role.label.contains("Visitor"), role.label)
        snapshot("joined")

        role.tap()
        let member = app.buttons["I attend this session"].firstMatch
        XCTAssertTrue(member.waitForExistence(timeout: 5))
        member.tap()
        app.buttons["role.save"].tap()
        XCTAssertTrue(app.buttons["role.save"].waitForNonExistence(timeout: 10))
        XCTAssertTrue(role.label.contains("Member"), role.label)

        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        let addNight = app.buttons["session.addNight"]
        XCTAssertTrue(addNight.waitForExistence(timeout: 10))
        addNight.tap()
        let add = app.buttons["night.add"]
        XCTAssertTrue(add.waitForExistence(timeout: 10))
        snapshot("add night")
        add.tap()
        // Straight to the new night's log.
        XCTAssertTrue(app.staticTexts["No tunes logged yet."].waitForExistence(timeout: 10))
        snapshot("new night")
        app.navigationBars.buttons.firstMatch.tap()

        XCTAssertTrue(role.waitForExistence(timeout: 10))
        role.tap()
        app.buttons["role.leave"].tap()
        let leave = app.buttons.matching(NSPredicate(format: "label == 'Leave' AND identifier != 'role.leave'")).firstMatch
        XCTAssertTrue(leave.waitForExistence(timeout: 5))
        leave.tap()
        XCTAssertTrue(app.buttons["session.join"].waitForExistence(timeout: 10))
    }

    /// Phase 4d: add a session by hand (no thesession.org call), with a weekly schedule,
    /// and land on its page. Each run's name is new, so a second run isn't refused as a
    /// taken path; the test-DB reseed clears them (paths 'uitest-town/ui-test-session-*').
    @MainActor
    func testAddingASessionByHand() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.sessions"].firstMatch.tap()
        let add = app.buttons["sessions.add"]
        XCTAssertTrue(add.waitForExistence(timeout: 10))
        add.tap()
        let manual = app.buttons["addSession.manual"]
        XCTAssertTrue(manual.waitForExistence(timeout: 10))
        manual.tap()

        func type(_ id: String, _ text: String) {
            let f = app.textFields[id]
            XCTAssertTrue(f.waitForExistence(timeout: 5), id)
            f.tap()
            f.typeText(text)
        }
        let n = Int.random(in: 1000...9999)
        type("details.name", "UI Test Session \(n)")
        type("details.city", "UITest Town")
        type("details.state", "TX")
        type("details.country", "USA")
        // The path is made from the city and name as the web makes it.
        XCTAssertTrue(app.staticTexts["ceol.io/sessions/uitest-town/ui-test-session-\(n)"].exists)

        app.keyboards.buttons["Return"].firstMatch.tap()
        let repeats = app.buttons["details.repeats"]
        XCTAssertTrue(repeats.waitForExistence(timeout: 5))
        repeats.tap()
        let weekly = app.buttons["Weekly"].firstMatch
        XCTAssertTrue(weekly.waitForExistence(timeout: 5))
        weekly.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label BEGINSWITH 'Tuesdays from 7pm-10pm'")).firstMatch
            .waitForExistence(timeout: 5))
        snapshot("details")

        app.buttons["details.save"].tap()
        // Straight to the new session's page, as its admin (in the details under its band).
        let band = app.buttons["session.band"]
        XCTAssertTrue(band.waitForExistence(timeout: 15), app.debugDescription)
        band.tap()
        let role = app.buttons["session.role"]
        XCTAssertTrue(role.waitForExistence(timeout: 15), app.debugDescription)
        XCTAssertTrue(role.label.contains("Admin"), role.label)
        XCTAssertTrue(app.staticTexts["Tuesdays from 7:00pm-10:00pm"].exists || app.staticTexts.containing(
            NSPredicate(format: "label CONTAINS 'Tuesdays'")).firstMatch.exists)
        snapshot("created")
    }

    /// The + on Tunes: search the catalogue, add a tune at once as To Learn, open it,
    /// and remove it again.
    @MainActor
    func testAddingATuneFromThePlus() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.tunes"].firstMatch.tap()
        let plus = app.buttons["tunes.add"]
        XCTAssertTrue(plus.waitForExistence(timeout: 10))
        plus.tap()
        let query = app.textFields["addTune.query"]
        XCTAssertTrue(query.waitForExistence(timeout: 10))
        query.tap()
        query.typeText("kisco")
        let quickAdd = app.buttons["addTune.quickAdd"].firstMatch
        XCTAssertTrue(quickAdd.waitForExistence(timeout: 10))
        quickAdd.tap()
        XCTAssertTrue(app.images["On your list"].firstMatch.waitForExistence(timeout: 10)
            || app.otherElements["On your list"].firstMatch.exists || app.descendants(matching: .any)["On your list"].exists)
        snapshot("add a tune")
        app.buttons["addTune.row"].firstMatch.tap()
        let learn = app.buttons["sheet.status.want to learn"]
        XCTAssertTrue(learn.waitForExistence(timeout: 10))
        XCTAssertTrue(learn.isSelected)
        app.swipeUp()
        app.buttons["sheet.remove"].tap()
        let confirm = app.buttons.matching(NSPredicate(format: "label == 'Remove' AND identifier != 'sheet.remove'")).firstMatch
        XCTAssertTrue(confirm.waitForExistence(timeout: 5))
        confirm.tap()
        XCTAssertTrue(app.buttons["sheet.remove"].waitForNonExistence(timeout: 10))
    }

    /// Home's Learning box opens Tunes, filtered to the tunes you're learning.
    @MainActor
    func testHomeLearningOpensTunes() throws {
        let app = launch()
        signIn(app)
        let learning = app.buttons.containing(NSPredicate(format: "label CONTAINS[c] 'Learning'")).matching(
            NSPredicate(format: "identifier != 'tab.tunes'")).firstMatch
        app.swipeUp()
        XCTAssertTrue(learning.waitForExistence(timeout: 10))
        learning.tap()
        let segment = app.segmentedControls.buttons["Learning"]
        XCTAssertTrue(segment.waitForExistence(timeout: 10))
        XCTAssertTrue(segment.isSelected)
    }

    /// Lists scroll clear of the tab bar: at rest after scrolling to the end, the last
    /// row sits above the bar (it came to rest under it).
    @MainActor
    func testListsEndAboveTheTabBar() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.tunes"].firstMatch.tap()
        let last = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Rights Of Man'")).firstMatch
        XCTAssertTrue(last.waitForExistence(timeout: 10))
        for _ in 0..<3 { app.swipeUp() }
        sleep(1)
        let bar = app.buttons["tab.home"].firstMatch.frame.minY - 6
        snapshot("tunes end")
        XCTAssertLessThanOrEqual(last.frame.maxY, bar, "the last tune rests under the tab bar")

        app.buttons["tab.me"].firstMatch.tap()
        let signOut = app.buttons["me.signout"]
        XCTAssertTrue(signOut.waitForExistence(timeout: 10))
        for _ in 0..<3 { app.swipeUp() }
        sleep(1)
        snapshot("me end")
        XCTAssertLessThanOrEqual(signOut.frame.maxY, bar, "Log Out rests under the tab bar")
    }

    /// Share: the pane with a QR code and this screen's address; with a tune's drawer
    /// up, Share (still in reach above it) offers that tune.
    @MainActor
    func testSharingAScreenAndATune() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.tunes"].firstMatch.tap()
        let share = app.buttons["share"].firstMatch
        XCTAssertTrue(share.waitForExistence(timeout: 10))
        share.tap()
        XCTAssertTrue(app.images["share.qr"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["share.url"].label.hasSuffix("/my-tunes"), app.staticTexts["share.url"].label)
        snapshot("share")
        app.swipeDown(velocity: .fast)
        XCTAssertTrue(app.images["share.qr"].waitForNonExistence(timeout: 5))

        app.buttons.containing(NSPredicate(format: "label CONTAINS \"Cooley's\"")).firstMatch.tap()
        XCTAssertTrue(app.images["Notation for Cooley's"].waitForExistence(timeout: 20))
        snapshot("drawer below the bar")
        // Tapped where it is on screen: behind a sheet, accessibility calls it hidden
        // even though the drawer stops below the bar and the tap gets through.
        share.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(app.staticTexts["share.url"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["share.url"].label.contains("thesession.org/tunes/"), app.staticTexts["share.url"].label)
    }

    /// Phase 5a: a night shows what another client logs, live. The test is the other
    /// client: it signs in over the API and adds a tune to the night the app has open,
    /// then removes it again.
    @MainActor
    func testANightUpdatesLive() async throws {
        let api = try await TestAPI.signedIn(server: server)
        let nights = try await api.get("/api/sessions/austin/mueller/logs")
        let years = (nights["sorted_years"] as? [Any])?.compactMap { "\($0)" } ?? []
        let byYear = nights["instances_by_year"] as? [String: [[String: Any]]] ?? [:]
        let newest = try XCTUnwrap(years.first.flatMap { byYear[$0]?.first })
        let instanceID = try XCTUnwrap(newest["session_instance_id"] as? Int)

        let app = launch()
        signIn(app)
        app.buttons["tab.sessions"].firstMatch.tap()
        let mueller = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch
        XCTAssertTrue(mueller.waitForExistence(timeout: 10))
        mueller.tap()
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        let night = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[0-9]+ tunes?.*'")).firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        night.tap()
        let status = app.descendants(matching: .any)["night.status"]
        XCTAssertTrue(status.waitForExistence(timeout: 15))
        let live = NSPredicate(format: "label CONTAINS 'Live'")
        await fulfillment(of: [XCTNSPredicateExpectation(predicate: live, object: status)], timeout: 15)

        let name = "Live Test Reel \(Int.random(in: 1000...9999))"
        let added = try await api.post("/api/live/instances/\(instanceID)/ops", [
            "op_id": UUID().uuidString.lowercased(), "op_type": "add_tune", "name": name,
        ])
        let recordID = (added["record"] as? [String: Any])?["session_instance_tune_id"] as? Int
        XCTAssertTrue(app.staticTexts[name].waitForExistence(timeout: 10), "the tune didn't arrive live")
        snapshot("night live")
        if let recordID {
            _ = try await api.post("/api/live/instances/\(instanceID)/ops", [
                "op_id": UUID().uuidString.lowercased(), "op_type": "remove_tune", "record_id": recordID,
            ])
            XCTAssertTrue(app.staticTexts[name].waitForNonExistence(timeout: 10), "the removal didn't arrive live")
        }
    }

    /// Phase 5b.1: logging a night. Two tunes go in (shown at once, then saved), the set
    /// is split between them from the ↑ pill's seam, and then joined; one tune is swiped
    /// away and the other removed from its row. The server is checked after each step,
    /// and what's left is cleaned up.
    @MainActor
    func testLoggingANight() async throws {
        let api = try await TestAPI.signedIn(server: server)
        let nights = try await api.get("/api/sessions/austin/mueller/logs")
        let years = (nights["sorted_years"] as? [Any])?.compactMap { "\($0)" } ?? []
        let byYear = nights["instances_by_year"] as? [String: [[String: Any]]] ?? [:]
        let newest = try XCTUnwrap(years.first.flatMap { byYear[$0]?.first })
        let instanceID = try XCTUnwrap(newest["session_instance_id"] as? Int)
        func records() async throws -> [[String: Any]] {
            let b = try await api.get("/api/live/instances/\(instanceID)/bootstrap")
            return ((b["records"] as? [[String: Any]]) ?? [])
                .filter { ($0["deleted"] as? Bool) != true }
                .sorted { ($0["order_position"] as? String ?? "") < ($1["order_position"] as? String ?? "") }
        }
        func waitFor(_ what: String, _ check: ([[String: Any]]) -> Bool) async throws {
            for _ in 0..<40 {
                if check(try await records()) { return }
                try await Task.sleep(for: .milliseconds(250))
            }
            XCTFail("the server never showed: \(what)")
        }
        let before = try await records().compactMap { $0["session_instance_tune_id"] as? Int }

        let app = launch()
        signIn(app)
        app.buttons["tab.sessions"].firstMatch.tap()
        let mueller = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch
        XCTAssertTrue(mueller.waitForExistence(timeout: 10))
        mueller.tap()
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        let night = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[0-9]+ tunes?.*'")).firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        night.tap()
        let status = app.descendants(matching: .any)["night.status"]
        XCTAssertTrue(status.waitForExistence(timeout: 15))
        await fulfillment(
            of: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "label CONTAINS 'Live'"), object: status)], timeout: 15)

        app.buttons["night.edit"].tap()
        let input = app.textFields["log.input"]
        XCTAssertTrue(input.waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["tab.home"].exists, "the tab bar gives way to the composer")
        // A closed log starts a new set; an open one would need End set first.
        if app.buttons["log.endSet"].exists { app.buttons["log.endSet"].tap() }

        let n = Int.random(in: 1000...9999)
        let first = "Edit Test Jig \(n)"
        let second = "Edit Test Reel \(n)"
        input.tap()
        input.typeText(first + "\n")
        input.typeText(second)
        app.buttons["log.commit"].tap()
        XCTAssertTrue(app.staticTexts[first].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts[second].waitForExistence(timeout: 5))
        try await waitFor("both tunes, in order, in one set") { rs in
            let names = rs.map { ($0["record_type"] as? String) == "break" ? "|" : ($0["name"] as? String ?? "") }
            guard let i = names.firstIndex(of: first) else { return false }
            return i + 1 < names.count && names[i + 1] == second
        }
        snapshot("logged two")

        // Select the second tune, insert above it: the seam between them, with Split.
        app.staticTexts[second].tap()
        XCTAssertTrue(app.buttons["row.insertAbove"].waitForExistence(timeout: 3))
        snapshot("selected")
        app.buttons["row.insertAbove"].tap()
        XCTAssertTrue(app.buttons["seam.split"].waitForExistence(timeout: 3))
        app.buttons["seam.split"].tap()
        try await waitFor("a break between them") { rs in
            let names = rs.map { ($0["record_type"] as? String) == "break" ? "|" : ($0["name"] as? String ?? "") }
            guard let i = names.firstIndex(of: first) else { return false }
            return i + 2 < names.count && names[i + 1] == "|" && names[i + 2] == second
        }
        snapshot("split")
        // The same spot now joins them again.
        XCTAssertTrue(app.buttons["seam.join"].waitForExistence(timeout: 3))
        app.buttons["seam.join"].tap()
        try await waitFor("the break gone") { rs in
            let names = rs.map { ($0["record_type"] as? String) == "break" ? "|" : ($0["name"] as? String ?? "") }
            guard let i = names.firstIndex(of: first) else { return false }
            return i + 1 < names.count && names[i + 1] == second
        }

        // Swipe one away; remove the other from its row.
        app.staticTexts[second].swipeLeft()
        XCTAssertTrue(app.staticTexts[second].waitForNonExistence(timeout: 5))
        app.staticTexts[first].tap()
        XCTAssertTrue(app.buttons["row.remove"].waitForExistence(timeout: 3))
        app.buttons["row.remove"].tap()
        XCTAssertTrue(app.staticTexts[first].waitForNonExistence(timeout: 5))
        try await waitFor("both removed") { rs in !rs.contains { ($0["name"] as? String) == first || ($0["name"] as? String) == second } }

        app.buttons["night.done"].tap()
        XCTAssertTrue(app.buttons["night.edit"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["tab.home"].waitForExistence(timeout: 3))

        // Leave the night as it was: drop any break this test added.
        for r in try await records() where (r["record_type"] as? String) == "break" {
            if let id = r["session_instance_tune_id"] as? Int, !before.contains(id) {
                _ = try await api.post("/api/live/instances/\(instanceID)/ops", [
                    "op_id": UUID().uuidString.lowercased(), "op_type": "set_break", "action": "remove", "record_id": id,
                ])
            }
        }
    }

    /// Phase 5b.2: select mode. Three tunes are put on the night over the API; in the
    /// app the last is dragged by its handle to between the first two, two are deleted
    /// and brought back with Undo, one is copied and pasted, and a set's starter is set
    /// from its tray. The server is checked after each, and everything is cleaned up.
    @MainActor
    func testSelectModeMovesDeletesAndPastes() async throws {
        let api = try await TestAPI.signedIn(server: server)
        let nights = try await api.get("/api/sessions/austin/mueller/logs")
        let years = (nights["sorted_years"] as? [Any])?.compactMap { "\($0)" } ?? []
        let byYear = nights["instances_by_year"] as? [String: [[String: Any]]] ?? [:]
        let newest = try XCTUnwrap(years.first.flatMap { byYear[$0]?.first })
        let instanceID = try XCTUnwrap(newest["session_instance_id"] as? Int)
        let opsPath = "/api/live/instances/\(instanceID)/ops"
        func op(_ body: [String: Any]) async throws -> [String: Any] {
            try await api.post(opsPath, body.merging(["op_id": UUID().uuidString.lowercased()]) { a, _ in a })
        }
        func live() async throws -> [[String: Any]] {
            let b = try await api.get("/api/live/instances/\(instanceID)/bootstrap")
            return ((b["records"] as? [[String: Any]]) ?? [])
                .filter { ($0["deleted"] as? Bool) != true }
                .sorted { ($0["order_position"] as? String ?? "") < ($1["order_position"] as? String ?? "") }
        }
        let n = Int.random(in: 1000...9999)
        let (a, b, c) = ("Sel Alpha \(n)", "Sel Bravo \(n)", "Sel Charlie \(n)")
        func ours(_ rs: [[String: Any]]) -> [String] {
            rs.compactMap { $0["name"] as? String }.filter { $0.hasSuffix(" \(n)") }
        }
        func waitFor(_ what: String, _ check: ([[String: Any]]) -> Bool) async throws {
            for _ in 0..<40 {
                if check(try await live()) { return }
                try await Task.sleep(for: .milliseconds(250))
            }
            XCTFail("the server never showed: \(what) — it has \(ours(try await live()))")
        }
        let before = try await live().compactMap { $0["session_instance_tune_id"] as? Int }
        let wasHere = Set(((try await api.get("/api/live/instances/\(instanceID)/people")["people"] as? [[String: Any]]) ?? [])
            .filter { ($0["attending"] as? Bool) == true }.compactMap { $0["person_id"] as? Int })
        // A set of our own at the end.
        if let last = try await live().last, (last["record_type"] as? String) == "tune" {
            _ = try await op(["op_type": "set_break", "action": "insert", "after_record_id": NSNull()])
        }
        for name in [a, b, c] { _ = try await op(["op_type": "add_tune", "name": name]) }
        addTeardownBlock {
            await Self.clearAdded(api, instanceID, keeping: Set(before))
            await Self.checkOutAdded(api, instanceID, keeping: wasHere)
        }
        try await selectModeSteps(a, b, c, waitFor: waitFor, ours: ours)
    }

    /// Check out whoever was checked in since `keeping` was taken (a teardown block).
    static func checkOutAdded(_ api: TestAPI, _ instanceID: Int, keeping: Set<Int>) async {
        let now = (try? await api.get("/api/live/instances/\(instanceID)/people")["people"] as? [[String: Any]]) ?? []
        for p in now where (p["attending"] as? Bool) == true {
            if let id = p["person_id"] as? Int, !keeping.contains(id) {
                _ = try? await api.post("/api/live/instances/\(instanceID)/ops",
                                        ["op_id": UUID().uuidString.lowercased(), "op_type": "attendance_remove", "person_id": id])
            }
        }
    }

    @MainActor
    private func selectModeSteps(
        _ a: String, _ b: String, _ c: String,
        waitFor: (String, ([[String: Any]]) -> Bool) async throws -> Void,
        ours: @escaping ([[String: Any]]) -> [String]
    ) async throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.sessions"].firstMatch.tap()
        let mueller = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch
        XCTAssertTrue(mueller.waitForExistence(timeout: 10))
        mueller.tap()
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        let night = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[0-9]+ tunes?.*'")).firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        night.tap()
        XCTAssertTrue(app.buttons["night.edit"].waitForExistence(timeout: 15))
        app.buttons["night.edit"].tap()
        XCTAssertTrue(app.staticTexts[c].waitForExistence(timeout: 10))
        app.buttons["night.select"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["select.count"].waitForExistence(timeout: 3))

        // Drag Charlie by its handle to between Alpha and Bravo.
        let row = app.descendants(matching: .any).matching(identifier: "select.row")
            .containing(NSPredicate(format: "label == %@", c)).firstMatch
        let grab = row.descendants(matching: .any)["row.grab"]
        XCTAssertTrue(grab.waitForExistence(timeout: 3))
        let alpha = app.staticTexts[a]
        let bravo = app.staticTexts[b]
        let gap = (alpha.frame.maxY + bravo.frame.minY) / 2
        let origin = app.coordinate(withNormalizedOffset: .zero)
        let from = grab.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        let to = origin.withOffset(CGVector(dx: grab.frame.midX, dy: gap))
        from.press(forDuration: 0.05, thenDragTo: to, withVelocity: 300, thenHoldForDuration: 0.4)
        try await waitFor("Charlie between Alpha and Bravo") { ours($0) == [a, c, b] }
        snapshot("moved")

        // Delete two, then Undo.
        app.staticTexts[a].tap()
        app.staticTexts[b].tap()
        XCTAssertEqual(app.descendants(matching: .any)["select.count"].label, "2 selected")
        app.buttons["select.delete"].tap()
        XCTAssertTrue(app.staticTexts[a].waitForNonExistence(timeout: 5))
        try await waitFor("Alpha and Bravo deleted") { ours($0) == [c] }
        XCTAssertTrue(app.buttons["toast.undo"].waitForExistence(timeout: 3))
        snapshot("undo")
        app.buttons["toast.undo"].tap()
        XCTAssertTrue(app.staticTexts[a].waitForExistence(timeout: 5))
        try await waitFor("Alpha and Bravo back") { ours($0) == [a, c, b] }

        // Copy Charlie, paste it (at the cursor: after the moved tune).
        app.staticTexts[c].tap()
        app.buttons["select.copy"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["toast.flash"].waitForExistence(timeout: 3))
        app.buttons["select.paste"].tap()
        try await waitFor("a second Charlie") { ours($0).filter { $0 == c }.count == 2 }

        // Set the starter from the set's tray, where the session tracks starters.
        app.buttons["select.done"].tap()
        let label = app.descendants(matching: .any).matching(identifier: "set.label").allElementsBoundByIndex.last
        if let label, label.exists {
            label.tap()
            let starter = app.buttons["tray.starter"]
            if starter.waitForExistence(timeout: 3) {
                starter.tap()
                let person = app.buttons.matching(identifier: "people.person").firstMatch
                XCTAssertTrue(person.waitForExistence(timeout: 10))
                snapshot("starter picker")
                person.tap()
                try await waitFor("a starter on our set") { rs in
                    rs.contains { ($0["name"] as? String) == c && !($0["started_by_person_id"] is NSNull) && $0["started_by_person_id"] != nil }
                }
            }
        }
        app.buttons["night.done"].tap()
    }

    /// Phase 5c: finding tunes as you type. A name the session knows logs at once; "maid"
    /// shows several and one is tapped; Enter on "maid" once the answer is in asks which,
    /// and the first choice is taken; a name nothing matches logs unlinked, and is then
    /// edited and relinked from the suggestions; deep search logs a tune from its sheet.
    /// Each lands on the server as expected; everything added is removed after.
    @MainActor
    func testFindingTunesAsYouType() async throws {
        let api = try await TestAPI.signedIn(server: server)
        let nights = try await api.get("/api/sessions/austin/mueller/logs")
        let years = (nights["sorted_years"] as? [Any])?.compactMap { "\($0)" } ?? []
        let byYear = nights["instances_by_year"] as? [String: [[String: Any]]] ?? [:]
        let newest = try XCTUnwrap(years.first.flatMap { byYear[$0]?.first })
        let instanceID = try XCTUnwrap(newest["session_instance_id"] as? Int)
        func live() async throws -> [[String: Any]] {
            let b = try await api.get("/api/live/instances/\(instanceID)/bootstrap")
            return ((b["records"] as? [[String: Any]]) ?? [])
                .filter { ($0["deleted"] as? Bool) != true }
                .sorted { ($0["order_position"] as? String ?? "") < ($1["order_position"] as? String ?? "") }
        }
        let before = Set(try await live().compactMap { $0["session_instance_tune_id"] as? Int })
        func added() async throws -> [[String: Any]] {
            try await live().filter { ($0["record_type"] as? String) == "tune" && !before.contains($0["session_instance_tune_id"] as? Int ?? -1) }
        }
        func waitFor(_ what: String, _ check: ([[String: Any]]) -> Bool) async throws {
            for _ in 0..<40 {
                if check(try await added()) { return }
                try await Task.sleep(for: .milliseconds(250))
            }
            XCTFail("the server never showed: \(what) — added: \(try await added().map { "\($0["name"] ?? "?") #\($0["tune_id"] ?? "-")" })")
        }
        func linked(_ rs: [[String: Any]], _ name: String) -> Bool {
            rs.contains { ($0["name"] as? String) == name && $0["tune_id"] is Int }
        }
        addTeardownBlock { await Self.clearAdded(api, instanceID, keeping: before) }
        try await findingSteps(waitFor: waitFor, linked: linked)
    }

    /// Remove every row added to a night since `keeping` was taken (a teardown block, so
    /// it runs even when a failed tap stops the test).
    static func clearAdded(_ api: TestAPI, _ instanceID: Int, keeping: Set<Int>) async {
        func rows() async -> [[String: Any]] {
            let b = (try? await api.get("/api/live/instances/\(instanceID)/bootstrap")) ?? [:]
            return ((b["records"] as? [[String: Any]]) ?? []).filter { ($0["deleted"] as? Bool) != true }
        }
        let ops = "/api/live/instances/\(instanceID)/ops"
        let tunes = await rows().filter { ($0["record_type"] as? String) == "tune" }
            .compactMap { $0["session_instance_tune_id"] as? Int }.filter { !keeping.contains($0) }
        if !tunes.isEmpty {
            _ = try? await api.post(ops, ["op_id": UUID().uuidString.lowercased(), "op_type": "remove_tunes", "record_ids": tunes])
        }
        for r in await rows() where (r["record_type"] as? String) == "break" {
            if let id = r["session_instance_tune_id"] as? Int, !keeping.contains(id) {
                _ = try? await api.post(ops, ["op_id": UUID().uuidString.lowercased(), "op_type": "set_break", "action": "remove", "record_id": id])
            }
        }
    }

    @MainActor
    private func findingSteps(
        waitFor: (String, ([[String: Any]]) -> Bool) async throws -> Void,
        linked: @escaping ([[String: Any]], String) -> Bool
    ) async throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.sessions"].firstMatch.tap()
        let mueller = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch
        XCTAssertTrue(mueller.waitForExistence(timeout: 10))
        mueller.tap()
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        let night = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[0-9]+ tunes?.*'")).firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        night.tap()
        XCTAssertTrue(app.buttons["night.edit"].waitForExistence(timeout: 15))
        app.buttons["night.edit"].tap()
        let input = app.textFields["log.input"]
        XCTAssertTrue(input.waitForExistence(timeout: 5))
        // A set of our own (an open set could merge a repeated tune), and the vocabulary.
        if app.buttons["log.endSet"].exists { app.buttons["log.endSet"].tap() }
        try await Task.sleep(for: .seconds(1.5))

        // A name the session knows: logged, linked, at once.
        input.tap()
        input.typeText("drowsy maggie\n")
        try await waitFor("Drowsy Maggie, linked") { linked($0, "Drowsy Maggie") }

        // Several match: tap one.
        input.typeText("maid")
        let sligo = app.buttons.matching(identifier: "suggest.row").containing(NSPredicate(format: "label CONTAINS 'Sligo Maid'")).firstMatch
        XCTAssertTrue(sligo.waitForExistence(timeout: 5))
        snapshot("suggestions")
        sligo.tap()
        try await waitFor("Sligo Maid, linked") { linked($0, "Sligo Maid, The") }

        // Enter once the answer is in, with several and none exact: choose.
        input.typeText("maid")
        XCTAssertTrue(sligo.waitForExistence(timeout: 5))
        try await Task.sleep(for: .milliseconds(600))
        app.buttons["log.commit"].tap()
        let asIs = app.buttons["suggest.asIs"]
        XCTAssertTrue(asIs.waitForExistence(timeout: 5), "several matches should ask which")
        snapshot("ambiguous")
        let first = app.buttons.matching(identifier: "suggest.row").containing(NSPredicate(format: "label CONTAINS 'Maid Behind'")).firstMatch
        first.tap()
        try await waitFor("Maid Behind The Bar, linked") { linked($0, "Maid Behind The Bar, The") }

        // Nothing matches: unlinked. Then edit it and relink from the suggestions.
        let odd = "Zzqx Unknown \(Int.random(in: 1000...9999))"
        input.typeText(odd + "\n")
        try await waitFor("the unmatched name, unlinked") { rs in rs.contains { ($0["name"] as? String) == odd && $0["tune_id"] is NSNull } }
        XCTAssertTrue(app.staticTexts[odd].waitForExistence(timeout: 5))
        app.staticTexts[odd].tap()
        XCTAssertTrue(app.buttons["row.edit"].waitForExistence(timeout: 3))
        app.buttons["row.edit"].tap()
        XCTAssertTrue(app.buttons["edit.cancel"].waitForExistence(timeout: 3))
        app.buttons["Clear entry"].tap()
        input.typeText("banish")
        let banish = app.buttons.matching(identifier: "suggest.row").containing(NSPredicate(format: "label CONTAINS 'Banish Misfortune'")).firstMatch
        XCTAssertTrue(banish.waitForExistence(timeout: 5))
        snapshot("editing")
        banish.tap()
        try await waitFor("the unmatched row relinked") { linked($0, "Banish Misfortune") }

        // Deep search.
        input.typeText("silver")
        XCTAssertTrue(app.buttons["log.search"].waitForExistence(timeout: 3))
        app.buttons["log.search"].tap()
        let card = app.buttons.matching(identifier: "deep.result").containing(NSPredicate(format: "label CONTAINS 'Silver Spear'")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 10))
        snapshot("deep search")
        card.tap()
        try await waitFor("Silver Spear from deep search") { linked($0, "Silver Spear, The") }
        app.buttons["night.done"].tap()
    }

    /// Phase 5d: logging without a connection. Offline, two tunes are logged and an
    /// existing one is renamed: all three wait on the phone, marked, and the server has
    /// none of them. The app is quit and reopened, still offline: they're still there.
    /// Meanwhile someone else removes the renamed tune. Back online, the two tunes arrive
    /// in order, and the rename is refused and listed for review.
    @MainActor
    func testLoggingOffline() async throws {
        let api = try await TestAPI.signedIn(server: server)
        let nights = try await api.get("/api/sessions/austin/mueller/logs")
        let years = (nights["sorted_years"] as? [Any])?.compactMap { "\($0)" } ?? []
        let byYear = nights["instances_by_year"] as? [String: [[String: Any]]] ?? [:]
        let newest = try XCTUnwrap(years.first.flatMap { byYear[$0]?.first })
        let instanceID = try XCTUnwrap(newest["session_instance_id"] as? Int)
        let opsPath = "/api/live/instances/\(instanceID)/ops"
        func live() async throws -> [[String: Any]] {
            let b = try await api.get("/api/live/instances/\(instanceID)/bootstrap")
            return ((b["records"] as? [[String: Any]]) ?? []).filter { ($0["deleted"] as? Bool) != true }
                .sorted { ($0["order_position"] as? String ?? "") < ($1["order_position"] as? String ?? "") }
        }
        let before = Set(try await live().compactMap { $0["session_instance_tune_id"] as? Int })
        addTeardownBlock { await Self.clearAdded(api, instanceID, keeping: before) }
        let n = Int.random(in: 1000...9999)
        let (target, one, two, renamed) = ("Off Target \(n)", "Off One \(n)", "Off Two \(n)", "Off Renamed \(n)")
        // A set of our own, holding the tune that will be renamed.
        _ = try await api.post(opsPath, ["op_id": UUID().uuidString.lowercased(), "op_type": "set_break", "action": "insert", "after_record_id": NSNull()])
        let added = try await api.post(opsPath, ["op_id": UUID().uuidString.lowercased(), "op_type": "add_tune", "name": target, "no_match": true])
        let targetID = try XCTUnwrap((added["record"] as? [String: Any])?["session_instance_tune_id"] as? Int)

        let hooks = ["-CeolTestHooks", "YES"]
        var app = launch(extra: hooks)
        signIn(app)
        openNewestMuellerNight(app)
        XCTAssertTrue(app.buttons["night.edit"].waitForExistence(timeout: 15))
        app.buttons["night.edit"].tap()
        let input = app.textFields["log.input"]
        XCTAssertTrue(input.waitForExistence(timeout: 5))

        // No signal.
        app.switches["debug.offline"].firstMatch.tap()
        let status = app.descendants(matching: .any)["night.status"]
        await fulfillment(of: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "label CONTAINS 'Offline'"), object: status)], timeout: 5)
        input.tap()
        input.typeText(one + "\n")
        input.typeText(two + "\n")
        XCTAssertTrue(app.staticTexts[two].waitForExistence(timeout: 5))
        // Rename the existing tune.
        app.staticTexts[target].tap()
        XCTAssertTrue(app.buttons["row.edit"].waitForExistence(timeout: 3))
        app.buttons["row.edit"].tap()
        app.buttons["Clear entry"].tap()
        input.typeText(renamed)
        app.buttons["log.commit"].tap()
        XCTAssertTrue(app.staticTexts[renamed].waitForExistence(timeout: 5))
        let banner = app.staticTexts["queued.banner"]
        XCTAssertTrue(banner.waitForExistence(timeout: 5))
        XCTAssertTrue(banner.label.contains("3 changes queued"), banner.label)
        XCTAssertEqual(app.descendants(matching: .any).matching(identifier: "row.offline").count, 2)
        snapshot("offline queue")
        var names = try await live().compactMap { $0["name"] as? String }
        XCTAssertFalse(names.contains(one), "nothing should reach the server offline")

        // Quit and come back, still offline: the queue is still there.
        app.terminate()
        app = launch(reset: false, extra: hooks + ["-CeolStartOffline", "YES"])
        openNewestMuellerNight(app)
        XCTAssertTrue(app.staticTexts[two].waitForExistence(timeout: 10), "the saved copy should show")
        XCTAssertTrue(app.staticTexts["queued.banner"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["queued.banner"].label.contains("3 changes queued"))

        // Someone else removes the tune that was renamed.
        _ = try await api.post(opsPath, ["op_id": UUID().uuidString.lowercased(), "op_type": "remove_tune", "record_id": targetID])

        // Signal again.
        app.switches["debug.offline"].firstMatch.tap()
        XCTAssertTrue(app.buttons["review.ok"].waitForExistence(timeout: 15), "the refused rename should be listed")
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Edit “\(renamed)” — it had already been removed")).firstMatch.exists)
        snapshot("review")
        app.buttons["review.ok"].tap()
        for _ in 0..<20 {
            names = try await live().compactMap { $0["name"] as? String }
            if names.contains(two) { break }
            try await Task.sleep(for: .milliseconds(250))
        }
        let ours = names.filter { $0.hasSuffix(" \(n)") }
        XCTAssertEqual(ours, [one, two], "both queued tunes, in order, and the removed one stays removed")
        XCTAssertFalse(app.staticTexts["queued.banner"].exists)
        // And on screen: the removed tune isn't brought back by undoing the refused rename.
        XCTAssertTrue(app.staticTexts[two].exists)
        XCTAssertFalse(app.staticTexts[target].exists, "the tune someone else removed came back")
        XCTAssertFalse(app.staticTexts[renamed].exists)
    }

    @MainActor
    private func openNewestMuellerNight(_ app: XCUIApplication) {
        app.buttons["tab.sessions"].firstMatch.tap()
        let mueller = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch
        XCTAssertTrue(mueller.waitForExistence(timeout: 10))
        mueller.tap()
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        let night = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[0-9]+ tunes?.*'")).firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        night.tap()
    }

    /// Phase 5e: who's there. Sarah (a second account, over the API) opens the night to
    /// log: her initials appear in the header, and when she types, "Sarah O'Connor is
    /// typing…" shows above the box. From the header's details, someone is checked in and
    /// out, and someone new is added; the server agrees each time.
    @MainActor
    func testWhoIsThere() async throws {
        let api = try await TestAPI.signedIn(server: server)
        let sarah = try await TestAPI.signedIn(server: server, email: "sarah.oconnor@example.com")
        let nights = try await api.get("/api/sessions/austin/mueller/logs")
        let years = (nights["sorted_years"] as? [Any])?.compactMap { "\($0)" } ?? []
        let byYear = nights["instances_by_year"] as? [String: [[String: Any]]] ?? [:]
        let newest = try XCTUnwrap(years.first.flatMap { byYear[$0]?.first })
        let instanceID = try XCTUnwrap(newest["session_instance_id"] as? Int)
        let config = try await api.get("/api/app-config")
        let stream = try XCTUnwrap(config["streaming_base_url"] as? String)
        func people() async throws -> [[String: Any]] {
            (try await api.get("/api/live/instances/\(instanceID)/people")["people"] as? [[String: Any]]) ?? []
        }
        let before = try await people()
        let wasHere = Set(before.filter { $0["attending"] as? Bool == true }.compactMap { $0["person_id"] as? Int })
        addTeardownBlock {
            // Leave attendance as it was: check out whoever this test checked in.
            let now = (try? await api.get("/api/live/instances/\(instanceID)/people")["people"] as? [[String: Any]]) ?? []
            for p in now where (p["attending"] as? Bool) == true {
                if let id = p["person_id"] as? Int, !wasHere.contains(id) {
                    _ = try? await api.post("/api/live/instances/\(instanceID)/ops",
                                            ["op_id": UUID().uuidString.lowercased(), "op_type": "attendance_remove", "person_id": id])
                }
            }
        }

        // Sarah, logging: an edit connection held open.
        var events = URLRequest(url: URL(string: "\(stream)/live/instances/\(instanceID)/events?mode=edit")!)
        events.setValue("Bearer \(sarah.token)", forHTTPHeaderField: "Authorization")
        events.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        let held = Task {
            if let (bytes, _) = try? await URLSession.shared.bytes(for: events) {
                for try await _ in bytes {}
            }
        }
        defer { held.cancel() }

        let app = launch()
        signIn(app)
        openNewestMuellerNight(app)
        let presence = app.descendants(matching: .any)["presence"]
        XCTAssertTrue(presence.waitForExistence(timeout: 15))
        let sarahAvatar = app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH %@", "Sarah O")).firstMatch
        XCTAssertTrue(sarahAvatar.waitForExistence(timeout: 10), "Sarah should show as logging")

        // Typing: shown to those logging.
        app.buttons["night.edit"].tap()
        XCTAssertTrue(app.textFields["log.input"].waitForExistence(timeout: 5))
        var typing = URLRequest(url: URL(string: "\(stream)/live/instances/\(instanceID)/typing")!)
        typing.httpMethod = "POST"
        typing.setValue("Bearer \(sarah.token)", forHTTPHeaderField: "Authorization")
        typing.setValue("application/json", forHTTPHeaderField: "Content-Type")
        typing.httpBody = try JSONSerialization.data(withJSONObject: ["typing": true, "anchor": NSNull()])
        _ = try await URLSession.shared.data(for: typing)
        let line = app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "is typing…")).firstMatch
        XCTAssertTrue(line.waitForExistence(timeout: 10))
        XCTAssertTrue(line.label.contains("Sarah"), line.label)
        snapshot("typing")
        typing.httpBody = try JSONSerialization.data(withJSONObject: ["typing": false, "anchor": NSNull()])
        _ = try await URLSession.shared.data(for: typing)
        XCTAssertTrue(line.waitForNonExistence(timeout: 10))

        // Sarah's changes, said in a line each.
        let tune = "Toast Test \(Int.random(in: 1000...9999))"
        let added = try await sarah.post("/api/live/instances/\(instanceID)/ops",
                                         ["op_id": UUID().uuidString.lowercased(), "op_type": "add_tune", "name": tune, "no_match": true])
        // The actor is named as the log names loggers: "Sarah O".
        let said = app.staticTexts["Sarah O added \(tune)"]
        XCTAssertTrue(said.waitForExistence(timeout: 10), "an activity line for Sarah's add")
        snapshot("activity")
        if let id = (added["record"] as? [String: Any])?["session_instance_tune_id"] as? Int {
            _ = try await sarah.post("/api/live/instances/\(instanceID)/ops",
                                     ["op_id": UUID().uuidString.lowercased(), "op_type": "remove_tune", "record_id": id])
            XCTAssertTrue(app.staticTexts["Sarah O removed \(tune)"].waitForExistence(timeout: 10))
        }
        XCTAssertTrue(said.waitForNonExistence(timeout: 8), "the line goes after a few seconds")
        app.buttons["night.done"].tap()

        // Attendance, from the header's details.
        app.descendants(matching: .any)["night.header"].firstMatch.tap()
        XCTAssertTrue(app.buttons["attendance.manage"].waitForExistence(timeout: 10))
        snapshot("details")
        app.buttons["attendance.manage"].tap()
        let absent = try XCTUnwrap(before.first { ($0["attending"] as? Bool) != true && ($0["archived"] as? Bool) != true })
        let name = try XCTUnwrap(absent["display_name"] as? String)
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        search.typeText(name)
        let row = app.buttons.matching(identifier: "people.person").containing(NSPredicate(format: "label CONTAINS %@", name)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        func attending(_ id: Int) async throws -> Bool {
            try await people().first { $0["person_id"] as? Int == id }?["attending"] as? Bool == true
        }
        let id = try XCTUnwrap(absent["person_id"] as? Int)
        for _ in 0..<20 where !(try await attending(id)) { try await Task.sleep(for: .milliseconds(250)) }
        let checkedIn = try await attending(id)
        XCTAssertTrue(checkedIn, "checked in on the server")
        // Check out again.
        search.tap()
        search.typeText(name)
        let out = app.buttons.matching(identifier: "people.checkOut").firstMatch
        XCTAssertTrue(out.waitForExistence(timeout: 5))
        snapshot("attendance")
        out.tap()
        for _ in 0..<20 where try await attending(id) { try await Task.sleep(for: .milliseconds(250)) }
        let stillIn = try await attending(id)
        XCTAssertFalse(stillIn, "checked out on the server")

        // Someone new.
        let newName = "Zed Tester\(Int.random(in: 1000...9999))"
        search.tap()
        if search.buttons["Clear text"].exists { search.buttons["Clear text"].tap() }
        search.typeText(newName)
        XCTAssertTrue(app.buttons["people.add"].waitForExistence(timeout: 5))
        app.buttons["people.add"].tap()
        XCTAssertTrue(app.buttons["newPerson.add"].waitForExistence(timeout: 5))
        app.buttons["newPerson.add"].tap()
        var found = false
        for _ in 0..<20 {
            found = try await people().contains { ($0["display_name"] as? String) == newName && ($0["attending"] as? Bool) == true }
            if found { break }
            try await Task.sleep(for: .milliseconds(250))
        }
        XCTAssertTrue(found, "the new person, checked in")
        app.buttons["people.done"].tap()
    }

    /// Phase 3d: Me shows the profile and opens it to edit (cancelled: seed data stays put).
    @MainActor
    func testMeShowsTheProfile() throws {
        let app = launch()
        signIn(app)
        app.buttons["tab.me"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Ian Varley"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS '@ian' AND label CONTAINS 'Austin'")).firstMatch.exists)
        XCTAssertTrue(app.descendants(matching: .any).containing(NSPredicate(format: "label CONTAINS 'Fiddle'")).firstMatch.exists)
        XCTAssertFalse(app.buttons["me.delete"].exists, "not offered to a system admin")
        XCTAssertTrue(app.switches["me.updateEmails"].exists || app.descendants(matching: .any)["me.updateEmails"].exists)
        snapshot("me")
        app.buttons["me.edit"].tap()
        XCTAssertTrue(app.navigationBars["Edit profile"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.textFields["First name"].waitForExistence(timeout: 10))
        snapshot("edit")
        app.buttons["Cancel"].tap()
        XCTAssertTrue(app.navigationBars["Edit profile"].waitForNonExistence(timeout: 5))
    }

    @MainActor
    func testPasswordSignInThenSignOut() throws {
        let app = launch()

        let email = app.textFields["signin.email"]
        XCTAssertTrue(email.waitForExistence(timeout: 15))
        email.tap()
        email.typeText("ian@ceol.io")
        app.buttons["signin.continue"].tap()

        let password = app.secureTextFields["signin.password"]
        XCTAssertTrue(password.waitForExistence(timeout: 10))
        password.tap()
        password.typeText("password123")
        app.buttons["signin.submit"].tap()

        // Signed in: the tabs, and Me knows who we are.
        let me = app.buttons["tab.me"].firstMatch
        XCTAssertTrue(me.waitForExistence(timeout: 10))
        me.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'Ian'")).firstMatch.waitForExistence(timeout: 5))

        app.buttons["me.signout"].tap()
        // The confirmation dialog's button, not the list's own (which it covers).
        let confirm = app.buttons.matching(NSPredicate(format: "label == 'Sign out' AND identifier != 'me.signout'")).firstMatch
        XCTAssertTrue(confirm.waitForExistence(timeout: 5))
        confirm.tap()
        XCTAssertTrue(app.textFields["signin.email"].waitForExistence(timeout: 10))
    }

    @MainActor
    func testAWrongPasswordSaysSo() throws {
        let app = launch()
        let email = app.textFields["signin.email"]
        XCTAssertTrue(email.waitForExistence(timeout: 15))
        email.tap()
        email.typeText("ian@ceol.io")
        app.buttons["signin.continue"].tap()
        let password = app.secureTextFields["signin.password"]
        XCTAssertTrue(password.waitForExistence(timeout: 10))
        password.tap()
        password.typeText("not-the-password")
        app.buttons["signin.submit"].tap()
        XCTAssertTrue(app.staticTexts["signin.error"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["tab.me"].firstMatch.exists)
    }

    @MainActor
    func testADeadLinkExplainsItself() throws {
        let app = launch(openURL: "\(server!)/auth/login/no-such-token")
        let message = app.staticTexts["signin.linkError"]
        XCTAssertTrue(message.waitForExistence(timeout: 15))
        XCTAssertTrue(message.label.contains("expired"))
    }

    @MainActor
    func testDeletingTheAccount() throws {
        let env = ProcessInfo.processInfo.environment
        guard let token = env["CEOL_TEST_DELETE_TOKEN"], let email = env["CEOL_TEST_DELETE_EMAIL"], !token.isEmpty else {
            throw XCTSkip("No throwaway account (make ios-ui-test creates one).")
        }
        let app = launch(openURL: "\(server!)/auth/login/\(token)")
        let me = app.buttons["tab.me"].firstMatch
        XCTAssertTrue(me.waitForExistence(timeout: 15))
        me.tap()
        app.buttons["me.delete"].tap()

        let confirm = app.buttons["delete.confirm"]
        XCTAssertTrue(confirm.waitForExistence(timeout: 5))
        XCTAssertFalse(confirm.isEnabled, "stays disabled until the email is typed")
        let field = app.textFields["delete.email"]
        field.tap()
        field.typeText(email)
        XCTAssertTrue(confirm.isEnabled)
        confirm.tap()

        let notice = app.staticTexts["signin.notice"]
        XCTAssertTrue(notice.waitForExistence(timeout: 10))
        XCTAssertTrue(notice.label.contains("deleted"))
    }

    @MainActor
    func testAnEmailedLinkSignsIn() throws {
        guard let token = ProcessInfo.processInfo.environment["CEOL_TEST_LOGIN_TOKEN"], !token.isEmpty else {
            throw XCTSkip("No CEOL_TEST_LOGIN_TOKEN (make ios-ui-test mints one).")
        }
        let app = launch(openURL: "\(server!)/auth/login/\(token)")
        XCTAssertTrue(app.buttons["tab.me"].firstMatch.waitForExistence(timeout: 15))
    }
}


/// The server as a second client would use it, for tests that need something to happen
/// while the app watches: signed in with the seeded admin over the API.
struct TestAPI: Sendable {
    let server: String
    let token: String

    static func signedIn(server: String, email: String = "ian@ceol.io") async throws -> TestAPI {
        var r = URLRequest(url: URL(string: server + "/api/auth/login-password")!)
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.setValue("ios/0.0.0 (ui-test)", forHTTPHeaderField: "X-Ceol-Client")
        r.httpBody = try JSONSerialization.data(withJSONObject: ["email": email, "password": "password123"])
        let (data, _) = try await URLSession.shared.data(for: r)
        let body = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return TestAPI(server: server, token: try XCTUnwrap(body?["token"] as? String))
    }

    func get(_ path: String) async throws -> [String: Any] {
        try await send(URLRequest(url: URL(string: server + path)!))
    }

    func post(_ path: String, _ body: [String: Any]) async throws -> [String: Any] {
        var r = URLRequest(url: URL(string: server + path)!)
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await send(r)
    }

    private func send(_ request: URLRequest) async throws -> [String: Any] {
        var r = request
        r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        r.setValue("ios/0.0.0 (ui-test)", forHTTPHeaderField: "X-Ceol-Client")
        let (data, _) = try await URLSession.shared.data(for: r)
        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }
}

