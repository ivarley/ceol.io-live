// A night's log while you're logging it (plan Phase 5b), close to the web logger's
// edit mode (frontend/src/App.svelte, app.css):
//
//   - Seams between the rows place the cursor: "＋ start of set" before a set, "＋"
//     after a tune, "＋ new set" between two sets and after a closed last set. The
//     active one is a yellow line; mid-set it carries Split, between sets Join.
//   - Tapping a tune selects it: yellow, with ↑/↓ pills to insert above or below it,
//     and Info / Confirm / Remove under it.
//   - The composer at the bottom: the name, Log, and End set (an open set at the end) or
//     Done (a closed one).
//   - A set's label opens its tray: who started it (a picker) and who logged it.
//   - Select mode (spec 029): tap tunes to pick them; Copy, Paste, Delete (with Undo)
//     and Assign act on them; the ⠿ handle drags a tune, or the picked run it's part
//     of, to any seam (Selection.dropTargets says which are real moves).
//
// The native additions: swipe a tune left to remove it, and in select mode, press and
// hold a tune to drag it.

import CeolDesign
import CeolLogic
import SwiftUI

/// The insertion-point yellow (the web's --insert).
extension CeolTokens {
    static let insert = Color(red: 0.961, green: 0.773, blue: 0.094)  // #f5c518
    static let insertInk = Color(red: 0.165, green: 0.125, blue: 0.031)  // #2a2008
    static let attention = Color(red: 0.878, green: 0.702, blue: 0.255)  // #e0b341
}

/// The coordinate space of the night's scroll view: seams and the finger are both
/// measured in it, so a drag can find the nearest seam while the log scrolls under it.
let nightScrollSpace = "nightScroll"

/// A drag in progress: what's lifted, where it may land, and where the finger is.
struct LogDrag: Equatable {
    var block: Selection.DragBlock
    var targets: [Selection.DropTarget]
    /// "Kesh", or "3 tunes in 2 sets".
    var label: String
    var start: CGPoint
    var location: CGPoint
    var started = false
    var activeKey: String?
}

/// Each seam's frame in the scroll view, by its drop key.
struct SeamFrames: PreferenceKey {
    static let defaultValue: [String: CGRect] = [:]
    static func reduce(value: inout [String: CGRect], nextValue: () -> [String: CGRect]) {
        value.merge(nextValue()) { $1 }
    }
}

/// The sets of a night being logged.
struct EditableLog: View {
    let model: NightModel
    let log: LiveLog
    let trackStarters: Bool
    let timeZone: TimeZone?
    var onFocusComposer: () -> Void
    var onInfo: (LogRecord) -> Void
    /// Scroll the log by this much (a drag held near the top or bottom).
    var autoScroll: (CGFloat) -> Void
    /// The part of the scroll view you can see (not what's under the header or the
    /// bottom bar), in its own coordinates.
    var visible: ClosedRange<CGFloat>

    @State private var frames: [String: CGRect] = [:]
    @State private var openTray: RecordID?
    @State private var pickingStarterFor: [LogRecord]?
    @State private var ticker: Task<Void, Never>?

