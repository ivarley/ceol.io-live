// Client.ceol(...) — what every request carries, end to end through the generated
// client, with a transport that records the request and answers from a fixture.

import Foundation
import HTTPTypes
import OpenAPIRuntime
import Testing

@testable import CeolAPI

/// Records every request and answers each with `status` and `body`.
private final class RecordingTransport: ClientTransport, @unchecked Sendable {
    private let lock = NSLock()
    private var _requests: [HTTPRequest] = []
    var requests: [HTTPRequest] { lock.withLock { _requests } }

    let status: HTTPResponse.Status
    let body: Data

    init(status: HTTPResponse.Status = .ok, body: Data) {
        self.status = status
        self.body = body
    }

    func send(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String
    ) async throws -> (HTTPResponse, HTTPBody?) {
        lock.withLock { _requests.append(request) }
        var response = HTTPResponse(status: status)
        response.headerFields[.contentType] = "application/json"
        return (response, HTTPBody(self.body))
    }
}

private func appConfigFixture() throws -> Data {
    let url = try #require(Bundle.module.url(forResource: "AppConfig", withExtension: "json", subdirectory: "Fixtures"))
    return try Data(contentsOf: url)
}

@Suite("Client.ceol")
struct CeolClientTests {
    @Test("identifies itself on every request")
    func sendsClientID() async throws {
        let transport = RecordingTransport(body: try appConfigFixture())
        let client = Client.ceol(clientID: "ios/1.2.3 (build 45)", token: { nil }, transport: transport)

        _ = try await client.getAppConfig()

        let request = try #require(transport.requests.first)
        #expect(request.headerFields[ClientIDMiddleware.headerName] == "ios/1.2.3 (build 45)")
        #expect(request.path == "/api/app-config")
    }

    @Test("sends the Bearer token only while one is held")
    func bearerToken() async throws {
        let transport = RecordingTransport(body: try appConfigFixture())
        let signedOut = Client.ceol(clientID: "ios/1.0.0", token: { nil }, transport: transport)
        let signedIn = Client.ceol(clientID: "ios/1.0.0", token: { "tok-123" }, transport: transport)

        _ = try await signedOut.getAppConfig()
        _ = try await signedIn.getAppConfig()

        #expect(transport.requests[0].headerFields[.authorization] == nil)
        #expect(transport.requests[1].headerFields[.authorization] == "Bearer tok-123")
    }

    @Test("reads a real app-config response through the generated operation")
    func decodesThroughTheOperation() async throws {
        let transport = RecordingTransport(body: try appConfigFixture())
        let client = Client.ceol(clientID: "ios/1.0.0", token: { nil }, transport: transport)

        let config = try await client.getAppConfig().ok.body.json

        #expect(config.success)
        #expect(config.forceUpgrade == false)
        #expect(config.client.platform == "ios")
    }

    @MainActor final class Heard {
        var paths: [String] = []
    }

    @Test("reports a 401 to a request that carried the token, except for signing in")
    @MainActor func unauthorized() async throws {
        let envelope = Data(#"{"success": false, "error": "x", "message": "x", "code": "unauthenticated"}"#.utf8)
        let transport = RecordingTransport(status: .unauthorized, body: envelope)
        let heard = Heard()
        let signedIn = Client.ceol(clientID: "ios/1.0.0", token: { "tok" }, unauthorized: { heard.paths.append($0) }, transport: transport)

        _ = try? await signedIn.getMe()
        #expect(heard.paths == ["/api/me"])

        // A wrong password is a 401 about the request, not the token.
        _ = try? await signedIn.loginWithPassword(body: .json(.init(email: "a@example.com", password: "nope")))
        #expect(heard.paths == ["/api/me"])

        // With no token sent, a 401 says nothing about one.
        let signedOut = Client.ceol(clientID: "ios/1.0.0", token: { nil }, unauthorized: { heard.paths.append($0) }, transport: transport)
        _ = try? await signedOut.getMe()
        #expect(heard.paths == ["/api/me"])
    }
}
