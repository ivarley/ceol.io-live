// Tunebook writes (plan Phase 4a): the same idempotent, tune_id-keyed ops the web's
// offline queue sends to POST /api/my-tunes/ops. Each is an absolute set (a status, a
// heard count, the notes), so sending one twice does no harm.
//
// With no signal (Phase 6) an op waits in TuneQueue and is applied to the kept
// Tunebook here, so the list and Home's counts show it at once; the caller sees it
// saved. Only a refusal the server answered is thrown.
//
// i18n-converted (spec 057). The server's own message is shown as it comes (a later stage).

import CeolAPI
import CeolLogic
import CeolSession
import Foundation

typealias TuneOp = Components.Schemas.MyTunesOp
typealias LearnStatus = Components.Schemas.LearnStatus

/// A write the server refused, or (`connection`) couldn't be reached for; `message` is fit to show.
struct TuneOpFailure: Error {
    let message: String
    var connection = false
}

extension LearnStatus {
    init?(stored: String?) {
        guard let stored, let s = LearnStatus(rawValue: stored) else { return nil }
        self = s
    }
}

extension AppModel {
    /// Apply one op: on the server when it can be reached, else queued and applied to
    /// the kept list. `name` and `tuneType` name an added tune until the server's row
    /// arrives. Throws only a refusal.
    @discardableResult
    func applyTuneOp(
        _ type: TuneOp._TypePayload, tuneID: Int, learnStatus: LearnStatus? = nil,
        heardCount: Int? = nil, notes: String? = nil, settingID: Int? = nil,
        nameAlias: String? = nil, key: String? = nil, name: String? = nil, tuneType: String? = nil
    ) async throws -> Components.Schemas.MyTunesOpResult {
        let op = TuneOp(
            opId: UUID().uuidString, _type: type, tuneId: tuneID, learnStatus: learnStatus,
            heardCount: heardCount, notes: notes, settingId: settingID, nameAlias: nameAlias, key: key)
        // Earlier changes wait: send them first, so this one is not applied out of order.
        if !tuneQueue.isEmpty { await tuneQueue.flush() }
        if tuneQueue.isEmpty {
            do {
                return try await sendTuneOp(op)
            } catch let f as TuneOpFailure where !f.connection {
                throw f
            } catch {
                // no signal: queued below
            }
        }
        tuneQueue.enqueue(QueuedTuneOp(op: op, name: name, tuneType: tuneType, queuedAt: Date()))
        let personID = user?.personId ?? 0
        myTunes.update { TunebookOps.apply(op, name: name, tuneType: tuneType, personID: personID, to: &$0) }
        if let tunes = myTunes.value?.tunes {
            home.update {
                $0.learningCount = tunes.filter { $0.learnStatus == LearnStatus.learning.rawValue }.count
                $0.wantToLearnCount = tunes.filter { $0.learnStatus == LearnStatus.wantToLearn.rawValue }.count
            }
        }
        return .init(success: true, opId: op.opId, _type: type.rawValue, tuneId: tuneID, heardCount: heardCount)
    }

    /// One op to the server: its result, a refusal, or a connection failure.
    func sendTuneOp(_ op: TuneOp) async throws -> Components.Schemas.MyTunesOpResult {
        if simulatedOffline { throw TuneOpFailure(message: offlineLoadMessage, connection: true) }
        let response: Operations.ApplyMyTunesOp.Output
        do {
            response = try await auth.client.applyMyTunesOp(body: .json(op))
        } catch {
            throw TuneOpFailure(
                message: tr("Couldn't reach Ceol, so that wasn't saved. Check your connection and try again."),
                connection: true)
        }
        switch response {
        case .ok(let ok):
            return try ok.body.json
        case .default(_, let error):
            throw TuneOpFailure(message: (try? error.body.json)?.message ?? tr("That wasn't saved. Try again."))
        }
    }
}

/// How each op changes the kept Tunebook, as the server will change the real one.
enum TunebookOps {
    static func apply(_ op: TuneOp, name: String?, tuneType: String?, personID: Int, to payload: inout MyTunesPayload) {
        let i = payload.tunes.firstIndex { $0.tuneId == op.tuneId }
        switch op._type {
        case .add:
            guard i == nil else { return }
            let now = ISO8601DateFormatter().string(from: Date())
            payload.tunes.append(
                PersonTune(
                    personTuneId: -op.tuneId, personId: personID, tuneId: op.tuneId,
                    learnStatus: (op.learnStatus ?? .wantToLearn).rawValue,
                    heardCount: 1,  // an add is itself a hearing (PersonTune.DEFAULT_HEARD_COUNT)
                    nameAlias: op.nameAlias, key: op.key, tags: [], createdDate: now, lastModifiedDate: now,
                    tuneName: name ?? "#\(op.tuneId)", tuneType: tuneType, instrumentStatus: .init(),
                    memberPlayCount: 0, attendedPlayCount: 0, sessionPlayCount: 0))
            payload.pagination.totalCount += 1
        case .setStatus:
            guard let i, let s = op.learnStatus else { return }
            payload.tunes[i].learnStatus = s.rawValue
        case .setHeard:
            guard let i, let n = op.heardCount else { return }
            payload.tunes[i].heardCount = n
        case .setNotes:
            guard let i else { return }
            payload.tunes[i].notes = op.notes
        case .setSetting:
            guard let i else { return }
            payload.tunes[i].settingId = op.settingId
        case .remove:
            guard let i else { return }
            payload.tunes.remove(at: i)
            payload.pagination.totalCount -= 1
        case .setTags, .setInstrumentStatus:
            // not sent by the app
            break
        }
    }
}
