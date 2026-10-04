// A night, live (plan Phase 5a): the log as the referee has it, kept current by the
// streaming service's events, as the web logger's view mode is (frontend/src/App.svelte
// connect(), client.js openStream()).
//
//   - The night is read raw (JSON, not a generated type) so no field of a record is
//     dropped; LiveLog holds it and applies each op through LogState.recordChanges /
//     metaChanges, the rules the web logger uses.
//   - The stream opens from the night's last event id (?last_event_id=, then the
//     Last-Event-ID header on reconnects), with mode=view: reading asserts no presence.
//   - An error reopens it from where it left off, backing off; a stream that goes quiet
//     for 45 seconds (the server pings every 15) is dead without saying so, and gets a
//     full fresh start, as the web's watchdog does.
//   - A finished log is shown as it is, with no stream (the web's render-only path).
//
// Offline (plan Phase 5d), as the web logger (spec 024 §G): the night and its unsent
// changes are kept on the phone (NightStore). A change that can't be sent waits there,
// marked "offline" on its row, with every later change queued behind it; when the
// connection is back (the stream reconnects, a load succeeds, the network returns, the
// app comes forward) the queue is sent in order. Changes refused then are listed for
// review. Opening a night without a connection shows the saved copy.
//
// Editing (plan Phase 5b): "Edit" reopens the stream with mode=edit (which is what shows
// you as logging to the others), and each change goes through LiveLog's optimistic
// pipeline: shown at once, sent one at a time in order, settled by the answer or the
// stream's echo, rolled back on a refusal.

import CeolAPI
import CeolLogic
import CeolSession
import Foundation
import Network
import Observation
import UIKit

@Observable
final class NightModel {
    enum Status: Equatable {
        case connecting
        case live
        case reconnecting
        /// Couldn't reach the server: showing what we have, retrying.
        case offline
        /// A finished log: nothing to stream.
        case finished
    }

    let instanceID: Int
    private(set) var log: LiveLog? {
        didSet { if running { scheduleSave() } }
    }
    /// The night's bootstrap, raw: names, dates, the people settings.
    private(set) var night: JSONValue?
    private(set) var status: Status = .connecting
    private(set) var loadError: String?
    /// Who's logging right now (the stream's presence events), for the header:
    /// {person_id, arrival_seq (their colour), name, devices, away}.
    private(set) var roster: [JSONValue] = []
    /// Who's typing a tune (the stream's typing events), me included.
    private(set) var typers: [JSONValue] = []

    /// Other people's changes, a line each ("Sarah O'Connor added The Kesh"), for four
    /// seconds, three at most (spec 024 §E).
    struct Activity: Identifiable, Equatable {
        let id: Int
        let text: String
        /// The actor's colour index, if they're on the roster.
        let color: Int?
    }
    private(set) var activities: [Activity] = []
    @ObservationIgnored private var activitySeq = 0
    /// Rows someone else just changed, ringed in their colour for a moment.
    private(set) var flashes: [RecordID: Int?] = [:]

    /// Logging, not just watching.
    private(set) var editing = false
    /// Where the next tune goes.
    var cursor: Cursor = .end
    /// The row whose actions are showing (the cursor hides while one is).
    var selected: RecordID?
    /// The last refusal or failure, for a banner.
    var notice: String?
    /// A passing confirmation ("Copied 3 tunes in 2 sets").
    var flash: String?

    /// Selection mode (spec 029): tap to pick rows, drag to move, bulk actions.
    private(set) var selecting = false
    var picked: Set<RecordID> = []
    /// A drag in progress (select mode).
    var drag: LogDrag?
    /// The last bulk delete, for Undo (for eight seconds).
    private(set) var undoable: (rows: [LogRecord], count: Int)?
    private var undoSeq = 0
    /// Our own last copy: pasting it back keeps the tunes' links.
    private var lastCopy: Selection.Copy?
    /// The session's roster with tonight's check-ins (the starter picker).
    private(set) var people: [JSONValue] = []
    private(set) var peopleLoaded = false

    /// The session's vocabulary as a match index (Composer), loaded after the night.
    private(set) var vocab: VocabIndex?
    /// The typing box: search, matching, the placeholder, editing a logged tune.
    @ObservationIgnored private(set) lazy var composer = LogComposerModel(night: self)
    /// The night's audio, where the segmenter has timestamped its tunes (spec 050).
    @ObservationIgnored private(set) lazy var player = NightPlayer(instanceID: instanceID, app: app)
    @ObservationIgnored private var audioAsked = false
    /// A tune that just merged into the open set, for "Keep both" (seven seconds).
    private(set) var merged: (name: String, payload: [String: JSONValue])?
    private var mergedSeq = 0
    /// Likely-next pairings dismissed this visit ("anchor->next").
    var dismissedNext: [String] = []

