//
//  ContentView.swift
//  Ceol
//
//  Created by Ian Varley on 6/29/26.
//

import CeolAPI
import CeolDesign
import CeolSession
import SwiftUI

/// The screen for where the app is: splash while launching, then sign-in, profile setup
/// or the tabs (AppModel.Phase).
struct ContentView: View {
    @Environment(AppModel.self) private var model
    @State private var minimumSplashDone = false

    var body: some View {
        ZStack {
            if model.phase == .launching || !minimumSplashDone {
                SplashView().transition(.opacity)
            } else {
                Group {
                    switch model.phase {
                    case .upgradeRequired: UpgradeRequiredView().transition(.opacity)
                    case .signedOut: SignInView().transition(.opacity)
                    case .profileSetup: ProfileSetupView().transition(.opacity)
                    case .signedIn, .launching: MainTabView().transition(.opacity)
                    }
                }
                // Spec 057: the id rebuilds the screens when the language changes, so text
                // from tr() follows too. It sits here, not on the root, so the launch tasks
                // below run once (rebuilding the root re-ran start() and re-opened links).
                .id(model.language)
            }
        }
        .animation(.easeInOut(duration: 0.4), value: model.phase)
        .animation(.easeInOut(duration: 0.4), value: minimumSplashDone)
        // The web is dark-only (static/css/theme.css), and the tokens are its palette.
        .preferredColorScheme(.dark)
        .task { await model.start() }
        .task {
            // Long enough to read as a splash, not a flicker, when launch is instant.
            try? await Task.sleep(for: .seconds(1))
            minimumSplashDone = true
        }
    }
}

/// The server says this build is too old to talk to it (app-config force_upgrade).
struct UpgradeRequiredView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "arrow.down.app").font(.system(size: 56)).foregroundStyle(CeolTokens.primary)
            Text("Time to update").font(.ceol(.title2, weight: .semibold))
            Text("This version of Ceol is too old to talk to the server. Update it from the App Store to carry on.")
                .multilineTextAlignment(.center)
                .foregroundStyle(CeolTokens.textMuted)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(CeolTokens.bgColor)
    }
}

/// The four tabs the web's phone tab bar already has (spec 052 §B1): Home, Sessions,
/// Tunes, Me. Search is not a tab — it is the field at the top of Tunes.
enum AppTab: Hashable, CaseIterable {
    case home, sessions, tunes, me

    var title: String {
        switch self {
        case .home: tr("Home")
        case .sessions: tr("Sessions")
        case .tunes: tr("Tunes")
        case .me: tr("Me")
        }
    }

    /// The tab's accessibility identifier ("tab.me"): English whatever the language,
    /// for the UI tests.
    var identifier: String {
        switch self {
        case .home: "tab.home"
        case .sessions: "tab.sessions"
        case .tunes: "tab.tunes"
        case .me: "tab.me"
        }
    }

    var icon: String {
        switch self {
        case .home: "TabHome"
        case .sessions: "TabSessions"
        case .tunes: "TabTunes"
        case .me: "TabMe"
        }
    }
}

/// The tabs, under the web's own tab bar (templates/tab_bar.html, css/tab_bar.css): a
/// flat strip, every tab in the logo's green and the current one in the full accent.
/// The system TabView keeps each tab's state and shows only the current one; its own
/// bar is hidden (iOS 26's glass bar takes no colours) and this one is drawn instead.
/// Every screen hides the system bar through ceolRootBar / ceolPushedBar.
struct MainTabView: View {
    @Environment(AppModel.self) private var model

    /// The tab bar, and the recorder's bar above it while a night is recorded.
    private var bottomBars: CGFloat {
        CeolTabBar.height + (model.recorder != nil ? RecorderBar.height : model.recordings.active != nil ? UploadBar.height : 0)
    }

