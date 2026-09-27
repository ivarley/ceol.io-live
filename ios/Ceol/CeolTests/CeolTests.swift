//
//  CeolTests.swift
//  CeolTests
//
//  Created by Ian Varley on 6/29/26.
//

import Foundation
import Testing
@testable import Ceol

struct CeolTests {

    /// The server parses X-Ceol-Client as "<platform>/<version> ..." (api_auth.current_client):
    /// "ios/" is what earns a Bearer token at login, and the version is compared with
    /// MIN_CLIENT_VERSION_IOS. A different shape would quietly get the web's cookie login.
    @Test func clientIDHasTheShapeTheServerParses() throws {
        let id = ClientID.current
        let match = try #require(id.wholeMatch(of: /ios\/(\d+(?:\.\d+)*) \(build (\S+)\)/))
        #expect(!match.1.isEmpty)
        #expect(!match.2.isEmpty)
    }
}
