// The session's own tunes for a night (spec 053): the tunes it logged before this night
// (GET /api/session-instances/<id>/known-tunes), which the listener shortlists and
// prefers. The listening service fetches them itself; a phone deciding for itself
// (PhoneDeciding) needs them on the phone, so they are fetched whenever a night's
// screen has a connection and kept, and a night at a pub with no signal still has them.
// None kept, and the popular tunes stand in, as on the service.

import Foundation

enum KnownTunes {
    private static let key = "KnownTunes"
    private static let keep = 30                  // nights remembered

    /// The tunes kept for a night, if any.
    static func cached(_ instanceID: Int) -> [Int]? {
        let all = UserDefaults.standard.dictionary(forKey: key) as? [String: [Int]] ?? [:]
        return all[String(instanceID)]
    }

    /// Fetch and keep the night's tunes. Nil if the server can't be reached.
    @discardableResult
    static func refresh(_ instanceID: Int, app: AppModel, timeout: TimeInterval = 15) async -> [Int]? {
        guard !app.simulatedOffline else { return nil }
        var request = app.authorized(URLRequest(url: app.webURL("/api/session-instances/\(instanceID)/known-tunes")))
        request.timeoutInterval = timeout
        guard let (data, response) = try? await URLSession.shared.data(for: request),
            (response as? HTTPURLResponse)?.statusCode == 200,
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let ids = (obj["tune_ids"] as? [NSNumber])?.map(\.intValue)
        else { return nil }
        var all = UserDefaults.standard.dictionary(forKey: key) as? [String: [Int]] ?? [:]
        all[String(instanceID)] = ids
        if all.count > keep {
            // the oldest nights have the smallest ids
            for k in all.keys.compactMap(Int.init).sorted().prefix(all.count - keep) { all[String(k)] = nil }
        }
        UserDefaults.standard.set(all, forKey: key)
        return ids
    }
}
