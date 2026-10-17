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
    /// The server's answer to "Forgot your password?".
    @State private var resetSent: String?
    @FocusState private var focused: Bool

    var body: some View {
        NavigationStack {
            Form {
                header
                if let notice = model.notice, step == .email {
                    Section { Text(notice).accessibilityIdentifier("signin.notice") }
                }
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
            VStack(alignment: .leading, spacing: 10) {
                // The same wordmark as the web's (static/images/logo3-1.png).
                Image("Wordmark").resizable().scaledToFit()
                    .frame(height: 56)
                    .accessibilityLabel(Text(verbatim: "Ceol"))
                Text("The tunes you know, the sessions you play, and what gets played there.")
                    .font(.ceol(.subheadline)).foregroundStyle(CeolTokens.textMuted)
            }
            .listRowBackground(Color.clear)
        }
    }

    // MARK: - Steps

    @ViewBuilder
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
        }
        .onAppear { focused = true }
        Section {
            primaryButton(tr("Continue"), id: "signin.continue",
                          disabled: email.trimmingCharacters(in: .whitespaces).isEmpty) {
                await checkEmail()
            }
        } footer: {
            Text("New here? Enter your email and we'll send you a link to create your account.")
        }
    }

    @ViewBuilder
    private func passwordStep(_ email: String) -> some View {
        Section {
            LabeledContent("Email", value: email)
            SecureField("Password", text: $password)
                .textContentType(.password)
                .submitLabel(.go)
                .focused($focused)
                .onSubmit { Task { await login(email) } }
                .accessibilityIdentifier("signin.password")
        }
        .onAppear { focused = true }
        Section {
            primaryButton(tr("Sign in"), id: "signin.submit", disabled: password.isEmpty) {
                await login(email)
            }
        }
        Section {
            if unverified {
                Button(resent ? tr("Sent. Check your email.") : tr("Send the confirmation email again")) {
                    Task { await resend(email) }
                }
                .disabled(resent)
            }
            Button("Email me a sign-in link instead") {
                Task { await checkEmail(again: email, link: true) }
            }
            .accessibilityIdentifier("signin.sendLink")
            if let resetSent {
                Text(resetSent).foregroundStyle(CeolTokens.textMuted).accessibilityIdentifier("signin.resetSent")
            } else {
                Button("Forgot your password?") { Task { await forgotPassword(email) } }
                    .accessibilityIdentifier("signin.forgot")
            }
            Button("Use a different email", role: .cancel) { reset() }
        }
    }

    private func sentStep(_ email: String, _ message: String, _ registration: Bool) -> some View {
        Section {
            Label(registration ? tr("Check your email to create your account") : tr("Check your email"),
                  systemImage: "envelope")
                .font(.ceol(.headline))
            Text(message)
            Text("We sent it to \(email). Open the link on this iPhone and it will sign you in here.")
                .font(.ceol(.footnote)).foregroundStyle(CeolTokens.textMuted)
            Button(resent ? tr("Sent again.") : tr("Send it again")) {
                Task {
                    // link: a password account that asked for a link gets another, not the
                    // password step; for the others the answer is the same as before.
                    await checkEmail(again: email, link: true)
                    resent = true
                }
            }
            .disabled(resent)
            Button("Use a different email", role: .cancel) { reset() }
        }
    }

    /// The step's main action: a filled button, so it doesn't read as another field.
    private func primaryButton(_ title: String, id: String, disabled: Bool,
                               action: @escaping () async -> Void) -> some View {
        Button { Task { await action() } } label: {
            ZStack {
                Text(title).opacity(busy ? 0 : 1)
                if busy { ProgressView().tint(.white) }
            }
            .font(.ceol(.headline))
            .frame(maxWidth: .infinity, minHeight: 34)
        }
        .buttonStyle(.borderedProminent)
        .tint(CeolTokens.primary)
        .disabled(disabled)
        .listRowBackground(Color.clear)
        .listRowInsets(EdgeInsets())
        .accessibilityIdentifier(id)
    }

    // MARK: - Actions

    private func checkEmail(again: String? = nil, link: Bool = false) async {
        let address = again ?? email.trimmingCharacters(in: .whitespaces)
        guard !address.isEmpty else { return }
        await run {
            model.linkError = nil
            model.notice = nil
            switch try await model.auth.checkEmail(address, link: link) {
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

    private func forgotPassword(_ email: String) async {
        await run {
            resetSent = try await model.auth.forgotPassword(email: email)
                ?? tr("If an account with that email exists, password reset instructions have been sent.")
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
        resetSent = nil
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
            self.error = tr("Couldn't reach Ceol. Check your connection and try again.")
        }
    }
}
