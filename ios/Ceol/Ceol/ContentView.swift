//
//  ContentView.swift
//  Ceol
//
//  Created by Ian Varley on 6/29/26.
//

import SwiftUI

struct ContentView: View {
    @State private var showSplash = true

    var body: some View {
        ZStack {
            if showSplash {
                SplashView()
                    .transition(.opacity)
            } else {
                HomePlaceholderView()
                    .transition(.opacity)
            }
        }
        .task {
            // Show the splash briefly, then fade into the app.
            try? await Task.sleep(for: .seconds(2))
            withAnimation(.easeInOut(duration: 0.5)) {
                showSplash = false
            }
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

struct HomePlaceholderView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "music.note.list")
                .font(.largeTitle)
                .foregroundStyle(.tint)
            Text("Home")
                .font(.title.bold())
            Text("Your sessions and tunes will live here.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding()
    }
}

#Preview("Splash") {
    SplashView()
}

#Preview("Home") {
    HomePlaceholderView()
}
