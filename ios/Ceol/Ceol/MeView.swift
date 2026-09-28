// The Me tab (plan Phase 3d), the app's twin of /me: your profile, then the account
// rows (Admin for system admins, Help), then Sign out, and Delete Account last and on
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

    private func web(_ path: String) -> URL { model.server.appending(path: path) }

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
                    Link(destination: web("admin")) { WebRow(title: "Admin") }
                }
                Link(destination: web("help")) { WebRow(title: "Help") }
            } footer: {
                if user?.isSystemAdmin == true { Text("Admin opens on the web.") }
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

    var body: some View {
        HStack {
            Text(title).foregroundStyle(CeolTokens.textColor)
            Spacer()
            Image(systemName: "arrow.up.right.square").foregroundStyle(CeolTokens.secondary)
        }
    }
}
