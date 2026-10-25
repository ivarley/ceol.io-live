// Offline from the second launch (spec 052 Phase 6): payloads kept on the phone, and
// tunebook changes made with no signal waiting in order, shown at once, sent later.

import CeolAPI
import CeolSession
import Foundation
import HTTPTypes
import OpenAPIRuntime
import Testing
@testable import Ceol

/// A server that has forgotten the token: 401 to everything.
private final class TokenForgottenTransport: ClientTransport, @unchecked Sendable {
    func send(_ request: HTTPRequest, body: HTTPBody?, baseURL: URL, operationID: String) async throws -> (HTTPResponse, HTTPBody?) {
        var response = HTTPResponse(status: .unauthorized)
        response.headerFields[.contentType] = "application/json"
        return (response, HTTPBody(#"{"success": false, "error": "Authentication required", "message": "Authentication required", "code": "unauthenticated"}"#))
    }
}

/// A server that takes every tunebook op.
private final class AcceptingTransport: ClientTransport, @unchecked Sendable {
    func send(_ request: HTTPRequest, body: HTTPBody?, baseURL: URL, operationID: String) async throws -> (HTTPResponse, HTTPBody?) {
        let sent = try await Data(collecting: body ?? HTTPBody(), upTo: 1 << 16)
        let op = try JSONDecoder().decode(TuneOp.self, from: sent)
        var response = HTTPResponse(status: .ok)
        response.headerFields[.contentType] = "application/json"
        return (response, HTTPBody(#"{"success": true, "op_id": "\#(op.opId)", "type": "\#(op._type.rawValue)", "tune_id": \#(op.tuneId)}"#))
    }
}

extension OnePhoneTests {
@MainActor
struct OfflineTests {
    private static func user(_ id: Int) throws -> User {
        try JSONDecoder().decode(User.self, from: Data("""
            {"user_id": \(id), "person_id": \(id + 100), "username": "u\(id)", "email": "u\(id)@example.com",
             "first_name": "U", "last_name": "\(id)", "is_system_admin": false, "timezone": "UTC",
             "email_verified": true, "has_password": true, "needs_profile_setup": false}
            """.utf8))
    }

    /// Back to nothing kept, for the next test.
    private static func clean(_ app: AppModel) {
        app.tuneQueue.stop()
        app.forgetPayloads()
        AppModel.localDataOwner = nil
    }
    private static func emptyTunebook() -> MyTunesPayload {
        MyTunesPayload(
            success: true, tunes: [], instruments: [], thesessionUserId: nil,
            pagination: .init(page: 1, perPage: 10000, totalCount: 0, totalPages: 1, hasNext: false, hasPrev: false))
    }

    private static func offlineApp() -> AppModel {
        let app = AppModel(server: URL(string: "http://127.0.0.1:9")!, store: MemoryTokenStore())
        app.simulatedOffline = true
        app.tuneQueue.stop()
        app.forgetPayloads()
        return app
    }

    @Test func aKeptPayloadComesBackWithWhenItWasSaved() throws {
        let at = Date(timeIntervalSince1970: 1_700_000_000)
        PayloadStore.save(["kesh": 42], key: "test/round-trip", at: at)
        let kept: PayloadStore.Stored<[String: Int]> = try #require(PayloadStore.load("test/round-trip"))
        #expect(kept.value == ["kesh": 42])
        #expect(kept.savedAt == at)
        PayloadStore.clearAll()
        let gone: PayloadStore.Stored<[String: Int]>? = PayloadStore.load("test/round-trip")
        #expect(gone == nil)
    }

    @Test func eachOpChangesTheKeptListAsTheServerWould() {
        var p = Self.emptyTunebook()
        func op(_ type: TuneOp._TypePayload, status: LearnStatus? = nil, heard: Int? = nil, notes: String? = nil, setting: Int? = nil) -> TuneOp {
            TuneOp(opId: UUID().uuidString, _type: type, tuneId: 42, learnStatus: status, heardCount: heard, notes: notes, settingId: setting)
        }
        TunebookOps.apply(op(.add, status: .learning), name: "The Kesh", tuneType: "jig", personID: 7, to: &p)
        #expect(p.tunes.map(\.tuneName) == ["The Kesh"])
        #expect(p.tunes[0].learnStatus == "learning")
        #expect(p.tunes[0].heardCount == 1)  // an add is itself a hearing
        #expect(p.tunes[0].tuneType == "jig")
        #expect(p.pagination.totalCount == 1)
        // twice does no harm
        TunebookOps.apply(op(.add, status: .wantToLearn), name: "The Kesh", tuneType: "jig", personID: 7, to: &p)
        #expect(p.tunes.count == 1 && p.tunes[0].learnStatus == "learning")
        TunebookOps.apply(op(.setStatus, status: .learned), name: nil, tuneType: nil, personID: 7, to: &p)
        #expect(p.tunes[0].learnStatus == "learned")
        TunebookOps.apply(op(.setHeard, heard: 4), name: nil, tuneType: nil, personID: 7, to: &p)
        #expect(p.tunes[0].heardCount == 4)
        TunebookOps.apply(op(.setNotes, notes: "B part twice"), name: nil, tuneType: nil, personID: 7, to: &p)
        #expect(p.tunes[0].notes == "B part twice")
        TunebookOps.apply(op(.setSetting, setting: 99), name: nil, tuneType: nil, personID: 7, to: &p)
        #expect(p.tunes[0].settingId == 99)
        TunebookOps.apply(op(.remove), name: nil, tuneType: nil, personID: 7, to: &p)
        #expect(p.tunes.isEmpty)
        #expect(p.pagination.totalCount == 0)
    }

    @Test func aChangeWithNoSignalWaitsInOrderAndShowsAtOnce() async throws {
        let app = Self.offlineApp()
        app.myTunes.replace(Self.emptyTunebook())
        try await app.applyTuneOp(.add, tuneID: 42, learnStatus: .wantToLearn, name: "The Kesh", tuneType: "jig")
        try await app.applyTuneOp(.setHeard, tuneID: 42, heardCount: 3)
        #expect(app.tuneQueue.count == 2)
        #expect(app.myTunes.value?.tunes.map(\.tuneName) == ["The Kesh"])
        #expect(app.myTunes.value?.tunes.first?.heardCount == 3)

        // The queue, and the kept list with the change on it, survive a relaunch.
        let relaunched = TuneQueue()
        #expect(relaunched.waiting.map(\.op._type) == [.add, .setHeard])
        #expect(relaunched.waiting.first?.name == "The Kesh")
        let kept: PayloadStore.Stored<MyTunesPayload>? = PayloadStore.load("my-tunes")
        #expect(kept?.value.tunes.first?.heardCount == 3)

        // A server that can't be reached keeps them waiting (nothing listens on port 9).
        app.simulatedOffline = false
        await app.tuneQueue.flush()
        #expect(app.tuneQueue.count == 2)

        // Signing out forgets this account's changes and payloads.
        await app.signOut()
        #expect(app.tuneQueue.isEmpty)
        #expect(TuneQueue().isEmpty)
        let afterSignOut: PayloadStore.Stored<MyTunesPayload>? = PayloadStore.load("my-tunes")
        #expect(afterSignOut == nil)
    }

    @Test func aChangeTheServerTookShowsAtOnceToo() async throws {
        // Online, the kept tunebook follows the op as well (not only when it queues):
        // a session's Tunes tab coloured by your status, open behind the tune's
        // sheet, must show the new status without a fetch.
        let app = AppModel(server: URL(string: "http://127.0.0.1:9")!, store: MemoryTokenStore(), transport: AcceptingTransport())
        Self.clean(app)
        try app.auth.store.setToken("fresh")
        app.enter(try Self.user(7), next: nil)
        app.myTunes.replace(Self.emptyTunebook())
        try await app.applyTuneOp(.add, tuneID: 42, learnStatus: .wantToLearn, name: "The Kesh", tuneType: "jig")
        try await app.applyTuneOp(.setStatus, tuneID: 42, learnStatus: .learning)
        #expect(app.tuneQueue.isEmpty)
        #expect(app.myTunes.value?.tunes.map(\.tuneName) == ["The Kesh"])
        #expect(app.myTunes.value?.tunes.first?.learnStatus == LearnStatus.learning.rawValue)
        Self.clean(app)
    }

    @Test func aRefusalIsThrownNotQueued() async {
        // No value kept and no signal: a refusal can't be told from a connection
        // failure here, so this holds the other half — a connection failure queues.
        let app = Self.offlineApp()
        app.myTunes.replace(Self.emptyTunebook())
        let result = try? await app.applyTuneOp(.setStatus, tuneID: 1, learnStatus: .learned)
        #expect(result?.success == true)
        #expect(app.tuneQueue.count == 1)
        app.tuneQueue.stop()
        app.forgetPayloads()
    }

    @Test func aSignInThatRanOutKeepsEverythingForTheSameAccount() async throws {
        let app = Self.offlineApp()
        AppModel.localDataOwner = nil
        try app.auth.store.setToken("tok-7")
        app.enter(try Self.user(7), next: nil)
        #expect(app.phase == .signedIn)
        #expect(AppModel.localDataOwner == 7)
        app.myTunes.replace(Self.emptyTunebook())
        try await app.applyTuneOp(.add, tuneID: 42, learnStatus: .wantToLearn, name: "The Kesh", tuneType: "jig")
        #expect(app.tuneQueue.count == 1)

        // The server no longer knows the token: a guest, asked to sign in, nothing lost.
        app.signInExpired()
        #expect(app.phase == .guest)
        #expect(app.signingIn)
        #expect(app.auth.store.token() == nil)
        #expect(app.notice?.contains("Sign in again") == true)
        #expect(app.tuneQueue.count == 1)
        #expect(TuneQueue().count == 1)
        let kept: PayloadStore.Stored<MyTunesPayload>? = PayloadStore.load("my-tunes")
        #expect(kept?.value.tunes.map(\.tuneName) == ["The Kesh"])

        // The same account signs in again: the change still waits, the list still shows it.
        app.enter(try Self.user(7), next: nil)
        #expect(app.tuneQueue.count == 1)
        #expect(app.myTunes.value?.tunes.map(\.tuneName) == ["The Kesh"])

        // Another account: none of it shows under them, none of it is sent as them.
        app.enter(try Self.user(8), next: nil)
        #expect(AppModel.localDataOwner == 8)
        #expect(app.tuneQueue.isEmpty)
        #expect(TuneQueue().isEmpty)
        #expect(app.myTunes.value == nil)
        let gone: PayloadStore.Stored<MyTunesPayload>? = PayloadStore.load("my-tunes")
        #expect(gone == nil)
        Self.clean(app)
    }

    /// Spec 060: signing in from the sheet closes it and leaves you where you were;
    /// deleting the account starts the tabs over as a guest.
    @Test func aGuestSignsInWhereTheyAreAndLeavesAsAGuest() async throws {
        let app = Self.offlineApp()
        AppModel.localDataOwner = nil
        app.tab = .sessions
        app.sessionsPath = [.session(path: "austin/mueller", name: "Mueller")]
        app.askToSignIn()
        #expect(app.signingIn)
        try app.auth.store.setToken("tok-7")
        app.enter(try Self.user(7), next: nil)
        #expect(app.phase == .signedIn)
        #expect(!app.signingIn)
        #expect(app.tab == .sessions)
        #expect(app.sessionsPath.count == 1)

        let generation = app.tabsGeneration
        app.accountDeleted()
        #expect(app.phase == .guest)
        #expect(app.isGuest)
        #expect(app.tab == .home)
        #expect(app.sessionsPath.isEmpty)
        #expect(app.tabsGeneration == generation + 1)
        #expect(app.notice?.contains("deleted") == true)
        Self.clean(app)
    }

    @Test func aServerThatForgotTheTokenSendsYouToSignInAndKeepsTheChange() async throws {
        let app = AppModel(server: URL(string: "http://127.0.0.1:9")!, store: MemoryTokenStore(), transport: TokenForgottenTransport())
        app.simulatedOffline = true
        Self.clean(app)
        try app.auth.store.setToken("stale")
        app.enter(try Self.user(7), next: nil)
        app.myTunes.replace(Self.emptyTunebook())
        // One change made with no signal...
        try await app.applyTuneOp(.setHeard, tuneID: 42, heardCount: 3)
        #expect(app.tuneQueue.count == 1)

        // ...then the network is back, and the server answers 401 to the replay: the
        // op is not a refusal (nothing is listed as refused), it waits; the sign-in
        // is over.
        app.simulatedOffline = false
        await app.tuneQueue.flush()
        #expect(app.tuneQueue.count == 1)
        #expect(app.tuneQueue.refused.isEmpty)
        #expect(app.phase == .guest)
        #expect(app.auth.store.token() == nil)

        // A change made now queues behind it rather than failing.
        let result = try await app.applyTuneOp(.setNotes, tuneID: 42, notes: "B part twice")
        #expect(result.success == true)
        #expect(app.tuneQueue.count == 2)
        Self.clean(app)
    }
}
}