    /// Bumped when the insertion point should come into view: after I log a tune, and
    /// on starting to edit (as the web keeps its active seam visible).
    private(set) var revealCursor = 0

    /// Offline changes the server refused once they were sent, for review.
    var review: [ReviewItem]?
    /// The vocabulary as it came, kept with the saved night.
    private var knownRaw: JSONValue?
    private var aliasesRaw: JSONValue?
    /// The copy on the phone, until the night loads.
    private var saved: SavedNight?
    private var stalePaint: Task<Void, Never>?
    private var saveTask: Task<Void, Never>?
    /// A send failed for want of a connection: new changes queue behind it.
    private var waitingForNetwork = false
    private var flushRejects: [ReviewItem] = []
    private var synced = 0
    private let path = NWPathMonitor()

    struct ReviewItem: Identifiable, Equatable {
        let id = UUID()
        let what: String
        let why: String
    }

    /// Changes waiting on the phone for a connection.
    var queuedCount: Int { log?.queuedCount ?? 0 }

    let app: AppModel
    /// Ops waiting to go, in order.
    private var outbox: [String] = []
    private var sender: Task<Void, Never>?
    private var stream: Task<Void, Never>?
    private var watchdog: Task<Void, Never>?
    private var lastAlive = Date()
    private var failures = 0
    private var running = false

    static let watchdogSeconds: TimeInterval = 45

    init(instanceID: Int, app: AppModel) {
        self.instanceID = instanceID
        self.app = app
    }

    /// Load the night and, unless it's finished, go live.
    func start() async {
        running = true
        path.pathUpdateHandler = { [weak self] p in
            guard p.status == .satisfied else { return }
            Task { @MainActor in await self?.networkBack() }
        }
        path.start(queue: .main)
        await connect()
    }

    /// The phone has a network again: reconnect if we're not live.
    private func networkBack() async {
        guard running, status != .live, status != .finished, status != .connecting else { return }
        await connect()
    }

    /// Test hook: pretend the phone has lost (or regained) its signal.
    func setSimulatedOffline(_ on: Bool) {
        app.simulatedOffline = on
        if on {
            stream?.cancel()
            watchdog?.cancel()
            status = .offline
        } else {
            Task { await connect() }
        }
    }

    func stop() {
        saveNow()
        player.release()
        path.cancel()
        running = false
        if editing { app.editingNight = false }
        stream?.cancel()
        watchdog?.cancel()
        stream = nil
        watchdog = nil
    }

    /// Back in the foreground: a stream the phone suspended is likely dead.
    func resume() async {
        guard running, status != .finished, status != .live || Date().timeIntervalSince(lastAlive) > 20 else { return }
        await connect()
    }

    // MARK: -

    private func connect() async {
        stream?.cancel()
        watchdog?.cancel()
        if log == nil {
            status = .connecting
            // The copy on the phone: shown if the load is slow (800ms) or can't happen.
            if saved == nil, let s = NightStore.load(instanceID) {
                saved = s
                stalePaint = Task { [weak self] in
                    try? await Task.sleep(for: .milliseconds(800))
                    guard let self, !Task.isCancelled, self.log == nil else { return }
                    self.paintSaved()
                }
            }
        }
        do {
            let b = try await app.getJSON("/api/live/instances/\(instanceID)/bootstrap")
            stalePaint?.cancel()
            night = b
            let meta: [String: JSONValue] = [
                "notes": b["notes"] ?? .null, "instance_date": b["instance_date"] ?? .null,
                "session_date": b["session_date"] ?? .null, "start_time": b["start_time"] ?? .null,
                "end_time": b["end_time"] ?? .null, "instance_name": b["instance_name"] ?? .null,
                "log_complete": b["log_complete"] ?? false,
            ]
            let fresh = LiveLog(records: b["records"]?.arrayValue ?? [], meta: meta, lastEventID: b["last_event_id"]?.intValue ?? 0)
            // Changes still in flight, or saved from last time, are laid over the fresh
            // log, not lost.
            let wasQueued = queuedCount
            let base = log ?? saved.map { restoredLog($0.log) }
            log = base.map { $0.rebased(onto: fresh) } ?? fresh
            if saved != nil && knownRaw == nil { knownRaw = saved?.knownTunes; aliasesRaw = saved?.knownAliases }
            saved = nil
            // (A send in flight owns the queue's head: leave the order to it.)
            if sender == nil { outbox = log?.sendOrder ?? [] }
            loadError = nil
            failures = 0
            Task { await loadVocabulary() }
            if !audioAsked {
                audioAsked = true
                Task { await player.load() }
            }
            // Send what waited before listening again, as the web does.
            if wasQueued > 0 || !outbox.isEmpty { await flush() }
        } catch {
            stalePaint?.cancel()
            if log == nil {
                if saved != nil { paintSaved() } else { loadError = loadFailureMessage(error) }
            }
            status = .offline
            retryLater()
            return
        }
        if log?.meta["log_complete"] == true && queuedCount == 0 {
            status = .finished
            return
        }
        openStream()
    }

