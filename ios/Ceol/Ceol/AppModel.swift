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
import CeolLogic
import Foundation
import Observation

@Observable
final class AppModel {
    enum Phase: Equatable {
        case launching, upgradeRequired, signedOut, profileSetup, signedIn
    }

    private(set) var phase: Phase = .launching
    private(set) var user: User?
    /// The tab on screen; a screen can move you to another (Home's "See all" -> Tunes).
    var tab: AppTab = .home
    /// The Sessions tab's stack. Home opens sessions and nights here, in the Sessions
    /// tab, which is where they live (as on the web, where they are /sessions pages).
    var sessionsPath: [Route] = []
    /// The Tunes tab's status filter (nil: All). Home's Learning / To Learn boxes set it.
    var tunesStatus: MyTunesRules.Status?

    /// The Share pane, when open (ShareButton sets it; ceolSharePane shows it).
    var sharing: ShareTarget?
    /// What Share offers while a drawer is up over the screen (the tune drawer: that
    /// tune's page). The drawer sets it as it appears and clears it as it goes.
    var shareOverride: ShareTarget?
    /// The drawers that are up, bottom to top. Only the topmost presents the Share pane
    /// (the tab view does when there are none): presenting from underneath closes the
    /// drawer on top.
    var shareHosts: [UUID] = []
    /// The streaming service's address, from app-config (fetched once, when a night
    /// first goes live).
    var streamingURL: URL?
    /// Test hook: every live-logging request fails as if the phone had no signal
    /// (-CeolStartOffline YES starts that way; -CeolTestHooks YES shows a switch on a night).
    var simulatedOffline: Bool = {
        #if DEBUG
            UserDefaults.standard.bool(forKey: "CeolStartOffline")
        #else
            false
        #endif
    }()
    static var testHooks: Bool {
        #if DEBUG
            UserDefaults.standard.bool(forKey: "CeolTestHooks")
        #else
            false
        #endif
    }
    /// A night is being logged: the tab bar gives way to the composer.
    var editingNight = false
    /// A night being recorded and listened to (spec 053): the mini bar over the tabs,
    /// the meter when it's opened. One at a time.
    var recorder: NightRecorder?

    /// The listening service. A debug build can point elsewhere with
    /// `-CeolListenURL ws://127.0.0.1:8440/listen`.
    static var listenURL: URL {
        #if DEBUG
            if let s = UserDefaults.standard.string(forKey: "CeolListenURL"), let url = URL(string: s) { return url }
        #endif
        return URL(string: "wss://ceol-listen.onrender.com/listen")!
    }

    /// The recordings on this phone, and their uploads (RecordingStore).
    let recordings = RecordingStore()
    /// The file the phone decides from when it listens offline, kept current.
    let deciderData = DeciderRefresher()

    /// Start recording a night (stopping any other first), and open the meter.
    func startRecording(instanceID: Int, title: String) {
        stopRecording()
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        let id = "night-\(instanceID)-\(stamp)"
        recordings.begin(id: id, instanceID: instanceID, title: title)
        let r = NightRecorder(instanceID: instanceID, title: title, recordingID: id,
                              fileURL: recordings.dir.appending(path: "\(id).caf"),
                              meterLogURL: recordings.meterLog(id),
                              listenURL: Self.listenURL, token: auth.store.token(), app: self)
        recorder = r
        r.showingMeter = true
        Task { await r.start() }
    }

    /// Stop, keep the file, and send it up (RecordingStore.upload).
    func stopRecording() {
        guard let r = recorder else { return }
        r.stop()
        recorder = nil
        recordings.finish(id: r.recordingID)
        Task { await recordings.upload(r.recordingID) }
    }

    /// A session, in the Sessions tab.
    func openSession(path: String, name: String) {
        sessionsPath = [.session(path: path, name: name)]
        tab = .sessions
    }

    /// A night, in the Sessions tab, on top of its session so Back goes there.
    func openNight(id: Int, title: String, sessionPath: String?, sessionName: String) {
        var stack: [Route] = []
        if let sessionPath { stack.append(.session(path: sessionPath, name: sessionName)) }
        stack.append(.night(id: id, title: title))
        sessionsPath = stack
        tab = .sessions
    }

    /// Your tunes, filtered to one status.
    func openTunes(status: MyTunesRules.Status?) {
        tunesStatus = status
        tab = .tunes
    }
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
            if UserDefaults.standard.bool(forKey: "CeolResetSession") {
                try? auth.store.setToken(nil)
                NightStore.clearAll()
            }
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
        // a recording's upload left half-way when the app last went away
        recordings.resume(app: self)
        deciderData.start(app: self)
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
        NightStore.clearAll()
        user = nil
        phase = .signedOut
    }

    /// The account is gone (AuthService.deleteAccount already forgot the token).
    func accountDeleted() {
        NightStore.clearAll()
        user = nil
        notice = "Your account has been deleted."
        phase = .signedOut
    }
}
