// Keeping the phone's decider file current (spec 053, "Listening on the phone,
// offline"). The file the phone decides from is rebuilt every week from thesession.org's
// dump; GET /api/listen/decider-data offers the newest. When there is a connection (not
// Low Data Mode), at most every twelve hours and never while a night is being recorded,
// this asks, and fetches the file if it is newer than the one the phone has.
// CeolDeciding's DeciderData checks it and puts it in place; the next night listened to
// on the phone decides from it.

import CeolAPI
import CeolDeciding
import CeolSession
import Foundation
import Network
import Observation

@Observable
final class DeciderRefresher {
    static let every: TimeInterval = 12 * 3600
    private static let lastCheckedKey = "DeciderDataLastChecked"

    /// What the last check came to, for a debug screen or the logs.
    private(set) var lastOutcome: String?
    @ObservationIgnored private weak var app: AppModel?
    @ObservationIgnored private var monitor: NWPathMonitor?
    @ObservationIgnored private var checking = false

    /// Begin watching for a connection (once signed in: the endpoint needs a token).
    func start(app: AppModel) {
        self.app = app
        guard monitor == nil else { return }
        let m = NWPathMonitor()
        m.pathUpdateHandler = { [weak self] path in
            guard path.status == .satisfied, !path.isConstrained else { return }
            Task { @MainActor in await self?.checkIfDue() }
        }
        m.start(queue: DispatchQueue(label: "io.ceol.decider-data.network"))
        monitor = m
    }

    func checkIfDue(force: Bool = false) async {
        guard let app, !app.simulatedOffline, app.recorder == nil, !checking else { return }
        let last = UserDefaults.standard.object(forKey: Self.lastCheckedKey) as? Date ?? .distantPast
        guard force || Date().timeIntervalSince(last) >= Self.every else { return }
        checking = true
        defer { checking = false }
        do {
            let offer = try await app.auth.client.getDeciderData(query: .init(format: Corpus.version)).ok.body.json
            // asked and answered: not again for a while, whatever comes of it
            UserDefaults.standard.set(Date(), forKey: Self.lastCheckedKey)
            guard offer.available, let link = offer.url.flatMap(URL.init(string:)), let sha = offer.sha256,
                let builtAt = offer.builtAt
            else { return finish("none published") }
            let current = Corpus.shipped.flatMap { try? Corpus(contentsOf: $0) }
            guard DeciderData.wanted(builtAt: builtAt, current: current) else {
                return finish("current (\(current?.builtAt ?? "-"))")
            }
            let config = URLSessionConfiguration.default
            config.allowsConstrainedNetworkAccess = false
            let (file, response) = try await URLSession(configuration: config).download(from: link)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                try? FileManager.default.removeItem(at: file)
                return finish("download refused (\((response as? HTTPURLResponse)?.statusCode ?? 0))")
            }
            let bytes = offer.bytes
            // the checksum of 16 MB, off the main thread
            let installed = try await Task.detached {
                defer { try? FileManager.default.removeItem(at: file) }
                return try DeciderData.install(file, sha256: sha, bytes: bytes)
            }.value
            finish("installed \(installed.builtAt): \(installed.tuneCount) tunes")
        } catch {
            finish("failed: \(error)")
        }
    }

    private func finish(_ outcome: String) {
        lastOutcome = outcome
        print("decider data: \(outcome)")
    }
}