    var body: some View {
        let segments = LogState.segmentByBreaks(log.ordered)
        let endIsOpen = !(log.ordered.last?.isBreak ?? true)
        let active: Cursor? = model.selected == nil && !model.selecting ? model.cursor : nil
        VStack(spacing: 0) {
            if segments.isEmpty {
                Text("No tunes yet — log one below.").font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity).padding(.vertical, 32)
            }
            // The drag-only "new set" zones (here, and below an open end) keep their
            // place whenever there's a log, drawn only during a drag: nothing moves under
            // the finger as a drag starts.
            if !segments.isEmpty { dropStrip("top-new") }
            ForEach(Array(segments.enumerated()), id: \.offset) { si, seg in
                let first = seg.tunes[0].recordID!
                SetCard(
                    label: LogState.setLabel(seg.tunes), starter: trackStarters ? setStarter(seg.tunes) : nil,
                    onLabelTap: { withAnimation(.easeOut(duration: 0.15)) { openTray = openTray == first ? nil : first } }
                ) {
                    if openTray == first {
                        SetTray(
                            tunes: seg.tunes, trackStarters: trackStarters, timeZone: timeZone,
                            onPickStarter: { pickingStarterFor = seg.tunes })
                    }
                    seam(.before(first), label: "＋ start of set", active: active)
                    ForEach(Array(seg.tunes.enumerated()), id: \.element) { ti, t in
                        let id = t.recordID!
                        if model.selecting {
                            SelectRow(
                                record: t, picked: model.picked.contains(id),
                                dragging: model.drag?.block.recordIDs.contains(id) == true && model.drag?.started == true,
                                onTap: { if !t["_temp"].isTruthy { model.togglePicked(id) } },
                                drag: { phase in dragChanged(id, phase, segments: segments, endIsOpen: endIsOpen) })
                        } else {
                            editRow(t, id, segments: segments, endIsOpen: endIsOpen)
                            .remoteFlash(model, id)
                            .id(rowScrollID(id))
                        }
                        if endIsOpen && si == segments.count - 1 && ti == seg.tunes.count - 1 {
                            seam(.end, label: "＋", active: active, tall: true)
                            dropStrip("end-new")
                        } else if !t["_temp"].isTruthy {
                            seam(.after(id), label: "＋", active: active,
                                 pill: ti < seg.tunes.count - 1 ? ("Split", { model.split(after: id) }) : nil)
                        }
                    }
                }
                if si < segments.count - 1, let brk = seg.breakAfter {
                    let next = segments[si + 1].tunes[0].recordID!
                    seam(.newSet(next), label: "＋ new set", active: active, tall: true,
                         pill: ("Join", { model.join(breakID: brk, at: .newSet(next)) }))
                }
            }
            if !segments.isEmpty && !endIsOpen {
                seam(.end, label: "＋ new set", active: active, tall: true, hint: "NEW SET")
            }
        }
        .onPreferenceChange(SeamFrames.self) { frames = $0 }
        .sensoryFeedback(.selection, trigger: model.drag?.activeKey)
        .sheet(item: Binding(get: { pickingStarterFor.map(StarterChoice.init) }, set: { pickingStarterFor = $0?.tunes })) { choice in
            PersonPicker(model: model, mode: .starter(tunes: choice.tunes, current: setStarter(choice.tunes)))
                .onDisappear { openTray = nil }
        }
    }

    /// One tune while editing, with everything it can do.
    private func editRow(_ t: LogRecord, _ id: RecordID, segments: [LogSegment], endIsOpen: Bool) -> EditableRow {
        let resolving = t["_resolving"].isTruthy
        let temp = t["_temp"].isTruthy
        let color: Color? =
            t["tune_id"].isTruthy && !temp
            ? People.loggerColorIndex(t, me: model.me, roster: model.roster).map(Color.player) : nil
        return EditableRow(
            record: t, selected: model.selected == id,
            onTap: { tap(t) },
            onInsertAbove: { insertAbove(id) },
            onInsertBelow: { place(.after(id), endIsOpen: endIsOpen, segments: segments) },
            onInfo: { onInfo(t) },
            onConfirm: { model.confirm(id) },
            onRemove: {
                if resolving {
                    model.selected = nil
                    model.composer.cancelResolving(returnText: false)
                } else {
                    withAnimation(.easeOut(duration: 0.2)) { model.remove(id) }
                }
            },
            onEdit: {
                if resolving {
                    model.selected = nil
                    model.composer.cancelResolving(returnText: true)
                } else {
                    model.composer.startEdit(t)
                }
                onFocusComposer()
            },
            editing: model.composer.editingID == id,
            byColor: color,
            drag: temp ? nil : { phase in dragChanged(id, phase, segments: segments, endIsOpen: endIsOpen) })
    }

    private func seam(
        _ cursor: Cursor, label: String, active: Cursor?, tall: Bool = false, hint: String? = nil,
        pill: (String, () -> Void)? = nil
    ) -> some View {
        let key = LogState.seamKey(for: cursor)
        return Group {
            if model.selecting || model.drag != nil {
                DropSeam(state: dropState(key), tall: tall, newSet: key == "end" ? hint != nil : key.hasPrefix("inter:"))
            } else {
                Seam(label: label, isActive: active == cursor, tall: tall, hint: hint, pill: pill) {
                    model.selected = nil
                    model.cursor = cursor
                    onFocusComposer()
                }
            }
        }
        .background(frameReporter(key))
        .id(seamScrollID(key))
    }

    /// A drag-only zone: a new set at the very top, or below an open end.
    private func dropStrip(_ key: String) -> some View {
        let shown = model.drag?.started == true && model.drag?.targets.contains(where: { $0.key == key }) == true
        return DropSeam(state: shown ? dropState(key) : .idle, tall: true, newSet: true, label: shown ? "new set" : nil)
            .opacity(shown ? 1 : 0)
            .background(frameReporter(key))
            .accessibilityHidden(!shown)
    }

    private func frameReporter(_ key: String) -> some View {
        GeometryReader { g in
            Color.clear.preference(key: SeamFrames.self, value: [key: g.frame(in: .named(nightScrollSpace))])
        }
    }

    private func dropState(_ key: String) -> DropSeam.State {
        guard let drag = model.drag, drag.started else { return .idle }
        if drag.activeKey == key { return .active }
        return drag.targets.contains { $0.key == key } ? .eligible : .idle
    }

    // MARK: - Dragging

    enum DragPhase { case changed(CGPoint), ended }

    private func dragChanged(_ id: RecordID, _ phase: DragPhase, segments: [LogSegment], endIsOpen: Bool) {
        switch phase {
        case .changed(let p):
            if model.drag == nil {
                guard let block = Selection.dragBlock(log.ordered, selected: model.picked, grabbed: id) else { return }
                let targets = Selection.dropTargets(log.ordered, segments: segments, endIsOpen: endIsOpen, block: block.recordIDs)
                let label =
                    block.tuneIDs.count == 1
                    ? (log.records.first { $0.recordID == id }?["name"]?.stringValue ?? "1 tune")
                    : "\(block.tuneIDs.count) tunes" + (block.setCount > 1 ? " in \(block.setCount) sets" : "")
                model.drag = LogDrag(block: block, targets: targets, label: label, start: p, location: p)
                startTicker()
            }
            model.drag?.location = p
            if let d = model.drag, !d.started, hypot(p.x - d.start.x, p.y - d.start.y) >= 6 { model.drag?.started = true }
            hitTest()
        case .ended:
            ticker?.cancel()
            ticker = nil
            if let d = model.drag, d.started, let key = d.activeKey, let target = d.targets.first(where: { $0.key == key }) {
                withAnimation(.easeOut(duration: 0.2)) { model.move(d.block, to: target) }
            }
            model.drag = nil
        }
    }

    /// The nearest real target to the finger (distance to the seam's band, capped).
    private func hitTest() {
        guard let d = model.drag, d.started else { return }
        let y = d.location.y
        var best: (String, CGFloat)?
        for t in d.targets {
            guard let f = frames[t.key] else { continue }
            let dist = y < f.minY ? f.minY - y : (y > f.maxY ? y - f.maxY : 0)
            if dist <= 44, dist < (best?.1 ?? .infinity) { best = (t.key, dist) }
        }
        if model.drag?.activeKey != best?.0 { model.drag?.activeKey = best?.0 }
    }

    /// While a drag is held near the top or bottom, scroll, faster the closer it is.
    private func startTicker() {
        ticker?.cancel()
        ticker = Task { @MainActor in
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(16))
                guard let d = model.drag, d.started else { continue }
                let edge: CGFloat = 70
                let y = d.location.y
                if y < visible.lowerBound + edge {
                    autoScroll(-max(2, (visible.lowerBound + edge - y) / 5))
                } else if y > visible.upperBound - edge {
                    autoScroll(max(2, (y - (visible.upperBound - edge)) / 5))
                } else {
                    continue
                }
                hitTest()
            }
        }
    }

    // MARK: - Edit mode

    private func tap(_ t: LogRecord) {
        guard let id = t.recordID, !t["_temp"].isTruthy || t["_resolving"].isTruthy else { return }
        model.selected = model.selected == id ? nil : id
    }

    /// Mid-set: after the tune before. At a set's start: before this one.
    private func insertAbove(_ id: RecordID) {
        let ord = log.ordered
        if let i = ord.firstIndex(where: { $0.recordID == id }), i > 0, !ord[i - 1].isBreak, let prev = ord[i - 1].recordID {
            model.cursor = .after(prev)
        } else {
            model.cursor = .before(id)
        }
        model.selected = nil
        onFocusComposer()
    }

    /// After the last tune of an open set is the end.
    private func place(_ cursor: Cursor, endIsOpen: Bool, segments: [LogSegment]) {
        if case .after(let id) = cursor, endIsOpen, segments.last?.tunes.last?.recordID == id {
            model.cursor = .end
        } else {
            model.cursor = cursor
        }
        model.selected = nil
        onFocusComposer()
    }
}

