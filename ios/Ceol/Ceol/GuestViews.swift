// The app without signing in (spec 060): reading is open, and changing things or
// keeping things of your own needs an account. A guest's Home is a short welcome and a
// button into each part of the app; wherever an account is needed, a prompt opens the
// sign-in sheet (AppModel.askToSignIn).
//
// i18n-converted (spec 057).

import CeolDesign
import SwiftUI

/// A guest's Home: what Ceol is, and a button into each part of it.
struct GuestHomeView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    Text("Welcome to Ceol, an app\nfor traditional Irish music.")
                        .font(.ceol(size: 24, relativeTo: .title3))
                        .lineSpacing(6)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(CeolTokens.textColor)
                        .frame(maxWidth: .infinity)
                        .padding(.bottom, 18)
                        .accessibilityIdentifier("home.welcome")
                    GuestHomeButton(title: tr("Listen to identify tunes"), id: "home.listen") { model.tab = .listen }
                    GuestHomeButton(title: tr("Find popular tunes"), id: "home.tunes") { model.tab = .tunes }
                    GuestHomeButton(title: tr("Browse session logs"), id: "home.sessions") { model.tab = .sessions }
                    GuestHomeButton(title: tr("Sign in or create a free account"), prominent: true, id: "home.signIn") {
                        model.askToSignIn()
                    }
                    .padding(.top, 10)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 28)
            }
            .scrollBounceBehavior(.basedOnSize)
            .background(CeolTokens.bgColor)
            .ceolRootBar(tr("Home"), sharePath: "/")
        }
    }
}

/// One of the guest Home's buttons: white on black with a green outline, or, for
/// signing in, white on the green fill.
struct GuestHomeButton: View {
    let title: String
    var prominent = false
    let id: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.ceol(size: 17, weight: .semibold))
                .multilineTextAlignment(.center)
                .foregroundStyle(.white)
                .padding(.horizontal, 16)
                .frame(maxWidth: .infinity, minHeight: 50)
                .background(prominent ? CeolTokens.primaryFill : .black, in: Capsule())
                .overlay(Capsule().strokeBorder(prominent ? .clear : CeolTokens.primary, lineWidth: 1.5))
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }
}

/// Where a control that needs an account would be, for a guest: a line that opens the
/// sign-in sheet.
struct SignInPrompt: View {
    @Environment(AppModel.self) private var model
    let text: String
    let id: String

    var body: some View {
        Button { model.askToSignIn() } label: {
            Label(text, systemImage: "person.crop.circle")
                .font(.ceol(size: 16, weight: .semibold))
                .foregroundStyle(CeolTokens.primary)
                .frame(maxWidth: .infinity, minHeight: 46)
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.primary.opacity(0.6), lineWidth: 1))
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }
}
