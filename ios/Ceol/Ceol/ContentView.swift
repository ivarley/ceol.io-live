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
                switch model.phase {
                case .upgradeRequired: UpgradeRequiredView().transition(.opacity)
                case .signedOut: SignInView().transition(.opacity)
                case .profileSetup: ProfileSetupView().transition(.opacity)
                case .signedIn, .launching: MainTabView().transition(.opacity)
                }
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
            Text("Time to update").font(.title2.bold())
            Text("This version of Ceol is too old to talk to the server. Update it from the App Store to carry on.")
                .multilineTextAlignment(.center)
                .foregroundStyle(CeolTokens.secondary)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(CeolTokens.bgColor)
    }
}

/// The four tabs the web's phone tab bar already has (spec 052 §B1): Home, Sessions,
/// Tunes, Me. Search is not a tab — it is the field at the top of Tunes.
enum AppTab: Hashable {
    case home, sessions, tunes, me
}

struct MainTabView: View {
    @State private var selection: AppTab = .home

    var body: some View {
        TabView(selection: $selection) {
            Tab("Home", systemImage: "house", value: AppTab.home) {
                HomeView()
            }
            Tab("Sessions", systemImage: "calendar", value: AppTab.sessions) {
                SessionsView()
            }
            Tab("Tunes", systemImage: "music.note.list", value: AppTab.tunes) {
                TunesView()
            }
            Tab("Me", systemImage: "person.crop.circle", value: AppTab.me) {
                MeView()
            }
        }
        .tint(CeolTokens.primary)
    }
}

/// Stands in for each tab until its screen is built (plan Phase 3).
struct PlaceholderScreen: View {
    let title: String
    let detail: String

    var body: some View {
        NavigationStack {
            Text(detail)
                .font(.subheadline)
                .foregroundStyle(CeolTokens.secondary)
                .multilineTextAlignment(.center)
                .padding()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(CeolTokens.bgColor)
                .navigationTitle(title)
        }
    }
}

struct SplashView: View {
    @State private var animateIn = false

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(red: 0.10, green: 0.35, blue: 0.22),
                         Color(red: 0.04, green: 0.18, blue: 0.12)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 16) {
                Image(systemName: "music.quarternote.3")
                    .font(.system(size: 72, weight: .semibold))
                    .foregroundStyle(.white)
                    .symbolEffect(.bounce, value: animateIn)

                Text("Ceol.io")
                    .font(.system(size: 44, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)

                Text("Irish session tracker")
                    .font(.headline)
                    .foregroundStyle(.white.opacity(0.75))
            }
            .opacity(animateIn ? 1 : 0)
            .scaleEffect(animateIn ? 1 : 0.92)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.7)) {
                animateIn = true
            }
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
