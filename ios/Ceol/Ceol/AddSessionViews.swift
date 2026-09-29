// Adding a session (plan Phase 4d), the app's twin of the web's two sheets (spec 052
// §B9): find it on thesession.org, or say it isn't there; then review the details and
// save. The rules (what the search text means, the path, the time zone guess, the
// schedule read from thesession.org's text, the recurrence JSON) are CeolLogic's
// AddSession, held to the web's own fixtures, so a session added here gets the same
// path, zone and schedule as one added on the web.

import CeolAPI
import CeolDesign
import CeolLogic
import CeolSession
import SwiftUI

typealias SessionSearchResult = Components.Schemas.TheSessionSessionSearch.ResultsPayloadPayload

/// What the details form opens with: a thesession.org session, or nothing (by hand).
struct SessionSeed {
    var thesessionID = ""
    var name = ""
    var venue = ""
    var phone = ""
    var website = ""
    var city = ""
    var state = ""
    var country = ""
    var inceptionDate = ""
    var timezone: String?
    var schedule: AddSession.Schedule?
    /// thesession.org's schedule text, when no schedule could be read from it.
    var unparsed: String?
}

private func refusal(_ error: Components.Responses._Error) -> String? { (try? error.body.json)?.message }

// MARK: - Stage 1: find it

