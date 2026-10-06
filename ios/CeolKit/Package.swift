// swift-tools-version: 6.2
//
// CeolKit: everything in the iOS app that is not a screen (spec 052 §C/§D).
//
//   CeolAPI     the client for the native surface, GENERATED at build time from
//               specs/api/native-surface.yaml (symlinked in as openapi.yaml) by
//               swift-openapi-generator. Method names are the spec's operationIds.
//   CeolDesign  the design tokens, design/Tokens.swift (symlinked), which
//               scripts/build_tokens.py generates from the same source as the web's CSS.
//   CeolSession sign-in: the Keychain token store, the emailed links, the auth calls.
//   CeolLogic   the live logger's client rules (logstate, fracindex, ...), ported from
//               the web and held to the web's own fixture files (spec 052 §B5).
//   CeolHearing listening on the phone (spec 053): audio -> notes and features, the lab's
//               listen.Hearer in Swift, held to fixtures the lab writes
//               (python -m lab hearing-fixtures).
//
// Both inputs live in the web repo and are symlinked rather than copied, so the app
// cannot quietly build against a stale copy of either — nor CeolLogicTests against a
// stale copy of the fixtures.
//
// `swift test` runs the package's tests on the Mac, with no simulator.

import PackageDescription

let package = Package(
    name: "CeolKit",
    platforms: [.iOS(.v26), .macOS(.v26)],
    products: [
        .library(name: "CeolAPI", targets: ["CeolAPI"]),
        .library(name: "CeolDesign", targets: ["CeolDesign"]),
        .library(name: "CeolLogic", targets: ["CeolLogic"]),
        .library(name: "CeolSession", targets: ["CeolSession"]),
        .library(name: "CeolHearing", targets: ["CeolHearing"]),
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-openapi-generator", from: "1.6.0"),
        .package(url: "https://github.com/apple/swift-openapi-runtime", from: "1.7.0"),
        .package(url: "https://github.com/apple/swift-openapi-urlsession", from: "1.0.0"),
        .package(url: "https://github.com/apple/swift-http-types", from: "1.3.0"),
    ],
    targets: [
        .target(
            name: "CeolAPI",
            dependencies: [
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "OpenAPIURLSession", package: "swift-openapi-urlsession"),
                .product(name: "HTTPTypes", package: "swift-http-types"),
            ],
            plugins: [.plugin(name: "OpenAPIGenerator", package: "swift-openapi-generator")]
        ),
        .target(name: "CeolDesign"),
        // Sign-in: the token store, the emailed links, and the auth calls (spec 052 A1).
        .target(
            name: "CeolSession",
            dependencies: ["CeolAPI", .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime")]
        ),
        .testTarget(
            name: "CeolSessionTests",
            dependencies: [
                "CeolSession", "CeolAPI",
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "HTTPTypes", package: "swift-http-types"),
            ]
        ),
        // The live logger's client rules, ported from the web (spec 052 §B5).
        .target(name: "CeolLogic"),
        // Reads the web's own frontend/src/**/*.fixtures.json in place (see
        // FixtureRunner.swift): one set of cases, run by Vitest there and here.
        .testTarget(name: "CeolLogicTests", dependencies: ["CeolLogic"]),
        // Listening on the phone (spec 053): the trackers (yin; PESTO and Basic Pitch as
        // Core ML models, compiled on first use), the notes, the beat and the features.
        .target(name: "CeolHearing", resources: [.copy("Models")]),
        // Stage by stage against the lab, on clips of real nights (Fixtures, written by
        // `python -m lab hearing-fixtures`).
        .testTarget(name: "CeolHearingTests", dependencies: ["CeolHearing"], resources: [.copy("Fixtures")]),
        .testTarget(
            name: "CeolAPITests",
            dependencies: [
                "CeolAPI",
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "HTTPTypes", package: "swift-http-types"),
            ],
            // Real responses from the seeded server (scripts/capture_native_fixtures.py).
            resources: [.copy("Fixtures")]
        ),
    ]
)
