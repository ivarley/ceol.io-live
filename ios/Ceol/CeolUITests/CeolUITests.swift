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
        let me = app.tabBars.buttons["Me"]
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
        XCTAssertFalse(app.tabBars.buttons["Me"].exists)
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
        let me = app.tabBars.buttons["Me"]
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
        XCTAssertTrue(app.tabBars.buttons["Me"].waitForExistence(timeout: 15))
    }
}
