// A payload kept on the phone (spec 052 Phase 6): one endpoint's answer, read from
// disk when first asked for and written on every successful fetch, so a screen opens
// on what it had last time and refreshes behind a quiet spinner. With no signal it
// shows the kept copy and says so. The night screen keeps its own model (NightStore).
//
//   - PayloadStore: one JSON file per key in Application Support/Payloads; cleared on
//     sign-out, as NightStore is (it is this account's data).
//   - Resource<Value>: the value, when it was saved, whether a refresh is running and
//     what the last one came to. One instance per key (AppModel.resource), shared by
//     the screen and the prefetcher: a refresh already in flight is joined, not
//     repeated. Fresh replaces kept: these are server-owned lists.
//   - Resourced: the screen's body over a resource — the kept value at once, a spinner
//     only when there is nothing yet, the failure with Retry only when there is nothing
//     and the fetch failed.
//   - ceolKept: the small spinner over the top of the screen while a kept value is
//     refreshed, and the one-line strip when it couldn't be.
//
// i18n-converted (spec 057).

import CeolDesign
import Foundation
import Observation
import OpenAPIRuntime
import SwiftUI

enum PayloadStore {
    struct Stored<Value: Codable>: Codable {
        var value: Value
        var savedAt: Date
    }

    static var folder: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appending(path: "Payloads", directoryHint: .isDirectory)
    }

    /// The file for a key: "session/kesh-inn/logs" is readable in the folder, with the
    /// one character a file name can't hold swapped.
    static func file(_ key: String) -> URL {
        folder.appending(path: key.replacingOccurrences(of: "/", with: "~") + ".json")
    }

    static func load<Value: Codable>(_ key: String) -> Stored<Value>? {
        guard let data = try? Data(contentsOf: file(key)) else { return nil }
        return try? JSONDecoder().decode(Stored<Value>.self, from: data)
    }

    static func save<Value: Codable>(_ value: Value, key: String, at date: Date = Date()) {
        do {
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            try JSONEncoder().encode(Stored(value: value, savedAt: date)).write(to: file(key), options: .atomic)
        } catch {
            // Best effort: the screen still has the value; it is only not kept.
        }
    }

    /// Everything, for signing out.
    static func clearAll() {
        try? FileManager.default.removeItem(at: folder)
    }
}

/// A kept payload, whatever its type: signing in fetches every open one again.
@MainActor
protocol Refreshing: AnyObject {
    @discardableResult func refresh() async -> Bool
}

@MainActor
@Observable
final class Resource<Value: Codable & Sendable>: Refreshing {
    let key: String
    private(set) var value: Value?
    /// When `value` was fetched (or last changed on the phone).
    private(set) var savedAt: Date?
    private(set) var refreshing = false
    /// What the last refresh came to: nil until one has finished, or after one succeeds;
    /// a sentence fit to show after one fails.
    private(set) var failure: String?
    @ObservationIgnored private let fetch: @MainActor () async throws -> Value
    @ObservationIgnored private var inFlight: Task<Bool, Never>?

    init(key: String, fetch: @escaping @MainActor () async throws -> Value) {
        self.key = key
        self.fetch = fetch
        if let s: PayloadStore.Stored<Value> = PayloadStore.load(key) {
            value = s.value
            savedAt = s.savedAt
        }
    }

    /// Fetch and keep. Joins a refresh already running. True when it succeeded.
    @discardableResult
    func refresh() async -> Bool {
        if let t = inFlight { return await t.value }
        refreshing = true
        let t = Task<Bool, Never> { @MainActor in
            defer {
                inFlight = nil
                refreshing = false
            }
            do {
                let v = try await fetch()
                let now = Date()
                value = v
                savedAt = now
                failure = nil
                PayloadStore.save(v, key: key, at: now)
                return true
            } catch {
                failure = loadFailureMessage(error)
                return false
            }
        }
        inFlight = t
        return await t.value
    }

