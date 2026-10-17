// The app without signing in (spec 060): reading is open, and changing things or
// keeping things of your own needs an account. A guest's Home is a short welcome whose
// links open the screens they name; wherever an account is needed, a prompt opens the
// sign-in sheet (AppModel.askToSignIn).
//
// i18n-converted (spec 057).

import CeolDesign
import SwiftUI

/// A guest's Home: what Ceol is, and links into it.
struct GuestHomeView: View {
    @Environment(AppModel.self) private var model

    /// The welcome, with its links as markdown so the Irish can place them where its own
    /// word order puts them. Each link is a `ceol-guest:` address `open` reads.
    private var welcome: AttributedString {
        let text = tr("Welcome to Ceol, an app for traditional Irish music. You can use the [Listen](ceol-guest:listen) feature to figure out what tune you're hearing, and browse [tunes](ceol-guest:tunes) and [session logs](ceol-guest:sessions). To track your own tunes or edit session logs, [sign in](ceol-guest:signin) or [create a free account](ceol-guest:signin).")
        var a = (try? AttributedString(markdown: text)) ?? AttributedString(text)
        for run in a.runs where run.link != nil {
            a[run.range].foregroundColor = CeolTokens.primary
            a[run.range].underlineStyle = .single
        }
        return a
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 32) {
                    Text(welcome)
                        .font(.ceol(size: 24, relativeTo: .title3))
                        .lineSpacing(6)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(CeolTokens.textColor)
                        .accessibilityIdentifier("home.welcome")
                    Button { model.askToSignIn() } label: {
                        Text("Sign in or create an account")
                            .font(.ceol(size: 17, weight: .semibold))
                            .frame(maxWidth: .infinity, minHeight: 50)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(CeolTokens.primary)
                    .accessibilityIdentifier("home.signIn")
                }
                .padding(24)
            }
            // In the middle of the screen, not hanging from the top; scrolls only when
            // large text makes it taller than the screen.
            .defaultScrollAnchor(.center)
            .scrollBounceBehavior(.basedOnSize)
            .background(CeolTokens.bgColor)
            .ceolRootBar(tr("Home"), sharePath: "/")
            .environment(\.openURL, OpenURLAction { url in
                open(url)
                return .handled
            })
        }
    }

    private func open(_ url: URL) {
        guard url.scheme == "ceol-guest" else { return }
        switch url.absoluteString.dropFirst("ceol-guest:".count) {
        case "listen": model.tab = .listen
        case "tunes": model.tab = .tunes
        case "sessions": model.tab = .sessions
        default: model.askToSignIn()
        }
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
