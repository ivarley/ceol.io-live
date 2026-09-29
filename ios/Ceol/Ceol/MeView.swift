// The Me tab (plan Phase 3d), the app's twin of /me: your profile, then the account
// rows (Admin for system admins, Help — the web, in a Safari view), then Sign out, and Delete Account last and on
// its own. Created / last login stay on the web; nobody checks when they signed up.
//
// Edit opens the profile form from first sign-in (ProfileSetupView, editing).

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

struct MeView: View {
    @Environment(AppModel.self) private var model
    @State private var state: LoadState<Profile> = .loading
    @State private var editing = false
    @State private var confirmSignOut = false
    @State private var deleting = false
    @State private var page: WebPage?
    @State private var opening: String?
    @State private var webFailure: String?

    var body: some View {
        NavigationStack {
            Loaded(state: state, retry: load) { p in list(p) }
                .background(CeolTokens.bgColor)
                .ceolRootBar("Me")
                .sheet(isPresented: $editing) {
                    ProfileSetupView(editing: true) { Task { await load() } }
                }
                .sheet(item: $page) { SafariView(url: $0.url).ignoresSafeArea() }
                .alert("Couldn't open that page", isPresented: Binding(get: { webFailure != nil }, set: { if !$0 { webFailure = nil } })) {
                    Button("OK") {}
                } message: {
                    Text(webFailure ?? "")
                }
                .confirmationDialog("Sign out of Ceol on this iPhone?", isPresented: $confirmSignOut, titleVisibility: .visible) {
                    Button("Sign out", role: .destructive) { Task { await model.signOut() } }
                }
                .task { if state.value == nil { await load() } }
        }
    }

    private func load() async {
        do {
            state = .loaded(try await model.auth.profile())
        } catch {
            if state.value == nil { state = .failed(loadFailureMessage(error)) }
        }
    }

    /// A web page, signed in: mint the one-time link, then open it. The handoff also
    /// tells the web it is inside the app, so it leaves out its own tab bar. A public
    /// page (Help) still opens, plainly, when the handoff can't be made.
    private func openWeb(_ path: String, needsSignIn: Bool) async {
        opening = path
        defer { opening = nil }
        do {
            page = WebPage(url: try await model.auth.webSession(next: path))
        } catch where !needsSignIn {
            page = WebPage(url: model.webURL(path))
        } catch let f as AuthFailure {
            webFailure = f.message
        } catch {
            webFailure = "Couldn't reach Ceol. Check your connection and try again."
        }
    }

    @ViewBuilder private func list(_ p: Profile) -> some View {
        let profile = p.profile
        let user = model.user
        let place = [profile.city, profile.state, profile.country].filter { !$0.isEmpty }.joined(separator: ", ")
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // The web's identity header: initials, name and role, handle and place, Edit.
                HStack(alignment: .center, spacing: 16) {
                    InitialsAvatar(first: profile.firstName, last: profile.lastName)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 10) {
                            Text("\(profile.firstName) \(profile.lastName)")
                                .font(.ceol(size: 24, weight: .semibold, relativeTo: .title2))
                                .foregroundStyle(CeolTokens.textColor)
                                .accessibilityIdentifier("me.name")
                            if user?.isSystemAdmin == true {
                                Text("ADMIN").font(.ceolItalic(size: 12)).tracking(0.8)
                                    .padding(.horizontal, 10).padding(.vertical, 3)
                                    .background(CeolTokens.primaryFill, in: Capsule())
                                    .foregroundStyle(.white)
                            }
                        }
                        let line = [user.map { "@\($0.username)" }, place.isEmpty ? nil : place].compactMap { $0 }
                        if !line.isEmpty {
                            Text(line.joined(separator: " · ")).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                        }
                    }
                    Spacer(minLength: 4)
                    Button("Edit") { editing = true }
                        .font(.ceol(size: 17, weight: .medium)).foregroundStyle(CeolTokens.primary)
                        .accessibilityIdentifier("me.edit")
                }
                KitGroup {
                    KitRow("Instruments", value: profile.instruments.isEmpty ? "None yet" : profile.instruments.joined(separator: ", "),
                           muted: profile.instruments.isEmpty)
                    KitRow("Location", value: place.isEmpty ? "Not provided" : place, muted: place.isEmpty)
                }
                KitGroup(title: "Account") {
                    if let user { KitRow("Username", value: user.username) }
                    if let email = user?.email { KitRow("Email", value: email) }
                    KitRow("Time zone", value: shortZone(p))
                }
                KitGroup {
                    if user?.isSystemAdmin == true {
                        Button { Task { await openWeb("/admin", needsSignIn: true) } } label: {
                            KitRow(label: "Admin") { WebMark(busy: opening == "/admin") }
                        }
                        .buttonStyle(.plain)
                        .disabled(opening != nil)
                        .accessibilityIdentifier("me.admin")
                    }
                    Button { Task { await openWeb("/help", needsSignIn: false) } } label: {
                        KitRow(label: "Help") { WebMark(busy: opening == "/help") }
                    }
                    .buttonStyle(.plain)
                    .disabled(opening != nil)
                    .accessibilityIdentifier("me.help")
                    Button { confirmSignOut = true } label: {
                        KitRow(label: "Log Out", labelColor: CeolTokens.danger) { EmptyView() }
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("me.signout")
                    .accessibilityLabel("Sign out")
                }
                // Last, and on its own. Not offered to system admins, whom the server
                // refuses: removing an admin is another admin's decision.
                if let user, let email = user.email, !user.isSystemAdmin {
                    KitGroup {
                        Button { deleting = true } label: {
                            KitRow(label: "Delete Account", labelColor: CeolTokens.danger) { EmptyView() }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("me.delete")
                    }
                    .sheet(isPresented: $deleting) { DeleteAccountView(email: email) }
                }
            }
            .padding(20)
        }
        .refreshable { await load() }
    }

    /// "US Central" from the option "US Central (UTC-05:00)", as the web's row shows it.
    private func shortZone(_ p: Profile) -> String {
        let label = p.timezoneOptions.first { $0.value == p.profile.timezone }?.label ?? p.profile.timezone
        return label.components(separatedBy: " (").first ?? label
    }
}

/// Opens on the web: a Safari mark, or a spinner while the link is made.
private struct WebMark: View {
    let busy: Bool

    var body: some View {
        if busy {
            ProgressView()
        } else {
            Image(systemName: "chevron.right").foregroundStyle(CeolTokens.textMuted)
        }
    }
}