/// A log row's scroll id, for bringing a selected row into view.
func rowScrollID(_ id: RecordID) -> String { "row-\(id)" }

/// A seam's scroll id (its seam key), for keeping the insertion point in view.
func seamScrollID(_ key: String) -> String { "seam-\(key)" }

/// The set a starter is being picked for, as a sheet item.
struct StarterChoice: Identifiable {
    let tunes: [LogRecord]
    var id: String { tunes.first?.recordID.map { "\($0)" } ?? "" }
}

/// A seam in select mode: nothing at rest; during a drag, a faint line where the block
/// may land and a thick one where it will.
struct DropSeam: View {
    enum State { case idle, eligible, active }
    let state: State
    var tall = false
    var newSet = false
    var label: String? = nil

    var body: some View {
        HStack(spacing: 8) {
            if state == .active && newSet {
                Text("NEW SET").font(.ceol(size: 11, weight: .semibold)).tracking(0.5).foregroundStyle(CeolTokens.insert)
            }
            if state != .idle {
                Capsule().fill(CeolTokens.insert.opacity(state == .active ? 1 : 0.3))
                    .frame(height: state == .active ? 5 : 2)
                    .shadow(color: CeolTokens.insert.opacity(state == .active ? 0.8 : 0), radius: 5)
            } else if let label {
                Text(label).font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
            }
        }
        .frame(maxWidth: .infinity)
        // The seams' own heights: nothing moves when a drag starts.
        .frame(height: label != nil || tall ? 22 : 12)
        .animation(.easeOut(duration: 0.12), value: state)
        .accessibilityHidden(state == .idle)
        .accessibilityIdentifier(state == .active ? "drop.active" : "drop")
    }
}

/// A tune in select mode: tap to pick it; drag the handle (or press and hold the row)
/// to move it.
struct SelectRow: View {
    let record: LogRecord
    let picked: Bool
    let dragging: Bool
    let onTap: () -> Void
    let drag: (EditableLog.DragPhase) -> Void

    var body: some View {
        let unlinked = !record["tune_id"].isTruthy
        let name = record["name"]?.stringValue ?? record["tune_id"]?.intValue.map { "#\($0)" } ?? "(unnamed)"
        HStack(spacing: 8) {
            Text(name)
                .font(.ceol(size: 19))
                .foregroundStyle(unlinked ? CeolTokens.attention : CeolTokens.textColor)
                .frame(maxWidth: .infinity, alignment: .leading)
            if picked {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(CeolTokens.primary).font(.system(size: 18))
            }
            if !record["_temp"].isTruthy {
                Text("⠿").font(.system(size: 22)).foregroundStyle(CeolTokens.textMuted)
                    .frame(width: 36, height: 40)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 0, coordinateSpace: .named(nightScrollSpace))
                            .onChanged { drag(.changed($0.location)) }
                            .onEnded { _ in drag(.ended) })
                    .accessibilityLabel("Drag to move")
                    .accessibilityIdentifier("row.grab")
            }
        }
        .padding(.vertical, 5).padding(.leading, 8)
        .background(
            RoundedRectangle(cornerRadius: 6).fill(picked ? CeolTokens.primary.opacity(0.14) : .clear)
        )
        .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(picked ? CeolTokens.primary.opacity(0.6) : .clear, lineWidth: 1))
        .opacity(dragging ? 0.35 : 1)
        .contentShape(Rectangle())
        .onTapGesture(perform: onTap)
        .gesture(
            LongPressGesture(minimumDuration: 0.35)
                .sequenced(before: DragGesture(minimumDistance: 0, coordinateSpace: .named(nightScrollSpace)))
                .onChanged { value in
                    if case .second(true, let d?) = value { drag(.changed(d.location)) }
                }
                .onEnded { _ in drag(.ended) })
        .accessibilityElement(children: .contain)
        .accessibilityAddTraits(picked ? [.isButton, .isSelected] : .isButton)
        .accessibilityIdentifier("select.row")
    }
}

