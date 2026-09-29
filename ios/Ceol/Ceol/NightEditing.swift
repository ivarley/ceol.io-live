// A night's log while you're logging it (plan Phase 5b.1), close to the web logger's
// edit mode (frontend/src/App.svelte, app.css):
//
//   - Seams between the rows place the cursor: "＋ start of set" before a set, "＋"
//     after a tune, "＋ new set" between two sets and after a closed last set. The
//     active one is a yellow line; mid-set it carries Split, between sets Join.
//   - Tapping a tune selects it: yellow, with ↑/↓ pills to insert above or below it,
//     and Info / Confirm / Remove under it.
//   - The composer at the bottom: the name, Log, and End set (an open set at the end) or
//     Done (a closed one).
//
// The native addition: swipe a tune left to remove it.

import CeolDesign
import CeolLogic
import SwiftUI

/// The insertion-point yellow (the web's --insert).
extension CeolTokens {
    static let insert = Color(red: 0.961, green: 0.773, blue: 0.094)  // #f5c518
    static let insertInk = Color(red: 0.165, green: 0.125, blue: 0.031)  // #2a2008
    static let attention = Color(red: 0.878, green: 0.702, blue: 0.255)  // #e0b341
}

/// The sets of a night being logged.
struct EditableLog: View {
    let model: NightModel
    let log: LiveLog
    let trackStarters: Bool
    var onFocusComposer: () -> Void
    var onInfo: (LogRecord) -> Void

    var body: some View {
        let segments = LogState.segmentByBreaks(log.ordered)
        let endIsOpen = !(log.ordered.last?.isBreak ?? true)
        let active: Cursor? = model.selected == nil ? model.cursor : nil
        VStack(spacing: 0) {
            if segments.isEmpty {
                Text("No tunes yet — log one below.").font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                    .frame(maxWidth: .infinity).padding(.vertical, 32)
            }
            ForEach(Array(segments.enumerated()), id: \.offset) { si, seg in
                let first = seg.tunes[0].recordID!
                SetCard(label: LogState.setLabel(seg.tunes), starter: trackStarters ? setStarter(seg.tunes) : nil) {
                    seam(.before(first), label: "＋ start of set", active: active)
                    ForEach(Array(seg.tunes.enumerated()), id: \.element) { ti, t in
                        let id = t.recordID!
                        EditableRow(
                            record: t, selected: model.selected == id,
                            onTap: { tap(t) },
                            onInsertAbove: { insertAbove(id) },
                            onInsertBelow: { place(.after(id), endIsOpen: endIsOpen, segments: segments) },
                            onInfo: { onInfo(t) },
                            onConfirm: { model.confirm(id) },
                            onRemove: { withAnimation(.easeOut(duration: 0.2)) { model.remove(id) } })
                        if endIsOpen && si == segments.count - 1 && ti == seg.tunes.count - 1 {
                            seam(.end, label: "＋", active: active, tall: true)
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
    }

    private func seam(
        _ cursor: Cursor, label: String, active: Cursor?, tall: Bool = false, hint: String? = nil,
        pill: (String, () -> Void)? = nil
    ) -> some View {
        Seam(label: label, isActive: active == cursor, tall: tall, hint: hint, pill: pill) {
            model.selected = nil
            model.cursor = cursor
            onFocusComposer()
        }
    }

    private func tap(_ t: LogRecord) {
        guard let id = t.recordID, !t["_temp"].isTruthy else { return }
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
        .frame(height: tall ? 26 : 18)
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
                Text(label).font(.ceol(size: 12)).foregroundStyle(CeolTokens.textMuted.opacity(0.6))
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
                if unlinked && !record["_temp"].isTruthy {
                    Text("⚠ unlinked").font(.ceol(size: 12, weight: .semibold)).foregroundStyle(CeolTokens.attention)
                }
            }
            .padding(.vertical, 9).padding(.horizontal, 8)
            .background {
                if selected {
                    RoundedRectangle(cornerRadius: 6).fill(CeolTokens.insert.opacity(0.14))
                        .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.insert, lineWidth: 1))
                        .shadow(color: CeolTokens.insert.opacity(0.18), radius: 6)
                }
            }
            .overlay(alignment: .topTrailing) { if selected { insertPill("↑", "Insert above", onInsertAbove).offset(y: -10) } }
            .overlay(alignment: .bottomTrailing) { if selected { insertPill("↓", "Insert below", onInsertBelow).offset(y: 10) } }
            .zIndex(1)
            .contentShape(Rectangle())
            .onTapGesture(perform: onTap)
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.isButton)
            .accessibilityIdentifier("log.row")
            .accessibilityAction(named: "Remove", onRemove)
            if selected {
                HStack(spacing: 6) {
                    if record["tune_id"].isTruthy { action("ⓘ Info", onInfo) }
                    if low { action("✓ Confirm", onConfirm) }
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

/// The bottom of the screen while logging: the name, Log, and End set or Done.
struct LogComposer: View {
    let model: NightModel
    let endIsOpen: Bool
    @Binding var text: String
    var focused: FocusState<Bool>.Binding
    let onDone: () -> Void

    var body: some View {
        VStack(spacing: 6) {
            if let notice = model.notice {
                Text(notice).font(.ceol(size: 14)).foregroundStyle(CeolTokens.errorText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(CeolTokens.errorBg, in: RoundedRectangle(cornerRadius: 8))
                    .onTapGesture { model.notice = nil }
                    .accessibilityIdentifier("log.notice")
            }
            HStack(spacing: 8) {
                HStack(spacing: 0) {
                    TextField("", text: $text, prompt: Text(prompt).foregroundStyle(CeolTokens.textMuted))
                        .font(.ceol(size: 17))
                        .foregroundStyle(CeolTokens.textColor)
                        .focused(focused)
                        .submitLabel(.done)
                        .autocorrectionDisabled()
                        .onSubmit(commit)
                        .accessibilityIdentifier("log.input")
                    if !text.isEmpty {
                        Button { text = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(CeolTokens.textMuted) }
                            .buttonStyle(.plain).accessibilityLabel("Clear entry")
                    }
                }
                .padding(.horizontal, 12).frame(height: 46)
                .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                Button("Log", action: commit)
                    .font(.ceol(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 18).frame(height: 46)
                    .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
                    .opacity(trimmed.isEmpty ? 0.4 : 1)
                    .disabled(trimmed.isEmpty)
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("log.commit")
                if trimmed.isEmpty && model.cursor == .end && model.selected == nil {
                    if endIsOpen {
                        Button("End set") { model.endSet() }
                            .font(.ceol(size: 16, weight: .bold))
                            .foregroundStyle(CeolTokens.insertInk)
                            .padding(.horizontal, 16).frame(height: 46)
                            .background(CeolTokens.insert, in: RoundedRectangle(cornerRadius: 8))
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("log.endSet")
                    } else {
                        Button("Done", action: onDone)
                            .font(.ceol(size: 16, weight: .semibold))
                            .foregroundStyle(CeolTokens.textMuted)
                            .padding(.horizontal, 16).frame(height: 46)
                            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("log.done")
                    }
                }
            }
        }
        .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 8)
        .background(CeolTokens.bgColor)
    }

    private var trimmed: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }

    private var prompt: String {
        switch model.cursor {
        case .end: "Tune name"
        case .newSet: "Tune name — starts a new set"
        default: "Tune name — goes at the yellow line"
        }
    }

    private func commit() {
        guard !trimmed.isEmpty else { return }
        model.logTune(trimmed)
        text = ""
        // Keep the keyboard up for the next tune, as the web's composer does.
        focused.wrappedValue = true
    }
}
