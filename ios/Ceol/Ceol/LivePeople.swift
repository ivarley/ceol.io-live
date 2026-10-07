// Who's there, on a night (plan Phase 5e), as the web logger shows it (App.svelte,
// lib/PersonPicker.svelte), with the rules in CeolLogic.People, held to the web's
// people.fixtures.json:
//
//   - The header: each person logging now as their colour and initials (dimmed once
//     they've gone, for an hour; a small count for two devices).
//   - Tap the header for the details: who's logging (and who was), and who's attending,
//     with Manage.
//   - Above the box while logging: "Sarah O'Connor is typing…".
//   - One people picker, three jobs: attendance (check in, check out, add someone), a
//     set's starter (checking them in first), and Assign for picked sets.

import CeolDesign
import CeolLogic
import SwiftUI

extension Color {
    /// "#4f9dff"
    init(hex: String) {
        let v = UInt32(hex.dropFirst(), radix: 16) ?? 0
        self.init(red: Double((v >> 16) & 0xff) / 255, green: Double((v >> 8) & 0xff) / 255, blue: Double(v & 0xff) / 255)
    }

    /// A player's colour, by their per-session index.
    static func player(_ seq: Int) -> Color { Color(hex: People.color(seq)) }
}

/// The people logging now, as coloured initials.
struct PresenceAvatars: View {
    let roster: [JSONValue]

    var body: some View {
        HStack(spacing: 4) {
            ForEach(Array(roster.enumerated()), id: \.offset) { _, p in
                let name = p["name"]?.stringValue ?? ""
                let away = p["away"] == true
                let devices = p["devices"]?.intValue ?? 1
                HStack(spacing: 0) {
                    Text(People.initials(name)).font(.ceol(size: 11, weight: .bold))
                    if !away && devices > 1 { Text("\(devices)").font(.ceol(size: 8, weight: .bold)).baselineOffset(5) }
                }
                .foregroundStyle(.white)
                .padding(.horizontal, 4)
                .frame(minWidth: 24, minHeight: 24)
                .background(Color.player(p["arrival_seq"]?.intValue ?? 0), in: Capsule())
                .opacity(away ? 0.4 : 1)
                .saturation(away ? 0.65 : 1)
                .accessibilityLabel(name + (away ? " " + tr("(away)") : devices > 1 ? " " + tr("(\(devices) devices)") : ""))
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("presence")
    }
}

/// The header's details: who's logging, and who's attending (with Manage).
struct NightPeopleDetails: View {
    let model: NightModel
    let onManage: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if !model.roster.isEmpty {
                let here = model.roster.filter { $0["away"] != true }.compactMap { $0["name"]?.stringValue }
                let away = model.roster.filter { $0["away"] == true }.compactMap { $0["name"]?.stringValue }
                row(tr("Logging")) {
                    (Text(here.isEmpty ? tr("No one right now") : here.joined(separator: ", "))
                        + Text(away.isEmpty ? "" : " · " + tr("away: \(away.joined(separator: ", "))")).foregroundColor(CeolTokens.textMuted.opacity(0.75)))
                        .font(.ceol(size: 15)).foregroundStyle(CeolTokens.textColor)
                }
            }
            if model.trackAttendance {
                let checkedIn = model.people.filter { $0["attending"] == true }
                row(attendingLabel) {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 10) {
                            Text("\(checkedIn.count)").font(.ceol(size: 15, weight: .bold)).foregroundStyle(CeolTokens.textColor)
                            Button("Manage", action: onManage)
                                .font(.ceol(size: 14, weight: .semibold)).foregroundStyle(CeolTokens.primary)
                                .accessibilityIdentifier("attendance.manage")
                        }
                        Text(checkedIn.isEmpty ? tr("No one checked in yet") : checkedIn.compactMap { $0["display_name"]?.stringValue }.joined(separator: ", "))
                            .font(.ceol(size: 15)).foregroundStyle(checkedIn.isEmpty ? CeolTokens.textMuted : CeolTokens.textColor)
                    }
                }
            }
        }
        .task { if model.trackAttendance && !model.peopleLoaded { await model.loadPeople() } }
    }

    /// "Attended" for a night gone by, "Attending" otherwise.
    private var attendingLabel: String {
        guard let d = model.night?["instance_date"]?.stringValue else { return tr("Attending") }
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return d < f.string(from: Date()) ? tr("Attended") : tr("Attending")
    }

    private func row(_ key: String, @ViewBuilder _ value: () -> some View) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(key).font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted).frame(width: 84, alignment: .leading)
            value()
        }
    }
}

