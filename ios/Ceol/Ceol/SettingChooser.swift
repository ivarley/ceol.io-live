// The setting chooser: "which written version of this tune do we play?" The app's twin
// of the web drawer's SettingChooser.svelte. Opened from the tune sheet for one layer
// (yours, the session's, or one night's), it pages through every setting of the tune
// (the ones Ceol holds, then the rest from thesession.org as they arrive), showing
// each one's whole notation, and hands the picked one back to the sheet to save.
//
// Paging has to feel instant, so the renders run ahead: while you look at a setting,
// the next two are drawn one after another. A setting Ceol holds is drawn by the
// server and kept there for everyone; one only thesession.org has is drawn for this
// look only (it isn't Ceol's until somebody picks it).
//
// i18n-converted (spec 057).

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI
import UIKit

struct SettingChooser: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let tuneID: Int
    let tuneName: String
    let tuneType: String?
    let heading: String
    /// The setting the layer uses now: where the pager opens, and the one marked in use.
    let current: Int?
    /// Saves the pick: nil when saved (the chooser then closes), else what went wrong.
    let choose: (Int) async -> String?

    struct Setting: Equatable {
        let id: Int
        let key: String?
        let abc: String
        let remote: Bool
    }

    @State private var settings: [Setting] = []
    @State private var index = 0
    @State private var loading = true
    @State private var loadFailed: String?
    @State private var backfilling = false
    @State private var touched = false
    @State private var saving = false
    @State private var failure: String?
    @State private var images: [Int: UIImage] = [:]
    @State private var undrawable: Set<Int> = []
    @State private var warmRun = 0

    private var setting: Setting? { settings.indices.contains(index) ? settings[index] : nil }
    private var isCurrent: Bool { setting != nil && setting?.id == current }

    var body: some View {
        NavigationStack {
            Group {
                if loading {
                    ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let loadFailed {
                    VStack(spacing: 12) {
                        Text(loadFailed).font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                            .multilineTextAlignment(.center)
                        Button("Try again") { Task { await load() } }.foregroundStyle(CeolTokens.primary)
                    }
                    .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if settings.isEmpty {
                    Text(backfilling ? tr("Looking for settings on thesession.org…") : tr("No settings found for this tune."))
                        .font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                        .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    pager
                }
            }
            .background(TuneSheet.surface)
            .navigationTitle(heading)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
            .safeAreaInset(edge: .bottom, spacing: 0) { if setting != nil { useButton } }
            .task { await load() }
            .onChange(of: index) { warm() }
            .onChange(of: settings) { warm() }
        }
        .ceolDrawer()
    }

    // MARK: The pager

    private var pager: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(tuneName).font(.ceol(size: 20, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                HStack(spacing: 10) {
                    stepButton(-1)
                    VStack(spacing: 2) {
                        Text("Setting \(index + 1) of \(settings.count)").font(.ceol(size: 16, weight: .medium))
                        HStack(spacing: 6) {
                            if let s = setting {
                                Text(verbatim: "#\(s.id)" + (s.key.map { " · \($0)" } ?? ""))
                                    .foregroundStyle(CeolTokens.textMuted)
                            }
                            if isCurrent {
                                (Text(verbatim: "★ ") + Text("in use")).foregroundStyle(CeolTokens.warning)
                            }
                        }
                        .font(.ceol(size: 14))
                    }
                    .frame(maxWidth: .infinity)
                    .foregroundStyle(CeolTokens.textColor)
                    stepButton(1)
                }
                notation
                    .contentShape(Rectangle())
                    // Swipe the staff to page, as well as the arrows.
                    .gesture(DragGesture(minimumDistance: 30).onEnded { v in
                        if v.translation.width < -40 { step(1) } else if v.translation.width > 40 { step(-1) }
                    })
                if let s = setting {
                    Link(destination: URL(string: "https://thesession.org/tunes/\(tuneID)?setting=\(s.id)#setting\(s.id)")!) {
                        Text("View on TheSession.org")
                    }
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                }
            }
            .padding(20)
        }
    }

    @ViewBuilder private var notation: some View {
        if let s = setting {
            if let image = images[s.id] {
                Image(uiImage: image).resizable().scaledToFit()
                    .padding(6)
                    .frame(maxWidth: .infinity)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                    .accessibilityLabel(tr("Notation for setting \(index + 1)"))
            } else if undrawable.contains(s.id) {
                // The renderer couldn't draw it: the abc still says what the setting is.
                Text(verbatim: s.abc).font(.system(size: 13, design: .monospaced))
                    .foregroundStyle(.black).padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
            } else {
                ProgressView().tint(.gray).frame(maxWidth: .infinity, minHeight: 180)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
            }
        }
    }

    private func stepButton(_ d: Int) -> some View {
        let n = index + d
        let more = backfilling && d > 0 && n >= settings.count
        return Button { step(d) } label: {
            Group {
                if more { ProgressView() } else { Image(systemName: d < 0 ? "chevron.left" : "chevron.right") }
            }
            .frame(width: 44, height: 44)
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .foregroundStyle(CeolTokens.textColor)
        .disabled(n < 0 || n >= settings.count)
        .opacity(n < 0 || n >= settings.count ? 0.35 : 1)
        .accessibilityLabel(d < 0 ? tr("Previous setting") : tr("Next setting"))
        .accessibilityIdentifier(d < 0 ? "chooser.prev" : "chooser.next")
    }

    private var useButton: some View {
        VStack(spacing: 6) {
            if let failure { Text(failure).font(.ceol(size: 14)).foregroundStyle(CeolTokens.danger) }
            Button { Task { await use() } } label: {
                Text(saving ? tr("Saving…") : isCurrent ? tr("This is the one in use") : tr("Use this setting"))
                    .font(.ceol(size: 17, weight: .semibold))
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .foregroundStyle(.white)
                    .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
            }
            .buttonStyle(.plain)
            .disabled(isCurrent || saving)
            .opacity(isCurrent || saving ? 0.55 : 1)
            .accessibilityIdentifier("chooser.use")
        }
        .padding(.horizontal, 20).padding(.vertical, 12)
        .background(TuneSheet.surface)
    }

    private func step(_ d: Int) {
        let n = index + d
        guard settings.indices.contains(n) else { return }
        index = n
        touched = true
        failure = nil
    }

    private func use() async {
        guard let s = setting, !isCurrent, !saving else { return }
        saving = true
        failure = nil
        let problem = await choose(s.id)
        saving = false
        if let problem { failure = problem } else { dismiss() }
    }

    // MARK: Loading

    /// The settings Ceol holds first (at once), then thesession.org's full list merged
    /// in setting order, so "Setting 3 of 12" means what it does there.
    private func load() async {
        loading = true
        loadFailed = nil
        do {
            let p = try await model.auth.client.getTunePreview(path: .init(tuneId: tuneID)).ok.body.json
            settings = p.settings.map { Setting(id: $0.settingId, key: $0.key, abc: $0.abc, remote: false) }
            loading = false
            jumpToCurrent()
            await backfill()
        } catch {
            loading = false
            loadFailed = tr("Couldn't load the settings of this tune.")
        }
    }

    private func backfill() async {
        backfilling = true
        defer { backfilling = false }
        guard let ts = try? await model.auth.client.getTheSessionTunePreview(
            path: .init(thesessionId: tuneID), query: .init(full: ._1)
        ).ok.body.json else { return }  // offline or thesession.org down: the ones we hold stand
        let have = Set(settings.map(\.id))
        let extra = (ts.settings ?? []).filter { !have.contains($0.settingId) }
            .map { Setting(id: $0.settingId, key: $0.key, abc: $0.abc, remote: true) }
        guard !extra.isEmpty else { return }
        let showing = setting?.id
        settings = (settings + extra).sorted { $0.id < $1.id }
        // The current setting may only just have arrived; otherwise stay on the one showing.
        if !touched && jumpToCurrent() { return }
        if let showing, let i = settings.firstIndex(where: { $0.id == showing }) { index = i }
    }

    @discardableResult
    private func jumpToCurrent() -> Bool {
        guard let current, let i = settings.firstIndex(where: { $0.id == current }) else { return false }
        index = i
        return true
    }

    // MARK: Drawing ahead

    /// The one in view first, then the next two, one at a time so the renderer works on
    /// what you'll see soonest. Paging on starts a fresh run from the new place.
    private func warm() {
        warmRun += 1
        let run = warmRun
        let from = index
        let list = settings
        Task {
            for i in [from, from + 1, from + 2] where list.indices.contains(i) {
                guard run == warmRun else { return }
                await draw(list[i])
            }
        }
    }

    private func draw(_ s: Setting) async {
        guard images[s.id] == nil, !undrawable.contains(s.id) else { return }
        let base64: String?
        if s.remote {
            base64 = try? await model.auth.client.renderAbc(body: .json(.init(
                abc: s.abc, key: s.key, tuneType: tuneType, kind: .full))).ok.body.json.image
        } else {
            base64 = try? await model.auth.client.getSettingImage(
                path: .init(settingId: s.id), query: .init(kind: .full)).ok.body.json.image
        }
        if let base64, let data = Data(base64Encoded: base64), let image = UIImage(data: data) {
            images[s.id] = image
        } else {
            undrawable.insert(s.id)
        }
    }
}
