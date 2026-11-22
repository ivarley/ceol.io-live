// The setting chooser: "which written version of this tune do we play?" The app's twin
// of the web drawer's SettingChooser.svelte. Opened from the tune sheet for one layer
// (yours, the session's, or one night's), it pages through every setting of the tune
// (the ones Ceol holds, then the rest from thesession.org as they arrive), showing
// each one's whole notation, and hands the picked one back to the sheet to save.
//
// The list, the paging and the drawing ahead are the settings pager's
// (SettingPager.swift), shared with the sheet's own notation card. Here the backfill
// from thesession.org runs as soon as the list is in: this sheet IS the ask for the
// whole list.
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

    @State private var pager: SettingPagerModel?
    @State private var saving = false
    @State private var failure: String?

    private var setting: SettingPagerModel.Setting? { pager?.setting }
    private var isCurrent: Bool { pager?.isCurrent ?? false }

    var body: some View {
        NavigationStack {
            Group {
                if let pager, !pager.loading {
                    if pager.loadFailed {
                        VStack(spacing: 12) {
                            Text("Couldn't load the settings of this tune.").font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                                .multilineTextAlignment(.center)
                            Button("Try again") { Task { await load() } }.foregroundStyle(CeolTokens.primary)
                        }
                        .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if pager.settings.isEmpty {
                        Text(pager.backfilling ? tr("Looking for settings on thesession.org…") : tr("No settings found for this tune."))
                            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                            .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else {
                        pagerView(pager)
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
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
            .onDisappear { pager?.dispose() }
        }
        .ceolDrawer()
    }

    // MARK: The pager

    private func pagerView(_ pager: SettingPagerModel) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(tuneName).font(.ceol(size: 20, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                HStack(spacing: 10) {
                    stepButton(pager, -1)
                    VStack(spacing: 2) {
                        Text("Setting \(pager.index + 1) of \(pager.count)").font(.ceol(size: 16, weight: .medium))
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
                    stepButton(pager, 1)
                }
                notation(pager)
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

    @ViewBuilder private func notation(_ pager: SettingPagerModel) -> some View {
        if let s = setting {
            if let image = pager.image(s.id, .full) {
                Image(uiImage: image).resizable().scaledToFit()
                    .padding(6)
                    .frame(maxWidth: .infinity)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                    .accessibilityLabel(tr("Notation for setting \(pager.index + 1)"))
            } else if pager.undrawable(s.id, .full) {
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

    private func stepButton(_ pager: SettingPagerModel, _ d: Int) -> some View {
        let n = pager.index + d
        let more = pager.backfilling && d > 0 && n >= pager.count
        return Button { step(d) } label: {
            Group {
                if more { ProgressView() } else { Image(systemName: d < 0 ? "chevron.left" : "chevron.right") }
            }
            .frame(width: 44, height: 44)
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .foregroundStyle(CeolTokens.textColor)
        .disabled(n < 0 || n >= pager.count)
        .opacity(n < 0 || n >= pager.count ? 0.35 : 1)
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
        pager?.step(d)
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

    /// A fresh pager, its held settings at once and thesession.org's list straight after.
    private func load() async {
        pager?.dispose()
        let p = SettingPagerModel(client: model.auth.client, tuneID: tuneID, tuneType: tuneType, current: current, size: .full)
        pager = p
        await p.load()
        p.ensureBackfill()
    }
}
