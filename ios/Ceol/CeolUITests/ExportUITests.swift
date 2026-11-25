// Export (the web's Me → Export my data), walked through the real app against a
// development server: the chooser, the Tunes tab in export mode with its share
// sheet, and a session's page in export mode across its tabs.
//
//     make ios-ui-test   (CEOL_TEST_SERVER, as the other UI tests)
//
// CEOL_SHOTS_DIR, when set, is a folder screenshots are written to as PNGs, so a
// reviewer on the Mac can look at them without opening the xcresult.

import XCTest

final class ExportUITests: XCTestCase {
    private var server: String!
    private var shotsDir: String?

    override func setUpWithError() throws {
        continueAfterFailure = false
        guard let s = ProcessInfo.processInfo.environment["CEOL_TEST_SERVER"], !s.isEmpty else {
            throw XCTSkip("No CEOL_TEST_SERVER: export UI tests need a development server (make ios-ui-test).")
        }
        server = s
        shotsDir = ProcessInfo.processInfo.environment["CEOL_SHOTS_DIR"]
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-CeolServerURL", server, "-CeolResetSession", "YES"]
        app.launch()
        return app
    }

    private func signIn(_ app: XCUIApplication, as account: String) {
        let button = app.buttons["home.signIn"]
        XCTAssertTrue(button.waitForExistence(timeout: 15))
        button.tap()
        let email = app.textFields["signin.email"]
        XCTAssertTrue(email.waitForExistence(timeout: 15))
        email.tap()
        email.typeText(account)
        app.buttons["signin.continue"].tap()
        let password = app.secureTextFields["signin.password"]
        XCTAssertTrue(password.waitForExistence(timeout: 10))
        password.tap()
        password.typeText("password123")
        app.buttons["signin.submit"].tap()
        XCTAssertTrue(password.waitForNonExistence(timeout: 10))
        XCTAssertTrue(app.buttons["tab.me"].firstMatch.waitForExistence(timeout: 10))
    }

    private func snapshot(_ name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let shot = XCTAttachment(screenshot: screenshot)
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
        if let shotsDir {
            try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: shotsDir).appendingPathComponent("\(name).png"))
        }
    }

    /// Me → Export my data → the chooser; a choice opens the screen in export mode.
    private func openChooser(_ app: XCUIApplication) {
        app.buttons["tab.me"].firstMatch.tap()
        let row = app.buttons["me.export"]
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(app.buttons["export.myTunes"].waitForExistence(timeout: 10))
    }

    @MainActor
    func testMyTunesExportModeAndTheShareSheet() throws {
        let app = launch()
        signIn(app, as: "sarah.oconnor@example.com")
        openChooser(app)
        sleep(1)
        snapshot("export-01-chooser")

        app.buttons["export.myTunes"].tap()
        let download = app.buttons["export.download"]
        let arrived = download.waitForExistence(timeout: 15)
        snapshot("export-02a-after-choice")
        XCTAssertTrue(arrived, "the export bar did not appear on the Tunes tab")
        XCTAssertTrue(app.buttons["export.leave"].exists, "the banner is up")
        // The tab bar gives way to the export bar; the + to add a tune is gone.
        XCTAssertFalse(app.buttons["tab.me"].firstMatch.exists)
        XCTAssertFalse(app.buttons["tunes.add"].exists)
        XCTAssertTrue(download.label.hasPrefix("Download"), download.label)
        sleep(1)
        snapshot("export-02-my-tunes")

        // JSON needs no warm-up: the share sheet is the download.
        download.tap()
        let share = app.otherElements["ActivityListView"]
        XCTAssertTrue(share.waitForExistence(timeout: 60))
        sleep(1)
        snapshot("export-03-share-sheet")
        let close = app.buttons["Close"].firstMatch
        if close.waitForExistence(timeout: 3) { close.tap() } else { share.swipeDown() }
        XCTAssertTrue(share.waitForNonExistence(timeout: 10))

        // Done: the list is itself again, tab bar and all.
        app.buttons["export.done"].tap()
        XCTAssertTrue(download.waitForNonExistence(timeout: 5))
        XCTAssertTrue(app.buttons["tab.me"].firstMatch.waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["tunes.add"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testASessionsPageExportsTheTabItIsOn() throws {
        let app = launch()
        signIn(app, as: "sarah.oconnor@example.com")
        openChooser(app)
        app.buttons["export.sessionLogs"].tap()
        let mueller = app.buttons.matching(NSPredicate(format: "identifier == 'export.session' AND label CONTAINS 'Mueller'")).firstMatch
        let pickerUp = mueller.waitForExistence(timeout: 15)
        snapshot("export-04-session-picker")
        XCTAssertTrue(pickerUp, "the session picker did not show Mueller")
        sleep(1)
        snapshot("export-04-session-picker")
        mueller.tap()

        let download = app.buttons["export.download"]
        let arrived = download.waitForExistence(timeout: 20)
        snapshot("export-04a-after-pick")
        XCTAssertTrue(arrived, "the export bar did not appear on the session page")
        // Logs: the nights the Logged filter leaves.
        XCTAssertTrue(download.label.contains("night"), download.label)
        sleep(1)
        snapshot("export-05-session-logs")

        // Tunes: the repertoire, with the same bar.
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Tunes'")).firstMatch.tap()
        let tunesLabel = NSPredicate(format: "label CONTAINS 'tune'")
        XCTAssertTrue(download.waitForExistence(timeout: 10))
        let expectation = XCTNSPredicateExpectation(predicate: tunesLabel, object: download)
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: 10), .completed, download.label)
        XCTAssertFalse(app.buttons["session.addTune"].exists)
        sleep(1)
        snapshot("export-06-session-tunes")

        // A PDF: the notation is warmed first (cached already here), then the share sheet.
        app.buttons["PDF"].firstMatch.tap()
        download.tap()
        let share = app.otherElements["ActivityListView"]
        XCTAssertTrue(share.waitForExistence(timeout: 120))
        sleep(1)
        snapshot("export-06b-session-tunes-pdf")
        let close = app.buttons["Close"].firstMatch
        if close.waitForExistence(timeout: 3) { close.tap() } else { share.swipeDown() }
        XCTAssertTrue(share.waitForNonExistence(timeout: 10))

        // People: nothing to export here; the bar says so and Download is off.
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'People'")).firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Nothing to export on this tab. Switch to Tunes or Logs."].waitForExistence(timeout: 10))
        XCTAssertFalse(download.isEnabled)
        sleep(1)
        snapshot("export-07-session-people")

        // Leave, from the banner: the page is its plain self again.
        app.buttons["export.leave"].tap()
        XCTAssertTrue(download.waitForNonExistence(timeout: 5))
        XCTAssertTrue(app.buttons["tab.me"].firstMatch.waitForExistence(timeout: 5))
    }
}
