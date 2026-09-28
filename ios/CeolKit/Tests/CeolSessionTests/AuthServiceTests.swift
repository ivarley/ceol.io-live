// AuthService against a transport that answers each path with a canned status and
// JSON body (shapes as the server sends them; the contract test holds the server to
// the same shapes).

import CeolAPI
import Foundation
import HTTPTypes
import OpenAPIRuntime
import Testing

@testable import CeolSession

private final class StubTransport: ClientTransport, @unchecked Sendable {
    private let lock = NSLock()
    private var routes: [String: (Int, String)]
    private(set) var requests: [HTTPRequest] = []

    init(_ routes: [String: (Int, String)]) { self.routes = routes }

    func send(_ request: HTTPRequest, body: HTTPBody?, baseURL: URL, operationID: String) async throws
        -> (HTTPResponse, HTTPBody?)
    {
        let path = request.path ?? ""
        let route = lock.withLock { () -> (Int, String)? in
            requests.append(request)
            return routes[path]
        }
        guard let (status, json) = route else { throw URLError(.notConnectedToInternet) }
        var response = HTTPResponse(status: .init(code: status))
        response.headerFields[.contentType] = "application/json"
        return (response, HTTPBody(json))
    }
}

private let user = """
{"user_id": 7, "person_id": 24, "username": "vera", "email": "vera@example.com", "first_name": "Vera",
 "last_name": "Verify", "is_system_admin": false, "timezone": "UTC", "email_verified": true,
 "has_password": true, "needs_profile_setup": false}
"""

private func login(next: String = "null", token: String? = "tok-1") -> String {
    let tokenField = token.map { ", \"token\": \"\($0)\", \"token_type\": \"Bearer\"" } ?? ""
    return """
    {"success": true, "user": \(user), "next": \(next), "method": "password"\(tokenField)}
    """
}

private func error(_ code: String, _ message: String) -> String {
    #"{"success": false, "error": "\#(message)", "message": "\#(message)", "code": "\#(code)"}"#
}

private func service(_ routes: [String: (Int, String)], token: String? = nil) -> (AuthService, MemoryTokenStore, StubTransport) {
    let store = MemoryTokenStore(token)
    let transport = StubTransport(routes)
    let client = Client.ceol(clientID: "ios/1.0 (build 1)", token: { store.token() }, transport: transport)
    return (AuthService(client: client, store: store), store, transport)
}

