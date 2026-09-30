// The night's audio on screen (spec 050 read side), as the web logger shows it: a ▶ on
// each timestamped tune (❚❚ while it plays), a ▶ / ■ on the set, the tune being heard
// tinted green (not the insertion point's yellow: the two can be on different rows), and
// the player: a one-line bar that opens into the transport.

import CeolDesign
import CeolLogic
import SwiftUI

/// A tune's ▶ / ❚❚.
struct TunePlayButton: View {
    let playing: Bool
    let paused: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: playing && !paused ? "pause.fill" : "play.fill")
                .font(.system(size: 12))
                .foregroundStyle(playing ? CeolTokens.primary : CeolTokens.textMuted)
                .frame(width: 30, height: 34)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .accessibilityLabel(playing && !paused ? "Pause" : "Play this tune")
        .accessibilityIdentifier("tune.play")
    }
}

extension View {
    /// The tune being heard: a green tint and edge.
    func nowPlaying(_ on: Bool) -> some View {
        background {
            if on {
                RoundedRectangle(cornerRadius: 6).fill(CeolTokens.primary.opacity(0.12))
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.primary.opacity(0.45), lineWidth: 1))
            }
        }
    }
}

/// The player: collapsed, play/pause, the tune and its time, and ×; open, the tune's own
/// scrubber, previous / play / next / stop, Repeat 1, Auto-continue and HD.
struct PlayerBar: View {
    let player: NightPlayer
    /// The playing tune's name.
    let name: String
    @State private var scrubbing = false
    @State private var scrubMs: Double = 0

    var body: some View {
        VStack(spacing: 0) {
            if player.open { transport }
            HStack(spacing: 6) {
                Button { player.togglePlayPause() } label: {
                    Image(systemName: player.paused ? "play.fill" : "pause.fill").foregroundStyle(CeolTokens.primary)
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(player.paused ? "Play" : "Pause")
                .accessibilityIdentifier("player.toggle")
                Button { withAnimation(.easeOut(duration: 0.2)) { player.open.toggle() } } label: {
                    HStack(spacing: 6) {
                        Text(name).lineLimit(1).foregroundStyle(CeolTokens.textColor)
                        Spacer(minLength: 4)
                        Text("\(Segments.formatClock(player.playhead)) / \(Segments.formatClock(player.tuneLengthMs))")
                            .monospacedDigit().foregroundStyle(CeolTokens.textMuted).font(.ceol(size: 12))
                        Image(systemName: player.open ? "chevron.down" : "chevron.up").font(.system(size: 11))
                            .foregroundStyle(CeolTokens.textMuted)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(player.open ? "Hide controls" : "Show controls")
                .accessibilityIdentifier("player.open")
                Button { player.stop() } label: {
                    Image(systemName: "xmark").foregroundStyle(CeolTokens.textMuted).frame(width: 36, height: 36)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Stop")
                .accessibilityIdentifier("player.stop")
            }
            .padding(.horizontal, 6)
            .font(.ceol(size: 14))
        }
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("player")
    }

    private var transport: some View {
        let length = max(1, player.tuneLengthMs)
        let value = scrubbing ? scrubMs : min(player.playhead, length)
        return VStack(spacing: 8) {
            // Scoped to this tune: the recording is hours long, the tune a minute or two.
            Slider(
                value: Binding(get: { value }, set: { scrubMs = $0 }), in: 0...length,
                onEditingChanged: { editing in
                    scrubbing = editing
                    if !editing { player.seek(toMs: scrubMs) }
                }
            )
            .tint(CeolTokens.primary)
            .accessibilityLabel("Position within this tune")
            HStack {
                Text(Segments.formatClock(value))
                Spacer()
                Text("\(player.idx + 1) of \(player.queue.count)")
                Spacer()
                Text("−\(Segments.formatClock(max(0, player.tuneLengthMs - value)))")
            }
            .font(.ceol(size: 12)).monospacedDigit().foregroundStyle(CeolTokens.textMuted)
            HStack(spacing: 18) {
                transportButton("backward.end.fill", "Previous tune") { player.previous() }
                transportButton(player.paused ? "play.fill" : "pause.fill", player.paused ? "Play" : "Pause", big: true) {
                    player.togglePlayPause()
                }
                transportButton("forward.end.fill", "Next tune") { player.next() }
                    .disabled(player.idx + 1 >= player.queue.count)
                transportButton("stop.fill", "Stop") { player.stop() }
            }
            HStack(spacing: 8) {
                mode("Repeat 1", on: player.repeatOne) { player.repeatOne.toggle() }
                mode("Auto-continue", on: player.autoContinue) { player.autoContinue.toggle() }
                if player.canSwitchHD {
                    let size = player.masterSize.map { " \(Self.megabytes($0))" } ?? ""
                    mode(player.hdOn ? "HD" : "HD\(size)", on: player.hdOn) { player.switchSource(player.hdOn ? "proxy" : "master") }
                }
            }
        }
        .padding(.horizontal, 12).padding(.top, 12).padding(.bottom, 4)
    }

    private func transportButton(_ symbol: String, _ label: String, big: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol).font(.system(size: big ? 20 : 15))
                .foregroundStyle(big ? CeolTokens.primary : CeolTokens.textColor)
                .frame(width: big ? 60 : 40, height: 40)
                .overlay { if big { RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1) } }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }

    private func mode(_ title: String, on: Bool, action: @escaping () -> Void) -> some View {
        Button(title, action: action)
            .font(.ceol(size: 12, weight: .semibold))
            .foregroundStyle(on ? CeolTokens.primary : CeolTokens.textMuted)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .background(on ? CeolTokens.primary.opacity(0.1) : .clear, in: Capsule())
            .overlay(Capsule().strokeBorder(on ? CeolTokens.primary : CeolTokens.borderColor, lineWidth: 1))
            .buttonStyle(.plain)
            .accessibilityAddTraits(on ? .isSelected : [])
    }

    /// "43 MB": the listener's basis for choosing HD.
    static func megabytes(_ n: Int) -> String {
        let mb = Double(n) / 1e6
        return mb >= 1000 ? String(format: "%.1f GB", mb / 1000) : "\(Int(mb.rounded())) MB"
    }
}
