// Deciding on the phone (spec 053, "Listening on the phone, offline"): the lab's
// listen.Listener.decide, so a phone that hears for itself (CeolHearing) can name the
// tune with no connection. Every 4 s, from what was heard over the last 24 s:
//
//   the shortlist   the session's tunes the n-grams like best (100; 300 once a person
//                   has said "none of these"), and the whole corpus's best 20 (60);
//   the aligner     each shortlisted tune, and those of the last six steps, against
//                   the newest 6 s of notes;
//   tune-ness       how much the last seconds sound like a tune at all;
//   the decoder     one step of belief, and the state the listening service would send.
//
// Held to the lab by fixtures it writes (`python -m lab decider fixtures`): the same
// heard messages in, the same shortlist, scores and state out.

import Foundation

public final class Decider {
    public let corpus: Corpus
    public let repertoire: Repertoire
    let lookup: Lookup
    let aligner: Aligner
    var decoder: TuneDecoder
    let tuneness: Tuneness
    let config: [String: Any]
    let frontends: [String]

    let windowMs, keep, poolTop, fallbackTop, widePoolTop, wideFallbackTop, ruleOutMs: Int

    // the scorer's memory
    var recent: [[Int]] = []
    var pinned: Set<Int> = []
    // the listener's
    var banned: [Int: Int] = [:]       // tune -> until (ms of audio)
    var widenUntil = 0
    var heardMs = 0
    var history: [[String: Any]] = []
    /// The newest state, as the listening service sends it.
    public private(set) var state: [String: Any] = ["status": "waiting for audio", "t_ms": 0, "top": [Any](),
                                                    "none": 1.0, "history": [Any]()]
    /// What the last step saw on the way, for the fixtures and the meter log.
    public private(set) var last: (pool: [Int], tunes: [Int], scores: [Int: Double], floor: Double,
                                   outside: [Int], nNotes: Int, tuneLogodds: Double)?

    /// `repertoire`: the session's tunes; nil is the default session's (the lab's).
    public init(corpus: Corpus, repertoire: [Int]? = nil) {
        self.corpus = corpus
        self.repertoire = Repertoire(repertoire ?? corpus.defaultRepertoire, in: corpus)
        lookup = Lookup(corpus)
        let cfg = corpus.meta["listener"] as? [String: Any] ?? [:]
        config = cfg
        func int(_ k: String, _ d: Int) -> Int { (cfg[k] as? NSNumber)?.intValue ?? d }
        windowMs = int("window_ms", 6000)
        keep = int("keep", 6)
        poolTop = int("pool_top", 100)
        fallbackTop = int("fallback_top", 20)
        widePoolTop = int("wide_pool_top", 300)
        wideFallbackTop = int("wide_fallback_top", 60)
        ruleOutMs = Int(((cfg["rule_out_s"] as? NSNumber)?.doubleValue ?? 30) * 1000)
        frontends = cfg["frontends"] as? [String] ?? ["yin", "basic_pitch", "pesto"]
        aligner = Aligner(corpus: corpus, chunk: int("chunk_notes", 24))
        tuneness = Tuneness(corpus.meta["tuneness"] as? [String: Any] ?? [:])
        let d = cfg["decoder"] as? [String: Any] ?? [:]
        func dbl(_ k: String, _ v: Double) -> Double { (d[k] as? NSNumber)?.doubleValue ?? v }
        decoder = TuneDecoder(lam: dbl("lam", 40), tau: dbl("tau", 0.45), pSwitch: dbl("p_switch", 0.05),
                          pNone: dbl("p_none", 0.3), nu: dbl("nu", 0.05), kappa: tuneness.kappa,
                          gamma: tuneness.gamma)
        decoder.nSettings = { [corpus] t in corpus.settingCount(of: t) }
    }