    var body: some View {
        @Bindable var model = model
        // The bar is laid over the tabs, and every scroll view in them (and on the
        // screens they push) gets a bottom margin of the bar's height, so a list at rest
        // ends above it. (An inset on each tab didn't reach the lists inside the
        // navigation stacks: they came to rest under the bar.)
        TabView(selection: $model.tab) {
            Tab(value: AppTab.home) { HomeView() }
            Tab(value: AppTab.sessions) { SessionsView() }
            Tab(value: AppTab.tunes) { TunesView() }
            Tab(value: AppTab.me) { MeView() }
        }
        .contentMargins(.bottom, model.editingNight ? 0 : bottomBars, for: .scrollContent)
        .contentMargins(.bottom, model.editingNight ? 0 : bottomBars, for: .scrollIndicators)
        .overlay(alignment: .bottom) {
            // Logging a night, the composer takes the bottom of the screen (the night
            // shows the recorder above it itself).
            if !model.editingNight {
                VStack(spacing: 0) {
                    if let recorder = model.recorder {
                        RecorderBar(recorder: recorder)
                    } else if model.recordings.active != nil {
                        UploadBar(store: model.recordings)
                    }
                    CeolTabBar()
                }
            }
        }
        .fullScreenCover(isPresented: Binding(
            get: { model.recorder?.showingMeter ?? false },
            set: { model.recorder?.showingMeter = $0 })
        ) {
            if let recorder = model.recorder {
                ListenMeterView(recorder: recorder) { model.stopRecording() }
            }
        }
        .ceolSharePane()
        .tint(CeolTokens.primary)
    }
}

struct CeolTabBar: View {
    @Environment(AppModel.self) private var model
    /// The bar above the home indicator: its top padding, the tabs, and the rule.
    static let height: CGFloat = 6 + 54 + 1 + 8

    var body: some View {
        HStack(spacing: 0) {
            ForEach(AppTab.allCases, id: \.self) { tab in
                let on = model.tab == tab
                Button {
                    model.tab = tab
                } label: {
                    VStack(spacing: 3) {
                        Image(tab.icon).renderingMode(.template).resizable().scaledToFit().frame(width: 24, height: 24)
                        Text(tab.title).font(.ceol(size: 11, weight: on ? .semibold : .medium, relativeTo: .caption2))
                    }
                    .foregroundStyle(on ? CeolTokens.primary : CeolTokens.logoGreenSoft)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 5)
                    // Where you are, at a glance: a soft green lozenge behind the tab.
                    .background(on ? CeolTokens.primary.opacity(0.16) : .clear, in: RoundedRectangle(cornerRadius: 12))
                    .frame(maxWidth: .infinity, minHeight: 54)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier(tab.identifier)
                .accessibilityLabel(tab.title)
                .accessibilityAddTraits(on ? [.isSelected, .isButton] : .isButton)
            }
        }
        .padding(.top, 6)
        .background(CeolTokens.bgColor.ignoresSafeArea(edges: .bottom))
        .overlay(alignment: .top) { Rectangle().fill(CeolTokens.borderColor).frame(height: 1) }
    }
}

/// Stands in for each tab until its screen is built (plan Phase 3).
struct PlaceholderScreen: View {
    let title: String
    let detail: String

    var body: some View {
        NavigationStack {
            Text(detail)
                .font(.ceol(.subheadline))
                .foregroundStyle(CeolTokens.textMuted)
                .multilineTextAlignment(.center)
                .padding()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(CeolTokens.bgColor)
                .navigationTitle(title)
        }
    }
}

/// While the app starts: the wordmark on black, exactly where the launch screen put it
/// (Ceol-Info.plist, LaunchLogo: 220 points wide, centred), and the tagline fading in
/// under it, so the hand-over from the launch screen doesn't jump.
struct SplashView: View {
    @State private var showTagline = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            Image("LaunchLogo")
                .resizable()
                .scaledToFit()
                .frame(width: 220)
                .accessibilityLabel(Text(verbatim: "Ceol"))
            Text("Trad Irish Session Tracker")
                .font(.ceol(size: 17, weight: .medium))
                .tracking(0.5)
                .foregroundStyle(Color.white.opacity(0.75))
                .offset(y: 78 / 2 + 30)
                .opacity(showTagline ? 1 : 0)
        }
        // Centred on the whole screen, as the launch screen centres its image; centred
        // in the safe area it sat 14 points lower and hopped at the hand-over.
        .ignoresSafeArea()
        .onAppear {
            withAnimation(.easeOut(duration: 0.5).delay(0.1)) { showTagline = true }
        }
    }
}

#Preview("Splash") {
    SplashView()
}

#Preview("Tabs") {
    MainTabView()
        .environment(AppModel(store: MemoryTokenStore("preview")))
        .preferredColorScheme(.dark)
}

#Preview("Sign in") {
    SignInView()
        .environment(AppModel(store: MemoryTokenStore()))
        .preferredColorScheme(.dark)
}
