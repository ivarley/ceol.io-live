import XCTest

/// Recordings kept on this phone: one made just listening plays here, is given a
/// night ("Attach to a night": the session, then one of its nights), and can then be
/// uploaded.
final class RecordingsUITests: XCTestCase {
    private var server: String!

    override func setUpWithError() throws {
        continueAfterFailure = false
        guard let s = ProcessInfo.processInfo.environment["CEOL_TEST_SERVER"], !s.isEmpty else {
            throw XCTSkip("No CEOL_TEST_SERVER: UI tests need a development server (make ios-ui-test).")
        }
        server = s
    }

    private func snapshot(_ name: String) {
        let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
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
    func testARecordingMadeListeningPlaysAndIsGivenANight() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-CeolServerURL", server, "-CeolResetSession", "YES"]
        app.launch()
        signIn(app)

        // Listen, ad hoc, keeping a recording; a few seconds, then stop.
        app.buttons["tab.listen"].firstMatch.tap()
        let keep = app.switches["start.recording"].firstMatch
        XCTAssertTrue(keep.waitForExistence(timeout: 10))
        if (keep.value as? String) != "1" { keep.tap() }
        XCTAssertEqual(keep.value as? String, "1", "keeping a recording")
        app.buttons["start.listen"].tap()
        let stop = app.buttons["meter.stop"]
        XCTAssertTrue(stop.waitForExistence(timeout: 15))
        sleep(4)
        snapshot("listening")
        stop.tap()
        let confirm = app.buttons["meter.stop.confirm"].firstMatch
        XCTAssertTrue(confirm.waitForExistence(timeout: 5))
        confirm.tap()
        XCTAssertTrue(stop.waitForNonExistence(timeout: 10))

        // The recordings list: it plays here.
        app.buttons["tab.me"].firstMatch.tap()
        let recordings = app.buttons["me.recordings"]
        XCTAssertTrue(recordings.waitForExistence(timeout: 10))
        recordings.tap()
        let play = app.buttons["recordings.play"].firstMatch
        XCTAssertTrue(play.waitForExistence(timeout: 10))
        // The newest recording is first; older ones (earlier runs) may sit below it.
        XCTAssertTrue(app.buttons["recordings.attach"].firstMatch.exists, "no night: Attach to a night")
        let uploadsBefore = app.buttons.matching(identifier: "recordings.upload").count
        snapshot("recordings")
        play.tap()
        XCTAssertTrue(app.sliders.firstMatch.waitForExistence(timeout: 5), "the transport")
        sleep(1)
        snapshot("playing")
        play.tap()

        // Give it a night: Mueller Session, one of its nights.
        app.buttons["recordings.attach"].firstMatch.tap()
        let search = app.textFields["attach.search"]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        snapshot("attach sessions")
        search.tap()
        search.typeText("Mueller")
        let session = app.buttons["attach.session"].firstMatch
        XCTAssertTrue(session.waitForExistence(timeout: 10))
        session.tap()
        let night = app.buttons["attach.night"].firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["attach.addNight"].exists, "or a new night on the day")
        snapshot("attach nights")
        night.tap()
        let uploads = app.buttons.matching(identifier: "recordings.upload")
        XCTAssertTrue(uploads.element(boundBy: uploadsBefore).waitForExistence(timeout: 10), "with a night, Upload")
        XCTAssertEqual(uploads.count, uploadsBefore + 1)
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Mueller Session'")).firstMatch.exists)
        snapshot("attached")
    }
}
