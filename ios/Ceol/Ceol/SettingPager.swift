// The settings pager: every written version of one tune, in thesession.org's order,
// with the notation of the one in view drawn ahead of you. One engine behind two
// faces — the tune sheet's notation card (swipe it, or the chevrons, to page in place)
// and the SettingChooser sheet (the same list, whole notation, "Use this setting"). The
// app's twin of the web's settingpager.svelte.js.
//
// The list is the settings Ceol holds (the tune preview, one cheap call) and then
// thesession.org's full list merged in (`backfill`). The backfill is a live call to
// thesession.org, and the sheet opens on every tune tap, so it is LAZY: `ensureBackfill()`
// runs it once, when something asks for it (the chooser right after load; the sheet on
// the first swipe or step). A step past the end while the backfill is still in flight
// is kept and applied when the list grows.
//
// Paging has to feel instant, so the renders run ahead: the setting in view, then the
// next, then the one before (a swipe slides either neighbour on), then the one after
// next, one at a time, in the size being looked at. A setting Ceol holds is drawn
// by the server and kept there for everyone; one only thesession.org has is drawn for
// this look only (it isn't Ceol's until somebody picks it).

import CeolAPI
import Observation
import SwiftUI
import UIKit

@Observable @MainActor
final class SettingPagerModel {
    enum Kind: Hashable { case incipit, full }

    struct Setting: Equatable, Identifiable {
        let id: Int
        let key: String?
        let abc: String
        let incipitAbc: String?
        let remote: Bool
    }

    let tuneID: Int
    let tuneType: String?
    /// thesession.org's list and the ephemeral render are sign-in gated: a guest pages
    /// the held settings only.
    let canBackfill: Bool
    private let client: Client

    private(set) var settings: [Setting] = []
    private(set) var index = 0
    private(set) var loading = true
    private(set) var loadFailed = false
    private(set) var backfilling = false
    /// Has the user paged? (Then a late backfill mustn't move them.)
    private(set) var touched = false
    /// The layer's setting now: where the pager opens, and the one marked in use.
    private(set) var current: Int?
    /// The size being looked at, and drawn ahead.
    var size: Kind {
        didSet { if size != oldValue { warm() } }
    }

    private var images: [String: UIImage] = [:]
    private var undrawables: Set<String> = []
    private var backfillStarted = false
    private var pendingStep = 0
    private var warmRun = 0
    private var generation = 0

    init(client: Client, tuneID: Int, tuneType: String?, current: Int?, size: Kind = .incipit, canBackfill: Bool = true) {
        self.client = client
        self.tuneID = tuneID
        self.tuneType = tuneType
        self.current = current
        self.size = size
        self.canBackfill = canBackfill
    }

    var setting: Setting? { settings.indices.contains(index) ? settings[index] : nil }
    var count: Int { settings.count }
    var isCurrent: Bool { setting != nil && setting?.id == current }

    private func key(_ id: Int, _ kind: Kind) -> String { "\(id):\(kind == .full ? "full" : "incipit")" }

    /// The drawn notation of a setting in a size, if it has arrived.
    func image(_ id: Int, _ kind: Kind? = nil) -> UIImage? { images[key(id, kind ?? size)] }
    /// The renderer couldn't draw it (the abc still says what the setting is).
    func undrawable(_ id: Int, _ kind: Kind? = nil) -> Bool { undrawables.contains(key(id, kind ?? size)) }

    /// An image the caller already has (the detail payload's): no render needed.
    func seed(_ image: UIImage?, for id: Int, kind: Kind) {
        guard let image else { return }
        images[key(id, kind)] = image
    }

    // MARK: Loading

    /// The settings Ceol holds, at once.
    func load() async {
        generation += 1
        let gen = generation
        settings = []
        index = 0
        touched = false
        loading = true
        loadFailed = false
        backfilling = false
        backfillStarted = false
        pendingStep = 0
        do {
            let p = try await client.getTunePreview(path: .init(tuneId: tuneID)).ok.body.json
            guard gen == generation else { return }
            for s in p.settings {
                if let b = s.incipitImage, let data = Data(base64Encoded: b), let img = UIImage(data: data) {
                    seed(img, for: s.settingId, kind: .incipit)
                }
            }
            settings = p.settings.map { Setting(id: $0.settingId, key: $0.key, abc: $0.abc, incipitAbc: $0.incipitAbc, remote: false) }
            loading = false
            jumpToCurrent()
            warm()
        } catch {
            guard gen == generation else { return }
            loading = false
            loadFailed = true
        }
    }

