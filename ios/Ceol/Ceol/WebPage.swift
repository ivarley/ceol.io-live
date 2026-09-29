// The web inside the app (plan Phase 4b): what isn't native (Admin, Help) opens in a
// Safari view rather than leaving for Safari. Admin needs you signed in, so it opens
// through a one-time handoff link (POST /api/auth/web-session); the Safari view keeps
// its own cookies, so the web stays signed in there afterwards.

import CeolDesign
import SafariServices
import SwiftUI

/// A page to show in the Safari view.
struct WebPage: Identifiable {
    let url: URL
    var id: URL { url }
}

struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let vc = SFSafariViewController(url: url)
        vc.preferredControlTintColor = UIColor(CeolTokens.primary)
        vc.dismissButtonStyle = .done
        return vc
    }

    func updateUIViewController(_ vc: SFSafariViewController, context: Context) {}
}

extension AppModel {
    /// The site's own address for `path` ("/sessions/austin/mueller").
    func webURL(_ path: String) -> URL {
        // Resolved, not appended: a path may carry a query ("/my-tunes?status=learning"),
        // whose "?" appending(path:) would escape.
        URL(string: path.hasPrefix("/") ? path : "/" + path, relativeTo: server)?.absoluteURL ?? server
    }
}
