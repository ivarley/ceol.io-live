// swift-tools-version: 6.2
//
// CeolKit: everything in the iOS app that is not a screen (spec 052 §C/§D).
//
//   CeolAPI     the client for the native surface, GENERATED at build time from
//               specs/api/native-surface.yaml (symlinked in as openapi.yaml) by
//               swift-openapi-generator. Method names are the spec's operationIds.
//   CeolDesign  the design tokens, design/Tokens.swift (symlinked), which
//               scripts/build_tokens.py generates from the same source as the web's CSS.
//
// Both inputs live in the web repo and are symlinked rather than copied, so the app
// cannot quietly build against a stale copy of either. The logic ports (logstate,
// fracindex, ...) join as further targets, tested against the web's fixture files.
//
// `swift test` runs the package's tests on the Mac, with no simulator.

import PackageDescription

let package = Package(
    name: "CeolKit",
    platforms: [.iOS(.v26), .macOS(.v26)],
    products: [
        .library(name: "CeolAPI", targets: ["CeolAPI"]),
        .library(name: "CeolDesign", targets: ["CeolDesign"]),
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
