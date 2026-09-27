//
//  CeolApp.swift
//  Ceol
//
//  Created by Ian Varley on 6/29/26.
//

import CeolAPI
import SwiftUI

@main
struct CeolApp: App {
    /// The one API client (spec 052). Signed out until sign-in lands (Phase 2), when
    /// the token provider reads the Keychain.
    private let api = Client.ceol(clientID: ClientID.current, token: { nil })

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.api, api)
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

extension EnvironmentValues {
    @Entry var api: Client? = nil
}
