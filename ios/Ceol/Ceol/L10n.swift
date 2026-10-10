// The language Ceol is shown in (spec 057): English or Irish, from the profile
// setting (`/api/me`'s `language`), not the phone's language. The app root sets
// `\.locale` from it, and SwiftUI's Text, Button and Label look their strings up in
// Localizable.xcstrings in that locale, so a change shows at once. Strings that never
// reach a Text as a literal (a String passed around, a toast, an alert built in code)
// go through tr(), which reads the same catalog in the same language.
//
// The rule (CLAUDE.md): every string a person reads exists in both languages.
// `make ios-strings` syncs the catalog from the build and applies the Irish in
// ios/Ceol/i18n-ga/*.json; tests/unit/test_ios_strings.py and `make ios-test` fail
// when a string has no Irish.

import Foundation
import SwiftUI

enum AppLanguage {
    private static let key = "CeolLanguage"
    // Read from any thread (a background upload may format a message); written only
    // from the main actor when the profile says so.
    nonisolated(unsafe) private static var stored: String =
        UserDefaults.standard.string(forKey: "CeolLanguage") == "ga" ? "ga" : "en"

    /// "en" or "ga".
    nonisolated static var code: String { stored }

    nonisolated static var locale: Locale { Locale(identifier: stored == "ga" ? "ga_IE" : "en_US") }

    /// The catalog's strings for this language. English is the source language, so it
    /// is the catalog's own keys; Irish is the compiled ga.lproj.
    nonisolated static var bundle: Bundle {
        if stored == "ga", let path = Bundle.main.path(forResource: "ga", ofType: "lproj"),
           let bundle = Bundle(path: path) {
            return bundle
        }
        if let path = Bundle.main.path(forResource: "en", ofType: "lproj"), let bundle = Bundle(path: path) {
            return bundle
        }
        return .main
    }

    /// Remembered for the next launch, so the app opens in it before `/api/me` answers.
    static func set(_ code: String?) {
        stored = code == "ga" ? "ga" : "en"
        UserDefaults.standard.set(stored, forKey: key)
    }
}

/// A string in the app's language, for text that doesn't reach SwiftUI as a literal.
/// The literal at the call site is extracted into Localizable.xcstrings like a Text's.
nonisolated func tr(_ value: String.LocalizationValue) -> String {
    String(localized: value, bundle: AppLanguage.bundle, locale: AppLanguage.locale)
}

/// Dates and times in the app's language ("Dé hAoine 23 Deireadh Fómhair").
nonisolated func localizedDate(_ date: Date, _ style: Date.FormatStyle) -> String {
    date.formatted(style.locale(AppLanguage.locale))
}
