// Adding to a session's lists, from the + on its Tunes and People tabs: the app's twins
// of the web's add-to-session pane (mytunes/SessionTuneAddApp.svelte) and its People
// tab's person picker (scope "session").
//
// A tune: the catalogue search (DeepSearchSheet, scoped to the session, so tunes already
// on its list say so and dim), then what the session calls it and, under Advanced, the
// setting and key it plays. Picking one already on the list opens it instead.
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
    /// Added: the tune's id and name.
    let onAdded: (Int, String) -> Void
    /// Picked one already on the list: the tune's id, name and type.
    let onAlready: (Int, String, String?) -> Void

    /// The pick (its add payload) and the search result it came from.
    @State private var picked: [String: JSONValue]?
    @State private var result: JSONValue?

    var body: some View {
        Group {
            if let picked {
                AddSessionTuneForm(path: path, picked: picked, result: result, onBack: {
                    self.picked = nil
                    result = nil
                }) { id, name in
                    dismiss()
                    onAdded(id, name)
                }
            } else {
                DeepSearchSheet(
                    app: model, scope: .session(path), initialQuery: initialQuery, preferType: nil,
                    title: tr("Add a tune to this session"), allowAsIs: false, closesOnPick: false,
                    pickedResult: { result = $0 },
                    onClose: { dismiss() }
                ) { payload in
                    let id = payload["tune_id"]?.intValue ?? payload["thesession_id"]?.intValue
                    if result?["in_session"] == true, let id {
                        // Already on the list: not an add. Show it instead.
                        dismiss()
                        onAlready(id, payload["name"]?.stringValue ?? "", payload["tune_type"]?.stringValue)
                    } else {
                        picked = payload
                    }
                }
            }
        }
        .ceolDrawer([.large])
    }
}

/// The add form for a picked tune: its card, "We call this", and Advanced.
private struct AddSessionTuneForm: View {
    @Environment(AppModel.self) private var model
    let path: String
    let picked: [String: JSONValue]
    let result: JSONValue?
    let onBack: () -> Void
    let onAdded: (Int, String) -> Void

    @State private var alias = ""
    @State private var advanced = false
    @State private var setting = ""
    @State private var settingError: String?
    @State private var key = ""
    @State private var busy = false
    @State private var failure: String?

    /// The keys the web's form offers.
    static let keys = [
        "Amajor", "Aminor", "Adorian", "Amixolydian", "Bminor", "Cmajor", "Dmajor", "Dminor",
        "Eminor", "Fmajor", "Gmajor", "Dmixolydian", "Bmixolydian", "Edorian", "Gdorian",
        "Gminor", "Ddorian", "Cdorian", "Fdorian", "Gmixolydian", "Emajor", "Bdorian", "Emixolydian",
    ]

    private var name: String { picked["name"]?.stringValue ?? "" }
    private var tuneID: Int? { picked["tune_id"]?.intValue }
    private var theSessionID: Int? { picked["thesession_id"]?.intValue }
    /// From thesession.org: adding it imports it.
    private var isRemote: Bool { theSessionID != nil }

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                Text("Add to session").font(.ceol(size: 17, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                HStack {
                    Button(action: onBack) { Image(systemName: "chevron.left") }
                        .accessibilityLabel("Back to search")
                        .accessibilityIdentifier("addSessionTune.back")
                    Spacer()
                }
                .font(.ceol(size: 17)).foregroundStyle(CeolTokens.primary)
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    card
                    VStack(alignment: .leading, spacing: 6) {
                        label(tr("We call this (optional)"))
                        field(tr("Local name for this tune, if different"), text: $alias, id: "addSessionTune.alias")
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Button { withAnimation(.easeOut(duration: 0.15)) { advanced.toggle() } } label: {
                            Label("Advanced", systemImage: advanced ? "chevron.down" : "chevron.right")
                                .font(.ceol(size: 16)).foregroundStyle(CeolTokens.primary)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("addSessionTune.advanced")
                        if advanced { advancedFields }
                    }
                    if let failure {
                        Text(failure).font(.ceol(size: 15)).foregroundStyle(CeolTokens.danger)
                    }
                    Button { Task { await add() } } label: {
                        Text(busy ? "Adding…" : "Add to Session").font(.ceol(size: 17, weight: .semibold))
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity, minHeight: 48)
                            .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                    .disabled(busy)
                    .accessibilityIdentifier("addSessionTune.add")
                }
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
        }
        .background(CeolTokens.drawerBg)
        // A setting picked in the search's preview would arrive here; open Advanced to show it.
        .onAppear {
            if let s = picked["setting_id"]?.intValue {
                setting = String(s)
                advanced = true
            }
        }
    }

