# 058: Move to ceol.app

**Date:** 2026-10-07
**Status:** Phase 0 BUILT and deployed 2026-10-16 (`domains.py`, `templates/moved_banner.html` (originally a moved page, replaced by a redirect and banner on 2026-10-16), `static/retired-sw.js`;
tests in `tests/unit/test_domains_058.py`). Phase 1 mostly done 2026-10-16: ceol.app, www.ceol.app and
streaming.ceol.app answer through Cloudflare; the Render settings are set (`SESSION_COOKIE_DOMAINS`,
`MOVE_TO_HOST`, `MOVE_FROM_HOSTS`, the streaming origins); SendGrid sends from ceol.app; the iOS app accepts
ceol.app links (not yet in a TestFlight build). Checked: sign-in, the `.ceol.app` cookie reaching the streaming
sidecar, the offline workers, the live logger's streaming address, the segmenter, and the retired worker
taking over from an old one in Chrome. The S3 upload rule (bucket `ceol-io-recordings`) allows ceol.app
(2026-10-16; checked with a preflight from each origin). Still open in Phase 1: the phone's universal links. Phases 2-4 to do.

## Why

Ceol has two domains: `ceol.io` (where the app lives today) and `ceol.app` (unused, already
on Cloudflare's nameservers). This spec makes `ceol.app` the primary domain and turns
`ceol.io` into a redirect.

- `ceol.app` says what the thing is. `.io` reads as a developer tool.
- `.io` is the country code of the British Indian Ocean Territory, which the UK agreed in
  2024 to hand to Mauritius. What becomes of the domain is not settled. A generic top-level
  domain has no such question hanging over it.
- The iOS app is on TestFlight with one user (the product owner). The App Store listing,
  support and privacy URLs and associated domains have not been published, so this is the
  cheapest time to move. **Finish the move before submitting the app for App Store review.**

Two alternatives were considered and rejected:
- *ceol.app as a brochure for the iOS app.* The app is a companion to the web, not a
  separate product, and a second site is a second thing to keep in two languages. A page
  on the main site does the same job.
- *Both domains serving the site.* Login cookies are per host, so people would be signed in
  on one and signed out on the other; search engines would see two copies of every page.

## Decisions

Made by the product owner, 2026-10-07.

- `ceol.app` is the canonical host. `www.ceol.app` redirects to it.
- `ceol.io` and `www.ceol.io` send visitors to the same path on `ceol.app`: first through
  an "update your bookmarks" page, later by a plain redirect (§The switch).
- When to let `ceol.io` go is decided later, from how much traffic still arrives there
  (§Counting ceol.io traffic).
- The product is called **"Ceol"** in the interface, not "ceol.io" or "ceol.app", so the
  name doesn't change again if the domain does.
- Email moves to `ceol.app` at the same time as the web. The `ceol.app` mail setup is
  built and tested before the switch.
- **No effort goes into carrying anything across.** Changes queued offline on `ceol.io`
  are dropped, and everyone signs in again on `ceol.app`. The site has few users; they
  get an email beforehand. Older iOS builds are not supported (only the product owner has
  the app).
- Nothing printed or posted points at `ceol.io`.
- Nothing about the data changes: paths, ids, tokens and the database are host-independent.

## What depends on the host today

Found by searching the repo for `ceol.io` (about 260 mentions in 118 files, most of them
in specs, tests and comments). The ones that matter:

| Where | What | Change |
|---|---|---|
| `app.py` (`SESSION_COOKIE_DOMAIN`, env `.ceol.io`) | One cookie domain for every request, shared with `streaming.ceol.io` | Choose the cookie domain from the request host (§Cookies) |
| Render env `STREAMING_BASE_URL` | `https://streaming.ceol.io` | Derive from the request host (§Streaming) |
| Render env `STREAMING_ALLOWED_ORIGINS` | `ceol.io`, `www.ceol.io` | Add `https://ceol.app` |
| `scripts/configure_s3_cors.py` | Upload origins `ceol.io`, `www.ceol.io` | Add `https://ceol.app`; rerun against the bucket |
| `email_utils.py` links | Built with `url_for(..., _external=True)`, so they take the host of the request that sent them; one link hardcodes `https://ceol.io/admin/...` | Fine after the switch, since every request is on `ceol.app`; replace the hardcoded one with `url_for` |
| `email_utils.py` senders | `noreply@`, `ceol@ceol.io`, plus `unsubscribe@ceol.io` in a header (env `MAIL_*` with these defaults) | `ceol.app` senders; the `unsubscribe@` header removed (§Email) |
| `api_app_routes.py` `/api/resolve` | Turns a `ceol.io` URL into ids | Accept `ceol.app` too |
| `api_app_routes.py` AASA | Served from whichever host asks | No change; check it answers on `ceol.app` |
| `ios/Ceol/Ceol/Ceol.entitlements` | `applinks:ceol.io`, `applinks:www.ceol.io` | Replace with `applinks:ceol.app` |
| `ios/CeolKit/.../AuthLink.swift` `hosts` | `ceol.io`, `www.ceol.io` | `ceol.app` (tests in `AuthServiceTests.swift`) |
| `ios/CeolKit/.../CeolClient.swift` `production` | `https://ceol.io` | `https://ceol.app` |
| `specs/api/native-surface.yaml` | Server URL | `https://ceol.app` |
| `listen/service.py` `CEOL_API_URL` | Default `https://ceol.io` | `https://ceol.app` (and its Render env) |
| `services/tune_merge_scan_service.py` | User-Agent sent to thesession.org: `https://ceol.io; contact: ian@ceol.io` | Update the URL, and give a contact address that receives mail (`ceol.io` receives none) |
| `scripts/prod_parity/capture.py` | `BASE = "https://ceol.io"` | Update |
| Templates, help pages (both languages), `App.svelte`, `AddSessionSheet.svelte`, the iOS add-session sheet | "ceol.io" as the product name, and in example addresses like `ceol.io/sessions/austin/mueller` | §Wording |
| `static/manifest.json` | `start_url: "/"`, scoped to the origin it was installed from | Nothing to change; home-screen installs need redoing |

## Cookies

`SESSION_COOKIE_DOMAIN` is a single value today (`.ceol.io` in production) so the cookie
reaches the streaming sidecar. A browser rejects a cookie whose domain doesn't match the
page, so with the current setting **sign-in would silently fail on `ceol.app`**.

During testing (Phase 1) both hosts serve the full site, so the cookie domain is chosen
per request: `.ceol.app` on a `ceol.app` host, `.ceol.io` on a `ceol.io` host, host-only on
anything else (local dev). Flask's session cookie allows this through
`SessionInterface.get_cookie_domain`; Flask-Login's remember cookie reads
`REMEMBER_COOKIE_DOMAIN` from config when it sets the cookie, so it needs the same
treatment. The env setting becomes a list: `SESSION_COOKIE_DOMAINS=.ceol.io,.ceol.app`.
After the switch `ceol.io` sets no cookies, and `.ceol.io` can be dropped from the list.

## Streaming

Add `streaming.ceol.app` as a custom domain on the `ceol-io-streaming` service. The
sidecar's address is `STREAMING_BASE_URL` with its parent domain swapped for the one the
page was served on (`https://streaming.ceol.io` becomes `https://streaming.ceol.app`), so a
page on `ceol.app` talks to `streaming.ceol.app` and sends the `.ceol.app` cookie. A host
on no listed domain (local dev) gets `STREAMING_BASE_URL` unchanged. The same goes for the
`streaming_base_url` in `/api/app-config`.

## Phases

### Phase 0 — Make the code host-independent (no visible change)

- Cookie domain per host (§Cookies), streaming address per host (§Streaming).
- `/api/resolve` accepts both domains. (It already ignored the host; a test now says so.)
- The hardcoded admin link in `email_utils.py` built with `url_for`.
- No unsubscribe headers on mail without a personal unsubscribe link (§Email).
- The switch-day behaviour, built now and off until its settings are set (§Settings):
  the redirect and banner, the retired service worker, the 308s, the moved-redirect log line, and
  `noindex` on the new host until the switch.
- Tests: `tests/unit/test_domains_058.py`, plus the email and resolve tests.

### Phase 1 — ceol.app answers, unannounced

- **Cloudflare** (the `ceol.app` zone): DNS for the apex, `www` and `streaming`, proxied;
  SSL mode Full (strict). A redirect rule `www.ceol.app` → `https://ceol.app` keeping the
  path. Nothing has ever cached a redirect on `www.ceol.app`, so a 301 is safe there.
- **Render:** add `ceol.app` and `www.ceol.app` to `ceol.io-live`, and `streaming.ceol.app`
  to the streaming service; wait for the certificates.
- `.app` is on the browsers' HSTS preload list: plain `http://` never works on it, on any
  subdomain. Cloudflare and Render both serve HTTPS, so this only matters if a subdomain
  is ever added without a certificate.
- Set `STREAMING_ALLOWED_ORIGINS`, S3 CORS and `SESSION_COOKIE_DOMAINS` to include `ceol.app`.
- Set `MOVE_TO_HOST=ceol.app` and `MOVE_FROM_HOSTS=ceol.io,www.ceol.io`. Every response
  on `ceol.app` then carries `X-Robots-Tag: noindex`, so search engines don't index a
  second copy.
- **Email** (§Email): authenticate `ceol.app` in SendGrid and send test mail from it.
- **Test on `ceol.app`** with real accounts: password and magic-link sign-in, live logging
  with two people (the streaming feed is the thing most likely to break), offline use,
  recording upload, the segmenter, an update email, and a universal link opening a
  TestFlight build that has the `ceol.app` changes (pointed at `ceol.app` with
  `-CeolServerURL` until the switch).

### Phase 2 — Tell people

About a week before the switch, an update email to everyone (the admin email-updates page;
each recipient gets their own language): the new address and date, that they'll need to
sign in again, that anything changed offline should be synced before the date, and that a
home-screen icon needs deleting and re-adding from `ceol.app`.

### Phase 3 — The switch

1. **Email:** switch the `MAIL_*` settings to the `ceol.app` addresses.
2. **Set `MOVE_SWITCHED=true`.** The `noindex` goes, and `ceol.io` stops serving the
   site. A `before_request` in Flask (`domains.py`), on a host in `MOVE_FROM_HOSTS`:
   - **`GET`/`HEAD` of a page:** a 302 (`Cache-Control: no-store`) to the same URL on
     `ceol.app` with `ceol_moved=1` added, which turns on the banner (below).
   - **`/sw.js` and `/live/sw.js`:** a worker (`static/retired-sw.js`) that deletes its
     caches, unregisters itself and reloads the open tabs. Without this, people who visited before keep the old worker, which would
     answer navigations from its cache. These two paths must not redirect: a browser
     won't follow a redirect to another origin when updating a worker, so the old one
     would stay.
   - **Everything else** (API calls, static files, other methods): a 308 to the same path
     on `ceol.app`. Requests that needed the `ceol.io` login fail there; that's accepted.
3. **iOS:** a TestFlight build with `CeolClient.production = https://ceol.app` and the
   `.app` associated domain only.
4. **Google Search Console:** add `ceol.app` and file a change of address from `ceol.io`.
5. **Release notes** for the month, in both languages.

Cloudflare's `www.ceol.io` → `ceol.io` redirect stays. An old link then takes three
hops (`www.ceol.io` → `ceol.io` → `ceol.app?ceol_moved=1` → `ceol.app`), which is fine.

#### The "Ceol has moved" banner

The product owner chose (2026-10-16) an automatic redirect with a banner over an
interrupt page. On `ceol.app`, a page request carrying `ceol_moved=1` sets the
`ceol_moved` cookie (a year, not HttpOnly) and 302s to the same URL without the
parameter, so the address bar shows the one worth bookmarking. While the cookie is set,
every page (`templates/base.html` and `live_logging.html` include
`templates/moved_banner.html`) shows a bar across the top: "Ceol has moved · Ceol has a
new address: ceol.app. Please update your bookmarks." with the home-screen note, in the
visitor's language. Its × deletes the cookie. The bar's script also hides it when the
cookie is gone, since the service worker may serve a page snapshot taken before.

Arriving from `ceol.io` again (an old bookmark not yet updated) sets the cookie again, so
the banner comes back until the bookmark is changed.

Later, when the product owner decides the old address has had its time, the 302 becomes a
301 without the marker. Use 301 only then: Chrome keeps a 301 without cache headers
forever (the September 2026 apex/www flip showed this), so it must be final.

### Phase 4 — Wording

Where the interface names the product ("ceol.io home", "What's ceol.io?", "Session 123 is
already on ceol.io.", page titles, `apple-mobile-web-app-title`): **"Ceol"**. Where it shows
an address (`ceol.io/sessions/austin/mueller` in the help, the iOS add-session sheet's path
preview): `ceol.app/...`. This can go out with the switch or just after.

Every changed string changes in both languages (spec 057): the `.po` catalog, the Svelte
`ga/*.json` files, `ios/Ceol/i18n-ga/*.json`, and the help pages with their Irish twins.
The Irish is drafted and marked for review as usual.

## Email

Set up and tested in Phase 1, switched in Phase 3.

- **Sending:** authenticate `ceol.app` in SendGrid (domain authentication: the DKIM and
  return-path CNAMEs it generates, added in Cloudflare with the proxy off), and add a DMARC
  record (`_dmarc.ceol.app`, starting at `p=none`). Send test mail of each kind
  (magic link, verification, password reset, an update email) to a Gmail and an
  iCloud address and check the headers show SPF, DKIM and DMARC passing.
- **Receiving:** nothing. `ceol.io` receives no mail today (product owner, 2026-10-07),
  and `ceol.app` won't either. One consequence to fix in the move: mail sent without a
  personal unsubscribe link (magic links, verification, password reset) carries
  `List-Unsubscribe: <mailto:unsubscribe@ceol.io>`, an address nobody receives, alongside a
  `List-Unsubscribe-Post` header that RFC 8058 only allows with an HTTPS link. So a Gmail
  "Unsubscribe" click on those messages goes nowhere. Those messages are transactional and
  shouldn't carry the headers at all: send them only when there is an `unsubscribe_url`
  (the update emails), and drop `MAIL_UNSUBSCRIBE`, rather than moving it to `ceol.app`.
- **After the switch:** nothing sends from `ceol.io` any more. Once a week of mail from
  `ceol.app` has gone out cleanly, replace `ceol.io`'s mail records with the ones for a
  domain that sends nothing (`v=spf1 -all`, DMARC `p=reject`, the SendGrid DKIM records
  removed), so nobody can send mail that passes as `ceol.io`.

## Settings

All on `ceol.io-live`; all read per request, so changing one needs no deploy.

| Setting | Phase 1 | Switch |
|---|---|---|
| `SESSION_COOKIE_DOMAINS` | `.ceol.io,.ceol.app` (replaces `SESSION_COOKIE_DOMAIN`, which is still read when this is unset) | same |
| `MOVE_TO_HOST` | `ceol.app` | same |
| `MOVE_FROM_HOSTS` | `ceol.io,www.ceol.io` | same |
| `MOVE_SWITCHED` | unset | `true` |
| `MAIL_DEFAULT_SENDER`, `MAIL_UPDATES_SENDER` | `ceol.io` addresses | `ceol.app` addresses |

## Counting ceol.io traffic

To decide when to retire the domain. Cloudflare's analytics for the `ceol.io` zone already
count requests per day, and after the switch every one of them is leftover traffic (bots
included). For the people behind it, the redirect logs one line per page (`moved-redirect path=… user_id=…`, logger
`ceol.domains`): the path, and the user id if the browser still carries a `ceol.io` login cookie. That shows who still
has old bookmarks, which can be followed up by email. Render keeps logs for a limited time,
so if a longer record is wanted, a small table with a daily count is the next step; not
built unless asked.

## Known costs

- **Installed web apps.** A home-screen install belongs to the origin it was installed
  from. Its icon opens `ceol.io`, which redirects out of the installed app's window. Delete it and re-add from
  `ceol.app`; the email says so.
- **Saved passwords.** Browser password managers file passwords by domain, so they may
  not offer the `ceol.io` password on `ceol.app`. The magic link covers anyone stuck.
- **Offline changes** queued on `ceol.io` and not synced before the switch are lost.
