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
                .ceolBackground()
                .navigationTitle("Me")
                .toolbar {
                    if state.value != nil {
                        ToolbarItem(placement: .topBarTrailing) {
                            Button("Edit") { editing = true }.accessibilityIdentifier("me.edit")
                        }
                    }
                }
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
        List {
            Section {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(profile.firstName) \(profile.lastName)")
                        .font(.title2.weight(.semibold))
                        .foregroundStyle(CeolTokens.textColor)
                        .accessibilityIdentifier("me.name")
                    let place = [profile.city, profile.state, profile.country].filter { !$0.isEmpty }.joined(separator: ", ")
                    let line: [String] = [user.map { "@\($0.username)" }, place.isEmpty ? nil : place].compactMap { $0 }
                    if !line.isEmpty {
                        Text(line.joined(separator: "  ·  ")).font(.subheadline).foregroundStyle(CeolTokens.secondary)
                    }
                }
                .padding(.vertical, 4)
            }
            Section {
                LabeledContent("Instruments", value: profile.instruments.isEmpty ? "None yet" : profile.instruments.joined(separator: ", "))
                LabeledContent("Time zone", value: p.timezoneOptions.first { $0.value == profile.timezone }?.label ?? profile.timezone)
                if let email = user?.email { LabeledContent("Email", value: email) }
            }
            Section {
                if user?.isSystemAdmin == true {
                    Button { Task { await openWeb("/admin", needsSignIn: true) } } label: {
                        WebRow(title: "Admin", busy: opening == "/admin")
                    }
                    .disabled(opening != nil)
                    .accessibilityIdentifier("me.admin")
                }
                Button { Task { await openWeb("/help", needsSignIn: false) } } label: {
                    WebRow(title: "Help", busy: opening == "/help")
                }
                .disabled(opening != nil)
                .accessibilityIdentifier("me.help")
            } footer: {
                if user?.isSystemAdmin == true { Text("Admin opens the web, signed in.") }
            }
            Section {
                Button("Sign out", role: .destructive) { confirmSignOut = true }
                    .accessibilityIdentifier("me.signout")
            }
            // Last, and on its own. Not offered to system admins, whom the server
            // refuses: removing an admin is another admin's decision.
            if let user, let email = user.email, !user.isSystemAdmin {
                Section {
                    Button("Delete Account", role: .destructive) { deleting = true }
                        .accessibilityIdentifier("me.delete")
                }
                .sheet(isPresented: $deleting) { DeleteAccountView(email: email) }
            }
        }
        .refreshable { await load() }
    }
}

/// A row that leaves the app for a page on the web.
private struct WebRow: View {
    let title: String
    var busy = false

    var body: some View {
        HStack {
            Text(title).foregroundStyle(CeolTokens.textColor)
            Spacer()
            if busy {
                ProgressView()
            } else {
                Image(systemName: "safari").foregroundStyle(CeolTokens.secondary)
            }
        }
        .contentShape(Rectangle())
    }
}
