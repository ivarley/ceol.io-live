// Recording segments (spec 050) — a port of frontend/src/shared/segments.js: where each
// placed tune ends, how a clock reads, and what queue playback does on each frame. The
// segmenter places the marks and the session page plays them; a native player is a
// third consumer, and a tune whose extent differs between them is a bug nobody would
// think to look for. Cases and the exact rules: shared/segments.fixtures.json.
//
// Milliseconds are Double, as they are JS numbers on the web.

import Foundation

public enum Segments {
    /// How far before a tune's end to hand over to the next one (a frame's worth).
    public static let handoverLeadMs: Double = 40
    /// Seek only when the next tune doesn't begin where this one ended.
    public static let contiguousMs: Double = 200

    // MARK: - formatClock

    /// mm:ss (h:mm:ss past an hour) for a millisecond offset; `--:--` for nothing or a
    /// non-finite value. `millis` adds the tenths, truncated.
    public static func formatClock(_ ms: Double?, millis: Bool = false) -> String {
        guard let ms, ms.isFinite else { return "--:--" }
        // Round the magnitude, so a half rounds away from zero on both sides of it.
        var t = Int64(abs(ms).rounded(.toNearestOrAwayFromZero))
        let shown = millis ? t / 100 : t / 1000
        let sign = ms < 0 && shown > 0 ? "-" : ""
        let msPart = t % 1000
        t /= 1000
        let s = t % 60
        let m = (t / 60) % 60
        let h = t / 3600
        let base = h != 0 ? "\(h):\(pad2(m)):\(pad2(s))" : "\(m):\(pad2(s))"
        return sign + base + (millis ? ".\(String(msPart / 100))" : "")
    }

    static func pad2(_ n: Int64) -> String { n < 10 ? "0\(n)" : "\(n)" }

    // MARK: - resolveSegments

    /// A tune as resolveSegments reads it: its id and, when placed, its segment.
    public struct Mark: Sendable {
        public var id: RecordID
        public var startMs: Double
        public var endMs: Double?

        public init(id: RecordID, startMs: Double, endMs: Double?) {
            self.id = id
            self.startMs = startMs
            self.endMs = endMs
        }
    }

    public struct Resolved: Equatable, Sendable {
        public var startMs: Double
        /// nil only for an implicit last end when the recording's duration is unknown.
        public var endMs: Double?
        public var explicitEnd: Bool
        /// Dead air after an explicit end, before the next tune (negative when marks overlap).
        public var gapAfterMs: Double
    }

    /// Every placed tune's end. An implicit end runs to the NEXT PLACED tune's start;
    /// the last placed tune's, to `durationMs`. Placed tunes in start order (a stable
    /// sort: equal starts keep their input order) — the order of the JS Map.
    public static func resolveSegments(_ marks: [Mark], durationMs: Double?) -> [(id: RecordID, segment: Resolved)] {
        let placed = marks.enumerated()
            .sorted { $0.element.startMs != $1.element.startMs ? $0.element.startMs < $1.element.startMs : $0.offset < $1.offset }
            .map(\.element)
        return placed.enumerated().map { i, mark in
            let next = i + 1 < placed.count ? placed[i + 1] : nil
            let implicitEnd = next?.startMs ?? durationMs
            let explicit = mark.endMs != nil
            let endMs = explicit ? mark.endMs : implicitEnd
            let gap: Double = explicit && next != nil ? next!.startMs - mark.endMs! : 0
            return (mark.id, Resolved(startMs: mark.startMs, endMs: endMs, explicitEnd: explicit, gapAfterMs: gap))
        }
    }

    // MARK: - playbackStep

    public struct PlaybackOptions: Sendable {
        public var leadMs: Double = Segments.handoverLeadMs
        public var contiguousMs: Double = Segments.contiguousMs
        /// Loop the current tune. Wins over autoContinue.
        public var repeatOne = false
        /// false stops at the end of the current tune.
        public var autoContinue = true

        public init() {}
    }

    public struct Step: Equatable, Sendable {
        public var idx: Int
        /// Where to seek; nil = let it run on.
        public var seekMs: Double?
        public var done: Bool
    }

    /// One frame of queue playback: given the playhead, which queue index should be
    /// playing, where to seek, and whether the queue is finished. `queue` is ids in
    /// play order; an id missing from `resolved`, or an idx past the end, is done.
    public static func playbackStep(
        queue: [RecordID], idx: Int, nowMs: Double, resolved: [RecordID: Resolved],
        options: PlaybackOptions = PlaybackOptions()
    ) -> Step {
        guard idx >= 0, idx < queue.count, let cur = resolved[queue[idx]] else {
            return Step(idx: idx, seekMs: nil, done: true)
        }
        // Still inside this tune (or before it, after a scrub). A null end reads as 0,
        // as it does in the JS arithmetic.
        if nowMs < (cur.endMs ?? 0) - options.leadMs { return Step(idx: idx, seekMs: nil, done: false) }
        if options.repeatOne { return Step(idx: idx, seekMs: cur.startMs, done: false) }
        if !options.autoContinue { return Step(idx: idx, seekMs: nil, done: true) }
        let nextIdx = idx + 1
        guard nextIdx < queue.count, let next = resolved[queue[nextIdx]] else {
            return Step(idx: idx, seekMs: nil, done: true)
        }
        return Step(
            idx: nextIdx,
            seekMs: abs(next.startMs - nowMs) > options.contiguousMs ? next.startMs : nil,
            done: false
        )
    }
}
