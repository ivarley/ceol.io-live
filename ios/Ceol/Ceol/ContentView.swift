//
//  ContentView.swift
//  Ceol
//
//  Created by Ian Varley on 6/29/26.
//

import CeolDesign
import SwiftUI

struct ContentView: View {
    @State private var showSplash = true

    var body: some View {
        ZStack {
            if showSplash {
                SplashView()
                    .transition(.opacity)
            } else {
                MainTabView()
                    .transition(.opacity)
            }
        }
        // The web is dark-only (static/css/theme.css), and the tokens are its palette.
        .preferredColorScheme(.dark)
        .task {
            // Show the splash briefly, then fade into the app.
            try? await Task.sleep(for: .seconds(2))
            withAnimation(.easeInOut(duration: 0.5)) {
                showSplash = false
            }
        }
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
                PlaceholderScreen(title: "Home", detail: "Today's session, this week, and what you're learning.")
            }
            Tab("Sessions", systemImage: "calendar", value: AppTab.sessions) {
                PlaceholderScreen(title: "Sessions", detail: "The sessions you play at, and the logs of each night.")
            }
            Tab("Tunes", systemImage: "music.note.list", value: AppTab.tunes) {
                PlaceholderScreen(title: "Tunes", detail: "Your list, and the whole catalogue from the search field.")
            }
            Tab("Me", systemImage: "person.crop.circle", value: AppTab.me) {
                PlaceholderScreen(title: "Me", detail: "Your profile, your instruments, and your account.")
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
        .preferredColorScheme(.dark)
}
