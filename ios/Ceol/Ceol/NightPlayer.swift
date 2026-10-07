// Hearing a night (spec 050, read side), as the web logger plays it (frontend/src/
// App.svelte: loadAudio, queueFor, startQueue, playTick): a tune timestamped in the
// segmenter gets a ▶ on its row, a set with any gets one on its card, and the player
// plays the set's marked tunes in order, stopping at the end of the set.
//
//   - The night's audio comes from /api/session-instances/{id}/audio, which the server
//     gates exactly as the segmenter (a system admin, or a session admin granted
//     recordings). Anyone else, and most nights, get nothing: no buttons at all.
//   - Where each tune starts and ends, and what the player does at each moment, are
//     CeolLogic.Segments (resolveSegments, playbackStep), held to the web's fixtures.
//   - The stream is the small proxy encode; HD switches to the master, keeping your place.
//   - The link is presigned and expires: a failure asks for a fresh one, once.
//
// i18n-converted (spec 057).

import AVFoundation
import CeolLogic
import Foundation
import Observation

@Observable
final class NightPlayer {
    /// Where each marked tune sits in the recording.
    private(set) var resolved: [RecordID: Segments.Resolved] = [:]
    private(set) var sources: [JSONValue] = []
    private(set) var sourceID = "proxy"
    /// What's playing: ids in play order, and which.
    private(set) var queue: [RecordID] = []
    private(set) var idx = 0
    /// ms into the current tune.
    private(set) var playhead: Double = 0
    private(set) var paused = true
    var error: String?
    /// The transport panel, open.
    var open = false
    var repeatOne = false
    var autoContinue = true

    @ObservationIgnored private let instanceID: Int
    @ObservationIgnored private unowned let app: AppModel
    @ObservationIgnored private var player: AVPlayer?
    @ObservationIgnored private var timeObserver: Any?
    @ObservationIgnored private var failObserver: NSObjectProtocol?
    @ObservationIgnored private var seeking = false
    @ObservationIgnored private var urlRetried = false

    static let restartBeforePrevMs: Double = 3000

    init(instanceID: Int, app: AppModel) {
        self.instanceID = instanceID
        self.app = app
    }

    var hasAudio: Bool { !resolved.isEmpty && !sources.isEmpty }
    var isPlaying: Bool { !queue.isEmpty }
    var playingID: RecordID? { queue.indices.contains(idx) ? queue[idx] : nil }
    var tuneLengthMs: Double {
        guard let id = playingID, let s = resolved[id] else { return 0 }
        return max(0, (s.endMs ?? s.startMs) - s.startMs)
    }
    var canSwitchHD: Bool { sources.count > 1 }
    var hdOn: Bool { currentSource?["id"]?.stringValue == "master" }
    var masterSize: Int? { sources.first { $0["id"] == "master" }?["size_bytes"]?.intValue }

    private var currentSource: JSONValue? {
        sources.first { $0["id"]?.stringValue == sourceID } ?? sources.first
    }

    // MARK: - Loading

    func load() async {
        guard let data = try? await app.getJSON("/api/session-instances/\(instanceID)/audio"),
            let recording = data["recording"], !recording.isNull
        else { return }
        var srcs = recording["audio_sources"]?.arrayValue ?? []
        #if DEBUG
            // Test hook: local development has no S3, so no presigned link; a UI test
            // points the player at a local file instead.
            if srcs.isEmpty, let s = UserDefaults.standard.string(forKey: "CeolTestAudioURL") {
                srcs = [["id": "proxy", "url": .string(s), "mime_type": "audio/mp4"]]
            }
        #endif
        guard !srcs.isEmpty else { return }
        let marks: [Segments.Mark] = (data["segments"]?.arrayValue ?? []).compactMap { s in
            guard let id = RecordID(s["session_instance_tune_id"]), let start = s["start_ms"]?.doubleValue else { return nil }
            return Segments.Mark(id: id, startMs: start, endMs: s["end_ms"]?.doubleValue)
        }
        var map: [RecordID: Segments.Resolved] = [:]
        for (id, seg) in Segments.resolveSegments(marks, durationMs: recording["duration_ms"]?.doubleValue) { map[id] = seg }
        sources = srcs
        resolved = map
    }

    // MARK: - Playing

    /// A set's marked tunes, in play order, from `from` on.
    func queueFor(_ setTunes: [LogRecord], from: RecordID? = nil) -> [RecordID] {
        let ids = setTunes.compactMap(\.recordID).filter { resolved[$0] != nil }
        guard let from else { return ids }
        guard let i = ids.firstIndex(of: from) else { return [] }
        return Array(ids[i...])
    }

    /// A tune's ▶: pause or resume it if it's the one playing, else play from it to the
    /// end of its set.
    func toggleTune(_ setTunes: [LogRecord], _ id: RecordID) {
        if playingID == id { return togglePlayPause() }
        start(queueFor(setTunes, from: id))
    }

    /// A set's ▶ / ■.
    func toggleSet(_ setTunes: [LogRecord]) {
        let ids = queueFor(setTunes)
        if let p = playingID, ids.contains(p) { stop() } else { start(ids) }
    }

