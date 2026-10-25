import XCTest

/// The tune sheet's four tabs (My List, Details, History, Played With): History's
/// "Change…" offers the session, each of its nights, your sessions and every session;
/// a night opens its log at the play; Played With pushes a companion's sheet; from
/// your own list History lands on every session. Screenshots go to CEOL_SHOTS when set.
final class TuneHistoryUITests: XCTestCase {
    private var server: String!

    override func setUpWithError() throws {
        continueAfterFailure = false
        guard let s = ProcessInfo.processInfo.environment["CEOL_TEST_SERVER"], !s.isEmpty else {
            throw XCTSkip("No CEOL_TEST_SERVER: UI tests need a development server (make ios-ui-test).")
        }
        server = s
    }

    private func snapshot(_ name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let shot = XCTAttachment(screenshot: screenshot)
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
        if let dir = ProcessInfo.processInfo.environment["CEOL_SHOTS"], !dir.isEmpty {
            try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
        }
    }

    private func signIn(_ app: XCUIApplication) {
        let button = app.buttons["home.signIn"]
        XCTAssertTrue(button.waitForExistence(timeout: 15))
        button.tap()
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
        XCTAssertTrue(password.waitForNonExistence(timeout: 10))
        XCTAssertTrue(app.buttons["tab.me"].firstMatch.waitForExistence(timeout: 10))
    }

