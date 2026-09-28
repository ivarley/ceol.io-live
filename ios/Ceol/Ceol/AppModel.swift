// Which screen the app is on, and the sign-in transitions between them (spec 052 A1,
// plan Phase 2). The API work is CeolSession's AuthService; this decides what the
// app shows around it.
//
//   launching       splash, while app-config and the stored token are checked
//   upgradeRequired the server says this build is too old (MIN_CLIENT_VERSION_IOS)
//   signedOut       the email-first sign-in
//   profileSetup    signed in, but name or location missing (auth.needs_profile_setup)
//   signedIn        the four tabs

import CeolAPI
import CeolSession
import Foundation
import Observation

@Observable
final class AppModel {
    enum Phase: Equatable {
        case launching, upgradeRequired, signedOut, profileSetup, signedIn
    }

    private(set) var phase: Phase = .launching
    private(set) var user: User?
    /// Why an emailed link didn't sign you in, for the sign-in screen to show.
    var linkError: String?
    /// A plain notice for the sign-in screen (e.g. after deleting the account).
    var notice: String?
    /// An emailed link is being exchanged.
    private(set) var openingLink = false

    let auth: AuthService
    /// The server the app talks to; its web pages (Help, Admin) open from here too.
    let server: URL
    /// Hosts, beyond ceol.io, whose sign-in links the app accepts: a development server.
    private let devHosts: Set<String>
    private var pendingLink: URL?

    init(server: URL = AppModel.serverURL, store: any TokenStore = KeychainTokenStore()) {
        let client = Client.ceol(serverURL: server, clientID: ClientID.current, token: { store.token() })
        auth = AuthService(client: client, store: store)
        self.server = server
        devHosts = CeolServer.production.host() == server.host() ? [] : [server.host() ?? ""]
    }

    /// The server to talk to. Production, unless a debug build is launched with
    /// `-CeolServerURL http://127.0.0.1:5031` (a UserDefaults argument).
    static var serverURL: URL {
        #if DEBUG
            if let s = UserDefaults.standard.string(forKey: "CeolServerURL"), let url = URL(string: s) { return url }
        #endif
        return CeolServer.production
    }

    // MARK: - Launch

    func start() async {
        #if DEBUG
            // Test hooks (UI tests, manual runs): -CeolResetSession YES starts signed out
            // (Keychain items survive a reinstall on the simulator); -CeolOpenURL <url>
            // opens a URL as a tapped link would.
            if UserDefaults.standard.bool(forKey: "CeolResetSession") { try? auth.store.setToken(nil) }
            if let s = UserDefaults.standard.string(forKey: "CeolOpenURL"), let url = URL(string: s) { pendingLink = url }
        #endif
        // An obsolete build is told so before anything else. If the server can't be
        // reached, launch anyway: being offline is not a reason to lock the app.
        if let config = try? await auth.appConfig(), config.forceUpgrade {
            phase = .upgradeRequired
            return
        }
        do {
            if let user = try await auth.currentUser() {
                enter(user, next: nil)
            } else {
                phase = .signedOut
            }
        } catch {
            // Can't reach the server, but a token is stored: stay signed in rather than
            // pretend the person is signed out. Screens load what they can.
            phase = auth.store.token() != nil ? .signedIn : .signedOut
        }
        if let url = pendingLink {
            pendingLink = nil
            await open(url)
        }
    }

    // MARK: - Signing in

    /// A successful sign-in, from the password step or an emailed link.
    func signedIn(_ s: SignedIn) {
        linkError = nil
        enter(s.user, next: s.next)
    }

    private func enter(_ user: User, next: SignedIn.Next?) {
        self.user = user
        phase = user.needsProfileSetup || next == .setupProfile ? .profileSetup : .signedIn
    }

    /// Profile setup saved: reload who we are and carry on.
    func profileSaved() async {
        if let user = try? await auth.currentUser() {
            enter(user, next: nil)
        } else {
            phase = .signedIn
        }
    }

    /// A URL the app was opened with. Sign-in links are exchanged for a session; any
    /// other ceol.io link is left for the screens that route pages (a later phase).
    func open(_ url: URL) async {
        guard let link = AuthLink(url, extraHosts: devHosts) else { return }
        if phase == .launching {
            pendingLink = url
            return
        }
        openingLink = true
        defer { openingLink = false }
        do {
            signedIn(try await auth.exchange(link))
        } catch let failure as AuthFailure {
            if phase != .signedIn { phase = .signedOut }
            linkError = Self.message(for: failure)
        } catch {
            if phase != .signedIn { phase = .signedOut }
            linkError = "Couldn't reach Ceol to open that link. Check your connection and tap it again."
        }
    }

    static func message(for failure: AuthFailure) -> String {
        switch failure.code {
        case "invalid_token":
            return "That link has expired or was already used. Enter your email below and we'll send a new one."
        default:
            return failure.message
        }
    }

    // MARK: - Signing out

    func signOut() async {
        await auth.logout()
        user = nil
        phase = .signedOut
    }

    /// The account is gone (AuthService.deleteAccount already forgot the token).
    func accountDeleted() {
        user = nil
        notice = "Your account has been deleted."
        phase = .signedOut
    }
}
