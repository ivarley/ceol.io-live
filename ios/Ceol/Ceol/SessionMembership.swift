// Belonging to a session, and adding a night (plan Phase 4c), as the web's session page
// does them (spec 034):
//   - not yours yet: "Do you attend this session?", local or just visiting. Joining lands
//     you unconfirmed; a session admin confirms you before you see its people.
//   - yours: your role (Member / Visitor, or Admin), a sheet to change member/visitor,
//     and Leave, confirmed. What you logged there stays either way.
//   - Add a night: anyone signed in may, as on the web. It opens on the date and times
//     the session's recurrence suggests, and goes to the new night when added.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

typealias Relationship = Components.Schemas.Relationship

/// The server's sentence for a refused write, or a fallback.
private func refusal(_ error: Components.Responses._Error) -> String? {
    (try? error.body.json)?.message
}

private let unreachable = "Couldn't reach Ceol, so nothing changed. Check your connection and try again."

// MARK: - Joining, and your role

struct MembershipSection: View {
    @Environment(AppModel.self) private var model
    let path: String
    let permissions: SessionDetailPayload.PermissionsPayload
    /// Reload the session after a change: membership decides much of the page.
    let onChange: () async -> Void
    /// Open the role sheet. The session screen presents it: a sheet hung on a Section
    /// inside a List doesn't reliably appear.
    let onEditRole: () -> Void

    @State private var asking = false
    @State private var busy = false
    @State private var failure: String?
    @State private var joined = false

    var body: some View {
        if let relationship = permissions.relationship {
            Section {
                Button { onEditRole() } label: {
                    HStack {
                        Text("You're").foregroundStyle(CeolTokens.textColor)
                        Spacer()
                        Text(roleLabel(relationship)).foregroundStyle(CeolTokens.secondary)
                        Image(systemName: "chevron.right").font(.footnote).foregroundStyle(CeolTokens.secondary)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("session.role")
            } footer: {
                if joined || !permissions.isConfirmed {
                    Text("A session admin can confirm you to show you who else plays here.")
                }
            }
        } else if permissions.isLoggedIn {
            Section {
                Button(busy ? "Adding…" : "Do you attend this session? Yes, add me") { asking = true }
                    .disabled(busy)
                    .accessibilityIdentifier("session.join")
            } footer: {
                if let failure { Text(failure).foregroundStyle(CeolTokens.danger) }
            }
            .confirmationDialog("Are you a local, or just visiting?", isPresented: $asking, titleVisibility: .visible) {
                Button("I'm local") { Task { await join(.member) } }
                Button("Just visiting") { Task { await join(.visitor) } }
            } message: {
                Text("Local: one of your sessions, so its tunes count towards your stats. Visiting: a record that you came.")
            }
        }
    }

    private func roleLabel(_ relationship: String) -> String {
        if permissions.isSessionAdmin { return "Admin" }
        return relationship == "visitor" ? "Visitor" : "Member"
    }

    private func join(_ relationship: Relationship) async {
        busy = true
        failure = nil
        defer { busy = false }
        do {
            switch try await model.auth.client.joinSession(
                path: .init(sessionPath: path), body: .json(.init(relationship: relationship)))
            {
            case .ok:
                joined = true
                await onChange()
            case .default(_, let error):
                failure = refusal(error) ?? "Couldn't add you to this session. Try again."
            }
        } catch {
            failure = unreachable
        }
    }
}

struct RoleSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let path: String
    let relationship: String
    let isAdmin: Bool
    let onChange: () async -> Void

    @State private var draft: Relationship = .member
    @State private var busy = false
    @State private var failure: String?
    @State private var confirmLeave = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Relationship", selection: $draft) {
                        Text("I attend this session").tag(Relationship.member)
                        Text("I've just visited").tag(Relationship.visitor)
                    }
                    .pickerStyle(.inline)
                    .labelsHidden()
                    .accessibilityIdentifier("role.picker")
                } header: {
                    Text("Your relationship to this session")
                } footer: {
                    Text(
                        draft == .member
                            ? "Its tunes and history count as one of your sessions."
                            : "You came, but it isn't one of your sessions: its tunes won't count as yours. The nights you were there still do."
                    )
                }
                if isAdmin {
                    Section { Text("You're an admin here. That doesn't change either way.").foregroundStyle(CeolTokens.secondary) }
                }
                Section {
                    Button("Leave this session", role: .destructive) { confirmLeave = true }
                        .disabled(busy)
                        .accessibilityIdentifier("role.leave")
                } footer: {
                    if let failure { Text(failure).foregroundStyle(CeolTokens.danger) }
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
            .navigationTitle("Your role")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(busy || draft.rawValue == relationship)
                        .accessibilityIdentifier("role.save")
                }
            }
            .confirmationDialog("Leave this session?", isPresented: $confirmLeave, titleVisibility: .visible) {
                Button("Leave", role: .destructive) { Task { await leave() } }
            } message: {
                Text("You'll stop seeing it on your home screen and its tunes will no longer count as yours. Everything you logged there stays, and you can join again whenever you like.")
            }
            .onAppear { draft = Relationship(rawValue: relationship) ?? .member }
        }
    }

    private func save() async {
        guard let personID = model.user?.personId else { return }
        busy = true
        failure = nil
        defer { busy = false }
        do {
            switch try await model.auth.client.setSessionRelationship(
                path: .init(sessionPath: path, personId: personID), body: .json(.init(relationship: draft)))
            {
            case .ok:
                await onChange()
                dismiss()
            case .default(_, let error):
                failure = refusal(error) ?? "Couldn't save that. Try again."
            }
        } catch {
            failure = unreachable
        }
    }

    private func leave() async {
        busy = true
        failure = nil
        defer { busy = false }
        do {
            switch try await model.auth.client.leaveSession(path: .init(sessionPath: path)) {
            case .ok:
                await onChange()
                dismiss()
            case .default(_, let error):
                failure = refusal(error) ?? "Couldn't leave this session. Try again."
            }
        } catch {
            failure = unreachable
        }
    }
}

