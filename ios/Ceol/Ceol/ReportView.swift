// Report, from the "⋯" menu on every screen (App Store guideline 1.2), the app's twin of
// the web's /report: what's wrong, a few words, and the screen's web address, sent to
// POST /api/report, which emails Ceol's support.

import CeolDesign
import CeolSession
import SwiftUI

struct ReportView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let target: ReportTarget

    @State private var reason: String?
    @State private var message = ""
    @State private var busy = false
    @State private var sent = false
    @State private var error: String?

    private static let reasons: [(String, LocalizedStringKey)] = [
        ("offensive", "Offensive or inappropriate"),
        ("wrong", "Wrong or spam"),
        ("broken", "Something's broken"),
        ("other", "Something else"),
    ]

    private var canSend: Bool {
        guard let reason, !busy else { return false }
        return reason != "other" || !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        NavigationStack {
            Form {
                if sent {
                    Section {
                        Text("Thanks. Your report has gone to Ceol's support, and someone will look at it soon.")
                            .accessibilityIdentifier("report.sent")
                    }
                } else {
                    if let url = target.url {
                        Section {
                            Text(verbatim: url.absoluteString).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                        } header: { Text("About this page") }
                    }
                    Section {
                        ForEach(Self.reasons, id: \.0) { value, label in
                            Button { reason = value } label: {
                                HStack {
                                    Text(label).foregroundStyle(CeolTokens.textColor)
                                    Spacer()
                                    if reason == value { Image(systemName: "checkmark").foregroundStyle(CeolTokens.primary) }
                                }
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("report.\(value)")
                            .accessibilityAddTraits(reason == value ? .isSelected : [])
                        }
                    } header: { Text("What's wrong?") }
                    Section {
                        TextField("Tell us more", text: $message, axis: .vertical)
                            .lineLimit(3...8)
                            .accessibilityIdentifier("report.message")
                    } footer: {
                        Text("Reports go to support@ceol.app, with your name and email so we can reply.")
                    }
                    if let error {
                        Section { Text(error).foregroundStyle(CeolTokens.danger) }
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
            .navigationTitle("Report")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if sent {
                    ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
                } else {
                    ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) {
                        if busy { ProgressView() } else {
                            Button("Send") { Task { await send() } }
                                .disabled(!canSend)
                                .accessibilityIdentifier("report.send")
                        }
                    }
                }
            }
        }
    }

    private func send() async {
        guard let reason else { return }
        busy = true
        error = nil
        defer { busy = false }
        do {
            try await model.auth.report(reason: reason, message: message.trimmingCharacters(in: .whitespacesAndNewlines),
                                        pageURL: target.url?.absoluteString)
            sent = true
        } catch let f as AuthFailure {
            error = f.message
        } catch {
            self.error = tr("Couldn't reach Ceol. Check your connection and try again.")
        }
    }
}