    /// thesession.org's full list merged in setting order, so "Setting 3 of 12" means
    /// what it does there. Once per load; offline or thesession.org down, the settings
    /// Ceol holds stand.
    func ensureBackfill() {
        guard canBackfill, !backfillStarted, !loading, !loadFailed else { return }
        backfillStarted = true
        let gen = generation
        Task { await backfill(gen) }
    }

    private func backfill(_ gen: Int) async {
        backfilling = true
        guard let ts = try? await client.getTheSessionTunePreview(
            path: .init(thesessionId: tuneID), query: .init(full: ._1)
        ).ok.body.json else {
            if gen == generation {
                backfilling = false
                pendingStep = 0
            }
            return
        }
        guard gen == generation else { return }
        backfilling = false
        let have = Set(settings.map(\.id))
        let extra = (ts.settings ?? []).filter { !have.contains($0.settingId) }
            .map { Setting(id: $0.settingId, key: $0.key, abc: $0.abc, incipitAbc: $0.incipitAbc, remote: true) }
        guard !extra.isEmpty else {
            pendingStep = 0
            return
        }
        let showing = setting?.id
        settings = (settings + extra).sorted { $0.id < $1.id }
        // The current setting may only just have arrived; otherwise stay on the one
        // showing, then honour a step asked for while the list was still growing.
        if !(!touched && jumpToCurrent()), let showing, let i = settings.firstIndex(where: { $0.id == showing }) {
            index = i
        }
        if pendingStep != 0 {
            let n = index + pendingStep
            pendingStep = 0
            if settings.indices.contains(n) {
                index = n
                touched = true // the user did page; the list was just late
            }
        }
        warm()
    }

    @discardableResult
    private func jumpToCurrent() -> Bool {
        guard let current, let i = settings.firstIndex(where: { $0.id == current }) else { return false }
        index = i
        return true
    }

    // MARK: Paging

    /// One step on, or back. Past the end while more may be coming, the step waits for
    /// them; a step also starts the backfill, since paging is the ask for the whole list.
    func step(_ d: Int) {
        guard !loading, !loadFailed else { return }
        ensureBackfill()
        let n = index + d
        guard settings.indices.contains(n) else {
            if d > 0 && backfilling { pendingStep = d }
            return
        }
        index = n
        touched = true
        pendingStep = 0
        warm()
    }

    @discardableResult
    func jumpTo(_ id: Int) -> Bool {
        guard let i = settings.firstIndex(where: { $0.id == id }) else { return false }
        index = i
        touched = true
        warm()
        return true
    }

    /// The layer's setting changed (a save): the mark moves; the pager stays put.
    func setCurrent(_ id: Int?) { current = id }

    /// Whatever is still in flight lands on nothing.
    func dispose() {
        generation += 1
        warmRun += 1
    }

    // MARK: Drawing ahead

    /// The one in view first, then its neighbours (next, then before: both slide on under
    /// a swipe), then the one after next, one at a time so the renderer works on what
    /// you'll see soonest. Paging on starts a fresh run from the new place.
    private func warm() {
        warmRun += 1
        let run = warmRun
        let from = index
        let list = settings
        let kind = size
        Task {
            for i in [from, from + 1, from - 1, from + 2] where list.indices.contains(i) {
                guard run == warmRun else { return }
                await draw(list[i], kind)
            }
        }
    }

    private func draw(_ s: Setting, _ kind: Kind) async {
        let k = key(s.id, kind)
        guard images[k] == nil, !undrawables.contains(k) else { return }
        let base64: String?
        if s.remote {
            base64 = try? await client.renderAbc(body: .json(.init(
                abc: s.abc, key: s.key, tuneType: tuneType, kind: kind == .full ? .full : .incipit))).ok.body.json.image
        } else {
            base64 = try? await client.getSettingImage(
                path: .init(settingId: s.id), query: .init(kind: kind == .full ? .full : .incipit)).ok.body.json.image
        }
        if let base64, let data = Data(base64Encoded: base64), let image = UIImage(data: data) {
            images[k] = image
        } else {
            undrawables.insert(k)
        }
    }
}