    /// Show the saved copy: the night, its log with its waiting changes, the vocabulary.
    private func paintSaved() {
        guard let s = saved, log == nil else { return }
        night = s.night
        log = restoredLog(s.log)
        knownRaw = s.knownTunes
        aliasesRaw = s.knownAliases
        vocab = Composer.buildIndex(known: s.knownTunes?.arrayValue, aliases: s.knownAliases?.arrayValue)
        outbox = log?.sendOrder ?? []
        waitingForNetwork = !outbox.isEmpty
        loadError = nil
    }

    /// A saved log's unanswered changes are waiting, whatever they were doing when saved.
    private func restoredLog(_ l: LiveLog) -> LiveLog {
        var l = l
        for id in l.sendOrder { l.markQueued(id) }
        return l
    }

    // MARK: - Saving

    private func scheduleSave() {
        saveTask?.cancel()
        saveTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(800))
            guard !Task.isCancelled else { return }
            self?.saveNow()
        }
    }

    private func saveNow() {
        saveTask?.cancel()
        guard let log, let night else { return }
        NightStore.save(
            SavedNight(night: night, log: log, knownTunes: knownRaw, knownAliases: aliasesRaw, savedAt: Date()), instanceID)
    }

    private func openStream() {
        guard running, let from = log?.highWater else { return }
        status = failures == 0 ? .connecting : .reconnecting
        lastAlive = Date()
        stream = Task { [weak self] in
            guard let self else { return }
            do {
                if self.app.simulatedOffline { throw URLError(.notConnectedToInternet) }
                let base = try await self.app.streamingBase()
                let url = base.appending(path: "live/instances/\(self.instanceID)/events")
                    .appending(queryItems: [.init(name: "last_event_id", value: String(from)), .init(name: "mode", value: self.editing ? "edit" : "view")])
                var request = self.app.authorized(URLRequest(url: url))
                request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                request.setValue(String(from), forHTTPHeaderField: "Last-Event-ID")
                request.timeoutInterval = 60
                let (bytes, response) = try await URLSession.shared.bytes(for: request)
                guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
                self.status = .live
                self.failures = 0
                self.startWatchdog()
                Task { await self.flush() }
                var parser = SSEParser(lastEventID: String(from))
                for try await byte in bytes {
                    self.lastAlive = Date()
                    for event in parser.feed(CollectionOfOne(byte)) { self.handle(event) }
                }
                throw URLError(.networkConnectionLost)  // the server closed it
            } catch is CancellationError {
                return
            } catch {
                if Task.isCancelled { return }
                self.failures += 1
                self.status = .reconnecting
                self.roster = []
                self.typers = []
                self.watchdog?.cancel()
                // Reopen from where it left off, backing off: 1, 2, 5, 10 seconds.
                let delay = [1.0, 2, 5, 10][min(self.failures - 1, 3)]
                try? await Task.sleep(for: .seconds(delay))
                if !Task.isCancelled && self.running { self.openStream() }
            }
        }
    }

    private func handle(_ event: SSEEvent) {
        guard let json = try? JSONDecoder().decode(JSONValue.self, from: Data(event.data.utf8)) else { return }
        switch event.type {
        case "op":
            noteRemote(json)
            let changed = log?.apply(json) == true
            if changed { settleCursor() }
            if changed, log?.meta["log_complete"] == true {
                // Finished while we watched: nothing more to stream, or to edit.
                status = .finished
                stop()
                editing = false
                running = true
            }
        case "presence":
            roster = json["roster"]?.arrayValue ?? []
        case "typing":
            typers = json["typing"]?.arrayValue ?? []
        default:
            break  // ping: proof of life only
        }
        // Someone checked in or out: the attendance list changed.
        if event.type == "op", json["op_type"]?.stringValue?.hasPrefix("attendance_") == true {
            Task { await loadPeople() }
        }
    }

    // MARK: - Editing

    /// Start or stop logging: the stream reopens in the new mode.
    func setEditing(_ on: Bool) {
        guard editing != on else { return }
        if !on {
            composer.reset()
            stopTyping()
        }
        editing = on
        selected = nil
        selecting = false
        picked = []
        if on { revealCursor += 1 }
        cursor = .end
        app.editingNight = on
        guard running, status != .finished else { return }
        stream?.cancel()
        watchdog?.cancel()
        failures = 0
        openStream()
    }

    /// Log a tune at a cursor (the current one unless a placeholder captured another):
    /// {tune_id, name, tune_type}, {name} for the server to match, or {thesession_id}. A
    /// tune the open set already has merges into it, with "Keep both" offered.
    func logTune(_ payload: [String: JSONValue], at: Cursor? = nil) {
        guard var l = log else { return }
        selected = nil
        let at = at ?? cursor
        let r = l.logTune(payload, at: at)
        log = l
        if cursor == at { cursor = r.cursor }
        revealCursor += 1
        enqueue(r.ops)
        if let target = r.mergedInto {
            let name = target["name"]?.stringValue ?? payload["name"]?.stringValue ?? "that tune"
            mergedSeq += 1
            let seq = mergedSeq
            merged = (name, payload)
            Task { [weak self] in
                try? await Task.sleep(for: .seconds(7))
                if self?.mergedSeq == seq { self?.merged = nil }
            }
        }
    }

    /// "Keep both": log the merged tune again as its own row at the end.
    func keepBoth() {
        guard let m = merged else { return }
        merged = nil
        logTune(m.payload.merging(["no_merge": true]) { _, b in b }, at: .end)
    }

    func dismissMerged() { merged = nil }

    /// A placeholder row while the server decides what typed text names.
    func startPlaceholder(_ text: String, at cursor: Cursor) -> String? {
        guard var l = log else { return nil }
        let id = l.startResolving(text, at: cursor)
        log = l
        return id
    }

    func dropPlaceholder(_ id: String) {
        log?.dropPlaceholder(id)
    }

    /// Relink, unlink or rename a logged tune.
    func changeTune(_ id: RecordID, _ payload: [String: JSONValue], patch: [String: JSONValue]) {
        guard var l = log, let op = l.changeTune(id, payload, patch: patch) else { return }
        log = l
        enqueue([op])
    }

    func loadVocabulary() async {
        guard let v = try? await app.getJSON("/api/live/instances/\(instanceID)/vocabulary") else { return }
        knownRaw = v["known_tunes"]
        aliasesRaw = v["known_aliases"]
        vocab = Composer.buildIndex(known: v["known_tunes"]?.arrayValue, aliases: v["known_aliases"]?.arrayValue)
        scheduleSave()
    }

    /// The set the cursor is building, its type and its tunes (for the suggestions).
    var cursorSegment: LogSegment? {
        guard let log else { return nil }
        return Composer.cursorSegment(
            LogState.segmentByBreaks(log.ordered), endIsOpen: !(log.ordered.last?.isBreak ?? true), cursor: cursor)
    }

    /// The cursor is after the last tune of a closed set: "End set" there means done
    /// with it (LogState.cursorAtClosedSetEnd, shared with the web).
    var atClosedSetEnd: Bool {
        guard let log else { return false }
        return LogState.cursorAtClosedSetEnd(cursor, segments: LogState.segmentByBreaks(log.ordered))
    }

    /// Leave "seam mode": the cursor back to the end of the log, no row selected (a tap
    /// on the empty part of the log, or End set at the end of a closed set).
    func leaveSeam() {
        guard editing, !selecting, cursor != .end || selected != nil else { return }
        cursor = .end
        selected = nil
        revealCursor += 1
    }

    /// The tune that usually comes next here, at the end of a set.
    var likelyNext: VocabTune? {
        guard editing, !selecting, log?.meta["log_complete"] != true, composer.resolving == nil, composer.editingID == nil
        else { return nil }
        return Composer.likelyNext(vocab, seg: cursorSegment, cursor: cursor, dismissed: dismissedNext)
    }

    func dismissLikelyNext() {
        guard let nx = likelyNext, let tid = cursorSegment?.tunes.last?["tune_id"]?.intValue else { return }
        dismissedNext.append(Composer.nextAssocKey(tid, nx.tuneID))
    }

    func endSet() {
        guard var l = log, let op = l.endSet() else { return }
        log = l
        cursor = .end
        enqueue([op])
    }

    func split(after id: RecordID) {
        guard var l = log else { return }
        let op = l.split(after: id)
        log = l
        // The spot becomes the gap between the two sets: tapping it again joins them.
        if let next = nextTune(after: id) { cursor = .newSet(next) }
        enqueue([op])
    }

    func join(breakID: RecordID, at cursor: Cursor) {
        guard var l = log else { return }
        // The gap becomes a seam inside the set: tapping it again splits it.
        if case .newSet(let first) = cursor, let prev = previousTune(before: first) { self.cursor = .after(prev) }
        guard let op = l.join(breakID: breakID) else { return }
        log = l
        enqueue([op])
    }

    func remove(_ id: RecordID) {
        guard var l = log else { return }
        if selected == id { selected = nil }
        // A cursor anchored on the row moves to the row before it (or the end).
        if cursor == .after(id) || cursor == .before(id) {
            cursor = previousTune(before: id).map { .after($0) } ?? .end
        }
        guard let op = l.remove(id) else { return }
        log = l
        enqueue([op])
    }

    func confirm(_ id: RecordID) {
        guard var l = log, let op = l.confirm(id) else { return }
        log = l
        selected = nil
        enqueue([op])
    }

    // MARK: - Selection mode

    func setSelecting(_ on: Bool) {
        selecting = on
        picked = []
        selected = nil
        drag = nil
    }

    func togglePicked(_ id: RecordID) {
        if picked.contains(id) { picked.remove(id) } else { picked.insert(id) }
    }

    func pickAll() {
        guard let log else { return }
        picked = Set(Selection.selectableIDs(LogState.segmentByBreaks(log.ordered)))
    }

    /// Move a block to a drop target; the cursor lands after it, as on the web.
    func move(_ block: Selection.DragBlock, to target: Selection.DropTarget) {
        guard var l = log else { return }
        let op = l.move(block, to: target)
        log = l
        if let last = block.tuneIDs.last { cursor = .after(last) }
        enqueue([op])
    }

    /// Delete the picked tunes in one op, with Undo.
    func deletePicked() {
        guard var l = log, let (op, rows) = l.removeMany(Array(picked)) else { return }
        log = l
        picked = []
        undoSeq += 1
        let seq = undoSeq
        undoable = (rows, rows.count)
        enqueue([op])
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(8))
            if self?.undoSeq == seq { self?.undoable = nil }
        }
    }

    func undoDelete() {
        guard let u = undoable, var l = log else { return }
        undoable = nil
        guard let op = l.restore(u.rows) else { return }
        log = l
        enqueue([op])
    }

    func copyPicked() {
        guard let log, let copy = Selection.serializeClipboard(LogState.segmentByBreaks(log.ordered), selected: picked)
        else { return }
        lastCopy = copy
        UIPasteboard.general.string = copy.text
        let tunes = copy.rich.reduce(0) { $0 + $1.count }
        say("Copied \(tunes) tune\(tunes == 1 ? "" : "s") in \(copy.rich.count) set\(copy.rich.count == 1 ? "" : "s")")
    }

    /// Paste at the cursor: our own last copy with its links, the old logger's JSON,
    /// or plain text (lines are sets, commas are tunes).
    func paste() {
        let text = UIPasteboard.general.string
        guard let plan = Selection.parseClipboard(text, lastCopy: lastCopy) ?? lastCopy.map({ (.internal, $0.rich) }),
            !plan.sets.isEmpty, var l = log
        else {
            say("Nothing to paste")
            return
        }
        let ops = l.paste(plan.sets, at: cursor)
        log = l
        enqueue(ops)
        let tunes = plan.sets.reduce(0) { $0 + $1.count }
        say("Pasted \(tunes) tune\(tunes == 1 ? "" : "s") in \(plan.sets.count) set\(plan.sets.count == 1 ? "" : "s")")
    }

    /// Who started a set (nil clears it).
    func setStarter(of setTunes: [LogRecord], person: JSONValue?) {
        guard var l = log else { return }
        let id = person?["person_id"]?.intValue
        guard let op = l.setStarter(of: setTunes, personID: id, name: person.map(Self.starterName)) else { return }
        log = l
        enqueue([op])
    }

    /// Assign every set holding a picked tune to one person (or clear it).
    func assignPicked(to person: JSONValue?) {
        guard let log else { return }
        let sets = LogState.segmentByBreaks(log.ordered).filter { $0.tunes.contains { $0.recordID.map(picked.contains) ?? false } }
        for set in sets { setStarter(of: set.tunes, person: person) }
        let n = sets.count
        let name = person?["display_name"]?.stringValue ?? ""
        say(person == nil ? "Cleared the starter on \(n) set\(n == 1 ? "" : "s")" : "Assigned \(n) set\(n == 1 ? "" : "s") to \(name)")
    }

    /// "Sarah O": the web's starterAbbrev.
    static func starterName(_ p: JSONValue) -> String {
        let first = p["first_name"]?.stringValue ?? ""
        guard !first.isEmpty else { return p["display_name"]?.stringValue ?? "" }
        if let last = p["last_name"]?.stringValue, let initial = last.first { return "\(first) \(initial)" }
        return first
    }

    /// Someone else changed the log: a line saying so, and their rows flash.
    private func noteRemote(_ d: JSONValue) {
        let actor = d["actor"]?["person_id"]?.intValue
        let color = actor.flatMap { a in roster.first { $0["person_id"]?.intValue == a }?["arrival_seq"]?.intValue }
        if let text = People.activityText(d, me: me, viewing: !editing) {
            activitySeq += 1
            let item = Activity(id: activitySeq, text: text, color: color)
            activities = Array((activities + [item]).suffix(People.maxActivity))
            Task { [weak self] in
                try? await Task.sleep(for: .seconds(4))
                self?.activities.removeAll { $0.id == item.id }
            }
        }
        // As the web: a tune someone else added or changed, or moved, rings in their colour.
        guard let actor, actor != me else { return }
        var ids: [RecordID] = []
        switch d["op_type"]?.stringValue {
        case "add_tune", "change_tune", "set_confidence":
            if let id = RecordID(d["record"]?["session_instance_tune_id"]) { ids = [id] }
        case "move_tunes":
            ids = (d["moved_ids"]?.arrayValue ?? []).compactMap { RecordID($0) }
        default: break
        }
        for id in ids {
            flashes[id] = color
            Task { [weak self] in
                try? await Task.sleep(for: .seconds(1.4))
                self?.flashes.removeValue(forKey: id)
            }
        }
    }

    /// Me, as the night knows me (for my own rows and my own typing).
    var me: Int? { night?["current_person"]?["person_id"]?.intValue }

    /// The session tracks attendance (spec 039); set starters need it too.
    var trackAttendance: Bool { night?["track_attendance"]?.boolValue ?? true }

    // MARK: - Typing (spec 024 §F): others see "X is typing…"

    @ObservationIgnored private var typingSentAt: Date?

    /// The box's text changed: say so at most every 3 seconds (the server forgets after
    /// 10), and say when it's empty again.
    func typed(_ text: String) {
        guard editing else { return }
        if text.trimmingCharacters(in: .whitespaces).isEmpty {
            stopTyping()
        } else if typingSentAt.map({ Date().timeIntervalSince($0) > 3 }) ?? true {
            typingSentAt = Date()
            Task { await sendTyping(true) }
        }
    }

    /// Committed, cleared, or the box let go.
    func stopTyping() {
        guard typingSentAt != nil else { return }
        typingSentAt = nil
        Task { await sendTyping(false) }
    }

    private func sendTyping(_ on: Bool) async {
        guard !app.simulatedOffline, let base = try? await app.streamingBase() else { return }
        var request = app.authorized(URLRequest(url: base.appending(path: "live/instances/\(instanceID)/typing")))
        request.httpMethod = "POST"
        request.timeoutInterval = 10
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        // The anchor is the log's last row, as the web sends it.
        let anchor = log?.ordered.last?["session_instance_tune_id"] ?? .null
        request.httpBody = try? JSONEncoder().encode(JSONValue.object(["typing": .bool(on), "anchor": anchor]))
        _ = try? await URLSession.shared.data(for: request)  // best effort
    }

    // MARK: - The log's details (spec 052 §B15): need a connection, as on the web

    /// Notes, the date and times, the name, complete or not: one op each, answered
    /// before it shows (the stream's echo updates everyone else). Returns the answer, or
    /// nil with `why` set.
    func metaOp(_ type: String, _ fields: [String: JSONValue], label: String) async -> (answer: JSONValue?, why: String?) {
        var body = fields
        body["op_id"] = .string(LiveLog.newOpID())
        body["op_type"] = .string(type)
        do {
            let (code, answer) = try await app.postJSON("/api/live/instances/\(instanceID)/ops", body: .object(body))
            if code != 200 {
                return (nil, answer["message"]?.stringValue ?? answer["error"]?.stringValue ?? "That didn't save.")
            }
            if answer["rejected"].isTruthy || answer["success"] == false {
                return (answer, answer["message"]?.stringValue ?? answer["reason"]?.stringValue ?? "That didn't save.")
            }
            var patched = answer
            if case .object(var o) = patched, o["op_type"] == nil { o["op_type"] = .string(type); patched = .object(o) }
            for (k, v) in LogState.metaChanges(patched) { log?.meta[k] = v }
            return (answer, nil)
        } catch {
            return (nil, "You're offline — \(label) needs a connection.")
        }
    }

    /// Mark the log complete: editing ends for everyone, and the stream closes.
    func markComplete() async -> String? {
        let r = await metaOp("mark_complete", [:], label: "marking complete")
        guard r.why == nil else { return r.why }
        log?.meta["log_complete"] = true
        setEditing(false)
        stream?.cancel()
        watchdog?.cancel()
        status = .finished
        return nil
    }

    /// Re-open a completed log: it goes live again.
    func reopen() async -> String? {
        let r = await metaOp("mark_incomplete", [:], label: "re-opening")
        guard r.why == nil else { return r.why }
        log?.meta["log_complete"] = false
        running = true
        await connect()
        return nil
    }

    // MARK: - Attendance (spec 034): needs a connection, as on the web

    func checkIn(_ person: JSONValue) async {
        guard let id = person["person_id"]?.intValue else { return }
        await attendanceOp(["op_type": "attendance_add", "person_id": JSONValue(id)], label: "Check in")
    }

    func checkOut(_ person: JSONValue) async {
        guard let id = person["person_id"]?.intValue else { return }
        await attendanceOp(["op_type": "attendance_remove", "person_id": JSONValue(id)], label: "Remove")
    }

    /// Add someone new to the session, checked in. Returns them.
    @discardableResult
    func createPerson(first: String, last: String, email: String, instruments: [String]) async -> JSONValue? {
        await attendanceOp(
            [
                "op_type": "attendance_create_person", "first_name": .string(first), "last_name": .string(last),
                "email": email.isEmpty ? .null : .string(email), "instruments": .array(instruments.map(JSONValue.string)),
            ], label: "Add person")
    }

    @discardableResult
    private func attendanceOp(_ fields: [String: JSONValue], label: String) async -> JSONValue? {
        var body = fields
        body["op_id"] = .string(LiveLog.newOpID())
        do {
            let (code, answer) = try await app.postJSON("/api/live/instances/\(instanceID)/ops", body: .object(body))
            if code != 200 || answer["success"] == false {
                notice = answer["message"]?.stringValue ?? answer["error"]?.stringValue ?? "\(label) didn't work."
                return nil
            }
            await loadPeople()
            return answer["person"]
        } catch {
            notice = "You're offline — \(label.lowercased()) needs a connection."
            return nil
        }
    }

    func loadPeople() async {
        guard let p = try? await app.getJSON("/api/live/instances/\(instanceID)/people") else { return }
        people = p["people"]?.arrayValue ?? []
        peopleLoaded = true
    }

    func say(_ text: String) {
        flash = text
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(3))
            if self?.flash == text { self?.flash = nil }
        }
    }

    private func nextTune(after id: RecordID) -> RecordID? {
        guard let ord = log?.ordered, let i = ord.firstIndex(where: { $0.recordID == id }) else { return nil }
        return ord[(i + 1)...].first { !$0.isBreak }?.recordID
    }

    private func previousTune(before id: RecordID) -> RecordID? {
        guard let ord = log?.ordered, let i = ord.firstIndex(where: { $0.recordID == id }) else { return nil }
        return ord[..<i].last { !$0.isBreak }?.recordID
    }

    /// A cursor on a row that has since been answered follows it to its real id; one
    /// whose row went away falls back to the end.
    private func settleCursor() {
        guard let l = log else { return }
        func fix(_ id: RecordID) -> RecordID? {
            let r = l.resolve(id)
            return l.records.contains { $0.recordID == r } ? r : nil
        }
        switch cursor {
        case .end: break
        case .after(let id): cursor = fix(id).map { .after($0) } ?? .end
        case .before(let id): cursor = fix(id).map { .before($0) } ?? .end
        case .newSet(let id): cursor = fix(id).map { .newSet($0) } ?? .end
        }
        if let sel = selected { selected = fix(sel) }
        // Rows removed elsewhere leave the selection.
        picked = Set(picked.compactMap(fix))
    }

    private func enqueue(_ ops: [PendingOp]) {
        notice = nil
        outbox += ops.map(\.opID)
        if waitingForNetwork {
            // Behind a queue: never jump ahead of changes already waiting.
            for op in ops { log?.markQueued(op.opID) }
            saveNow()
            return
        }
        if sender == nil { sender = Task { await drain() } }
    }

    /// Send what's waiting (the connection is back).
    private func flush() async {
        guard !outbox.isEmpty else { return }
        waitingForNetwork = false
        if sender == nil { sender = Task { await drain() } }
        await sender?.value
    }

    /// Send the outbox one op at a time, in order: a later op may anchor on an earlier
    /// one's row, and needs its real id. No connection: this op and everything behind
    /// it wait on the phone (the server knows an op_id it has seen, so a resend is
    /// safe). A refusal or a server error rolls the op back; a refusal of a change that
    /// waited offline is kept for review.
    private func drain() async {
        while let opID = outbox.first {
            guard let l = log, let op = l.pending[opID] else {
                outbox.removeFirst()  // settled already, by the stream's echo
                continue
            }
            guard let body = l.sendableBody(opID) else {
                // Its row never reached the server (that add was refused): nothing to send.
                log?.rollback(opID)
                outbox.removeFirst()
                if op.queued { flushRejects.append(reviewItem(op, why: "the tune it changed was never saved")) }
                continue
            }
            do {
                let (code, answer) = try await app.postJSON("/api/live/instances/\(instanceID)/ops", body: .object(body))
                outbox.removeFirst()
                if code == 200 {
                    if let reason = log?.settle(opID: opID, answer: answer) {
                        if op.queued { flushRejects.append(reviewItem(op, why: Self.reason(answer) ?? reason)) } else { notice = reason }
                    } else if op.queued {
                        synced += 1
                    }
                } else {
                    log?.rollback(opID)
                    notice = answer["message"]?.stringValue ?? answer["error"]?.stringValue ?? "That change wasn't saved."
                }
                settleCursor()
            } catch {
                waitingForNetwork = true
                for id in outbox { log?.markQueued(id) }
                saveNow()
                break
            }
        }
        sender = nil
        if outbox.isEmpty {
            if !flushRejects.isEmpty { review = flushRejects }
            if synced > 0 { say("↻ \(synced) synced") }
            flushRejects = []
            synced = 0
            saveNow()
        }
    }

    /// The web's reconciliation wording (RECONCILE_VERB / RECONCILE_REASON).
    private func reviewItem(_ op: PendingOp, why: String) -> ReviewItem {
        let verbs = [
            "add_tune": "Add", "change_tune": "Edit", "remove_tune": "Remove", "set_break": "Set break",
            "set_confidence": "Confirm", "attribute_set_starter": "Set starter", "edit_notes": "Edit notes",
            "move_tunes": "Move", "remove_tunes": "Bulk remove", "restore_tunes": "Restore",
        ]
        let verb = verbs[op.opType] ?? op.opType
        let name = op.label ?? op.prev.first?["name"]?.stringValue
        return ReviewItem(what: name.map { "\(verb) “\($0)”" } ?? verb, why: why)
    }

    static func reason(_ answer: JSONValue) -> String? {
        switch answer["reason"]?.stringValue {
        case "target_deleted", "target_removed": "it had already been removed"
        case "not_found": "it no longer exists"
        default: answer["message"]?.stringValue ?? answer["reason"]?.stringValue
        }
    }

    /// A silent half-open stream never errors. If nothing arrives for 45 seconds (the
    /// server pings every 15), start over: a fresh bootstrap closes any gap.
    private func startWatchdog() {
        watchdog?.cancel()
        watchdog = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                guard let self, !Task.isCancelled else { return }
                if Date().timeIntervalSince(self.lastAlive) > Self.watchdogSeconds {
                    self.status = .reconnecting
                    await self.connect()
                    return
                }
            }
        }
    }

    private func retryLater() {
        guard running else { return }
        failures += 1
        let delay = [2.0, 5, 10, 10][min(failures - 1, 3)]
        stream = Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard let self, !Task.isCancelled, self.running else { return }
            await self.connect()
        }
    }
}

