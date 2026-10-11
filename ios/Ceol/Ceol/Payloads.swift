// The payloads the app keeps (spec 052 Phase 6), one Resource each, by name. A screen
// and the prefetcher ask for the same instance, so one fetch serves both. Every fetch
// honours the offline test hook, as getJSON does.

import CeolAPI
import CeolSession
import Foundation

typealias ProfilePayload = Components.Schemas.Profile
typealias SessionTunesRestPayload = Components.Schemas.SessionTunesRemaining

extension AppModel {
    /// The one Resource for a key, made on first use with `fetch`.
    func resource<Value: Codable & Sendable>(_ key: String, fetch: @escaping @MainActor () async throws -> Value) -> Resource<Value> {
        if let r = resources[key] as? Resource<Value> { return r }
        let r = Resource<Value>(key: key) { [weak self] in
            guard let self else { throw URLError(.cancelled) }
            if simulatedOffline { throw URLError(.notConnectedToInternet) }
            return try await fetch()
        }
        resources[key] = r
        return r
    }

    /// Forget every kept payload (signing out): the instances and the files.
    func forgetPayloads() {
        resources = [:]
        PayloadStore.clearAll()
    }

    var home: Resource<HomePayload> {
        resource("home") { [auth] in try await auth.client.getHome().ok.body.json }
    }

    var sessions: Resource<SessionsPayload> {
        resource("sessions") { [auth] in try await auth.client.listSessions().ok.body.json }
    }

    var myTunes: Resource<MyTunesPayload> {
        resource("my-tunes") { [auth] in try await auth.client.getMyTunes().ok.body.json }
    }

    var profile: Resource<ProfilePayload> {
        resource("profile") { [auth] in try await auth.profile() }
    }

    func sessionDetail(_ path: String) -> Resource<SessionDetailPayload> {
        resource("session/\(path)/detail") { [auth] in
            try await auth.client.getSessionDetail(path: .init(sessionPath: path)).ok.body.json
        }
    }

    /// The tunes after the detail's first 20.
    func sessionTunesRest(_ path: String) -> Resource<SessionTunesRestPayload> {
        resource("session/\(path)/tunes-rest") { [auth] in
            try await auth.client.getSessionTunesRemaining(path: .init(sessionPath: path)).ok.body.json
        }
    }

    func sessionLogs(_ path: String) -> Resource<SessionLogsPayload> {
        resource("session/\(path)/logs") { [auth] in
            try await auth.client.getSessionLogs(path: .init(sessionPath: path)).ok.body.json
        }
    }

    func sessionPeople(_ path: String) -> Resource<SessionPeoplePayload> {
        resource("session/\(path)/people") { [auth] in
            try await auth.client.getSessionPeople(path: .init(sessionPath: path)).ok.body.json
        }
    }
}