/// A set's tray: who started it, and who logged it and when.
struct SetTray: View {
    let tunes: [LogRecord]
    let trackStarters: Bool
    let timeZone: TimeZone?
    /// nil: read-only (the view mode).
    var onPickStarter: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if trackStarters {
                HStack(spacing: 10) {
                    key("Started by")
                    let name = setStarter(tunes)
                    if let onPickStarter {
                        Button(name ?? "Not set", action: onPickStarter)
                            .font(.ceol(size: 14, weight: .semibold))
                            .foregroundStyle(name == nil ? CeolTokens.textMuted : CeolTokens.primary)
                            .padding(.horizontal, 12).padding(.vertical, 4)
                            .background(Color.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 8))
                            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("tray.starter")
                    } else {
                        Text(name ?? "Not set").font(.ceol(size: 14, weight: .semibold)).foregroundStyle(CeolTokens.textMuted)
                    }
                }
            }
            if let logged = loggedInfo(tunes, timeZone: timeZone) {
                HStack(spacing: 10) {
                    key("Logged by")
                    Text(logged).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textColor)
                }
            }
        }
        .padding(.horizontal, 10).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.03), in: RoundedRectangle(cornerRadius: 8))
        .padding(.bottom, 6)
    }

    private func key(_ text: String) -> some View {
        Text(text).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted).frame(width: 84, alignment: .leading)
    }
}

/// "Ian V, Sarah O · 9:42 PM": who logged a set's tunes, and the latest time (the
/// web's loggedInfo), in the session's own time zone.
func loggedInfo(_ tunes: [LogRecord], timeZone: TimeZone?) -> String? {
    var seen = Set<String>()
    var names: [String] = []
    var latest: Date?
    for t in tunes where !t.isBreak {
        if let who = t["logged_by"]?.stringValue, !who.isEmpty {
            let key = t["logged_by_person_id"]?.intValue.map(String.init) ?? who
            if seen.insert(key).inserted { names.append(who) }
        }
        if let at = t["logged_at"]?.stringValue, let d = HomeRulesISO.parse(at), latest.map({ d > $0 }) ?? true { latest = d }
    }
    guard !names.isEmpty || latest != nil else { return nil }
    let when = latest.map { d -> String in
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US")
        f.timeZone = timeZone ?? .current
        f.dateFormat = "h:mm a"
        return f.string(from: d)
    }
    return [names.isEmpty ? "someone" : names.joined(separator: ", "), when].compactMap { $0 }.joined(separator: " · ")
}

/// ISO dates as the server sends them (with or without fractions or a zone).
enum HomeRulesISO {
    static func parse(_ s: String) -> Date? {
        let a = ISO8601DateFormatter()
        a.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = a.date(from: s) { return d }
        if let d = ISO8601DateFormatter().date(from: s) { return d }
        // A naive UTC timestamp ("2026-09-29T21:42:10.123456").
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        for fmt in ["yyyy-MM-dd'T'HH:mm:ss.SSSSSS", "yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd HH:mm:ss.SSSSSS", "yyyy-MM-dd HH:mm:ss"] {
            f.dateFormat = fmt
            if let d = f.date(from: s) { return d }
        }
        return nil
    }
}

/// The bottom of the screen in select mode: the count, all or none, and the actions.
struct SelectionBar: View {
    let model: NightModel
    let trackStarters: Bool
    let onAssign: () -> Void

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text("\(model.picked.count) selected").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor)
                    .accessibilityIdentifier("select.count")
                Spacer()
                Button("Select all") { model.pickAll() }.accessibilityIdentifier("select.all")
                Text("·").foregroundStyle(CeolTokens.textMuted)
                Button("None") { model.picked = [] }.accessibilityIdentifier("select.none")
            }
            .font(.ceol(size: 15))
            .foregroundStyle(CeolTokens.primary)
            .buttonStyle(.plain)
            HStack(spacing: 8) {
                action("Copy", enabled: !model.picked.isEmpty) { model.copyPicked() }
                action("Paste", enabled: true) { model.paste() }
                action("Delete", enabled: !model.picked.isEmpty, danger: true) {
                    withAnimation(.easeOut(duration: 0.2)) { model.deletePicked() }
                }
                if trackStarters { action("Assign", enabled: !model.picked.isEmpty, action: onAssign) }
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
        .background(CeolTokens.bgColor)
    }

    private func action(_ title: String, enabled: Bool, danger: Bool = false, action: @escaping () -> Void) -> some View {
        Button(title, action: action)
            .font(.ceol(size: 15, weight: .semibold))
            .foregroundStyle(danger ? CeolTokens.danger : CeolTokens.primary)
            .frame(maxWidth: .infinity).frame(height: 42)
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            .opacity(enabled ? 1 : 0.4)
            .disabled(!enabled)
            .buttonStyle(.plain)
            .accessibilityIdentifier("select.\(title.lowercased())")
    }
}

/// Passing messages over the bottom bar: an Undo for a bulk delete, a confirmation.
struct LogToasts: View {
    let model: NightModel