struct AddSessionView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    /// Go to a session: one just created, or one Ceol already had.
    let onOpen: (_ path: String, _ name: String) -> Void

    @State private var query = ""
    @State private var results: [SessionSearchResult]?
    @State private var pendingID: String?
    @State private var searching = false
    @State private var failure: String?
    @State private var existing: (path: String, name: String)?
    @State private var options: Components.Schemas.AddSessionOptions?
    @State private var seed: SessionSeed?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    SearchRow(text: $query, prompt: "Session name, or a thesession.org link", fieldID: "addSession.query")
                    if let failure {
                        Text(failure).font(.ceol(size: 15)).foregroundStyle(CeolTokens.danger)
                    } else if searching {
                        Text("Searching thesession.org…").font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
                    } else if results == nil && pendingID == nil {
                        Text("Sessions come from thesession.org. Search for yours, or paste its link.")
                            .font(.ceol(size: 16)).foregroundStyle(CeolTokens.textMuted)
                    }
                    if let existing {
                        Button {
                            dismiss()
                            onOpen(existing.path, existing.name)
                        } label: {
                            card(title: "Open \(existing.name)", subtitle: "That session is already on Ceol.")
                        }
                        .buttonStyle(.plain)
                    }
                    if let pendingID {
                        Button { Task { await check(pendingID) } } label: {
                            card(title: "thesession.org session \(pendingID)", subtitle: "Look it up")
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("addSession.pendingID")
                    }
                    if let results {
                        VStack(alignment: .leading, spacing: 0) {
                            Text(results.isEmpty ? "Nothing on thesession.org by that name" : "On thesession.org")
                                .font(.ceol(size: 13, weight: .semibold)).textCase(.uppercase).tracking(0.8)
                                .foregroundStyle(CeolTokens.textMuted).padding(.bottom, 6)
                            ForEach(results, id: \.id) { r in
                                Button { Task { await pick(r) } } label: { resultRow(r) }
                                    .buttonStyle(.plain)
                                    .accessibilityIdentifier("addSession.result")
                                Hairline()
                            }
                        }
                    }
                    Button {
                        seed = SessionSeed(timezone: options?.defaultTimezone)
                    } label: {
                        card(title: "Add a session manually", subtitle: "For sessions that aren't on thesession.org")
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("addSession.manual")
                }
                .padding(20)
            }
            .background(CeolTokens.bgColor)
            .navigationTitle("Add a Session")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
            .navigationDestination(item: $seed) { s in
                SessionDetailsForm(seed: s, options: options) { path, name in
                    dismiss()
                    onOpen(path, name)
                }
            }
            .task(id: query) { await onQuery() }
            .task { options = try? await model.auth.client.getAddSessionOptions().ok.body.json }
        }
    }

    private func card(title: String, subtitle: String) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.ceol(size: 19, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                Text(subtitle).font(.ceol(size: 15)).foregroundStyle(CeolTokens.textMuted)
            }
            Spacer()
            Image(systemName: "chevron.right").foregroundStyle(CeolTokens.textMuted)
        }
        .padding(16)
        .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
        .contentShape(Rectangle())
    }

    private func resultRow(_ r: SessionSearchResult) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(r.name).font(.ceol(size: 18, weight: .medium)).foregroundStyle(CeolTokens.textColor)
                let place = placeOf(r)
                if !place.isEmpty { Text(place).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted) }
            }
            Spacer()
            if r.existsInDb { Text("On Ceol").font(.ceol(.caption)).foregroundStyle(CeolTokens.primary) }
        }
        .padding(.vertical, 10)
        .contentShape(Rectangle())
    }

    /// thesession.org's display text often repeats the name before the place.
    private func placeOf(_ r: SessionSearchResult) -> String {
        let text = r.displayText
        guard !r.name.isEmpty, text.lowercased().hasPrefix(r.name.lowercased()) else { return text }
        return String(text.dropFirst(r.name.count)).trimmingCharacters(in: CharacterSet(charactersIn: ", "))
    }

    /// Typing is the fix for almost every error here, so it clears them. A pasted link
    /// is resolved; bare digits are offered as a row (a pause while typing "1247"
    /// settles on "124"); a name of three or more characters is searched.
    private func onQuery() async {
        failure = nil
        existing = nil
        try? await Task.sleep(for: .milliseconds(450))
        guard !Task.isCancelled else { return }
        switch AddSession.parseSessionInput(query) {
        case .id(let id):
            results = nil
            if query.trimmingCharacters(in: .whitespaces).lowercased().hasPrefix("http") {
                pendingID = nil
                await check(id)
            } else {
                pendingID = id
            }
        case .search(let q):
            pendingID = nil
            guard q.count >= 3 else {
                results = nil
                return
            }
            await search(q)
        }
    }

    private func search(_ q: String) async {
        searching = true
        defer { searching = false }
        do {
            switch try await model.auth.client.searchTheSessionSessions(body: .json(.init(query: q))) {
            case .ok(let ok): results = try ok.body.json.results
            case .default(_, let e): failure = refusal(e) ?? "Could not search thesession.org."
            }
        } catch {
            if !Task.isCancelled { failure = "Could not reach thesession.org. Please try again." }
        }
    }

    private func pick(_ r: SessionSearchResult) async {
        if r.existsInDb, let path = r.sessionPath {
            existing = (String(path.dropFirst("/sessions/".count)), r.name)
        } else {
            await check(String(r.id))
        }
    }

    /// Ceol may have it already; if not, fetch it from thesession.org as the form's seed.
    private func check(_ id: String) async {
        guard let n = Int(id) else { return }
        searching = true
        defer { searching = false }
        do {
            switch try await model.auth.client.checkExistingSession(body: .json(.init(sessionId: n))) {
            case .ok(let ok):
                let r = try ok.body.json
                if r.exists, let path = r.sessionPath {
                    existing = (String(path.dropFirst("/sessions/".count)), "session \(id)")
                    failure = "Session \(id) is already on ceol.io."
                    return
                }
            case .default(_, let e):
                failure = refusal(e) ?? "Could not check that session. Please try again."
                return
            }
            switch try await model.auth.client.fetchTheSessionSession(body: .json(.init(sessionId: n))) {
            case .ok(let ok): seed = seedFrom(try ok.body.json.sessionData)
            case .default(_, let e): failure = refusal(e) ?? "Could not fetch that session from thesession.org."
            }
        } catch {
            failure = "Could not reach thesession.org. Please try again."
        }
    }

    private func seedFrom(_ d: Components.Schemas.TheSessionSessionData.SessionDataPayload) -> SessionSeed {
        let text: String =
            switch d.recurrence {
            case .case1(let line): line
            case .case2(let lines): lines.joined(separator: " ")
            }
        let comments = d.comments.map(\.content)
        let schedule = AddSession.parseTheSessionRecurrence(text: text, comments: comments)
        return SessionSeed(
            thesessionID: d.id.map(String.init) ?? "",
            name: d.name, venue: d.locationName, phone: d.locationPhone, website: d.locationWebsite,
            city: d.city, state: d.state, country: d.country, inceptionDate: d.inceptionDate,
            timezone: AddSession.guessTimezone(
                country: d.country, state: d.state, fallback: options?.defaultTimezone ?? "America/Chicago"),
            schedule: schedule,
            unparsed: schedule == nil && !text.isEmpty ? text : nil)
    }
}

extension SessionSeed: Hashable {
    static func == (a: SessionSeed, b: SessionSeed) -> Bool { a.thesessionID == b.thesessionID && a.name == b.name }
    func hash(into h: inout Hasher) {
        h.combine(thesessionID)
        h.combine(name)
    }
}

// MARK: - Stage 2: the details

struct SessionDetailsForm: View {
    @Environment(AppModel.self) private var model
    let seed: SessionSeed
    let options: Components.Schemas.AddSessionOptions?
    let onCreated: (_ path: String, _ name: String) -> Void

