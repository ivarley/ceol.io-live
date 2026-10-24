// A page's link, opened as a Universal Link (spec 052 A7): the app shows the page
// itself rather than coming forward and doing nothing.
//
//   https://ceol.app/sessions/austin/mueller            a session (or a town, a festival)
//   https://ceol.app/sessions/austin/mueller/2026-10-03 a night, by its date or its id
//   https://ceol.app/live/instances/499                 a night, by its id
//   https://ceol.app/sessions                           the Sessions tab
//   https://ceol.app/my-tunes                           the Tunes tab
//   https://ceol.app/me                                 the Me tab
//
// What a site path is (a session, a night, a festival's picker, a town) is the
// server's call — `GET /api/resolve?path=` applies web_routes.session_handler's rules —
// so the app carries the path over and asks. The one query parameter it reads is
// `?highlight=<session_instance_tune_id>`, which on the web scrolls a night's log to
// that record and flashes it (a tune's play history links this way). `?tune=<id>`,
// which the web treats as "log this tune here", is deliberately ignored: a tapped
// link should never log a tune. The hosts are AuthLink's.

import Foundation

public struct PageLink: Equatable, Sendable {
    public enum Destination: Equatable, Sendable {
        /// A path under /sessions/ or /live/instances/, for /api/resolve to name.
        case site(path: String)
        case sessions
        case myTunes
        case me
    }

    public let destination: Destination
    /// A record in a night's log to scroll to and flash: ?highlight=<session_instance_tune_id>.
    public let highlight: Int?

    public init(destination: Destination, highlight: Int? = nil) {
        self.destination = destination
        self.highlight = highlight
    }

    /// The page a URL is, or nil when it is some other page (the home page, help, a
    /// sign-in link). `extraHosts` admits a development server.
    public init?(_ url: URL, extraHosts: Set<String> = []) {
        guard let host = url.host()?.lowercased(), AuthLink.hosts.contains(host) || extraHosts.contains(host) else {
            return nil
        }
        let parts = url.pathComponents.filter { $0 != "/" }
        guard let first = parts.first else { return nil }
        switch first {
        case "sessions" where parts.count == 1:
            destination = .sessions
        case "sessions":
            destination = .site(path: "/" + parts.joined(separator: "/"))
        case "live" where parts.count == 3 && parts[1] == "instances" && Int(parts[2]) != nil:
            destination = .site(path: "/" + parts.joined(separator: "/"))
        case "my-tunes" where parts.count == 1:
            destination = .myTunes
        case "me" where parts.count == 1:
            destination = .me
        default:
            return nil
        }
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        highlight = items.first { $0.name == "highlight" }?.value.flatMap { Int($0) }.flatMap { $0 > 0 ? $0 : nil }
    }
}
