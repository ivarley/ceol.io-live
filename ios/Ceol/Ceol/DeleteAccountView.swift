// Delete Account on Me (spec 054), the app's twin of the web's /me dialog: the same
// words, and the same typed-email confirmation, which the server checks again. App
// Store review requires this in any app that lets people sign up.

import CeolDesign
import CeolSession
import SwiftUI

struct DeleteAccountView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let email: String

    @State private var typed = ""
    @State private var busy = false
    @State private var error: String?

    private var matches: Bool {
        typed.trimmingCharacters(in: .whitespaces).lowercased() == email.lowercased()
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("This deletes your login, your tune list and instruments, and your contact details, straight away. It can't be undone.")
                    Text("Your name stays on the sessions you were part of, as it would for anyone a session admin adds, and the tunes logged at those sessions stay in their logs.")
                        .foregroundStyle(CeolTokens.textMuted)
                }
                Section {
                    TextField(email, text: $typed)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .accessibilityIdentifier("delete.email")
                } header: {
                    Text("Type \(email) to confirm")
                }
                Section {
                    Button(role: .destructive) {
                        Task { await delete() }
                    } label: {
                        HStack {
                            Text("Delete account")
                            if busy { Spacer(); ProgressView() }
                        }
                    }
                    .disabled(!matches || busy)
                    .accessibilityIdentifier("delete.confirm")
                }
                if let error {
                    Section { Text(error).foregroundStyle(CeolTokens.danger) }
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
            .navigationTitle("Delete your account?")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
        }
    }

    private func delete() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            try await model.auth.deleteAccount(confirmEmail: typed.trimmingCharacters(in: .whitespaces))
            dismiss()
            model.accountDeleted()
        } catch let f as AuthFailure {
            error = f.message
        } catch {
            self.error = tr("Couldn't reach Ceol, so nothing was deleted. Check your connection and try again.")
        }
    }
}
