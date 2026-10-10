// One model per open night (AppModel.openNight): the night's screen and the recorder's
// "this is it" share it, so a tune logged by one shows in the other with no connection.

import CeolSession
import Foundation
import Testing
@testable import Ceol

@MainActor
struct OpenNightTests {
    @Test func theScreenAndTheRecorderShareOneNight() {
        let app = AppModel(server: URL(string: "http://127.0.0.1:9")!, store: MemoryTokenStore())
        app.simulatedOffline = true
        let screen = app.openNight(42)
        let recorder = app.openNight(42)
        #expect(screen === recorder)
        #expect(app.openNight(43) !== screen)

        // the screen goes; the recorder still has it, and a screen opened again gets it
        app.closeNight(screen)
        let again = app.openNight(42)
        #expect(again === recorder)

        // both gone: the next to open it gets a fresh one
        app.closeNight(again)
        app.closeNight(recorder)
        #expect(app.openNight(42) !== recorder)
    }
}