    /// One step from a heard message's parts: each tracker's notes over the last 24 s,
    /// the step's features, and how much audio the phone has heard.
    @discardableResult
    public func step(tMs t: Int, notes: [String: [HeardNote]], features: [String: Double?], heardMs: Int?)
        -> [String: Any]
    {
        let started = Date()
        self.heardMs = heardMs ?? 0
        let wide = t < widenUntil
        let ctx = frontends.map { notes[$0] ?? [] }

        // the shortlist: the session's tunes, then the whole corpus's best not among them
        let steps = ctx.map { intervals($0) }
        let top = wide ? widePoolTop : poolTop, fbTop = wide ? wideFallbackTop : fallbackTop
        var pool = fuse(steps.map { lookup.lookup($0, top: top, within: repertoire) }).prefix(top)
            .map { corpus.tuneID(at: $0.tune) }
        var inPool = Set(pool)
        for r in fuse(steps.map { lookup.lookup($0, top: fbTop) }).prefix(fbTop) {
            let id = corpus.tuneID(at: r.tune)
            if inPool.insert(id).inserted { pool.append(id) }
        }

        // the aligner, on this step's pool and the last few steps'
        recent = Array((recent + [pool]).suffix(keep + 1))
        var tunes = [Int](), seen = Set<Int>()
        for p in recent.reversed() { for id in p where seen.insert(id).inserted { tunes.append(id) } }
        for id in pinned where !seen.contains(id) { tunes.append(id) }
        let heard = ctx.map { $0.filter { $0.t0 >= t - windowMs } }
        let queries = heard.filter { !$0.isEmpty }.map(Aligner.query)
        var scores = (queries.isEmpty || tunes.isEmpty) ? [Double]() : aligner.scores(tunes, queries)
        var scored = scores.isEmpty ? [] : tunes
        let nNotes = heard.reduce(0) { $0 + $1.count }
        var outside = scored.filter { !repertoire.tuneIDs.contains($0) }

        // tune-ness, with the aligner's own evidence
        let sorted = scores.sorted(by: >) + [0, 0]
        var row = features
        row["n_notes"] = Double(nNotes)
        row["top_score"] = sorted[0]
        row["margin"] = sorted[0] - sorted[1]
        let logodds = tuneness.logodds(row)
        var floor = scores.min() ?? 0

        // what a person ruled out stays out for a while
        banned = banned.filter { $0.value > t }
        if !banned.isEmpty {
            let keepIdx = scored.indices.filter { banned[scored[$0]] == nil }
            scored = keepIdx.map { scored[$0] }
            scores = keepIdx.map { scores[$0] }
            outside = outside.filter { banned[$0] == nil }
            floor = scores.min() ?? 0
        }
        last = (pool, tunes, Dictionary(uniqueKeysWithValues: zip(scored, scores)), floor, outside, nNotes, logodds)

        let shown = decoder.step(Chunk(tMs: t, tunes: scored, scores: scores, floor: floor,
                                       outside: Set(outside), nNotes: nNotes, tuneLogodds: logodds))
        // a confirmed tune is held while the decoder agrees, and let go once it moves on
        if !pinned.isEmpty && !pinned.contains(shown) { pinned = [] }
        let belief = decoder.belief(8)
        let none = belief.first { $0.state == notATune }?.p ?? 0
        let out = Set(outside)
        let topList: [[String: Any]] = belief.filter { $0.state != notATune && banned[$0.state] == nil }.prefix(5)
            .map { b in
                ["tune_id": b.state, "name": corpus.name(of: b.state) as Any, "type": corpus.type(of: b.state) as Any,
                 "p": pyRound(b.p, 4), "outside": out.contains(b.state)]
            }
        let now: Int? = shown == notATune ? nil : shown
        if let now, (history.last?["tune_id"] as? Int) != now {
            history.append(["tune_id": now, "name": corpus.name(of: now) as Any, "from_ms": t])
        }
        state = ["status": "listening", "t_ms": t, "top": topList, "none": pyRound(none, 4),
                 "tuneness": pyRound(1 / (1 + exp(-logodds)), 3), "shown": now as Any, "notes": nNotes,
                 "wide": wide, "compute_ms": Int(1000 * Date().timeIntervalSince(started)),
                 "lag_ms": self.heardMs - t, "history": Array(history.suffix(8))]
        return state
    }

    /// One step from a heard message's JSON (CeolHearing's `Heard.message()`).
    @discardableResult
    public func step(message: String) -> [String: Any]? {
        guard let obj = try? JSONSerialization.jsonObject(with: Data(message.utf8)) as? [String: Any],
            let t = (obj["t_ms"] as? NSNumber)?.intValue
        else { return nil }
        var notes = [String: [HeardNote]]()
        for (name, list) in obj["notes"] as? [String: Any] ?? [:] {
            notes[name] = (list as? [[NSNumber]] ?? []).map { HeardNote($0[0].intValue, $0[1].intValue, $0[2].intValue) }
        }
        var feats = [String: Double?]()
        for (k, v) in obj["features"] as? [String: Any] ?? [:] { feats[k] = (v as? NSNumber)?.doubleValue }
        return step(tMs: t, notes: notes, features: feats, heardMs: (obj["heard_ms"] as? NSNumber)?.intValue)
    }

    /// "This is it": the tune a person says is playing.
    public func tapThis(_ tuneID: Int) {
        decoder.confirm(tuneID)
        pinned = [tuneID]
    }

    /// "None of these": the shown tunes ruled out for a while, and a wider search meanwhile.
    public func tapNone(shown: [Int]) {
        decoder.ruleOut(shown)
        for id in shown { banned[id] = heardMs + ruleOutMs }
        widenUntil = heardMs + ruleOutMs
    }

    /// The newest state as the listening service's "state" message.
    public func stateMessage() -> String {
        var s = state
        s["type"] = "state"
        s["heard_ms"] = heardMs
        let data = (try? JSONSerialization.data(withJSONObject: s, options: [.sortedKeys])) ?? Data()
        return String(decoding: data, as: UTF8.self)
    }
}

/// Is this a tune at all? (lab: analysis.tuneness.TunenessModel): a logistic model over
/// the step's features and the aligner's evidence.
struct Tuneness {
    let names: [String]
    let coef, median, mu, sd: [Double]
    let intercept, gamma, kappa: Double

    init(_ d: [String: Any]) {
        func arr(_ k: String) -> [Double] { (d[k] as? [NSNumber] ?? []).map(\.doubleValue) }
        names = d["names"] as? [String] ?? []
        coef = arr("coef"); median = arr("median"); mu = arr("mu"); sd = arr("sd")
        intercept = (d["intercept"] as? NSNumber)?.doubleValue ?? 0
        gamma = (d["gamma"] as? NSNumber)?.doubleValue ?? 0
        kappa = (d["kappa"] as? NSNumber)?.doubleValue ?? 0
    }

    func logodds(_ row: [String: Double?]) -> Double {
        var z = 0.0
        for (i, name) in names.enumerated() {
            var x = (row[name] ?? nil) ?? .nan
            if x.isNaN { x = median[i] }
            z += (x - mu[i]) / sd[i] * coef[i]
        }
        return z + intercept
    }
}
