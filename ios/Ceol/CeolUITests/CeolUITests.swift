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

    private func launch(openURL: String? = nil) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-CeolServerURL", server, "-CeolResetSession", "YES"]
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
        XCTAssertTrue(app.tabBars.buttons["Me"].firstMatch.waitForExistence(timeout: 10))
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

        app.tabBars.buttons["Sessions"].firstMatch.tap()
        let mueller = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Mueller Session'")).firstMatch
        XCTAssertTrue(mueller.waitForExistence(timeout: 10))
        snapshot("sessions")
        mueller.tap()

        XCTAssertTrue(app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Tunes'")).firstMatch.waitForExistence(timeout: 10))
        snapshot("session")
        app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Logs'")).firstMatch.tap()
        // The first night with tunes in it (the newest may have none yet).
        let night = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[1-9][0-9]* tunes.*'")).firstMatch
        XCTAssertTrue(night.waitForExistence(timeout: 10))
        snapshot("logs")
        night.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label BEGINSWITH 'Set 1'")).firstMatch.waitForExistence(timeout: 10))
        snapshot("night")
    }

    /// Phase 3c: the Tunes tab, a tune's sheet, and the catalogue below your matches.
    @MainActor
    func testBrowsingTunes() throws {
        let app = launch()
        signIn(app)
        app.tabBars.buttons["Tunes"].firstMatch.tap()
        let cooleys = app.buttons.containing(NSPredicate(format: "label CONTAINS \"Cooley's\"")).firstMatch
        XCTAssertTrue(cooleys.waitForExistence(timeout: 10))
        snapshot("tunes")
        cooleys.tap()
        XCTAssertTrue(app.images["Notation for Cooley's"].waitForExistence(timeout: 20))
        snapshot("sheet")
        app.buttons["Done"].tap()
        XCTAssertTrue(app.images["Notation for Cooley's"].waitForNonExistence(timeout: 5))

        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
        search.typeText("maid")
        XCTAssertTrue(app.staticTexts["Not on your list"].waitForExistence(timeout: 10))
        snapshot("search")
    }

    /// Phase 4a: add a catalogue tune, change it, and remove it again (so the seed
    /// data ends as it began).
    @MainActor
    func testEditingATune() throws {
        let app = launch()
        signIn(app)
        app.tabBars.buttons["Tunes"].firstMatch.tap()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
        search.typeText("maid")
        XCTAssertTrue(app.staticTexts["Not on your list"].waitForExistence(timeout: 10))
        let row = app.buttons.matching(identifier: "catalogue.row").firstMatch
        let name = row.staticTexts.firstMatch.label
        row.tap()

        // The sheet is still sliding up when the button first exists; a tap then is lost.
        let add = app.buttons["sheet.add"]
        XCTAssertTrue(add.waitForExistence(timeout: 10))
        let toLearn = app.buttons["sheet.add.want to learn"]
        for _ in 0..<3 where !toLearn.exists {
            add.tap()
            _ = toLearn.waitForExistence(timeout: 2)
        }
        toLearn.tap()
        let status = app.segmentedControls["sheet.status"]
        XCTAssertTrue(status.waitForExistence(timeout: 10))
        XCTAssertTrue(status.buttons["To Learn"].isSelected)
        // The stepper reads its label and value as one: "Heard it, once".
        let heard = app.steppers["sheet.heard"]
        XCTAssertTrue(heard.descendants(matching: .any).containing(NSPredicate(format: "label CONTAINS 'once'")).firstMatch.exists
            || heard.label.contains("once"), heard.debugDescription)
        heard.buttons.element(boundBy: 1).tap()
        let twice = app.descendants(matching: .any).containing(NSPredicate(format: "label CONTAINS '2 times'")).firstMatch
        XCTAssertTrue(twice.waitForExistence(timeout: 5) || heard.label.contains("2 times"), heard.debugDescription)
        status.buttons["Learning"].tap()
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
        app.tabBars.buttons["Me"].firstMatch.tap()
        let admin = app.buttons["me.admin"]
        XCTAssertTrue(admin.waitForExistence(timeout: 10))
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

    /// Phase 3d: Me shows the profile and opens it to edit (cancelled: seed data stays put).
    @MainActor
    func testMeShowsTheProfile() throws {
        let app = launch()
        signIn(app)
        app.tabBars.buttons["Me"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Ian Varley"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS '@ian' AND label CONTAINS 'Austin'")).firstMatch.exists)
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'Fiddle'")).firstMatch.exists)
        XCTAssertFalse(app.buttons["me.delete"].exists, "not offered to a system admin")
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
        let me = app.tabBars.buttons["Me"].firstMatch
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
        XCTAssertFalse(app.tabBars.buttons["Me"].firstMatch.exists)
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
        let me = app.tabBars.buttons["Me"].firstMatch
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
        XCTAssertTrue(app.tabBars.buttons["Me"].firstMatch.waitForExistence(timeout: 15))
    }
}
