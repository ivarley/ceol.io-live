// Which screen the app is on, and the sign-in transitions between them (spec 052 A1,
// plan Phase 2). The API work is CeolSession's AuthService; this decides what the
// app shows around it.
//
//   launching       splash, while app-config and the stored token are checked
//   upgradeRequired the server says this build is too old (MIN_CLIENT_VERSION_IOS)
//   guest           the tabs, signed out (spec 060): reading is open; the sign-in
//                   sheet (`signingIn`) opens from whatever needs an account
//   profileSetup    signed in, but name or location missing (auth.needs_profile_setup)
//   signedIn        the four tabs

import CeolAPI
import CeolSession
import CeolLogic
import Foundation
import Observation
import OpenAPIRuntime
import OpenAPIURLSession

@Observable
final class AppModel {
    enum Phase: Equatable {
        case launching, upgradeRequired, guest, profileSetup, signedIn
    }

    /// Signed out, using the app as a guest (spec 060).
    var isGuest: Bool { phase == .guest }
    /// The sign-in sheet is up, over wherever you were.
    var signingIn = false
    /// Counts the times the tabs were started over (signing out, an account deleted):
    /// the tab view's identity, so nothing of the account stays on screen.
    private(set) var tabsGeneration = 0

    /// Something that needs an account was tapped: the sign-in sheet.
    func askToSignIn() {
        signingIn = true
    }

    private(set) var phase: Phase = .launching
    private(set) var user: User?
    /// The interface language, "en" or "ga" (spec 057): the profile's, remembered across
    /// launches. The app root's locale follows it.
    private(set) var language: String = AppLanguage.code
    private var started = false
    /// The tab on screen; a screen can move you to another (Home's "See all" -> Tunes).
    var tab: AppTab = .home
    /// The Sessions tab's stack. Home opens sessions and nights here, in the Sessions
    /// tab, which is where they live (as on the web, where they are /sessions pages).
    var sessionsPath: [Route] = []
    /// The Tunes tab's status filter (nil: All). Home's Learning / To Learn boxes set it.
    var tunesStatus: MyTunesRules.Status?
    /// Counts the taps on a tab's icon while already in it: each one asks that tab to
    /// come back to its top-level page (returnToRoot). A tab's root watches its count
    /// and closes whatever it has open over itself.
    private(set) var rootRequests: [AppTab: Int] = [:]

    /// The tab's icon, tapped while in it: back to the top of that section. Sessions
    /// pops its stack here; each tab's root closes its own sheets on `rootRequests`.
    func returnToRoot(_ tab: AppTab) {
        if tab == .sessions { sessionsPath = [] }
        rootRequests[tab, default: 0] += 1
    }

