// The two emailed links that sign someone in, opened as Universal Links:
//
//   https://ceol.io/auth/login/<token>    a magic-link login (15 minutes)
//   https://ceol.io/verify-email/<token>  a registration link (migration 056) or an
//                                         unverified account's verification link
//
// Both go to POST /api/auth/exchange with the token; the server tells them apart. The
// app accepts them on ceol.io and on www.ceol.io, which redirects to it but appears
// in links sent before ceol.io became canonical.

import Foundation

public enum AuthLink: Equatable, Sendable {
    case login(token: String)
    case verifyEmail(token: String)

    public static let hosts: Set<String> = ["ceol.io", "www.ceol.io"]

    public var token: String {
        switch self {
        case .login(let t), .verifyEmail(let t): return t
        }
    }

    /// The link a URL is, or nil when it is some other page. `extraHosts` admits a
    /// development server (e.g. "localhost").
    public init?(_ url: URL, extraHosts: Set<String> = []) {
        guard let host = url.host()?.lowercased(), Self.hosts.contains(host) || extraHosts.contains(host) else {
            return nil
        }
        let parts = url.pathComponents.filter { $0 != "/" }
        switch parts.count {
        case 3 where parts[0] == "auth" && parts[1] == "login" && !parts[2].isEmpty:
            self = .login(token: parts[2])
        case 2 where parts[0] == "verify-email" && !parts[1].isEmpty:
            self = .verifyEmail(token: parts[1])
        default:
            return nil
        }
    }
}
