// Offline from the second launch (spec 052 Phase 6): payloads kept on the phone, and
// tunebook changes made with no signal waiting in order, shown at once, sent later.

import CeolAPI
import CeolSession
import Foundation
import Testing
@testable import Ceol

@MainActor
struct OfflineTests {
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
}
