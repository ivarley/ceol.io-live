// Tunebook writes with no signal (spec 052 Phase 6), as the web's offline queue
// (frontend/src/offline.js) sends them: an op the server can't be reached for waits in
// a file, applied to the kept Tunebook at once so the list shows the change, and is
// sent in order when the network returns, the app comes forward, or the next op is
// tried. The ops are absolute sets keyed by op id (POST /api/my-tunes/ops), so sending
// one twice does no harm. A refusal drops that op and is listed on the Tunes tab; a
// connection failure stops the round until the next chance.
//
// i18n-converted (spec 057).

import CeolAPI
import Foundation
import Network
import Observation

struct QueuedTuneOp: Codable {
    var op: TuneOp
    /// For an add: what the kept list calls the tune until the server's row arrives.
    var name: String?
    var tuneType: String?
    var queuedAt: Date
}

@MainActor
@Observable
final class TuneQueue {
    private(set) var waiting: [QueuedTuneOp] = []
    /// Ops the server refused once sent ("The Kesh: invalid learn_status"), until dismissed.
    var refused: [String] = []
    private(set) var sending = false
    @ObservationIgnored private weak var app: AppModel?
    @ObservationIgnored private var monitor: NWPathMonitor?
    @ObservationIgnored private var flushing: Task<Void, Never>?

    static var file: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appending(path: "tunebook-queue.json")
    }

    init() {
        if let data = try? Data(contentsOf: Self.file), let q = try? JSONDecoder().decode([QueuedTuneOp].self, from: data) {
            waiting = q
        }
    }

    var count: Int { waiting.count }
    var isEmpty: Bool { waiting.isEmpty }

    /// Begin (signed in): send what waits, now and whenever the network returns.
    func start(app: AppModel) {
        self.app = app
        if monitor == nil {
            let m = NWPathMonitor()
            m.pathUpdateHandler = { [weak self] path in
                guard path.status == .satisfied else { return }
                Task { @MainActor in await self?.flush() }
            }
            m.start(queue: DispatchQueue(label: "io.ceol.tunebook-queue.network"))
            monitor = m
        }
        Task { await flush() }
    }

    /// Signing out: this account's changes go with it.
    func stop() {
        monitor?.cancel()
        monitor = nil
        flushing?.cancel()
        waiting = []
        refused = []
        try? FileManager.default.removeItem(at: Self.file)
    }

    func enqueue(_ q: QueuedTuneOp) {
        waiting.append(q)
        save()
    }

    private func save() {
        if waiting.isEmpty {
            try? FileManager.default.removeItem(at: Self.file)
        } else {
            try? JSONEncoder().encode(waiting).write(to: Self.file, options: .atomic)
        }
    }

    /// Send what waits, in order. Joins a round already running.
    func flush() async {
        if let t = flushing {
            await t.value
            return
        }
        guard let app, !waiting.isEmpty, !app.simulatedOffline else { return }
        let t = Task { @MainActor in
            sending = true
            defer {
                sending = false
                flushing = nil
            }
            var sent = 0
            while let next = waiting.first, !Task.isCancelled {
                do {
                    _ = try await app.sendTuneOp(next.op)
                    sent += 1
                } catch let f as TuneOpFailure where !f.connection {
                    let what = next.name ?? app.myTunes.value?.tunes.first { $0.tuneId == next.op.tuneId }?.tuneName ?? "#\(next.op.tuneId)"
                    refused.append("\(what): \(f.message)")
                } catch {
                    break
                }
                waiting.removeFirst()
                save()
            }
            // The server's own rows now, in place of the phone's guesses.
            if sent > 0 || (waiting.isEmpty && !refused.isEmpty) {
                await app.myTunes.refresh()
                await app.home.refresh()
            }
        }
        flushing = t
        await t.value
    }
}
