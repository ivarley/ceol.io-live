// A person on a session's People tab, tapped: the app's twin of the web's person sheet
// (sessionpage/PeopleTab.svelte). Who they are here (how many nights they've come, where
// they're from, their instruments, thesession.org), the nights they came, and the
// session's say over them: member or visitor (them or an admin), and for an admin,
// confirm (which lets them see the session's people) and archive.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

typealias SessionPersonRow = SessionPeoplePayload.PeoplePayloadPayload
typealias SessionPersonDetail = Components.Schemas.SessionPersonDetail.PersonPayload

/// The person a sheet is open on.
struct PersonRef: Identifiable, Hashable {
    let id: Int
}

struct SessionPersonSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let path: String
    let sessionName: String
    /// Their row on the session's list: what the detail doesn't carry (relationship,
    /// confirmed, archived, the count of nights).
    let row: SessionPersonRow
    let isSessionAdmin: Bool
    let trackAttendance: Bool
    /// After a change here: the list reloads.
    let onChanged: () async -> Void

    @State private var detail: LoadState<SessionPersonDetail> = .loading
    @State private var relationship: String?
    @State private var confirmed = false
    @State private var archived = false
    /// Which change is saving ("relationship", "confirmed", "archived").
    @State private var saving: String?
    @State private var failure: String?

    private var isMe: Bool { model.user?.personId == row.personId }
    private var name: String { "\(row.firstName) \(row.lastName)".trimmingCharacters(in: .whitespaces) }

    var body: some View {
        NavigationStack {
            Loaded(state: detail, retry: load) { p in content(p) }
                .background(CeolTokens.drawerBg)
                .navigationTitle(name)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { dismiss() }.accessibilityIdentifier("person.done")
                    }
                }
        }
        .ceolDrawer([.medium, .large])
        .task {
            relationship = row.relationship
            confirmed = row.confirmed
            archived = row.archived ?? false
            if detail.value == nil { await load() }
        }
    }

    private func load() async {
        do {
            switch try await model.auth.client.getSessionPerson(path: .init(sessionPath: path, personId: row.personId)) {
            case .ok(let ok): detail = .loaded(try ok.body.json.person)
            case .default(_, let error):
                detail = .failed((try? error.body.json)?.message ?? tr("Couldn't load this person's details."))
            }
        } catch {
            detail = .failed(loadFailureMessage(error))
        }
    }

    @ViewBuilder private func content(_ p: SessionPersonDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                summary(p)
                links(p)
                if relationship != nil && (isSessionAdmin || isMe) { relationshipSection }
                if isSessionAdmin { adminSection }
                if let failure {
                    Text(failure).font(.ceol(size: 15)).foregroundStyle(CeolTokens.danger)
                }
                section(tr("Instruments")) {
                    if p.instruments.isEmpty {
                        muted(tr("No instruments listed"))
                    } else {
                        FlowLayout(spacing: 6) {
                            ForEach(p.instruments, id: \.self) { Pill(text: SessionsL10n.instrument($0.capitalized), size: 14) }
                        }
                    }
                }
                section("TheSession.org") {
                    if let id = p.thesessionUserId, let url = URL(string: "https://thesession.org/members/\(id)") {
                        Link("View on TheSession.org", destination: url)
                            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
                    } else {
                        muted(tr("Not linked"))
                    }
                }
                if trackAttendance { nights(p) }
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// How often they come, and where they're from: the first thing you want to know.
    private func summary(_ p: SessionPersonDetail) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                if archived { Pill(text: tr("Archived"), size: 12) }
                if relationship == "visitor" {
                    Pill(text: tr("Visitor"), style: .filled, color: Color(red: 0.55, green: 0.45, blue: 0.15), size: 12)
                }
                if row.isAdmin { Pill(text: SessionsL10n.adminRole, style: .filled, color: CeolTokens.primaryFill, size: 12) }
                // Can't see the session's people yet: an admin's to fix.
                if isSessionAdmin && !confirmed { Pill(text: tr("Unconfirmed"), size: 12) }
            }
            if trackAttendance {
                let n = p.attendedInstances.count
                Text(n == 0 ? tr("Hasn't been checked in here yet") : n == 1 ? tr("Came 1 night") : tr("Came \(n) nights"))
                    .font(.ceol(size: 18, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                    .accessibilityIdentifier("person.nights")
            }
            let place = [p.city, p.state, p.country].compactMap { $0 }.filter { !$0.isEmpty }
            Text(place.isEmpty ? tr("No location specified") : place.joined(separator: ", "))
                .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
        }
    }

    @ViewBuilder private func links(_ p: SessionPersonDetail) -> some View {
        if isMe {
            Button("View my profile") {
                dismiss()
                model.tab = .me
            }
            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
            .accessibilityIdentifier("person.profile")
        } else if p.hasUserAccount {
            // The tunes you both have, in the app (the web's /me/and/<id>).
            NavigationLink {
                CommonTunesView(personID: row.personId, name: name)
            } label: {
                HStack(spacing: 6) {
                    Text("Tunes in common")
                    Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold))
                }
            }
            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
            .accessibilityIdentifier("person.commonTunes")
        }
    }

    private var relationshipSection: some View {
        section(tr("Relationship to this session")) {
            Picker("Relationship", selection: Binding(get: { relationship ?? "member" }, set: { v in
                Task { await setRelationship(v) }
            })) {
                Text("Member").tag("member")
                Text("Visitor").tag("visitor")
            }
            .pickerStyle(.segmented)
            .disabled(saving != nil)
            .accessibilityIdentifier("person.relationship")
            muted(saving == "relationship" ? tr("Saving…")
                : relationship == "visitor" ? tr("Came here, but this isn't one of their sessions.")
                : tr("This is one of their sessions — its tunes count towards their stats."))
        }
    }

    /// What each control does, said at the point of tapping it: confirming hands over the
    /// session's people list, and an admin must know that.
    private var adminSection: some View {
        section(tr("Session admin")) {
            action(
                saving == "confirmed" ? tr("Saving…")
                    : confirmed
                    ? tr("Un-confirm \(name) — they'll no longer see this session's people list and attendance records")
                    : tr("Confirm \(name) — they'll be able to see this session's people list and attendance records"),
                id: "person.confirm"
            ) { await setConfirmed(!confirmed) }
            action(
                saving == "archived" ? tr("Saving…")
                    : archived ? tr("Restore \(name) to the roster")
                    : tr("Archive \(name) — hide them from lists (still findable by name)"),
                id: "person.archive"
            ) { await setArchived(!archived) }
        }
    }

    @ViewBuilder private func nights(_ p: SessionPersonDetail) -> some View {
        section(tr("Nights attended")) {
            if p.attendedInstances.isEmpty {
                muted(tr("No nights attended yet"))
            } else {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(p.attendedInstances, id: \.sessionInstanceId) { night in
                        Button {
                            // The night's log, in the Sessions tab under this session.
                            dismiss()
                            model.sessionsPath.append(
                                .night(id: night.sessionInstanceId, title: "\(sessionName) · \(SessionsL10n.shortDate(night.date))"))
                        } label: {
                            HStack {
                                Text(longDay(night.date) + yearSuffix(night.date)).font(.ceol(size: 16))
                                    .foregroundStyle(CeolTokens.primary)
                                Spacer()
                                Image(systemName: "chevron.right").font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted)
                            }
                            .padding(.vertical, 10)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("person.night")
                        Hairline()
                    }
                }
            }
        }
    }

    private func yearSuffix(_ date: String) -> String {
        let year = String(date.prefix(4))
        return year == String(Calendar.current.component(.year, from: Date())) ? "" : ", \(year)"
    }

    private func section(_ title: String, @ViewBuilder _ body: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased()).font(.ceol(size: 12, weight: .semibold)).tracking(0.8)
                .foregroundStyle(CeolTokens.textMuted)
            body()
        }
    }

    private func muted(_ s: String) -> some View {
        Text(s).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
    }

    private func action(_ title: String, id: String, _ run: @escaping () async -> Void) -> some View {
        Button { Task { await run() } } label: {
            Text(title).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor)
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .disabled(saving != nil)
        .accessibilityIdentifier(id)
    }

    // MARK: Changes

    private func setRelationship(_ value: String) async {
        guard value != relationship, let r = Relationship(rawValue: value) else { return }
        await save("relationship", failed: tr("Couldn't change their relationship to this session. Try again.")) {
            switch try await model.auth.client.setSessionRelationship(
                path: .init(sessionPath: path, personId: row.personId), body: .json(.init(relationship: r)))
            {
            case .ok: return nil
            case .default(_, let e): return (try? e.body.json)?.message ?? ""
            }
        } then: { relationship = value }
    }

    private func setConfirmed(_ value: Bool) async {
        await save("confirmed", failed: tr("Couldn't change whether they are confirmed. Try again.")) {
            switch try await model.auth.client.setSessionPersonConfirmed(
                path: .init(sessionPath: path, personId: row.personId), body: .json(.init(confirmed: value)))
            {
            case .ok: return nil
            case .default(_, let e): return (try? e.body.json)?.message ?? ""
            }
        } then: { confirmed = value }
    }

    private func setArchived(_ value: Bool) async {
        await save("archived", failed: tr("Couldn't change whether they are archived. Try again.")) {
            switch try await model.auth.client.setSessionPersonArchived(
                path: .init(sessionPath: path, personId: row.personId), body: .json(.init(archived: value)))
            {
            case .ok: return nil
            case .default(_, let e): return (try? e.body.json)?.message ?? ""
            }
        } then: { archived = value }
    }

    /// Runs a change: `call` answers nil when it worked, else the server's refusal.
    private func save(_ field: String, failed: String, call: () async throws -> String?, then apply: () -> Void) async {
        guard saving == nil else { return }
        saving = field
        failure = nil
        defer { saving = nil }
        do {
            if let refusal = try await call() {
                failure = refusal.isEmpty ? failed : refusal
                return
            }
            apply()
            await onChanged()
        } catch {
            failure = tr("Couldn't reach Ceol, so nothing changed. Check your connection and try again.")
        }
    }
}