    @State private var name = ""
    @State private var venue = ""
    @State private var city = ""
    @State private var state = ""
    @State private var country = ""
    @State private var timezone = "America/Chicago"
    @State private var addMe = true
    @State private var addMeAsAdmin = true
    // The schedule editor.
    @State private var recType = ""
    @State private var weekday = "tuesday"
    @State private var frequency = 1
    @State private var which: [Int] = []
    @State private var start = "19:00"
    @State private var end = "22:00"
    // Advanced: the defaults are already right.
    @State private var advanced = false
    @State private var manualPath: String?
    @State private var thesessionID = ""
    @State private var phone = ""
    @State private var website = ""
    @State private var inceptionDate = ""
    @State private var festival = false
    @State private var bufferBefore = "60"
    @State private var bufferAfter = "60"
    @State private var showPeople = true
    @State private var trackAttendance = true
    @State private var trackStarters = true

    @State private var failure: String?
    @State private var saving = false
    @State private var loaded = false

    private static let weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    private static let nths: [(Int, String)] = [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (-1, "Last")]

    private var generatedPath: String { AddSession.generatePath(city: city, sessionName: name) }
    private var path: String { manualPath ?? generatedPath }
    private var recurrence: (summary: String, json: String?) {
        AddSession.summarizeRecurrence(
            type: recType, weekday: weekday, frequency: frequency, which: which, startTime: start, endTime: end)
    }

