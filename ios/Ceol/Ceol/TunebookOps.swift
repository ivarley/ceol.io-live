// Tunebook writes (plan Phase 4a): the same idempotent, tune_id-keyed ops the web's
// offline queue sends to POST /api/my-tunes/ops. Each is an absolute set (a status, a
// heard count, the notes), so sending one twice does no harm.

import CeolAPI
import CeolSession
import Foundation

typealias TuneOp = Components.Schemas.MyTunesOp
typealias LearnStatus = Components.Schemas.LearnStatus

/// A write the server refused, or couldn't be reached for; `message` is fit to show.
struct TuneOpFailure: Error {
    let message: String
}

extension LearnStatus {
    init?(stored: String?) {
        guard let stored, let s = LearnStatus(rawValue: stored) else { return nil }
        self = s
    }
}

extension AppModel {
    @discardableResult
    func applyTuneOp(
        _ type: TuneOp._TypePayload, tuneID: Int, learnStatus: LearnStatus? = nil,
        heardCount: Int? = nil, notes: String? = nil
    ) async throws -> Components.Schemas.MyTunesOpResult {
        let op = TuneOp(
            opId: UUID().uuidString, _type: type, tuneId: tuneID, learnStatus: learnStatus,
            heardCount: heardCount, notes: notes)
        let response: Operations.ApplyMyTunesOp.Output
        do {
            response = try await auth.client.applyMyTunesOp(body: .json(op))
        } catch {
            throw TuneOpFailure(message: "Couldn't reach Ceol, so that wasn't saved. Check your connection and try again.")
        }
        switch response {
        case .ok(let ok):
            return try ok.body.json
        case .default(_, let error):
            throw TuneOpFailure(message: (try? error.body.json)?.message ?? "That wasn't saved. Try again.")
        }
    }
}
