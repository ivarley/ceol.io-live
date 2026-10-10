# Ceol for iOS

The native app (spec 052). SwiftUI for the four tabs and the live logger; admin and help
open the web in a Safari view. Plan and phases: `specs/changes/inprogress/052-native-ios-readiness.md`.

## Layout

| Path | What |
|---|---|
| `Ceol/` | The Xcode project: the app target (screens only), `CeolTests`, `CeolUITests`. iOS 26.0, Swift 6, main-actor isolation by default. Source folders are synchronized: a new `.swift` file in `Ceol/Ceol/` is in the target without touching the project file. |
| `CeolKit/` | A local Swift package with everything that is not a screen. The app links its products. |
| `CeolKit/Sources/CeolAPI` | The API client. **Generated at build time** by `swift-openapi-generator` from `openapi.yaml`, a symlink to `specs/api/native-surface.yaml`. Each operation is a method named by its `operationId` (`getSessionDetail`, `applyLiveOp`, …); schemas are `Components.Schemas.<Name>`. `CeolClient.swift` adds what the spec can't say: `Client.ceol(clientID:token:)` sends `X-Ceol-Client` and, when signed in, `Authorization: Bearer`. |
| `CeolKit/Sources/CeolDesign` | `CeolTokens`: `Tokens.swift` is a symlink to `design/Tokens.swift`, which `make tokens` generates from the same source as the web's CSS. |
| `CeolKit/Sources/CeolSession` | Sign-in: `AuthService` (check-email, password login, link exchange, logout, app-config, profile), `KeychainTokenStore` (the Bearer token, this device only), `AuthLink` (the emailed `/auth/login/<token>` and `/verify-email/<token>` links). |
| `CeolKit/Sources/CeolLogic` | The live logger's client rules, ported from the web: `FracIndex`, `LogState` (ordering, sets, cursor, anchors, merge), `OfflineRules`, `ABCQuery`, `Segments`, `NameMatch`, `TheSession` (id parsing); and the screens' list rules, `HomeRules`, `SessionsRules`, `MyTunesRules`. Records and op payloads stay `JSONValue`, so a row passes through with every field it arrived with. |
| `CeolKit/Sources/CeolHearing` | Listening on the phone (spec 053): `Hearer`, the lab's `listen.Hearer` in Swift. Every 4 s of audio it tracks with yin, Basic Pitch and PESTO (`Models/`, Core ML packages compiled on first use), makes each tracker's notes over the last 24 s and the music detector's features, and `Heard.message()` is what goes to the listening service in place of the audio. |
| `CeolKit/Sources/CeolDeciding` | Deciding on the phone, offline (spec 053): `Decider`, the lab's `listen.Listener.decide` in Swift (the shortlist, the aligner, tune-ness, the decoder, the taps), over `Corpus`, a 16 MB file the lab writes (`python -m lab decider export`) and the app maps. `Decider(corpus:sessionTunes:)` takes the night's own tunes (the app's `KnownTunes`, from `GET /api/session-instances/<id>/known-tunes`, kept for nights with no signal; none, and the popular tunes stand in). The app ships the copy in `Data/` (gitignored: `python -m lab decider export --out ios/CeolKit/Sources/CeolDeciding/Data/decider-v2.bin`), and `DeciderData` installs a newer one fetched since (the app's `DeciderRefresher`: `GET /api/listen/decider-data`, rebuilt weekly from thesession.org's dump, checked against its SHA-256 before it replaces anything); without either, "This phone" decides on Ceol's server. |
| `CeolKit/Tests/CeolDecidingTests` | Holds the decider to the lab step by step: `Fixtures/` (written by `python -m lab decider fixtures`) are four-minute stretches of real nights as heard, with taps, and what the lab decided at each step. Needs the data file packed from the index the fixtures were decided with (`python -m lab decider export --from-index`: `CEOL_DECIDER_DATA`, `LAB_DATA_DIR/index/decider-v2.bin`, or the one in `Data/`), else skipped. Also a clip heard and decided in Swift end to end. |
| `CeolKit/Tests/CeolHearingTests` | Holds that port to the lab stage by stage: `Fixtures/` (written by `python -m lab hearing-fixtures`) are clips of real nights and each stage's input and output as the lab computes them. `CEOL_LISTEN_URL=ws://localhost:8440/listen` also runs a clip through a local listening service. |
| `CeolKit/Tests/CeolLogicTests` | Holds that port to the web's OWN fixture files (`frontend/src/**/*.fixtures.json`), read in place: every function in a file needs a Swift port, and every case must give the web's answer, including the name matcher's calibration bars. |
| `CeolKit/Tests/CeolAPITests` | The client's headers, and decoding: `Fixtures/` holds **real** responses captured from the seeded server (`make ios-fixtures`), and each must decode into its generated type. |

The two symlinks are the point: the app cannot build against a stale copy of the API
contract or the palette. A change to either is picked up on the next build.

## Commands

```bash
make ios-test       # swift test in CeolKit (Mac, no simulator), then the app's tests in the simulator
make ios-ui-test    # UI tests (sign-in, browsing, Me) in the simulator, against a LOCAL server (see below)
make ios-build      # build the app for the simulator
make ios-fixtures   # re-capture the response fixtures from the seeded local DB
```

Or open `Ceol/Ceol.xcodeproj` in Xcode. The first build asks you to **trust the
OpenAPIGenerator plugin** — it is Apple's, and it is what writes the API client. (The
`make` targets pass `-skipPackagePluginValidation` for the same reason.)

## Running against a local server

Debug builds read three launch arguments (Xcode: Scheme > Run > Arguments):

| Argument | Does |
|---|---|
| `-CeolServerURL http://127.0.0.1:5031` | Talk to a development server instead of https://ceol.io (plain HTTP to 127.0.0.1 needs no ATS exception). Sign-in links on that host are accepted too. |
| `-CeolResetSession YES` | Start signed out. Keychain items survive a reinstall on the simulator. |
| `-CeolOpenURL <url>` | Open a URL at launch, as if a link were tapped: how the UI tests open an emailed link. |

`make ios-ui-test` expects the app on `IOS_TEST_SERVER` (default `http://127.0.0.1:5031`)
and refuses anything but a local address. It signs in with the seeded password account,
and mints a magic-link token straight into the local database
(`scripts/mint_login_token.py`), so it never sends email. Local runs of the web app DO
send real email, so don't type a real address into a locally-pointed app.

## Rules

- **The API contract lives in the web repo.** Need an endpoint or a field? Add it to
  `specs/api/native-surface.yaml` and the web's contract test first; the client follows on
  the next build. The surface is additive-only once a build ships, and so are
  `operationId`s — they are this app's method names.
- **Re-capture fixtures** after a payload changes (`make ios-fixtures`), and commit them.
- **Logic ports agree with the web byte for byte.** `logstate`, `fracindex` and friends are
  ported into CeolKit and tested against the web's own `frontend/src/**/*.fixtures.json`
  (spec 052 §B5). A behaviour change lands in the fixtures first.
