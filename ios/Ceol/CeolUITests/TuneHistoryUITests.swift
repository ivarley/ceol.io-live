import XCTest

/// A tune's play counts open the nights it was played (TuneHistoryView), pushed from the
/// sheet; a night opens its log at the play. Screenshots go to CEOL_SHOTS when set.
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

    @MainActor
    func testThePlayCountsOpenTheNights() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-CeolServerURL", server, "-CeolResetSession", "YES"]
        app.launch()
        signIn(app)

        // Mueller's Tunes tab, Drowsy Maggie's sheet.
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

        // The sheet: the counts carry a chevron.
        let here = app.buttons["sheet.historyHere"]
        XCTAssertTrue(here.waitForExistence(timeout: 15))
        if !here.isHittable { app.swipeUp() }
        sleep(1)
        snapshot("1 sheet")
        here.tap()

        // The nights at this session, then only the ones I was at.
        let night = app.buttons["history.night"].firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 15))
        sleep(1)
        snapshot("2 history at this session")
        // The Toggle's identifier spans its row; the switch sits at its right end.
        let attended = app.switches["history.attended"].firstMatch
        XCTAssertTrue(attended.exists)
        attended.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        sleep(2)
        XCTAssertEqual(attended.value as? String, "1")
        snapshot("3 only when I was there")
        attended.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        sleep(1)

        // Back to the sheet, then every session on Ceol.
        app.navigationBars.buttons.element(boundBy: 0).tap()
        let all = app.buttons["sheet.historyAll"]
        XCTAssertTrue(all.waitForExistence(timeout: 10))
        all.tap()
        XCTAssertTrue(night.waitForExistence(timeout: 15))
        sleep(1)
        snapshot("4 history at every session")

        // A night opens its log, at the play.
        night.tap()
        XCTAssertTrue(app.buttons["night.tune"].firstMatch.waitForExistence(timeout: 15))
        sleep(2)
        snapshot("5 the night at the play")
    }
}
