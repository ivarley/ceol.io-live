import XCTest

/// A session's tab strip stays on screen as its list scrolls, and on Logs the header
/// of the day (a festival) or year you are in stays under it, one at a time.
final class PinnedHeadersUITests: XCTestCase {
    private var server: String!

    override func setUpWithError() throws {
        continueAfterFailure = false
        guard let s = ProcessInfo.processInfo.environment["CEOL_TEST_SERVER"], !s.isEmpty else {
            throw XCTSkip("No CEOL_TEST_SERVER: UI tests need a development server (make ios-ui-test).")
        }
        server = s
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-CeolServerURL", server, "-CeolResetSession", "YES"]
        app.launch()
        return app
    }

    private func snapshot(_ name: String) {
        let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }

    /// A slow drag up by a fraction of the screen, held at the end so nothing coasts.
    private func dragUp(_ app: XCUIApplication, by fraction: CGFloat) {
        let from = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.45 + fraction / 2))
        let to = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.45 - fraction / 2))
        from.press(forDuration: 0.05, thenDragTo: to, withVelocity: .slow, thenHoldForDuration: 0.3)
    }

    /// Whether any text with this label is on screen (a pinned header has a twin in the flow).
    private func hittable(_ app: XCUIApplication, _ label: String) -> Bool {
        app.staticTexts.matching(identifier: label).allElementsBoundByIndex.contains { $0.isHittable }
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

    /// From the Sessions tab: search the directory for the session and open it.
    private func openSession(_ app: XCUIApplication, _ query: String, filterAll: Bool = false) {
        app.buttons["tab.sessions"].firstMatch.tap()
        if filterAll {
            let filter = app.buttons["sessions.search.filter"].firstMatch
            XCTAssertTrue(filter.waitForExistence(timeout: 10))
            filter.tap()
            // Every scope and every status (the festival is past): both "All" chips.
            XCTAssertTrue(app.buttons["All"].firstMatch.waitForExistence(timeout: 5))
            for chip in app.buttons.matching(identifier: "All").allElementsBoundByIndex { chip.tap() }
            app.buttons["filters.done"].tap()
        }
        let search = app.textFields["sessions.search"]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        search.typeText(query)
        let row = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", query)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
    }

    @MainActor
    func testAFestivalsTabsAndDayHeadersPin() throws {
        let app = launch()
        signIn(app)
        openSession(app, "Hill Country", filterAll: true)
        let sessionsTab = app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Sessions'"))
        XCTAssertTrue(sessionsTab.firstMatch.waitForExistence(timeout: 15))
        XCTAssertTrue(app.staticTexts["Friday, June 5"].waitForExistence(timeout: 10))
        // Open the details so there is more above the list than fits.
        app.buttons["session.band"].tap()
        sleep(1)
        snapshot("festival 0 top")
        for i in 1...3 {
            dragUp(app, by: 0.35)
            snapshot("festival \(i)")
            XCTAssertTrue(sessionsTab.allElementsBoundByIndex.contains { $0.isHittable }, "tab strip after drag \(i)")
        }
        // The band has scrolled away; the first day's header stays under the tabs
        // (the seeded festival is too short for a later day's to replace it).
        XCTAssertFalse(app.buttons["session.band"].isHittable)
        XCTAssertTrue(hittable(app, "Friday, June 5"))
    }

    @MainActor
    func testASessionsTabsAndYearHeadersPin() throws {
        let app = launch()
        signIn(app)
        openSession(app, "Mueller")
        let logsTab = app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'"))
        XCTAssertTrue(logsTab.firstMatch.waitForExistence(timeout: 15))
        logsTab.firstMatch.tap()
        XCTAssertTrue(app.staticTexts["2026"].waitForExistence(timeout: 10))
        sleep(1)
        snapshot("session 0 top")
        for i in 1...5 {
            dragUp(app, by: 0.35)
            snapshot("session \(i)")
            XCTAssertTrue(logsTab.allElementsBoundByIndex.contains { $0.isHittable }, "tab strip after drag \(i)")
        }
        XCTAssertTrue(hittable(app, "2024"))
        XCTAssertFalse(hittable(app, "2026"))
    }
}
