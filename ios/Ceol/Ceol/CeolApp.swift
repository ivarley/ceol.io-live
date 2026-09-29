//
//  CeolApp.swift
//  Ceol
//
//  Created by Ian Varley on 6/29/26.
//

import SwiftUI

@main
struct CeolApp: App {
    @State private var model = AppModel()

    init() {
        CeolFont.register()
        CeolAppearance.apply()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(model)
                .font(.ceol())
                // Universal Links (applinks:ceol.io) and any URL the app is opened with.
                .onOpenURL { url in Task { await model.open(url) } }
        }
    }
}

/// X-Ceol-Client for this build: "ios/<version> (build <n>)". The server keys the
/// Bearer-token login on the "ios/" prefix and compares the version with
/// MIN_CLIENT_VERSION_IOS to decide force_upgrade.
nonisolated enum ClientID {
    static var current: String {
        let info = Bundle.main.infoDictionary ?? [:]
        let version = info["CFBundleShortVersionString"] as? String ?? "0.0.0"
        let build = info["CFBundleVersion"] as? String ?? "0"
        return "ios/\(version) (build \(build))"
    }
}