    var body: some View {
        VStack(spacing: 6) {
            if model.queuedCount > 0 {
                QueuedBanner(model: model)
            }
            if let u = model.undoable {
                HStack {
                    Text("Deleted \(u.count) tune\(u.count == 1 ? "" : "s")").foregroundStyle(CeolTokens.textColor)
                    Spacer()
                    Button("Undo") { withAnimation { model.undoDelete() } }
                        .font(.ceol(size: 15, weight: .semibold)).foregroundStyle(CeolTokens.primary)
                        .accessibilityIdentifier("toast.undo")
                }
                .toastStyle()
            }
            if let flash = model.flash {
                Text(flash).foregroundStyle(CeolTokens.textColor).frame(maxWidth: .infinity, alignment: .leading)
                    .toastStyle()
                    .accessibilityIdentifier("toast.flash")
            }
        }
        .font(.ceol(size: 15))
        .padding(.horizontal, 16)
        .animation(.easeOut(duration: 0.2), value: model.flash)
    }
}

private extension View {
    func toastStyle() -> some View {
        padding(.horizontal, 14).padding(.vertical, 10)
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
    }
}

/// An insertion point: a faint "＋" until it's the cursor, then a yellow line.
struct Seam: View {
    let label: String
    let isActive: Bool
    var tall = false
    var hint: String? = nil
    var pill: (String, () -> Void)? = nil
    let onTap: () -> Void

    var body: some View {
        // The pill sits outside the seam's own tap area, so its tap is its own.
        HStack(spacing: 8) {
            line
            if isActive, let pill {
                Button(pill.0, action: pill.1)
                    .font(.ceol(size: 12, weight: .bold))
                    .foregroundStyle(CeolTokens.insertInk)
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(CeolTokens.insert, in: Capsule())
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("seam.\(pill.0.lowercased())")
            }
        }
        // Thin, as the web's; the cursor's own seam grows to hold its Split or Join.
        .frame(height: tall || (isActive && pill != nil) ? 22 : 12)
    }

