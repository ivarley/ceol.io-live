// Fetching ahead (spec 052 Phase 6): as soon as the app is signed in, and again when it
// comes forward or the network returns, the screens' payloads are fetched and kept so
// none spins when opened, and all of them open with no signal from the second launch.
//
// A round: Home, the Sessions list and your Tunebook at once; then, for each session
// you are a member of, its detail, remaining tunes, logs and people; then the nights
// you are likely to open at the pub (this week's from Home, each member session's
// active and three most recent), saved for the night screen as NightStore keeps them,
// with the night's known tunes for the decider. One round at a time. In Low Data Mode
// only the first three.

import CeolAPI
import CeolLogic
import Foundation
import Network
import Observation

@MainActor
@Observable
final class Prefetcher {
    /// How long a round's result stands before the app coming forward starts another.
    static let foregroundInterval: TimeInterval = 10 * 60
    /// Nights saved ahead per round, at most.
    static let nightsPerRound = 24
    /// A session's payloads or a night fetched this recently are not fetched again by a
    /// round: the lists refresh every time, the fan-out behind them only when it is stale.
    static let fanOutAge: TimeInterval = 10 * 60

    private(set) var running = false
    private(set) var lastRound: Date?
    /// What the last round came to, for a debug screen or the logs.
    private(set) var lastOutcome: String?
    @ObservationIgnored private var lastFailed = false
    @ObservationIgnored private weak var app: AppModel?
    @ObservationIgnored private var monitor: NWPathMonitor?
    @ObservationIgnored private var constrained = false
    @ObservationIgnored private var task: Task<Void, Never>?

    /// Begin: a round now, and one whenever the network returns after a failed one.
    func start(app: AppModel) {
        self.app = app
        if monitor == nil {
            let m = NWPathMonitor()
            m.pathUpdateHandler = { [weak self] path in
                Task { @MainActor in
                    guard let self else { return }
                    self.constrained = path.isConstrained
                    if path.status == .satisfied, self.lastFailed { self.run() }
                }
            }
            m.start(queue: DispatchQueue(label: "io.ceol.prefetch.network"))
            monitor = m
        }
        run()
    }

    /// Signing out: nothing more to fetch for this account.
    func stop() {
        task?.cancel()
        task = nil
        monitor?.cancel()
        monitor = nil
        lastRound = nil
        lastFailed = false
    }

    /// The app came forward: a round, unless the last one was recent and whole.
    func appCameForward() {
        if let last = lastRound, !lastFailed, Date().timeIntervalSince(last) < Self.foregroundInterval { return }
        run()
    }

    /// A round, unless one is running.
    func run() {
        guard task == nil, app != nil else { return }
        task = Task { [weak self] in
            await self?.round()
            self?.task = nil
        }
    }

    private func round() async {
        guard let app else { return }
        running = true
        defer { running = false }
        await app.restoreUser()
        async let h = app.home.refresh()
        async let s = app.sessions.refresh()
        async let t = app.myTunes.refresh()
        var ok = await [h, s, t].allSatisfy { $0 }
        // Changes made with no signal go first, so the lists fetched next show them.
        await app.tuneQueue.flush()
        if constrained || Task.isCancelled {
            finish(ok, note: constrained ? "Low Data Mode: the lists only" : "cancelled")
            return
        }
        var nights: [Int] = []
        if let home = app.home.value {
            nights += home.upcomingSessions.map(\.sessionInstanceId)
            nights += home.inProgressLogs.map(\.sessionInstanceId)
        }
        let mine = (app.sessions.value?.sessions ?? []).filter { $0.userIsMember && $0.kind == .session }
        for session in mine {
            guard !Task.isCancelled else { return }
            let path = session.path
            let d = await app.sessionDetail(path).refresh(ifOlderThan: Self.fanOutAge)
            let r = await app.sessionTunesRest(path).refresh(ifOlderThan: Self.fanOutAge)
            let l = await app.sessionLogs(path).refresh(ifOlderThan: Self.fanOutAge)
            let p = await app.sessionPeople(path).refresh(ifOlderThan: Self.fanOutAge)
            ok = ok && d && r && l && p
            nights += session.activeInstances.map(\.sessionInstanceId)
            if let logs = app.sessionLogs(path).value { nights += Self.recentNights(logs, count: 3) }
        }
        var seen: Set<Int> = []
        let wanted = nights.filter { seen.insert($0).inserted }.prefix(Self.nightsPerRound)
        for id in wanted {
            guard !Task.isCancelled else { return }
            ok = await prefetchNight(id, app: app) && ok
        }
        finish(ok, note: "\(mine.count) sessions, \(wanted.count) nights")
    }

    private func finish(_ ok: Bool, note: String) {
        lastRound = Date()
        lastFailed = !ok
        lastOutcome = (ok ? "complete" : "incomplete") + " (" + note + ")"
    }

    /// The most recent `count` nights in a session's logs (a festival's are by day).
    static func recentNights(_ logs: SessionLogsPayload, count: Int) -> [Int] {
        var nights: [Components.Schemas.SessionLogNight] = []
        for year in logs.sortedYears { nights += logs.instancesByYear.additionalProperties[String(year)] ?? [] }
        for day in logs.sortedDays { nights += logs.instancesByDay.additionalProperties[day] ?? [] }
        return nights.sorted { $0.date > $1.date }.prefix(count).map(\.sessionInstanceId)
    }

    /// Save a night for its screen, unless the phone holds that night with changes
    /// waiting (the screen's own save wins) or has it open (its model saves itself).
    /// True when saved, or rightly left alone.
    private func prefetchNight(_ id: Int, app: AppModel) async -> Bool {
        guard !app.isNightOpen(id) else { return true }
        if let kept = NightStore.load(id), !kept.log.pending.isEmpty || Date().timeIntervalSince(kept.savedAt) < Self.fanOutAge {
            return true
        }
        guard let b = try? await app.getJSON("/api/live/instances/\(id)/bootstrap") else { return false }
        let v = try? await app.getJSON("/api/live/instances/\(id)/vocabulary")
        let log = LiveLog(records: b["records"]?.arrayValue ?? [], meta: NightModel.meta(from: b),
                          lastEventID: b["last_event_id"]?.intValue ?? 0)
        NightStore.save(SavedNight(night: b, log: log, knownTunes: v?["known_tunes"], knownAliases: v?["known_aliases"],
                                   savedAt: Date()), id)
        await KnownTunes.refresh(id, app: app)
        return v != nil
    }
}