    var body: some View {
        Form {
            Section {
                TextField("Name (required)", text: $name).accessibilityIdentifier("details.name")
                TextField("Venue", text: $venue)
                TextField("City (required)", text: $city).accessibilityIdentifier("details.city")
                TextField("State or county (required)", text: $state).accessibilityIdentifier("details.state")
                TextField("Country (required)", text: $country).accessibilityIdentifier("details.country")
            } footer: {
                Text("ceol.io/sessions/\(path.isEmpty ? "…" : path)")
            }
            scheduleSection
            Section {
                Picker("Time zone", selection: $timezone) {
                    ForEach(timezoneChoices, id: \.value) { Text($0.label).tag($0.value) }
                }
                Toggle("Add me to this session", isOn: $addMe)
                if addMe { Toggle("As an admin", isOn: $addMeAsAdmin) }
            }
            Section {
                DisclosureGroup("Advanced", isExpanded: $advanced) { advancedFields }
            }
            if let failure {
                Section { Text(failure).foregroundStyle(CeolTokens.danger).accessibilityIdentifier("details.error") }
            }
        }
        .scrollContentBackground(.hidden)
        .background(CeolTokens.bgColor)
        .navigationTitle("Session Details")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button(saving ? "Saving…" : "Save") { Task { await save() } }
                    .disabled(saving)
                    .accessibilityIdentifier("details.save")
            }
        }
        .onAppear(perform: applySeed)
    }

    private var timezoneChoices: [Components.Schemas.Option] {
        let list = options?.timezoneOptions ?? []
        return list.contains { $0.value == timezone } ? list : [.init(value: timezone, label: timezone)] + list
    }

    @ViewBuilder private var scheduleSection: some View {
        Section {
            Picker("Repeats", selection: $recType) {
                Text("No schedule").tag("")
                Text("Weekly").tag("weekly")
                Text("Monthly").tag("monthly_nth_weekday")
            }
            .accessibilityIdentifier("details.repeats")
            if !recType.isEmpty {
                Picker("Day", selection: $weekday) {
                    ForEach(Self.weekdays, id: \.self) { Text($0.capitalized).tag($0) }
                }
                if recType == "weekly" {
                    Picker("Every", selection: $frequency) {
                        Text("Week").tag(1)
                        Text("Other week").tag(2)
                        Text("3 weeks").tag(3)
                        Text("4 weeks").tag(4)
                    }
                } else {
                    ForEach(Self.nths, id: \.0) { n, label in
                        Toggle(label, isOn: Binding(
                            get: { which.contains(n) },
                            set: { on in which = on ? which + [n] : which.filter { $0 != n } }))
                    }
                }
                TimeField(label: "Starts", time: $start)
                TimeField(label: "Ends", time: $end)
            }
        } header: {
            Text("Schedule")
        } footer: {
            VStack(alignment: .leading, spacing: 4) {
                if let unparsed = seed.unparsed {
                    Text("Couldn't read a schedule from \"\(unparsed)\". Set it here.").foregroundStyle(CeolTokens.warning)
                }
                Text(recurrence.summary)
            }
        }
    }

    @ViewBuilder private var advancedFields: some View {
        LabeledContent("Path") {
            TextField(generatedPath, text: Binding(get: { manualPath ?? "" }, set: { manualPath = $0.isEmpty ? nil : $0 }))
                .multilineTextAlignment(.trailing)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .accessibilityIdentifier("details.path")
        }
        TextField("thesession.org session link or id", text: $thesessionID)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
        TextField("Venue phone", text: $phone).keyboardType(.phonePad)
        TextField("Venue website", text: $website).keyboardType(.URL).textInputAutocapitalization(.never)
        TextField("Started (YYYY-MM-DD)", text: $inceptionDate).keyboardType(.numbersAndPunctuation)
        Toggle("A festival (several sessions share a date)", isOn: $festival)
        LabeledContent("On now: minutes before") {
            TextField("60", text: $bufferBefore).keyboardType(.numberPad).multilineTextAlignment(.trailing)
        }
        LabeledContent("On now: minutes after") {
            TextField("60", text: $bufferAfter).keyboardType(.numberPad).multilineTextAlignment(.trailing)
        }
        Toggle("Show the people list", isOn: $showPeople)
        Toggle("Track attendance", isOn: $trackAttendance)
            .onChange(of: trackAttendance) { _, on in if !on { trackStarters = false } }
        Toggle("Track who starts sets", isOn: $trackStarters).disabled(!trackAttendance)
    }

    private func applySeed() {
        guard !loaded else { return }
        loaded = true
        name = seed.name
        venue = seed.venue
        city = seed.city
        state = seed.state
        country = seed.country
        timezone = seed.timezone ?? options?.defaultTimezone ?? "America/Chicago"
        thesessionID = seed.thesessionID
        phone = seed.phone
        website = seed.website
        inceptionDate = seed.inceptionDate
        if let s = seed.schedule {
            recType = s.kind.rawValue
            weekday = s.weekday
            frequency = s.everyNWeeks ?? 1
            which = s.which ?? []
            start = s.startTime
            end = s.endTime
        }
    }

    private func trimmed(_ s: String) -> String { s.trimmingCharacters(in: .whitespacesAndNewlines) }

    private func save() async {
        failure = nil
        let missing = [("Name", name), ("City", city), ("State", state), ("Country", country)]
            .filter { trimmed($0.1).isEmpty }.map(\.0)
        if !missing.isEmpty {
            failure = "Please fill in required fields: \(missing.joined(separator: ", "))"
            return
        }
        let checked = SessionPath.normalize(path)
        guard let finalPath = checked.path else {
            failure = checked.error
            advanced = true
            if manualPath == nil { manualPath = path }
            return
        }
        if !trimmed(thesessionID).isEmpty && TheSession.sessionID(thesessionID) == nil {
            failure = "Enter a thesession.org session URL (thesession.org/sessions/1234) or numeric ID"
            advanced = true
            return
        }
        guard let before = Int(trimmed(bufferBefore)), let after = Int(trimmed(bufferAfter)), before >= 0, after >= 0 else {
            failure = "Minutes before and after must be whole numbers of minutes"
            advanced = true
            return
        }
        if !recType.isEmpty && recurrence.json == nil {
            failure = recurrence.summary
            return
        }
        saving = true
        defer { saving = false }
        func optional(_ s: String) -> String? { trimmed(s).isEmpty ? nil : trimmed(s) }
        let body = Operations.AddSession.Input.Body.JsonPayload(
            name: trimmed(name), path: finalPath, city: trimmed(city), state: trimmed(state), country: trimmed(country),
            thesessionId: optional(thesessionID), locationName: optional(venue), locationPhone: optional(phone),
            locationWebsite: optional(website), inceptionDate: optional(inceptionDate), timezone: timezone,
            sessionType: festival ? .festival : .regular, activeBufferMinutesBefore: before,
            activeBufferMinutesAfter: after, recurrence: recurrence.json, addCurrentUser: addMe,
            addCurrentUserRole: addMe ? (addMeAsAdmin ? .admin : .member) : nil, showPeopleList: showPeople,
            trackAttendance: trackAttendance, trackSetStarters: trackStarters && trackAttendance)
        do {
            switch try await model.auth.client.addSession(body: .json(body)) {
            case .ok(let ok): onCreated(try ok.body.json.sessionPath, trimmed(name))
            case .default(_, let e): failure = refusal(e) ?? "Failed to save session"
            }
        } catch {
            failure = "Couldn't reach Ceol, so the session wasn't saved. Check your connection and try again."
        }
    }
}

/// An "HH:MM" string edited as a time.
private struct TimeField: View {
    let label: String
    @Binding var time: String

    private static let format: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "HH:mm"
        return f
    }()

    var body: some View {
        DatePicker(
            label,
            selection: Binding(
                get: { Self.format.date(from: time) ?? Self.format.date(from: "19:00")! },
                set: { time = Self.format.string(from: $0) }),
            displayedComponents: .hourAndMinute)
    }
}
