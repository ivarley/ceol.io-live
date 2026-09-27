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
| `CeolKit/Sources/CeolLogic` | The live logger's client rules, ported from the web: `FracIndex`, `LogState` (ordering, sets, cursor, anchors, merge), `OfflineRules`, `ABCQuery`, `Segments`, `NameMatch`, `TheSession` (id parsing). Records and op payloads stay `JSONValue`, so a row passes through with every field it arrived with. |
| `CeolKit/Tests/CeolLogicTests` | Holds that port to the web's OWN fixture files (`frontend/src/**/*.fixtures.json`), read in place: every function in a file needs a Swift port, and every case must give the web's answer, including the name matcher's calibration bars. |
| `CeolKit/Tests/CeolAPITests` | The client's headers, and decoding: `Fixtures/` holds **real** responses captured from the seeded server (`make ios-fixtures`), and each must decode into its generated type. |

The two symlinks are the point: the app cannot build against a stale copy of the API
contract or the palette. A change to either is picked up on the next build.

## Commands

```bash
make ios-test       # swift test in CeolKit (Mac, no simulator), then the app's tests in the simulator
make ios-build      # build the app for the simulator
make ios-fixtures   # re-capture the response fixtures from the seeded local DB
```

Or open `Ceol/Ceol.xcodeproj` in Xcode. The first build asks you to **trust the
OpenAPIGenerator plugin** — it is Apple's, and it is what writes the API client. (The
`make` targets pass `-skipPackagePluginValidation` for the same reason.)

## Rules

- **The API contract lives in the web repo.** Need an endpoint or a field? Add it to
  `specs/api/native-surface.yaml` and the web's contract test first; the client follows on
  the next build. The surface is additive-only once a build ships, and so are
  `operationId`s — they are this app's method names.
- **Re-capture fixtures** after a payload changes (`make ios-fixtures`), and commit them.
- **Logic ports agree with the web byte for byte.** `logstate`, `fracindex` and friends are
  ported into CeolKit and tested against the web's own `frontend/src/**/*.fixtures.json`
  (spec 052 §B5). A behaviour change lands in the fixtures first.
