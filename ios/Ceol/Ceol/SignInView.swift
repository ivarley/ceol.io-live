// Email-first sign-in, as on the web (spec 013): type your address, and the server
// decides what happens next — ask for the password, or email a link (a login link for
// an account without a password, or one that creates the account). The server's own
// sentences are shown as they come, so the app and the web say the same thing.

import CeolDesign
import CeolSession
import SwiftUI

struct SignInView: View {
    @Environment(AppModel.self) private var model

    private enum Step: Equatable {
        case email
        case password(email: String)
        case sent(email: String, message: String, registration: Bool)
    }

    @State private var step: Step = .email
    @State private var email = ""
    @State private var password = ""
    @State private var busy = false
    @State private var error: String?
    /// A password login refused because the address was never confirmed.
    @State private var unverified = false
    @State private var resent = false
    @FocusState private var focused: Bool

    var body: some View {
        NavigationStack {
            Form {
                header
                if let linkError = model.linkError, step == .email {
                    Section { Text(linkError).foregroundStyle(CeolTokens.warning).accessibilityIdentifier("signin.linkError") }
                }
                switch step {
                case .email: emailStep
                case .password(let email): passwordStep(email)
                case .sent(let email, let message, let registration): sentStep(email, message, registration)
                }
                if let error {
                    Section { Text(error).foregroundStyle(CeolTokens.danger).accessibilityIdentifier("signin.error") }
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
            .disabled(busy || model.openingLink)
            .overlay { if model.openingLink { ProgressView("Signing you in…") } }
        }
    }

    private var header: some View {
        Section {
            VStack(alignment: .leading, spacing: 6) {
                Text("Ceol").font(.largeTitle.bold()).foregroundStyle(CeolTokens.primary)
                Text("The tunes you know, the sessions you play, and what gets played there.")
                    .font(.subheadline).foregroundStyle(CeolTokens.secondary)
            }
            .listRowBackground(Color.clear)
        }
    }

    // MARK: - Steps

    private var emailStep: some View {
        Section {
            TextField("Email address", text: $email)
                .textContentType(.emailAddress)
                .keyboardType(.emailAddress)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.continue)
                .focused($focused)
                .onSubmit { Task { await checkEmail() } }
                .accessibilityIdentifier("signin.email")
            Button { Task { await checkEmail() } } label: { progressLabel("Continue") }
                .disabled(email.trimmingCharacters(in: .whitespaces).isEmpty)
                .accessibilityIdentifier("signin.continue")
        } footer: {
            Text("New here? Enter your email and we'll send you a link to create your account.")
        }
        .onAppear { focused = true }
    }

    private func passwordStep(_ email: String) -> some View {
        Section {
            LabeledContent("Email", value: email)
            SecureField("Password", text: $password)
                .textContentType(.password)
                .submitLabel(.go)
                .focused($focused)
                .onSubmit { Task { await login(email) } }
                .accessibilityIdentifier("signin.password")
            Button { Task { await login(email) } } label: { progressLabel("Sign in") }
                .disabled(password.isEmpty)
                .accessibilityIdentifier("signin.submit")
            if unverified {
                Button(resent ? "Sent. Check your email." : "Send the confirmation email again") {
                    Task { await resend(email) }
                }
                .disabled(resent)
            }
            Button("Use a different email", role: .cancel) { reset() }
        }
        .onAppear { focused = true }
    }

    private func sentStep(_ email: String, _ message: String, _ registration: Bool) -> some View {
        Section {
            Label(registration ? "Check your email to create your account" : "Check your email",
                  systemImage: "envelope")
                .font(.headline)
            Text(message)
            Text("We sent it to \(email). Open the link on this iPhone and it will sign you in here.")
                .font(.footnote).foregroundStyle(CeolTokens.secondary)
            Button(resent ? "Sent again." : "Send it again") {
                Task {
                    await checkEmail(again: email)
                    resent = true
                }
            }
            .disabled(resent)
            Button("Use a different email", role: .cancel) { reset() }
        }
    }

    private func progressLabel(_ title: String) -> some View {
        HStack {
            Text(title)
            if busy { Spacer(); ProgressView() }
        }
    }

    // MARK: - Actions

    private func checkEmail(again: String? = nil) async {
        let address = again ?? email.trimmingCharacters(in: .whitespaces)
        guard !address.isEmpty else { return }
        await run {
            model.linkError = nil
            switch try await model.auth.checkEmail(address) {
            case .needsPassword(let email): step = .password(email: email)
            case .linkSent(let email, let message): step = .sent(email: email, message: message, registration: false)
            case .registrationStarted(let email, let message):
                step = .sent(email: email, message: message, registration: true)
            }
        }
    }

    private func login(_ email: String) async {
        await run {
            do {
                model.signedIn(try await model.auth.login(email: email, password: password))
            } catch let f as AuthFailure where f.code == "email_not_verified" {
                unverified = true
                throw f
            }
        }
    }

    private func resend(_ email: String) async {
        await run {
            try await model.auth.resendVerification(email: email)
            resent = true
        }
    }

    private func reset() {
        step = .email
        password = ""
        error = nil
        unverified = false
        resent = false
    }

    /// Runs an action with the busy state, showing a refusal in the server's words and
    /// anything else as a connection problem.
    private func run(_ action: () async throws -> Void) async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            try await action()
        } catch let f as AuthFailure {
            error = AppModel.message(for: f)
        } catch {
            self.error = "Couldn't reach Ceol. Check your connection and try again."
        }
    }
}