    private var card: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(name).font(.ceol(size: 19, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                Spacer()
                if let t = picked["tune_type"]?.stringValue { TypeChip(label: t) }
            }
            if !isRemote, let id = tuneID {
                DeepIncipit(app: model, tuneID: id, base64: result?["incipit_image"]?.stringValue,
                            canRender: result?["can_render"] == true)
            }
            let meta = [
                isRemote ? tr("importing from thesession.org") : nil,
                result?["tunebook_count"]?.intValue.map { tr("\($0) tunebooks") },
            ].compactMap { $0 }
            if !meta.isEmpty {
                Text(meta.joined(separator: " · ")).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
            }
            Button("Not this one? Back to search", action: onBack)
                .font(.ceol(size: 15)).foregroundStyle(CeolTokens.primary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
    }

    private var advancedFields: some View {
        VStack(alignment: .leading, spacing: 6) {
            label(tr("Setting (optional)"))
            field(tr("Setting number or thesession.org URL"), text: $setting, id: "addSessionTune.setting")
                .onChange(of: setting) { settingError = nil }
            help(tr("If the session plays a specific setting of the tune, paste its URL or setting number."))
            if let settingError { Text(settingError).font(.ceol(size: 14)).foregroundStyle(CeolTokens.danger) }
            label(tr("Key (optional)")).padding(.top, 8)
            Menu {
                Button("(not specified)") { key = "" }
                ForEach(Self.keys, id: \.self) { k in Button(k) { key = k } }
            } label: {
                HStack {
                    Text(key.isEmpty ? tr("(not specified)") : key).font(.ceol(size: 16))
                        .foregroundStyle(key.isEmpty ? CeolTokens.textMuted : CeolTokens.textColor)
                    Spacer()
                    Image(systemName: "chevron.up.chevron.down").font(.system(size: 13)).foregroundStyle(CeolTokens.textMuted)
                }
                .padding(.horizontal, 12).frame(height: 44)
                .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            }
            .accessibilityIdentifier("addSessionTune.key")
            help(tr("The key the session typically plays this tune in."))
        }
    }

    private func label(_ s: String) -> some View {
        Text(s).font(.ceol(size: 15, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
    }

    private func help(_ s: String) -> some View {
        Text(s).font(.ceol(size: 13)).foregroundStyle(CeolTokens.textMuted)
    }

    private func field(_ prompt: String, text: Binding<String>, id: String) -> some View {
        TextField("", text: text, prompt: Text(prompt).foregroundStyle(CeolTokens.textMuted))
            .font(.ceol(size: 16))
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .padding(.horizontal, 12).frame(height: 44)
            .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            .accessibilityIdentifier(id)
    }

    /// A bare number, or a thesession.org URL's ?setting= / #setting.
    private var settingID: (ok: Bool, id: Int?) {
        let t = setting.trimmingCharacters(in: .whitespaces)
        if t.isEmpty { return (true, nil) }
        if let n = Int(t), n > 0 { return (true, n) }
        if let n = TheSession.settingID(t) { return (true, n) }
        return (false, nil)
    }

    private func add() async {
        guard !busy else { return }
        failure = nil
        let s = settingID
        guard s.ok else {
            settingError = tr("Enter a setting number or paste a thesession.org URL.")
            advanced = true
            return
        }
        busy = true
        defer { busy = false }
        let trimmedAlias = alias.trimmingCharacters(in: .whitespaces)
        do {
            switch try await model.auth.client.addSessionTune(
                path: .init(sessionPath: path),
                body: .json(.init(
                    tuneId: tuneID, thesessionId: theSessionID,
                    alias: trimmedAlias.isEmpty ? nil : trimmedAlias, settingId: s.id, key: key.isEmpty ? nil : key)))
            {
            case .created(let created):
                let r = try created.body.json
                onAdded(r.tuneId, trimmedAlias.isEmpty ? name : trimmedAlias)
            case .default(let status, let error):
                failure = status == 409
                    ? tr("\(name) is already on this session's list.")
                    : refusalMessage(error) ?? tr("Couldn't add the tune to the session. Try again.")
            }
        } catch {
            failure = offlineMessage
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