    /// Scrolls the sheet until the element can be tapped.
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<4 where !element.isHittable { app.swipeUp() }
        XCTAssertTrue(element.isHittable, "\(element) never came into view")
    }

    private func openDrowsyMaggieAtMueller(_ app: XCUIApplication) {
        app.buttons["tab.sessions"].firstMatch.tap()
        let search = app.textFields["sessions.search"]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        search.typeText("Mueller")
        let row = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        // The session's tab strip, not the app's Tunes tab under it.
        let tunesTab = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Tunes' AND identifier != 'tab.tunes'")).firstMatch
        XCTAssertTrue(tunesTab.waitForExistence(timeout: 15))
        tunesTab.tap()
        let tuneSearch = app.textFields["session.tunes.search"]
        XCTAssertTrue(tuneSearch.waitForExistence(timeout: 10))
        tuneSearch.tap()
        tuneSearch.typeText("Drowsy")
        let tune = app.buttons["session.tune"].firstMatch
        XCTAssertTrue(tune.waitForExistence(timeout: 10))
        tune.tap()
    }

    @MainActor
    func testTheSheetsTabsAndHistoryChoices() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-CeolServerURL", server, "-CeolResetSession", "YES"]
        app.launch()
        signIn(app)
        openDrowsyMaggieAtMueller(app)

        // Signed in, the sheet lands on My List; Configure folds out your own fields.
        let historyTab = app.buttons["History"].firstMatch
        XCTAssertTrue(historyTab.waitForExistence(timeout: 15))
        let configure = app.buttons["sheet.configure"]
        XCTAssertTrue(configure.waitForExistence(timeout: 10))
        sleep(1)
        snapshot("1 my list")
        reveal(app, configure)
        configure.tap()
        XCTAssertTrue(app.textFields["sheet.myAlias"].waitForExistence(timeout: 5))
        sleep(1)
        snapshot("2 my list configure")

        // Details: the session's block (Ian administers Mueller) and the counts.
        app.buttons["Details"].firstMatch.tap()
        let here = app.buttons["sheet.historyHere"]
        XCTAssertTrue(here.waitForExistence(timeout: 10))
        XCTAssertTrue(app.textFields["sheet.sessAlias"].exists)
        sleep(1)
        snapshot("3 details")

        // The count opens History on this session.
        reveal(app, here)
        here.tap()
        let scopeLabel = app.staticTexts["history.change.label"]
        XCTAssertTrue(scopeLabel.waitForExistence(timeout: 10))
        XCTAssertEqual(scopeLabel.label, "At Mueller Session")
        let night = app.buttons["history.night"].firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 15))
        XCTAssertEqual(app.switches["history.attended"].firstMatch.value as? String, "0")
        sleep(1)
        snapshot("4 history at this session")

        // Change…: the session, each of its nights, my sessions, every session.
        app.buttons["history.change"].tap()
        let option = app.buttons.matching(identifier: "scope.option")
        XCTAssertTrue(option.firstMatch.waitForExistence(timeout: 10))
        XCTAssertGreaterThanOrEqual(option.count, 4)
        sleep(1)
        snapshot("5 history choices")
        option.matching(NSPredicate(format: "label BEGINSWITH '… on'")).firstMatch.tap()
        XCTAssertTrue(app.buttons["history.position"].firstMatch.waitForExistence(timeout: 10))
        XCTAssertTrue(scopeLabel.label.hasPrefix("On "))
        sleep(1)
        snapshot("6 one night")
        app.buttons["history.change"].tap()
        XCTAssertTrue(option.firstMatch.waitForExistence(timeout: 10))
        option.matching(NSPredicate(format: "label == 'All my sessions'")).firstMatch.tap()
        XCTAssertTrue(night.waitForExistence(timeout: 15))
        XCTAssertEqual(scopeLabel.label, "All my sessions")
        sleep(1)
        snapshot("7 history at my sessions")

        // Played With: companions, each pushing its own sheet.
        app.buttons["Played With"].firstMatch.tap()
        let companion = app.buttons["playedwith.row"].firstMatch
        XCTAssertTrue(companion.waitForExistence(timeout: 15))
        XCTAssertEqual(app.staticTexts["playedwith.change.label"].label, "At Mueller Session")
        sleep(1)
        snapshot("8 played with")
        reveal(app, companion)
        companion.tap()
        XCTAssertTrue(app.navigationBars.buttons.element(boundBy: 0).waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["Details"].firstMatch.waitForExistence(timeout: 15))
        sleep(2)
        snapshot("9 a companion's sheet")
        app.navigationBars.buttons.element(boundBy: 0).tap()

        // A night opens its log at the play.
        XCTAssertTrue(historyTab.waitForExistence(timeout: 10))
        historyTab.tap()
        XCTAssertTrue(night.waitForExistence(timeout: 15))
        reveal(app, night)
        night.tap()
        XCTAssertTrue(app.buttons["night.tune"].firstMatch.waitForExistence(timeout: 15))
        sleep(2)
        snapshot("10 the night at the play")

        // From one session's night, a play at ANOTHER session opens that night: a fresh
        // screen with its own log (the stack is replaced whole, a session and a night in
        // the same two places), whose tunes open without an error.
        let logTune = app.buttons["night.tune"].firstMatch
        logTune.tap()
        XCTAssertTrue(historyTab.waitForExistence(timeout: 15))
        historyTab.tap()
        XCTAssertTrue(app.buttons["history.change"].waitForExistence(timeout: 10))
        app.buttons["history.change"].tap()
        XCTAssertTrue(option.firstMatch.waitForExistence(timeout: 10))
        option.matching(NSPredicate(format: "label == 'All sessions'")).firstMatch.tap()
        let elsewhere = app.buttons.matching(identifier: "history.night").matching(NSPredicate(format: "label CONTAINS 'Mueller'")).firstMatch
        XCTAssertTrue(elsewhere.waitForExistence(timeout: 15))
        reveal(app, elsewhere)
        elsewhere.tap()
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch.waitForExistence(timeout: 15))
        XCTAssertTrue(logTune.waitForExistence(timeout: 15))
        sleep(2)
        snapshot("12 another session's night")
        logTune.tap()
        XCTAssertTrue(app.buttons["Details"].firstMatch.waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["Couldn't load this"].exists)
        snapshot("13 its tune opens")
        app.buttons["Done"].firstMatch.tap()

        // From your own list there is no session: History lands on every session, with
        // the session named on each row.
        app.buttons["tab.tunes"].firstMatch.tap()
        let mySearch = app.textFields["tunes.search"]
        XCTAssertTrue(mySearch.waitForExistence(timeout: 10))
        mySearch.tap()
        mySearch.typeText("Drowsy")
        let myRow = app.buttons["tunes.row"].firstMatch
        XCTAssertTrue(myRow.waitForExistence(timeout: 10))
        myRow.tap()
        XCTAssertTrue(historyTab.waitForExistence(timeout: 15))
        historyTab.tap()
        XCTAssertTrue(night.waitForExistence(timeout: 15))
        XCTAssertEqual(scopeLabel.label, "All sessions")
        sleep(1)
        snapshot("11 from my tunes")
    }
}
