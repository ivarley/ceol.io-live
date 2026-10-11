// Adding to a session's lists, from the + on its Tunes and People tabs: the app's twins
// of the web's add-to-session pane (mytunes/SessionTuneAddApp.svelte) and its People
// tab's person picker (scope "session").
//
// A tune: the catalogue search (DeepSearchSheet, scoped to the session, so tunes already
// on its list say so and dim). The + on a result adds it as it is; the preview adds it
// with the setting paged to, and what the session calls it and the key it plays, when
// those differ. Picking one already on the list opens it instead.
//
// A person: the session's own list first, since the one you mean is often already on
// it; failing that, the new-person form. No search of everyone on Ceol: that would tell
// you who exists elsewhere (spec 034).

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

/// A refusal from the server, worded for the person: what a form shows.
struct Refusal: LocalizedError {
    let errorDescription: String?
}

private func refusalMessage(_ error: Components.Responses._Error) -> String? {
    (try? error.body.json)?.message
}

private var offlineMessage: String { tr("Couldn't reach Ceol, so nothing changed. Check your connection and try again.") }

// MARK: - A tune

struct AddSessionTuneSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let path: String
    let initialQuery: String
    /// Added: the tune's id and name (the session's own, when one was given).
    let onAdded: (Int, String) -> Void
    /// Picked one already on the list: the tune's id, name and type.
    let onAlready: (Int, String, String?) -> Void

    /// The search result the pick came from (whether it was already on the list).
    @State private var result: JSONValue?

    var body: some View {
        DeepSearchSheet(
            app: model, scope: .session(path), initialQuery: initialQuery, preferType: nil,
            title: tr("Add a tune to this session"), actionLabel: tr("＋ Add This Tune"), allowAsIs: false,
            closesOnPick: false, pickedResult: { result = $0 }, sessionExtras: true,
            onClose: { dismiss() }
        ) { payload in
            let id = payload["tune_id"]?.intValue ?? payload["thesession_id"]?.intValue
            if result?["in_session"] == true, let id {
                // Already on the list: not an add. Show it instead.
                dismiss()
                onAlready(id, payload["name"]?.stringValue ?? "", payload["tune_type"]?.stringValue)
                return nil
            }
            return await add(payload)
        }
        .ceolDrawer(interactive: false)
    }

    /// Adds it to the session's list: the + takes the tune as it is (its first setting,
    /// no name or key of the session's own); the preview's button brings the setting
    /// chosen in its pager, and the alias and key when given. What went wrong, or nil.
    private func add(_ payload: [String: JSONValue]) async -> String? {
        let name = payload["name"]?.stringValue ?? ""
        let alias = payload["alias"]?.stringValue
        do {
            switch try await model.auth.client.addSessionTune(
                path: .init(sessionPath: path),
                body: .json(.init(
                    tuneId: payload["tune_id"]?.intValue, thesessionId: payload["thesession_id"]?.intValue,
                    alias: alias, settingId: payload["setting_id"]?.intValue, key: payload["key"]?.stringValue)))
            {
            case .created(let created):
                let r = try created.body.json
                dismiss()
                onAdded(r.tuneId, alias ?? name)
                return nil
            case .default(let status, let error):
                return status == 409
                    ? tr("\(name) is already on this session's list.")
                    : refusalMessage(error) ?? tr("Couldn't add the tune to the session. Try again.")
            }
        } catch {
            return offlineMessage
        }
    }
}

// MARK: - A person

struct AddSessionPersonSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let path: String
    /// The session's list, as its People tab has it.
    let people: [SessionPeoplePayload.PeoplePayloadPayload]
    let onAdded: () -> Void

    @State private var query = ""
    @State private var creating = false

    var body: some View {
        NavigationStack {
            Group {
                if creating {
                    NewPersonForm(app: model, name: People.splitName(query), needsLastName: true) { first, last, email, instruments in
                        try await add(first: first, last: last, email: email, instruments: instruments)
                    } onDone: { person in
                        if person != nil {
                            dismiss()
                            onAdded()
                        }
                    }
                } else {
                    list
                }
            }
            .navigationTitle("Add someone")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if creating {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Back") { creating = false }.accessibilityIdentifier("addPerson.back")
                    }
                } else {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }
                    }
                }
            }
        }
        .ceolDrawer([.medium, .large])
    }

    private var list: some View {
        let q = query.trimmingCharacters(in: .whitespaces)
        let matches = q.isEmpty ? [] : SessionPage.filterPeople(
            people.map {
                SessionPage.Person(name: "\($0.firstName) \($0.lastName)", instruments: $0.instruments,
                                   relationship: $0.relationship, archived: $0.archived ?? false)
            },
            view: .members, search: q
        ).map { people[$0] }
        return List {
            if q.isEmpty {
                Text("Type their name. If they're already on this session's list, they'll show here.")
                    .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    .listRowBackground(Color.clear)
            }
            if !matches.isEmpty {
                Section("Already on this session's list") {
                    ForEach(matches, id: \.personId) { p in
                        HStack {
                            Text(p.displayName).foregroundStyle(CeolTokens.textColor)
                            if p.archived == true { Pill(text: tr("archived")) }
                            if p.relationship == "visitor" { Pill(text: tr("visitor")) }
                        }
                        .listRowBackground(Color.clear)
                    }
                }
            }
            if !q.isEmpty {
                Button { creating = true } label: {
                    Text("＋ Add \(Text(q).bold())").foregroundStyle(CeolTokens.primary)
                }
                .listRowBackground(Color.clear)
                .accessibilityIdentifier("addPerson.new")
            }
        }
        .scrollContentBackground(.hidden)
        .background(CeolTokens.drawerBg)
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Their name…")
        .autocorrectionDisabled()
    }

    /// Onto the session's list, as a member.
    private func add(first: String, last: String, email: String, instruments: [String]) async throws -> JSONValue? {
        let result: Operations.AddSessionPerson.Output
        do {
            result = try await model.auth.client.addSessionPerson(
                path: .init(sessionPath: path),
                body: .json(.init(firstName: first, lastName: last, email: email.isEmpty ? nil : email, instruments: instruments)))
        } catch {
            throw Refusal(errorDescription: offlineMessage)
        }
        switch result {
        case .ok(let ok):
            return .number(Double(try ok.body.json.personId))
        case .default(_, let error):
            throw Refusal(errorDescription: refusalMessage(error) ?? tr("That person wasn't added. Try again."))
        }
    }
}