// MARK: - Adding a night

struct AddNightView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let path: String
    let usualVenue: String?
    /// The new night's id, once added.
    let onAdded: (Int, String) -> Void

    @State private var date = Date()
    @State private var hasTimes = false
    @State private var start = Date()
    @State private var end = Date()
    @State private var location = ""
    @State private var comments = ""
    @State private var suggesting = true
    @State private var suggestFailed = false
    @State private var busy = false
    @State private var failure: String?

    var body: some View {
        NavigationStack {
            Form {
                if suggestFailed {
                    Section {
                        Text("Couldn't look up the next usual date, so this is today. Check it before adding.")
                            .foregroundStyle(CeolTokens.warning)
                    }
                }
                Section {
                    DatePicker("Date", selection: $date, displayedComponents: .date)
                        .accessibilityIdentifier("night.date")
                    Toggle("Start and end times", isOn: $hasTimes)
                    if hasTimes {
                        DatePicker("Starts", selection: $start, displayedComponents: .hourAndMinute)
                        DatePicker("Ends", selection: $end, displayedComponents: .hourAndMinute)
                    }
                } footer: {
                    if suggesting { Text("Looking up the next usual date…") }
                }
                Section {
                    TextField(usualVenue.map { "Venue (usually \($0))" } ?? "Venue", text: $location)
                    TextField("Notes", text: $comments, axis: .vertical).lineLimit(1...4)
                } footer: {
                    if let failure { Text(failure).foregroundStyle(CeolTokens.danger) }
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
            .navigationTitle("Add a night")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(busy ? "Adding…" : "Add") { Task { await add() } }
                        .disabled(busy)
                        .accessibilityIdentifier("night.add")
                }
            }
            .task { await suggest() }
        }
    }

    private static let day: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static let time: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "HH:mm"
        return f
    }()

    /// The next date and times the session's recurrence suggests, as the web prefills.
    private func suggest() async {
        defer { suggesting = false }
        guard let s = try? await model.auth.client.getNextInstanceSuggestion(path: .init(sessionPath: path)).ok.body.json,
            let d = Self.day.date(from: s.date)
        else {
            suggestFailed = true
            return
        }
        date = d
        if let st = s.startTime.flatMap({ Self.time.date(from: String($0.prefix(5))) }) {
            start = st
            hasTimes = true
        }
        if let et = s.endTime.flatMap({ Self.time.date(from: String($0.prefix(5))) }) { end = et }
    }

    private func add() async {
        busy = true
        failure = nil
        defer { busy = false }
        let trimmedLocation = location.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedComments = comments.trimmingCharacters(in: .whitespacesAndNewlines)
        let day = Self.day.string(from: date)
        do {
            switch try await model.auth.client.addSessionInstance(
                path: .init(sessionPath: path),
                body: .json(
                    .init(
                        date: day,
                        startTime: hasTimes ? Self.time.string(from: start) : nil,
                        endTime: hasTimes ? Self.time.string(from: end) : nil,
                        location: trimmedLocation.isEmpty ? nil : trimmedLocation,
                        comments: trimmedComments.isEmpty ? nil : trimmedComments)))
            {
            case .ok(let ok):
                let r = try ok.body.json
                dismiss()
                onAdded(r.sessionInstanceId, r.date)
            case .default(_, let error):
                failure = refusal(error) ?? "Couldn't add the night. Try again."
            }
        } catch {
            failure = "Couldn't reach Ceol, so the night wasn't added. Check your connection and try again."
        }
    }
}