    /// The Share pane, when open (PageMenu sets it; ceolSharePane shows it).
    var sharing: ShareTarget?
    /// The report form, when open (Report in a "⋯" menu; shown where Share is).
    var reporting: ReportTarget?
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
    }() {
        didSet { offlineFlag.value = simulatedOffline }
    }
    /// The same switch, readable from the API client's middleware off the main actor.
    /// One per model, not shared: the tests build several models at once, and one
    /// pretending to have no signal must not cut another off.
    private let offlineFlag: OfflineFlag
    static var testHooks: Bool {
        #if DEBUG
            UserDefaults.standard.bool(forKey: "CeolTestHooks")
        #else
            false
        #endif
    }
    /// A night is being logged: the tab bar gives way to the composer.
    var editingNight = false
    /// The listener (spec 053, 059): the Listen tab's meter, and the mini bar over the
    /// tabs while another tab is up. One at a time; logging a night's tunes or not.
    var recorder: NightRecorder?
    /// A night whose Listen button was tapped with nothing listening yet: the listen
    /// screen's start screen names it, and "Start Listening" logs to it. Nil: just listening.
    var pendingLog: (instanceID: Int, title: String)?
    /// The listen screen slid up over whatever is on screen (a night's Listen button,
    /// Home's, the mini bar). The Listen tab shows the same screen in place.
    var presentedListen: ListenPresentation?

    /// The listening service. A debug build can point elsewhere with
    /// `-CeolListenURL ws://127.0.0.1:8440/listen`.
    static var listenURL: URL {
        #if DEBUG
            if let s = UserDefaults.standard.string(forKey: "CeolListenURL"), let url = URL(string: s) { return url }
        #endif
        return URL(string: "wss://ceol-listen.onrender.com/listen")!
    }

    /// The nights open now, one model each, shared by whoever has it open (the night's
    /// screen, the recorder's "this is it"): two copies of one log would each keep their
    /// own offline queue, and with no stream to carry changes between them a tune logged
    /// by one would not show in the other (and each would save over the other's).
    @ObservationIgnored private var openNights: [Int: (model: NightModel, users: Int)] = [:]
    /// The payloads kept on the phone, one Resource per key (Payloads.swift).
    @ObservationIgnored var resources: [String: Any] = [:]
    /// Fetches them ahead (Prefetcher), and sends tunebook changes made with no signal (TuneQueue).
    let prefetcher = Prefetcher()
    let tuneQueue = TuneQueue()

    /// Whether a night's model is open (its own saves win over a prefetch).
    func isNightOpen(_ instanceID: Int) -> Bool { openNights[instanceID] != nil }

    /// The night's model, shared; started if this is the first to open it.
    func openNight(_ instanceID: Int) -> NightModel {
        if let open = openNights[instanceID] {
            openNights[instanceID] = (open.model, open.users + 1)
            return open.model
        }
        let m = NightModel(instanceID: instanceID, app: self)
        openNights[instanceID] = (m, 1)
        Task { await m.start() }
        return m
    }

    /// Done with a night's model: stopped once nobody has it open.
    func closeNight(_ model: NightModel) {
        guard let open = openNights[model.instanceID], open.model === model else {
            model.stop()
            return
        }
        if open.users <= 1 {
            openNights[model.instanceID] = nil
            model.stop()
        } else {
            // still open for the recorder: the screen's logging ends with the screen
            model.setEditing(false)
            openNights[model.instanceID] = (model, open.users - 1)
        }
    }

    /// The recordings on this phone, and their uploads (RecordingStore).
    let recordings = RecordingStore()
    /// The file the phone decides from when it listens offline, kept current.
    let deciderData = DeciderRefresher()

    /// Start listening (stopping any other first): logging the tunes to a night, which is
    /// recorded as well, or just listening, with no recording unless it's turned on.
    func startListening(logging: (instanceID: Int, title: String)?, recording: Bool? = nil) {
        stopListening()
        pendingLog = nil
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        let id = logging.map { "night-\($0.instanceID)-\(stamp)" } ?? "listen-\(stamp)"
        // the server admits system admins only (listen/service.py); everyone else listens
        // on the phone
        let place: ListenWhere = user?.isSystemAdmin == true ? .preferred : .phone
        let r = NightRecorder(logging: logging, recording: recording ?? (logging != nil), recordingID: id,
                              fileURL: recordings.dir.appending(path: "\(id).caf"),
                              meterLogURL: recordings.meterLog(id),
                              listenURL: Self.listenURL, token: auth.store.token(), listenWhere: place, app: self)
        recorder = r
        Task { await r.start() }
    }

    /// Stop; keep the recording if there is one, and send it up (RecordingStore.upload)
    /// when that option is on and it is a night's.
    func stopListening() {
        guard let r = recorder else { return }
        r.stop()
        recorder = nil
        guard r.recording else { return }
        // uploaded only with the option on; otherwise kept on the phone (Upload in the list)
        let upload = r.uploadsRecording && r.logsTo != nil
        recordings.finish(id: r.recordingID, keepOnPhone: !upload)
        if upload { Task { await recordings.upload(r.recordingID) } }
    }

    /// The listen screen, slid up (spec 059): with a night to log to (its Listen button),
    /// or none (Home, the mini bar). Already listening, a night given is logged from
    /// here on. Already on the Listen tab, nothing slides up: the screen is there.
    func openListen(logging: (instanceID: Int, title: String)? = nil) {
        if let recorder, let logging {
            recorder.startLogging(instanceID: logging.instanceID, title: logging.title)
        } else if recorder == nil {
            pendingLog = logging
        }
        if tab != .listen { presentedListen = ListenPresentation() }
    }

    /// A session, in the Sessions tab.
    func openSession(path: String, name: String) {
        sessionsPath = [.session(path: path, name: name)]
        tab = .sessions
    }

    /// A night, in the Sessions tab, on top of its session so Back goes there.
    /// `highlight`: a record of its log to scroll to and flash (a link's ?highlight=).
    func openNight(id: Int, title: String, sessionPath: String?, sessionName: String, highlight: RecordID? = nil) {
        var stack: [Route] = []
        if let sessionPath { stack.append(.session(path: sessionPath, name: sessionName)) }
        stack.append(.night(id: id, title: title, highlight: highlight))
        sessionsPath = stack
        tab = .sessions
    }

    /// A festival as a whole (its picker, or the near year), in the Sessions tab.
    func openFestival(slug: String, name: String) {
        sessionsPath = [.festival(slug: slug, name: name)]
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
    /// Why a tapped page link opened nothing (the server couldn't be reached, or the
    /// page is gone), for the root to show over whatever is on screen.
    var linkNotice: String?
    /// An emailed link is being exchanged.
    private(set) var openingLink = false

    let auth: AuthService
    /// The server the app talks to; its web pages (Help, Admin) open from here too.
    let server: URL
    /// Hosts, beyond ceol.app and ceol.io, whose sign-in links the app accepts: a development server.
    private let devHosts: Set<String>
    private var pendingLink: URL?

    /// Where the client's 401s land (UnauthorizedMiddleware): a box, because the client
    /// is built before `self` is, so the handler is hung on it at the end of init.
    private let signInWatch: SignInWatch

    init(server: URL = AppModel.serverURL, store: any TokenStore = KeychainTokenStore(),
         transport: any ClientTransport = URLSessionTransport()) {
        let watch = SignInWatch()
        let flag = OfflineFlag()
        let client = Client.ceol(
            serverURL: server, clientID: ClientID.current, token: { store.token() }, language: { AppLanguage.code },
            offline: { flag.value }, unauthorized: { _ in watch.rejected?() }, transport: transport)
        auth = AuthService(client: client, store: store)
        self.server = server
        devHosts = CeolServer.production.host() == server.host() ? [] : [server.host() ?? ""]
        signInWatch = watch
        offlineFlag = flag
        flag.value = simulatedOffline
        watch.rejected = { [weak self] in self?.signInExpired() }
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
        // Once per launch, whatever re-runs the view's task.
        guard !started else { return }
        started = true
        #if DEBUG
            // Test hooks (UI tests, manual runs): -CeolResetSession YES starts signed out
            // (Keychain items survive a reinstall on the simulator); -CeolOpenURL <url>
            // opens a URL as a tapped link would.
            if UserDefaults.standard.bool(forKey: "CeolResetSession") {
                try? auth.store.setToken(nil)
                forgetAccountData()
            }
            if let s = UserDefaults.standard.string(forKey: "CeolOpenURL"), let url = URL(string: s) { pendingLink = url }
            // -CeolTab me: start on that tab (screenshots of one screen).
            if let t = UserDefaults.standard.string(forKey: "CeolTab"),
               let start = AppTab.allCases.first(where: { "\($0)" == t })
            {
                tab = start
            }
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
                enterGuest()
            }
        } catch {
            // Can't reach the server, but a token is stored: stay signed in rather than
            // pretend the person is signed out. Screens show what they kept, and the
            // prefetcher fills in who we are once the server can be reached.
            if auth.store.token() != nil {
                phase = .signedIn
                prefetcher.start(app: self)
                tuneQueue.start(app: self)
            } else {
                enterGuest()
            }
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

    /// Signed out: the tabs, as a guest. The phone still hears tunes, so its decider
    /// file is kept current; the prefetcher and the tunebook queue are an account's.
    private func enterGuest() {
        phase = .guest
        deciderData.start(app: self)
    }

    func enter(_ user: User, next: SignedIn.Next?) {
        let wasGuest = phase == .guest
        // What the phone kept belongs to the account that was signed in when it was
        // kept. The same account back (after the sign-in ran out, say) finds it all
        // there, and its waiting changes go now; another account starts clean, so one
        // person's nights never show under another's name and one tunebook's waiting
        // changes never land in another.
        if let owner = Self.localDataOwner, owner != user.userId { forgetAccountData() }
        Self.localDataOwner = user.userId
        self.user = user
        setLanguage(user.language?.rawValue)
        phase = user.needsProfileSetup || next == .setupProfile ? .profileSetup : .signedIn
        // a recording's upload left half-way when the app last went away
        recordings.resume(app: self)
        deciderData.start(app: self)
        // the screens' payloads, ahead of their opening; changes made with no signal
        prefetcher.start(app: self)
        tuneQueue.start(app: self)
        signingIn = false
        // Signed in from the sheet: the screens behind it were fetched as a guest, so
        // fetch them again for their personal parts (your status, Join, the add buttons).
        if wasGuest { refreshKept() }
    }

    /// Fetch every payload a screen has open again.
    private func refreshKept() {
        for r in resources.values {
            if let r = r as? any Refreshing { Task { await r.refresh() } }
        }
    }

    /// Launched with no signal, the person is unknown though signed in: once the server
    /// answers, learn who they are (the prefetcher's first move).
    func restoreUser() async {
        guard user == nil, phase == .signedIn, let u = try? await auth.currentUser() else { return }
        enter(u, next: nil)
    }

    /// The app came forward: fetch what changed, send what waited.
    func appCameForward() {
        guard phase == .signedIn else { return }
        prefetcher.appCameForward()
        Task { await tuneQueue.flush() }
    }

    /// The interface language changed (sign-in, or the Me screen's setting).
    func setLanguage(_ code: String?) {
        AppLanguage.set(code)
        language = AppLanguage.code
    }

    /// Profile setup saved: reload who we are and carry on.
    func profileSaved() async {
        if let user = try? await auth.currentUser() {
            enter(user, next: nil)
        } else {
            phase = .signedIn
        }
    }

    /// A URL the app was opened with (a Universal Link, spec 052 A7). An emailed sign-in
    /// link is exchanged for a session; a page's link (a session, a night, a festival,
    /// your tunes, your page) opens that screen, the server saying what the path is
    /// (PageLink, /api/resolve). Any other link just brings the app forward. A link
    /// that arrives while launching waits for start() to finish.
    func open(_ url: URL) async {
        if phase == .launching {
            pendingLink = url
            return
        }
        if let link = AuthLink(url, extraHosts: devHosts) {
            await exchange(link)
        } else if let page = PageLink(url, extraHosts: devHosts) {
            await open(page)
        }
    }

    /// A page's link: the tab it names, or what /api/resolve says its path is.
    private func open(_ page: PageLink) async {
        switch page.destination {
        case .sessions:
            sessionsPath = []
            tab = .sessions
        case .myTunes:
            openTunes(status: nil)
        case .me:
            tab = .me
        case .site(let path):
            do {
                let r = try await auth.client.resolvePath(query: .init(path: path)).ok.body.json
                switch r.kind {
                case .instance:
                    guard let s = r.session, let i = r.instance else { return }
                    // Named as the session's own list names its nights: a festival's
                    // room by the room, any other night by its date.
                    let title = i.locationOverride ?? "\(s.name) · \(SessionsL10n.shortDate(i.date))"
                    openNight(id: i.sessionInstanceId, title: title, sessionPath: s.path, sessionName: s.name,
                              highlight: page.highlight.map(RecordID.server))
                case .session:
                    guard let s = r.session else { return }
                    openSession(path: s.path, name: s.name)
                case .place:
                    // A festival has a screen (its years); a town's page is the web's,
                    // so its link lands on the Sessions tab.
                    if let p = r.place, p.kind == .festival {
                        openFestival(slug: p.slug, name: p.name)
                    } else {
                        sessionsPath = []
                        tab = .sessions
                    }
                }
            } catch {
                linkNotice = isConnectionFailure(error)
                    ? tr("Couldn't reach Ceol to open that link. Check your connection and tap it again.")
                    : tr("That link doesn't lead anywhere now. The session or night may have been removed.")
            }
        }
    }

    /// An emailed sign-in link: exchanged for a session.
    private func exchange(_ link: AuthLink) async {
        openingLink = true
        defer { openingLink = false }
        do {
            signedIn(try await auth.exchange(link))
        } catch let failure as AuthFailure {
            linkFailed(Self.message(for: failure))
        } catch {
            linkFailed(tr("Couldn't reach Ceol to open that link. Check your connection and tap it again."))
        }
    }

    /// An emailed link that didn't sign you in: a guest sees why on the sign-in sheet.
    private func linkFailed(_ message: String) {
        linkError = message
        if phase == .guest { signingIn = true }
    }

    static func message(for failure: AuthFailure) -> String {
        switch failure.code {
        case "invalid_token":
            return tr("That link has expired or was already used. Enter your email below and we'll send a new one.")
        default:
            return failure.message
        }
    }

    // MARK: - Signing out

    func signOut() async {
        await auth.logout()
        forgetAccountData()
        startOverAsGuest()
    }

    /// The tabs from the top, as a guest: nothing of the account left on screen.
    private func startOverAsGuest() {
        sessionsPath = []
        tunesStatus = nil
        tab = .home
        tabsGeneration += 1
        enterGuest()
    }

    /// The server no longer knows the token (six weeks idle, or signed out from the
    /// web): back to being a guest, with the sign-in sheet up. Nothing the phone kept is touched — the payloads, the
    /// nights, the changes waiting to be sent — so an evening's work with no signal
    /// is not lost to a sign-in that ran out while the phone was away; it goes once
    /// the same account is signed in again (enter). The queues stop trying meanwhile:
    /// every send would be refused the same way.
    func signInExpired() {
        guard phase == .signedIn || phase == .profileSetup else { return }
        try? auth.store.setToken(nil)
        prefetcher.stop()
        tuneQueue.pause()
        user = nil
        notice = tr("Your sign-in ran out. Sign in again and the changes waiting on this phone will be sent.")
        enterGuest()
        signingIn = true
    }

    /// The account whose data is on this phone (user_id), while any is.
    private static let localDataOwnerKey = "LocalDataOwnerUserID"
    static var localDataOwner: Int? {
        get { UserDefaults.standard.object(forKey: localDataOwnerKey) as? Int }
        set {
            if let newValue { UserDefaults.standard.set(newValue, forKey: localDataOwnerKey) }
            else { UserDefaults.standard.removeObject(forKey: localDataOwnerKey) }
        }
    }

    /// The account is gone (AuthService.deleteAccount already forgot the token).
    func accountDeleted() {
        forgetAccountData()
        notice = tr("Your account has been deleted.")
        startOverAsGuest()
        signingIn = true
    }

    /// Everything kept for this account: nights, payloads, waiting tunebook changes.
    private func forgetAccountData() {
        prefetcher.stop()
        tuneQueue.stop()
        NightStore.clearAll()
        forgetPayloads()
        Self.forgetSettings()
        Self.localDataOwner = nil
        user = nil
    }

    /// Settings about this account's data (a night's tunebook filter), gone with it.
    static func forgetSettings() {
        for key in ["night.myStatus", "night.myStatusInstrument"] { UserDefaults.standard.removeObject(forKey: key) }
    }
}

/// Where the API client reports a rejected token (Client.ceol's `unauthorized`).
final class SignInWatch {
    var rejected: (() -> Void)?
}

/// A flag read from any thread (the client's middleware) and set on the main actor.
nonisolated final class OfflineFlag: @unchecked Sendable {
    private let lock = NSLock()
    private var on = false
    var value: Bool {
        get { lock.withLock { on } }
        set { lock.withLock { on = newValue } }
    }
}
