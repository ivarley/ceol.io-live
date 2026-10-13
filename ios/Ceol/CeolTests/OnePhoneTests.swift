// The suites that build an AppModel share the phone's one set of files — NightStore,
// PayloadStore, the tunebook queue, UserDefaults — and Swift Testing runs suites side
// by side. Nested here they run one at a time, so a sign-out or an account switch in
// one never wipes the night another has just saved.

import Testing

@Suite(.serialized)
struct OnePhoneTests {}
