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
        // Straight to the new session's page, as its admin.
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