    private var line: some View {
        HStack(spacing: 8) {
            if isActive {
                if let hint {
                    Text(hint).font(.ceol(size: 11, weight: .semibold)).tracking(0.5).foregroundStyle(CeolTokens.textColor)
                }
                Capsule().fill(hint == nil ? CeolTokens.insert : CeolTokens.textColor).frame(height: 3)
                    .shadow(color: (hint == nil ? CeolTokens.insert : CeolTokens.textColor).opacity(0.8), radius: 4)
            } else {
                // Invisible until it's the cursor, as on the web's phone layout: a tap
                // still places the cursor here. (The label stays for VoiceOver.)
                Color.clear
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .contentShape(Rectangle())
        .onTapGesture(perform: onTap)
        .accessibilityElement(children: .ignore)
        .accessibilityAddTraits(.isButton)
        .accessibilityLabel(isActive ? "Insertion point" : label.replacingOccurrences(of: "＋", with: "Insert").trimmingCharacters(in: .whitespaces))
        .accessibilityIdentifier(isActive ? "seam.active" : "seam")
    }
}

/// A tune while logging: tap to select, swipe left to remove.
struct EditableRow: View {
    let record: LogRecord
    let selected: Bool
    let onTap: () -> Void
    let onInsertAbove: () -> Void
    let onInsertBelow: () -> Void
    let onInfo: () -> Void
    let onConfirm: () -> Void
    let onRemove: () -> Void
    var onEdit: () -> Void = {}
    /// Being edited in the box below (yellow, like a selection, without the actions).
    var editing = false
    /// Someone else logged it: a faint border in their colour (the web's has-by).
    var byColor: Color? = nil
    /// The handle's drag (nil: no handle, e.g. an optimistic row).
    var drag: ((EditableLog.DragPhase) -> Void)? = nil

    @State private var dx: CGFloat = 0
    static let removeAt: CGFloat = 110

    var body: some View {
        let unlinked = !record["tune_id"].isTruthy
        let low = !record["_temp"].isTruthy && (record["confidence"]?.intValue).map { $0 <= 70 } ?? false
        let name = record["name"]?.stringValue ?? record["tune_id"]?.intValue.map { "#\($0)" } ?? "(unnamed)"
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                Text(name)
                    .font(.ceol(size: 19))
                    .foregroundStyle(unlinked || low ? CeolTokens.attention : CeolTokens.textColor)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if record["_resolving"].isTruthy {
                    ProgressView().controlSize(.small)
                    Text("resolving…").font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted)
                } else if record["_status"] == "queued" {
                    // Saved on the phone; sent when the connection is back.
                    Text("offline").font(.ceol(size: 12, weight: .semibold)).foregroundStyle(CeolTokens.warning)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .overlay(Capsule().strokeBorder(CeolTokens.warning.opacity(0.6), lineWidth: 1))
                        .accessibilityIdentifier("row.offline")
                } else if unlinked && !record["_temp"].isTruthy {
                    Text("⚠ unlinked").font(.ceol(size: 12, weight: .semibold)).foregroundStyle(CeolTokens.attention)
                }
                // The tune's details in one tap (the web's ⓘ), in its logger's colour.
                if !unlinked && !record["_temp"].isTruthy {
                    Button(action: onInfo) {
                        Image(systemName: "info.circle").font(.system(size: 17))
                            .foregroundStyle(byColor ?? CeolTokens.textMuted)
                            .frame(width: 30, height: 34)
                    }
                    .buttonStyle(.borderless)
                    .accessibilityLabel("Tune details")
                    .accessibilityIdentifier("row.info")
                }
                if let drag {
                    Text("⠿").font(.system(size: 22)).foregroundStyle(CeolTokens.textMuted)
                        .frame(width: 30, height: 34)
                        .contentShape(Rectangle())
                        .gesture(
                            DragGesture(minimumDistance: 0, coordinateSpace: .named(nightScrollSpace))
                                .onChanged { drag(.changed($0.location)) }
                                .onEnded { _ in drag(.ended) })
                        .accessibilityLabel("Drag to move")
                        .accessibilityIdentifier("row.grab")
                }
            }
            .padding(.vertical, 9).padding(.horizontal, 8)
            .background {
                if selected || editing {
                    RoundedRectangle(cornerRadius: 6).fill(CeolTokens.insert.opacity(0.14))
                        .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.insert, lineWidth: 1))
                        .shadow(color: CeolTokens.insert.opacity(0.18), radius: 6)
                } else if let byColor {
                    RoundedRectangle(cornerRadius: 6).strokeBorder(byColor.opacity(0.3), lineWidth: 1)
                }
            }
            .overlay(alignment: .topTrailing) {
                if selected && !record["_temp"].isTruthy { insertPill("↑", "Insert above", onInsertAbove).offset(y: -10) }
            }
            .overlay(alignment: .bottomTrailing) {
                if selected && !record["_temp"].isTruthy { insertPill("↓", "Insert below", onInsertBelow).offset(y: 10) }
            }
            .zIndex(1)
            .contentShape(Rectangle())
            .onTapGesture(perform: onTap)
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("log.row")
            .accessibilityAction(named: "Remove", onRemove)
            if selected {
                HStack(spacing: 6) {
                    if record["tune_id"].isTruthy { action("ⓘ Info", onInfo) }
                    if low { action("✓ Confirm", onConfirm) }
                    action("✎ Edit", onEdit)
                    action("🗑 Remove", onRemove, danger: true)
                }
                .padding(.top, 14).padding(.bottom, 8).padding(.horizontal, 2)
            }
        }
        .offset(x: dx)
        .background(alignment: .trailing) {
            if dx < 0 {
                HStack(spacing: 6) {
                    Image(systemName: "trash")
                    Text("Remove")
                }
                .font(.ceol(size: 14, weight: .semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .frame(maxHeight: .infinity)
                .frame(width: max(-dx, 0), alignment: .trailing)
                .background(CeolTokens.danger.opacity(-dx >= Self.removeAt ? 1 : 0.7), in: RoundedRectangle(cornerRadius: 6))
                .clipped()
            }
        }
        .gesture(
            SwipeLeft(
                onChange: { dx = min(0, $0) },
                onEnd: { end in
                    if end <= -Self.removeAt {
                        withAnimation(.easeOut(duration: 0.18)) { dx = -600 }
                        onRemove()
                    } else {
                        withAnimation(.spring(duration: 0.25)) { dx = 0 }
                    }
                }))
        .sensoryFeedback(.impact(weight: .medium), trigger: dx <= -Self.removeAt)
    }

    private func insertPill(_ glyph: String, _ label: String, _ tap: @escaping () -> Void) -> some View {
        Button(glyph, action: tap)
            .font(.ceol(size: 12, weight: .bold))
            .foregroundStyle(CeolTokens.insertInk)
            .frame(minWidth: 34).padding(.vertical, 4)
            .background(CeolTokens.insert, in: Capsule())
            .buttonStyle(.plain)
            .padding(.trailing, 10)
            .accessibilityLabel(label)
            .accessibilityIdentifier(label == "Insert above" ? "row.insertAbove" : "row.insertBelow")
    }

    private func action(_ title: String, _ tap: @escaping () -> Void, danger: Bool = false) -> some View {
        Button(title, action: tap)
            .font(.ceol(size: 14))
            .foregroundStyle(danger ? CeolTokens.danger : CeolTokens.textColor)
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(Color(red: 0.125, green: 0.125, blue: 0.165), in: RoundedRectangle(cornerRadius: 7))
            .overlay(RoundedRectangle(cornerRadius: 7).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            .buttonStyle(.plain)
            .accessibilityIdentifier("row.\(title.split(separator: " ").last!.lowercased())")
    }
}

/// A leftward pan that only starts when the finger moves mostly sideways, so the log
/// still scrolls under a vertical drag.
struct SwipeLeft: UIGestureRecognizerRepresentable {
    var onChange: (CGFloat) -> Void
    var onEnd: (CGFloat) -> Void

    func makeUIGestureRecognizer(context: Context) -> UIPanGestureRecognizer {
        let g = UIPanGestureRecognizer()
        g.delegate = context.coordinator
        return g
    }

    func makeCoordinator(converter: CoordinateSpaceConverter) -> Coordinator { Coordinator() }

    func handleUIGestureRecognizerAction(_ g: UIPanGestureRecognizer, context: Context) {
        let x = g.translation(in: g.view).x
        switch g.state {
        case .changed: onChange(x)
        case .ended: onEnd(x)
        case .cancelled, .failed: onEnd(0)
        default: break
        }
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        func gestureRecognizerShouldBegin(_ g: UIGestureRecognizer) -> Bool {
            guard let pan = g as? UIPanGestureRecognizer else { return false }
            let v = pan.velocity(in: pan.view)
            return v.x < 0 && abs(v.x) > abs(v.y) * 1.5
        }
    }
}

/// The bottom of the screen while logging (the web's dock): the suggestions above the
/// box, the box, Log (Save while editing), and one more: Cancel while editing, Search
/// while typing, End set on an open set at the end, or Done on a closed one.
struct LogComposer: View {
    let model: NightModel
    let endIsOpen: Bool
    var focused: FocusState<Bool>.Binding
    let onDone: () -> Void
    let onDeepSearch: () -> Void

    var body: some View {
        let c = model.composer
        VStack(spacing: 6) {
            if let notice = model.notice {
                Text(notice).font(.ceol(size: 14)).foregroundStyle(CeolTokens.errorText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(CeolTokens.errorBg, in: RoundedRectangle(cornerRadius: 8))
                    .onTapGesture { model.notice = nil }
                    .accessibilityIdentifier("log.notice")
            }
            if let m = model.merged {
                HStack {
                    Text("Merged with \(m.name) already in this set").foregroundStyle(CeolTokens.textColor)
                    Spacer()
                    Button("Keep both") { model.keepBoth() }.foregroundStyle(CeolTokens.primary)
                        .accessibilityIdentifier("merge.keepBoth")
                    Button { model.dismissMerged() } label: { Image(systemName: "xmark") }.foregroundStyle(CeolTokens.textMuted)
                }
                .font(.ceol(size: 14))
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 8))
            }
            if c.editingID != nil {
                HStack(spacing: 8) {
                    (Text("Editing ") + Text(c.editingName).bold() + Text(" — pick a match, or type a new name"))
                        .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textColor)
                    Spacer(minLength: 4)
                    // The whole catalogue, or thesession.org, for the tune being edited.
                    Button("Search", action: onDeepSearch)
                        .font(.ceol(size: 14, weight: .semibold)).foregroundStyle(CeolTokens.info)
                        .accessibilityIdentifier("edit.search")
                    Button("Unlink") { c.unlink() }
                        .font(.ceol(size: 14, weight: .semibold)).foregroundStyle(CeolTokens.attention)
                        .accessibilityIdentifier("edit.unlink")
                }
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(CeolTokens.insert.opacity(0.12), in: RoundedRectangle(cornerRadius: 8))
            }
            TypingLine(model: model)
                .font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityIdentifier("typing")
            Suggestions(model: model, focused: focused.wrappedValue)
            HStack(spacing: 8) {
                HStack(spacing: 0) {
                    TextField("", text: Binding(get: { c.text }, set: { c.text = $0 }), prompt: Text(prompt).foregroundStyle(CeolTokens.textMuted))
                        .font(.ceol(size: 17))
                        .foregroundStyle(CeolTokens.textColor)
                        .focused(focused)
                        .submitLabel(.done)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.words)
                        .disabled(c.resolving != nil)
                        .onSubmit(commit)
                        .accessibilityIdentifier("log.input")
                    if !c.text.isEmpty {
                        Button { c.text = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(CeolTokens.textMuted) }
                            .buttonStyle(.plain).accessibilityLabel("Clear entry")
                    }
                }
                .padding(.horizontal, 12).frame(height: 46)
                .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(c.ambiguous ? CeolTokens.danger : CeolTokens.borderColor, lineWidth: 1))
                let canLog = c.editingID != nil || c.ambiguous || !trimmed.isEmpty
                Button(c.editingID != nil ? "Save" : "Log", action: commit)
                    .font(.ceol(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 18).frame(height: 46)
                    .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
                    .opacity(canLog ? 1 : 0.4)
                    .disabled(!canLog)
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("log.commit")
                trailing
            }
        }
        .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 8)
        .background(CeolTokens.bgColor)
        // The box is locked while a placeholder waits; when it settles, the keyboard
        // comes back for the next tune.
        .onChange(of: c.resolving == nil) { _, free in if free { focused.wrappedValue = true } }
        // Letting go of the box stops "typing…" for the others.
        .onChange(of: focused.wrappedValue) { _, on in if !on { model.stopTyping() } }
    }

    @ViewBuilder private var trailing: some View {
        let c = model.composer
        if c.editingID != nil {
            outline("Cancel", id: "edit.cancel") { c.cancelEdit() }
        } else if !trimmed.isEmpty && c.resolving == nil {
            outline("Search", id: "log.search", color: CeolTokens.info, action: onDeepSearch)
        } else if trimmed.isEmpty && model.cursor == .end && model.selected == nil && c.resolving == nil {
            if endIsOpen {
                Button("End set") { model.endSet() }
                    .font(.ceol(size: 16, weight: .bold))
                    .foregroundStyle(CeolTokens.insertInk)
                    .padding(.horizontal, 16).frame(height: 46)
                    .background(CeolTokens.insert, in: RoundedRectangle(cornerRadius: 8))
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("log.endSet")
            } else {
                outline("Done", id: "log.done", action: onDone)
            }
        }
    }

    private func outline(_ title: String, id: String, color: Color = CeolTokens.textMuted, action: @escaping () -> Void) -> some View {
        Button(title, action: action)
            .font(.ceol(size: 16, weight: .semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 16).frame(height: 46)
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            .buttonStyle(.plain)
            .accessibilityIdentifier(id)
    }

    private var trimmed: String { model.composer.text.trimmingCharacters(in: .whitespacesAndNewlines) }

    private var prompt: String {
        let c = model.composer
        if c.resolving != nil { return c.ambiguous ? "Pick one above" : "Resolving…" }
        if c.editingID != nil { return "Re-pick or rename this tune…" }
        switch model.cursor {
        case .end: return "Tune name"
        case .newSet: return "Tune name — starts a new set"
        default: return "Tune name — goes at the yellow line"
        }
    }

    private func commit() {
        Task { await model.composer.commit() }
        // Keep the keyboard up for the next tune, as the web's composer does.
        focused.wrappedValue = true
    }
}

