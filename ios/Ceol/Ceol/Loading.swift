// Loading, loaded, or failed — one pattern for every screen that fetches (the web's
// d66a9e6: a failure says what went wrong and offers Retry, and never looks like an
// empty list). Screens also pull to refresh.

import CeolDesign
import SwiftUI

enum LoadState<Value> {
    case loading
    case loaded(Value)
    case failed(String)

    var value: Value? {
        if case .loaded(let v) = self { return v }
        return nil
    }
}

/// Shows `content` once loaded; a spinner, or the failure with Retry, before that.
struct Loaded<Value, Content: View>: View {
    let state: LoadState<Value>
    let retry: () async -> Void
    @ViewBuilder let content: (Value) -> Content

    var body: some View {
        switch state {
        case .loading:
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed(let message):
            ContentUnavailableView {
                Label("Couldn't load this", systemImage: "wifi.exclamationmark")
            } description: {
                Text(message)
            } actions: {
                Button("Retry") { Task { await retry() } }.buttonStyle(.bordered)
            }
        case .loaded(let value):
            content(value)
        }
    }
}

/// What a screen says when a fetch fails. The server's own sentence when it sent one.
func loadFailureMessage(_ error: Error) -> String {
    if let url = error as? URLError, url.code == .notConnectedToInternet || url.code == .networkConnectionLost {
        return tr("You're offline. Check your connection, then try again.")
    }
    return tr("Something went wrong reaching Ceol. Try again in a moment.")
}

extension View {
    /// The app's dark background behind lists and forms.
    func ceolBackground() -> some View {
        scrollContentBackground(.hidden).background(CeolTokens.bgColor)
    }
}
