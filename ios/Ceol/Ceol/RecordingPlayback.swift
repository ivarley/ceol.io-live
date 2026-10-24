// Hearing a recording kept on this phone (the recordings list's ▶): the CAF the
// recorder wrote, played with AVAudioPlayer, one at a time. Nothing to do with the
// server's audio (NightPlayer), which plays a night's uploaded, segmented recording.
//
// i18n-converted (spec 057): no text of its own.

import AVFoundation
import Foundation
import Observation

@Observable
final class RecordingPlayer {
    /// The recording playing or paused, if any.
    private(set) var current: String?
    private(set) var playing = false
    /// Seconds into it, and its length.
    private(set) var position: TimeInterval = 0
    private(set) var duration: TimeInterval = 0
    var error: String?

    @ObservationIgnored private var player: AVAudioPlayer?
    @ObservationIgnored private var timer: Timer?

    /// ▶ on a recording: play it from the start, resume it, or pause it.
    func toggle(_ id: String, file: URL) {
        if current == id {
            if playing { pause() } else { resume() }
            return
        }
        stop()
        do {
            let p = try AVAudioPlayer(contentsOf: file)
            p.prepareToPlay()
            player = p
            current = id
            duration = p.duration
            position = 0
            error = nil
            resume()
        } catch {
            self.error = error.localizedDescription
        }
    }

    func seek(_ seconds: TimeInterval) {
        guard let player else { return }
        player.currentTime = max(0, min(seconds, duration))
        position = player.currentTime
    }

    func pause() {
        player?.pause()
        playing = false
        timer?.invalidate()
        timer = nil
    }

    func stop() {
        pause()
        player?.stop()
        player = nil
        current = nil
        position = 0
        duration = 0
    }

    private func resume() {
        guard let player else { return }
        try? AVAudioSession.sharedInstance().setCategory(.playback)
        try? AVAudioSession.sharedInstance().setActive(true)
        player.play()
        playing = true
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
    }

    /// Where the player has got to; at the end, back to the start, stopped.
    private func tick() {
        guard let player else { return }
        if player.isPlaying {
            position = player.currentTime
        } else if playing {
            playing = false
            position = 0
            timer?.invalidate()
            timer = nil
        }
    }
}