/// What shows above the box: a thesession.org tune, the likely next tune, the matches,
/// "no match", and while a placeholder waits, the choice to log the text as typed.
struct Suggestions: View {
    let model: NightModel
    let focused: Bool

    var body: some View {
        let c = model.composer
        let next = focused || c.text.isEmpty ? model.likelyNext : nil
        let showNext = next != nil && Composer.nextMatchesInput(next, c.text)
        let rows = showNext ? c.results.filter { $0["tune_id"]?.intValue != next?.tuneID } : c.results
        let any = c.theSessionID != nil || showNext || !rows.isEmpty || (c.noMatch && c.editingID == nil) || c.resolving != nil
        if any {
            VStack(spacing: 0) {
                if c.ambiguous, let r = c.resolving {
                    Text("“\(r.text)” matches several tunes — tap one, or log it as typed")
                        .font(.ceol(size: 13)).foregroundStyle(CeolTokens.attention)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                }
                ScrollView {
                    // Bottom-up, as the web's list: the best match sits nearest the box.
                    VStack(spacing: 0) {
                        ForEach(Array(items(c, next: showNext ? next : nil, rows: rows).reversed().enumerated()), id: \.offset) { _, item in
                            view(item, c)
                        }
                    }
                }
                .defaultScrollAnchor(.bottom)
                .frame(maxHeight: 240)
                .fixedSize(horizontal: false, vertical: true)
            }
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            .overlay(alignment: .topTrailing) {
                if c.searching { ProgressView().controlSize(.small).padding(8) }
            }
        }
    }

