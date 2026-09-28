// Sign-in, as the app sees it (spec 052 A1): the web's email-first flow over the native
// handshake. Each call turns a generated operation's result into what the app acts on,
// and keeps the TokenStore in step: a successful login or link exchange stores the
// token, and signing out — or the server saying the token is dead — removes it.
//
// Errors: a refusal the server explains is an AuthFailure carrying its own message
// and code (every auth operation's default response is the Error schema). Anything
// else (no network, a timeout) is thrown as is, for the app to call "couldn't reach".

import CeolAPI
import Foundation
import OpenAPIRuntime

public typealias User = Components.Schemas.User
public typealias AppConfig = Components.Schemas.AppConfig
public typealias Profile = Components.Schemas.Profile

/// The server refused, and said why.
public struct AuthFailure: Error, Equatable, Sendable {
    public let status: Int
    /// The machine code (email_not_verified, invalid_token, account_exists, ...).
    public let code: String?
    /// The server's own sentence, fit to show as is.
    public let message: String

    public init(status: Int, code: String?, message: String) {
        self.status = status
        self.code = code
        self.message = message
    }
}

/// Step 1's answer: what the sign-in screen does next.
public enum CheckEmailOutcome: Equatable, Sendable {
    /// The account has a password: ask for it.
    case needsPassword(email: String)
    /// The account has no password: a login link was emailed.
    case linkSent(email: String, message: String)
    /// No account for the address: a link that creates one was emailed. Nothing
    /// exists until it is opened.
    case registrationStarted(email: String, message: String)
}

/// A successful sign-in, and the one step the server wants first, if any.
public struct SignedIn: Equatable, Sendable {
    public enum Next: Equatable, Sendable {
        /// A magic-link account without a password may set one (optional).
        case setPassword
        /// Name or location missing: the profile needs filling in before the app.
        case setupProfile
    }

    public let user: User
    public let next: Next?
}

public struct AuthService: Sendable {
    public let client: Client
    public let store: any TokenStore

    public init(client: Client, store: any TokenStore) {
        self.client = client
        self.store = store
    }

    // MARK: - Launch

    /// The server's steering for this build: minimum version, force_upgrade, URLs.
    public func appConfig() async throws -> AppConfig {
        try await client.getAppConfig().ok.body.json
    }

    /// Who the stored token belongs to. nil when there is no token, or when the server
    /// says it is no longer valid (the token is then forgotten).
    public func currentUser() async throws -> User? {
        guard store.token() != nil else { return nil }
        switch try await client.getMe() {
        case .ok(let ok):
            return try ok.body.json.user
        case .default(statusCode: 401, _):
            try store.setToken(nil)
            return nil
        case .default(let status, let error):
            throw failure(status, try? error.body.json)
        }
    }

    // MARK: - Signing in

    /// Step 1: the address. The server decides what happens next.
    public func checkEmail(_ email: String) async throws -> CheckEmailOutcome {
        switch try await client.checkEmail(body: .json(.init(email: email))) {
        case .ok(let ok):
            let r = try ok.body.json
            switch r.action {
            case .passwordLogin: return .needsPassword(email: r.email)
            case .magicLinkSent: return .linkSent(email: r.email, message: r.message)
            case .registrationStarted: return .registrationStarted(email: r.email, message: r.message)
            }
        case .default(let status, let error):
            throw failure(status, try? error.body.json)
        }
    }

    /// Step 2 for a password account. Stores the token.
    public func login(email: String, password: String) async throws -> SignedIn {
        switch try await client.loginWithPassword(body: .json(.init(email: email, password: password))) {
        case .ok(let ok):
            return try signedIn(try ok.body.json)
        case .default(let status, let error):
            throw failure(status, try? error.body.json)
        }
    }

    /// An emailed link, opened in the app. Stores the token.
    public func exchange(_ link: AuthLink) async throws -> SignedIn {
        switch try await client.exchangeLoginToken(body: .json(.init(token: link.token))) {
        case .ok(let ok):
            return try signedIn(try ok.body.json)
        case .default(let status, let error):
            throw failure(status, try? error.body.json)
        }
    }

    /// Send the verification email again, for an account whose address was never
    /// confirmed. The server answers the same whether or not the address exists.
    public func resendVerification(email: String) async throws {
        switch try await client.resendVerification(body: .json(.init(email: email))) {
        case .ok: return
        case .default(let status, let error): throw failure(status, try? error.body.json)
        }
    }

    /// Revoke the token on the server, then forget it. The local sign-out happens
    /// even when the server can't be reached: the user asked to be signed out here.
    public func logout() async {
        _ = try? await client.logout()
        try? store.setToken(nil)
    }

    // MARK: - Profile setup

    public func profile() async throws -> Profile {
        try await client.getProfile().ok.body.json
    }

    public func updateProfile(_ fields: Operations.UpdateProfile.Input.Body.JsonPayload) async throws -> Profile {
        switch try await client.updateProfile(body: .json(fields)) {
        case .ok(let ok):
            return try ok.body.json
        case .default(let status, let error):
            throw failure(status, try? error.body.json)
        }
    }

    // MARK: -

    private func signedIn(_ r: Components.Schemas.LoginResponse) throws -> SignedIn {
        // No token means the server took this for the web (X-Ceol-Client missing).
        guard let token = r.token else {
            throw AuthFailure(status: 200, code: "no_token", message: "The server didn't return a sign-in token.")
        }
        try store.setToken(token)
        let next: SignedIn.Next? =
            switch r.next {
            case .setPassword?: .setPassword
            case .setupProfile?: .setupProfile
            default: nil
            }
        return SignedIn(user: r.user, next: next)
    }

    private func failure(_ status: Int, _ body: Components.Schemas._Error?) -> AuthFailure {
        AuthFailure(
            status: status, code: body?.code,
            message: body?.message ?? "Something went wrong (\(status)). Try again.")
    }
}
