// The one way the app builds an API client. The operations themselves (getHome,
// applyLiveOp, ...) are generated from specs/api/native-surface.yaml into `Client`;
// this file only adds what every request needs and the spec cannot say:
//
//   - X-Ceol-Client: ios/<version> (build <n>). The server keys the Bearer-vs-cookie
//     login on it, records it on the session and in login history, and compares it
//     with MIN_CLIENT_VERSION_IOS for /api/app-config's force_upgrade (spec 052 A1/A8).
//   - Authorization: Bearer <token>, whenever a token is held. The token is a
//     user_session id; the app keeps it in the Keychain.

import Foundation
import HTTPTypes
import OpenAPIRuntime
import OpenAPIURLSession

public enum CeolServer {
    /// The canonical host. www.ceol.io redirects here.
    public static let production = URL(string: "https://ceol.io")!
}

/// Where the token comes from. Called once per request, so a sign-in or sign-out
/// takes effect on the very next call without rebuilding the client.
public typealias TokenProvider = @Sendable () async -> String?

extension Client {
    /// A client for `serverURL` that identifies itself as `clientID` (the value of
    /// X-Ceol-Client, e.g. "ios/1.0.0 (build 12)") and sends `token()` when it has one.
    /// `language()` is the app's interface language ("en" / "ga"), sent as
    /// Accept-Language so the server answers in it even before sign-in (spec 057).
    public static func ceol(
        serverURL: URL = CeolServer.production,
        clientID: String,
        token: @escaping TokenProvider,
        language: @escaping @Sendable () -> String? = { nil },
        transport: any ClientTransport = URLSessionTransport()
    ) -> Client {
        Client(
            serverURL: serverURL,
            transport: transport,
            middlewares: [
                ClientIDMiddleware(clientID: clientID, language: language), BearerTokenMiddleware(token: token),
            ]
        )
    }
}

/// X-Ceol-Client on every request, and Accept-Language when the app names its language.
public struct ClientIDMiddleware: ClientMiddleware {
    public static let headerName = HTTPField.Name("X-Ceol-Client")!

    public let clientID: String
    public let language: @Sendable () -> String?

    public init(clientID: String, language: @escaping @Sendable () -> String? = { nil }) {
        self.clientID = clientID
        self.language = language
    }

    public func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        var request = request
        request.headerFields[Self.headerName] = clientID
        if let language = language() { request.headerFields[.acceptLanguage] = language }
        return try await next(request, body, baseURL)
    }
}

/// Authorization: Bearer on every request, while a token is held. Public endpoints
/// (app-config, check-email, the login itself) simply ignore it.
public struct BearerTokenMiddleware: ClientMiddleware {
    public let token: TokenProvider

    public init(token: @escaping TokenProvider) {
        self.token = token
    }

    public func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        var request = request
        if let token = await token() {
            request.headerFields[.authorization] = "Bearer \(token)"
        }
        return try await next(request, body, baseURL)
    }
}