    private enum Item {
        case theSession(Int)
        case next(VocabTune)
        case result(JSONValue)
        case noMatch
        case asIs(String)
    }

    /// Nearest the box first: the thesession tune, the likely next, the matches, then
    /// "no match" or "log as typed".
    private func items(_ c: LogComposerModel, next: VocabTune?, rows: [JSONValue]) -> [Item] {
        var out: [Item] = []
        if let id = c.theSessionID { out.append(.theSession(id)) }
        if let next { out.append(.next(next)) }
        out += rows.map { .result($0) }
        if c.noMatch && c.editingID == nil && c.resolving == nil { out.append(.noMatch) }
        if let r = c.resolving { out.append(.asIs(r.text)) }
        return out
    }

    @ViewBuilder private func view(_ item: Item, _ c: LogComposerModel) -> some View {
        switch item {
        case .theSession(let id):
            row(title: "Tune #\(id) from thesession.org", detail: nil, id: "suggest.thesession") { c.logTheSession(id) }
        case .next(let next):
            HStack(spacing: 0) {
                row(title: next.name, detail: ["usually next", next.tuneType].compactMap { $0 }.joined(separator: " · "),
                    bold: true, id: "suggest.next") { c.pick(next.json) }
                Button { model.dismissLikelyNext() } label: {
                    Image(systemName: "xmark").font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted).frame(width: 40, height: 40)
                }
                .accessibilityLabel("Not this one")
            }
        case .result(let t):
            let detail = [
                t["tune_type"]?.stringValue, t["in_session_tune"] == true ? "in session" : nil,
                t["abc"] == true ? "♪ notation" : nil,
            ].compactMap { $0 }.joined(separator: " · ")
            row(title: t["name"]?.stringValue ?? "", detail: detail.isEmpty ? nil : detail, id: "suggest.row") { c.pick(t) }
        case .noMatch:
            Text("No tunes match your search").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                .frame(maxWidth: .infinity, alignment: .leading).padding(12)
        case .asIs(let text):
            row(title: "Log “\(text)” as typed", detail: nil, id: "suggest.asIs", color: CeolTokens.primary) { c.logAsIs() }
        }
    }

    private func row(title: String, detail: String?, bold: Bool = false, id: String, color: Color = CeolTokens.textColor,
                     action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Text(title).font(.ceol(size: 16, weight: bold ? .semibold : .regular)).foregroundStyle(color)
                    .lineLimit(1)
                Spacer(minLength: 4)
                if let detail {
                    Text(detail).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted).lineLimit(1)
                }
            }
            .padding(.horizontal, 12).frame(minHeight: 42)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }
}

/// Changes waiting on the phone (the web's "⏳ N changes queued — offline").
struct QueuedBanner: View {
    let model: NightModel

    var body: some View {
        let n = model.queuedCount
        Text("⏳ \(n) change\(n == 1 ? "" : "s") queued — \(model.status == .live ? "syncing…" : "offline")")
            .font(.ceol(size: 14)).foregroundStyle(CeolTokens.warning)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(CeolTokens.warning.opacity(0.1), in: RoundedRectangle(cornerRadius: 8))
            .background(CeolTokens.bgColor, in: RoundedRectangle(cornerRadius: 8))
            .accessibilityIdentifier("queued.banner")
    }
}

/// Offline changes the server refused once they were sent (the web's reconciliation
/// review): what, and why, and an OK.
struct ReviewSheet: View {
    @Environment(\.dismiss) private var dismiss
    let items: [NightModel.ReviewItem]

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(items) { item in
                        Text("\(item.what) — \(item.why)").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor)
                    }
                } header: {
                    Text("\(items.count) change\(items.count == 1 ? "" : "s") you made offline couldn’t be applied when you reconnected — usually because someone else changed the same tune first.")
                        .font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted).textCase(nil)
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.drawerBg)
            .navigationTitle("Some offline changes didn’t stick")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Got it") { dismiss() }.accessibilityIdentifier("review.ok") }
            }
        }
        .ceolDrawer([.medium, .large])
    }
}