/// "Sarah O'Connor, Ian Varley are typing…", in their colours.
struct TypingLine: View {
    let model: NightModel

    var body: some View {
        let others = People.othersTyping(model.typers, me: model.me)
        if !others.isEmpty {
            others.enumerated().reduce(Text("")) { line, item in
                let (i, t) = item
                return line + Text(i > 0 ? ", " : "")
                    + Text(t["name"]?.stringValue ?? "").bold().foregroundColor(.player(t["arrival_seq"]?.intValue ?? 0))
            }
            + (others.count == 1 ? Text(" is typing…") : Text(" are typing…"))
        }
    }
}

// MARK: - The people picker

struct PersonPicker: View {
    enum Mode {
        /// Check people in and out; add someone.
        case attendance
        /// Who started this set: checks them in first if they aren't.
        case starter(tunes: [LogRecord], current: String?)
        /// Assign the picked sets: checked-in people only.
        case assign
    }

    @Environment(\.dismiss) private var dismiss
    let model: NightModel
    let mode: Mode
    @State private var query = ""
    @State private var creating = false

    var body: some View {
        NavigationStack {
            Group {
                if creating {
                    NewPersonForm(app: model.app, name: People.splitName(query), create: { first, last, email, instruments in
                        await model.createPerson(first: first, last: last, email: email, instruments: instruments)
                    }) { person in
                        creating = false
                        query = ""
                        if let person { chose(person, isNew: true) }
                    }
                } else {
                    list
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if creating {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Back to list") { creating = false }.accessibilityIdentifier("people.back")
                    }
                } else {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { dismiss() }.accessibilityIdentifier("people.done")
                    }
                }
            }
        }
        .ceolDrawer([.medium, .large])
        .task { if !model.peopleLoaded { await model.loadPeople() } }
    }

    private var title: String {
        switch mode {
        case .attendance: tr("Attendance")
        case .starter: tr("Who started this set?")
        case .assign: tr("Sets started by…")
        }
    }

    private var list: some View {
        let tiers = People.pickerTiers(model.people, query: query)
        let assign = if case .assign = mode { true } else { false }
        let q = query.trimmingCharacters(in: .whitespaces)
        return List {
            if case .starter(_, let current) = mode, current != nil, q.isEmpty {
                Button("— Clear —") { choose(nil) }.foregroundStyle(CeolTokens.textMuted)
            }
            if case .assign = mode, q.isEmpty {
                Button("— Clear —") { choose(nil) }.foregroundStyle(CeolTokens.textMuted)
            }
            if !model.peopleLoaded {
                ProgressView().frame(maxWidth: .infinity)
            } else if tiers.here.isEmpty && (assign || (tiers.roster.isEmpty && tiers.archived.isEmpty)) {
                Text(assign ? tr("No one checked in yet.") : q.isEmpty ? tr("No one on this session's list yet.") : tr("No one here by that name."))
                    .foregroundStyle(CeolTokens.textMuted)
            }
            if !tiers.here.isEmpty {
                Section("Checked in") { ForEach(tiers.here, id: \.self) { row($0, tier: .here) } }
            }
            if !assign {
                if !tiers.roster.isEmpty {
                    Section("Not checked in") { ForEach(tiers.roster, id: \.self) { row($0, tier: .roster) } }
                }
                if !tiers.archived.isEmpty {
                    Section("Archived") { ForEach(tiers.archived, id: \.self) { row($0, tier: .archived) } }
                }
                if !q.isEmpty {
                    Button { creating = true } label: {
                        Text("＋ Add \(Text(q).bold())").foregroundStyle(CeolTokens.primary)
                    }
                    .accessibilityIdentifier("people.add")
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(CeolTokens.drawerBg)
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: assign ? tr("Filter players…") : tr("Filter or add someone…"))
        .autocorrectionDisabled()
    }

    private enum Tier { case here, roster, archived }

    private func row(_ p: JSONValue, tier: Tier) -> some View {
        HStack {
            Button { choose(p) } label: {
                HStack(spacing: 8) {
                    Text(p["display_name"]?.stringValue ?? "").foregroundStyle(CeolTokens.textColor)
                        .italic(tier == .archived)
                    if p["archived"] == true { Pill(text: tr("archived")) }
                    if p["relationship"] == "visitor" { Pill(text: tr("visitor")) }
                    Spacer()
                    if case .starter(_, let current) = mode, current == NightModel.starterName(p) {
                        Image(systemName: "checkmark").foregroundStyle(CeolTokens.primary)
                    }
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("people.person")
            if case .attendance = mode, tier == .here {
                Button { Task { await model.checkOut(p) } } label: {
                    Image(systemName: "xmark").foregroundStyle(CeolTokens.textMuted)
                }
                .buttonStyle(.borderless)
                .accessibilityLabel("Check out \(p["display_name"]?.stringValue ?? "")")
                .accessibilityIdentifier("people.checkOut")
            }
        }
        .opacity(tier == .roster ? 0.62 : tier == .archived ? 0.45 : 1)
    }

    private func choose(_ p: JSONValue?) { chose(p, isNew: false) }

    private func chose(_ p: JSONValue?, isNew: Bool) {
        switch mode {
        case .attendance:
            // Tapping someone checks them in (someone new already is); the list stays.
            if let p, !isNew, p["attending"] != true { Task { await model.checkIn(p) } }
            query = ""
        case .starter(let tunes, _):
            Task {
                if let p, !isNew, p["attending"] != true { await model.checkIn(p) }
                model.setStarter(of: tunes, person: p)
            }
            dismiss()
        case .assign:
            model.assignPicked(to: p)
            dismiss()
        }
    }
}

/// Someone new: name, email (links an account), instruments. On a night they are checked
/// in on adding; on a session's People tab they join its list.
struct NewPersonForm: View {
    let app: AppModel
    /// Saves them: the new person, nil when it didn't work and the caller has said so,
    /// or a thrown error whose description the form shows.
    let create: (_ first: String, _ last: String, _ email: String, _ instruments: [String]) async throws -> JSONValue?
    /// A session's list needs both names; a night takes a first name alone.
    var needsLastName = false
    let onDone: (JSONValue?) -> Void
    @State private var first: String
    @State private var last: String
    @State private var email = ""
    @State private var chosen: [String] = []
    @State private var other = ""
    @State private var canonical: [String] = []
    @State private var busy = false
    @State private var failure: String?

    init(
        app: AppModel, name: (first: String, last: String), needsLastName: Bool = false,
        create: @escaping (_ first: String, _ last: String, _ email: String, _ instruments: [String]) async throws -> JSONValue?,
        onDone: @escaping (JSONValue?) -> Void
    ) {
        self.app = app
        self.create = create
        self.needsLastName = needsLastName
        self.onDone = onDone
        _first = State(initialValue: name.first)
        _last = State(initialValue: name.last)
    }

    var body: some View {
        Form {
            Section {
                TextField("First name", text: $first).accessibilityIdentifier("newPerson.first")
                TextField("Last name", text: $last).accessibilityIdentifier("newPerson.last")
                TextField("Email (optional)", text: $email).keyboardType(.emailAddress).textInputAutocapitalization(.never)
            } footer: {
                VStack(alignment: .leading, spacing: 6) {
                    Text("If they already have an account, their email links them to it.")
                    if let failure { Text(failure).foregroundStyle(CeolTokens.danger) }
                }
            }
            Section("Instruments (optional)") {
                FlowLayout(spacing: 6) {
                    ForEach(canonical + chosen.filter { c in !canonical.contains { $0.lowercased() == c.lowercased() } }, id: \.self) { i in
                        let on = chosen.contains(i)
                        Button(instrumentName(i)) { if on { chosen.removeAll { $0 == i } } else { chosen.append(i) } }
                            .font(.ceol(size: 14))
                            .foregroundStyle(on ? .white : CeolTokens.textColor)
                            .padding(.horizontal, 10).padding(.vertical, 5)
                            .background(on ? CeolTokens.primaryFill : Color.clear, in: Capsule())
                            .overlay(Capsule().strokeBorder(CeolTokens.borderColor, lineWidth: on ? 0 : 1))
                            .buttonStyle(.plain)
                    }
                }
                HStack {
                    TextField("Other instrument…", text: $other)
                    Button("Add") {
                        let o = other.trimmingCharacters(in: .whitespaces)
                        if !o.isEmpty && !chosen.contains(o) { chosen.append(o) }
                        other = ""
                    }
                    .disabled(other.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
        .toolbar {
            // Always in reach, as the web's footer button is.
            ToolbarItem(placement: .confirmationAction) {
                Button(busy ? tr("Adding…") : tr("Add person")) {
                    busy = true
                    failure = nil
                    Task {
                        do {
                            let p = try await create(
                                first.trimmingCharacters(in: .whitespaces), last.trimmingCharacters(in: .whitespaces),
                                email.trimmingCharacters(in: .whitespaces), chosen)
                            busy = false
                            onDone(p)
                        } catch {
                            busy = false
                            failure = (error as? LocalizedError)?.errorDescription ?? tr("That person wasn't added. Try again.")
                        }
                    }
                }
                .disabled(first.trimmingCharacters(in: .whitespaces).isEmpty
                    || (needsLastName && last.trimmingCharacters(in: .whitespaces).isEmpty) || busy)
                .accessibilityIdentifier("newPerson.add")
            }
        }
        .scrollContentBackground(.hidden)
        .background(CeolTokens.drawerBg)
        .task {
            canonical = (try? await app.getJSON("/api/me/profile"))?["canonical_instruments"]?.arrayValue?.compactMap(\.stringValue) ?? []
        }
    }
}

/// Other people's changes, a line each in their colour, under the header.
struct ActivityLines: View {
    let model: NightModel

    var body: some View {
        VStack(spacing: 6) {
            // While watching, passing messages show here (editing, above the composer).
            if !model.editing, let flash = model.flash {
                Text(flash)
                    .font(.ceol(size: 13, weight: .semibold)).foregroundStyle(CeolTokens.textColor)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 14).padding(.vertical, 6)
                    .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                    .padding(.horizontal, 16)
                    .accessibilityIdentifier("toast.flash")
            }
            ForEach(model.activities) { a in
                Text(a.text)
                    .font(.ceol(size: 13, weight: .semibold))
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 14).padding(.vertical, 5)
                    .background(a.color.map(Color.player) ?? CeolTokens.textMuted, in: RoundedRectangle(cornerRadius: 10))
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .accessibilityIdentifier("activity")
            }
        }
        .padding(.top, 8)
        .animation(.easeOut(duration: 0.24), value: model.activities)
        .allowsHitTesting(false)
    }
}

extension View {
    /// A ring in someone's colour while their change is fresh (the web's flash-remote).
    func remoteFlash(_ model: NightModel, _ id: RecordID?) -> some View {
        let color: Color? = id.flatMap { model.flashes[$0] }.map { $0.map(Color.player) ?? CeolTokens.primary }
        return overlay {
            RoundedRectangle(cornerRadius: 6)
                .strokeBorder(color ?? .clear, lineWidth: 3)
                .opacity(color == nil ? 0 : 1)
                .animation(.easeOut(duration: color == nil ? 1.0 : 0.1), value: color == nil)
                .allowsHitTesting(false)
        }
    }
}