extension AppModel {
    /// An authenticated request: the Bearer token and the client header, as the API
    /// client sends them.
    func authorized(_ request: URLRequest) -> URLRequest {
        var r = request
        if let token = auth.store.token() { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        r.setValue(ClientID.current, forHTTPHeaderField: "X-Ceol-Client")
        return r
    }

    /// A GET, as raw JSON: for payloads whose every field must survive (a night's records).
    func getJSON(_ path: String) async throws -> JSONValue {
        if simulatedOffline { throw URLError(.notConnectedToInternet) }
        var request = authorized(URLRequest(url: webURL(path)))
        request.timeoutInterval = 10
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try JSONDecoder().decode(JSONValue.self, from: data)
    }

    /// A POST of raw JSON: the status code and the body (an error's body too).
    func postJSON(_ path: String, body: JSONValue) async throws -> (Int, JSONValue) {
        if simulatedOffline { throw URLError(.notConnectedToInternet) }
        var request = authorized(URLRequest(url: webURL(path)))
        request.timeoutInterval = 10
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        let json = (try? JSONDecoder().decode(JSONValue.self, from: data)) ?? .null
        return (http.statusCode, json)
    }

    /// The streaming service's address (app-config's streaming_base_url).
    func streamingBase() async throws -> URL {
        if let cached = streamingURL { return cached }
        let config = try await auth.appConfig()
        guard let url = URL(string: config.streamingBaseUrl) else { throw URLError(.badURL) }
        streamingURL = url
        return url
    }
}