@Suite("AuthService")
struct AuthServiceTests {
    @Test("check-email: each action is a next step")
    func checkEmail() async throws {
        for (action, expected) in [
            ("password_login", CheckEmailOutcome.needsPassword(email: "v@x.io")),
            ("magic_link_sent", .linkSent(email: "v@x.io", message: "Check your email")),
            ("registration_started", .registrationStarted(email: "v@x.io", message: "Check your email")),
        ] {
            let (auth, _, _) = service([
                "/api/auth/check-email": (200, #"{"action": "\#(action)", "email": "v@x.io", "message": "Check your email"}"#)
            ])
            #expect(try await auth.checkEmail("V@x.io") == expected)
        }
    }

    @Test("login stores the token and passes on what the server wants next")
    func loginStoresToken() async throws {
        let (auth, store, _) = service(["/api/auth/login-password": (200, login(next: #""setup_profile""#))])
        let signedIn = try await auth.login(email: "vera@example.com", password: "pw")
        #expect(store.token() == "tok-1")
        #expect(signedIn.next == .setupProfile)
        #expect(signedIn.user.firstName == "Vera")
    }

    @Test("a login answered without a token is refused, not half-signed-in")
    func loginWithoutToken() async throws {
        let (auth, store, _) = service(["/api/auth/login-password": (200, login(token: nil))])
        await #expect(throws: AuthFailure.self) { try await auth.login(email: "v@x.io", password: "pw") }
        #expect(store.token() == nil)
    }

    @Test("refusals carry the server's code and message")
    func refusals() async throws {
        let (auth, store, _) = service([
            "/api/auth/login-password": (403, error("email_not_verified", "Please verify your email address first")),
            "/api/auth/exchange": (409, error("account_exists", "There's already an account for this email address.")),
        ])
        do {
            _ = try await auth.login(email: "v@x.io", password: "pw")
            Issue.record("expected a refusal")
        } catch let f as AuthFailure {
            #expect(f == AuthFailure(status: 403, code: "email_not_verified", message: "Please verify your email address first"))
        }
        do {
            _ = try await auth.exchange(.verifyEmail(token: "abc"))
            Issue.record("expected a refusal")
        } catch let f as AuthFailure {
            #expect(f.code == "account_exists")
        }
        #expect(store.token() == nil)
    }

    @Test("an emailed link exchanges for a stored token")
    func exchange() async throws {
        let (auth, store, transport) = service(["/api/auth/exchange": (200, login())])
        _ = try await auth.exchange(.login(token: "link-token"))
        #expect(store.token() == "tok-1")
        #expect(transport.requests.first?.path == "/api/auth/exchange")
    }

    @Test("currentUser: nil without a token, and a dead token is forgotten")
    func currentUser() async throws {
        let (noToken, _, transport) = service([:])
        #expect(try await noToken.currentUser() == nil)
        #expect(transport.requests.isEmpty)

        let (dead, store, _) = service(["/api/me": (401, error("unauthorized", "Login required"))], token: "old")
        #expect(try await dead.currentUser() == nil)
        #expect(store.token() == nil)

        let (live, liveStore, liveTransport) = service(["/api/me": (200, #"{"success": true, "user": \#(user)}"#)], token: "good")
        #expect(try await live.currentUser()?.userId == 7)
        #expect(liveStore.token() == "good")
        #expect(liveTransport.requests.first?.headerFields[.authorization] == "Bearer good")
    }

    @Test("logout forgets the token even when the server can't be reached")
    func logoutOffline() async throws {
        let (auth, store, _) = service([:], token: "tok")
        await auth.logout()
        #expect(store.token() == nil)
    }

    @Test("delete account: forgets the token; a refusal keeps it")
    func deleteAccount() async throws {
        let (auth, store, _) = service(["/api/me/delete-account": (200, #"{"success": true}"#)], token: "tok")
        try await auth.deleteAccount(confirmEmail: "vera@example.com")
        #expect(store.token() == nil)

        let (refused, keptStore, _) = service(
            ["/api/me/delete-account": (403, error("admin_account", "A system admin account can't be deleted from here."))],
            token: "tok")
        do {
            try await refused.deleteAccount(confirmEmail: "ian@ceol.io")
            Issue.record("expected a refusal")
        } catch let f as AuthFailure {
            #expect(f.code == "admin_account")
        }
        #expect(keptStore.token() == "tok")
    }

    @Test("network failures are thrown as is, not dressed up as refusals")
    func networkFailure() async throws {
        let (auth, _, _) = service([:])
        await #expect(throws: (any Error).self) { try await auth.checkEmail("v@x.io") }
        do { _ = try await auth.checkEmail("v@x.io") } catch { #expect(!(error is AuthFailure)) }
    }
}

@Suite("AuthLink")
struct AuthLinkTests {
    @Test("the two emailed links, on either host")
    func parses() {
        #expect(AuthLink(URL(string: "https://ceol.io/auth/login/abc123")!) == .login(token: "abc123"))
        #expect(AuthLink(URL(string: "https://www.ceol.io/verify-email/xyz")!) == .verifyEmail(token: "xyz"))
        #expect(AuthLink(URL(string: "https://CEOL.io/verify-email/xyz?utm=1")!) == .verifyEmail(token: "xyz"))
    }

    @Test("anything else is not a sign-in link")
    func rejects() {
        for s in [
            "https://ceol.io/sessions/austin/mueller", "https://ceol.io/auth/login/", "https://ceol.io/verify-email",
            "https://evil.example/auth/login/abc", "https://ceol.io/auth/login/abc/extra",
        ] {
            #expect(AuthLink(URL(string: s)!) == nil, "\(s)")
        }
    }

    @Test("a development host only when admitted")
    func devHost() {
        let url = URL(string: "http://localhost:5031/auth/login/abc")!
        #expect(AuthLink(url) == nil)
        #expect(AuthLink(url, extraHosts: ["localhost"]) == .login(token: "abc"))
    }
}

@Suite("Token stores")
struct TokenStoreTests {
    @Test("memory store")
    func memory() throws {
        let store = MemoryTokenStore()
        #expect(store.token() == nil)
        try store.setToken("a")
        #expect(store.token() == "a")
        try store.setToken(nil)
        #expect(store.token() == nil)
    }

    @Test("Keychain store round trip")
    func keychain() throws {
        let store = KeychainTokenStore(service: "io.ceol.Ceol.tests", account: UUID().uuidString)
        defer { try? store.setToken(nil) }
        #expect(store.token() == nil)
        try store.setToken("first")
        try store.setToken("second")  // replaces, never duplicates
        #expect(store.token() == "second")
        try store.setToken(nil)
        #expect(store.token() == nil)
    }
}
