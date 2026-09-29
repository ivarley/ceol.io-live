// A night, live (plan Phase 5a): the log as the referee has it, kept current by the
// streaming service's events, as the web logger's view mode is (frontend/src/App.svelte
// connect(), client.js openStream()).
//
//   - The night is read raw (JSON, not a generated type) so no field of a record is
//     dropped; LiveLog holds it and applies each op through LogState.recordChanges /
//     metaChanges, the rules the web logger uses.
//   - The stream opens from the night's last event id (?last_event_id=, then the
//     Last-Event-ID header on reconnects), with mode=view: reading asserts no presence.
//   - An error reopens it from where it left off, backing off; a stream that goes quiet
//     for 45 seconds (the server pings every 15) is dead without saying so, and gets a
//     full fresh start, as the web's watchdog does.
//   - A finished log is shown as it is, with no stream (the web's render-only path).

import CeolAPI
import CeolLogic
import CeolSession
import Foundation
import Observation

@Observable
final class NightModel {
    enum Status: Equatable {
        case connecting
        case live
        case reconnecting
        /// Couldn't reach the server: showing what we have, retrying.
        case offline
        /// A finished log: nothing to stream.
        case finished
    }

    let instanceID: Int
    private(set) var log: LiveLog?
    /// The night's bootstrap, raw: names, dates, the people settings.
    private(set) var night: JSONValue?
    private(set) var status: Status = .connecting
    private(set) var loadError: String?
    /// Who's logging right now (the stream's presence events), for the header.
    private(set) var roster: [JSONValue] = []

    private let app: AppModel
    private var stream: Task<Void, Never>?
    private var watchdog: Task<Void, Never>?
    private var lastAlive = Date()
    private var failures = 0
    private var running = false

    static let watchdogSeconds: TimeInterval = 45

    init(instanceID: Int, app: AppModel) {
        self.instanceID = instanceID
        self.app = app
    }

    /// Load the night and, unless it's finished, go live.
    func start() async {
        running = true
        await connect()
    }

    func stop() {
        running = false
        stream?.cancel()
        watchdog?.cancel()
        stream = nil
        watchdog = nil
    }

    /// Back in the foreground: a stream the phone suspended is likely dead.
    func resume() async {
        guard running, status != .finished, status != .live || Date().timeIntervalSince(lastAlive) > 20 else { return }
        await connect()
    }

    // MARK: -

    private func connect() async {
        stream?.cancel()
        watchdog?.cancel()
        if log == nil { status = .connecting }
        do {
            let b = try await app.getJSON("/api/live/instances/\(instanceID)/bootstrap")
            night = b
            let meta: [String: JSONValue] = [
                "notes": b["notes"] ?? .null, "instance_date": b["instance_date"] ?? .null,
                "session_date": b["session_date"] ?? .null, "start_time": b["start_time"] ?? .null,
                "end_time": b["end_time"] ?? .null, "instance_name": b["instance_name"] ?? .null,
                "log_complete": b["log_complete"] ?? false,
            ]
            log = LiveLog(records: b["records"]?.arrayValue ?? [], meta: meta, lastEventID: b["last_event_id"]?.intValue ?? 0)
            loadError = nil
            failures = 0
        } catch {
            if log == nil { loadError = loadFailureMessage(error) }
            status = .offline
            retryLater()
            return
        }
        if log?.meta["log_complete"] == true {
            status = .finished
            return
        }
        openStream()
    }

    private func openStream() {
        guard running, let from = log?.highWater else { return }
        status = failures == 0 ? .connecting : .reconnecting
        lastAlive = Date()
        stream = Task { [weak self] in
            guard let self else { return }
            do {
                let base = try await self.app.streamingBase()
                let url = base.appending(path: "live/instances/\(self.instanceID)/events")
                    .appending(queryItems: [.init(name: "last_event_id", value: String(from)), .init(name: "mode", value: "view")])
                var request = self.app.authorized(URLRequest(url: url))
                request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                request.setValue(String(from), forHTTPHeaderField: "Last-Event-ID")
                request.timeoutInterval = 60
                let (bytes, response) = try await URLSession.shared.bytes(for: request)
                guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
                self.status = .live
                self.failures = 0
                self.startWatchdog()
                var parser = SSEParser(lastEventID: String(from))
                for try await byte in bytes {
                    self.lastAlive = Date()
                    for event in parser.feed(CollectionOfOne(byte)) { self.handle(event) }
                }
                throw URLError(.networkConnectionLost)  // the server closed it
            } catch is CancellationError {
                return
            } catch {
                if Task.isCancelled { return }
                self.failures += 1
                self.status = .reconnecting
                self.roster = []
                self.watchdog?.cancel()
                // Reopen from where it left off, backing off: 1, 2, 5, 10 seconds.
                let delay = [1.0, 2, 5, 10][min(self.failures - 1, 3)]
                try? await Task.sleep(for: .seconds(delay))
                if !Task.isCancelled && self.running { self.openStream() }
            }
        }
    }

    private func handle(_ event: SSEEvent) {
        guard let json = try? JSONDecoder().decode(JSONValue.self, from: Data(event.data.utf8)) else { return }
        switch event.type {
        case "op":
            if log?.apply(json) == true, log?.meta["log_complete"] == true {
                // Finished while we watched: nothing more to stream.
                status = .finished
                stop()
                running = true
            }
        case "presence":
            roster = json["roster"]?.arrayValue ?? []
        default:
            break  // ping, typing: proof of life only
        }
    }

    /// A silent half-open stream never errors. If nothing arrives for 45 seconds (the
    /// server pings every 15), start over: a fresh bootstrap closes any gap.
    private func startWatchdog() {
        watchdog?.cancel()
        watchdog = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                guard let self, !Task.isCancelled else { return }
                if Date().timeIntervalSince(self.lastAlive) > Self.watchdogSeconds {
                    self.status = .reconnecting
                    await self.connect()
                    return
                }
            }
        }
    }

    private func retryLater() {
        guard running else { return }
        failures += 1
        let delay = [2.0, 5, 10, 20][min(failures - 1, 3)]
        stream = Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard let self, !Task.isCancelled, self.running else { return }
            await self.connect()
        }
    }
}

extension AppModel {
    /// An authenticated request: the Bearer token and the client header, as the API
    /// client sends them.
    func authorized(_ request: URLRequest) -> URLRequest {
        var r = request
        if let token = auth.store.token() { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        r.setValue(ClientID.current, forHTTPHeaderField: "X-Ceol-Client")
        return r
    }

    /// A GET, as raw JSON: for payloads whose every field must survive (a night's records).
    func getJSON(_ path: String) async throws -> JSONValue {
        var request = authorized(URLRequest(url: webURL(path)))
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try JSONDecoder().decode(JSONValue.self, from: data)
    }

    /// The streaming service's address (app-config's streaming_base_url).
    func streamingBase() async throws -> URL {
        if let cached = streamingURL { return cached }
        let config = try await auth.appConfig()
        guard let url = URL(string: config.streamingBaseUrl) else { throw URLError(.badURL) }
        streamingURL = url
        return url
    }
}