    func setIsPlaying(_ setTunes: [LogRecord]) -> Bool {
        guard let p = playingID else { return false }
        return queueFor(setTunes).contains(p)
    }

    func start(_ ids: [RecordID]) {
        guard !ids.isEmpty, let p = ensurePlayer() else { return }
        error = nil
        queue = ids
        idx = 0
        try? AVAudioSession.sharedInstance().setCategory(.playback)
        try? AVAudioSession.sharedInstance().setActive(true)
        seekToCurrent()
        p.play()
        paused = false
    }

    func stop() {
        player?.pause()
        queue = []
        idx = 0
        playhead = 0
        paused = true
        open = false
    }

    func togglePlayPause() {
        guard let p = player else { return }
        if p.rate == 0 {
            p.play()
            paused = false
        } else {
            p.pause()
            paused = true
        }
    }

    func next() {
        guard !queue.isEmpty else { return }
        if idx + 1 >= queue.count { return stop() }
        jump(to: idx + 1)
    }

    /// Restart this tune once you're into it (or at the head of the queue); else back one.
    func previous() {
        guard !queue.isEmpty else { return }
        if playhead > Self.restartBeforePrevMs || idx == 0 { return seekToCurrent() }
        jump(to: idx - 1)
    }

    /// The scrubber, within this tune.
    func seek(toMs ms: Double) {
        guard let id = playingID, let s = resolved[id] else { return }
        playhead = ms
        seek((s.startMs + ms) / 1000)
    }

    /// HD on or off, keeping your place and whether it was playing.
    func switchSource(_ id: String) {
        guard id != sourceID, sources.contains(where: { $0["id"]?.stringValue == id }), let old = player else { return }
        let at = old.currentTime()
        let wasPlaying = old.rate != 0
        sourceID = id
        guard let url = currentSource?["url"]?.stringValue.flatMap(URL.init(string:)) else { return }
        old.replaceCurrentItem(with: AVPlayerItem(url: url))
        watchFailure()
        old.seek(to: at, toleranceBefore: .zero, toleranceAfter: .zero) { _ in if wasPlaying { old.play() } }
    }

    private func jump(to i: Int) {
        guard queue.indices.contains(i) else { return }
        idx = i
        seekToCurrent()
    }

    private func seekToCurrent() {
        guard let id = playingID, let s = resolved[id] else { return }
        playhead = 0
        seek(s.startMs / 1000)
    }

    private func seek(_ seconds: Double) {
        guard let p = player else { return }
        seeking = true
        p.seek(to: CMTime(seconds: seconds, preferredTimescale: 1000), toleranceBefore: .zero, toleranceAfter: .zero) {
            [weak self] _ in
            Task { @MainActor in self?.seeking = false }
        }
    }

    private func ensurePlayer() -> AVPlayer? {
        if let player { return player }
        guard let url = currentSource?["url"]?.stringValue.flatMap(URL.init(string:)) else { return nil }
        let p = AVPlayer(url: url)
        player = p
        timeObserver = p.addPeriodicTimeObserver(forInterval: CMTime(value: 1, timescale: 10), queue: .main) { [weak self] t in
            MainActor.assumeIsolated { self?.tick(t.seconds * 1000) }
        }
        watchFailure()
        return p
    }

    /// One moment of playback: move on at a tune's end, seeking only across a real gap,
    /// and stop at the end of the set (Segments.playbackStep).
    private func tick(_ nowMs: Double) {
        guard !queue.isEmpty, !seeking else { return }
        var options = Segments.PlaybackOptions()
        options.repeatOne = repeatOne
        options.autoContinue = autoContinue
        let step = Segments.playbackStep(queue: queue, idx: idx, nowMs: nowMs, resolved: resolved, options: options)
        if step.done { return stop() }
        if step.idx != idx { idx = step.idx }
        if let ms = step.seekMs { seek(ms / 1000) }
        if let id = playingID, let s = resolved[id] { playhead = max(0, nowMs - s.startMs) }
        paused = (player?.rate ?? 0) == 0
    }

    /// The presigned link expires: ask for a fresh one, once, and carry on.
    private func watchFailure() {
        if let failObserver { NotificationCenter.default.removeObserver(failObserver) }
        failObserver = NotificationCenter.default.addObserver(
            forName: AVPlayerItem.failedToPlayToEndTimeNotification, object: player?.currentItem, queue: .main
        ) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in await self.retry() }
        }
    }

    private func retry() async {
        guard !urlRetried else {
            error = tr("Audio unavailable")
            return
        }
        urlRetried = true
        let was = Array(queue.dropFirst(idx))
        player?.pause()
        if let o = timeObserver { player?.removeTimeObserver(o) }
        player = nil
        await load()
        if !was.isEmpty { start(was) }
    }

    /// Leaving the night: stop, and let the player go.
    func release() {
        stop()
        if let o = timeObserver { player?.removeTimeObserver(o) }
        if let failObserver { NotificationCenter.default.removeObserver(failObserver) }
        timeObserver = nil
        failObserver = nil
        player = nil
    }
}