    /// Refresh unless the kept value is younger than `age` (a tab tapped again moments
    /// later needs no new fetch). True when there is a value afterwards.
    @discardableResult
    func refresh(ifOlderThan age: TimeInterval) async -> Bool {
        if let savedAt, value != nil, Date().timeIntervalSince(savedAt) < age { return true }
        await refresh()
        return value != nil
    }

    /// A value that arrived another way (a profile save's answer), kept as a fetch's would be.
    func replace(_ v: Value) {
        let now = Date()
        value = v
        savedAt = now
        failure = nil
        PayloadStore.save(v, key: key, at: now)
    }

    /// A change made on the phone (an optimistic tunebook edit), kept with the value.
    func update(_ change: (inout Value) -> Void) {
        guard var v = value else { return }
        change(&v)
        value = v
        PayloadStore.save(v, key: key, at: savedAt ?? Date())
    }
}

/// A screen's body over a kept payload: see the file's header.
struct Resourced<Value: Codable & Sendable, Content: View>: View {
    let resource: Resource<Value>
    @ViewBuilder let content: (Value) -> Content

    var body: some View {
        if let v = resource.value {
            content(v)
        } else if let message = resource.failure, !resource.refreshing {
            ContentUnavailableView {
                Label("Couldn't load this", systemImage: "wifi.exclamationmark")
            } description: {
                Text(message)
            } actions: {
                Button("Retry") { Task { await resource.refresh() } }.buttonStyle(.bordered)
            }
        } else {
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

/// What the top bar shows for a screen's kept payload: a small spinner while it is
/// refreshed, or "Offline" when the refresh failed. Set by `ceolKept`, read by CeolTopBar.
struct KeptStatus: Equatable {
    var refreshing = false
    var failure: String?

    /// The bar's word for the failure: short, beside the wordmark.
    var failureWord: String? {
        guard let failure else { return nil }
        return failure == offlineLoadMessage ? tr("Offline") : tr("Couldn't refresh")
    }
}

struct KeptStatusPreference: PreferenceKey {
    static let defaultValue: KeptStatus? = nil
    static func reduce(value: inout KeptStatus?, nextValue: () -> KeptStatus?) {
        if let next = nextValue() { value = next }
    }
}

/// The bar's view of a KeptStatus: the spinner, or the word.
struct KeptStatusView: View {
    let status: KeptStatus

    var body: some View {
        if status.refreshing {
            ProgressView().controlSize(.small).tint(CeolTokens.textMuted)
                .transition(.opacity)
                .accessibilityLabel("Updating")
        } else if let word = status.failureWord {
            // Not a Label: the toolbar would keep its icon and drop the word.
            HStack(spacing: 5) {
                Image(systemName: "wifi.slash").font(.system(size: 12))
                Text(word).font(.ceol(size: 13))
            }
            .foregroundStyle(CeolTokens.textMuted)
            .lineLimit(1)
            .transition(.opacity)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("kept.offline")
        }
    }
}

extension View {
    /// Tells the screen's top bar (ceolRootBar / ceolPushedBar, applied after this)
    /// about `resource`: a quiet spinner while it is refreshed over a kept value, and
    /// "Offline" when the refresh failed and the kept value is what's showing.
    func ceolKept<Value>(_ resource: Resource<Value>) -> some View {
        preference(
            key: KeptStatusPreference.self,
            value: resource.value == nil ? nil : KeptStatus(refreshing: resource.refreshing, failure: resource.failure))
    }
}

/// Computed, not stored: the interface language can change while the app runs (spec 057).
var offlineLoadMessage: String { tr("You're offline. Check your connection, then try again.") }

/// A request that never reached the server (no signal, no route, timed out), as against
/// a refusal it answered. The generated client wraps the transport's error in its own.
func isConnectionFailure(_ error: Error) -> Bool {
    let e = (error as? ClientError)?.underlyingError ?? error
    guard let url = e as? URLError else { return false }
    switch url.code {
    case .notConnectedToInternet, .networkConnectionLost, .cannotConnectToHost, .cannotFindHost, .timedOut,
        .dnsLookupFailed, .internationalRoamingOff, .dataNotAllowed, .secureConnectionFailed:
        return true
    default:
        return false
    }
}
